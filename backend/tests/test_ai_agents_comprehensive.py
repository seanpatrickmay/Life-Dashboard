"""Schema validation tests for LLM output models.

Replaces the original broken test file that imported non-existent classes.
Covers TodoExtractionOutput and TodoCalendarTitleOutput parsing.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.llm_outputs import (
    TodoCalendarTitleOutput,
    TodoExtractionItemOutput,
    TodoExtractionOutput,
)


class TestTodoExtractionOutput:
    """Validate TodoExtractionOutput schema parsing."""

    def test_empty_items(self):
        out = TodoExtractionOutput(items=[], summary=None)
        assert out.items == []
        assert out.summary is None

    def test_single_item_minimal(self):
        out = TodoExtractionOutput(
            items=[{"text": "Buy groceries"}],
            summary="One task",
        )
        assert len(out.items) == 1
        assert out.items[0].text == "Buy groceries"
        assert out.items[0].deadline_utc is None
        assert out.items[0].deadline_inferred is False
        assert out.items[0].time_horizon == "this_week"

    def test_single_item_full_fields(self):
        out = TodoExtractionOutput(
            items=[
                {
                    "text": "Submit report",
                    "deadline_utc": "2026-03-25T17:00:00Z",
                    "deadline_inferred": True,
                    "time_horizon": "this_month",
                }
            ],
        )
        item = out.items[0]
        assert item.text == "Submit report"
        assert item.deadline_utc == "2026-03-25T17:00:00Z"
        assert item.deadline_inferred is True
        assert item.time_horizon == "this_month"

    def test_multiple_items(self):
        out = TodoExtractionOutput(
            items=[
                {"text": "Task A"},
                {"text": "Task B", "time_horizon": "this_year"},
            ],
            summary="Two tasks",
        )
        assert len(out.items) == 2
        assert out.items[1].time_horizon == "this_year"

    def test_invalid_time_horizon_rejected(self):
        with pytest.raises(ValidationError):
            TodoExtractionOutput(
                items=[{"text": "Bad", "time_horizon": "next_decade"}],
            )

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            TodoExtractionOutput(
                items=[{"text": "Ok", "bogus_field": 123}],
            )


class TestTodoCalendarTitleOutput:
    """Validate TodoCalendarTitleOutput schema parsing."""

    def test_title_only(self):
        out = TodoCalendarTitleOutput(title="Doctor appointment")
        assert out.title == "Doctor appointment"
        assert out.details is None

    def test_title_and_details(self):
        out = TodoCalendarTitleOutput(
            title="Team standup",
            details="Daily sync with engineering",
        )
        assert out.title == "Team standup"
        assert out.details == "Daily sync with engineering"

    def test_missing_title_rejected(self):
        with pytest.raises(ValidationError):
            TodoCalendarTitleOutput(details="No title provided")

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            TodoCalendarTitleOutput(title="Ok", unknown=True)
