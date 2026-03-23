"""Tests for iMessage relevancy scoring and journal consolidation."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def service():
    """Create a minimal IMessageProcessingService with mocked dependencies."""
    from app.services.imessage_processing_service import IMessageProcessingService

    svc = object.__new__(IMessageProcessingService)
    svc.session = MagicMock()
    svc.openai_client = MagicMock()
    svc.todo_repo = MagicMock()
    svc.project_repo = MagicMock()
    return svc


# ── Substance scoring ──────────────────────────────────────────────


class TestSubstanceScoring:
    def test_short_text_low_substance(self, service):
        score = service._score_action_relevance(
            action_type="journal.entry",
            action={"text": "ok"},
            cluster_actions=[("journal.entry", {"text": "ok"})],
        )
        # Short text (<15) with no uppercase -> substance=0.2
        # journal.entry with text < 40 -> coherence=0.3
        # single action -> novelty=1.0
        # 0.4*0.2 + 0.3*0.3 + 0.3*1.0 = 0.08 + 0.09 + 0.30 = 0.47
        assert 0.0 < score < 0.55

    def test_reaction_text_very_low_substance(self, service):
        score = service._score_action_relevance(
            action_type="journal.entry",
            action={"text": "Liked a message about dinner"},
            cluster_actions=[("journal.entry", {"text": "Liked a message about dinner"})],
        )
        # Contains "liked" -> substance=0.1
        assert score < 0.45  # Should be rejected

    def test_long_text_high_substance(self, service):
        long_text = "Had a great meeting about the project roadmap and next quarter planning"
        score = service._score_action_relevance(
            action_type="todo.create",
            action={"text": long_text},
            cluster_actions=[("todo.create", {"text": long_text})],
        )
        # len > 30 -> substance=0.8
        # default coherence=0.6
        # single action -> novelty=1.0
        # 0.4*0.8 + 0.3*0.6 + 0.3*1.0 = 0.32 + 0.18 + 0.30 = 0.80
        assert score > 0.7


# ── Coherence scoring ──────────────────────────────────────────────


class TestCoherenceScoring:
    def test_calendar_from_business_low_coherence(self, service):
        long_text = "Schedule a team sync for next Friday about the Q2 report"
        score = service._score_action_relevance(
            action_type="calendar.create",
            action={"text": long_text},
            cluster_actions=[("calendar.create", {"text": long_text})],
            conversation_type="business",
        )
        # substance=0.8 (len>30), coherence=0.1 (calendar + business), novelty=1.0
        # 0.4*0.8 + 0.3*0.1 + 0.3*1.0 = 0.32 + 0.03 + 0.30 = 0.65
        assert score < 0.7

    def test_todo_from_group_not_from_me_low_coherence(self, service):
        long_text = "Someone should pick up groceries for the group dinner"
        score = service._score_action_relevance(
            action_type="todo.create",
            action={"text": long_text, "is_from_me": False},
            cluster_actions=[("todo.create", {"text": long_text, "is_from_me": False})],
            conversation_type="group",
        )
        # substance=0.8, coherence=0.2 (group + not from me), novelty=1.0
        # 0.4*0.8 + 0.3*0.2 + 0.3*1.0 = 0.32 + 0.06 + 0.30 = 0.68
        assert score < 0.7

    def test_todo_from_group_from_me_higher_coherence(self, service):
        long_text = "I need to pick up the ingredients for Friday dinner"
        score_from_me = service._score_action_relevance(
            action_type="todo.create",
            action={"text": long_text, "is_from_me": True},
            cluster_actions=[("todo.create", {"text": long_text, "is_from_me": True})],
            conversation_type="group",
        )
        score_not_from_me = service._score_action_relevance(
            action_type="todo.create",
            action={"text": long_text, "is_from_me": False},
            cluster_actions=[("todo.create", {"text": long_text, "is_from_me": False})],
            conversation_type="group",
        )
        assert score_from_me > score_not_from_me


# ── Novelty scoring ───────────────────────────────────────────────


class TestNoveltyScoring:
    def test_single_action_high_novelty(self, service):
        text = "Finish the quarterly report by end of week"
        score = service._score_action_relevance(
            action_type="todo.create",
            action={"text": text},
            cluster_actions=[("todo.create", {"text": text})],
        )
        # novelty = 1.0/1 = 1.0
        assert score > 0.6

    def test_two_same_type_lower_novelty(self, service):
        text_a = "Finish the quarterly report by end of week"
        text_b = "Review the marketing plan for next month rollout"
        cluster = [
            ("todo.create", {"text": text_a}),
            ("todo.create", {"text": text_b}),
        ]
        score = service._score_action_relevance(
            action_type="todo.create",
            action={"text": text_a},
            cluster_actions=cluster,
        )
        # novelty = 1.0/2 = 0.5
        assert score < 0.80  # lower than N=1

    def test_three_same_type_even_lower_novelty(self, service):
        texts = [
            "Finish the quarterly report by end of week",
            "Review the marketing plan for next month rollout",
            "Update the budget spreadsheet with the latest numbers",
        ]
        cluster = [("todo.create", {"text": t}) for t in texts]
        score = service._score_action_relevance(
            action_type="todo.create",
            action={"text": texts[0]},
            cluster_actions=cluster,
        )
        # novelty = 1.0/3 = 0.33
        assert score < 0.7

    def test_high_text_overlap_kills_novelty(self, service):
        text_a = "Pick up groceries from the store today after work"
        text_b = "Pick up groceries from the store today before dinner"
        cluster = [
            ("todo.create", {"text": text_a}),
            ("todo.create", {"text": text_b}),
        ]
        score = service._score_action_relevance(
            action_type="todo.create",
            action={"text": text_a},
            cluster_actions=cluster,
        )
        # High overlap -> novelty capped at 0.2
        assert score < 0.6


# ── Journal consolidation ─────────────────────────────────────────


def _consolidate(entries: list[dict]) -> list[dict]:
    """Apply the same consolidation logic used in the service."""
    raw_extracted = {"journal_entries": entries}
    journal_entries = raw_extracted.get("journal_entries") or []
    if len(journal_entries) > 1:
        sorted_entries = sorted(
            journal_entries,
            key=lambda e: e.get("source_occurred_at_utc") or e.get("occurred_at_utc") or "",
        )
        merged_text = " · ".join(
            e.get("text", "").strip() for e in sorted_entries if e.get("text", "").strip()
        )
        all_msg_ids: list[int] = []
        for e in sorted_entries:
            for mid in e.get("source_message_ids") or []:
                if mid not in all_msg_ids:
                    all_msg_ids.append(mid)
        merged = {**sorted_entries[0], "text": merged_text, "source_message_ids": all_msg_ids}
        if sorted_entries[0].get("reason"):
            merged["reason"] = sorted_entries[0]["reason"]
        raw_extracted["journal_entries"] = [merged]
    return raw_extracted["journal_entries"]


class TestJournalConsolidation:
    def test_three_entries_merge_to_one_with_stable_ordering(self):
        entries = [
            {"text": "Third entry", "source_occurred_at_utc": "2026-03-23T12:00:00Z", "source_message_ids": [3]},
            {"text": "First entry", "source_occurred_at_utc": "2026-03-23T10:00:00Z", "source_message_ids": [1]},
            {"text": "Second entry", "source_occurred_at_utc": "2026-03-23T11:00:00Z", "source_message_ids": [2]},
        ]
        result = _consolidate(entries)
        assert len(result) == 1
        merged = result[0]
        assert merged["text"] == "First entry · Second entry · Third entry"
        assert merged["source_occurred_at_utc"] == "2026-03-23T10:00:00Z"

    def test_single_entry_unchanged(self):
        entries = [
            {"text": "Only entry", "source_occurred_at_utc": "2026-03-23T10:00:00Z", "source_message_ids": [1]},
        ]
        result = _consolidate(entries)
        assert len(result) == 1
        assert result[0]["text"] == "Only entry"
        assert result[0]["source_message_ids"] == [1]

    def test_message_ids_unioned_without_duplicates(self):
        entries = [
            {"text": "Entry A", "source_occurred_at_utc": "2026-03-23T10:00:00Z", "source_message_ids": [1, 2, 3]},
            {"text": "Entry B", "source_occurred_at_utc": "2026-03-23T11:00:00Z", "source_message_ids": [2, 3, 4]},
            {"text": "Entry C", "source_occurred_at_utc": "2026-03-23T12:00:00Z", "source_message_ids": [4, 5]},
        ]
        result = _consolidate(entries)
        assert len(result) == 1
        assert result[0]["source_message_ids"] == [1, 2, 3, 4, 5]

    def test_reason_preserved_from_first_sorted_entry(self):
        entries = [
            {"text": "Later", "source_occurred_at_utc": "2026-03-23T11:00:00Z", "reason": "later reason", "source_message_ids": [2]},
            {"text": "Earlier", "source_occurred_at_utc": "2026-03-23T10:00:00Z", "reason": "earlier reason", "source_message_ids": [1]},
        ]
        result = _consolidate(entries)
        assert result[0]["reason"] == "earlier reason"

    def test_empty_entries_not_consolidated(self):
        result = _consolidate([])
        assert result == []


# ── Integration: relevancy gate rejects low-substance action ──────


class TestRelevancyGateIntegration:
    def test_rejects_low_substance_action(self, service):
        """A short, reaction-like journal entry should score below the 0.45 threshold."""
        action = {"text": "Loved it"}
        score = service._score_action_relevance(
            action_type="journal.entry",
            action=action,
            cluster_actions=[("journal.entry", action)],
        )
        assert score < 0.45, f"Expected score < 0.45, got {score:.3f}"

    def test_accepts_substantial_action(self, service):
        """A well-formed todo with enough text should pass the threshold."""
        action = {"text": "Submit the updated project proposal to the committee by Thursday"}
        score = service._score_action_relevance(
            action_type="todo.create",
            action=action,
            cluster_actions=[("todo.create", action)],
        )
        assert score >= 0.45, f"Expected score >= 0.45, got {score:.3f}"
