"""Comprehensive test suite for MonetAssistantAgent — routing, tool execution, contextual actions, and reply composition."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.schemas.assistant import AssistantAction, AssistantPageContext, AssistantSelectedEntity
from app.schemas.llm_outputs import (
    AssistantActionPlanOutput,
    AssistantActionPlanItemOutput,
    AssistantRouterOutput,
    AssistantToolCallOutput,
)
from app.services.monet_assistant import (
    MonetAssistantAgent,
    MonetToolRegistry,
    NutritionLogTool,
    TodoCreateTool,
    RouterDecision,
    ToolCall,
    ToolExecutionResult,
)


def _run(coro):
    """Helper to run async code in sync tests."""
    return asyncio.run(coro)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def agent(mock_session, monkeypatch):
    mock_client = MagicMock()
    mock_context_builder = MagicMock()
    monkeypatch.setattr("app.services.monet_assistant.get_shared_openai_client", lambda: MagicMock())
    monkeypatch.setattr("app.services.monet_assistant.OpenAIResponsesClient", lambda **kwargs: mock_client)
    monkeypatch.setattr("app.services.monet_assistant.MonetContextBuilder", lambda session: mock_context_builder)
    a = MonetAssistantAgent(mock_session)
    a.client = mock_client
    a.context_builder = mock_context_builder
    return a


# ── MonetToolRegistry ─────────────────────────────────────────────────────

class TestMonetToolRegistry:
    def test_registers_both_tools(self, mock_session):
        registry = MonetToolRegistry(mock_session)
        assert registry.get("nutrition.log_intake") is not None
        assert registry.get("todos.create_items") is not None

    def test_returns_none_for_unknown_tool(self, mock_session):
        registry = MonetToolRegistry(mock_session)
        assert registry.get("unknown.tool") is None

    def test_prompt_specs_returns_tool_descriptions(self, mock_session):
        registry = MonetToolRegistry(mock_session)
        specs = registry.prompt_specs()
        assert len(specs) == 2
        ids = {s["tool_id"] for s in specs}
        assert "nutrition.log_intake" in ids
        assert "todos.create_items" in ids
        for spec in specs:
            assert "description" in spec
            assert "input_schema" in spec


# ── NutritionLogTool ──────────────────────────────────────────────────────

class TestNutritionLogTool:
    def test_run_delegates_to_nutrition_agent(self, mock_session, monkeypatch):
        monkeypatch.setattr("app.services.monet_assistant.NutritionAssistantAgent", lambda s: MagicMock())
        tool = NutritionLogTool(mock_session)
        mock_response = Mock(reply="Logged banana.", logged_entries=[{"food_name": "banana", "quantity": 1, "unit": "medium"}])
        tool.agent.respond = AsyncMock(return_value=mock_response)

        result = _run(tool.run(1, {"message": "I ate a banana"}))

        tool.agent.respond.assert_awaited_once_with(1, "I ate a banana")
        assert result["reply"] == "Logged banana."
        assert len(result["logged_entries"]) == 1

    def test_run_returns_empty_for_blank_message(self, mock_session, monkeypatch):
        monkeypatch.setattr("app.services.monet_assistant.NutritionAssistantAgent", lambda s: MagicMock())
        tool = NutritionLogTool(mock_session)
        result = _run(tool.run(1, {"message": ""}))
        assert result["logged_entries"] == []

    def test_run_returns_empty_for_missing_message(self, mock_session, monkeypatch):
        monkeypatch.setattr("app.services.monet_assistant.NutritionAssistantAgent", lambda s: MagicMock())
        tool = NutritionLogTool(mock_session)
        result = _run(tool.run(1, {}))
        assert result["logged_entries"] == []


# ── TodoCreateTool ────────────────────────────────────────────────────────

class TestTodoCreateTool:
    def test_run_delegates_to_todo_agent(self, mock_session, monkeypatch):
        monkeypatch.setattr("app.services.monet_assistant.TodoAssistantAgent", lambda s: MagicMock())
        tool = TodoCreateTool(mock_session)
        mock_item = Mock(id=1, text="Call bank", project_id=1, completed=False)
        mock_response = Mock(reply="Added todo.", items=[mock_item], raw_payload={})
        tool.agent.respond = AsyncMock(return_value=mock_response)

        result = _run(tool.run(1, {"message": "Remind me to call the bank"}))

        tool.agent.respond.assert_awaited_once_with(1, "Remind me to call the bank")
        assert result["reply"] == "Added todo."
        assert len(result["items"]) == 1

    def test_run_returns_empty_for_blank_message(self, mock_session, monkeypatch):
        monkeypatch.setattr("app.services.monet_assistant.TodoAssistantAgent", lambda s: MagicMock())
        tool = TodoCreateTool(mock_session)
        result = _run(tool.run(1, {"message": "  "}))
        assert result["items"] == []


# ── RouterDecision ────────────────────────────────────────────────────────

class TestRouterDecision:
    def test_to_prompt_dict_format(self):
        decision = RouterDecision(
            reply_mode="respond_and_call_tools",
            narrative_intent="Log food and create todo.",
            tool_calls=[
                ToolCall(tool_id="nutrition.log_intake", args={"message": "ate pizza"}),
                ToolCall(tool_id="todos.create_items", args={"message": "call mom"}),
            ],
        )
        d = decision.to_prompt_dict()
        assert d["reply_mode"] == "respond_and_call_tools"
        assert len(d["tool_calls"]) == 2
        assert d["tool_calls"][0]["tool_id"] == "nutrition.log_intake"

    def test_empty_tool_calls(self):
        decision = RouterDecision("respond_only", "Just chat.", [])
        d = decision.to_prompt_dict()
        assert d["tool_calls"] == []


# ── MonetAssistantAgent._route_message ────────────────────────────────────

class TestRouteMessage:
    def test_routes_to_respond_only(self, agent):
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantRouterOutput(
                reply_mode="respond_only",
                narrative_intent="Just answer the question.",
                tool_calls=[],
            )
        ))
        decision = _run(agent._route_message("What's the weather?", {}))
        assert decision.reply_mode == "respond_only"
        assert decision.tool_calls == []

    def test_routes_to_nutrition_tool(self, agent):
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantRouterOutput(
                reply_mode="respond_and_call_tools",
                narrative_intent="User wants to log food.",
                tool_calls=[
                    AssistantToolCallOutput(tool_id="nutrition.log_intake", args_json=json.dumps({"message": "ate a salad"})),
                ],
            )
        ))
        decision = _run(agent._route_message("I just ate a salad", {}))
        assert decision.reply_mode == "respond_and_call_tools"
        assert len(decision.tool_calls) == 1
        assert decision.tool_calls[0].tool_id == "nutrition.log_intake"

    def test_routes_to_todo_tool(self, agent):
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantRouterOutput(
                reply_mode="respond_and_call_tools",
                narrative_intent="User wants to create a todo.",
                tool_calls=[
                    AssistantToolCallOutput(tool_id="todos.create_items", args_json=json.dumps({"message": "call dentist"})),
                ],
            )
        ))
        decision = _run(agent._route_message("Remind me to call the dentist", {}))
        assert len(decision.tool_calls) == 1
        assert decision.tool_calls[0].tool_id == "todos.create_items"

    def test_routes_to_both_tools(self, agent):
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantRouterOutput(
                reply_mode="respond_and_call_tools",
                narrative_intent="Log food and create reminder.",
                tool_calls=[
                    AssistantToolCallOutput(tool_id="nutrition.log_intake", args_json=json.dumps({"message": "banana"})),
                    AssistantToolCallOutput(tool_id="todos.create_items", args_json=json.dumps({"message": "call bank"})),
                ],
            )
        ))
        decision = _run(agent._route_message("I ate a banana and remind me to call the bank", {}))
        assert len(decision.tool_calls) == 2

    def test_falls_back_on_llm_failure(self, agent):
        agent.client.generate_json = AsyncMock(side_effect=Exception("LLM down"))
        decision = _run(agent._route_message("Hello", {}))
        assert decision.reply_mode == "respond_only"
        assert decision.tool_calls == []

    def test_skips_empty_tool_ids(self, agent):
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantRouterOutput(
                reply_mode="respond_and_call_tools",
                narrative_intent="Intent.",
                tool_calls=[
                    AssistantToolCallOutput(tool_id="", args_json="{}"),
                    AssistantToolCallOutput(tool_id="nutrition.log_intake", args_json=json.dumps({"message": "pizza"})),
                ],
            )
        ))
        decision = _run(agent._route_message("Ate pizza", {}))
        assert len(decision.tool_calls) == 1
        assert decision.tool_calls[0].tool_id == "nutrition.log_intake"


# ── MonetAssistantAgent._execute_tools ────────────────────────────────────

class TestExecuteTools:
    def test_executes_nutrition_tool(self, agent):
        mock_tool = AsyncMock()
        mock_tool.run = AsyncMock(return_value={
            "reply": "Logged.",
            "logged_entries": [{"food_name": "pasta", "quantity": 1, "unit": "plate"}],
        })
        agent.tool_registry._tools["nutrition.log_intake"] = mock_tool
        calls = [ToolCall(tool_id="nutrition.log_intake", args={"message": "ate pasta"})]
        results = _run(agent._execute_tools(1, calls))
        assert "nutrition.log_intake" in results.tools_used
        assert len(results.nutrition_entries) == 1

    def test_executes_todo_tool(self, agent):
        mock_todo = Mock(
            id=42, project_id=1, text="Buy milk", completed=False,
            deadline_utc=None, deadline_is_date_only=False, is_overdue=False,
            created_at=None, updated_at=None, completed_at_utc=None, time_horizon=None,
        )
        mock_tool = AsyncMock()
        mock_tool.run = AsyncMock(return_value={
            "reply": "Created.", "items": [mock_todo], "raw_payload": {},
        })
        agent.tool_registry._tools["todos.create_items"] = mock_tool
        calls = [ToolCall(tool_id="todos.create_items", args={"message": "buy milk"})]
        results = _run(agent._execute_tools(1, calls))
        assert "todos.create_items" in results.tools_used
        assert len(results.todo_items) == 1

    def test_skips_unknown_tool(self, agent):
        calls = [ToolCall(tool_id="unknown.tool", args={})]
        results = _run(agent._execute_tools(1, calls))
        assert results.tools_used == []

    def test_handles_multiple_tool_calls(self, agent):
        mock_nutrition = AsyncMock()
        mock_nutrition.run = AsyncMock(return_value={"reply": "Logged.", "logged_entries": [{"food_name": "banana"}]})
        mock_todo = AsyncMock()
        mock_todo.run = AsyncMock(return_value={"reply": "Created.", "items": [], "raw_payload": {}})
        agent.tool_registry._tools["nutrition.log_intake"] = mock_nutrition
        agent.tool_registry._tools["todos.create_items"] = mock_todo
        calls = [
            ToolCall(tool_id="nutrition.log_intake", args={"message": "banana"}),
            ToolCall(tool_id="todos.create_items", args={"message": "call bank"}),
        ]
        results = _run(agent._execute_tools(1, calls))
        assert len(results.tools_used) == 2


# ── MonetAssistantAgent._compose_reply ────────────────────────────────────

class TestComposeReply:
    def test_returns_llm_text(self, agent):
        agent.client.generate_text = AsyncMock(return_value=SimpleNamespace(
            text="Logged your banana and added call the bank to your list."
        ))
        decision = RouterDecision("respond_and_call_tools", "Log food + create todo.", [])
        tool_results = ToolExecutionResult(
            nutrition_entries=[{"food_name": "banana"}],
            todo_items=[{"text": "Call the bank"}],
            tools_used=["nutrition.log_intake", "todos.create_items"],
        )
        reply = _run(agent._compose_reply("ate banana and remind me to call bank", {}, decision, tool_results))
        assert len(reply) > 0

    def test_returns_fallback_on_empty_reply(self, agent):
        agent.client.generate_text = AsyncMock(return_value=SimpleNamespace(text=""))
        decision = RouterDecision("respond_only", "Respond.", [])
        tool_results = ToolExecutionResult()
        reply = _run(agent._compose_reply("Hello", {}, decision, tool_results))
        assert reply == "I'm here whenever you're ready to continue."


# ── MonetAssistantAgent.respond (full flow) ───────────────────────────────

class TestRespondFullFlow:
    def test_respond_only_flow(self, agent):
        agent.context_builder.build_context = AsyncMock(return_value={"time": "now"})
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantRouterOutput(reply_mode="respond_only", narrative_intent="Answer.", tool_calls=[])
        ))
        agent.client.generate_text = AsyncMock(return_value=SimpleNamespace(text="I'm doing well!"))

        result = _run(agent.respond(user_id=1, message="How are you?"))

        assert result.reply == "I'm doing well!"
        assert result.nutrition_entries == []
        assert result.todo_items == []
        assert result.tools_used == []
        assert result.session_id

    def test_respond_with_tools_flow(self, agent):
        agent.context_builder.build_context = AsyncMock(return_value={})
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantRouterOutput(
                reply_mode="respond_and_call_tools",
                narrative_intent="Log food.",
                tool_calls=[AssistantToolCallOutput(tool_id="nutrition.log_intake", args_json=json.dumps({"message": "ate eggs"}))],
            )
        ))
        mock_tool = AsyncMock()
        mock_tool.run = AsyncMock(return_value={
            "reply": "Logged eggs.",
            "logged_entries": [{"food_name": "eggs", "quantity": 2, "unit": "large", "status": "logged"}],
        })
        agent.tool_registry._tools["nutrition.log_intake"] = mock_tool
        agent.client.generate_text = AsyncMock(return_value=SimpleNamespace(text="Got it — logged 2 large eggs."))

        result = _run(agent.respond(user_id=1, message="I ate 2 eggs"))

        assert "eggs" in result.reply.lower()
        assert len(result.nutrition_entries) == 1
        assert "nutrition.log_intake" in result.tools_used

    def test_preserves_session_id(self, agent):
        agent.context_builder.build_context = AsyncMock(return_value={})
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantRouterOutput(reply_mode="respond_only", narrative_intent=".", tool_calls=[])
        ))
        agent.client.generate_text = AsyncMock(return_value=SimpleNamespace(text="Hi!"))
        result = _run(agent.respond(user_id=1, message="hi", session_id="my-session-123"))
        assert result.session_id == "my-session-123"

    def test_generates_session_id_if_none(self, agent):
        agent.context_builder.build_context = AsyncMock(return_value={})
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantRouterOutput(reply_mode="respond_only", narrative_intent=".", tool_calls=[])
        ))
        agent.client.generate_text = AsyncMock(return_value=SimpleNamespace(text="Hi!"))
        result = _run(agent.respond(user_id=1, message="hi"))
        assert result.session_id
        assert len(result.session_id) > 10


# ── Contextual actions (preview/commit) ───────────────────────────────────

class TestContextualActions:
    def test_preview_mode_returns_proposed_actions(self, agent):
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantActionPlanOutput(actions=[
                AssistantActionPlanItemOutput(
                    action_type="calendar.create_event",
                    params_json=json.dumps({"summary": "Team standup", "start_time": "2026-03-20T10:00:00Z", "end_time": "2026-03-20T10:30:00Z"}),
                ),
            ])
        ))
        page_context = AssistantPageContext(page="calendar")
        result = _run(agent.respond(user_id=1, message="Schedule standup", page_context=page_context, execution_mode="preview"))
        assert result.requires_confirmation is True
        assert len(result.proposed_actions) == 1
        assert result.proposed_actions[0].action_type == "calendar.create_event"
        assert result.action_plan_id is not None

    def test_preview_mode_no_actions(self, agent):
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantActionPlanOutput(actions=[])
        ))
        page_context = AssistantPageContext(page="calendar")
        result = _run(agent.respond(user_id=1, message="Do something", page_context=page_context, execution_mode="preview"))
        assert result.requires_confirmation is False
        assert result.proposed_actions == []
        assert "more detail" in result.reply.lower()

    def test_preview_filters_wrong_page_actions(self, agent):
        agent.client.generate_json = AsyncMock(return_value=SimpleNamespace(
            data=AssistantActionPlanOutput(actions=[
                AssistantActionPlanItemOutput(action_type="projects.create_todo", params_json=json.dumps({"text": "Buy milk"})),
            ])
        ))
        page_context = AssistantPageContext(page="calendar")
        result = _run(agent.respond(user_id=1, message="Add todo", page_context=page_context, execution_mode="preview"))
        assert result.proposed_actions == []


# ── _normalize_action ─────────────────────────────────────────────────────

class TestNormalizeAction:
    def test_rejects_unknown_action_type(self, agent):
        ctx = AssistantPageContext(page="calendar")
        assert agent._normalize_action({"action_type": "unknown.type", "params": {}}, ctx) is None

    def test_rejects_calendar_action_on_projects_page(self, agent):
        ctx = AssistantPageContext(page="projects")
        assert agent._normalize_action({"action_type": "calendar.create_event", "params": {}}, ctx) is None

    def test_rejects_project_action_on_calendar_page(self, agent):
        ctx = AssistantPageContext(page="calendar")
        assert agent._normalize_action({"action_type": "projects.create_todo", "params": {}}, ctx) is None

    def test_accepts_valid_calendar_action(self, agent):
        ctx = AssistantPageContext(page="calendar")
        result = agent._normalize_action({"action_type": "calendar.create_event", "params": {"summary": "Standup"}}, ctx)
        assert result is not None
        assert result.action_type == "calendar.create_event"

    def test_injects_selected_entity_project_id(self, agent):
        ctx = AssistantPageContext(page="projects", selected_entity=AssistantSelectedEntity(project_id=42))
        result = agent._normalize_action({"action_type": "projects.create_todo", "params": {"text": "Buy milk"}}, ctx)
        assert result is not None
        assert result.params["project_id"] == 42

    def test_injects_selected_entity_event_id(self, agent):
        ctx = AssistantPageContext(page="calendar", selected_entity=AssistantSelectedEntity(calendar_event_id=99))
        result = agent._normalize_action({"action_type": "calendar.update_event", "params": {"summary": "Updated"}}, ctx)
        assert result is not None
        assert result.params["event_id"] == 99

    def test_handles_missing_params(self, agent):
        ctx = AssistantPageContext(page="calendar")
        result = agent._normalize_action({"action_type": "calendar.create_event"}, ctx)
        assert result is not None
        assert result.params == {}


# ── _format_preview_reply / _format_commit_reply ─────────────────────────

class TestFormatReplies:
    def test_format_preview_reply_with_actions(self, agent):
        actions = [
            AssistantAction(action_type="calendar.create_event", params={"summary": "Standup"}),
        ]
        reply = agent._format_preview_reply("calendar", actions)
        assert "Standup" in reply
        assert "Confirm" in reply

    def test_format_preview_reply_empty_calendar(self, agent):
        assert "more detail" in agent._format_preview_reply("calendar", []).lower()

    def test_format_preview_reply_empty_projects(self, agent):
        assert "more detail" in agent._format_preview_reply("projects", []).lower()

    def test_format_commit_reply_success(self, agent):
        from app.services.monet_assistant import ContextualExecutionResult
        r = ContextualExecutionResult(calendar_created=1, todo_items=[{"text": "test"}], tools_used=["calendar.create_event"])
        reply = agent._format_commit_reply(r)
        assert "calendar event" in reply.lower()
        assert "todo" in reply.lower()

    def test_format_commit_reply_no_actions(self, agent):
        from app.services.monet_assistant import ContextualExecutionResult
        assert "no actions" in agent._format_commit_reply(ContextualExecutionResult()).lower()

    def test_format_commit_reply_with_errors(self, agent):
        from app.services.monet_assistant import ContextualExecutionResult
        r = ContextualExecutionResult(errors=["calendar.create_event: Missing summary"])
        assert "could not" in agent._format_commit_reply(r).lower()

    def test_format_commit_reply_partial_with_errors(self, agent):
        from app.services.monet_assistant import ContextualExecutionResult
        r = ContextualExecutionResult(calendar_created=1, errors=["note: Missing title"], tools_used=["calendar.create_event"])
        reply = agent._format_commit_reply(r)
        assert "calendar event" in reply.lower()
        assert "failed" in reply.lower()


# ── _parse_dt ─────────────────────────────────────────────────────────────

class TestParseDt:
    def test_parses_iso_string(self, agent):
        from datetime import datetime
        result = agent._parse_dt("2026-03-20T10:00:00Z")
        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_returns_none_for_none(self, agent):
        assert agent._parse_dt(None) is None

    def test_returns_none_for_empty_string(self, agent):
        assert agent._parse_dt("") is None

    def test_returns_none_for_invalid_string(self, agent):
        assert agent._parse_dt("not a date") is None

    def test_passes_through_datetime(self, agent):
        from datetime import datetime
        dt = datetime(2026, 3, 20, 10, 0)
        assert agent._parse_dt(dt) is dt


# ── _parse_tags ───────────────────────────────────────────────────────────

class TestParseTags:
    def test_parses_list_of_strings(self, agent):
        assert agent._parse_tags(["work", "urgent"]) == ["work", "urgent"]

    def test_returns_empty_for_non_list(self, agent):
        assert agent._parse_tags("not a list") == []
        assert agent._parse_tags(None) == []
        assert agent._parse_tags(42) == []

    def test_deduplicates_tags(self, agent):
        assert agent._parse_tags(["work", "work", "urgent"]) == ["work", "urgent"]

    def test_truncates_long_tags(self, agent):
        assert len(agent._parse_tags(["a" * 100])[0]) == 64

    def test_skips_empty_tags(self, agent):
        assert agent._parse_tags(["", "  ", "valid"]) == ["valid"]
