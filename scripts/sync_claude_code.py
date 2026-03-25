#!/usr/bin/env python3
"""Claude Code conversation log sync + processing runner."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# DATABASE_URL_HOST → async DATABASE_URL rewriting (matches sync_imessage.py pattern)
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

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.claude_code_sync_service import (  # noqa: E402
    ClaudeCodeSyncService,
    extract_session_content,
)
from app.services.claude_code_processing_service import (  # noqa: E402
    ClaudeCodeProcessingService,
    get_git_log_for_session,
)
from app.services.claude_code_project_resolver import ClaudeCodeProjectResolver  # noqa: E402
from app.utils.timezone import local_today  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sync_claude_code")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Claude Code history")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--time-zone", type=str, default="America/New_York")
    parser.add_argument(
        "--claude-dir",
        type=str,
        default=os.path.expanduser("~/.claude"),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _session_date(first_timestamp: str | None, time_zone: str) -> datetime:
    """Convert session timestamp to local date, respecting timezone."""
    if not first_timestamp:
        return local_today(time_zone)
    try:
        ts_str = first_timestamp
        if isinstance(ts_str, str):
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        else:
            ts = datetime.fromtimestamp(ts_str / 1000, tz=timezone.utc)
        # Convert to local timezone
        import zoneinfo
        local_tz = zoneinfo.ZoneInfo(time_zone)
        return ts.astimezone(local_tz).date()
    except (ValueError, AttributeError, KeyError):
        return local_today(time_zone)


async def main() -> None:
    args = parse_args()
    claude_dir = Path(args.claude_dir)

    if not claude_dir.exists():
        logger.error("Claude directory not found: %s", claude_dir)
        sys.exit(1)

    logger.info("Starting Claude Code sync: user_id=%d, claude_dir=%s", args.user_id, claude_dir)

    async with AsyncSessionLocal() as session:
        sync_service = ClaudeCodeSyncService(session)
        processing_service = ClaudeCodeProcessingService(session)
        resolver = ClaudeCodeProjectResolver(session)

        unprocessed = await sync_service.find_unprocessed_sessions(
            user_id=args.user_id,
            claude_dir=claude_dir,
        )
        logger.info("Found %d unprocessed/updated sessions", len(unprocessed))

        if not unprocessed:
            logger.info("Nothing to process. Done.")
            return

        projects_with_new_activity: set[int] = set()

        for session_info, session_file in unprocessed:
            try:
                logger.info("Processing session %s (project: %s)", session_info.session_id, session_info.project_path)

                content = extract_session_content(session_file)
                if not content.user_messages:
                    logger.info("Session %s has no user messages, skipping", session_info.session_id)
                    continue

                project_path = content.project_path or session_info.project_path

                project = await resolver.resolve(
                    user_id=args.user_id,
                    project_path=project_path,
                )

                git_log = get_git_log_for_session(
                    project_path,
                    content.first_timestamp,
                    content.last_timestamp,
                )

                summary_data = await processing_service.summarize_session(content, git_log=git_log)

                session_date = _session_date(content.first_timestamp, args.time_zone)

                if not args.dry_run:
                    await processing_service.upsert_project_activity(
                        user_id=args.user_id,
                        project_id=project.id,
                        session_id=session_info.session_id,
                        local_date=session_date,
                        summary=summary_data["summary"],
                        details_json=summary_data,
                        source_project_path=project_path,
                    )

                    await processing_service.upsert_journal_entry(
                        user_id=args.user_id,
                        project_name=project.name,
                        local_date=session_date,
                        summary=summary_data["summary"],
                        time_zone=args.time_zone,
                    )

                    file_mtime = os.path.getmtime(session_file)
                    await sync_service.upsert_cursor(
                        user_id=args.user_id,
                        session_id=session_info.session_id,
                        project_path=project_path,
                        entry_count=content.entry_count,
                        file_mtime=file_mtime,
                    )

                    projects_with_new_activity.add(project.id)
                    await session.commit()

                logger.info("Processed session %s → %s: %s", session_info.session_id, project.name, summary_data["summary"][:100])

            except Exception:
                logger.exception("Failed to process session %s", session_info.session_id)
                await session.rollback()
                continue

        if not args.dry_run and projects_with_new_activity:
            logger.info("Regenerating state for %d projects", len(projects_with_new_activity))
            for project_id in projects_with_new_activity:
                try:
                    await processing_service.regenerate_project_state(
                        user_id=args.user_id,
                        project_id=project_id,
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to regenerate state for project %d", project_id)
                    await session.rollback()

    logger.info("Claude Code sync complete.")


if __name__ == "__main__":
    asyncio.run(main())
