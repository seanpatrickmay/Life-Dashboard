"""AI Digest pipeline: fetch, normalize, deduplicate, store."""
from __future__ import annotations

import asyncio
import hashlib
import re
from calendar import timegm
from datetime import datetime, timedelta, timezone
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
    {
        "url": "https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml",
        "name": "Anthropic News",
        "category": "claude-anthropic",
    },
    {
        "url": "https://deepmind.google/blog/rss.xml",
        "name": "Google DeepMind",
        "category": "google-ai",
    },
    {
        "url": "https://api.cursor-changelog.com/api/versions/rss",
        "name": "Cursor Changelog",
        "category": "developer-tools",
    },
    {
        "url": "https://github.com/cline/cline/releases.atom",
        "name": "Cline Releases",
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


# ── Jaccard Title Dedup ───────────────────────────────────────────────

_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "will", "would", "could", "should", "may", "can",
    "this", "that", "these", "those", "it", "its", "new", "now",
})

_SOURCE_QUALITY: dict[str, int] = {
    "Claude Code Releases": 10,
    "OpenAI Blog": 9,
    "Google DeepMind": 9,
    "Anthropic News": 8,
    "GitHub Copilot": 8,
    "Cursor Changelog": 7,
    "Cline Releases": 7,
    "Import AI": 6,
    "TLDR AI": 5,
}

JACCARD_THRESHOLD = 0.45


def _extract_significant_words(title: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if len(w) >= 4 and w not in _STOPWORDS}


def jaccard_title_similarity(title_a: str, title_b: str) -> float:
    words_a = _extract_significant_words(title_a)
    words_b = _extract_significant_words(title_b)
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def deduplicate_by_title(items: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for item in items:
        is_dup = False
        for i, existing in enumerate(kept):
            if jaccard_title_similarity(item["title"], existing["title"]) >= JACCARD_THRESHOLD:
                item_quality = _SOURCE_QUALITY.get(item["source_name"], 0)
                existing_quality = _SOURCE_QUALITY.get(existing["source_name"], 0)
                if item_quality > existing_quality:
                    kept[i] = item
                is_dup = True
                break
        if not is_dup:
            kept.append(item)
    return kept


# ── Feed Parsing ──────────────────────────────────────────────────────

def _content_hash(title: str, url: str) -> str:
    return hashlib.sha256(f"{title}|{url}".encode()).hexdigest()[:16]


def _parse_published(entry: dict) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)
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

        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "LifeDashboard/1.0"},
        ) as client:
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

        unique_items = deduplicate_by_title(unique_items)

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
