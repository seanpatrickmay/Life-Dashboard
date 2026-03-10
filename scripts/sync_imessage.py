#!/usr/bin/env python3
"""Read-only iMessage sync + processing runner."""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any

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

from app.services.imessage_utils import (  # type: ignore  # noqa: E402
    APPLE_EPOCH,
    apple_timestamp_to_datetime,
    conversation_display_name,
    extract_message_text,
    normalize_message_text,
    stable_fingerprint,
)


@dataclass
class SourceMessageRow:
    message_row_id: int
    message_guid: str
    chat_row_id: int
    chat_guid: str
    service_name: str | None
    chat_identifier: str | None
    display_name: str | None
    handle_identifier: str | None
    is_from_me: bool
    text: str | None
    content_source: str
    has_attachments: bool
    associated_message_guid: str | None
    associated_message_type: int
    item_type: int
    sent_at_utc: datetime | None
    delivered_at_utc: datetime | None
    read_at_utc: datetime | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync iMessages into Life Dashboard.")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument(
        "--db-path",
        default=str(Path("~/Library/Messages/chat.db").expanduser()),
        help="Path to the macOS Messages SQLite database.",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--limit-batches", type=int, default=0)
    parser.add_argument("--skip-processing", action="store_true")
    parser.add_argument("--time-zone", default="America/New_York")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=90,
        help="Only ingest messages newer than this many days. Use 0 for unlimited history.",
    )
    parser.add_argument(
        "--rescan-retained-window",
        action="store_true",
        help="Start from the retention cutoff instead of the latest synced row so retained messages are refreshed.",
    )
    return parser.parse_args()


def open_source_db(path: str) -> sqlite3.Connection:
    expanded = str(Path(path).expanduser())
    return sqlite3.connect(f"file:{expanded}?mode=ro", uri=True)


def _apple_seconds_for_datetime(value: datetime) -> float:
    return (value.astimezone(timezone.utc) - APPLE_EPOCH).total_seconds()


def fetch_message_batch(
    conn: sqlite3.Connection,
    *,
    after_row_id: int,
    batch_size: int,
    cutoff_utc: datetime | None,
) -> list[SourceMessageRow]:
    cutoff_apple_seconds = _apple_seconds_for_datetime(cutoff_utc) if cutoff_utc else None
    query = """
        SELECT
            m.ROWID AS message_row_id,
            COALESCE(m.guid, 'message-' || m.ROWID) AS message_guid,
            c.ROWID AS chat_row_id,
            COALESCE(c.guid, 'chat-' || c.ROWID) AS chat_guid,
            COALESCE(m.service, c.service_name) AS service_name,
            c.chat_identifier AS chat_identifier,
            c.display_name AS display_name,
            h.id AS handle_identifier,
            COALESCE(m.is_from_me, 0) AS is_from_me,
            m.text AS text,
            m.attributedBody AS attributed_body,
            COALESCE(m.cache_has_attachments, 0) AS has_attachments,
            m.associated_message_guid AS associated_message_guid,
            COALESCE(m.associated_message_type, 0) AS associated_message_type,
            COALESCE(m.item_type, 0) AS item_type,
            m.date AS date_raw,
            m.date_delivered AS delivered_raw,
            m.date_read AS read_raw
        FROM message AS m
        JOIN chat_message_join AS cmj ON cmj.message_id = m.ROWID
        JOIN chat AS c ON c.ROWID = cmj.chat_id
        LEFT JOIN handle AS h ON h.ROWID = m.handle_id
        WHERE m.ROWID > ?
          AND (
            ? IS NULL
            OR (
                m.date IS NOT NULL
                AND (
                    CASE
                        WHEN ABS(m.date) >= 10000000000000000 THEN (m.date / 1000000000.0)
                        WHEN ABS(m.date) >= 10000000000000 THEN (m.date / 1000000.0)
                        WHEN ABS(m.date) >= 10000000000 THEN (m.date / 1000.0)
                        ELSE (m.date * 1.0)
                    END
                ) >= ?
            )
          )
        ORDER BY m.ROWID ASC
        LIMIT ?
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        query,
        (after_row_id, cutoff_apple_seconds, cutoff_apple_seconds, batch_size),
    ).fetchall()
    output: list[SourceMessageRow] = []
    for row in rows:
        extracted_text = extract_message_text(
            row["text"],
            attributed_body=row["attributed_body"],
            associated_message_type=row["associated_message_type"],
            item_type=row["item_type"],
        )
        output.append(
            SourceMessageRow(
                message_row_id=int(row["message_row_id"]),
                message_guid=str(row["message_guid"]),
                chat_row_id=int(row["chat_row_id"]),
                chat_guid=str(row["chat_guid"]),
                service_name=row["service_name"],
                chat_identifier=row["chat_identifier"],
                display_name=row["display_name"],
                handle_identifier=row["handle_identifier"],
                is_from_me=bool(row["is_from_me"]),
                text=extracted_text,
                content_source="text" if normalize_message_text(row["text"]) else ("attributedBody" if extracted_text else "none"),
                has_attachments=bool(row["has_attachments"]),
                associated_message_guid=row["associated_message_guid"],
                associated_message_type=int(row["associated_message_type"] or 0),
                item_type=int(row["item_type"] or 0),
                sent_at_utc=apple_timestamp_to_datetime(row["date_raw"]),
                delivered_at_utc=apple_timestamp_to_datetime(row["delivered_raw"]),
                read_at_utc=apple_timestamp_to_datetime(row["read_raw"]),
            )
        )
    return output


def fetch_participants(conn: sqlite3.Connection, chat_row_ids: list[int]) -> dict[int, list[str]]:
    if not chat_row_ids:
        return {}
    placeholders = ",".join("?" for _ in chat_row_ids)
    query = f"""
        SELECT chj.chat_id AS chat_row_id, h.id AS handle_identifier
        FROM chat_handle_join AS chj
        JOIN handle AS h ON h.ROWID = chj.handle_id
        WHERE chj.chat_id IN ({placeholders})
        ORDER BY chj.chat_id ASC, h.id ASC
    """
    rows = conn.execute(query, chat_row_ids).fetchall()
    participants: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        identifier = str(row["handle_identifier"] or "").strip()
        if identifier:
            participants[int(row["chat_row_id"])].append(identifier)
    return participants


async def main() -> None:
    from sqlalchemy import delete, exists, func, select, update

    from app.db.models.entities import User  # type: ignore  # noqa: E402
    from app.db.models.imessage import (  # type: ignore  # noqa: E402
        IMessageActionAudit,
        IMessageConversation,
        IMessageMessage,
        IMessageParticipant,
        IMessageSyncRun,
    )
    from app.db.session import AsyncSessionLocal  # type: ignore  # noqa: E402
    from app.services.imessage_processing_service import IMessageProcessingService  # type: ignore  # noqa: E402

    args = parse_args()
    cutoff_utc = (
        datetime.now(timezone.utc) - timedelta(days=args.lookback_days)
        if args.lookback_days > 0
        else None
    )
    conn = open_source_db(args.db_path)
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, args.user_id)
            if user is None:
                user = User(id=args.user_id, email=f"owner+{args.user_id}@example.com", display_name="Owner")
                session.add(user)
                await session.commit()

        async with AsyncSessionLocal() as session:
            run = IMessageSyncRun(
                user_id=args.user_id,
                status="running",
                started_at_utc=datetime.now(timezone.utc),
                source_path=str(Path(args.db_path).expanduser()),
            )
            session.add(run)
            await session.flush()
            run_id = run.id
            from app.services.imessage_contact_service import IMessageContactResolver  # type: ignore  # noqa: E402

            contact_resolver = IMessageContactResolver(session)

            try:
                if cutoff_utc is not None:
                    pruned_messages = await session.execute(
                        delete(IMessageMessage).where(
                            IMessageMessage.user_id == args.user_id,
                            (
                                (IMessageMessage.sent_at_utc.is_not(None) & (IMessageMessage.sent_at_utc < cutoff_utc))
                                | (
                                    IMessageMessage.sent_at_utc.is_(None)
                                    & (IMessageMessage.created_at < cutoff_utc)
                                )
                            ),
                        )
                    )
                    stale_conversation_ids = list(
                        (
                            await session.execute(
                                select(IMessageConversation.id).where(
                                    IMessageConversation.user_id == args.user_id,
                                    ~exists(
                                        select(IMessageMessage.id).where(
                                            IMessageMessage.conversation_id == IMessageConversation.id
                                        )
                                    ),
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    pruned_conversations = 0
                    if stale_conversation_ids:
                        await session.execute(
                            update(IMessageActionAudit)
                            .where(IMessageActionAudit.conversation_id.in_(stale_conversation_ids))
                            .values(conversation_id=None)
                        )
                        await session.execute(
                            delete(IMessageParticipant).where(
                                IMessageParticipant.conversation_id.in_(stale_conversation_ids)
                            )
                        )
                        deleted_conversations = await session.execute(
                            delete(IMessageConversation).where(
                                IMessageConversation.id.in_(stale_conversation_ids)
                            )
                        )
                        pruned_conversations = int(getattr(deleted_conversations, "rowcount", 0) or 0)
                    await session.commit()
                    print(
                        (
                            f"{datetime.now(timezone.utc).isoformat()} "
                            f"retention cutoff={cutoff_utc.isoformat()} "
                            f"pruned_messages={int(getattr(pruned_messages, 'rowcount', 0) or 0)} "
                            f"pruned_conversations={pruned_conversations}"
                        ),
                        flush=True,
                    )

                if args.rescan_retained_window and cutoff_utc is not None:
                    resume_stmt = select(func.max(IMessageMessage.source_row_id)).where(
                        IMessageMessage.user_id == args.user_id,
                        (
                            (IMessageMessage.sent_at_utc.is_not(None) & (IMessageMessage.sent_at_utc < cutoff_utc))
                            | (
                                IMessageMessage.sent_at_utc.is_(None)
                                & (IMessageMessage.created_at < cutoff_utc)
                            )
                        ),
                    )
                elif args.rescan_retained_window:
                    resume_stmt = select(func.min(IMessageMessage.source_row_id) - 1).where(
                        IMessageMessage.user_id == args.user_id
                    )
                else:
                    resume_stmt = select(func.max(IMessageMessage.source_row_id)).where(
                        IMessageMessage.user_id == args.user_id
                    )
                result = await session.execute(resume_stmt)
                last_row_id = int(result.scalar_one_or_none() or 0)
                print(
                    (
                        f"{datetime.now(timezone.utc).isoformat()} "
                        f"sync start user_id={args.user_id} "
                        f"lookback_days={args.lookback_days} "
                        f"rescan_retained_window={args.rescan_retained_window} "
                        f"resume_row_id={last_row_id}"
                    ),
                    flush=True,
                )

                batch_count = 0
                while True:
                    if args.limit_batches and batch_count >= args.limit_batches:
                        break
                    batch = fetch_message_batch(
                        conn,
                        after_row_id=last_row_id,
                        batch_size=args.batch_size,
                        cutoff_utc=cutoff_utc,
                    )
                    if not batch:
                        break
                    batch_count += 1
                    run.messages_scanned += len(batch)
                    last_row_id = max(item.message_row_id for item in batch)
                    chat_row_ids = sorted({item.chat_row_id for item in batch})
                    participants_map = fetch_participants(conn, chat_row_ids)
                    resolved_names = await contact_resolver.resolve_identifiers(
                        user_id=args.user_id,
                        identifiers=(
                            [item.handle_identifier for item in batch]
                            + [
                                identifier
                                for identifiers in participants_map.values()
                                for identifier in identifiers
                            ]
                        ),
                    )

                    conversation_payloads: list[dict[str, Any]] = []
                    seen_chat_guids: set[str] = set()
                    for item in batch:
                        if item.chat_guid in seen_chat_guids:
                            continue
                        seen_chat_guids.add(item.chat_guid)
                        participants = participants_map.get(item.chat_row_id, [])
                        participant_labels = [
                            resolved_names.get(identifier) or identifier
                            for identifier in participants
                        ]
                        conversation_payloads.append(
                            {
                                "user_id": args.user_id,
                                "source_guid": item.chat_guid,
                                "source_row_id": item.chat_row_id,
                                "service_name": item.service_name,
                                "chat_identifier": item.chat_identifier,
                                "display_name": conversation_display_name(
                                    item.display_name,
                                    item.chat_identifier,
                                    participant_labels,
                                ),
                                "participant_hash": stable_fingerprint("participants", participants),
                                "participants_json": participants,
                                "last_message_at_utc": item.sent_at_utc,
                                "last_synced_at_utc": datetime.now(timezone.utc),
                            }
                        )
                    if conversation_payloads:
                        await upsert_conversations(session, conversation_payloads)
                        run.conversations_scanned += len(conversation_payloads)
                        run.conversations_upserted += len(conversation_payloads)

                    conversation_map = await load_conversation_map(
                        session,
                        args.user_id,
                        [item["source_guid"] for item in conversation_payloads],
                    )
                    participant_payloads: list[dict[str, Any]] = []
                    for item in conversation_payloads:
                        conversation_id = conversation_map.get(str(item["source_guid"]))
                        if not conversation_id:
                            continue
                        for identifier in item.get("participants_json") or []:
                            participant_payloads.append(
                                {
                                    "user_id": args.user_id,
                                    "conversation_id": conversation_id,
                                    "identifier": identifier,
                                    "display_name": resolved_names.get(identifier) or identifier,
                                    "is_self": False,
                                }
                            )
                    if participant_payloads:
                        await upsert_participants(session, participant_payloads)

                    message_payloads_by_guid: dict[str, dict[str, Any]] = {}
                    for item in batch:
                        conversation_id = conversation_map.get(item.chat_guid)
                        if conversation_id is None:
                            continue
                        normalized = normalize_message_text(item.text)
                        message_payloads_by_guid[item.message_guid] = {
                            "user_id": args.user_id,
                            "conversation_id": conversation_id,
                            "source_guid": item.message_guid,
                            "source_row_id": item.message_row_id,
                            "service_name": item.service_name,
                            "handle_identifier": item.handle_identifier,
                            "sender_label": (
                                "You"
                                if item.is_from_me
                                else (resolved_names.get(item.handle_identifier or "") or item.handle_identifier)
                            ),
                            "is_from_me": item.is_from_me,
                            "text": item.text,
                            "normalized_text": normalized or None,
                            "has_attachments": item.has_attachments,
                            "sent_at_utc": item.sent_at_utc,
                            "delivered_at_utc": item.delivered_at_utc,
                            "read_at_utc": item.read_at_utc,
                            "raw_payload": {
                                "chat_guid": item.chat_guid,
                                "chat_row_id": item.chat_row_id,
                                "message_row_id": item.message_row_id,
                                "content_source": item.content_source,
                                "associated_message_guid": item.associated_message_guid,
                                "associated_message_type": item.associated_message_type,
                                "item_type": item.item_type,
                            },
                        }
                    message_payloads = list(message_payloads_by_guid.values())
                    if message_payloads:
                        await upsert_messages(session, message_payloads)
                        run.messages_upserted += len(message_payloads)
                    await session.commit()

                    if batch_count == 1 or batch_count % 10 == 0:
                        print(
                            (
                                f"{datetime.now(timezone.utc).isoformat()} "
                                f"batch={batch_count} "
                                f"last_row_id={last_row_id} "
                                f"messages_scanned={run.messages_scanned} "
                                f"messages_upserted={run.messages_upserted}"
                            ),
                            flush=True,
                        )

                run.status = "completed"
                run.completed_at_utc = datetime.now(timezone.utc)
                await session.commit()
                print(
                    (
                        f"{datetime.now(timezone.utc).isoformat()} "
                        f"sync completed user_id={args.user_id} "
                        f"messages_scanned={run.messages_scanned} "
                        f"messages_upserted={run.messages_upserted}"
                    ),
                    flush=True,
                )
            except Exception as exc:
                await session.rollback()
                run = await session.get(IMessageSyncRun, run_id)
                if run is None:
                    raise
                run.status = "error"
                run.error_message = str(exc)
                run.completed_at_utc = datetime.now(timezone.utc)
                await session.commit()
                print(
                    f"{datetime.now(timezone.utc).isoformat()} sync failed error={exc}",
                    flush=True,
                )
                raise

        if not args.skip_processing:
            async with AsyncSessionLocal() as session:
                processor = IMessageProcessingService(session)
                await processor.process_new_messages(args.user_id, time_zone=args.time_zone)
    finally:
        conn.close()


async def load_conversation_map(
    session,
    user_id: int,
    source_guids: list[str],
) -> dict[str, int]:
    from sqlalchemy import select

    from app.db.models.imessage import IMessageConversation  # type: ignore  # noqa: E402

    if not source_guids:
        return {}
    stmt = select(IMessageConversation).where(
        IMessageConversation.user_id == user_id,
        IMessageConversation.source_guid.in_(source_guids),
    )
    result = await session.execute(stmt)
    return {item.source_guid: item.id for item in result.scalars().all()}


async def upsert_conversations(session, payloads: list[dict[str, Any]]) -> None:
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.models.imessage import IMessageConversation  # type: ignore  # noqa: E402

    if not payloads:
        return
    stmt = pg_insert(IMessageConversation).values(payloads)
    update_map = {
        "source_row_id": stmt.excluded.source_row_id,
        "service_name": stmt.excluded.service_name,
        "chat_identifier": stmt.excluded.chat_identifier,
        "display_name": stmt.excluded.display_name,
        "participant_hash": stmt.excluded.participant_hash,
        "participants_json": stmt.excluded.participants_json,
        "last_message_at_utc": stmt.excluded.last_message_at_utc,
        "last_synced_at_utc": stmt.excluded.last_synced_at_utc,
        "updated_at": func.now(),
    }
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "source_guid"],
            set_=update_map,
        )
    )


async def upsert_participants(session, payloads: list[dict[str, Any]]) -> None:
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.models.imessage import IMessageParticipant  # type: ignore  # noqa: E402

    if not payloads:
        return
    stmt = pg_insert(IMessageParticipant).values(payloads)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["conversation_id", "identifier"],
            set_={
                "display_name": stmt.excluded.display_name,
                "updated_at": func.now(),
            },
        )
    )


async def upsert_messages(session, payloads: list[dict[str, Any]]) -> None:
    from sqlalchemy import func
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.db.models.imessage import IMessageMessage  # type: ignore  # noqa: E402

    if not payloads:
        return
    stmt = pg_insert(IMessageMessage).values(payloads)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "source_guid"],
            set_={
                "conversation_id": stmt.excluded.conversation_id,
                "source_row_id": stmt.excluded.source_row_id,
                "service_name": stmt.excluded.service_name,
                "handle_identifier": stmt.excluded.handle_identifier,
                "sender_label": stmt.excluded.sender_label,
                "is_from_me": stmt.excluded.is_from_me,
                "text": stmt.excluded.text,
                "normalized_text": stmt.excluded.normalized_text,
                "has_attachments": stmt.excluded.has_attachments,
                "sent_at_utc": stmt.excluded.sent_at_utc,
                "delivered_at_utc": stmt.excluded.delivered_at_utc,
                "read_at_utc": stmt.excluded.read_at_utc,
                "raw_payload": stmt.excluded.raw_payload,
                "updated_at": func.now(),
            },
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
