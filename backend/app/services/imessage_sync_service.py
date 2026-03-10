"""Local macOS iMessage sync into the Postgres cache."""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.imessage import (
    IMessageConversation,
    IMessageMessage,
    IMessageParticipant,
    IMessageSyncRun,
)
from app.services.imessage_contact_service import IMessageContactResolver
from app.services.imessage_utils import (
    apple_timestamp_to_datetime,
    conversation_display_name,
    extract_message_text,
    normalize_message_text,
    participant_hash,
)


class IMessageSyncService:
    """Copies raw messages from the macOS Messages SQLite database into Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.contact_resolver = IMessageContactResolver(session)

    async def sync_from_chat_db(
        self,
        *,
        user_id: int,
        db_path: str,
        batch_size: int = 500,
    ) -> IMessageSyncRun:
        run = IMessageSyncRun(
            user_id=user_id,
            status="running",
            started_at_utc=datetime.now(timezone.utc),
            source_path=db_path,
        )
        self.session.add(run)
        await self.session.flush()

        try:
            source_path = Path(db_path).expanduser()
            if not source_path.exists():
                raise FileNotFoundError(f"Messages database not found at {source_path}")
            last_row_id = await self._last_source_row_id(user_id)
            with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                while True:
                    rows = self._fetch_message_batch(conn, after_row_id=last_row_id, batch_size=batch_size)
                    if not rows:
                        break
                    run.messages_scanned += len(rows)
                    conversations_upserted, messages_upserted = await self._persist_batch(
                        user_id=user_id,
                        conn=conn,
                        rows=rows,
                    )
                    run.conversations_upserted += conversations_upserted
                    run.messages_upserted += messages_upserted
                    run.conversations_scanned += len({row["chat_guid"] for row in rows})
                    last_row_id = max(int(row["message_row_id"]) for row in rows)
                    await self.session.commit()
            run.status = "completed"
            run.completed_at_utc = datetime.now(timezone.utc)
            await self.session.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("[imessage] sync failed user={} err={}", user_id, exc)
            run.status = "error"
            run.error_message = str(exc)
            run.completed_at_utc = datetime.now(timezone.utc)
            await self.session.commit()
            raise
        return run

    async def _last_source_row_id(self, user_id: int) -> int:
        stmt = select(func.max(IMessageMessage.source_row_id)).where(IMessageMessage.user_id == user_id)
        value = (await self.session.execute(stmt)).scalar_one_or_none()
        return int(value or 0)

    def _fetch_message_batch(
        self, conn: sqlite3.Connection, *, after_row_id: int, batch_size: int
    ) -> list[sqlite3.Row]:
        query = """
        SELECT
            m.ROWID AS message_row_id,
            COALESCE(m.guid, 'msg-' || m.ROWID) AS message_guid,
            m.text AS message_text,
            m.attributedBody AS attributed_body,
            m.service AS message_service,
            m.is_from_me AS is_from_me,
            m.cache_has_attachments AS has_attachments,
            COALESCE(m.associated_message_type, 0) AS associated_message_type,
            COALESCE(m.item_type, 0) AS item_type,
            m.associated_message_guid AS associated_message_guid,
            m.date AS message_date,
            m.date_read AS message_date_read,
            m.date_delivered AS message_date_delivered,
            h.id AS handle_identifier,
            c.ROWID AS chat_row_id,
            COALESCE(c.guid, 'chat-' || c.ROWID) AS chat_guid,
            c.display_name AS chat_display_name,
            c.chat_identifier AS chat_identifier,
            c.service_name AS chat_service_name
        FROM message AS m
        JOIN chat_message_join AS cmj ON cmj.message_id = m.ROWID
        JOIN chat AS c ON c.ROWID = cmj.chat_id
        LEFT JOIN handle AS h ON h.ROWID = m.handle_id
        WHERE m.ROWID > ?
        ORDER BY m.ROWID ASC
        LIMIT ?
        """
        rows = conn.execute(query, (after_row_id, batch_size)).fetchall()
        return list(rows)

    def _fetch_participants(
        self, conn: sqlite3.Connection, chat_row_ids: list[int]
    ) -> dict[int, list[str]]:
        if not chat_row_ids:
            return {}
        placeholders = ",".join("?" for _ in chat_row_ids)
        query = f"""
        SELECT
            chj.chat_id AS chat_id,
            h.id AS handle_identifier
        FROM chat_handle_join AS chj
        JOIN handle AS h ON h.ROWID = chj.handle_id
        WHERE chj.chat_id IN ({placeholders})
        ORDER BY chj.chat_id ASC, h.id ASC
        """
        rows = conn.execute(query, chat_row_ids).fetchall()
        by_chat: dict[int, list[str]] = defaultdict(list)
        for row in rows:
            identifier = normalize_message_text(row["handle_identifier"])
            if identifier:
                by_chat[int(row["chat_id"])].append(identifier)
        return by_chat

    async def _persist_batch(
        self, *, user_id: int, conn: sqlite3.Connection, rows: list[sqlite3.Row]
    ) -> tuple[int, int]:
        chat_row_ids = sorted({int(row["chat_row_id"]) for row in rows})
        participant_lookup = self._fetch_participants(conn, chat_row_ids)
        resolved_names = await self.contact_resolver.resolve_identifiers(
            user_id=user_id,
            identifiers=(
                [
                    normalize_message_text(row["handle_identifier"])
                    for row in rows
                ]
                + [
                    identifier
                    for participants in participant_lookup.values()
                    for identifier in participants
                ]
            ),
        )
        now_utc = datetime.now(timezone.utc)
        conversation_payloads: dict[str, dict[str, Any]] = {}
        message_values: list[dict[str, Any]] = []
        for row in rows:
            chat_row_id = int(row["chat_row_id"])
            participants = participant_lookup.get(chat_row_id, [])
            participant_labels = [
                resolved_names.get(identifier) or identifier
                for identifier in participants
            ]
            display_name = conversation_display_name(
                display_name=row["chat_display_name"],
                chat_identifier=row["chat_identifier"],
                participants=participant_labels,
            )
            message_sent_at = apple_timestamp_to_datetime(row["message_date"])
            conversation_payloads[str(row["chat_guid"])] = {
                "user_id": user_id,
                "source_guid": str(row["chat_guid"]),
                "source_row_id": chat_row_id,
                "service_name": normalize_message_text(row["chat_service_name"]),
                "chat_identifier": normalize_message_text(row["chat_identifier"]),
                "display_name": display_name,
                "participant_hash": participant_hash(participants) if participants else None,
                "participants_json": participants,
                "last_message_at_utc": message_sent_at,
                "last_synced_at_utc": now_utc,
            }
            normalized_text = extract_message_text(
                row["message_text"],
                attributed_body=row["attributed_body"],
                associated_message_type=row["associated_message_type"],
                item_type=row["item_type"],
            )
            message_values.append(
                {
                    "user_id": user_id,
                    "conversation_source_guid": str(row["chat_guid"]),
                    "source_guid": str(row["message_guid"]),
                    "source_row_id": int(row["message_row_id"]),
                    "service_name": normalize_message_text(row["message_service"]),
                    "handle_identifier": normalize_message_text(row["handle_identifier"]),
                    "sender_label": (
                        "You"
                        if bool(row["is_from_me"])
                        else (
                            resolved_names.get(normalize_message_text(row["handle_identifier"]))
                            or normalize_message_text(row["handle_identifier"])
                        )
                    ),
                    "is_from_me": bool(row["is_from_me"]),
                    "text": normalized_text,
                    "normalized_text": normalized_text,
                    "has_attachments": bool(row["has_attachments"]),
                    "sent_at_utc": message_sent_at,
                    "delivered_at_utc": apple_timestamp_to_datetime(row["message_date_delivered"]),
                    "read_at_utc": apple_timestamp_to_datetime(row["message_date_read"]),
                    "raw_payload": {
                        "chat_row_id": chat_row_id,
                        "message_row_id": int(row["message_row_id"]),
                        "content_source": (
                            "text"
                            if normalize_message_text(row["message_text"])
                            else ("attributedBody" if normalized_text else "none")
                        ),
                        "associated_message_guid": row["associated_message_guid"],
                        "associated_message_type": int(row["associated_message_type"] or 0),
                        "item_type": int(row["item_type"] or 0),
                    },
                }
            )
        conversation_values = list(conversation_payloads.values())
        if conversation_values:
            stmt = insert(IMessageConversation).values(conversation_values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_imessage_conversation_user_source_guid",
                set_={
                    "source_row_id": stmt.excluded.source_row_id,
                    "service_name": stmt.excluded.service_name,
                    "chat_identifier": stmt.excluded.chat_identifier,
                    "display_name": stmt.excluded.display_name,
                    "participant_hash": stmt.excluded.participant_hash,
                    "participants_json": stmt.excluded.participants_json,
                    "last_message_at_utc": stmt.excluded.last_message_at_utc,
                    "last_synced_at_utc": stmt.excluded.last_synced_at_utc,
                    "updated_at": now_utc,
                },
            )
            await self.session.execute(stmt)

            conversation_stmt = select(IMessageConversation).where(
                IMessageConversation.user_id == user_id,
                IMessageConversation.source_guid.in_(list(conversation_payloads)),
            )
            conversation_rows = list((await self.session.execute(conversation_stmt)).scalars().all())
            by_guid = {row.source_guid: row for row in conversation_rows}
            await self.session.execute(
                delete(IMessageParticipant).where(
                    IMessageParticipant.user_id == user_id,
                    IMessageParticipant.conversation_id.in_([row.id for row in conversation_rows]),
                )
            )
            participant_rows = []
            for payload in conversation_values:
                conversation = by_guid.get(payload["source_guid"])
                if conversation is None:
                    continue
                for identifier in payload["participants_json"] or []:
                    participant_rows.append(
                        {
                            "user_id": user_id,
                            "conversation_id": conversation.id,
                            "identifier": identifier,
                            "display_name": resolved_names.get(identifier) or identifier,
                            "is_self": False,
                        }
                    )
            if participant_rows:
                await self.session.execute(insert(IMessageParticipant).values(participant_rows))

            message_rows = []
            for payload in message_values:
                conversation = by_guid.get(payload.pop("conversation_source_guid"))
                if conversation is None:
                    continue
                message_rows.append(
                    {
                        **payload,
                        "conversation_id": conversation.id,
                    }
                )
            if message_rows:
                message_stmt = insert(IMessageMessage).values(message_rows)
                message_stmt = message_stmt.on_conflict_do_update(
                    constraint="uq_imessage_message_user_source_guid",
                    set_={
                        "conversation_id": message_stmt.excluded.conversation_id,
                        "source_row_id": message_stmt.excluded.source_row_id,
                        "service_name": message_stmt.excluded.service_name,
                        "handle_identifier": message_stmt.excluded.handle_identifier,
                        "sender_label": message_stmt.excluded.sender_label,
                        "is_from_me": message_stmt.excluded.is_from_me,
                        "text": message_stmt.excluded.text,
                        "normalized_text": message_stmt.excluded.normalized_text,
                        "has_attachments": message_stmt.excluded.has_attachments,
                        "sent_at_utc": message_stmt.excluded.sent_at_utc,
                        "delivered_at_utc": message_stmt.excluded.delivered_at_utc,
                        "read_at_utc": message_stmt.excluded.read_at_utc,
                        "raw_payload": message_stmt.excluded.raw_payload,
                        "updated_at": now_utc,
                    },
                )
                result = await self.session.execute(message_stmt)
                inserted = result.rowcount or 0
            else:
                inserted = 0
            return len(conversation_values), inserted
        return 0, 0
