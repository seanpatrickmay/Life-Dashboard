from __future__ import annotations

import json
import os
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from types import MethodType, SimpleNamespace
from typing import Any, Callable

import pytest
from dotenv import load_dotenv

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
load_dotenv(backend_root.parent / ".env")

from app.clients.genai_client import build_genai_client
from app.core.config import settings
from app.services.imessage_processing_service import IMessageProcessingService
from app.services.imessage_utils import infer_project_match
from app.utils.timezone import resolve_time_zone


pytestmark = pytest.mark.live_llm


def _require_live_llm() -> None:
    if os.getenv("RUN_LIVE_LLM_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_LLM_TESTS=1 to run live LLM evaluations.")


@dataclass(frozen=True)
class MessageExample:
    text: str
    is_from_me: bool = False
    sender: str | None = None
    sent_at_utc: datetime | None = None


@dataclass(frozen=True)
class ExtractionCase:
    name: str
    conversation_name: str
    messages: tuple[MessageExample, ...]
    action_key: str
    open_todos: tuple[dict[str, Any], ...] = ()
    projects: tuple[str, ...] = ("Forest Fire", "Personal Ops", "Splitwise")
    participants: tuple[str, ...] = ("alice@example.com", "bob@example.com")
    validate: Callable[[dict[str, Any], str], None] | None = None


@dataclass(frozen=True)
class ProjectInferenceCase:
    name: str
    conversation_name: str
    messages: tuple[MessageExample, ...]
    projects: tuple[str, ...]
    heuristic_project_name: str | None
    heuristic_confidence: float
    project_candidates: tuple[dict[str, Any], ...]
    expected_project_name: str | None
    min_confidence: float = 0.0


@dataclass(frozen=True)
class MixedExtractionCase:
    name: str
    conversation_name: str
    messages: tuple[MessageExample, ...]
    expected_non_empty_keys: tuple[str, ...]
    open_todos: tuple[dict[str, Any], ...] = ()
    projects: tuple[str, ...] = ("Forest Fire", "Personal Ops", "Splitwise")
    participants: tuple[str, ...] = ("alice@example.com", "bob@example.com")
    validate: Callable[[dict[str, Any], str], None] | None = None


def build_payload(
    *,
    conversation_name: str,
    messages: tuple[MessageExample, ...],
    open_todos: tuple[dict[str, Any], ...] = (),
    projects: tuple[str, ...] = ("Forest Fire", "Personal Ops", "Splitwise"),
    participants: tuple[str, ...] = ("alice@example.com", "bob@example.com"),
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
    return {
        "conversation": {
            "id": 11,
            "name": conversation_name,
            "chat_identifier": conversation_name.lower().replace(" ", "-"),
            "service_name": "iMessage",
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
        "open_todos": list(open_todos),
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


@pytest.fixture(scope="session")
def live_service() -> IMessageProcessingService:
    _require_live_llm()
    service = object.__new__(IMessageProcessingService)
    service.client = build_genai_client()
    service.model_name = settings.vertex_model_name or "gemini-2.5-flash"
    return service


def clone_live_service(base_service: IMessageProcessingService) -> IMessageProcessingService:
    service = object.__new__(IMessageProcessingService)
    service.client = base_service.client
    service.model_name = base_service.model_name
    return service


async def run_pipeline_async(
    service: IMessageProcessingService,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    prompts: list[str] = []
    responses: list[str] = []
    original_call_model = service._call_model

    async def tracked_call_model(self, prompt: str) -> str:
        prompts.append(prompt)
        text = await original_call_model(prompt)
        responses.append(text)
        return text

    service._call_model = MethodType(tracked_call_model, service)
    try:
        extracted = await service._extract_actions(payload)
        judged = await service._judge_actions(payload, extracted)
    finally:
        service._call_model = original_call_model
    return extracted, judged, prompts, responses


def run_pipeline(
    service: IMessageProcessingService,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str], list[str]]:
    return asyncio.run(run_pipeline_async(service, payload))


def assert_keywords(value: str | None, expected_keywords: tuple[str, ...], *, label: str, raw_text: str) -> None:
    text = (value or "").lower()
    missing = [keyword for keyword in expected_keywords if keyword.lower() not in text]
    assert not missing, f"{label} missing keywords {missing!r}.\nRaw response:\n{raw_text}"


def assert_any_keywords(
    values: list[str | None],
    expected_keywords: tuple[str, ...],
    *,
    label: str,
    raw_text: str,
) -> None:
    normalized_values = [(value or "").lower() for value in values]
    for value in normalized_values:
        if all(keyword.lower() in value for keyword in expected_keywords):
            return
    assert False, f"{label} missing keywords {list(expected_keywords)!r}.\nRaw response:\n{raw_text}"


def assert_any_action_field_matches(
    actions: list[dict[str, Any]],
    field_name: str,
    expected_keywords: tuple[str, ...],
    *,
    label: str,
    raw_text: str,
) -> None:
    assert actions, f"{label} expected at least one action.\nRaw response:\n{raw_text}"
    assert_any_keywords(
        [str(action.get(field_name) or "") for action in actions],
        expected_keywords,
        label=label,
        raw_text=raw_text,
    )


def assert_actions_have_source_ids(
    actions: list[dict[str, Any]],
    *,
    label: str,
    raw_text: str,
) -> None:
    assert actions, f"{label} expected at least one action.\nRaw response:\n{raw_text}"
    for index, action in enumerate(actions):
        source_ids = action.get("source_message_ids")
        assert isinstance(source_ids, list) and source_ids, (
            f"{label}[{index}] missing source_message_ids.\nRaw response:\n{raw_text}"
        )
        assert all(isinstance(item, int) and item > 0 for item in source_ids), (
            f"{label}[{index}] has invalid source_message_ids {source_ids!r}.\nRaw response:\n{raw_text}"
        )


def assert_any_approved(judged: dict[str, Any], action_key: str, raw_text: str) -> None:
    items = judged.get(action_key)
    assert isinstance(items, list) and items, f"Judge did not return verdicts for {action_key}.\nRaw response:\n{raw_text}"
    assert any(bool(item.get("approved")) for item in items), f"Judge rejected every {action_key} candidate.\nRaw response:\n{raw_text}"


def validate_todo_create_explicit(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["todo_creates"],
        "text",
        ("send", "sam", "permit"),
        label="todo_creates.text",
        raw_text=raw,
    )


def validate_todo_create_subtle(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["todo_creates"],
        "text",
        ("splitwise",),
        label="todo_creates.text",
        raw_text=raw,
    )


def validate_todo_create_named_meetup(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["todo_creates"],
        "text",
        ("owen", "poker", "heads-up"),
        label="todo_creates.text",
        raw_text=raw,
    )


def validate_todo_create_named_recipient(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["todo_creates"],
        "text",
        ("18.01", "madelyn"),
        label="todo_creates.text",
        raw_text=raw,
    )


def validate_todo_create_named_topic(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["todo_creates"],
        "text",
        ("madelyn", "chem"),
        label="todo_creates.text",
        raw_text=raw,
    )


def validate_todo_completion(extracted: dict[str, Any], raw: str) -> None:
    actions = extracted.get("todo_completions") or []
    assert actions, f"Expected todo completion suggestion.\nRaw response:\n{raw}"


def validate_calendar_explicit(extracted: dict[str, Any], raw: str) -> None:
    actions = extracted["calendar_creates"]
    assert_any_action_field_matches(
        actions,
        "summary",
        ("permit", "review"),
        label="calendar_creates.summary",
        raw_text=raw,
    )
    assert any(action.get("start_time") for action in actions), f"Missing start_time.\nRaw response:\n{raw}"
    assert any(action.get("end_time") for action in actions), f"Missing end_time.\nRaw response:\n{raw}"


def validate_calendar_subtle(extracted: dict[str, Any], raw: str) -> None:
    actions = extracted["calendar_creates"]
    assert_any_action_field_matches(
        actions,
        "summary",
        ("deck",),
        label="calendar_creates.summary",
        raw_text=raw,
    )
    assert any(action.get("start_time") for action in actions), f"Missing start_time.\nRaw response:\n{raw}"
    assert any(action.get("end_time") for action in actions), f"Missing end_time.\nRaw response:\n{raw}"


def validate_calendar_historical_relative(extracted: dict[str, Any], raw: str) -> None:
    actions = extracted["calendar_creates"]
    assert_any_action_field_matches(
        actions,
        "summary",
        ("dinner",),
        label="calendar_creates.summary",
        raw_text=raw,
    )
    start_times = [str(action.get("start_time") or "") for action in actions]
    assert any(start_time.startswith("2026-01-15") for start_time in start_times), (
        f"Expected historical relative date to resolve to 2026-01-15.\nRaw response:\n{raw}"
    )


def validate_calendar_named_counterparty(extracted: dict[str, Any], raw: str) -> None:
    actions = extracted["calendar_creates"]
    assert_any_action_field_matches(
        actions,
        "summary",
        ("dinner", "owen"),
        label="calendar_creates.summary",
        raw_text=raw,
    )


def validate_journal_explicit(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["journal_entries"],
        "text",
        ("submitted", "permit"),
        label="journal_entries.text",
        raw_text=raw,
    )


def validate_journal_subtle(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["journal_entries"],
        "text",
        ("lease", "signed"),
        label="journal_entries.text",
        raw_text=raw,
    )


def validate_journal_discussion_summary(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["journal_entries"],
        "text",
        ("aidan", "philosophy"),
        label="journal_entries.text",
        raw_text=raw,
    )


def validate_journal_family_planning(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["journal_entries"],
        "text",
        ("mom", "travel"),
        label="journal_entries.text",
        raw_text=raw,
    )


def validate_journal_specific_show(extracted: dict[str, Any], raw: str) -> None:
    assert_any_action_field_matches(
        extracted["journal_entries"],
        "text",
        ("watch", "severance"),
        label="journal_entries.text",
        raw_text=raw,
    )


def validate_workspace_explicit(extracted: dict[str, Any], raw: str) -> None:
    assert extracted["project_inference"]["project_name"] == "Forest Fire", f"Wrong project inference.\nRaw response:\n{raw}"
    assert extracted["project_inference"]["confidence"] >= 0.5, f"Confidence too low.\nRaw response:\n{raw}"
    assert_any_action_field_matches(
        extracted["workspace_updates"],
        "page_title",
        ("forest", "architecture"),
        label="workspace_updates.page_title",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["workspace_updates"],
        "summary",
        ("vendor",),
        label="workspace_updates.summary",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["workspace_updates"],
        "summary",
        ("pdf",),
        label="workspace_updates.summary",
        raw_text=raw,
    )


def validate_workspace_subtle(extracted: dict[str, Any], raw: str) -> None:
    assert extracted["project_inference"]["project_name"] == "Forest Fire", f"Wrong project inference.\nRaw response:\n{raw}"
    page_titles = [str(item.get("page_title") or "").lower() for item in extracted["workspace_updates"]]
    assert any("forest" in page_title for page_title in page_titles), (
        f"workspace_updates.page_title missing 'forest'.\nRaw response:\n{raw}"
    )
    assert any(
        "forest" in page_title and any(keyword in page_title for keyword in ("plan", "strategy", "rollout"))
        for page_title in page_titles
    ), (
        f"workspace_updates.page_title missing rollout-planning signal.\nRaw response:\n{raw}"
    )
    assert_any_action_field_matches(
        extracted["workspace_updates"],
        "summary",
        ("risk",),
        label="workspace_updates.summary",
        raw_text=raw,
    )


def validate_mixed_project_cluster(extracted: dict[str, Any], raw: str) -> None:
    assert extracted["project_inference"]["project_name"] == "Forest Fire", f"Wrong project inference.\nRaw response:\n{raw}"
    assert extracted["todo_creates"], f"Expected todo create.\nRaw response:\n{raw}"
    assert extracted["calendar_creates"], f"Expected calendar create.\nRaw response:\n{raw}"
    assert extracted["workspace_updates"], f"Expected workspace update.\nRaw response:\n{raw}"
    assert_any_action_field_matches(
        extracted["todo_creates"],
        "text",
        ("permit", "packet"),
        label="todo_creates.text",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["calendar_creates"],
        "summary",
        ("permit", "review"),
        label="calendar_creates.summary",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["workspace_updates"],
        "summary",
        ("pdf", "county"),
        label="workspace_updates.summary",
        raw_text=raw,
    )


def validate_mixed_personal_cluster(extracted: dict[str, Any], raw: str) -> None:
    assert extracted["todo_completions"], f"Expected todo completion.\nRaw response:\n{raw}"
    assert extracted["journal_entries"], f"Expected journal entry.\nRaw response:\n{raw}"
    assert_any_action_field_matches(
        extracted["journal_entries"],
        "text",
        ("aidan", "philosophy"),
        label="journal_entries.text",
        raw_text=raw,
    )


def validate_mixed_capital_one_cluster(extracted: dict[str, Any], raw: str) -> None:
    assert extracted["project_inference"]["project_name"] == "Capital One", f"Wrong project inference.\nRaw response:\n{raw}"
    assert extracted["todo_creates"], f"Expected todo create.\nRaw response:\n{raw}"
    assert extracted["calendar_creates"], f"Expected calendar create.\nRaw response:\n{raw}"
    assert extracted["workspace_updates"], f"Expected workspace update.\nRaw response:\n{raw}"
    assert_any_action_field_matches(
        extracted["todo_creates"],
        "text",
        ("upload", "receipts"),
        label="todo_creates.text",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["calendar_creates"],
        "summary",
        ("dispute", "deadline"),
        label="calendar_creates.summary",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["workspace_updates"],
        "summary",
        ("pdf", "documents"),
        label="workspace_updates.summary",
        raw_text=raw,
    )


def validate_mixed_personal_planning_cluster(extracted: dict[str, Any], raw: str) -> None:
    assert extracted["todo_creates"], f"Expected todo create.\nRaw response:\n{raw}"
    assert extracted["calendar_creates"], f"Expected calendar create.\nRaw response:\n{raw}"
    assert extracted["journal_entries"], f"Expected journal entry.\nRaw response:\n{raw}"
    assert_any_action_field_matches(
        extracted["todo_creates"],
        "text",
        ("book", "table"),
        label="todo_creates.text",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["calendar_creates"],
        "summary",
        ("dinner",),
        label="calendar_creates.summary",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["journal_entries"],
        "text",
        ("aidan", "philosophy"),
        label="journal_entries.text",
        raw_text=raw,
    )


def validate_mixed_training_cluster(extracted: dict[str, Any], raw: str) -> None:
    assert extracted["project_inference"]["project_name"] == "Ironman Training", f"Wrong project inference.\nRaw response:\n{raw}"
    assert extracted["todo_creates"], f"Expected todo create.\nRaw response:\n{raw}"
    assert extracted["calendar_creates"], f"Expected calendar create.\nRaw response:\n{raw}"
    assert extracted["workspace_updates"], f"Expected workspace update.\nRaw response:\n{raw}"
    assert_any_action_field_matches(
        extracted["todo_creates"],
        "text",
        ("swim", "friday"),
        label="todo_creates.text",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["calendar_creates"],
        "summary",
        ("long", "run"),
        label="calendar_creates.summary",
        raw_text=raw,
    )
    assert_any_action_field_matches(
        extracted["workspace_updates"],
        "summary",
        ("zone", "build"),
        label="workspace_updates.summary",
        raw_text=raw,
    )


TODO_CREATE_CASES = [
    ExtractionCase(
        name="explicit_todo_create",
        conversation_name="Personal Admin",
        messages=(MessageExample("I need to send Sam the signed permit packet tonight.", is_from_me=True),),
        action_key="todo_creates",
        validate=validate_todo_create_explicit,
    ),
    ExtractionCase(
        name="subtle_todo_create",
        conversation_name="Roommates",
        messages=(MessageExample("Can you settle up on Splitwise before dinner?"),),
        action_key="todo_creates",
        validate=validate_todo_create_subtle,
    ),
    ExtractionCase(
        name="named_person_trip_planning_todo_create",
        conversation_name="Owen",
        messages=(MessageExample("Can you meet Owen to plan the poker trip and play HU?"),),
        action_key="todo_creates",
        participants=("Owen", "Sean"),
        validate=validate_todo_create_named_meetup,
    ),
    ExtractionCase(
        name="named_recipient_todo_create",
        conversation_name="Madelyn",
        messages=(MessageExample("Please send 18.01 to Madelyn tonight."),),
        action_key="todo_creates",
        participants=("Madelyn", "Sean"),
        validate=validate_todo_create_named_recipient,
    ),
    ExtractionCase(
        name="named_topic_todo_create",
        conversation_name="Madelyn",
        messages=(MessageExample("Can you ask Madelyn about the chem p-set when you text her?"),),
        action_key="todo_creates",
        participants=("Madelyn", "Sean"),
        validate=validate_todo_create_named_topic,
    ),
]


TODO_COMPLETION_CASES = [
    ExtractionCase(
        name="explicit_todo_completion",
        conversation_name="Roommates",
        messages=(MessageExample("Done, I paid Splitwise.", is_from_me=True),),
        action_key="todo_completions",
        open_todos=(
            {
                "id": 401,
                "project_id": 9,
                "text": "Pay Splitwise balance",
                "deadline_utc": None,
                "completed": False,
            },
        ),
        validate=validate_todo_completion,
    ),
    ExtractionCase(
        name="subtle_todo_completion",
        conversation_name="Personal Admin",
        messages=(MessageExample("Took care of the reimbursement this morning.", is_from_me=True),),
        action_key="todo_completions",
        open_todos=(
            {
                "id": 402,
                "project_id": None,
                "text": "Send reimbursement",
                "deadline_utc": None,
                "completed": False,
            },
        ),
        validate=validate_todo_completion,
    ),
]


CALENDAR_CASES = [
    ExtractionCase(
        name="explicit_calendar_create",
        conversation_name="Forest Fire Scheduling",
        messages=(
            MessageExample(
                "March 12, 2026 from 3:00 to 3:30 PM is confirmed for the permit review."
            ),
        ),
        action_key="calendar_creates",
        validate=validate_calendar_explicit,
    ),
    ExtractionCase(
        name="subtle_calendar_create",
        conversation_name="Forest Fire Scheduling",
        messages=(
            MessageExample(
                "March 12, 2026 from 2:00 to 2:30 PM works for the deck walkthrough, let's put it on the calendar."
            ),
        ),
        action_key="calendar_creates",
        validate=validate_calendar_subtle,
    ),
    ExtractionCase(
        name="inferred_duration_calendar_create",
        conversation_name="Forest Fire Scheduling",
        messages=(
            MessageExample(
                "Tomorrow at 3 works for the permit review if we keep it quick."
            ),
            MessageExample(
                "Perfect, let's lock that in for 30 minutes.",
                sender="bob@example.com",
            ),
        ),
        action_key="calendar_creates",
        validate=validate_calendar_explicit,
    ),
    ExtractionCase(
        name="historical_relative_calendar_create",
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
        action_key="calendar_creates",
        participants=("aidan@example.com", "sean@example.com"),
        validate=validate_calendar_historical_relative,
    ),
    ExtractionCase(
        name="named_counterparty_calendar_create",
        conversation_name="Owen",
        messages=(
            MessageExample("Tomorrow at 6 works for dinner with Owen if we keep it to an hour.", is_from_me=True),
            MessageExample("Perfect, let's lock it in.", sender="Owen"),
        ),
        action_key="calendar_creates",
        participants=("Owen", "Sean"),
        validate=validate_calendar_named_counterparty,
    ),
]


JOURNAL_CASES = [
    ExtractionCase(
        name="explicit_journal_entry",
        conversation_name="Personal Wins",
        messages=(MessageExample("I submitted the permit packet this afternoon, so that's done.", is_from_me=True),),
        action_key="journal_entries",
        validate=validate_journal_explicit,
    ),
    ExtractionCase(
        name="subtle_journal_entry",
        conversation_name="Personal Wins",
        messages=(MessageExample("Finally got the lease signed.", is_from_me=True),),
        action_key="journal_entries",
        validate=validate_journal_subtle,
    ),
    ExtractionCase(
        name="discussion_summary_journal_entry",
        conversation_name="Aidan",
        messages=(
            MessageExample(
                "Talked to Aidan about philosophy for an hour and compared deontology against consequentialism.",
                is_from_me=True,
            ),
        ),
        action_key="journal_entries",
        participants=("aidan@example.com", "sean@example.com"),
        validate=validate_journal_discussion_summary,
    ),
    ExtractionCase(
        name="family_planning_journal_entry",
        conversation_name="Mom",
        messages=(
            MessageExample(
                "Had a call with Mom about July travel and narrowed down the best dates.",
                is_from_me=True,
            ),
        ),
        action_key="journal_entries",
        participants=("mom@example.com", "sean@example.com"),
        validate=validate_journal_family_planning,
    ),
    ExtractionCase(
        name="specific_show_journal_entry",
        conversation_name="Owen",
        messages=(
            MessageExample(
                "We decided to watch Severance after dinner.",
                is_from_me=True,
            ),
        ),
        action_key="journal_entries",
        participants=("Owen", "Sean"),
        validate=validate_journal_specific_show,
    ),
]


WORKSPACE_CASES = [
    ExtractionCase(
        name="explicit_workspace_update",
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
        action_key="workspace_updates",
        validate=validate_workspace_explicit,
    ),
    ExtractionCase(
        name="subtle_workspace_update",
        conversation_name="Forest Fire Core Team",
        messages=(
            MessageExample(
                "Forest Fire rollout should stay phased so permitting risk stays manageable while crews ramp up."
            ),
            MessageExample(
                "Agreed, let's keep the rollout phased while crews ramp up so permitting stays manageable."
                ,
                sender="bob@example.com",
            ),
        ),
        action_key="workspace_updates",
        validate=validate_workspace_subtle,
    ),
]


PROJECT_INFERENCE_CASES = [
    ProjectInferenceCase(
        name="forest_fire_over_forest_floor",
        conversation_name="Core Team",
        messages=(
            MessageExample("County permitting is still the gating item, and vendor X needs the final debris scope."),
            MessageExample("Let's keep the rollout phased until the county signoff lands."),
        ),
        projects=("Forest Fire", "Forest Floor", "Personal Ops"),
        heuristic_project_name="Forest Fire",
        heuristic_confidence=0.57,
        project_candidates=(
            {
                "project_name": "Forest Fire",
                "confidence": 0.57,
                "reasons": ["messages overlap with county permit and vendor vocabulary from project notes"],
            },
            {
                "project_name": "Forest Floor",
                "confidence": 0.49,
                "reasons": ["generic overlap on forest-related naming"],
            },
        ),
        expected_project_name="Forest Fire",
        min_confidence=0.5,
    ),
    ProjectInferenceCase(
        name="capital_one_over_personal_ops",
        conversation_name="Capital One",
        messages=(
            MessageExample("The Venture X dispute still needs follow-up with the travel credit team."),
            MessageExample("Let's keep all card-benefit notes in the Capital One page."),
        ),
        projects=("Capital One", "Ironman Training", "Personal Ops"),
        heuristic_project_name="Capital One",
        heuristic_confidence=0.61,
        project_candidates=(
            {
                "project_name": "Capital One",
                "confidence": 0.61,
                "reasons": ["conversation title names Capital One and messages mention Venture X card support"],
            },
            {
                "project_name": "Personal Ops",
                "confidence": 0.42,
                "reasons": ["generic admin overlap"],
            },
        ),
        expected_project_name="Capital One",
        min_confidence=0.5,
    ),
    ProjectInferenceCase(
        name="ironman_training_over_personal_ops",
        conversation_name="Coach Mike",
        messages=(
            MessageExample("The long ride should stay at zone 2 and the brick run moves to Sunday."),
            MessageExample("Let's update the Ironman build plan after this week."),
        ),
        projects=("Capital One", "Ironman Training", "Personal Ops"),
        heuristic_project_name="Ironman Training",
        heuristic_confidence=0.55,
        project_candidates=(
            {
                "project_name": "Ironman Training",
                "confidence": 0.55,
                "reasons": ["messages mention long ride, brick run, and training build plan"],
            },
            {
                "project_name": "Personal Ops",
                "confidence": 0.34,
                "reasons": ["generic planning overlap"],
            },
        ),
        expected_project_name="Ironman Training",
        min_confidence=0.45,
    ),
    ProjectInferenceCase(
        name="ambiguous_generic_planning_returns_none",
        conversation_name="Core Team",
        messages=(
            MessageExample("Let's review the plan tomorrow."),
            MessageExample("Three works for me."),
        ),
        projects=("Forest Fire", "Capital One", "Personal Ops"),
        heuristic_project_name="Forest Fire",
        heuristic_confidence=0.52,
        project_candidates=(
            {
                "project_name": "Forest Fire",
                "confidence": 0.52,
                "reasons": ["weak generic planning overlap"],
            },
            {
                "project_name": "Capital One",
                "confidence": 0.5,
                "reasons": ["weak generic planning overlap"],
            },
        ),
        expected_project_name=None,
    ),
]


MIXED_EXTRACTION_CASES = [
    MixedExtractionCase(
        name="project_cluster_emits_calendar_todo_and_workspace",
        conversation_name="Forest Fire Core Team",
        messages=(
            MessageExample("March 12, 2026 from 3:00 to 3:30 PM is confirmed for the permit review."),
            MessageExample("I need to send Sam the revised permit packet before then.", is_from_me=True),
            MessageExample("County only accepts PDF submissions now."),
            MessageExample(
                "Agreed, let's capture the PDF requirement in the architecture page.",
                sender="bob@example.com",
            ),
        ),
        expected_non_empty_keys=("todo_creates", "calendar_creates", "workspace_updates"),
        validate=validate_mixed_project_cluster,
    ),
    MixedExtractionCase(
        name="personal_cluster_emits_completion_and_discussion_journal",
        conversation_name="Aidan",
        messages=(
            MessageExample("Done, I sent the reimbursement form.", is_from_me=True),
            MessageExample(
                "Talked to Aidan about philosophy and compared deontology with consequentialism.",
                is_from_me=True,
            ),
        ),
        expected_non_empty_keys=("todo_completions", "journal_entries"),
        open_todos=(
            {
                "id": 499,
                "project_id": None,
                "text": "Send reimbursement form",
                "deadline_utc": None,
                "completed": False,
            },
        ),
        participants=("aidan@example.com", "sean@example.com"),
        validate=validate_mixed_personal_cluster,
    ),
    MixedExtractionCase(
        name="capital_one_cluster_emits_deadline_todo_and_workspace",
        conversation_name="Capital One",
        messages=(
            MessageExample("The Venture X dispute filing deadline is March 14, 2026."),
            MessageExample("I need to upload the travel receipts tonight.", is_from_me=True),
            MessageExample("Capital One wants every supporting document bundled into one PDF."),
            MessageExample(
                "Agreed, let's add the one-PDF requirement to the dispute notes.",
                sender="bob@example.com",
            ),
        ),
        expected_non_empty_keys=("todo_creates", "calendar_creates", "workspace_updates"),
        projects=("Capital One", "Ironman Training", "Personal Ops"),
        participants=("support@capitalone.com", "sean@example.com"),
        validate=validate_mixed_capital_one_cluster,
    ),
    MixedExtractionCase(
        name="personal_cluster_emits_calendar_todo_and_journal",
        conversation_name="Aidan",
        messages=(
            MessageExample("Tomorrow at 6 works for dinner if we keep it to an hour.", is_from_me=True),
            MessageExample("Perfect, let's lock it in.", sender="aidan@example.com"),
            MessageExample("I need to book the table this afternoon.", is_from_me=True),
            MessageExample("Talked with Aidan about free will and philosophy after work.", is_from_me=True),
        ),
        expected_non_empty_keys=("todo_creates", "calendar_creates", "journal_entries"),
        participants=("aidan@example.com", "sean@example.com"),
        validate=validate_mixed_personal_planning_cluster,
    ),
    MixedExtractionCase(
        name="training_cluster_emits_calendar_todo_and_workspace",
        conversation_name="Ironman Training Coach",
        messages=(
            MessageExample("Thursday, March 12 at 7:00 AM works for the long run if we cap it at 90 minutes."),
            MessageExample("Perfect, let's lock that in.", is_from_me=True),
            MessageExample("I need to move the swim session to Friday, March 13.", is_from_me=True),
            MessageExample("Zone 2 should stay the focus for this build block.", is_from_me=True),
            MessageExample("Agreed, let's keep zone 2 as the focus this build block.", sender="coach@example.com"),
        ),
        expected_non_empty_keys=("todo_creates", "calendar_creates", "workspace_updates"),
        projects=("Capital One", "Ironman Training", "Personal Ops"),
        participants=("coach@example.com", "sean@example.com"),
        validate=validate_mixed_training_cluster,
    ),
]


def _validate_action_and_judge(case: ExtractionCase, service: IMessageProcessingService) -> None:
    payload = build_payload(
        conversation_name=case.conversation_name,
        messages=case.messages,
        open_todos=case.open_todos,
        projects=case.projects,
        participants=case.participants,
    )
    extracted, judged, prompts, responses = run_pipeline(service, payload)
    extractor_raw = "\n\n".join(responses[:-1]) or json.dumps(extracted, ensure_ascii=False, indent=2)
    actions = extracted.get(case.action_key)
    assert isinstance(actions, list) and actions, f"Extractor produced no {case.action_key}.\nRaw response:\n{extractor_raw}"
    assert_actions_have_source_ids(actions, label=case.action_key, raw_text=extractor_raw)
    if case.validate:
        case.validate(extracted, extractor_raw)

    judge_raw = responses[-1] if responses else json.dumps(judged, ensure_ascii=False, indent=2)
    assert any("non-calendar action extractor" in prompt for prompt in prompts), (
        f"Expected the narrowed non-calendar extractor prompt to run.\nPrompts:\n{prompts}"
    )
    if case.action_key == "calendar_creates":
        assert any("calendar extractor" in prompt for prompt in prompts), (
            f"Expected the dedicated calendar extractor prompt to run.\nPrompts:\n{prompts}"
        )
    assert_any_approved(judged, case.action_key, judge_raw)
    if case.action_key == "workspace_updates":
        project_verdict = judged.get("project_inference") or {}
        assert bool(project_verdict.get("approved")), f"Judge rejected project inference.\nRaw response:\n{judge_raw}"


async def _validate_action_and_judge_async(
    case: ExtractionCase,
    base_service: IMessageProcessingService,
    semaphore: asyncio.Semaphore,
) -> str | None:
    async with semaphore:
        service = clone_live_service(base_service)
        payload = build_payload(
            conversation_name=case.conversation_name,
            messages=case.messages,
            open_todos=case.open_todos,
            projects=case.projects,
            participants=case.participants,
        )
        try:
            extracted, judged, prompts, responses = await run_pipeline_async(service, payload)
            extractor_raw = "\n\n".join(responses[:-1]) or json.dumps(extracted, ensure_ascii=False, indent=2)
            actions = extracted.get(case.action_key)
            assert isinstance(actions, list) and actions, (
                f"{case.name}: extractor produced no {case.action_key}.\nRaw response:\n{extractor_raw}"
            )
            assert_actions_have_source_ids(actions, label=f"{case.name}.{case.action_key}", raw_text=extractor_raw)
            if case.validate:
                case.validate(extracted, extractor_raw)
            judge_raw = responses[-1] if responses else json.dumps(judged, ensure_ascii=False, indent=2)
            assert any("non-calendar action extractor" in prompt for prompt in prompts), (
                f"{case.name}: expected the narrowed non-calendar extractor prompt to run.\nPrompts:\n{prompts}"
            )
            if case.action_key == "calendar_creates":
                assert any("calendar extractor" in prompt for prompt in prompts), (
                    f"{case.name}: expected the dedicated calendar extractor prompt to run.\nPrompts:\n{prompts}"
                )
            assert_any_approved(judged, case.action_key, judge_raw)
            if case.action_key == "workspace_updates":
                project_verdict = judged.get("project_inference") or {}
                assert bool(project_verdict.get("approved")), (
                    f"{case.name}: judge rejected project inference.\nRaw response:\n{judge_raw}"
                )
            return None
        except AssertionError as exc:
            return str(exc)


def _run_cases_concurrently(
    *,
    cases: list[ExtractionCase],
    live_service: IMessageProcessingService,
    limit: int = 3,
) -> None:
    async def _runner() -> list[str]:
        semaphore = asyncio.Semaphore(limit)
        results = await asyncio.gather(
            *(_validate_action_and_judge_async(case, live_service, semaphore) for case in cases)
        )
        return [item for item in results if item]

    failures = asyncio.run(_runner())
    assert not failures, "\n\n".join(failures)


def _validate_project_inference(case: ProjectInferenceCase, live_service: IMessageProcessingService) -> None:
    payload = build_payload(
        conversation_name=case.conversation_name,
        messages=case.messages,
        projects=case.projects,
    )
    payload["heuristic_project_guess"] = {
        "project_name": case.heuristic_project_name,
        "confidence": case.heuristic_confidence,
        "reason": "Deterministic retrieval result under review.",
    }
    payload["project_candidates"] = list(case.project_candidates)

    prompts: list[str] = []
    responses: list[str] = []
    service = clone_live_service(live_service)
    original_call_model = service._call_model

    async def tracked_call_model(self, prompt: str) -> str:
        prompts.append(prompt)
        text = await original_call_model(prompt)
        responses.append(text)
        return text

    service._call_model = MethodType(tracked_call_model, service)
    try:
        project_inference = asyncio.run(service._extract_project_inference(payload))
    finally:
        service._call_model = original_call_model

    raw = responses[-1] if responses else json.dumps(project_inference, ensure_ascii=False, indent=2)
    assert any("You infer whether an iMessage cluster belongs to one existing project." in prompt for prompt in prompts), (
        f"Expected the dedicated project inference prompt to run.\nPrompts:\n{prompts}"
    )
    assert project_inference["project_name"] == case.expected_project_name, f"Wrong project inference for {case.name}.\nRaw response:\n{raw}"
    if case.expected_project_name is not None:
        assert project_inference["confidence"] >= case.min_confidence, f"Confidence too low for {case.name}.\nRaw response:\n{raw}"
        source_ids = project_inference.get("source_message_ids")
        assert isinstance(source_ids, list) and source_ids, (
            f"Expected source_message_ids for routed project inference {case.name}.\nRaw response:\n{raw}"
        )
    else:
        assert project_inference["confidence"] <= 0.35, f"Expected low confidence null routing for {case.name}.\nRaw response:\n{raw}"


async def _validate_mixed_case_async(
    case: MixedExtractionCase,
    base_service: IMessageProcessingService,
    semaphore: asyncio.Semaphore,
) -> str | None:
    async with semaphore:
        service = clone_live_service(base_service)
        payload = build_payload(
            conversation_name=case.conversation_name,
            messages=case.messages,
            open_todos=case.open_todos,
            projects=case.projects,
            participants=case.participants,
        )
        try:
            extracted, judged, prompts, responses = await run_pipeline_async(service, payload)
            raw = "\n\n".join(responses) or json.dumps({"extracted": extracted, "judged": judged}, ensure_ascii=False, indent=2)
            assert any("calendar extractor" in prompt for prompt in prompts), (
                f"{case.name}: expected dedicated calendar extractor prompt.\nPrompts:\n{prompts}"
            )
            for key in case.expected_non_empty_keys:
                actions = extracted.get(key)
                assert isinstance(actions, list) and actions, f"{case.name}: expected non-empty {key}.\nRaw response:\n{raw}"
                assert_actions_have_source_ids(actions, label=f"{case.name}.{key}", raw_text=raw)
                assert_any_approved(judged, key, raw)
            if "workspace_updates" in case.expected_non_empty_keys:
                assert bool((judged.get("project_inference") or {}).get("approved")), (
                    f"{case.name}: expected approved project inference.\nRaw response:\n{raw}"
                )
            if case.validate:
                case.validate(extracted, raw)
            return None
        except AssertionError as exc:
            return str(exc)


def _run_mixed_cases_concurrently(
    *,
    cases: list[MixedExtractionCase],
    live_service: IMessageProcessingService,
    limit: int = 2,
) -> None:
    async def _runner() -> list[str]:
        semaphore = asyncio.Semaphore(limit)
        results = await asyncio.gather(
            *(_validate_mixed_case_async(case, live_service, semaphore) for case in cases)
        )
        return [item for item in results if item]

    failures = asyncio.run(_runner())
    assert not failures, "\n\n".join(failures)


def test_live_llm_todo_create_cases(live_service: IMessageProcessingService) -> None:
    _run_cases_concurrently(cases=TODO_CREATE_CASES, live_service=live_service)


def test_live_llm_todo_completion_cases(live_service: IMessageProcessingService) -> None:
    _run_cases_concurrently(cases=TODO_COMPLETION_CASES, live_service=live_service)


def test_live_llm_calendar_cases(live_service: IMessageProcessingService) -> None:
    _run_cases_concurrently(cases=CALENDAR_CASES, live_service=live_service)


def test_live_llm_journal_cases(live_service: IMessageProcessingService) -> None:
    _run_cases_concurrently(cases=JOURNAL_CASES, live_service=live_service)


def test_live_llm_workspace_update_cases(live_service: IMessageProcessingService) -> None:
    _run_cases_concurrently(cases=WORKSPACE_CASES, live_service=live_service)


@pytest.mark.parametrize("case", PROJECT_INFERENCE_CASES, ids=lambda case: case.name)
def test_live_llm_project_inference_cases(case: ProjectInferenceCase, live_service: IMessageProcessingService) -> None:
    _validate_project_inference(case, live_service)


def test_live_llm_mixed_cluster_cases(live_service: IMessageProcessingService) -> None:
    _run_mixed_cases_concurrently(cases=MIXED_EXTRACTION_CASES, live_service=live_service)


def test_live_llm_deduplicator_todo_case(live_service: IMessageProcessingService) -> None:
    service = clone_live_service(live_service)
    cluster = SimpleNamespace(
        messages=[
            SimpleNamespace(
                id=1,
                sent_at_utc=datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc),
                is_from_me=False,
                sender_label="Madelyn",
                handle_identifier="madelyn@example.com",
                text="Please send 18.01 to Madelyn tonight.",
            )
        ]
    )

    async def fake_candidates(self, **kwargs):
        return [
            {
                "artifact_type": "todo",
                "artifact_id": 77,
                "text": "Send 18.01 to Madelyn",
                "deadline_utc": None,
                "created_at": "2026-03-10T12:00:00Z",
            }
        ]

    service._load_dedup_candidates = MethodType(fake_candidates, service)

    decision = asyncio.run(
        service._deduplicate_action(
            user_id=1,
            cluster=cluster,
            action_type="todo.create",
            action={
                "text": "Send 18.01 to Madelyn tonight",
                "source_message_ids": [1],
                "reason": "Direct request.",
            },
            project_id=None,
            time_zone="America/New_York",
        )
    )

    assert decision.is_duplicate is True
    assert decision.matched_candidate_type == "todo"
    assert decision.matched_candidate_id == 77
