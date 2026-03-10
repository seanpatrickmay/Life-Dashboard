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

from dotenv import load_dotenv
from sqlalchemy import text


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

from app.db.session import AsyncSessionLocal  # type: ignore  # noqa: E402
from app.services.imessage_processing_service import IMessageProcessingService  # type: ignore  # noqa: E402


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


async def main() -> None:
    args = parse_args()
    since_utc = (
        datetime.now(timezone.utc) - timedelta(days=args.lookback_days)
        if args.lookback_days > 0
        else None
    )

    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(text("SET TRANSACTION READ ONLY"))
            preview = await IMessageProcessingService(session).preview_messages(
                user_id=args.user_id,
                time_zone=args.time_zone,
                max_messages=args.max_messages,
                message_scope=args.message_scope,
                since_utc=since_utc,
                conversation_id=args.conversation_id,
            )
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
