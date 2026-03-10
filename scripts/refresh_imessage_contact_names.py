#!/usr/bin/env python3
"""Refresh resolved contact names across synced iMessage rows."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import exists, or_, select
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

from app.db.models.imessage import (  # type: ignore  # noqa: E402
    IMessageConversation,
    IMessageMessage,
    IMessageParticipant,
)
from app.db.session import AsyncSessionLocal  # type: ignore  # noqa: E402
from app.services.imessage_contact_service import IMessageContactResolver  # type: ignore  # noqa: E402
from app.services.imessage_utils import conversation_display_name, normalize_message_text  # type: ignore  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh resolved contact names for synced iMessages.")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--conversation-id", type=int, default=None)
    return parser.parse_args()


def _looks_like_raw_handle(value: str | None) -> bool:
    normalized = normalize_message_text(value)
    if not normalized:
        return True
    return ("@" in normalized) or any(char.isdigit() for char in normalized)


async def main() -> None:
    args = parse_args()
    since_utc = (
        datetime.now(timezone.utc) - timedelta(days=args.lookback_days)
        if args.lookback_days > 0
        else None
    )

    async with AsyncSessionLocal() as session:
        resolver = IMessageContactResolver(session)
        message_filter = [IMessageMessage.user_id == args.user_id]
        if args.conversation_id is not None:
            message_filter.append(IMessageMessage.conversation_id == args.conversation_id)
        if since_utc is not None:
            message_filter.append(
                or_(
                    IMessageMessage.sent_at_utc >= since_utc,
                    (IMessageMessage.sent_at_utc.is_(None) & (IMessageMessage.created_at >= since_utc)),
                )
            )

        message_identifiers = list(
            (
                await session.execute(
                    select(IMessageMessage.handle_identifier)
                    .where(*message_filter, IMessageMessage.handle_identifier.is_not(None))
                    .distinct()
                )
            )
            .scalars()
            .all()
        )

        participant_stmt = select(IMessageParticipant.identifier).where(IMessageParticipant.user_id == args.user_id)
        if args.conversation_id is not None:
            participant_stmt = participant_stmt.where(IMessageParticipant.conversation_id == args.conversation_id)
        elif since_utc is not None:
            participant_stmt = participant_stmt.where(
                exists(
                    select(IMessageMessage.id).where(
                        IMessageMessage.user_id == args.user_id,
                        IMessageMessage.conversation_id == IMessageParticipant.conversation_id,
                        or_(
                            IMessageMessage.sent_at_utc >= since_utc,
                            (
                                IMessageMessage.sent_at_utc.is_(None)
                                & (IMessageMessage.created_at >= since_utc)
                            ),
                        ),
                    )
                )
            )
        participant_identifiers = list((await session.execute(participant_stmt.distinct())).scalars().all())

        identifiers = [
            identifier
            for identifier in (message_identifiers + participant_identifiers)
            if normalize_message_text(identifier)
        ]
        resolved_names = await resolver.refresh_cached_identities(
            user_id=args.user_id,
            identifiers=identifiers,
        )
        await session.commit()

        updated_messages = 0
        last_message_id = 0
        while True:
            stmt = (
                select(IMessageMessage)
                .where(*message_filter, IMessageMessage.id > last_message_id)
                .order_by(IMessageMessage.id.asc())
                .limit(args.batch_size)
            )
            batch = list((await session.execute(stmt)).scalars().all())
            if not batch:
                break
            for message in batch:
                desired_label = "You" if message.is_from_me else (
                    resolved_names.get(normalize_message_text(message.handle_identifier)) or message.handle_identifier
                )
                desired_label = normalize_message_text(desired_label) or desired_label
                if message.sender_label != desired_label:
                    message.sender_label = desired_label
                    updated_messages += 1
            last_message_id = batch[-1].id
            await session.commit()

        updated_participants = 0
        participant_filter = [IMessageParticipant.user_id == args.user_id]
        if args.conversation_id is not None:
            participant_filter.append(IMessageParticipant.conversation_id == args.conversation_id)
        elif since_utc is not None:
            participant_filter.append(
                exists(
                    select(IMessageMessage.id).where(
                        IMessageMessage.user_id == args.user_id,
                        IMessageMessage.conversation_id == IMessageParticipant.conversation_id,
                        or_(
                            IMessageMessage.sent_at_utc >= since_utc,
                            (
                                IMessageMessage.sent_at_utc.is_(None)
                                & (IMessageMessage.created_at >= since_utc)
                            ),
                        ),
                    )
                )
            )
        last_participant_id = 0
        while True:
            stmt = (
                select(IMessageParticipant)
                .where(*participant_filter, IMessageParticipant.id > last_participant_id)
                .order_by(IMessageParticipant.id.asc())
                .limit(args.batch_size)
            )
            batch = list((await session.execute(stmt)).scalars().all())
            if not batch:
                break
            for participant in batch:
                desired_name = resolved_names.get(normalize_message_text(participant.identifier)) or participant.identifier
                desired_name = normalize_message_text(desired_name) or desired_name
                if participant.display_name != desired_name:
                    participant.display_name = desired_name
                    updated_participants += 1
            last_participant_id = batch[-1].id
            await session.commit()

        conversation_ids_stmt = select(IMessageConversation.id).where(IMessageConversation.user_id == args.user_id)
        if args.conversation_id is not None:
            conversation_ids_stmt = conversation_ids_stmt.where(IMessageConversation.id == args.conversation_id)
        elif since_utc is not None:
            conversation_ids_stmt = conversation_ids_stmt.where(
                exists(
                    select(IMessageMessage.id).where(
                        IMessageMessage.user_id == args.user_id,
                        IMessageMessage.conversation_id == IMessageConversation.id,
                        or_(
                            IMessageMessage.sent_at_utc >= since_utc,
                            (
                                IMessageMessage.sent_at_utc.is_(None)
                                & (IMessageMessage.created_at >= since_utc)
                            ),
                        ),
                    )
                )
            )
        conversation_ids = list((await session.execute(conversation_ids_stmt)).scalars().all())
        updated_conversations = 0
        if conversation_ids:
            conversations = list(
                (
                    await session.execute(
                        select(IMessageConversation)
                        .options(selectinload(IMessageConversation.participants))
                        .where(IMessageConversation.id.in_(conversation_ids))
                    )
                )
                .scalars()
                .all()
            )
            for conversation in conversations:
                participant_labels = [
                    normalize_message_text(item.display_name or item.identifier)
                    for item in conversation.participants
                    if normalize_message_text(item.display_name or item.identifier)
                ]
                refreshed_name = conversation_display_name(
                    None,
                    conversation.chat_identifier,
                    participant_labels,
                )
                if not refreshed_name:
                    continue
                if (
                    not normalize_message_text(conversation.display_name)
                    or conversation.display_name == conversation.chat_identifier
                    or _looks_like_raw_handle(conversation.display_name)
                ) and normalize_message_text(conversation.display_name) != refreshed_name:
                    conversation.display_name = refreshed_name
                    updated_conversations += 1
            await session.commit()

    print(
        (
            f"refreshed identifiers={len(identifiers)} "
            f"updated_messages={updated_messages} "
            f"updated_participants={updated_participants} "
            f"updated_conversations={updated_conversations}"
        ),
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
