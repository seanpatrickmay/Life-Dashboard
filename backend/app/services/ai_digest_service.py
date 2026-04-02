"""AI Digest pipeline: fetch, normalize, deduplicate, store."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from time import mktime
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import feedparser
import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ai_digest import DigestItem
from app.utils.timezone import eastern_now

# ── Feed Configuration ────────────────────────────────────────────────

FEED_SOURCES = [
    {
        "url": "https://github.com/anthropics/claude-code/releases.atom",
        "name": "Claude Code Releases",
        "category": "claude-anthropic",
    },
    {
        "url": "https://openai.com/news/rss.xml",
        "name": "OpenAI Blog",
        "category": "openai",
    },
    {
        "url": "https://tldr.tech/api/rss/ai",
        "name": "TLDR AI",
        "category": "aggregator",
    },
    {
        "url": "https://importai.substack.com/feed",
        "name": "Import AI",
        "category": "analysis",
    },
    {
        "url": "https://github.blog/changelog/label/copilot/feed/",
        "name": "GitHub Copilot",
        "category": "developer-tools",
    },
]

_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "source", "fbclid", "gclid", "mc_cid", "mc_eid",
})

STALENESS_HOURS = 6


# ── URL Normalization ─────────────────────────────────────────────────

def normalize_url(raw_url: str) -> str:
    """Normalize a URL for deduplication: lowercase, strip tracking params, remove www."""
    parsed = urlparse(raw_url.strip())
    scheme = parsed.scheme.lower()
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/").lower() or ""
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered = {k: v for k, v in query_params.items() if k.lower() not in _TRACKING_PARAMS}
    query = urlencode(filtered, doseq=True) if filtered else ""
    return urlunparse((scheme, host, path, "", query, ""))


# ── Feed Parsing ──────────────────────────────────────────────────────

def _content_hash(title: str, url: str) -> str:
    return hashlib.sha256(f"{title}|{url}".encode()).hexdigest()[:16]


def _parse_published(entry: dict) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime.fromtimestamp(mktime(parsed)).astimezone()
            except (TypeError, ValueError, OverflowError):
                continue
    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text).strip()


async def fetch_single_feed(
    client: httpx.AsyncClient,
    source: dict,
) -> list[dict]:
    """Fetch and parse a single RSS/Atom feed. Returns normalized entry dicts."""
    url = source["url"]
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch feed {}: {}", source["name"], exc)
        return []

    feed = feedparser.parse(resp.text)
    if feed.bozo and not feed.entries:
        logger.warning("Malformed feed from {}: {}", source["name"], feed.bozo_exception)
        return []

    items = []
    for entry in feed.entries:
        entry_url = entry.get("link", "")
        if not entry_url:
            continue
        title = entry.get("title", "").strip()
        if not title:
            continue
        summary = entry.get("summary", "") or entry.get("description", "")
        if summary and "<" in summary:
            summary = _strip_html(summary)
        if len(summary) > 500:
            summary = summary[:497] + "..."

        items.append({
            "url": entry_url,
            "normalized_url": normalize_url(entry_url),
            "title": title,
            "summary": summary or None,
            "source_name": source["name"],
            "source_feed_url": source["url"],
            "category": source["category"],
            "published_at": _parse_published(entry),
            "content_hash": _content_hash(title, entry_url),
        })

    logger.info("Fetched {} items from {}", len(items), source["name"])
    return items


# ── Pipeline ──────────────────────────────────────────────────────────

class AIDigestService:
    """Orchestrates the feed aggregation pipeline."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_stale(self) -> bool:
        cutoff = eastern_now() - timedelta(hours=STALENESS_HOURS)
        result = await self._session.execute(
            select(DigestItem.id).where(DigestItem.fetched_at > cutoff).limit(1)
        )
        return result.scalar_one_or_none() is None

    async def get_latest_refresh_time(self) -> datetime | None:
        result = await self._session.execute(
            select(DigestItem.fetched_at).order_by(DigestItem.fetched_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_today_items(self) -> list[DigestItem]:
        cutoff = eastern_now() - timedelta(hours=36)
        result = await self._session.execute(
            select(DigestItem)
            .where(DigestItem.fetched_at > cutoff)
            .order_by(DigestItem.published_at.desc().nullslast(), DigestItem.fetched_at.desc())
            .limit(50)
        )
        return list(result.scalars().all())

    async def run_pipeline(self) -> int:
        now = eastern_now()
        all_items: list[dict] = []

        async with httpx.AsyncClient(timeout=15.0) as client:
            import asyncio
            tasks = [fetch_single_feed(client, source) for source in FEED_SOURCES]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning("Feed fetch failed: {}", result)
                continue
            all_items.extend(result)

        if not all_items:
            logger.warning("No items fetched from any feed")
            return 0

        seen_urls: set[str] = set()
        unique_items: list[dict] = []
        for item in all_items:
            if item["normalized_url"] not in seen_urls:
                seen_urls.add(item["normalized_url"])
                unique_items.append(item)

        new_count = 0
        for item in unique_items:
            item["fetched_at"] = now
            stmt = (
                pg_insert(DigestItem)
                .values(**item)
                .on_conflict_do_nothing(index_elements=["normalized_url"])
            )
            result = await self._session.execute(stmt)
            if result.rowcount > 0:
                new_count += 1

        await self._session.commit()
        logger.info("Digest pipeline complete: {} new items from {} total", new_count, len(unique_items))
        return new_count
