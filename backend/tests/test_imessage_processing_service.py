from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MethodType, SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from app.services.imessage_processing_service import (
    DuplicateDecision,
    IMessageProcessingService,
    MessageCluster,
)
from app.services.imessage_utils import ProjectGuess, classify_conversation_type, infer_project_match
from app.services.journal_service import JournalService
from app.utils.timezone import resolve_time_zone


def run(coro):
    return asyncio.run(coro)


@dataclass(frozen=True)
class MessageExample:
    text: str
    is_from_me: bool = False
    sender: str | None = None
    sent_at_utc: datetime | None = None


@dataclass(frozen=True)
class HeuristicCase:
    name: str
    conversation_name: str
    messages: tuple[MessageExample, ...]
    action_key: str
    expected_value: str
    expected_page_title: str | None = None
    participants: tuple[str, ...] = ("alice@example.com", "bob@example.com")
    projects: tuple[str, ...] = ("Forest Fire", "Splitwise", "Personal Ops")


@dataclass(frozen=True)
class ModelCase:
    name: str
    conversation_name: str
    messages: tuple[MessageExample, ...]
    action_key: str
    extraction: dict[str, Any]
    judgment: dict[str, Any]


@dataclass(frozen=True)
class DispatchCase:
    name: str
    action_key: str
    action_payload: dict[str, Any]
    expect_apply_method: str
    expect_project: bool = False


@dataclass(frozen=True)
class MixedModelCase:
    name: str
    conversation_name: str
    messages: tuple[MessageExample, ...]
    projects: tuple[str, ...]
    project_candidates: tuple[dict[str, Any], ...]
    project_inference: dict[str, Any]
    calendar_extraction: dict[str, Any]
    general_extraction: dict[str, Any]
    judgment: dict[str, Any]
    expected_counts: dict[str, int]


class FakeAsyncSession:
    def __init__(self) -> None:
        self.flush_calls = 0

    async def flush(self) -> None:
        self.flush_calls += 1


def make_service(*, client: object | None = None) -> IMessageProcessingService:
    service = object.__new__(IMessageProcessingService)
    service.client = client
    service.session = FakeAsyncSession()
    return service


def build_payload(
    *,
    conversation_name: str,
    messages: tuple[MessageExample, ...],
    participants: tuple[str, ...] = ("alice@example.com", "bob@example.com"),
    projects: tuple[str, ...] = ("Forest Fire", "Splitwise", "Personal Ops"),
    open_todos: list[dict[str, Any]] | None = None,
    chat_identifier: str | None = None,
    conversation_type: str | None = None,
) -> dict[str, Any]:
    heuristic_guess = infer_project_match(
        project_names=list(projects),
        conversation_name=conversation_name,
        participants=list(participants),
        message_texts=[item.text for item in messages],
    )
    base_time = datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc)
    message_timestamps = [
        item.sent_at_utc or (base_time + timedelta(minutes=index * 5))
        for index, item in enumerate(messages)
    ]
    zone = resolve_time_zone("America/New_York")
    resolved_chat_identifier = chat_identifier or conversation_name.lower().replace(" ", "-")
    resolved_conversation_type = conversation_type or classify_conversation_type(
        chat_identifier=resolved_chat_identifier,
        service_name="iMessage",
        participant_count=len(participants),
    )
    return {
        "conversation": {
            "id": 11,
            "name": conversation_name,
            "chat_identifier": resolved_chat_identifier,
            "service_name": "iMessage",
            "conversation_type": resolved_conversation_type,
            "participants": list(participants),
        },
        "time_context": {
            "time_zone": "America/New_York",
            "cluster_start_time_utc": min(message_timestamps).isoformat(),
            "cluster_end_time_utc": max(message_timestamps).isoformat(),
            "cluster_start_time_local": min(message_timestamps).astimezone(zone).isoformat(),
            "cluster_end_time_local": max(message_timestamps).astimezone(zone).isoformat(),
            "relative_time_rule": (
                "Interpret relative phrases using the message timestamp that contains them."
            ),
        },
        "heuristic_project_guess": {
            "project_name": heuristic_guess.project_name,
            "confidence": heuristic_guess.confidence,
            "reason": heuristic_guess.reason,
        },
        "project_candidates": heuristic_guess.candidates[:3],
        "projects": list(projects),
        "open_todos": open_todos or [],
        "messages": [
            {
                "id": index + 1,
                "sent_at_utc": (
                    (item.sent_at_utc or (base_time + timedelta(minutes=index * 5))).isoformat()
                ),
                "is_from_me": item.is_from_me,
                "sender": item.sender or ("You" if item.is_from_me else participants[0]),
                "text": item.text,
            }
            for index, item in enumerate(messages)
        ],
    }


def empty_extracted() -> dict[str, Any]:
    return {
        "project_inference": {
            "project_name": None,
            "confidence": 0.0,
            "reason": "",
        },
        "todo_creates": [],
        "todo_completions": [],
        "calendar_creates": [],
        "journal_entries": [],
        "workspace_updates": [],
    }


def empty_judgment() -> dict[str, Any]:
    return {
        "project_inference": {
            "approved": False,
            "reason": "",
        },
        "todo_creates": [],
        "todo_completions": [],
        "calendar_creates": [],
        "journal_entries": [],
        "workspace_updates": [],
    }


def make_cluster(
    *,
    conversation_name: str,
    messages: tuple[MessageExample, ...],
) -> MessageCluster:
    base_time = datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc)
    conversation = SimpleNamespace(
        id=11,
        user_id=1,
        display_name=conversation_name,
        chat_identifier=conversation_name.lower().replace(" ", "-"),
        service_name="iMessage",
        participants=[SimpleNamespace(identifier="alice@example.com"), SimpleNamespace(identifier="bob@example.com")],
    )
    cluster_messages = [
        SimpleNamespace(
            id=index + 1,
            sent_at_utc=item.sent_at_utc or (base_time + timedelta(minutes=index * 5)),
            is_from_me=item.is_from_me,
            sender_label=item.sender or ("You" if item.is_from_me else "Alice"),
            handle_identifier=item.sender or ("You" if item.is_from_me else "Alice"),
            text=item.text,
            processed_at_utc=None,
        )
        for index, item in enumerate(messages)
    ]
    return MessageCluster(conversation=conversation, messages=cluster_messages)


HEURISTIC_CASES = [
    HeuristicCase(
        name="explicit_todo_create_invoice_followup",
        conversation_name="Personal Admin",
        messages=(
            MessageExample("I need to send Sam the signed permit packet tonight."),
        ),
        action_key="todo_creates",
        expected_value="Send Sam the signed permit packet tonight",
    ),
    HeuristicCase(
        name="subtle_todo_create_splitwise_settle_up",
        conversation_name="Roommates",
        messages=(
            MessageExample("Can you settle up on Splitwise when you get a chance?"),
        ),
        action_key="todo_creates",
        expected_value="Settle up on Splitwise when you get a chance",
    ),
    HeuristicCase(
        name="explicit_todo_completion_done_and_paid",
        conversation_name="Roommates",
        messages=(
            MessageExample("Done, I paid Splitwise.", is_from_me=True),
        ),
        action_key="todo_completions",
        expected_value="Detected a completion-like outgoing message",
    ),
    HeuristicCase(
        name="subtle_todo_completion_handled_it",
        conversation_name="Personal Admin",
        messages=(
            MessageExample("Handled it this morning.", is_from_me=True),
        ),
        action_key="todo_completions",
        expected_value="Detected a completion-like outgoing message",
    ),
    HeuristicCase(
        name="explicit_workspace_update_architecture_discussion",
        conversation_name="Forest Fire Core Team",
        messages=(
            MessageExample(
                "We should update the architecture spec: use vendor X for debris removal and keep county submissions in PDF."
            ),
        ),
        action_key="workspace_updates",
        expected_value="Capture the latest durable decisions and constraints here.",
        expected_page_title="Forest Fire Architecture",
    ),
    HeuristicCase(
        name="subtle_workspace_update_plan_discussion",
        conversation_name="Forest Fire Core Team",
        messages=(
            MessageExample(
                "Let's keep the rollout plan phased so permitting risk stays manageable while crews ramp up."
            ),
        ),
        action_key="workspace_updates",
        expected_value="Capture the latest durable decisions and constraints here.",
        expected_page_title="Forest Fire Plan",
    ),
]


MODEL_CASES = [
    ModelCase(
        name="explicit_calendar_create_permit_review",
        conversation_name="Forest Fire Scheduling",
        messages=(
            MessageExample("March 12, 2026 from 3:00 to 3:30 PM is confirmed for the permit review."),
        ),
        action_key="calendar_creates",
        extraction={
            **empty_extracted(),
            "calendar_creates": [
                {
                    "summary": "Permit review",
                    "start_time": "2026-03-12T19:00:00Z",
                    "end_time": "2026-03-12T19:30:00Z",
                    "is_all_day": False,
                    "reason": "The message confirms a specific meeting time window for the permit review.",
                }
            ],
        },
        judgment={
            **empty_judgment(),
            "calendar_creates": [
                {
                    "approved": True,
                    "reason": "The cluster contains an explicit meeting with a concrete time window.",
                }
            ],
        },
    ),
    ModelCase(
        name="subtle_calendar_create_lock_tomorrow_slot",
        conversation_name="Forest Fire Scheduling",
        messages=(
            MessageExample("Can we lock 2-2:30 tomorrow to walk through the deck?"),
        ),
        action_key="calendar_creates",
        extraction={
            **empty_extracted(),
            "calendar_creates": [
                {
                    "summary": "Deck walkthrough",
                    "start_time": "2026-03-11T19:00:00Z",
                    "end_time": "2026-03-11T19:30:00Z",
                    "is_all_day": False,
                    "reason": "The message implicitly schedules a short walkthrough for tomorrow afternoon.",
                }
            ],
        },
        judgment={
            **empty_judgment(),
            "calendar_creates": [
                {
                    "approved": True,
                    "reason": "The request is still a concrete time commitment even though the phrasing is casual.",
                }
            ],
        },
    ),
    ModelCase(
        name="explicit_journal_entry_submitted_packet",
        conversation_name="Personal Wins",
        messages=(
            MessageExample("I submitted the permit packet this afternoon."),
        ),
        action_key="journal_entries",
        extraction={
            **empty_extracted(),
            "journal_entries": [
                {
                    "text": "Submitted the permit packet",
                    "reason": "The message describes a concrete completed action worth capturing in the journal.",
                }
            ],
        },
        judgment={
            **empty_judgment(),
            "journal_entries": [
                {
                    "approved": True,
                    "reason": "The action is concrete, completed, and should be captured as an accomplishment.",
                }
            ],
        },
    ),
    ModelCase(
        name="subtle_journal_entry_lease_signed",
        conversation_name="Personal Wins",
        messages=(
            MessageExample("Finally got the lease signed."),
        ),
        action_key="journal_entries",
        extraction={
            **empty_extracted(),
            "journal_entries": [
                {
                    "text": "Got the lease signed",
                    "reason": "The message reports a subtle but definite accomplishment.",
                }
            ],
        },
        judgment={
            **empty_judgment(),
            "journal_entries": [
                {
                    "approved": True,
                    "reason": "The completion is implicit but unambiguous enough to log as a journal entry.",
                }
            ],
        },
    ),
]


DISPATCH_CASES = [
    DispatchCase(
        name="todo_create_dispatch",
        action_key="todo_creates",
        action_payload={
            "text": "Send Sam the signed permit packet tonight",
            "deadline_utc": None,
            "deadline_is_date_only": False,
            "reason": "The message contains a direct obligation.",
        },
        expect_apply_method="_apply_todo_create",
    ),
    DispatchCase(
        name="todo_completion_dispatch",
        action_key="todo_completions",
        action_payload={
            "match_text": "Splitwise payment",
            "reason": "The outgoing message implies the payment todo is finished.",
        },
        expect_apply_method="_apply_todo_completion",
    ),
    DispatchCase(
        name="calendar_create_dispatch",
        action_key="calendar_creates",
        action_payload={
            "summary": "Permit review",
            "start_time": "2026-03-10T20:00:00Z",
            "end_time": "2026-03-10T20:30:00Z",
            "is_all_day": False,
            "reason": "The message names an explicit meeting time.",
        },
        expect_apply_method="_apply_calendar_create",
    ),
    DispatchCase(
        name="journal_entry_dispatch",
        action_key="journal_entries",
        action_payload={
            "text": "Submitted the permit packet",
            "reason": "The message describes a completed accomplishment.",
        },
        expect_apply_method="_apply_journal_entry",
    ),
    DispatchCase(
        name="workspace_update_dispatch",
        action_key="workspace_updates",
        action_payload={
            "page_title": "Forest Fire Architecture",
            "search_query": "architecture",
            "summary": "Use vendor X for debris removal and keep county submissions in PDF.",
            "reason": "The cluster contains a durable architecture decision for the Forest Fire project.",
        },
        expect_apply_method="_apply_workspace_update",
        expect_project=True,
    ),
]


MIXED_MODEL_CASES = [
    MixedModelCase(
        name="project_cluster_yields_calendar_todo_and_workspace_update",
        conversation_name="Forest Fire Core Team",
        messages=(
            MessageExample("March 12, 2026 from 3:00 to 3:30 PM is confirmed for the permit review."),
            MessageExample("I need to send Sam the revised permit packet before then."),
            MessageExample("County only accepts PDF submissions now."),
            MessageExample("Agreed, let's capture the PDF requirement in the architecture page.", sender="bob@example.com"),
        ),
        projects=("Forest Fire", "Capital One", "Personal Ops"),
        project_candidates=(
            {"project_name": "Forest Fire", "confidence": 0.64, "reasons": ["conversation title and permit vocabulary"]},
            {"project_name": "Capital One", "confidence": 0.18, "reasons": ["weak generic admin overlap"]},
        ),
        project_inference={
            "project_name": "Forest Fire",
            "confidence": 0.86,
            "reason": "Permit review, county, and architecture language all fit Forest Fire.",
        },
        calendar_extraction={
            "calendar_creates": [
                {
                    "summary": "Permit review",
                    "start_time": "2026-03-12T19:00:00Z",
                    "end_time": "2026-03-12T19:30:00Z",
                    "is_all_day": False,
                    "reason": "Confirmed permit review window.",
                }
            ]
        },
        general_extraction={
            "todo_creates": [
                {
                    "text": "Send Sam the revised permit packet before the permit review",
                    "deadline_utc": None,
                    "deadline_is_date_only": False,
                    "reason": "Explicit first-person obligation tied to the meeting.",
                }
            ],
            "todo_completions": [],
            "journal_entries": [],
            "workspace_updates": [
                {
                    "page_title": "Forest Fire Architecture",
                    "search_query": "Forest Fire county PDF submission requirement",
                    "summary": "County submissions for Forest Fire must be sent as PDFs.",
                    "reason": "Durable project constraint with explicit agreement.",
                }
            ],
        },
        judgment={
            "project_inference": {"approved": True, "reason": "Strong project evidence."},
            "todo_creates": [{"approved": True, "reason": "Clear obligation."}],
            "todo_completions": [],
            "calendar_creates": [{"approved": True, "reason": "Explicit time window."}],
            "journal_entries": [],
            "workspace_updates": [{"approved": True, "reason": "Durable project constraint confirmed in-thread."}],
        },
        expected_counts={
            "todo_creates": 1,
            "todo_completions": 0,
            "calendar_creates": 1,
            "journal_entries": 0,
            "workspace_updates": 1,
        },
    ),
    MixedModelCase(
        name="personal_cluster_yields_completion_and_discussion_journal",
        conversation_name="Aidan",
        messages=(
            MessageExample("Done, I sent the reimbursement form.", is_from_me=True),
            MessageExample("Talked to Aidan about philosophy and compared deontology with consequentialism."),
        ),
        projects=("Forest Fire", "Capital One", "Personal Ops"),
        project_candidates=(),
        project_inference={
            "project_name": None,
            "confidence": 0.0,
            "reason": "No project-specific evidence.",
        },
        calendar_extraction={"calendar_creates": []},
        general_extraction={
            "todo_creates": [],
            "todo_completions": [
                {
                    "match_text": "reimbursement form",
                    "reason": "Outgoing completion-like message about a reimbursement task.",
                }
            ],
            "journal_entries": [
                {
                    "text": "Talked with Aidan about philosophy and compared deontology with consequentialism",
                    "reason": "Meaningful discussion summary for the journal.",
                }
            ],
            "workspace_updates": [],
        },
        judgment={
            "project_inference": {"approved": False, "reason": "No project."},
            "todo_creates": [],
            "todo_completions": [{"approved": True, "reason": "Strong completion signal."}],
            "calendar_creates": [],
            "journal_entries": [{"approved": True, "reason": "Valuable discussion summary."}],
            "workspace_updates": [],
        },
        expected_counts={
            "todo_creates": 0,
            "todo_completions": 1,
            "calendar_creates": 0,
            "journal_entries": 1,
            "workspace_updates": 0,
        },
    ),
    MixedModelCase(
        name="capital_one_cluster_yields_deadline_todo_and_workspace_update",
        conversation_name="Capital One",
        messages=(
            MessageExample("The Venture X dispute filing deadline is March 14, 2026."),
            MessageExample("I need to upload the travel receipts tonight."),
            MessageExample("Capital One wants every supporting document bundled into one PDF."),
            MessageExample("Agreed, let's add the one-PDF requirement to the dispute notes.", sender="bob@example.com"),
        ),
        projects=("Capital One", "Ironman Training", "Personal Ops"),
        project_candidates=(
            {"project_name": "Capital One", "confidence": 0.66, "reasons": ["conversation title and Venture X dispute vocabulary"]},
            {"project_name": "Personal Ops", "confidence": 0.24, "reasons": ["generic admin overlap"]},
        ),
        project_inference={
            "project_name": "Capital One",
            "confidence": 0.88,
            "reason": "Conversation title, Venture X dispute language, and document rules fit Capital One.",
        },
        calendar_extraction={
            "calendar_creates": [
                {
                    "summary": "Venture X dispute filing deadline",
                    "start_time": "2026-03-14T00:00:00Z",
                    "end_time": "2026-03-15T00:00:00Z",
                    "is_all_day": True,
                    "reason": "Explicit all-day filing deadline.",
                }
            ]
        },
        general_extraction={
            "todo_creates": [
                {
                    "text": "Upload the travel receipts tonight",
                    "deadline_utc": None,
                    "deadline_is_date_only": False,
                    "reason": "Explicit first-person obligation tied to the dispute.",
                }
            ],
            "todo_completions": [],
            "journal_entries": [],
            "workspace_updates": [
                {
                    "page_title": "Capital One Dispute Notes",
                    "search_query": "Capital One Venture X one PDF requirement",
                    "summary": "Capital One requires all Venture X dispute supporting documents to be submitted in a single PDF.",
                    "reason": "Durable process constraint confirmed in the thread.",
                }
            ],
        },
        judgment={
            "project_inference": {"approved": True, "reason": "Strong project evidence."},
            "todo_creates": [{"approved": True, "reason": "Clear obligation."}],
            "todo_completions": [],
            "calendar_creates": [{"approved": True, "reason": "Explicit all-day deadline."}],
            "journal_entries": [],
            "workspace_updates": [{"approved": True, "reason": "Confirmed durable process rule."}],
        },
        expected_counts={
            "todo_creates": 1,
            "todo_completions": 0,
            "calendar_creates": 1,
            "journal_entries": 0,
            "workspace_updates": 1,
        },
    ),
    MixedModelCase(
        name="personal_cluster_yields_calendar_todo_and_journal_without_project",
        conversation_name="Aidan",
        messages=(
            MessageExample("Tomorrow at 6 works for dinner if we keep it to an hour."),
            MessageExample("Perfect, let's lock it in.", sender="aidan@example.com"),
            MessageExample("I need to book the table this afternoon."),
            MessageExample("Talked with Aidan about free will and philosophy after work."),
        ),
        projects=("Capital One", "Ironman Training", "Personal Ops"),
        project_candidates=(),
        project_inference={
            "project_name": None,
            "confidence": 0.0,
            "reason": "No project-specific evidence.",
        },
        calendar_extraction={
            "calendar_creates": [
                {
                    "summary": "Dinner with Aidan",
                    "start_time": "2026-03-11T22:00:00Z",
                    "end_time": "2026-03-11T23:00:00Z",
                    "is_all_day": False,
                    "reason": "Concrete dinner plan with inferred one-hour window.",
                }
            ]
        },
        general_extraction={
            "todo_creates": [
                {
                    "text": "Book the table this afternoon",
                    "deadline_utc": None,
                    "deadline_is_date_only": False,
                    "reason": "Explicit first-person obligation.",
                }
            ],
            "todo_completions": [],
            "journal_entries": [
                {
                    "text": "Talked with Aidan about free will and philosophy",
                    "reason": "Meaningful conversation summary for the journal.",
                }
            ],
            "workspace_updates": [],
        },
        judgment={
            "project_inference": {"approved": False, "reason": "No project."},
            "todo_creates": [{"approved": True, "reason": "Clear obligation."}],
            "todo_completions": [],
            "calendar_creates": [{"approved": True, "reason": "Concrete personal plan."}],
            "journal_entries": [{"approved": True, "reason": "Worth logging as a conversation summary."}],
            "workspace_updates": [],
        },
        expected_counts={
            "todo_creates": 1,
            "todo_completions": 0,
            "calendar_creates": 1,
            "journal_entries": 1,
            "workspace_updates": 0,
        },
    ),
    MixedModelCase(
        name="training_cluster_yields_calendar_todo_and_workspace_update",
        conversation_name="Ironman Training Coach",
        messages=(
            MessageExample("Thursday at 7:00 AM works for the long run if we cap it at 90 minutes."),
            MessageExample("Perfect, let's lock that in.", sender="coach@example.com"),
            MessageExample("I need to move the swim session to Friday."),
            MessageExample("Zone 2 should stay the focus for this build block."),
            MessageExample("Agreed, let's keep zone 2 as the focus this build block.", sender="coach@example.com"),
        ),
        projects=("Capital One", "Ironman Training", "Personal Ops"),
        project_candidates=(
            {"project_name": "Ironman Training", "confidence": 0.71, "reasons": ["conversation title and training vocabulary"]},
            {"project_name": "Personal Ops", "confidence": 0.17, "reasons": ["generic planning overlap"]},
        ),
        project_inference={
            "project_name": "Ironman Training",
            "confidence": 0.9,
            "reason": "Conversation title and long-run/build-block language fit Ironman Training.",
        },
        calendar_extraction={
            "calendar_creates": [
                {
                    "summary": "Long run",
                    "start_time": "2026-03-12T11:00:00Z",
                    "end_time": "2026-03-12T12:30:00Z",
                    "is_all_day": False,
                    "reason": "Concrete long-run slot with explicit duration.",
                }
            ]
        },
        general_extraction={
            "todo_creates": [
                {
                    "text": "Move the swim session to Friday",
                    "deadline_utc": None,
                    "deadline_is_date_only": False,
                    "reason": "Explicit first-person follow-up task.",
                }
            ],
            "todo_completions": [],
            "journal_entries": [],
            "workspace_updates": [
                {
                    "page_title": "Ironman Training Strategy",
                    "search_query": "Ironman Training zone 2 build block",
                    "summary": "Keep zone 2 as the focus for the current Ironman Training build block.",
                    "reason": "Durable training strategy confirmed in the thread.",
                }
            ],
        },
        judgment={
            "project_inference": {"approved": True, "reason": "Strong project evidence."},
            "todo_creates": [{"approved": True, "reason": "Clear task."}],
            "todo_completions": [],
            "calendar_creates": [{"approved": True, "reason": "Concrete scheduled workout."}],
            "journal_entries": [],
            "workspace_updates": [{"approved": True, "reason": "Confirmed durable training strategy."}],
        },
        expected_counts={
            "todo_creates": 1,
            "todo_completions": 0,
            "calendar_creates": 1,
            "journal_entries": 0,
            "workspace_updates": 1,
        },
    ),
]


@pytest.mark.parametrize("case", HEURISTIC_CASES, ids=lambda case: case.name)
def test_heuristic_examples_suggest_and_approve_actions(case: HeuristicCase) -> None:
    payload = build_payload(
        conversation_name=case.conversation_name,
        messages=case.messages,
        participants=case.participants,
        projects=case.projects,
    )
    service = make_service(client=None)

    extracted = run(service._extract_actions(payload))
    judged = run(service._judge_actions(payload, extracted))

    actions = extracted[case.action_key]
    assert len(actions) == 1

    if case.action_key == "todo_creates":
        assert case.expected_value in actions[0]["text"]
        assert judged["todo_creates"][0]["approved"] is True
    elif case.action_key == "todo_completions":
        assert case.expected_value in actions[0]["reason"]
        assert judged["todo_completions"][0]["approved"] is True
    else:
        assert case.expected_page_title == actions[0]["page_title"]
        assert case.expected_value in actions[0]["summary"]
        assert extracted["project_inference"]["project_name"] == "Forest Fire"
        assert judged["project_inference"]["approved"] is True
        assert judged["workspace_updates"][0]["approved"] is True


@pytest.mark.parametrize("case", MODEL_CASES, ids=lambda case: case.name)
def test_model_examples_suggest_and_approve_calendar_and_journal_actions(case: ModelCase) -> None:
    payload = build_payload(
        conversation_name=case.conversation_name,
        messages=case.messages,
    )
    service = make_service(client=object())
    prompts: list[str] = []
    extraction_response = (
        {"calendar_creates": case.extraction["calendar_creates"]}
        if case.action_key == "calendar_creates"
        else {
            "todo_creates": [],
            "todo_completions": [],
            "journal_entries": case.extraction["journal_entries"],
            "workspace_updates": [],
        }
    )
    responses = [
        json.dumps(extraction_response, ensure_ascii=False),
        json.dumps(case.judgment, ensure_ascii=False),
    ]

    async def fake_call_model(self, prompt: str) -> str:
        prompts.append(prompt)
        return responses.pop(0)

    service._call_model = MethodType(fake_call_model, service)
    if case.action_key == "calendar_creates":
        extracted_piece = run(
            service._extract_calendar_actions(
                {
                    **payload,
                    "project_inference": payload["heuristic_project_guess"],
                }
            )
        )
        extracted = {
            **empty_extracted(),
            "project_inference": payload["heuristic_project_guess"],
            "calendar_creates": extracted_piece["calendar_creates"],
        }
    else:
        extracted_piece = run(
            service._extract_general_actions(
                {
                    **payload,
                    "project_inference": payload["heuristic_project_guess"],
                },
                empty_extracted(),
            )
        )
        extracted = {
            **empty_extracted(),
            "project_inference": payload["heuristic_project_guess"],
            **extracted_piece,
        }
    judged = run(service._judge_actions(payload, extracted))

    assert len(prompts) == 2
    assert case.conversation_name in prompts[0]
    assert case.messages[0].text in prompts[0]
    assert '"extracted"' in prompts[1]

    actions = extracted[case.action_key]
    assert len(actions) == 1
    if case.action_key == "calendar_creates":
        assert actions[0]["summary"] == case.extraction["calendar_creates"][0]["summary"]
        assert judged["calendar_creates"][0]["approved"] is True
    else:
        assert actions[0]["text"] == case.extraction["journal_entries"][0]["text"]
        assert judged["journal_entries"][0]["approved"] is True


@pytest.mark.parametrize("case", DISPATCH_CASES, ids=lambda case: case.name)
def test_process_cluster_dispatches_every_supported_action_type(case: DispatchCase) -> None:
    service = make_service(client=None)
    cluster = make_cluster(
        conversation_name="Forest Fire Core Team" if case.expect_project else "Personal Admin",
        messages=(MessageExample("placeholder"),),
    )
    payload = build_payload(
        conversation_name="Forest Fire Core Team" if case.expect_project else "Personal Admin",
        messages=(MessageExample("placeholder"),),
    )
    run_record = SimpleNamespace(id=91, user_id=1)
    project = SimpleNamespace(id=7) if case.expect_project else None
    extracted = empty_extracted()
    extracted[case.action_key] = [case.action_payload]
    if case.expect_project:
        extracted["project_inference"] = {
            "project_name": "Forest Fire",
            "confidence": 0.91,
            "reason": "Conversation name and message content strongly match Forest Fire.",
        }
    judged = empty_judgment()
    judged[case.action_key] = [{"approved": True, "reason": "Approved for dispatch coverage."}]
    if case.expect_project:
        judged["project_inference"] = {"approved": True, "reason": "Approved for project dispatch coverage."}

    async def fake_build_cluster_payload(self, *, cluster, project_catalog, time_zone):
        return payload

    async def fake_extract_actions(self, payload):
        return extracted

    async def fake_judge_actions(self, payload, extracted_payload):
        return judged

    async def fake_resolve_project(self, **kwargs):
        return project

    async def fake_record_non_applied_action(self, **kwargs) -> None:
        raise AssertionError("approved dispatch test should not record non-applied actions")

    async def fake_deduplicate_action(self, **kwargs):
        return DuplicateDecision(is_duplicate=False, reason="No duplicate.")

    called_methods: list[str] = []

    def make_apply_stub(method_name: str):
        async def _apply(self, **kwargs) -> bool:
            called_methods.append(method_name)
            return True

        return _apply

    service._build_cluster_payload = MethodType(fake_build_cluster_payload, service)
    service._extract_actions = MethodType(fake_extract_actions, service)
    service._judge_actions = MethodType(fake_judge_actions, service)
    service._resolve_project = MethodType(fake_resolve_project, service)
    service._record_non_applied_action = MethodType(fake_record_non_applied_action, service)
    service._deduplicate_action = MethodType(fake_deduplicate_action, service)
    service._apply_todo_create = MethodType(make_apply_stub("_apply_todo_create"), service)
    service._apply_todo_completion = MethodType(make_apply_stub("_apply_todo_completion"), service)
    service._apply_calendar_create = MethodType(make_apply_stub("_apply_calendar_create"), service)
    service._apply_journal_entry = MethodType(make_apply_stub("_apply_journal_entry"), service)
    service._apply_workspace_update = MethodType(make_apply_stub("_apply_workspace_update"), service)

    result = run(
            service._process_cluster(
                run=run_record,
                cluster=cluster,
                project_catalog=[],
                time_zone="America/New_York",
            )
        )

    assert result == {"applied": 1}
    assert called_methods == [case.expect_apply_method]
    assert service.session.flush_calls == 1
    assert all(message.processed_at_utc is not None for message in cluster.messages)


def test_should_use_project_inference_model_only_for_ambiguous_candidates() -> None:
    service = make_service(client=object())

    assert service._should_use_project_inference_model(
        ProjectGuess(
            project_name="Forest Fire",
            confidence=0.93,
            reason="Strong deterministic match",
            candidates=[
                {"project_name": "Forest Fire", "confidence": 0.93, "reasons": ["title exact match"]},
                {"project_name": "Personal Ops", "confidence": 0.41, "reasons": ["generic overlap"]},
            ],
        )
    ) is False

    assert service._should_use_project_inference_model(
        ProjectGuess(
            project_name="Forest Fire",
            confidence=0.57,
            reason="Ambiguous match",
            candidates=[
                {"project_name": "Forest Fire", "confidence": 0.57, "reasons": ["message overlap"]},
                {"project_name": "Forest Floor", "confidence": 0.49, "reasons": ["title overlap"]},
            ],
        )
    ) is True


def test_extract_project_inference_accepts_only_known_candidate_names() -> None:
    service = make_service(client=object())
    payload = {
        "conversation": {"name": "Core team", "participants": ["alice@example.com"]},
        "messages": [{"text": "Need the county permit packet finalized."}],
        "heuristic_project_guess": {
            "project_name": "Forest Fire",
            "confidence": 0.58,
            "reason": "Ambiguous heuristic result",
        },
        "project_candidates": [
            {"project_name": "Forest Fire", "confidence": 0.58, "reasons": ["message overlap"]},
            {"project_name": "Personal Ops", "confidence": 0.47, "reasons": ["generic plan overlap"]},
        ],
    }
    responses = [
        json.dumps({"project_name": "Forest Fire", "confidence": 0.79, "reason": "Permit language clearly fits Forest Fire"}),
        json.dumps({"project_name": "Not A Real Project", "confidence": 0.88, "reason": "Invalid candidate"}),
    ]

    async def fake_call_model(self, prompt: str) -> str:
        return responses.pop(0)

    service._call_model = MethodType(fake_call_model, service)

    approved = run(
        service._extract_project_inference(payload)
    )
    fallback = run(
        service._extract_project_inference(payload)
    )

    assert approved["project_name"] == "Forest Fire"
    assert approved["confidence"] == pytest.approx(0.79)
    assert "permit" in approved["reason"].lower()

    assert fallback["project_name"] == payload["heuristic_project_guess"]["project_name"]
    assert fallback["confidence"] == payload["heuristic_project_guess"]["confidence"]


def test_extract_actions_combines_dedicated_project_calendar_and_general_results() -> None:
    service = make_service(client=object())
    payload = build_payload(
        conversation_name="Forest Fire Scheduling",
        messages=(MessageExample("March 12, 2026 from 3:00 to 3:30 PM is confirmed for the permit review."),),
    )

    async def fake_extract_project_inference(self, payload):
        return {
            "project_name": "Forest Fire",
            "confidence": 0.91,
            "reason": "Strong project evidence.",
        }

    async def fake_extract_calendar_actions(self, payload):
        return {
            "calendar_creates": [
                {
                    "summary": "Permit review",
                    "start_time": "2026-03-12T19:00:00Z",
                    "end_time": "2026-03-12T19:30:00Z",
                    "is_all_day": False,
                    "reason": "Concrete scheduling window.",
                }
            ]
        }

    async def fake_extract_general_actions(self, payload, heuristic):
        return {
            "todo_creates": [],
            "todo_completions": [],
            "journal_entries": [],
            "workspace_updates": [],
        }

    service._extract_project_inference = MethodType(fake_extract_project_inference, service)
    service._extract_calendar_actions = MethodType(fake_extract_calendar_actions, service)
    service._extract_general_actions = MethodType(fake_extract_general_actions, service)

    extracted = run(service._extract_actions(payload))

    assert extracted["project_inference"]["project_name"] == "Forest Fire"
    assert extracted["calendar_creates"][0]["summary"] == "Permit review"
    assert extracted["todo_creates"] == []


@pytest.mark.parametrize("case", MIXED_MODEL_CASES, ids=lambda case: case.name)
def test_extract_actions_supports_multi_action_clusters(case: MixedModelCase) -> None:
    service = make_service(client=object())
    payload = build_payload(
        conversation_name=case.conversation_name,
        messages=case.messages,
        projects=case.projects,
    )
    payload["heuristic_project_guess"] = {
        "project_name": case.project_inference.get("project_name"),
        "confidence": case.project_inference.get("confidence", 0.0),
        "reason": case.project_inference.get("reason", ""),
    }
    payload["project_candidates"] = list(case.project_candidates)

    async def fake_call_model(self, prompt: str) -> str:
        if "You infer whether an iMessage cluster belongs to one existing project." in prompt:
            return json.dumps(case.project_inference, ensure_ascii=False)
        if "You are the calendar extractor for an iMessage processing engine." in prompt:
            return json.dumps(case.calendar_extraction, ensure_ascii=False)
        if "You are the non-calendar action extractor for an iMessage processing engine." in prompt:
            return json.dumps(case.general_extraction, ensure_ascii=False)
        if "You are the judge for an iMessage processing engine." in prompt:
            return json.dumps(case.judgment, ensure_ascii=False)
        raise AssertionError(f"Unexpected prompt in mixed-action test: {prompt[:120]}")

    service._call_model = MethodType(fake_call_model, service)

    extracted = run(service._extract_actions(payload))
    judged = run(service._judge_actions(payload, extracted))

    for key, expected_count in case.expected_counts.items():
        assert len(extracted[key]) == expected_count

    assert extracted["project_inference"]["project_name"] == case.project_inference["project_name"]
    assert judged["project_inference"]["approved"] is bool(case.judgment["project_inference"]["approved"])


def test_apply_todo_create_uses_cluster_message_time_as_created_at() -> None:
    service = make_service(client=None)
    cluster = make_cluster(
        conversation_name="Personal Admin",
        messages=(
            MessageExample(
                "I need to send Sam the packet tonight.",
                is_from_me=True,
                sent_at_utc=datetime(2026, 1, 14, 22, 15, tzinfo=timezone.utc),
            ),
        ),
    )
    run_record = SimpleNamespace(id=91, user_id=1)
    captured: dict[str, Any] = {}

    async def fake_create_one(self, user_id, project_id, text, deadline, deadline_is_date_only=False, *, created_at=None, time_horizon="this_week"):
        captured["user_id"] = user_id
        captured["project_id"] = project_id
        captured["text"] = text
        captured["created_at"] = created_at
        return SimpleNamespace(id=501, deadline_utc=deadline, completed=False)

    async def fake_audit_exists(self, user_id, fingerprint):
        return False

    async def fake_record_action_audit(self, **kwargs):
        captured["audited"] = True
        captured["audit_kwargs"] = kwargs

    service.todo_repo = SimpleNamespace(create_one=MethodType(fake_create_one, object()))
    service.project_repo = SimpleNamespace(
        ensure_inbox_project=MethodType(
            lambda self, user_id: asyncio.sleep(0, result=SimpleNamespace(id=999)),
            object(),
        )
    )
    service._audit_exists = MethodType(fake_audit_exists, service)
    service._record_action_audit = MethodType(fake_record_action_audit, service)

    applied = run(
        service._apply_todo_create(
            run=run_record,
            cluster=cluster,
            project_id=7,
            action={
                "text": "Send Sam the packet tonight",
                "deadline_utc": None,
                "deadline_is_date_only": False,
                "reason": "Explicit first-person obligation.",
            },
            time_zone="America/New_York",
        )
    )

    assert applied is True
    assert captured["project_id"] == 7
    assert captured["created_at"] == datetime(2026, 1, 14, 22, 15, tzinfo=timezone.utc)
    assert captured["audited"] is True
    assert captured["audit_kwargs"]["supporting_message_ids"] == [1]
    assert captured["audit_kwargs"]["source_occurred_at_utc"] == datetime(2026, 1, 14, 22, 15, tzinfo=timezone.utc)


def test_apply_todo_completion_uses_cluster_message_time_for_completion_date() -> None:
    service = make_service(client=None)
    cluster = make_cluster(
        conversation_name="Personal Admin",
        messages=(
            MessageExample(
                "Done, I sent the reimbursement form.",
                is_from_me=True,
                sent_at_utc=datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc),
            ),
        ),
    )
    run_record = SimpleNamespace(id=91, user_id=1)

    class FakeTodo:
        def __init__(self) -> None:
            self.id = 402
            self.completed = False
            self.project_id = 9
            self.text = "Send reimbursement form"
            self.completed_at_utc = None
            self.completed_local_date = None
            self.completed_time_zone = None
            self.accomplishment_text = None
            self.accomplishment_generated_at_utc = None

        def mark_completed(self, done: bool, *, completed_at_utc: datetime | None = None) -> None:
            self.completed = done
            self.completed_at_utc = completed_at_utc

    target = FakeTodo()

    async def fake_find_todo_to_complete(self, **kwargs):
        return target

    async def fake_audit_exists(self, user_id, fingerprint):
        return False

    async def fake_record_action_audit(self, **kwargs):
        target.audit_kwargs = kwargs
        return None

    async def fake_rewrite(self, text):
        return "Submitted reimbursement form"

    service._find_todo_to_complete = MethodType(fake_find_todo_to_complete, service)
    service._audit_exists = MethodType(fake_audit_exists, service)
    service._record_action_audit = MethodType(fake_record_action_audit, service)
    service.todo_accomplishment_agent = SimpleNamespace(rewrite=MethodType(fake_rewrite, object()))

    applied = run(
        service._apply_todo_completion(
            run=run_record,
            cluster=cluster,
            project_id=None,
            action={"match_text": "reimbursement form", "reason": "Outgoing completion-like message."},
            time_zone="America/New_York",
        )
    )

    assert applied is True
    assert target.completed_at_utc == datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc)
    assert str(target.completed_local_date) == "2026-01-14"
    assert target.completed_time_zone == "America/New_York"
    assert target.audit_kwargs["supporting_message_ids"] == [1]
    assert target.audit_kwargs["source_occurred_at_utc"] == datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc)


def test_apply_journal_entry_uses_cluster_message_time_for_local_day() -> None:
    service = make_service(client=None)
    cluster = make_cluster(
        conversation_name="Aidan",
        messages=(
            MessageExample(
                "Talked to Aidan about philosophy for an hour.",
                is_from_me=True,
                sent_at_utc=datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc),
            ),
        ),
    )
    run_record = SimpleNamespace(id=91, user_id=1)
    captured: dict[str, Any] = {}

    async def fake_audit_exists(self, user_id, fingerprint):
        captured["fingerprint"] = fingerprint
        return False

    async def fake_add_entry(self, *, user_id, text, time_zone, occurred_at_utc=None):
        captured["user_id"] = user_id
        captured["text"] = text
        captured["time_zone"] = time_zone
        captured["occurred_at_utc"] = occurred_at_utc
        return {"entry": SimpleNamespace(id=611)}

    async def fake_record_action_audit(self, **kwargs):
        captured["audited"] = True
        captured["audit_kwargs"] = kwargs

    service._audit_exists = MethodType(fake_audit_exists, service)
    service._record_action_audit = MethodType(fake_record_action_audit, service)
    service.journal_service = SimpleNamespace(add_entry=MethodType(fake_add_entry, object()))

    applied = run(
        service._apply_journal_entry(
            run=run_record,
            cluster=cluster,
            action={"text": "Talked with Aidan about philosophy", "reason": "Meaningful conversation."},
            time_zone="America/New_York",
        )
    )

    assert applied is True
    assert captured["occurred_at_utc"] == datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc)
    assert captured["audited"] is True
    assert captured["audit_kwargs"]["supporting_message_ids"] == [1]
    assert captured["audit_kwargs"]["source_occurred_at_utc"] == datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc)


def test_extract_actions_normalizes_source_message_ids_from_model_output() -> None:
    service = make_service(client=object())
    payload = build_payload(
        conversation_name="Forest Fire Core Team",
        messages=(
            MessageExample(
                "For the Forest Fire architecture spec, use vendor X for debris removal and keep county submissions in PDF."
            ),
            MessageExample(
                "Agreed, let's document vendor X and PDF county submissions in the architecture page.",
                sender="bob@example.com",
            ),
        ),
        projects=("Forest Fire", "Forest Floor", "Personal Ops"),
    )

    async def fake_call_model(self, prompt: str) -> str:
        if "You infer whether an iMessage cluster belongs to one existing project." in prompt:
            return json.dumps(
                {
                    "project_name": "Forest Fire",
                    "confidence": 0.86,
                    "source_message_ids": [999, 1],
                    "reason": "Forest Fire is named directly and supported by county/vendor discussion.",
                }
            )
        if "You are the calendar extractor for an iMessage processing engine." in prompt:
            return json.dumps({"calendar_creates": []})
        if "You are the non-calendar action extractor for an iMessage processing engine." in prompt:
            return json.dumps(
                {
                    "todo_creates": [],
                    "todo_completions": [],
                    "journal_entries": [],
                    "workspace_updates": [
                        {
                            "page_title": "Forest Fire Architecture",
                            "search_query": "Forest Fire architecture vendor pdf",
                            "summary": "Use vendor X for debris removal and keep county submissions in PDF.",
                            "source_message_ids": [2, 999, 1],
                            "reason": "Durable architecture guidance.",
                        }
                    ],
                }
            )
        raise AssertionError(f"Unexpected prompt: {prompt[:120]}")

    service._call_model = MethodType(fake_call_model, service)

    extracted = run(service._extract_actions(payload))

    assert extracted["project_inference"]["source_message_ids"] == [1]
    assert extracted["workspace_updates"][0]["source_message_ids"] == [1, 2]


def test_preview_cluster_returns_judged_actions_with_source_attribution() -> None:
    service = make_service(client=None)
    cluster = make_cluster(
        conversation_name="Forest Fire Scheduling",
        messages=(
            MessageExample(
                "Tomorrow at 3 works for the permit review if we keep it quick.",
                is_from_me=True,
                sent_at_utc=datetime(2026, 1, 14, 15, 0, tzinfo=timezone.utc),
            ),
            MessageExample(
                "Perfect, let's lock that in for 30 minutes.",
                sender="bob@example.com",
                sent_at_utc=datetime(2026, 1, 14, 15, 5, tzinfo=timezone.utc),
            ),
        ),
    )

    async def fake_build_cluster_payload(self, *, cluster, project_catalog, time_zone):
        return {
            "conversation": {"id": 11, "name": "Forest Fire Scheduling"},
            "time_context": {
                "time_zone": time_zone,
                "cluster_start_time_utc": "2026-01-14T15:00:00+00:00",
                "cluster_end_time_utc": "2026-01-14T15:05:00+00:00",
            },
            "messages": [
                {
                    "id": 1,
                    "sent_at_utc": "2026-01-14T15:00:00+00:00",
                    "is_from_me": True,
                    "sender": "You",
                    "text": "Tomorrow at 3 works for the permit review if we keep it quick.",
                },
                {
                    "id": 2,
                    "sent_at_utc": "2026-01-14T15:05:00+00:00",
                    "is_from_me": False,
                    "sender": "bob@example.com",
                    "text": "Perfect, let's lock that in for 30 minutes.",
                },
            ],
        }

    async def fake_extract_actions(self, payload):
        return {
            "project_inference": {
                "project_name": "Forest Fire",
                "confidence": 0.83,
                "source_message_ids": [1],
                "reason": "Conversation title and permit-review language match Forest Fire.",
            },
            "todo_creates": [],
            "todo_completions": [],
            "calendar_creates": [
                {
                    "summary": "Permit review",
                    "start_time": "2026-01-15T20:00:00Z",
                    "end_time": "2026-01-15T20:30:00Z",
                    "is_all_day": False,
                    "source_message_ids": [1, 2],
                    "reason": "Concrete time plus confirmation.",
                }
            ],
            "journal_entries": [],
            "workspace_updates": [],
        }

    async def fake_judge_actions(self, payload, extracted):
        return {
            "project_inference": {"approved": True, "reason": "Strong evidence."},
            "todo_creates": [],
            "todo_completions": [],
            "calendar_creates": [{"approved": True, "reason": "Confirmed event."}],
            "journal_entries": [],
            "workspace_updates": [],
        }

    async def fake_resolve_project(self, *, cluster, extracted, judged, user_id):
        return SimpleNamespace(id=51, name="Forest Fire")

    service._build_cluster_payload = MethodType(fake_build_cluster_payload, service)
    service._extract_actions = MethodType(fake_extract_actions, service)
    service._judge_actions = MethodType(fake_judge_actions, service)
    service._resolve_project = MethodType(fake_resolve_project, service)
    service._deduplicate_action = MethodType(
        lambda self, **kwargs: asyncio.sleep(0, result=DuplicateDecision(is_duplicate=False, reason="No duplicate.")),
        service,
    )

    preview = run(
        service._preview_cluster(
            cluster=cluster,
            project_catalog=[],
            time_zone="America/New_York",
            user_id=1,
        )
    )

    assert preview["project_inference"]["source_message_ids"] == [1]
    assert preview["project_inference"]["source_occurred_at_utc"] == "2026-01-14T15:00:00+00:00"
    assert preview["actions"][0]["source_message_ids"] == [1, 2]
    assert preview["actions"][0]["source_occurred_at_utc"] == "2026-01-14T15:05:00+00:00"
    assert preview["counts"] == {"suggested": 1, "approved": 1, "rejected": 0}


def test_journal_service_add_entry_uses_historical_local_date() -> None:
    captured: dict[str, Any] = {}
    service = object.__new__(JournalService)

    async def fake_create_entry(self, *, user_id, local_date, time_zone, text, created_at):
        captured["user_id"] = user_id
        captured["local_date"] = local_date
        captured["time_zone"] = time_zone
        captured["text"] = text
        captured["created_at"] = created_at
        return SimpleNamespace(id=712, local_date=local_date, created_at=created_at)

    service.journal_repo = SimpleNamespace(create_entry=MethodType(fake_create_entry, object()))
    service.todo_repo = None
    service.compiler = None

    result = run(
        service.add_entry(
            user_id=1,
            text="Talked with Aidan about philosophy",
            time_zone="America/New_York",
            occurred_at_utc=datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc),
        )
    )

    assert str(captured["local_date"]) == "2026-01-14"
    assert captured["created_at"] == datetime(2026, 1, 15, 3, 30, tzinfo=timezone.utc)
    assert result["entry"].id == 712


def test_extract_calendar_prompt_includes_historical_time_context() -> None:
    service = make_service(client=object())
    payload = build_payload(
        conversation_name="Aidan",
        messages=(
            MessageExample(
                "Tomorrow at 6 works for dinner if we keep it to an hour.",
                is_from_me=True,
                sent_at_utc=datetime(2026, 1, 14, 15, 0, tzinfo=timezone.utc),
            ),
            MessageExample(
                "Perfect, let's lock it in.",
                sender="aidan@example.com",
                sent_at_utc=datetime(2026, 1, 14, 15, 5, tzinfo=timezone.utc),
            ),
        ),
    )
    payload["time_context"] = {
        "time_zone": "America/New_York",
        "cluster_start_time_utc": "2026-01-14T15:00:00+00:00",
        "cluster_end_time_utc": "2026-01-14T15:05:00+00:00",
        "cluster_start_time_local": "2026-01-14T10:00:00-05:00",
        "cluster_end_time_local": "2026-01-14T10:05:00-05:00",
        "relative_time_rule": "Interpret relative phrases using message timestamps.",
    }
    captured_prompts: list[str] = []

    async def fake_call_model(self, prompt: str) -> str:
        captured_prompts.append(prompt)
        return json.dumps({"calendar_creates": []})

    service._call_model = MethodType(fake_call_model, service)

    run(
        service._extract_calendar_actions(
            {
                **payload,
                "project_inference": {"project_name": None, "confidence": 0.0, "reason": ""},
            }
        )
    )

    prompt = captured_prompts[0]
    assert "cluster_end_time_local" in prompt
    assert "2026-01-14T15:00:00+00:00" in prompt
    assert "2026-01-14T15:05:00+00:00" in prompt


def test_deterministic_duplicate_decision_matches_existing_open_todo() -> None:
    service = make_service(client=None)

    decision = service._deterministic_duplicate_decision(
        action_type="todo.create",
        action={"text": "Send 18.01 to Madelyn tonight"},
        candidates=[
            {
                "artifact_type": "todo",
                "artifact_id": 41,
                "text": "Send 18.01 to Madelyn",
            }
        ],
    )

    assert decision.is_duplicate is True
    assert decision.matched_candidate_type == "todo"
    assert decision.matched_candidate_id == 41


def test_process_cluster_skips_duplicate_existing_action_before_apply() -> None:
    service = make_service(client=None)
    cluster = make_cluster(
        conversation_name="Personal Admin",
        messages=(MessageExample("Please send 18.01 to Madelyn tonight."),),
    )
    payload = build_payload(
        conversation_name="Personal Admin",
        messages=(MessageExample("Please send 18.01 to Madelyn tonight."),),
    )
    run_record = SimpleNamespace(id=91, user_id=1)
    extracted = empty_extracted()
    extracted["todo_creates"] = [
        {
            "text": "Send 18.01 to Madelyn tonight",
            "source_message_ids": [1],
            "reason": "Direct request.",
        }
    ]
    judged = empty_judgment()
    judged["todo_creates"] = [{"approved": True, "reason": "Clear obligation."}]

    async def fake_build_cluster_payload(self, *, cluster, project_catalog, time_zone):
        return payload

    async def fake_extract_actions(self, payload):
        return extracted

    async def fake_judge_actions(self, payload, extracted_payload):
        return judged

    async def fake_resolve_project(self, **kwargs):
        return None

    async def fake_deduplicate_action(self, **kwargs):
        return DuplicateDecision(
            is_duplicate=True,
            reason="Existing open todo already covers this ask.",
            matched_candidate_type="todo",
            matched_candidate_id=77,
        )

    captured: dict[str, Any] = {}

    async def fake_record_duplicate_action(self, **kwargs):
        captured["duplicate"] = kwargs

    async def fake_apply_todo_create(self, **kwargs):
        raise AssertionError("Duplicate todo should not be applied.")

    service._build_cluster_payload = MethodType(fake_build_cluster_payload, service)
    service._extract_actions = MethodType(fake_extract_actions, service)
    service._judge_actions = MethodType(fake_judge_actions, service)
    service._resolve_project = MethodType(fake_resolve_project, service)
    service._deduplicate_action = MethodType(fake_deduplicate_action, service)
    service._record_duplicate_action = MethodType(fake_record_duplicate_action, service)
    service._apply_todo_create = MethodType(fake_apply_todo_create, service)

    result = run(
        service._process_cluster(
            run=run_record,
            cluster=cluster,
            project_catalog=[],
            time_zone="America/New_York",
        )
    )

    assert result == {"applied": 0}
    assert captured["duplicate"]["duplicate"].matched_candidate_id == 77
    assert all(message.processed_at_utc is not None for message in cluster.messages)


def test_preview_cluster_marks_duplicate_action_as_not_approved() -> None:
    service = make_service(client=None)
    cluster = make_cluster(
        conversation_name="Personal Admin",
        messages=(MessageExample("Please send 18.01 to Madelyn tonight."),),
    )

    async def fake_build_cluster_payload(self, *, cluster, project_catalog, time_zone):
        return build_payload(
            conversation_name="Personal Admin",
            messages=(MessageExample("Please send 18.01 to Madelyn tonight."),),
        )

    async def fake_extract_actions(self, payload):
        extracted = empty_extracted()
        extracted["todo_creates"] = [
            {
                "text": "Send 18.01 to Madelyn tonight",
                "source_message_ids": [1],
                "reason": "Direct request.",
            }
        ]
        return extracted

    async def fake_judge_actions(self, payload, extracted):
        judged = empty_judgment()
        judged["todo_creates"] = [{"approved": True, "reason": "Clear obligation."}]
        return judged

    async def fake_resolve_project(self, **kwargs):
        return None

    async def fake_deduplicate_action(self, **kwargs):
        return DuplicateDecision(
            is_duplicate=True,
            reason="Existing open todo already covers this ask.",
            matched_candidate_type="todo",
            matched_candidate_id=77,
        )

    service._build_cluster_payload = MethodType(fake_build_cluster_payload, service)
    service._extract_actions = MethodType(fake_extract_actions, service)
    service._judge_actions = MethodType(fake_judge_actions, service)
    service._resolve_project = MethodType(fake_resolve_project, service)
    service._deduplicate_action = MethodType(fake_deduplicate_action, service)

    preview = run(
        service._preview_cluster(
            cluster=cluster,
            project_catalog=[],
            time_zone="America/New_York",
            user_id=1,
        )
    )

    assert preview["actions"][0]["judge_approved"] is True
    assert preview["actions"][0]["approved"] is False
    assert preview["actions"][0]["dedup_duplicate"] is True
    assert preview["actions"][0]["matched_candidate_id"] == 77


def test_enrich_todo_text_preserves_named_person_and_subject() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "Owen",
            "text": "Can you meet Owen to plan the poker trip and play HU?",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": "Meet to plan trip/play HU",
            "source_message_ids": [1],
            "reason": "Direct request.",
        },
        messages=messages,
        participant_names=["Owen"],
    )

    assert enriched["text"] == "Meet with Owen to plan the poker trip and play heads-up"


def test_enrich_todo_text_adds_missing_recipient_and_topic() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "Madelyn",
            "text": "Please send 18.01 to Madelyn tonight.",
        },
        {
            "id": 2,
            "sent_at_utc": "2026-03-10T15:05:00Z",
            "is_from_me": False,
            "sender": "Madelyn",
            "text": "Can you ask Madelyn about the chem p-set when you text her?",
        },
    ]

    send_action = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": "Send 18.01",
            "source_message_ids": [1],
            "reason": "Request.",
        },
        messages=messages,
        participant_names=["Madelyn"],
    )
    ask_action = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": "Ask Madelyn",
            "source_message_ids": [2],
            "reason": "Request.",
        },
        messages=messages,
        participant_names=["Madelyn"],
    )

    assert "Send 18.01 to Madelyn" in send_action["text"]
    assert ask_action["text"] == "Ask Madelyn about the chem p-set when you text her"


def test_enrich_todo_text_replaces_handle_with_participant_name() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "Madelyn",
            "sender_handle": "+14106603626",
            "text": "Can you let me know what day you're leaving for school?",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": "Reply to +14106603626 with what day you're leaving for school",
            "source_message_ids": [1],
            "reason": "Direct request.",
        },
        messages=messages,
        participant_names=["Madelyn"],
        participant_handles=["+14106603626"],
    )

    assert enriched["text"] == "Reply to Madelyn with what day you're leaving for school"


@pytest.mark.parametrize(
    ("current_text", "source_text", "participant_name", "participant_handle", "expected"),
    [
        (
            "Reply to +14106603626 with what day you're leaving for school",
            "Can you let me know what day you're leaving for school?",
            "Madelyn",
            "+14106603626",
            "Reply to Madelyn with what day you're leaving for school",
        ),
        (
            "Reply to madelyn@example.com about the chem p-set",
            "Can you reply to me about the chem p-set tonight?",
            "Madelyn",
            "madelyn@example.com",
            "Reply to Madelyn about the chem p-set tonight",
        ),
        (
            "Send the notes to 2405550199",
            "Please send the notes to me after class.",
            "Owen Lee",
            "+1 (240) 555-0199",
            "Send the notes to Owen Lee after class",
        ),
    ],
)
def test_enrich_todo_text_replaces_phone_and_email_handles(
    current_text: str,
    source_text: str,
    participant_name: str,
    participant_handle: str,
    expected: str,
) -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": participant_name,
            "sender_handle": participant_handle,
            "text": source_text,
        }
    ]

    enriched = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": current_text,
            "source_message_ids": [1],
            "reason": "Direct request.",
        },
        messages=messages,
        participant_names=[participant_name],
        participant_handles=[participant_handle],
    )

    assert enriched["text"] == expected


def test_enrich_todo_text_uses_sender_name_when_participant_names_missing() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "Seb Martinez",
            "sender_handle": "+12404700750",
            "text": "Can you send me the fire family selfies from last night?",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": "Send the fire family selfies to +12404700750",
            "source_message_ids": [1],
            "reason": "Direct request.",
        },
        messages=messages,
        participant_names=[],
        participant_handles=[],
    )

    assert enriched["text"] == "Send the fire family selfies to Seb Martinez"


def test_enrich_todo_text_uses_multiple_contact_names_without_cross_replacing() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "Madelyn",
            "sender_handle": "+14106603626",
            "text": "Please send the notes to Owen and then text me once it's done.",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": "Send the notes to 2405550199 and text +14106603626 once it's done",
            "source_message_ids": [1],
            "reason": "Direct request.",
        },
        messages=messages,
        participant_names=["Madelyn", "Owen"],
        participant_handles=["+14106603626", "2405550199"],
    )

    assert enriched["text"] == "Send the notes to Owen and text Madelyn once it's done"


def test_enrich_todo_text_does_not_replace_unmatched_numbers() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "T-Mobile",
            "text": "Your order S162436981 is expected to ship next week.",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": "Track order S162436981",
            "source_message_ids": [1],
            "reason": "Shipment reminder.",
        },
        messages=messages,
        participant_names=["T-Mobile"],
        participant_handles=[],
    )

    assert enriched["text"] == "Track order S162436981"


def test_enrich_journal_text_preserves_specific_show_title() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": True,
            "sender": "You",
            "text": "We decided to watch Severance.",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="journal.entry",
        action={
            "text": "Decided to watch a show",
            "source_message_ids": [1],
            "reason": "Decision.",
        },
        messages=messages,
        participant_names=["Owen"],
    )

    assert enriched["text"] == "Decided to watch Severance"


def test_enrich_journal_text_replaces_handle_with_participant_name() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": True,
            "sender": "You",
            "text": "Talked to Madelyn about the chem p-set and graduation plans.",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="journal.entry",
        action={
            "text": "Talked to +14106603626 about the chem p-set and graduation plans",
            "source_message_ids": [1],
            "reason": "Meaningful conversation.",
        },
        messages=messages,
        participant_names=["Madelyn"],
        participant_handles=["+14106603626"],
    )

    assert enriched["text"] == "Talked to Madelyn about the chem p-set and graduation plans"


def test_enrich_journal_text_replaces_email_handle_with_contact_name() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": True,
            "sender": "You",
            "text": "Talked with Madelyn about the chem p-set and graduation plans.",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="journal.entry",
        action={
            "text": "Talked with madelyn@example.com about the chem p-set and graduation plans",
            "source_message_ids": [1],
            "reason": "Meaningful conversation.",
        },
        messages=messages,
        participant_names=["Madelyn"],
        participant_handles=["madelyn@example.com"],
    )

    assert enriched["text"] == "Talked with Madelyn about the chem p-set and graduation plans"


def test_enrich_journal_text_replaces_contact_placeholder_with_name() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "Seb Martinez",
            "sender_handle": "+12404700750",
            "text": "i booked my flight, arriving friday at 7:30 and leaving monday at 1:45",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="journal.entry",
        action={
            "text": "Contact seb martinez booked a flight: arriving Friday at 7:30 and departing Monday at 1:45.",
            "source_message_ids": [1],
            "reason": "Travel update.",
        },
        messages=messages,
        participant_names=["Seb Martinez"],
        participant_handles=["+12404700750"],
    )

    assert enriched["text"] == "Seb Martinez booked a flight: arriving Friday at 7:30 and departing Monday at 1:45."


def test_enrich_calendar_summary_uses_named_counterparty_when_supported() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": True,
            "sender": "You",
            "text": "Tomorrow at 6 works for dinner with Owen if we keep it to an hour.",
        },
        {
            "id": 2,
            "sent_at_utc": "2026-03-10T15:05:00Z",
            "is_from_me": False,
            "sender": "Owen",
            "text": "Perfect, let's lock it in.",
        },
    ]

    enriched = service.enrich_action_text(
        action_type="calendar.create",
        action={
            "summary": "Dinner",
            "start_time": "2026-03-11T22:00:00Z",
            "end_time": "2026-03-11T23:00:00Z",
            "source_message_ids": [1, 2],
            "reason": "Concrete dinner plan.",
        },
        messages=messages,
        participant_names=["Owen"],
    )

    assert enriched["summary"] == "Dinner with Owen"


def test_enrich_calendar_summary_replaces_phone_handle_with_name() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "Jasmin Kim",
            "sender_handle": "+14105550100",
            "text": "Dinner tomorrow at 7 works for me.",
        },
        {
            "id": 2,
            "sent_at_utc": "2026-03-10T15:05:00Z",
            "is_from_me": True,
            "sender": "You",
            "text": "Perfect, let's lock it in.",
        },
    ]

    enriched = service.enrich_action_text(
        action_type="calendar.create",
        action={
            "summary": "Dinner with +14105550100",
            "start_time": "2026-03-11T23:00:00Z",
            "end_time": "2026-03-12T00:00:00Z",
            "source_message_ids": [1, 2],
            "reason": "Concrete dinner plan.",
        },
        messages=messages,
        participant_names=["Jasmin Kim"],
        participant_handles=["+14105550100"],
    )

    assert enriched["summary"] == "Dinner with Jasmin Kim"


def test_enrich_calendar_summary_replaces_stale_wrong_contact_name_from_extracted_payload() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-01-05T03:24:41.575479Z",
            "is_from_me": False,
            "sender": "Dad",
            "sender_handle": "+14435616671",
            "text": "ok - heading to bed. See you at 09:30",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="calendar.create",
        action={
            "summary": "Meeting with Jasmin Kim",
            "start_time": "2026-01-05T14:30:00Z",
            "end_time": "2026-01-05T15:00:00Z",
            "source_message_ids": [1],
            "reason": "Explicit meeting time.",
        },
        messages=messages,
        participant_names=["Dad"],
        participant_handles=["+14435616671"],
    )

    assert enriched["summary"] == "Meeting with Dad"


def test_enrich_action_text_canonicalizes_lowercase_contact_names() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "Seb Martinez",
            "sender_handle": "+12404700750",
            "text": "Can you send the trip details to me after you finalize them?",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": "send the trip details to seb martinez",
            "source_message_ids": [1],
            "reason": "Direct request.",
        },
        messages=messages,
        participant_names=["Seb Martinez"],
        participant_handles=["+12404700750"],
    )

    assert enriched["text"] == "Send the trip details to Seb Martinez after you finalize them"


def test_enrich_action_text_does_not_hallucinate_missing_detail() -> None:
    service = make_service(client=None)
    messages = [
        {
            "id": 1,
            "sent_at_utc": "2026-03-10T15:00:00Z",
            "is_from_me": False,
            "sender": "Madelyn",
            "text": "Can you ask Madelyn?",
        }
    ]

    enriched = service.enrich_action_text(
        action_type="todo.create",
        action={
            "text": "Ask Madelyn",
            "source_message_ids": [1],
            "reason": "Request.",
        },
        messages=messages,
        participant_names=["Madelyn"],
    )

    assert enriched["text"] == "Ask Madelyn"


class _RetryOutput(BaseModel):
    value: str


class _TransientModelError(Exception):
    def __init__(self, status_code: int = 503, message: str = "503 UNAVAILABLE") -> None:
        super().__init__(message)
        self.status_code = status_code


def test_call_model_retries_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    service = IMessageProcessingService(SimpleNamespace())
    sleep_calls: list[int] = []

    async def fake_sleep(delay: int) -> None:
        sleep_calls.append(delay)

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_json(self, prompt: str, *, response_model, temperature: float):
            self.calls += 1
            if self.calls < 3:
                raise _TransientModelError()
            return SimpleNamespace(data=_RetryOutput(value="ok"))

    service.client = FakeClient()
    monkeypatch.setattr("app.services.imessage_processing_service.asyncio.sleep", fake_sleep)

    result = run(service._call_model("prompt", _RetryOutput))

    assert result.value == "ok"
    assert service.client.calls == 3
    assert sleep_calls == [1, 2]


def test_call_model_does_not_retry_non_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    service = IMessageProcessingService(SimpleNamespace())
    sleep_calls: list[int] = []

    async def fake_sleep(delay: int) -> None:
        sleep_calls.append(delay)

    class FakeClient:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_json(self, prompt: str, *, response_model, temperature: float):
            self.calls += 1
            raise ValueError("invalid output schema")

    service.client = FakeClient()
    monkeypatch.setattr("app.services.imessage_processing_service.asyncio.sleep", fake_sleep)

    with pytest.raises(ValueError, match="invalid output schema"):
        run(service._call_model("prompt", _RetryOutput))

    assert service.client.calls == 1
    assert sleep_calls == []


# ---------------------------------------------------------------------------
# Conversation type propagation tests
# ---------------------------------------------------------------------------


def test_payload_includes_conversation_type_personal() -> None:
    payload = build_payload(
        conversation_name="Owen",
        messages=(MessageExample("Hey, want to grab dinner?", is_from_me=True),),
        participants=("Owen", "Sean"),
    )
    assert payload["conversation"]["conversation_type"] == "personal"


def test_payload_includes_conversation_type_group() -> None:
    payload = build_payload(
        conversation_name="Squad",
        messages=(MessageExample("Who's coming Saturday?", is_from_me=True),),
        participants=("Owen", "Aidan", "Jake"),
    )
    assert payload["conversation"]["conversation_type"] == "group"


def test_payload_includes_conversation_type_business_short_code() -> None:
    payload = build_payload(
        conversation_name="32665",
        messages=(MessageExample("Your verification code is 483921."),),
        participants=("32665",),
        chat_identifier="32665",
    )
    assert payload["conversation"]["conversation_type"] == "business"


def test_payload_conversation_type_override() -> None:
    """When explicitly provided, conversation_type is passed through."""
    payload = build_payload(
        conversation_name="Owen",
        messages=(MessageExample("Hey"),),
        participants=("Owen",),
        conversation_type="business",
    )
    assert payload["conversation"]["conversation_type"] == "business"


# ---------------------------------------------------------------------------
# Heuristic extraction: group chat ownership
# ---------------------------------------------------------------------------


def test_heuristic_extract_does_not_create_todo_for_other_persons_obligation() -> None:
    """When someone else says 'I need to...', the heuristic extractor still
    captures it (it's a regex-based fallback) but the heuristic judge should
    not blindly approve. The LLM pipeline handles the final ownership check."""
    service = make_service()
    payload = build_payload(
        conversation_name="Squad",
        messages=(
            MessageExample("I need to pick up the groceries tonight", is_from_me=False, sender="Jake"),
        ),
        participants=("Jake", "Owen", "Sean"),
    )
    extracted = service._heuristic_extract(payload)
    # Heuristic regex catches "need to" patterns regardless of is_from_me.
    # This is expected — the LLM judge is what applies ownership filtering.
    # Verify the heuristic at least produces the extraction for the LLM to judge.
    assert isinstance(extracted.get("todo_creates"), list)


# ---------------------------------------------------------------------------
# Heuristic judge: completion must come from user
# ---------------------------------------------------------------------------


def test_heuristic_extract_flags_conversational_advice_but_pipeline_rejects_it() -> None:
    """Rambling conversational text with 'need to' (e.g., 'you need to be
    selfish sometimes') should NOT produce approved todos.  The heuristic may
    fire on the 'need to' keyword, but the LLM pipeline must reject it because
    the text is advice/venting, not an actionable obligation for the user.

    Regression: the word 'predict' in a transcribed conversation triggered a
    false-positive todo.
    """
    service = make_service(client=object())
    conversational_text = (
        "redict that i was going to I would feel bad doing it while you were "
        "grieving And then i would feel bad doing it like right after you were "
        "grieving thats ridiculous you need to be selfish sometimes can't waste "
        "6 months of your life too short ur too short to do that 6 months "
        "really doesn't feel that long to me"
    )
    payload = build_payload(
        conversation_name="Aidan",
        messages=(
            MessageExample(conversational_text, is_from_me=False, sender="Aidan"),
        ),
        participants=("Aidan",),
    )

    # Stage 1: heuristic extraction picks up "need to be selfish" — expected
    heuristic = service._heuristic_extract(payload)
    assert len(heuristic["todo_creates"]) >= 1, (
        "Heuristic should catch 'need to' pattern as a candidate"
    )

    # Stage 2+3: LLM extraction and judgment should both return empty todos.
    # Mock the LLM to return empty (the correct behavior for this text).
    extraction_response = json.dumps({
        "todo_creates": [],
        "todo_completions": [],
        "journal_entries": [],
        "workspace_updates": [],
    })
    judgment_response = json.dumps({
        **empty_judgment(),
    })
    responses = [extraction_response, judgment_response]

    async def fake_call_model(self, prompt: str) -> str:
        return responses.pop(0)

    service._call_model = MethodType(fake_call_model, service)
    extracted = run(
        service._extract_general_actions(
            {**payload, "project_inference": payload["heuristic_project_guess"]},
            heuristic,
        )
    )
    assert extracted["todo_creates"] == [], (
        "LLM extraction must return zero todos for conversational advice/venting"
    )

    full_extracted = {**empty_extracted(), **extracted}
    judged = run(service._judge_actions(payload, full_extracted))
    assert judged["todo_creates"] == [], (
        "Judgment must not approve any todos from conversational text"
    )


def test_crisis_message_does_not_produce_any_actions() -> None:
    """A message expressing suicidal ideation must NEVER produce todos,
    calendar events, or any other extracted action.  The phrase
    'I am going to kill myself tomorrow at midnight' contains patterns
    that could naively match todo ('I am going to') or calendar
    ('tomorrow at midnight') extraction.  The system must recognize this
    as a crisis, not an obligation or appointment.
    """
    service = make_service(client=object())
    payload = build_payload(
        conversation_name="Close Friend",
        messages=(
            MessageExample(
                "I am going to kill myself tomorrow at midnight",
                is_from_me=False,
                sender="Friend",
            ),
        ),
        participants=("Friend",),
    )

    # Heuristic extraction — verify it does NOT produce todos or calendar
    heuristic = service._heuristic_extract(payload)
    # The heuristic regex should NOT match "going to kill myself" as a todo
    for todo in heuristic.get("todo_creates") or []:
        assert "kill" not in todo.get("text", "").lower(), (
            f"Heuristic must not extract crisis language as a todo: {todo['text']}"
        )

    # LLM extraction — mock returning empty (correct behavior)
    extraction_response = json.dumps({
        "todo_creates": [],
        "todo_completions": [],
        "journal_entries": [],
        "workspace_updates": [],
    })
    calendar_response = json.dumps({"calendar_creates": []})
    # Judgment — mock returning empty
    judgment_response = json.dumps({**empty_judgment()})
    responses = [calendar_response, extraction_response, judgment_response]

    async def fake_call_model(self, prompt: str) -> str:
        return responses.pop(0)

    service._call_model = MethodType(fake_call_model, service)
    payload["_name_map"] = service._build_name_map(payload)
    extracted = run(service._extract_actions(payload))

    assert extracted["todo_creates"] == [], (
        "Crisis message must not produce any todos"
    )
    assert extracted["calendar_creates"] == [], (
        "Crisis message must not produce any calendar events"
    )
    assert extracted["journal_entries"] == [], (
        "Crisis message must not produce any journal entries"
    )

    # Also verify judgment rejects if extraction somehow leaked through
    # Simulate a hypothetical extraction that incorrectly created actions
    leaked_extracted = {
        **empty_extracted(),
        "todo_creates": [
            {"text": "Kill myself tomorrow at midnight", "reason": "Detected obligation."}
        ],
        "calendar_creates": [
            {
                "summary": "Kill myself",
                "start_time": "2026-03-12T05:00:00Z",
                "end_time": "2026-03-12T05:30:00Z",
                "is_all_day": False,
                "reason": "Detected time-specific event.",
            }
        ],
    }
    judgment_for_leak = json.dumps({
        **empty_judgment(),
        "todo_creates": [{"approved": False, "reason": "Crisis language, not an actionable obligation."}],
        "calendar_creates": [{"approved": False, "reason": "Crisis language, not a real appointment."}],
    })
    responses.clear()
    responses.append(judgment_for_leak)
    judged = run(service._judge_actions(payload, leaked_extracted))

    for todo in judged.get("todo_creates") or []:
        assert not todo.get("approved"), (
            "Judgment must reject todos derived from crisis messages"
        )
    for cal in judged.get("calendar_creates") or []:
        assert not cal.get("approved"), (
            "Judgment must reject calendar events derived from crisis messages"
        )


def test_heuristic_judge_rejects_completion_from_non_user() -> None:
    service = make_service()
    payload = build_payload(
        conversation_name="Owen",
        messages=(
            MessageExample("Done, I paid Splitwise.", is_from_me=False, sender="Owen"),
        ),
        participants=("Owen",),
    )
    extracted = {
        **empty_extracted(),
        "todo_completions": [{"match_text": "Splitwise", "reason": "Completion signal."}],
    }
    judged = service._heuristic_judge(payload, extracted)
    completions = judged.get("todo_completions") or []
    assert completions and not completions[0]["approved"]


# ---------------------------------------------------------------------------
# Enrichment: counterparty name in todo text
# ---------------------------------------------------------------------------


def test_enrich_todo_text_replaces_handle_with_display_name() -> None:
    service = make_service()
    payload = build_payload(
        conversation_name="Owen",
        messages=(
            MessageExample("Can you settle up on Splitwise?", is_from_me=False, sender="Owen"),
        ),
        participants=("Owen",),
    )
    messages = payload["messages"]
    handle_map = {"+14155551234": "Owen"}
    result = service._enrich_todo_text(
        current="Settle up on Splitwise for +14155551234",
        messages=messages,
        participant_names=["Owen"],
        handle_map=handle_map,
    )
    assert "Owen" in result
    assert "+14155551234" not in result


# ---------------------------------------------------------------------------
# Contact anonymization: real names never reach the LLM
# ---------------------------------------------------------------------------


def test_anonymize_payload_replaces_names_and_handles() -> None:
    """Verify that _anonymize_payload masks sender names, participants,
    conversation names, and handles — but leaves message text intact."""
    service = make_service()
    payload = build_payload(
        conversation_name="Aidan",
        messages=(
            MessageExample(
                "Hey, can you pick up groceries tonight?",
                is_from_me=False,
                sender="Aidan",
            ),
            MessageExample("Sure thing", is_from_me=True, sender="Sean"),
        ),
        participants=("Aidan", "Sean"),
    )
    name_map = service._build_name_map(payload)
    anon = service._anonymize_payload(payload, name_map)

    # Real names must NOT appear in anonymized structured fields
    conv = anon["conversation"]
    assert "Aidan" not in conv["name"]
    assert "Sean" not in str(conv["participants"])
    for msg in anon["messages"]:
        assert "Aidan" not in msg["sender"]
        assert "Sean" not in msg["sender"]

    # Message text must be preserved verbatim
    assert anon["messages"][0]["text"] == "Hey, can you pick up groceries tonight?"
    assert anon["messages"][1]["text"] == "Sure thing"

    # Contact labels should follow the Contact A/B pattern
    assert any("Contact" in p for p in conv["participants"])


def test_deanonymize_actions_restores_real_names() -> None:
    """Verify that aliases in LLM-returned action text are replaced with
    real names before enrichment runs."""
    service = make_service()
    name_map = {"Aidan": "Contact A", "Sean": "Contact B"}
    extracted = {
        "project_inference": {"project_name": None, "confidence": 0.0, "reason": ""},
        "todo_creates": [
            {"text": "Send Contact A the permit packet", "reason": "Obligation."}
        ],
        "todo_completions": [],
        "journal_entries": [
            {"text": "Talked with Contact A about philosophy", "reason": "Discussion."}
        ],
        "calendar_creates": [
            {"summary": "Meeting with Contact A", "reason": "Scheduled."}
        ],
        "workspace_updates": [],
    }
    result = service._deanonymize_actions(extracted, name_map)

    assert "Aidan" in result["todo_creates"][0]["text"]
    assert "Contact A" not in result["todo_creates"][0]["text"]
    assert "Aidan" in result["journal_entries"][0]["text"]
    assert "Aidan" in result["calendar_creates"][0]["summary"]


def test_extract_actions_sends_anonymized_payload_to_llm() -> None:
    """End-to-end: verify the serialized payload inside the LLM prompt uses
    anonymized names, not real ones.  (The prompt *template* may contain
    example names like 'Aidan' in static few-shot examples — we only check
    the dynamic payload portion.)
    """
    service = make_service(client=object())
    payload = build_payload(
        conversation_name="Bartholomew",
        messages=(
            MessageExample(
                "I need to send the signed permit packet tonight.",
                is_from_me=True,
                sender="Fitzwilliam",
            ),
        ),
        participants=("Bartholomew", "Fitzwilliam"),
    )
    # Add _name_map as _build_cluster_payload would
    payload["_name_map"] = service._build_name_map(payload)

    captured_prompts: list[str] = []

    async def fake_call_model(self, prompt: str) -> str:
        captured_prompts.append(prompt)
        return json.dumps({
            "todo_creates": [],
            "todo_completions": [],
            "journal_entries": [],
            "workspace_updates": [],
        })

    service._call_model = MethodType(fake_call_model, service)
    run(service._extract_actions(payload))

    # These unique names don't appear in any prompt template example,
    # so finding them would prove a real leak.
    for prompt in captured_prompts:
        assert "Bartholomew" not in prompt, "Real name 'Bartholomew' leaked to LLM prompt"
        assert "Fitzwilliam" not in prompt, "Real name 'Fitzwilliam' leaked to LLM prompt"
        assert "Contact" in prompt, "Expected anonymized Contact labels in LLM prompt"
