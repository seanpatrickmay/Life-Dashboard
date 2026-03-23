"""Tests for IMessageContactResolver.refresh_unresolved_contacts."""
from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.models.imessage import IMessageContactIdentity, IMessageParticipant
from app.services.imessage_contact_service import IMessageContactResolver, ResolvedContact


def run(coro):
    return asyncio.run(coro)


def _build_contacts_db(path: Path) -> None:
    """Create a minimal macOS-style Contacts SQLite DB with two contacts."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE ZABCDRECORD (
              Z_PK INTEGER PRIMARY KEY,
              ZNAME TEXT,
              ZFIRSTNAME TEXT,
              ZLASTNAME TEXT,
              ZNICKNAME TEXT,
              ZORGANIZATION TEXT
            );
            CREATE TABLE ZABCDPHONENUMBER (
              Z_PK INTEGER PRIMARY KEY,
              ZOWNER INTEGER,
              Z22_OWNER INTEGER,
              ZFULLNUMBER TEXT,
              ZISPRIMARY INTEGER,
              ZORDERINGINDEX INTEGER
            );
            CREATE TABLE ZABCDEMAILADDRESS (
              Z_PK INTEGER PRIMARY KEY,
              ZOWNER INTEGER,
              Z22_OWNER INTEGER,
              ZADDRESS TEXT,
              ZADDRESSNORMALIZED TEXT,
              ZISPRIMARY INTEGER,
              ZORDERINGINDEX INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO ZABCDRECORD VALUES (1, 'Alice Johnson', 'Alice', 'Johnson', NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO ZABCDRECORD VALUES (2, 'Bob Williams', 'Bob', 'Williams', NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO ZABCDPHONENUMBER VALUES (1, 1, NULL, '+12407559991', 1, 0)"
        )
        conn.execute(
            "INSERT INTO ZABCDPHONENUMBER VALUES (2, 2, NULL, '+13015550202', 1, 0)"
        )
        conn.commit()
    finally:
        conn.close()


def _make_identity(
    *,
    user_id: int = 1,
    identifier: str,
    resolved_name: str | None = None,
    last_resolved_at_utc: datetime | None = None,
) -> IMessageContactIdentity:
    """Build an IMessageContactIdentity ORM instance (detached, no DB)."""
    return IMessageContactIdentity(
        user_id=user_id,
        identifier=identifier,
        normalized_identifier=identifier,
        identifier_kind="phone",
        resolved_name=resolved_name,
        source_record_id=None,
        last_resolved_at_utc=last_resolved_at_utc,
    )


class FakeScalarsResult:
    """Mimics result.scalars().all() returning a list of ORM objects."""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def all(self) -> list:
        return self._rows


class FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> FakeScalarsResult:
        return FakeScalarsResult(self._rows)


class FakeSession:
    """Tracks execute/flush calls; returns canned rows for the first SELECT."""

    def __init__(self, unresolved_rows: list[IMessageContactIdentity] | None = None) -> None:
        self._unresolved_rows = unresolved_rows or []
        self.execute_calls: list = []
        self.flush_calls = 0

    async def execute(self, stmt, *args, **kwargs):
        self.execute_calls.append(stmt)
        # First call is the SELECT for unresolved contacts; subsequent are UPDATEs.
        if len(self.execute_calls) == 1:
            return FakeResult(self._unresolved_rows)
        return FakeResult([])

    async def flush(self) -> None:
        self.flush_calls += 1


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "AddressBook-v22.abcddb"
    _build_contacts_db(path)
    return path


def test_refresh_unresolved_all_already_resolved(db_path: Path) -> None:
    """When no unresolved contacts exist, returns 0 and issues no UPDATEs."""
    session = FakeSession(unresolved_rows=[])
    resolver = IMessageContactResolver(session, contacts_db_path=db_path)

    count = run(resolver.refresh_unresolved_contacts(user_id=1))

    assert count == 0
    # Only the initial SELECT should have been executed, no UPDATEs or flush.
    assert len(session.execute_calls) == 1
    assert session.flush_calls == 0


def test_refresh_unresolved_resolves_one_of_two(db_path: Path) -> None:
    """With 2 unresolved, 1 resolvable from contacts DB, returns 1 and updates the resolvable one."""
    resolvable = _make_identity(identifier="+12407559991")
    not_resolvable = _make_identity(identifier="+19995550000")

    session = FakeSession(unresolved_rows=[resolvable, not_resolvable])
    resolver = IMessageContactResolver(session, contacts_db_path=db_path)

    count = run(resolver.refresh_unresolved_contacts(user_id=1))

    assert count == 1

    # The resolvable one should have its name and timestamp set.
    assert resolvable.resolved_name == "Alice Johnson"
    assert resolvable.last_resolved_at_utc is not None

    # The unresolvable one should remain NULL.
    assert not_resolvable.resolved_name is None
    assert not_resolvable.last_resolved_at_utc is None


def test_refresh_unresolved_updates_participant_display_name(db_path: Path) -> None:
    """An UPDATE for participant display_name is issued for each resolved contact."""
    unresolved = _make_identity(identifier="+12407559991")

    session = FakeSession(unresolved_rows=[unresolved])
    resolver = IMessageContactResolver(session, contacts_db_path=db_path)

    count = run(resolver.refresh_unresolved_contacts(user_id=1))

    assert count == 1
    # execute_calls: [SELECT unresolved, UPDATE participants]
    # The second call should be the participant UPDATE statement.
    assert len(session.execute_calls) >= 2
    update_stmt = session.execute_calls[1]
    # Verify it's an UPDATE targeting imessage_participant.
    compiled = update_stmt.compile()
    assert "imessage_participant" in str(compiled)
    assert session.flush_calls == 1


def test_refresh_unresolved_does_not_touch_already_resolved(db_path: Path) -> None:
    """Already-resolved contacts are excluded by the initial query, so they're never modified."""
    original_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    resolved = _make_identity(
        identifier="+12407559991",
        resolved_name="Custom Name Override",
        last_resolved_at_utc=original_time,
    )

    # The query filters resolved_name IS NULL, so this contact won't appear in results.
    session = FakeSession(unresolved_rows=[])
    resolver = IMessageContactResolver(session, contacts_db_path=db_path)

    count = run(resolver.refresh_unresolved_contacts(user_id=1))

    assert count == 0
    # The resolved contact should be untouched.
    assert resolved.resolved_name == "Custom Name Override"
    assert resolved.last_resolved_at_utc == original_time
