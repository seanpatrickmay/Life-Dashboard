#!/usr/bin/env python3
"""Rewrite iMessage-derived artifacts from audit provenance."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import or_, select
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

from app.db.models.calendar import CalendarEvent  # type: ignore  # noqa: E402
from app.db.models.imessage import (  # type: ignore  # noqa: E402
    IMessageActionAudit,
    IMessageConversation,
    IMessageMessage,
)
from app.db.models.journal import JournalEntry  # type: ignore  # noqa: E402
from app.db.models.todo import TodoItem  # type: ignore  # noqa: E402
from app.db.session import AsyncSessionLocal  # type: ignore  # noqa: E402
from app.services.imessage_processing_service import IMessageProcessingService  # type: ignore  # noqa: E402
from app.services.imessage_utils import normalize_message_text, stable_fingerprint  # type: ignore  # noqa: E402


SUPPORTED_ACTION_TYPES = ("todo.create", "journal.entry", "calendar.create")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill iMessage-derived artifact text from action audit provenance.")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--after-audit-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _message_payloads(messages: list[IMessageMessage]) -> list[dict]:
    return [
        {
            "id": message.id,
            "sent_at_utc": message.sent_at_utc.isoformat() if message.sent_at_utc else None,
            "is_from_me": message.is_from_me,
            "sender": message.sender_label or message.handle_identifier,
            "text": message.text or "",
        }
        for message in messages
    ]


async def main() -> None:
    args = parse_args()
    since_utc = (
        datetime.now(timezone.utc) - timedelta(days=args.lookback_days)
        if args.lookback_days > 0
        else None
    )

    updated_audits = 0
    updated_todos = 0
    updated_journals = 0
    updated_calendars = 0
    processed = 0
    last_audit_id = args.after_audit_id

    async with AsyncSessionLocal() as session:
        service = IMessageProcessingService(session)
        while True:
            stmt = (
                select(IMessageActionAudit)
                .options(selectinload(IMessageActionAudit.conversation).selectinload(IMessageConversation.participants))
                .where(
                    IMessageActionAudit.user_id == args.user_id,
                    IMessageActionAudit.status == "applied",
                    IMessageActionAudit.action_type.in_(SUPPORTED_ACTION_TYPES),
                    IMessageActionAudit.id > last_audit_id,
                )
                .order_by(IMessageActionAudit.id.asc())
                .limit(args.batch_size)
            )
            if since_utc is not None:
                stmt = stmt.where(
                    or_(
                        IMessageActionAudit.source_occurred_at_utc >= since_utc,
                        (
                            IMessageActionAudit.source_occurred_at_utc.is_(None)
                            & (IMessageActionAudit.created_at >= since_utc)
                        ),
                    )
                )
            audits = list((await session.execute(stmt)).scalars().all())
            if not audits:
                break

            for audit in audits:
                last_audit_id = audit.id
                processed += 1
                if args.limit and processed > args.limit:
                    break

                source_ids = [int(item) for item in (audit.supporting_message_ids_json or [])]
                if not source_ids:
                    continue
                messages = list(
                    (
                        await session.execute(
                            select(IMessageMessage)
                            .where(IMessageMessage.id.in_(source_ids))
                            .order_by(IMessageMessage.sent_at_utc.asc().nullslast(), IMessageMessage.id.asc())
                        )
                    )
                    .scalars()
                    .all()
                )
                if not messages:
                    continue
                conversation = audit.conversation
                participant_names = [
                    normalize_message_text(item.display_name or item.identifier)
                    for item in (conversation.participants if conversation else [])
                    if normalize_message_text(item.display_name or item.identifier)
                ]
                enriched = service.enrich_action_text(
                    action_type=audit.action_type,
                    action=dict(audit.extracted_payload or {}),
                    messages=_message_payloads(messages),
                    participant_names=participant_names,
                )
                changed = False

                if audit.action_type == "todo.create" and audit.target_todo_id:
                    todo = await session.get(TodoItem, audit.target_todo_id)
                    if todo is not None:
                        text_value = normalize_message_text(enriched.get("text"))
                        if text_value and todo.text != text_value:
                            todo.text = text_value
                            updated_todos += 1
                            changed = True
                        deadline = service._parse_dt(enriched.get("deadline_utc"))
                        new_fingerprint = stable_fingerprint(
                            "todo.create",
                            audit.conversation_id,
                            text_value.lower() if text_value else "",
                            deadline.isoformat() if deadline else None,
                        )
                        if audit.action_fingerprint != new_fingerprint:
                            audit.action_fingerprint = new_fingerprint
                            changed = True
                elif audit.action_type == "journal.entry" and audit.target_journal_entry_id:
                    entry = await session.get(JournalEntry, audit.target_journal_entry_id)
                    if entry is not None:
                        text_value = normalize_message_text(enriched.get("text"))
                        if text_value and entry.text != text_value:
                            entry.text = text_value
                            updated_journals += 1
                            changed = True
                        new_fingerprint = stable_fingerprint(
                            "journal.entry",
                            audit.conversation_id,
                            text_value.lower() if text_value else "",
                            entry.local_date.isoformat(),
                        )
                        if audit.action_fingerprint != new_fingerprint:
                            audit.action_fingerprint = new_fingerprint
                            changed = True
                elif audit.action_type == "calendar.create" and audit.target_calendar_event_id:
                    event = await session.get(CalendarEvent, audit.target_calendar_event_id)
                    if event is not None:
                        summary_value = normalize_message_text(enriched.get("summary"))
                        if summary_value and event.summary != summary_value:
                            event.summary = summary_value
                            updated_calendars += 1
                            changed = True
                        start = service._parse_dt(enriched.get("start_time"))
                        end = service._parse_dt(enriched.get("end_time"))
                        new_fingerprint = stable_fingerprint(
                            "calendar.create",
                            audit.conversation_id,
                            summary_value.lower() if summary_value else "",
                            start.isoformat() if start else None,
                            end.isoformat() if end else None,
                        )
                        if audit.action_fingerprint != new_fingerprint:
                            audit.action_fingerprint = new_fingerprint
                            changed = True

                if enriched != (audit.extracted_payload or {}):
                    audit.extracted_payload = enriched
                    changed = True
                if changed:
                    updated_audits += 1

            if args.dry_run:
                await session.rollback()
            else:
                await session.commit()

            if args.limit and processed >= args.limit:
                break

    print(
        (
            f"processed={processed} "
            f"updated_audits={updated_audits} "
            f"updated_todos={updated_todos} "
            f"updated_journals={updated_journals} "
            f"updated_calendars={updated_calendars} "
            f"dry_run={args.dry_run}"
        ),
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
