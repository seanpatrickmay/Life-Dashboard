from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime
from dataclasses import dataclass, field
from textwrap import dedent
from typing import Any, Protocol
from uuid import uuid4

from google.genai.types import GenerateContentConfig

try:
    from google.genai.types import HttpOptions
except ImportError:  # pragma: no cover - google-genai shim
    HttpOptions = None  # type: ignore[assignment]

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.clients.genai_client import build_genai_client
from app.schemas.todos import TodoItemResponse
from app.services.claude_nutrition_agent import ClaudeNutritionAgent
from app.services.claude_todo_agent import ClaudeTodoAgent
from app.services.monet_context_service import MonetContextBuilder


def _json_fallback(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return str(value)


@dataclass
class AssistantToolSpec:
    id: str
    description: str
    input_schema: dict[str, Any]

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.id,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class AssistantTool(Protocol):
    spec: AssistantToolSpec

    async def run(self, user_id: int, args: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass
class ToolCall:
    tool_id: str
    args: dict[str, Any]


@dataclass
class RouterDecision:
    reply_mode: str
    narrative_intent: str
    tool_calls: list[ToolCall]

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "reply_mode": self.reply_mode,
            "narrative_intent": self.narrative_intent,
            "tool_calls": [
                {"tool_id": call.tool_id, "args": call.args} for call in self.tool_calls
            ],
        }


@dataclass
class ToolExecutionResult:
    nutrition_entries: list[dict[str, Any]] = field(default_factory=list)
    todo_items: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    raw_results: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssistantResult:
    session_id: str
    reply: str
    nutrition_entries: list[dict[str, Any]]
    todo_items: list[dict[str, Any]]
    tools_used: list[str]


class NutritionLogTool:
    spec = AssistantToolSpec(
        id="nutrition.log_intake",
        description="Parse the user's natural language meal description and log foods into the nutrition tracker.",
        input_schema={
            "message": "string — required. The verbatim text describing foods eaten."
        },
    )

    def __init__(self, session: AsyncSession) -> None:
        self.agent = ClaudeNutritionAgent(session)

    async def run(self, user_id: int, args: dict[str, Any]) -> dict[str, Any]:
        message = (args.get("message") or "").strip()
        if not message:
            return {"reply": "No food description provided.", "logged_entries": []}
        response = await self.agent.respond(user_id, message)
        return {"reply": response.reply, "logged_entries": response.logged_entries}


class TodoCreateTool:
    spec = AssistantToolSpec(
        id="todos.create_items",
        description="Turn user instructions into actionable to-do items and store them in the lily pad list.",
        input_schema={
            "message": "string — required. User text describing the tasks that need tracking."
        },
    )

    def __init__(self, session: AsyncSession) -> None:
        self.agent = ClaudeTodoAgent(session)

    async def run(self, user_id: int, args: dict[str, Any]) -> dict[str, Any]:
        message = (args.get("message") or "").strip()
        if not message:
            return {"reply": "No task description provided.", "items": []}
        response = await self.agent.respond(user_id, message)
        return {
            "reply": response.reply,
            "items": response.items,
            "raw_payload": response.raw_payload,
        }


class MonetToolRegistry:
    """Registers available tool adapters for the assistant."""

    def __init__(self, session: AsyncSession) -> None:
        self._tools: dict[str, AssistantTool] = {
            NutritionLogTool.spec.id: NutritionLogTool(session),
            TodoCreateTool.spec.id: TodoCreateTool(session),
        }

    def prompt_specs(self) -> list[dict[str, Any]]:
        return [tool.spec.to_prompt_dict() for tool in self._tools.values()]

    def get(self, tool_id: str) -> AssistantTool | None:
        return self._tools.get(tool_id)


class MonetAssistantAgent:
    """High-level orchestrator that routes Monet chat messages to tools and composes replies."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        http_options = HttpOptions(api_version="v1") if HttpOptions else None
        self.client = build_genai_client(http_options=http_options)
        self.model_name = settings.vertex_model_name or "gemini-2.5-flash"
        self.context_builder = MonetContextBuilder(session)
        self.tool_registry = MonetToolRegistry(session)

    async def respond(
        self,
        user_id: int,
        *,
        message: str,
        session_id: str | None = None,
        window_days: int = 14,
        time_zone: str | None = None,
    ) -> AssistantResult:
        session_key = session_id or str(uuid4())
        context = await self.context_builder.build_context(
            user_id, window_days, time_zone=time_zone
        )
        logger.debug("[assistant] context built window=%s keys=%s", window_days, context.keys())
        decision = await self._route_message(message, context)
        logger.info(
            "[assistant] router decision mode=%s tools=%s",
            decision.reply_mode,
            [call.tool_id for call in decision.tool_calls],
        )
        tool_results = await self._execute_tools(user_id, decision.tool_calls)
        reply = await self._compose_reply(message, context, decision, tool_results)
        return AssistantResult(
            session_id=session_key,
            reply=reply,
            nutrition_entries=tool_results.nutrition_entries,
            todo_items=tool_results.todo_items,
            tools_used=tool_results.tools_used,
        )

    async def _route_message(self, message: str, context: dict[str, Any]) -> RouterDecision:
        tools = self.tool_registry.prompt_specs()
        payload = {
            "message": message,
            "available_tools": tools,
            "context": context,
        }
        prompt = dedent(
            f"""
            You are Monet, an AI coach who can answer questions directly or call specialized tools.
            Decide whether the user message requires logging nutrition, creating to-dos, both, or neither.
            Only call tools when the user explicitly asks to log food or track tasks.
            Respond strictly with JSON in the shape:
            {{"reply_mode":"respond_only|respond_and_call_tools","narrative_intent":"...", "tool_calls":[{{"tool_id":"...", "args":{{...}}}}]}}
            DATA:
            {json.dumps(payload, ensure_ascii=False, default=_json_fallback)}
            """
        )
        text = await self._call_model(prompt)
        plan_data = self._safe_parse_json(text)
        if not isinstance(plan_data, dict):
            logger.warning("[assistant] router returned invalid payload, defaulting to respond_only")
            return RouterDecision("respond_only", "Reply to the user directly.", [])

        reply_mode = plan_data.get("reply_mode") or "respond_only"
        narrative_intent = plan_data.get("narrative_intent") or "Respond helpfully."
        calls: list[ToolCall] = []
        for raw_call in plan_data.get("tool_calls") or []:
            if not isinstance(raw_call, dict):
                continue
            tool_id = str(raw_call.get("tool_id") or "").strip()
            if not tool_id:
                continue
            args = raw_call.get("args") or {}
            if not isinstance(args, dict):
                args = {}
            calls.append(ToolCall(tool_id=tool_id, args=args))

        return RouterDecision(reply_mode=reply_mode, narrative_intent=narrative_intent, tool_calls=calls)

    async def _execute_tools(self, user_id: int, calls: list[ToolCall]) -> ToolExecutionResult:
        results = ToolExecutionResult()
        for call in calls:
            tool = self.tool_registry.get(call.tool_id)
            if not tool:
                logger.warning("[assistant] unknown tool requested: %s", call.tool_id)
                continue
            tool_output = await tool.run(user_id, call.args)
            results.tools_used.append(call.tool_id)
            results.raw_results[call.tool_id] = tool_output
            if call.tool_id == NutritionLogTool.spec.id:
                entries = tool_output.get("logged_entries") or []
                if isinstance(entries, list):
                    results.nutrition_entries.extend(entries)
            elif call.tool_id == TodoCreateTool.spec.id:
                items = tool_output.get("items") or []
                if isinstance(items, list):
                    results.todo_items.extend(
                        [self._serialize_todo(item) for item in items]
                    )
        return results

    async def _compose_reply(
        self,
        message: str,
        context: dict[str, Any],
        decision: RouterDecision,
        tool_results: ToolExecutionResult,
    ) -> str:
        summary = {
            "message": message,
            "context": context,
            "router_decision": decision.to_prompt_dict(),
            "tool_results": {
                "tools_used": tool_results.tools_used,
                "nutrition_entries": tool_results.nutrition_entries,
                "todo_items": tool_results.todo_items,
            },
        }
        prompt = dedent(
            f"""
            You are Monet, the user's steady companion.
            Given the structured context and actions taken, reply in 1-3 sentences.
            Mention any foods logged or todos created.
            Only reference health metrics, sleep, readiness, or 14-day trends if the user explicitly asked for insights or a summary.
            Otherwise, do not introduce unrelated context; use context only to resolve ambiguities in the user's request.
            If reply_mode is respond_and_call_tools, focus on summarizing the tool outputs.
            Never return JSON—just the natural-language reply.
            Example:
            User: "I ate a banana and remind me to call the bank tomorrow."
            Reply: "Logged the banana and added a reminder to call the bank tomorrow."
            DATA:
            {json.dumps(summary, ensure_ascii=False, default=_json_fallback)}
            """
        )
        text = await self._call_model(prompt)
        reply = text.strip()
        if not reply:
            reply = "I'm here whenever you're ready to continue."
        return reply

    async def _call_model(self, prompt: str) -> str:
        def _invoke() -> str:
            config = GenerateContentConfig(temperature=0.2)
            logger.debug("[assistant] model invocation payload chars=%s", len(prompt))
            result = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            return result.text or ""

        return await asyncio.to_thread(_invoke)

    def _safe_parse_json(self, text: str) -> dict[str, Any] | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
        return None

    def _serialize_todo(self, item: Any) -> dict[str, Any]:
        try:
            return TodoItemResponse.model_validate(item).model_dump()
        except Exception:  # pragma: no cover - schema fallback
            return {
                "id": getattr(item, "id", None),
                "text": getattr(item, "text", ""),
                "completed": getattr(item, "completed", False),
                "deadline_utc": getattr(item, "deadline_utc", None),
                "is_overdue": False,
                "created_at": getattr(item, "created_at", None),
                "updated_at": getattr(item, "updated_at", None),
            }
