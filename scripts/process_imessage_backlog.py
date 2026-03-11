#!/usr/bin/env python3
"""Process pending iMessage rows until the backlog is drained."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import sys

from dotenv import load_dotenv
from sqlalchemy import func, select


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

from app.db.models.imessage import IMessageMessage  # type: ignore  # noqa: E402
from app.db.session import AsyncSessionLocal  # type: ignore  # noqa: E402
from app.services.imessage_processing_service import IMessageProcessingService  # type: ignore  # noqa: E402


_stop_requested = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process pending iMessage backlog.")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--time-zone", default="America/New_York")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Maximum pending messages to process per run.",
    )
    parser.add_argument(
        "--max-runs",
        type=int,
        default=0,
        help="Optional cap on processing runs. Use 0 for unlimited.",
    )
    return parser.parse_args()


async def _pending_count(user_id: int) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count())
            .select_from(IMessageMessage)
            .where(
                IMessageMessage.user_id == user_id,
                IMessageMessage.processed_at_utc.is_(None),
            )
        )
        return int(result.scalar_one() or 0)


async def main() -> None:
    args = parse_args()
    run_index = 0

    def _request_stop(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        global _stop_requested
        _stop_requested = True
        print(
            f"{datetime.now(timezone.utc).isoformat()} stop_requested "
            f"user_id={args.user_id} signal={signum}"
        )

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    while True:
        if _stop_requested:
            print(
                f"{datetime.now(timezone.utc).isoformat()} stopping "
                f"user_id={args.user_id} runs={run_index}"
            )
            return
        pending_before = await _pending_count(args.user_id)
        if pending_before == 0:
            print(
                f"{datetime.now(timezone.utc).isoformat()} backlog drained "
                f"user_id={args.user_id}"
            )
            return

        if args.max_runs and run_index >= args.max_runs:
            print(
                f"{datetime.now(timezone.utc).isoformat()} stopping early "
                f"user_id={args.user_id} runs={run_index} pending={pending_before}"
            )
            return

        run_index += 1
        async with AsyncSessionLocal() as session:
            run = await IMessageProcessingService(session).process_pending_messages(
                user_id=args.user_id,
                time_zone=args.time_zone,
                max_messages=args.batch_size,
            )
            print(
                f"{datetime.now(timezone.utc).isoformat()} run={run_index} "
                f"processing_run_id={run.id} status={run.status} "
                f"messages_considered={run.messages_considered} "
                f"clusters_processed={run.clusters_processed} "
                f"actions_applied={run.actions_applied} "
                f"error={run.error_message or ''}"
            )

        pending_after = await _pending_count(args.user_id)
        print(
            f"{datetime.now(timezone.utc).isoformat()} run={run_index} "
            f"pending_before={pending_before} pending_after={pending_after}"
        )

        if _stop_requested:
            print(
                f"{datetime.now(timezone.utc).isoformat()} stopping_after_run "
                f"user_id={args.user_id} run={run_index} pending={pending_after}"
            )
            return

        if pending_after == 0:
            print(
                f"{datetime.now(timezone.utc).isoformat()} backlog drained "
                f"user_id={args.user_id}"
            )
            return


if __name__ == "__main__":
    asyncio.run(main())
