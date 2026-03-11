#!/usr/bin/env python3
"""Preview iMessage replay suggestions without mutating the database."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import or_, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import selectinload


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

host_db_url = os.getenv("DATABASE_URL_HOST")
database_url = os.getenv("DATABASE_URL")
if not database_url and host_db_url:
    async_database_url = host_db_url
    if async_database_url.startswith("postgresql://"):
        async_database_url = async_database_url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    os.environ["DATABASE_URL"] = async_database_url

sys.path.append(str(ROOT / "backend"))

from app.db.models.imessage import IMessageConversation, IMessageMessage  # type: ignore  # noqa: E402
from app.db.session import AsyncSessionLocal  # type: ignore  # noqa: E402
from app.services.imessage_processing_service import (  # type: ignore  # noqa: E402
    IMessageProcessingService,
    cluster_messages,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview iMessage processing suggestions without updating the database."
    )
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--time-zone", default="America/New_York")
    parser.add_argument(
        "--message-scope",
        choices=("processed", "pending", "all"),
        default="processed",
        help="Which messages to preview. 'processed' is the usual replay dry-run.",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=250,
        help="Maximum messages to preview. Use 0 for no limit.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=90,
        help="Limit the preview to messages within the trailing N days. Use 0 for no time cutoff.",
    )
    parser.add_argument("--conversation-id", type=int, default=None)
    parser.add_argument(
        "--approved-only",
        action="store_true",
        help="Only keep actions the judge approved in the output.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional file path to write the JSON preview to.",
    )
    return parser.parse_args()


def _filter_preview(preview: dict, *, approved_only: bool) -> dict:
    if not approved_only:
        return preview
    filtered_clusters = []
    approved_actions = 0
    rejected_actions = 0
    for cluster in preview.get("clusters", []):
        actions = [action for action in cluster.get("actions", []) if action.get("approved")]
        if not actions:
            continue
        approved_actions += len(actions)
        filtered_clusters.append({**cluster, "actions": actions, "counts": {
            "suggested": len(actions),
            "approved": len(actions),
            "rejected": 0,
        }})
    summary = dict(preview.get("summary") or {})
    summary["clusters_considered"] = len(filtered_clusters)
    summary["suggested_actions"] = approved_actions
    summary["approved_actions"] = approved_actions
    summary["rejected_actions"] = rejected_actions
    return {**preview, "summary": summary, "clusters": filtered_clusters}


def _is_transient_db_error(exc: Exception) -> bool:
    if not isinstance(exc, DBAPIError):
        return False
    detail = str(exc).lower()
    return "connection was closed in the middle of operation" in detail or "connection reset by peer" in detail


async def _load_preview_seed(
    *,
    user_id: int,
    time_zone: str,
    max_messages: int,
    message_scope: str,
    since_utc: datetime | None,
    conversation_id: int | None,
) -> tuple[list[Any], list[IMessageMessage]]:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("SET TRANSACTION READ ONLY"))
            service = IMessageProcessingService(session)
            projects = await service.project_repo.list_for_user(user_id, include_archived=False)
            project_catalog = await service._build_project_catalog(user_id=user_id, projects=projects)
            stmt = (
                select(IMessageMessage)
                .options(
                    selectinload(IMessageMessage.conversation).selectinload(IMessageConversation.participants)
                )
                .where(IMessageMessage.user_id == user_id)
                .order_by(IMessageMessage.sent_at_utc.asc().nullslast(), IMessageMessage.id.asc())
            )
            if message_scope == "pending":
                stmt = stmt.where(IMessageMessage.processed_at_utc.is_(None))
            elif message_scope == "processed":
                stmt = stmt.where(IMessageMessage.processed_at_utc.is_not(None))
            if conversation_id is not None:
                stmt = stmt.where(IMessageMessage.conversation_id == conversation_id)
            if since_utc is not None:
                stmt = stmt.where(
                    or_(
                        IMessageMessage.sent_at_utc >= since_utc,
                        (
                            IMessageMessage.sent_at_utc.is_(None)
                            & (IMessageMessage.created_at >= since_utc)
                        ),
                    )
                )
            if max_messages > 0:
                stmt = stmt.limit(max_messages)
            result = await session.execute(stmt)
            messages = list(result.scalars().all())
    return project_catalog, messages


async def _preview_cluster_with_retry(
    *,
    cluster,
    project_catalog: list[Any],
    user_id: int,
    time_zone: str,
    max_attempts: int = 3,
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await session.execute(text("SET TRANSACTION READ ONLY"))
                    service = IMessageProcessingService(session)
                    return await service._preview_cluster(
                        cluster=cluster,
                        project_catalog=project_catalog,
                        time_zone=time_zone,
                        user_id=user_id,
                    )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= max_attempts or not _is_transient_db_error(exc):
                raise
            await asyncio.sleep(1.5 * attempt)
    assert last_exc is not None
    raise last_exc


async def main() -> None:
    args = parse_args()
    since_utc = (
        datetime.now(timezone.utc) - timedelta(days=args.lookback_days)
        if args.lookback_days > 0
        else None
    )

    project_catalog, messages = await _load_preview_seed(
        user_id=args.user_id,
        time_zone=args.time_zone,
        max_messages=args.max_messages,
        message_scope=args.message_scope,
        since_utc=since_utc,
        conversation_id=args.conversation_id,
    )
    clusters = cluster_messages(messages)
    cluster_previews: list[dict[str, Any]] = []
    total_suggested_actions = 0
    total_approved_actions = 0
    total_rejected_actions = 0
    for index, cluster in enumerate(clusters, start=1):
        preview = await _preview_cluster_with_retry(
            cluster=cluster,
            project_catalog=project_catalog,
            user_id=args.user_id,
            time_zone=args.time_zone,
        )
        cluster_previews.append(preview)
        total_suggested_actions += int(preview["counts"]["suggested"])
        total_approved_actions += int(preview["counts"]["approved"])
        total_rejected_actions += int(preview["counts"]["rejected"])
        print(
            json.dumps(
                {
                    "cluster": index,
                    "of": len(clusters),
                    "suggested": preview["counts"]["suggested"],
                    "approved": preview["counts"]["approved"],
                    "rejected": preview["counts"]["rejected"],
                }
            ),
            flush=True,
        )

    preview = {
        "summary": {
            "user_id": args.user_id,
            "time_zone": args.time_zone,
            "message_scope": args.message_scope,
            "messages_considered": len(messages),
            "clusters_considered": len(cluster_previews),
            "suggested_actions": total_suggested_actions,
            "approved_actions": total_approved_actions,
            "rejected_actions": total_rejected_actions,
        },
        "clusters": cluster_previews,
    }
    preview = _filter_preview(preview, approved_only=args.approved_only)

    rendered = json.dumps(preview, ensure_ascii=False, indent=2, default=str)
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote dry-run preview to {output_path}")
        return
    print(rendered)


if __name__ == "__main__":
    asyncio.run(main())
