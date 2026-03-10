from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
import sys

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.services.imessage_contact_service import (
    IMessageContactResolver,
    format_contact_display_name,
    normalize_contact_identifier,
)


def run(coro):
    return asyncio.run(coro)


class DummySession:
    async def execute(self, *args, **kwargs):  # pragma: no cover - not used in these tests
        raise AssertionError("DummySession.execute should not be called in contact DB tests")


def _build_contacts_db(path: Path) -> None:
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
            "INSERT INTO ZABCDRECORD (Z_PK, ZNAME, ZFIRSTNAME, ZLASTNAME, ZNICKNAME, ZORGANIZATION) VALUES (1, 'Madelyn Smith', 'Madelyn', 'Smith', NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO ZABCDRECORD (Z_PK, ZNAME, ZFIRSTNAME, ZLASTNAME, ZNICKNAME, ZORGANIZATION) VALUES (2, NULL, 'Owen', 'Lee', 'Ow', NULL)"
        )
        conn.execute(
            "INSERT INTO ZABCDPHONENUMBER (Z_PK, ZOWNER, Z22_OWNER, ZFULLNUMBER, ZISPRIMARY, ZORDERINGINDEX) VALUES (1, 1, NULL, '+1 (301) 555-1111', 1, 0)"
        )
        conn.execute(
            "INSERT INTO ZABCDPHONENUMBER (Z_PK, ZOWNER, Z22_OWNER, ZFULLNUMBER, ZISPRIMARY, ZORDERINGINDEX) VALUES (2, 2, NULL, '3015551111', 0, 99)"
        )
        conn.execute(
            "INSERT INTO ZABCDEMAILADDRESS (Z_PK, ZOWNER, Z22_OWNER, ZADDRESS, ZADDRESSNORMALIZED, ZISPRIMARY, ZORDERINGINDEX) VALUES (1, 2, NULL, 'owen@example.com', 'owen@example.com', 1, 0)"
        )
        conn.commit()
    finally:
        conn.close()


def test_normalize_contact_identifier_handles_phone_and_email() -> None:
    assert normalize_contact_identifier(" Madelyn@Example.com ") == ("email", "madelyn@example.com")
    assert normalize_contact_identifier("+1 (301) 555-1111") == ("phone", "3015551111")
    assert normalize_contact_identifier("12345") == (None, "12345")


def test_format_contact_display_name_falls_back_through_available_fields() -> None:
    assert format_contact_display_name(
        name=None,
        first_name="Owen",
        last_name="Lee",
        nickname=None,
        organization=None,
    ) == "Owen Lee"
    assert format_contact_display_name(
        name=None,
        first_name=None,
        last_name=None,
        nickname="Ow",
        organization=None,
    ) == "Ow"
    assert format_contact_display_name(
        name=None,
        first_name=None,
        last_name=None,
        nickname=None,
        organization="Acme",
    ) == "Acme"


def test_contact_resolver_matches_phone_and_email_and_prefers_primary(tmp_path: Path) -> None:
    db_path = tmp_path / "AddressBook-v22.abcddb"
    _build_contacts_db(db_path)
    resolver = IMessageContactResolver(DummySession(), contacts_db_path=db_path)

    rows = run(
        resolver._resolve_from_contacts(
            [
                "+1 (301) 555-1111",
                "owen@example.com",
                "unknown@example.com",
            ]
        )
    )

    by_identifier = {row.identifier: row for row in rows}
    assert by_identifier["+1 (301) 555-1111"].resolved_name == "Madelyn Smith"
    assert by_identifier["owen@example.com"].resolved_name == "Owen Lee"
    assert by_identifier["unknown@example.com"].resolved_name is None
