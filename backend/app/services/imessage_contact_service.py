"""Local Contacts lookup and cached identity resolution for iMessage handles."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from pathlib import Path
import re
from typing import Iterable

from loguru import logger
from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.imessage import IMessageContactIdentity, IMessageParticipant
from app.services.imessage_utils import normalize_message_text


CONTACTS_ROOT = Path("~/Library/Application Support/AddressBook").expanduser()
CONTACTS_SOURCES_ROOT = CONTACTS_ROOT / "Sources"
CONTACTS_DB_FILENAME = "AddressBook-v22.abcddb"
CONTACTS_DB_PATH = CONTACTS_ROOT / CONTACTS_DB_FILENAME
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
    joined_name = " ".join(part for part in (_clean_display_text(first_name), _clean_display_text(last_name)) if part)
    for value in (
        _clean_display_text(name),
        joined_name or None,
        _clean_display_text(nickname),
        _clean_display_text(organization),
    ):
        if value:
            return value
    return None


def _clean_display_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    if cleaned and cleaned == cleaned.lower() and re.search(r"[a-z]", cleaned) and not re.search(r"[@\d]", cleaned):
        cleaned = " ".join(part.capitalize() for part in cleaned.split(" "))
    return cleaned or None


class IMessageContactResolver:
    def __init__(self, session: AsyncSession, *, contacts_db_path: str | Path | None = None) -> None:
        self.session = session
        self.contacts_db_path = Path(contacts_db_path).expanduser() if contacts_db_path else CONTACTS_DB_PATH
        self._explicit_contacts_path = contacts_db_path is not None
        self._phone_index: dict[str, ResolvedContact] | None = None
        self._email_index: dict[str, ResolvedContact] | None = None
        self._contacts_available: bool | None = None

    async def resolve_identifiers(self, *, user_id: int, identifiers: Iterable[str | None]) -> dict[str, str | None]:
        requested = self._normalized_identifier_list(identifiers)
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
        requested = self._normalized_identifier_list(identifiers)
        if not requested:
            return {}
        resolved_rows = await self._resolve_from_contacts(requested)
        await self._upsert_cache(user_id=user_id, rows=resolved_rows)
        return {row.identifier: row.resolved_name for row in resolved_rows}

    async def refresh_unresolved_contacts(self, *, user_id: int) -> int:
        """Re-resolve contacts where resolved_name is NULL.

        Returns count of newly resolved contacts.
        """
        stmt = select(IMessageContactIdentity).where(
            IMessageContactIdentity.user_id == user_id,
            IMessageContactIdentity.resolved_name.is_(None),
        )
        result = await self.session.execute(stmt)
        unresolved = result.scalars().all()

        if not unresolved:
            return 0

        identifiers = [c.identifier for c in unresolved]
        resolved_rows = await self._resolve_from_contacts(identifiers)
        resolved_map = {row.identifier: row for row in resolved_rows if row.resolved_name}

        now_utc = datetime.now(timezone.utc)
        count = 0
        for contact in unresolved:
            match = resolved_map.get(contact.identifier)
            if not match:
                continue
            contact.resolved_name = match.resolved_name
            contact.last_resolved_at_utc = now_utc
            count += 1

            participant_stmt = (
                update(IMessageParticipant)
                .where(
                    IMessageParticipant.user_id == user_id,
                    IMessageParticipant.identifier == contact.identifier,
                    or_(
                        IMessageParticipant.display_name.is_(None),
                        IMessageParticipant.display_name == contact.identifier,
                    ),
                )
                .values(display_name=match.resolved_name)
            )
            await self.session.execute(participant_stmt)

        await self.session.flush()
        return count

    def _normalized_identifier_list(self, identifiers: Iterable[str | None]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in identifiers:
            value = normalize_message_text(item)
            if not value or value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        return normalized

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
            phone_index: dict[str, tuple[int, ResolvedContact]] = {}
            email_index: dict[str, tuple[int, ResolvedContact]] = {}
            db_paths = self._candidate_contacts_db_paths()
            if not db_paths:
                raise FileNotFoundError(f"No Contacts databases found under {self.contacts_db_path}")

            for source_path in db_paths:
                conn = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
                conn.row_factory = sqlite3.Row
                try:
                    phone_rows = self._contact_rows_for_table(conn, table_name="ZABCDPHONENUMBER")
                    email_rows = self._contact_rows_for_table(conn, table_name="ZABCDEMAILADDRESS")
                finally:
                    conn.close()

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
                        source_record_id=f"{source_path}:{row['record_id']}",
                    )
                    current = phone_index.get(normalized_phone)
                    if current is None or score > current[0]:
                        phone_index[normalized_phone] = (score, resolved)

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
                        source_record_id=f"{source_path}:{row['record_id']}",
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

    def _candidate_contacts_db_paths(self) -> list[Path]:
        if self._explicit_contacts_path:
            path = self.contacts_db_path.expanduser()
            if path.is_dir():
                candidates: list[Path] = []
                direct_db = path / CONTACTS_DB_FILENAME
                if direct_db.exists():
                    candidates.append(direct_db)
                candidates.extend(sorted(path.glob(f"*/{CONTACTS_DB_FILENAME}")))
                return candidates
            return [path] if path.exists() else []

        candidates = [CONTACTS_DB_PATH]
        if CONTACTS_SOURCES_ROOT.exists():
            candidates.extend(sorted(CONTACTS_SOURCES_ROOT.glob(f"*/{CONTACTS_DB_FILENAME}")))
        deduped: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            resolved = str(candidate.expanduser())
            if candidate.exists() and resolved not in seen:
                deduped.append(candidate)
                seen.add(resolved)
        return deduped

    def _contact_rows_for_table(self, conn: sqlite3.Connection, *, table_name: str) -> list[sqlite3.Row]:
        columns = {
            str(row["name"])
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if not columns:
            return []
        table_name_alias = "p" if table_name == "ZABCDPHONENUMBER" else "e"
        # In modern macOS Contacts schemas, ZOWNER is the actual contact-record foreign key.
        # Auxiliary owner columns such as Z21_OWNER/Z22_OWNER can point at unrelated records and
        # must only be used as fallbacks when ZOWNER is absent for a given row.
        owner_columns = [name for name in ("ZOWNER", "Z22_OWNER", "Z21_OWNER") if name in columns]
        if not owner_columns:
            return []
        owner_expr = f"COALESCE({', '.join(f'{table_name_alias}.{name}' for name in owner_columns)})"

        if table_name == "ZABCDPHONENUMBER":
            value_select = "p.ZFULLNUMBER AS phone_number"
            value_filter = "p.ZFULLNUMBER IS NOT NULL AND trim(p.ZFULLNUMBER) <> ''"
        else:
            value_select = "e.ZADDRESS AS email_address, e.ZADDRESSNORMALIZED AS email_normalized"
            value_filter = "e.ZADDRESS IS NOT NULL AND trim(e.ZADDRESS) <> ''"

        query = f"""
            SELECT
                r.Z_PK AS record_id,
                r.ZNAME AS full_name,
                r.ZFIRSTNAME AS first_name,
                r.ZLASTNAME AS last_name,
                r.ZNICKNAME AS nickname,
                r.ZORGANIZATION AS organization,
                {value_select},
                {table_name_alias}.ZISPRIMARY AS is_primary,
                {table_name_alias}.ZORDERINGINDEX AS ordering_index
            FROM {table_name} AS {table_name_alias}
            JOIN ZABCDRECORD AS r
              ON r.Z_PK = {owner_expr}
            WHERE {value_filter}
        """
        return conn.execute(query).fetchall()

    async def _upsert_cache(self, *, user_id: int, rows: list[ResolvedContact]) -> None:
        if not rows:
            return
        now_utc = datetime.now(timezone.utc)
        deduped_rows: dict[str, ResolvedContact] = {}
        for row in rows:
            current = deduped_rows.get(row.identifier)
            if current is None:
                deduped_rows[row.identifier] = row
                continue
            if current.resolved_name is None and row.resolved_name is not None:
                deduped_rows[row.identifier] = row
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
            for row in deduped_rows.values()
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
