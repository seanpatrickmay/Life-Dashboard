from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

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


def _build_contacts_db(path: Path, *, owner_column: str = "Z22_OWNER") -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            f"""
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
              {owner_column} INTEGER,
              ZFULLNUMBER TEXT,
              ZISPRIMARY INTEGER,
              ZORDERINGINDEX INTEGER
            );
            CREATE TABLE ZABCDEMAILADDRESS (
              Z_PK INTEGER PRIMARY KEY,
              ZOWNER INTEGER,
              {owner_column} INTEGER,
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
            f"INSERT INTO ZABCDPHONENUMBER (Z_PK, ZOWNER, {owner_column}, ZFULLNUMBER, ZISPRIMARY, ZORDERINGINDEX) VALUES (1, 1, NULL, '+1 (301) 555-1111', 1, 0)"
        )
        conn.execute(
            f"INSERT INTO ZABCDPHONENUMBER (Z_PK, ZOWNER, {owner_column}, ZFULLNUMBER, ZISPRIMARY, ZORDERINGINDEX) VALUES (2, 2, NULL, '3015551111', 0, 99)"
        )
        conn.execute(
            f"INSERT INTO ZABCDEMAILADDRESS (Z_PK, ZOWNER, {owner_column}, ZADDRESS, ZADDRESSNORMALIZED, ZISPRIMARY, ZORDERINGINDEX) VALUES (1, 2, NULL, 'owen@example.com', 'owen@example.com', 1, 0)"
        )
        conn.commit()
    finally:
        conn.close()


def _build_conflicting_owner_contacts_db(path: Path) -> None:
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
              Z21_OWNER INTEGER,
              ZFULLNUMBER TEXT,
              ZISPRIMARY INTEGER,
              ZORDERINGINDEX INTEGER
            );
            CREATE TABLE ZABCDEMAILADDRESS (
              Z_PK INTEGER PRIMARY KEY,
              ZOWNER INTEGER,
              Z21_OWNER INTEGER,
              ZADDRESS TEXT,
              ZADDRESSNORMALIZED TEXT,
              ZISPRIMARY INTEGER,
              ZORDERINGINDEX INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO ZABCDRECORD (Z_PK, ZNAME, ZFIRSTNAME, ZLASTNAME, ZNICKNAME, ZORGANIZATION) VALUES (21, NULL, 'Jasmin', 'Kim', NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO ZABCDRECORD (Z_PK, ZNAME, ZFIRSTNAME, ZLASTNAME, ZNICKNAME, ZORGANIZATION) VALUES (308, NULL, 'Jamie', 'Actual', NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO ZABCDRECORD (Z_PK, ZNAME, ZFIRSTNAME, ZLASTNAME, ZNICKNAME, ZORGANIZATION) VALUES (309, NULL, 'Connor', 'Real', NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO ZABCDPHONENUMBER (Z_PK, ZOWNER, Z21_OWNER, ZFULLNUMBER, ZISPRIMARY, ZORDERINGINDEX) VALUES (281, 308, 21, '+14438129986', 1, 0)"
        )
        conn.execute(
            "INSERT INTO ZABCDEMAILADDRESS (Z_PK, ZOWNER, Z21_OWNER, ZADDRESS, ZADDRESSNORMALIZED, ZISPRIMARY, ZORDERINGINDEX) VALUES (411, 309, 21, 'connor@example.com', 'connor@example.com', 1, 0)"
        )
        conn.commit()
    finally:
        conn.close()


def _build_fallback_owner_contacts_db(path: Path) -> None:
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
              Z21_OWNER INTEGER,
              ZFULLNUMBER TEXT,
              ZISPRIMARY INTEGER,
              ZORDERINGINDEX INTEGER
            );
            CREATE TABLE ZABCDEMAILADDRESS (
              Z_PK INTEGER PRIMARY KEY,
              ZOWNER INTEGER,
              Z21_OWNER INTEGER,
              ZADDRESS TEXT,
              ZADDRESSNORMALIZED TEXT,
              ZISPRIMARY INTEGER,
              ZORDERINGINDEX INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO ZABCDRECORD (Z_PK, ZNAME, ZFIRSTNAME, ZLASTNAME, ZNICKNAME, ZORGANIZATION) VALUES (21, NULL, 'Legacy', 'Fallback', NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO ZABCDPHONENUMBER (Z_PK, ZOWNER, Z21_OWNER, ZFULLNUMBER, ZISPRIMARY, ZORDERINGINDEX) VALUES (1, NULL, 21, '+14105550101', 1, 0)"
        )
        conn.execute(
            "INSERT INTO ZABCDEMAILADDRESS (Z_PK, ZOWNER, Z21_OWNER, ZADDRESS, ZADDRESSNORMALIZED, ZISPRIMARY, ZORDERINGINDEX) VALUES (1, NULL, 21, 'legacy@example.com', 'legacy@example.com', 1, 0)"
        )
        conn.commit()
    finally:
        conn.close()


def test_normalize_contact_identifier_handles_phone_and_email() -> None:
    assert normalize_contact_identifier(" Madelyn@Example.com ") == ("email", "madelyn@example.com")
    assert normalize_contact_identifier("+1 (301) 555-1111") == ("phone", "3015551111")
    assert normalize_contact_identifier("12345") == (None, "12345")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("301.555.1111", ("phone", "3015551111")),
        ("+1 301 555 1111 ext 9", ("phone", "30155511119")),
        ("1-240-555-0199", ("phone", "2405550199")),
        ("MADelyn+travel@Example.com", ("email", "madelyn+travel@example.com")),
        ("not-an-email@", (None, "not-an-email@")),
        (None, (None, None)),
    ],
)
def test_normalize_contact_identifier_more_variants(raw: str | None, expected: tuple[str | None, str | None]) -> None:
    assert normalize_contact_identifier(raw) == expected


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
    assert format_contact_display_name(
        name="seb martinez",
        first_name=None,
        last_name=None,
        nickname=None,
        organization=None,
    ) == "Seb Martinez"


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


def test_contact_resolver_matches_phone_variants_to_same_contact(tmp_path: Path) -> None:
    db_path = tmp_path / "AddressBook-v22.abcddb"
    _build_contacts_db(db_path)
    resolver = IMessageContactResolver(DummySession(), contacts_db_path=db_path)

    rows = run(
        resolver._resolve_from_contacts(
            [
                "+1 (301) 555-1111",
                "301-555-1111",
                "13015551111",
            ]
        )
    )

    assert [row.resolved_name for row in rows] == [
        "Madelyn Smith",
        "Madelyn Smith",
        "Madelyn Smith",
    ]


def test_contact_resolver_matches_email_case_insensitively(tmp_path: Path) -> None:
    db_path = tmp_path / "AddressBook-v22.abcddb"
    _build_contacts_db(db_path)
    resolver = IMessageContactResolver(DummySession(), contacts_db_path=db_path)

    rows = run(
        resolver._resolve_from_contacts(
            [
                "OWEN@EXAMPLE.COM",
                "owen@example.com",
            ]
        )
    )

    assert [row.resolved_name for row in rows] == ["Owen Lee", "Owen Lee"]


def test_contact_resolver_scans_source_dbs_and_supports_z21_owner(tmp_path: Path) -> None:
    sources_root = tmp_path / "Sources"
    (sources_root / "source-a").mkdir(parents=True)
    (sources_root / "source-b").mkdir(parents=True)
    _build_contacts_db(sources_root / "source-a" / "AddressBook-v22.abcddb", owner_column="Z21_OWNER")
    _build_contacts_db(sources_root / "source-b" / "AddressBook-v22.abcddb")

    resolver = IMessageContactResolver(DummySession(), contacts_db_path=sources_root)

    rows = run(
        resolver._resolve_from_contacts(
            [
                "+1 (301) 555-1111",
                "owen@example.com",
            ]
        )
    )

    by_identifier = {row.identifier: row for row in rows}
    assert by_identifier["+1 (301) 555-1111"].resolved_name == "Madelyn Smith"
    assert by_identifier["owen@example.com"].resolved_name == "Owen Lee"


def test_contact_resolver_prefers_zowner_over_conflicting_z21_owner_for_source_correctness(tmp_path: Path) -> None:
    db_path = tmp_path / "AddressBook-v22.abcddb"
    _build_conflicting_owner_contacts_db(db_path)
    resolver = IMessageContactResolver(DummySession(), contacts_db_path=db_path)

    rows = run(
        resolver._resolve_from_contacts(
            [
                "+14438129986",
                "connor@example.com",
            ]
        )
    )

    by_identifier = {row.identifier: row for row in rows}
    assert by_identifier["+14438129986"].resolved_name == "Jamie Actual"
    assert by_identifier["+14438129986"].source_record_id.endswith(":308")
    assert by_identifier["connor@example.com"].resolved_name == "Connor Real"
    assert by_identifier["connor@example.com"].source_record_id.endswith(":309")


def test_contact_resolver_falls_back_to_z21_owner_when_zowner_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "AddressBook-v22.abcddb"
    _build_fallback_owner_contacts_db(db_path)
    resolver = IMessageContactResolver(DummySession(), contacts_db_path=db_path)

    rows = run(
        resolver._resolve_from_contacts(
            [
                "+14105550101",
                "legacy@example.com",
            ]
        )
    )

    by_identifier = {row.identifier: row for row in rows}
    assert by_identifier["+14105550101"].resolved_name == "Legacy Fallback"
    assert by_identifier["+14105550101"].source_record_id.endswith(":21")
    assert by_identifier["legacy@example.com"].resolved_name == "Legacy Fallback"
    assert by_identifier["legacy@example.com"].source_record_id.endswith(":21")


def test_contact_resolver_uses_nickname_or_organization_when_name_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "AddressBook-v22.abcddb"
    conn = sqlite3.connect(db_path)
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
            "INSERT INTO ZABCDRECORD (Z_PK, ZNAME, ZFIRSTNAME, ZLASTNAME, ZNICKNAME, ZORGANIZATION) VALUES (1, NULL, NULL, NULL, 'coach mike', NULL)"
        )
        conn.execute(
            "INSERT INTO ZABCDRECORD (Z_PK, ZNAME, ZFIRSTNAME, ZLASTNAME, ZNICKNAME, ZORGANIZATION) VALUES (2, NULL, NULL, NULL, NULL, 'ClubWPT Gold')"
        )
        conn.execute(
            "INSERT INTO ZABCDPHONENUMBER (Z_PK, ZOWNER, Z22_OWNER, ZFULLNUMBER, ZISPRIMARY, ZORDERINGINDEX) VALUES (1, 1, NULL, '+1 410 555 0101', 1, 0)"
        )
        conn.execute(
            "INSERT INTO ZABCDEMAILADDRESS (Z_PK, ZOWNER, Z22_OWNER, ZADDRESS, ZADDRESSNORMALIZED, ZISPRIMARY, ZORDERINGINDEX) VALUES (1, 2, NULL, 'support@clubwptgold.com', 'support@clubwptgold.com', 1, 0)"
        )
        conn.commit()
    finally:
        conn.close()

    resolver = IMessageContactResolver(DummySession(), contacts_db_path=db_path)
    rows = run(
        resolver._resolve_from_contacts(
            [
                "+1 410 555 0101",
                "support@clubwptgold.com",
            ]
        )
    )

    by_identifier = {row.identifier: row for row in rows}
    assert by_identifier["+1 410 555 0101"].resolved_name == "Coach Mike"
    assert by_identifier["support@clubwptgold.com"].resolved_name == "ClubWPT Gold"
