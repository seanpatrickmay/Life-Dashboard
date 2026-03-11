#!/usr/bin/env python3
"""Backfill historical completion timestamps for iMessage-created todos."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv


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
from app.services.imessage_todo_reconciliation_service import (  # type: ignore  # noqa: E402
    IMessageTodoReconciliationService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile historical completions for iMessage-created todos.")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--time-zone", default="America/New_York")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--after-audit-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--max-followup-messages", type=int, default=200)
    parser.add_argument("--apply", action="store_true", help="Persist the reconciled completions.")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    since_utc = (
        datetime.now(timezone.utc) - timedelta(days=args.lookback_days)
        if args.lookback_days > 0
        else None
    )

    async with AsyncSessionLocal() as session:
        service = IMessageTodoReconciliationService(session)
        proposals = await service.list_completion_proposals(
            user_id=args.user_id,
            after_audit_id=args.after_audit_id,
            limit=args.limit,
            batch_size=args.batch_size,
            since_utc=since_utc,
            max_followup_messages=args.max_followup_messages,
        )

        payload = {
            "mode": "apply" if args.apply else "dry_run",
            "user_id": args.user_id,
            "time_zone": args.time_zone,
            "proposal_count": len(proposals),
            "proposals": [
                {
                    "todo_id": proposal.todo_id,
                    "conversation_id": proposal.conversation_id,
                    "source_audit_id": proposal.source_audit_id,
                    "completion_message_id": proposal.completion_message_id,
                    "completed_at_utc": proposal.completed_at_utc.isoformat(),
                    "completion_message_text": proposal.completion_message_text,
                    "score": round(proposal.score, 3),
                    "reason": proposal.reason,
                }
                for proposal in proposals
            ],
        }

        if args.output is not None:
            args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if args.apply:
            applied = 0
            for proposal in proposals:
                changed = await service.apply_proposal(
                    user_id=args.user_id,
                    proposal=proposal,
                    time_zone=args.time_zone,
                )
                if changed:
                    applied += 1
            await session.commit()
            payload["applied_count"] = applied
        else:
            await session.rollback()

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
