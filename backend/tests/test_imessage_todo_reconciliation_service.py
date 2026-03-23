from __future__ import annotations

from app.services.imessage_todo_reconciliation_service import score_completion_match


def test_score_completion_match_prefers_specific_overlap() -> None:
    score, reason = score_completion_match(
        todo_text="Send the 18.01 form to Madelyn",
        message_text="Just sent the 18.01 form to Madelyn.",
        is_from_me=True,
        open_todos_in_conversation=2,
    )

    assert score >= 0.58
    assert "Madelyn" in reason or "18" in reason


def test_score_completion_match_accepts_specific_action_update_language() -> None:
    score, reason = score_completion_match(
        todo_text="Call Pat when I wake up",
        message_text="I called Pat just now.",
        is_from_me=True,
        open_todos_in_conversation=2,
    )

    assert score >= 0.58
    assert "action update" in reason


def test_score_completion_match_allows_short_done_when_only_one_open_todo() -> None:
    score, reason = score_completion_match(
        todo_text="Take the trash out",
        message_text="Done",
        is_from_me=True,
        open_todos_in_conversation=1,
    )

    assert score >= 0.52
    assert "single open todo" in reason


def test_score_completion_match_rejects_short_done_with_multiple_open_todos() -> None:
    score, reason = score_completion_match(
        todo_text="Take the trash out",
        message_text="Done",
        is_from_me=True,
        open_todos_in_conversation=3,
    )

    assert score < 0.58
    assert "single open todo" not in reason


def test_score_completion_match_rejects_incoming_messages() -> None:
    score, reason = score_completion_match(
        todo_text="Ask Madelyn about graduation tickets",
        message_text="Thanks, sounds good.",
        is_from_me=False,
        open_todos_in_conversation=1,
    )

    assert score == 0.0
    assert "outgoing message" in reason
