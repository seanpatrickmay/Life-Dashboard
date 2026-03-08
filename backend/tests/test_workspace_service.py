from __future__ import annotations

from datetime import timezone

from app.services.workspace_service import WorkspaceService, _normalize_property_value, _parse_datetime


def test_extract_link_titles_reads_bracket_links_and_mentions() -> None:
    service = WorkspaceService(None)  # type: ignore[arg-type]

    titles = service._extract_link_titles("Link [[Capital One launch brief]] and @Health operating notes.")

    assert titles == ["Capital One launch brief", "Health operating notes"]


def test_normalize_property_value_handles_relations_and_multiselect() -> None:
    assert _normalize_property_value("relation", "42") == 42
    assert _normalize_property_value("relation", [17, 18]) == 17
    assert _normalize_property_value("multi_select", [" one ", "", "two"]) == ["one", "two"]
    assert _normalize_property_value("checkbox", "truthy") is True
    assert _normalize_property_value("status", " in-progress ") == "in-progress"
    assert _normalize_property_value("files", ["", {"url": "https://example.com/file.png"}]) == [
        {"url": "https://example.com/file.png"}
    ]


def test_parse_datetime_accepts_iso_strings() -> None:
    parsed = _parse_datetime("2026-03-08T10:15:00Z")

    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert parsed.isoformat() == "2026-03-08T10:15:00+00:00"
