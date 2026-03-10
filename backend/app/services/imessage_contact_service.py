"""Local Contacts lookup and cached identity resolution for iMessage handles."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
import re
from typing import Iterable

from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.imessage import IMessageContactIdentity
from app.services.imessage_utils import normalize_message_text


CONTACTS_DB_PATH = Path("~/Library/Application Support/AddressBook/AddressBook-v22.abcddb").expanduser()
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NON_DIGIT_RE = re.compile(r"\D+")


@dataclass(frozen=True)
class ResolvedContact:
    identifier: str
    normalized_identifier: str
    identifier_kind: str
    resolved_name: str | None
    source_record_id: str | None = None


def normalize_contact_identifier(identifier: str | None) -> tuple[str | None, str | None]:
    raw = normalize_message_text(identifier)
    if not raw:
        return None, None
    lowered = raw.lower()
    if _EMAIL_RE.match(lowered):
        return "email", lowered

    digits = _NON_DIGIT_RE.sub("", raw)
    if len(digits) < 7:
        return None, raw
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) > 11 and digits.startswith("1"):
        digits = digits[1:]
    return "phone", digits


def format_contact_display_name(
    *,
    name: str | None,
    first_name: str | None,
    last_name: str | None,
    nickname: str | None,
    organization: str | None,
) -> str | None:
    for value in (name, " ".join(part for part in (first_name, last_name) if normalize_message_text(part)), nickname, organization):
        normalized = normalize_message_text(value)
        if normalized:
            return normalized
    return None


class IMessageContactResolver:
    def __init__(self, session: AsyncSession, *, contacts_db_path: str | Path | None = None) -> None:
        self.session = session
        self.contacts_db_path = Path(contacts_db_path).expanduser() if contacts_db_path else CONTACTS_DB_PATH
        self._phone_index: dict[str, ResolvedContact] | None = None
        self._email_index: dict[str, ResolvedContact] | None = None
        self._contacts_available: bool | None = None

    async def resolve_identifiers(self, *, user_id: int, identifiers: Iterable[str | None]) -> dict[str, str | None]:
        requested = [
            normalize_message_text(item)
            for item in identifiers
            if normalize_message_text(item)
        ]
        if not requested:
            return {}
        result: dict[str, str | None] = {}
        cached = await self._load_cached(user_id=user_id, identifiers=requested)
        result.update(cached)

        missing = [item for item in requested if item not in result]
        if not missing:
            return result

        resolved_rows = await self._resolve_from_contacts(missing)
        await self._upsert_cache(user_id=user_id, rows=resolved_rows)
        result.update({row.identifier: row.resolved_name for row in resolved_rows})
        return result

    async def refresh_cached_identities(
        self,
        *,
        user_id: int,
        identifiers: Iterable[str | None],
    ) -> dict[str, str | None]:
        requested = [
            normalize_message_text(item)
            for item in identifiers
            if normalize_message_text(item)
        ]
        if not requested:
            return {}
        resolved_rows = await self._resolve_from_contacts(requested)
        await self._upsert_cache(user_id=user_id, rows=resolved_rows)
        return {row.identifier: row.resolved_name for row in resolved_rows}

    async def _load_cached(self, *, user_id: int, identifiers: list[str]) -> dict[str, str | None]:
        stmt = select(IMessageContactIdentity).where(
            IMessageContactIdentity.user_id == user_id,
            IMessageContactIdentity.identifier.in_(identifiers),
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return {
            row.identifier: row.resolved_name
            for row in rows
        }

    async def _resolve_from_contacts(self, identifiers: list[str]) -> list[ResolvedContact]:
        await self._ensure_contact_indexes()
        rows: list[ResolvedContact] = []
        for identifier in identifiers:
            identifier_kind, normalized_identifier = normalize_contact_identifier(identifier)
            resolved_name = None
            source_record_id = None
            if identifier_kind == "email" and normalized_identifier and self._email_index:
                match = self._email_index.get(normalized_identifier)
                if match:
                    resolved_name = match.resolved_name
                    source_record_id = match.source_record_id
            elif identifier_kind == "phone" and normalized_identifier and self._phone_index:
                match = self._phone_index.get(normalized_identifier)
                if match:
                    resolved_name = match.resolved_name
                    source_record_id = match.source_record_id
            rows.append(
                ResolvedContact(
                    identifier=identifier,
                    normalized_identifier=normalized_identifier or identifier,
                    identifier_kind=identifier_kind or "unknown",
                    resolved_name=resolved_name,
                    source_record_id=source_record_id,
                )
            )
        return rows

    async def _ensure_contact_indexes(self) -> None:
        if self._contacts_available is False:
            return
        if self._phone_index is not None and self._email_index is not None:
            return
        try:
            self._phone_index, self._email_index = await self._load_contact_indexes()
            self._contacts_available = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("[imessage] contact resolution unavailable: {}", exc)
            self._phone_index = {}
            self._email_index = {}
            self._contacts_available = False

    async def _load_contact_indexes(self) -> tuple[dict[str, ResolvedContact], dict[str, ResolvedContact]]:
        def _load() -> tuple[dict[str, ResolvedContact], dict[str, ResolvedContact]]:
            source_path = self.contacts_db_path.expanduser()
            if not source_path.exists():
                raise FileNotFoundError(f"Contacts database not found at {source_path}")
            conn = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            try:
                phone_rows = conn.execute(
                    """
                    SELECT
                        r.Z_PK AS record_id,
                        r.ZNAME AS full_name,
                        r.ZFIRSTNAME AS first_name,
                        r.ZLASTNAME AS last_name,
                        r.ZNICKNAME AS nickname,
                        r.ZORGANIZATION AS organization,
                        p.ZFULLNUMBER AS phone_number,
                        p.ZISPRIMARY AS is_primary,
                        p.ZORDERINGINDEX AS ordering_index
                    FROM ZABCDPHONENUMBER AS p
                    JOIN ZABCDRECORD AS r
                      ON r.Z_PK = COALESCE(p.Z22_OWNER, p.ZOWNER)
                    WHERE p.ZFULLNUMBER IS NOT NULL AND trim(p.ZFULLNUMBER) <> ''
                    """
                ).fetchall()
                email_rows = conn.execute(
                    """
                    SELECT
                        r.Z_PK AS record_id,
                        r.ZNAME AS full_name,
                        r.ZFIRSTNAME AS first_name,
                        r.ZLASTNAME AS last_name,
                        r.ZNICKNAME AS nickname,
                        r.ZORGANIZATION AS organization,
                        e.ZADDRESS AS email_address,
                        e.ZADDRESSNORMALIZED AS email_normalized,
                        e.ZISPRIMARY AS is_primary,
                        e.ZORDERINGINDEX AS ordering_index
                    FROM ZABCDEMAILADDRESS AS e
                    JOIN ZABCDRECORD AS r
                      ON r.Z_PK = COALESCE(e.Z22_OWNER, e.ZOWNER)
                    WHERE e.ZADDRESS IS NOT NULL AND trim(e.ZADDRESS) <> ''
                    """
                ).fetchall()
            finally:
                conn.close()

            phone_index: dict[str, tuple[int, ResolvedContact]] = {}
            for row in phone_rows:
                name = format_contact_display_name(
                    name=row["full_name"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    nickname=row["nickname"],
                    organization=row["organization"],
                )
                if not name:
                    continue
                _, normalized_phone = normalize_contact_identifier(str(row["phone_number"]))
                if not normalized_phone:
                    continue
                score = int(row["is_primary"] or 0) * 100 - int(row["ordering_index"] or 0)
                resolved = ResolvedContact(
                    identifier=str(row["phone_number"]),
                    normalized_identifier=normalized_phone,
                    identifier_kind="phone",
                    resolved_name=name,
                    source_record_id=str(row["record_id"]),
                )
                current = phone_index.get(normalized_phone)
                if current is None or score > current[0]:
                    phone_index[normalized_phone] = (score, resolved)

            email_index: dict[str, tuple[int, ResolvedContact]] = {}
            for row in email_rows:
                name = format_contact_display_name(
                    name=row["full_name"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    nickname=row["nickname"],
                    organization=row["organization"],
                )
                if not name:
                    continue
                email_value = normalize_message_text(row["email_normalized"] or row["email_address"]).lower()
                _, normalized_email = normalize_contact_identifier(email_value)
                if not normalized_email:
                    continue
                score = int(row["is_primary"] or 0) * 100 - int(row["ordering_index"] or 0)
                resolved = ResolvedContact(
                    identifier=str(row["email_address"]),
                    normalized_identifier=normalized_email,
                    identifier_kind="email",
                    resolved_name=name,
                    source_record_id=str(row["record_id"]),
                )
                current = email_index.get(normalized_email)
                if current is None or score > current[0]:
                    email_index[normalized_email] = (score, resolved)

            return (
                {key: value[1] for key, value in phone_index.items()},
                {key: value[1] for key, value in email_index.items()},
            )

        from asyncio import to_thread

        return await to_thread(_load)

    async def _upsert_cache(self, *, user_id: int, rows: list[ResolvedContact]) -> None:
        if not rows:
            return
        now_utc = datetime.now(timezone.utc)
        payloads = [
            {
                "user_id": user_id,
                "identifier": row.identifier,
                "normalized_identifier": row.normalized_identifier,
                "identifier_kind": row.identifier_kind,
                "resolved_name": row.resolved_name,
                "source_record_id": row.source_record_id,
                "last_resolved_at_utc": now_utc,
            }
            for row in rows
        ]
        stmt = pg_insert(IMessageContactIdentity).values(payloads)
        await self.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["user_id", "identifier"],
                set_={
                    "normalized_identifier": stmt.excluded.normalized_identifier,
                    "identifier_kind": stmt.excluded.identifier_kind,
                    "resolved_name": stmt.excluded.resolved_name,
                    "source_record_id": stmt.excluded.source_record_id,
                    "last_resolved_at_utc": stmt.excluded.last_resolved_at_utc,
                    "updated_at": now_utc,
                },
            )
        )
