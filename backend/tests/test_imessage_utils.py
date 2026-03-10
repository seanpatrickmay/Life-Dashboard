from __future__ import annotations

from datetime import UTC, timedelta
import importlib.util
from pathlib import Path
import sqlite3
import sys

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.services.imessage_utils import (
    ProjectCatalogEntry,
    apple_timestamp_to_datetime,
    conversation_display_name,
    extract_attributed_body_text,
    extract_message_text,
    infer_project_match,
    looks_like_completion,
    should_split_message_cluster,
)


def test_apple_timestamp_to_datetime_handles_seconds_microseconds_and_nanoseconds() -> None:
    seconds = 788_918_400
    micros = seconds * 1_000_000
    nanos = seconds * 1_000_000_000

    parsed_seconds = apple_timestamp_to_datetime(seconds)
    parsed_micros = apple_timestamp_to_datetime(micros)
    parsed_nanos = apple_timestamp_to_datetime(nanos)

    assert parsed_seconds is not None
    assert parsed_seconds.tzinfo == UTC
    assert parsed_seconds.year == 2026
    assert parsed_micros == parsed_seconds
    assert parsed_nanos == parsed_seconds


def test_conversation_display_name_prefers_display_then_identifier_then_participants() -> None:
    assert conversation_display_name("Forest Fire", "chat-1", ["a", "b"]) == "Forest Fire"
    assert conversation_display_name(None, "chat-1", ["a", "b"]) == "chat-1"
    assert conversation_display_name(None, None, ["a", "b"]) == "a, b"


def test_infer_project_match_uses_conversation_metadata_and_messages() -> None:
    guess = infer_project_match(
        project_names=["Forest Fire", "Capital One", "Personal"],
        conversation_name="Forest Fire Core Team",
        participants=["alice@example.com", "bob@example.com"],
        message_texts=["Need to finalize the forest fire permit plan before Friday."],
    )

    assert guess.project_name == "Forest Fire"
    assert guess.confidence >= 0.8
    assert guess.candidates[0]["project_name"] == "Forest Fire"


def test_infer_project_match_uses_aliases_and_conversation_affinity() -> None:
    guess = infer_project_match(
        project_catalog=[
            ProjectCatalogEntry(
                name="Forest Fire",
                aliases=("Forest Fire", "FF"),
                notes="County permit plan and debris-removal vendor decisions.",
                conversation_affinity=1.0,
            ),
            ProjectCatalogEntry(
                name="Personal Ops",
                aliases=("Personal Ops", "PO"),
                notes="Errands and reimbursements.",
            ),
        ],
        conversation_name="FF core team",
        participants=["alice@example.com", "bob@example.com"],
        message_texts=["Need the county permit plan locked before Friday."],
    )

    assert guess.project_name == "Forest Fire"
    assert guess.confidence >= 0.8
    assert "previous approved actions" in guess.reason.lower() or "conversation title" in guess.reason.lower()


def test_infer_project_match_returns_none_when_only_generic_language_overlaps() -> None:
    guess = infer_project_match(
        project_catalog=[
            ProjectCatalogEntry(name="Forest Fire", aliases=("Forest Fire",), notes="Permits, vendors, and rollout"),
            ProjectCatalogEntry(name="Personal Ops", aliases=("Personal Ops",), notes="Admin and errands"),
        ],
        conversation_name="Weekend plans",
        participants=["alice@example.com"],
        message_texts=["Let's make a plan for dinner tomorrow."],
    )

    assert guess.project_name is None
    assert guess.confidence == 0.0


def test_infer_project_match_handles_finance_project_language() -> None:
    guess = infer_project_match(
        project_catalog=[
            ProjectCatalogEntry(
                name="Capital One",
                aliases=("Capital One", "Venture X"),
                notes="Card disputes, travel credits, and statement issues.",
            ),
            ProjectCatalogEntry(
                name="Ironman Training",
                aliases=("Ironman Training", "IM"),
                notes="Long rides, swim sets, and brick workouts.",
            ),
            ProjectCatalogEntry(
                name="Personal Ops",
                aliases=("Personal Ops",),
                notes="General errands and admin.",
            ),
        ],
        conversation_name="Capital One",
        participants=["support@capitalone.com"],
        message_texts=["Need to follow up on the Venture X travel credit dispute before the statement closes."],
    )

    assert guess.project_name == "Capital One"
    assert guess.confidence >= 0.6


def test_infer_project_match_handles_training_language() -> None:
    guess = infer_project_match(
        project_catalog=[
            ProjectCatalogEntry(
                name="Capital One",
                aliases=("Capital One", "Venture X"),
                notes="Card disputes, travel credits, and statement issues.",
            ),
            ProjectCatalogEntry(
                name="Ironman Training",
                aliases=("Ironman Training", "IM"),
                notes="Long rides, swim sets, brick workouts, and pace targets.",
            ),
            ProjectCatalogEntry(
                name="Apartment Hunt",
                aliases=("Apartment Hunt",),
                notes="Tours, lease terms, and broker follow-up.",
            ),
        ],
        conversation_name="Ironman Training Coach",
        participants=["coach@example.com"],
        message_texts=["The Ironman Training build keeps the long ride at zone 2 and moves the brick workout to Sunday after the swim set."],
    )

    assert guess.project_name == "Ironman Training"
    assert guess.confidence >= 0.45


def test_looks_like_completion_detects_common_completion_language() -> None:
    assert looks_like_completion("Done, I paid Splitwise.")
    assert looks_like_completion("Handled it this morning")
    assert not looks_like_completion("Can you handle it tomorrow?")


def test_should_split_message_cluster_detects_explicit_topic_boundary() -> None:
    batch = [
        type("Msg", (), {"sent_at_utc": apple_timestamp_to_datetime(788_918_400), "text": "Can you settle up on Splitwise tonight?"})(),
        type("Msg", (), {"sent_at_utc": apple_timestamp_to_datetime(788_918_700), "text": "I can pay after dinner."})(),
    ]
    next_message = type(
        "Msg",
        (),
        {
            "sent_at_utc": apple_timestamp_to_datetime(788_919_000),
            "text": "Switching gears, the permit review is confirmed for Friday at 3.",
        },
    )()

    should_split, reason = should_split_message_cluster(
        batch,
        next_message,
        max_cluster_messages=20,
        max_cluster_gap=timedelta(hours=6),
    )

    assert should_split is True
    assert reason in {"explicit_topic_boundary", "semantic_topic_shift"}


def test_should_split_message_cluster_keeps_same_topic_follow_up_together() -> None:
    batch = [
        type("Msg", (), {"sent_at_utc": apple_timestamp_to_datetime(788_918_400), "text": "The county permit packet still needs the revised PDF."})(),
        type("Msg", (), {"sent_at_utc": apple_timestamp_to_datetime(788_918_700), "text": "Vendor X also needs the site plan attachment."})(),
    ]
    next_message = type(
        "Msg",
        (),
        {
            "sent_at_utc": apple_timestamp_to_datetime(788_919_000),
            "text": "Let's send the final permit PDF and site plan together this afternoon.",
        },
    )()

    should_split, reason = should_split_message_cluster(
        batch,
        next_message,
        max_cluster_messages=20,
        max_cluster_gap=timedelta(hours=6),
    )

    assert should_split is False
    assert reason == "same_topic"


def test_extract_attributed_body_text_recovers_human_message_content() -> None:
    blob = (
        b"streamtypedNSMutableAttributedStringNSString"
        b"+Cteam i have not slept bc my fire alarm has been going off all night"
        b"NSDictionary__kIMMessagePartAttributeNameNSNumberNSValue"
    )

    extracted = extract_attributed_body_text(blob)

    assert extracted == "team i have not slept bc my fire alarm has been going off all night"


def test_extract_message_text_skips_reaction_style_rows() -> None:
    blob = (
        b"streamtypedNSMutableAttributedStringNSString"
        b"+5Loved"
        b"according to me we re building a wallet"
        b"NSDictionary__kIMMessagePartAttributeNameNSNumberNSValue"
    )

    extracted = extract_message_text(
        None,
        attributed_body=blob,
        associated_message_type=2000,
        item_type=0,
    )

    assert extracted is None


def test_fetch_message_batch_reads_minimal_messages_schema(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "sync_imessage.py"
    if str(repo_root / "backend") not in sys.path:
        sys.path.insert(0, str(repo_root / "backend"))
    spec = importlib.util.spec_from_file_location("sync_imessage", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_imessage"] = module
    spec.loader.exec_module(module)

    db_path = tmp_path / "chat.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, guid TEXT, chat_identifier TEXT, display_name TEXT, service_name TEXT);
            CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
            CREATE TABLE message (
              ROWID INTEGER PRIMARY KEY,
              guid TEXT,
              service TEXT,
              handle_id INTEGER,
              is_from_me INTEGER,
              text TEXT,
              attributedBody BLOB,
              cache_has_attachments INTEGER,
              associated_message_guid TEXT,
              associated_message_type INTEGER,
              item_type INTEGER,
              date INTEGER,
              date_delivered INTEGER,
              date_read INTEGER
            );
            CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
            """
        )
        conn.execute(
            "INSERT INTO chat (ROWID, guid, chat_identifier, display_name, service_name) VALUES (1, 'chat-1', 'forest-fire', 'Forest Fire', 'iMessage')"
        )
        conn.execute("INSERT INTO handle (ROWID, id) VALUES (1, '+15555550123')")
        conn.execute(
            """
            INSERT INTO message (ROWID, guid, service, handle_id, is_from_me, text, attributedBody, cache_has_attachments, associated_message_guid, associated_message_type, item_type, date, date_delivered, date_read)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                10,
                "msg-10",
                "iMessage",
                1,
                0,
                "Need to update the architecture doc.",
                None,
                0,
                None,
                0,
                0,
                788_918_400,
                788_918_401,
                788_918_402,
            ),
        )
        conn.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 10)")
        conn.commit()
    finally:
        conn.close()

    source_conn = module.open_source_db(str(db_path))
    try:
        batch = module.fetch_message_batch(
            source_conn,
            after_row_id=0,
            batch_size=10,
            cutoff_utc=None,
        )
    finally:
        source_conn.close()

    assert len(batch) == 1
    row = batch[0]
    assert row.chat_guid == "chat-1"
    assert row.message_guid == "msg-10"
    assert row.text == "Need to update the architecture doc."
    assert row.handle_identifier == "+15555550123"
    assert row.sent_at_utc is not None
    assert row.sent_at_utc.year == 2026


def test_fetch_message_batch_extracts_attributed_body_when_text_is_missing(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "sync_imessage.py"
    if str(repo_root / "backend") not in sys.path:
        sys.path.insert(0, str(repo_root / "backend"))
    spec = importlib.util.spec_from_file_location("sync_imessage", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_imessage"] = module
    spec.loader.exec_module(module)

    db_path = tmp_path / "chat.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, guid TEXT, chat_identifier TEXT, display_name TEXT, service_name TEXT);
            CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
            CREATE TABLE message (
              ROWID INTEGER PRIMARY KEY,
              guid TEXT,
              service TEXT,
              handle_id INTEGER,
              is_from_me INTEGER,
              text TEXT,
              attributedBody BLOB,
              cache_has_attachments INTEGER,
              associated_message_guid TEXT,
              associated_message_type INTEGER,
              item_type INTEGER,
              date INTEGER,
              date_delivered INTEGER,
              date_read INTEGER
            );
            CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
            """
        )
        conn.execute(
            "INSERT INTO chat (ROWID, guid, chat_identifier, display_name, service_name) VALUES (1, 'chat-1', 'forest-fire', 'Forest Fire', 'RCS')"
        )
        conn.execute("INSERT INTO handle (ROWID, id) VALUES (1, '+15555550123')")
        conn.execute(
            """
            INSERT INTO message (ROWID, guid, service, handle_id, is_from_me, text, attributedBody, cache_has_attachments, associated_message_guid, associated_message_type, item_type, date, date_delivered, date_read)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                10,
                "msg-10",
                "RCS",
                1,
                0,
                None,
                b"streamtypedNSMutableAttributedStringNSString+CHello from attributed bodyNSDictionary__kIMMessagePartAttributeNameNSNumberNSValue",
                0,
                None,
                0,
                0,
                788_918_400,
                788_918_401,
                788_918_402,
            ),
        )
        conn.execute("INSERT INTO chat_message_join (chat_id, message_id) VALUES (1, 10)")
        conn.commit()
    finally:
        conn.close()

    source_conn = module.open_source_db(str(db_path))
    try:
        batch = module.fetch_message_batch(
            source_conn,
            after_row_id=0,
            batch_size=10,
            cutoff_utc=None,
        )
    finally:
        source_conn.close()

    assert len(batch) == 1
    row = batch[0]
    assert row.text == "Hello from attributed body"
    assert row.content_source == "attributedBody"
