"""Tests for conversation topic hint inference."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.services.imessage_utils import infer_topic_hints


@dataclass
class FakeMessage:
    text: str | None = None
    normalized_text: str | None = None


class TestInferTopicHints:
    def test_travel_messages(self):
        messages = [
            FakeMessage(text="I booked a flight to Denver"),
            FakeMessage(text="What time should I get to the airport?"),
            FakeMessage(text="Don't forget your luggage"),
        ]
        hints = infer_topic_hints(messages)
        assert "travel" in hints

    def test_work_messages(self):
        messages = [
            FakeMessage(text="Can you review the PR before standup?"),
            FakeMessage(text="The deploy is scheduled for 3pm"),
        ]
        hints = infer_topic_hints(messages)
        assert "work" in hints

    def test_mixed_travel_and_social(self):
        messages = [
            FakeMessage(text="Let's grab dinner after the flight"),
            FakeMessage(text="I'll book the restaurant near the hotel"),
        ]
        hints = infer_topic_hints(messages)
        assert "travel" in hints
        assert "social" in hints

    def test_no_keyword_matches(self):
        messages = [
            FakeMessage(text="hey"),
            FakeMessage(text="what's up"),
            FakeMessage(text="not much"),
        ]
        hints = infer_topic_hints(messages)
        assert hints == []

    def test_empty_messages(self):
        hints = infer_topic_hints([])
        assert hints == []

    def test_empty_text_messages(self):
        messages = [
            FakeMessage(text=None),
            FakeMessage(text=""),
        ]
        hints = infer_topic_hints(messages)
        assert hints == []

    def test_dict_format_messages(self):
        messages: list[dict[str, Any]] = [
            {"text": "The flight lands at 6pm"},
            {"text": "I'll grab an uber from the airport"},
        ]
        hints = infer_topic_hints(messages)
        assert "travel" in hints

    def test_md_in_travel_context(self):
        """'md' alone shouldn't trigger health, but travel keywords should win."""
        messages = [
            FakeMessage(text="i go md early tmr"),
            FakeMessage(text="what time is your flight"),
            FakeMessage(text="i need to get to the airport by 5"),
        ]
        hints = infer_topic_hints(messages)
        assert "travel" in hints
        # "doctor" is not in these messages, so health should not appear
        assert "health" not in hints

    def test_max_three_topics(self):
        messages = [
            FakeMessage(
                text="flight meeting dinner venmo gym lecture"
            ),
        ]
        hints = infer_topic_hints(messages)
        assert len(hints) <= 3

    def test_normalized_text_fallback(self):
        messages = [
            FakeMessage(text=None, normalized_text="heading to the airport now"),
        ]
        hints = infer_topic_hints(messages)
        assert "travel" in hints
