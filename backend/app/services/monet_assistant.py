from __future__ import annotations

import json
from datetime import date, datetime
from dataclasses import dataclass, field
from textwrap import dedent
from typing import Any, Protocol
from uuid import uuid4

from dateutil import parser as date_parser
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.calendar import CalendarEvent, GoogleCalendar
from app.db.repositories.project_note_repository import ProjectNoteRepository
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.todo_repository import TodoRepository
from app.clients.openai_client import OpenAIResponsesClient
from app.schemas.assistant import AssistantAction, AssistantPageContext
from app.schemas.llm_outputs import AssistantActionPlanOutput, AssistantRouterOutput
from app.schemas.todos import TodoItemResponse
from app.services.claude_nutrition_agent import NutritionAssistantAgent
from app.services.claude_todo_agent import TodoAssistantAgent
from app.services.google_calendar_event_service import GoogleCalendarEventService
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
    requires_confirmation: bool = False
    proposed_actions: list[AssistantAction] = field(default_factory=list)
    action_plan_id: str | None = None


@dataclass
class ContextualExecutionResult:
    tools_used: list[str] = field(default_factory=list)
    todo_items: list[dict[str, Any]] = field(default_factory=list)
    created_notes: int = 0
    updated_notes: int = 0
    calendar_created: int = 0
    calendar_updated: int = 0
    errors: list[str] = field(default_factory=list)


class NutritionLogTool:
    spec = AssistantToolSpec(
        id="nutrition.log_intake",
        description="Parse the user's natural language meal description and log foods into the nutrition tracker.",
        input_schema={
            "message": "string — required. The verbatim text describing foods eaten."
        },
    )

    def __init__(self, session: AsyncSession) -> None:
        self.agent = NutritionAssistantAgent(session)

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
        self.agent = TodoAssistantAgent(session)

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
        self.client = OpenAIResponsesClient()
        self.context_builder = MonetContextBuilder(session)
        self.tool_registry = MonetToolRegistry(session)

    async def respond(
        self,
        user_id: int,
        *,
        message: str,
        session_id: str | None = None,
        window_days: int = 7,
        time_zone: str | None = None,
        page_context: AssistantPageContext | None = None,
        execution_mode: str = "auto",
        proposed_actions: list[AssistantAction] | None = None,
    ) -> AssistantResult:
        session_key = session_id or str(uuid4())
        if page_context is not None and execution_mode in {"preview", "commit"}:
            if execution_mode == "preview":
                planned_actions = await self._plan_contextual_actions(
                    message=message,
                    page_context=page_context,
                    time_zone=time_zone,
                )
                return AssistantResult(
                    session_id=session_key,
                    reply=self._format_preview_reply(page_context.page, planned_actions),
                    nutrition_entries=[],
                    todo_items=[],
                    tools_used=[],
                    requires_confirmation=bool(planned_actions),
                    proposed_actions=planned_actions,
                    action_plan_id=str(uuid4()) if planned_actions else None,
                )

            execution = await self._execute_contextual_actions(
                user_id=user_id,
                page_context=page_context,
                actions=proposed_actions or [],
                time_zone=time_zone,
            )
            return AssistantResult(
                session_id=session_key,
                reply=self._format_commit_reply(execution),
                nutrition_entries=[],
                todo_items=execution.todo_items,
                tools_used=execution.tools_used,
                requires_confirmation=False,
                proposed_actions=[],
                action_plan_id=None,
            )

        try:
            context = await self.context_builder.build_context(
                user_id,
                window_days,
                time_zone=time_zone,
                page_context=page_context,
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
        except Exception as exc:  # noqa: BLE001
            logger.exception("[assistant] respond failed for user %s: %s", user_id, exc)
            return AssistantResult(
                session_id=session_key,
                reply="Something went wrong on my end — give it another try in a moment.",
                nutrition_entries=[],
                todo_items=[],
                tools_used=[],
            )

    async def _plan_contextual_actions(
        self,
        *,
        message: str,
        page_context: AssistantPageContext,
        time_zone: str | None,
    ) -> list[AssistantAction]:
        payload = {
            "message": message,
            "time_zone": time_zone or "UTC",
            "page_context": page_context.model_dump(),
            "supported_actions": [
                {
                    "action_type": "calendar.create_event",
                    "required_params": ["summary", "start_time", "end_time"],
                    "optional_params": ["is_all_day"],
                },
                {
                    "action_type": "calendar.update_event",
                    "required_params": ["event_id"],
                    "optional_params": ["summary", "start_time", "end_time", "is_all_day", "scope"],
                },
                {
                    "action_type": "projects.create_todo",
                    "required_params": ["text"],
                    "optional_params": ["project_id", "deadline_utc", "deadline_is_date_only"],
                },
                {
                    "action_type": "projects.create_note",
                    "required_params": ["title"],
                    "optional_params": ["project_id", "body_markdown", "tags", "pinned"],
                },
                {
                    "action_type": "projects.update_note",
                    "required_params": ["note_id"],
                    "optional_params": ["project_id", "title", "body_markdown", "tags", "pinned", "archived"],
                },
            ],
        }
        prompt = dedent(
            f"""
            You convert page-specific user intent into structured actions.
            Rules:
            - On page "calendar", only output calendar.* actions.
            - On page "projects", only output projects.* actions.
            - If required fields are missing, output no actions.
            - Use selected ids in page_context when user implies "this/selected/current".
            - Output strict JSON only:
            {{"actions":[{{"action_type":"...", "params":{{...}}}}]}}
            DATA:
            {json.dumps(payload, ensure_ascii=False, default=_json_fallback)}
            """
        )
        result = await self.client.generate_json(
            prompt,
            response_model=AssistantActionPlanOutput,
            temperature=0.2,
        )
        raw_actions = [item.model_dump() for item in result.data.actions]
        actions: list[AssistantAction] = []
        for raw_action in raw_actions or []:
            if not isinstance(raw_action, dict):
                continue
            normalized = self._normalize_action(raw_action, page_context)
            if normalized is not None:
                actions.append(normalized)
        return actions

    async def _execute_contextual_actions(
        self,
        *,
        user_id: int,
        page_context: AssistantPageContext,
        actions: list[AssistantAction],
        time_zone: str | None,
    ) -> ContextualExecutionResult:
        result = ContextualExecutionResult()
        project_repo = ProjectRepository(self.session)
        note_repo = ProjectNoteRepository(self.session)
        todo_repo = TodoRepository(self.session)
        calendar_service = GoogleCalendarEventService(self.session)

        for action in actions:
            try:
                if action.action_type == "projects.create_todo":
                    project_id = int(
                        action.params.get("project_id")
                        or (page_context.selected_entity.project_id if page_context.selected_entity else 0)
                        or (await project_repo.ensure_inbox_project(user_id)).id
                    )
                    project = await project_repo.get_for_user(user_id, project_id)
                    if project is None:
                        raise ValueError("Project not found for todo creation.")
                    todo = await todo_repo.create_one(
                        user_id=user_id,
                        project_id=project_id,
                        text=str(action.params.get("text") or "").strip(),
                        deadline=self._parse_dt(action.params.get("deadline_utc")),
                        deadline_is_date_only=bool(action.params.get("deadline_is_date_only", False)),
                    )
                    await self.session.flush()
                    await self.session.commit()
                    result.todo_items.append(self._serialize_todo(todo))
                    result.tools_used.append(action.action_type)

                elif action.action_type == "projects.create_note":
                    project_id = int(
                        action.params.get("project_id")
                        or (page_context.selected_entity.project_id if page_context.selected_entity else 0)
                    )
                    if not project_id:
                        raise ValueError("Select a project before creating a note.")
                    project = await project_repo.get_for_user(user_id, project_id)
                    if project is None:
                        raise ValueError("Project not found for note creation.")
                    title = str(action.params.get("title") or "").strip()
                    if not title:
                        raise ValueError("Note title is required.")
                    await note_repo.create_one(
                        user_id=user_id,
                        project_id=project_id,
                        title=title,
                        body_markdown=str(action.params.get("body_markdown") or ""),
                        tags=self._parse_tags(action.params.get("tags")),
                        pinned=bool(action.params.get("pinned", False)),
                    )
                    await self.session.commit()
                    result.created_notes += 1
                    result.tools_used.append(action.action_type)

                elif action.action_type == "projects.update_note":
                    note_id = int(
                        action.params.get("note_id")
                        or (page_context.selected_entity.note_id if page_context.selected_entity else 0)
                    )
                    if not note_id:
                        raise ValueError("Note id is required to update a note.")
                    note = await note_repo.get_for_user(user_id=user_id, note_id=note_id)
                    if note is None:
                        raise ValueError("Project note not found.")
                    project_id = int(
                        action.params.get("project_id")
                        or note.project_id
                        or (page_context.selected_entity.project_id if page_context.selected_entity else 0)
                    )
                    project = await project_repo.get_for_user(user_id, project_id)
                    if project is None or note.project_id != project.id:
                        raise ValueError("Cannot update note outside its project.")
                    if "title" in action.params and action.params["title"] is not None:
                        title = str(action.params.get("title") or "").strip()
                        if not title:
                            raise ValueError("Note title cannot be empty.")
                        note.title = title
                    if "body_markdown" in action.params and action.params["body_markdown"] is not None:
                        note.body_markdown = str(action.params["body_markdown"])
                    if "tags" in action.params:
                        note.tags = self._parse_tags(action.params.get("tags"))
                    if "pinned" in action.params:
                        note.pinned = bool(action.params.get("pinned"))
                    if "archived" in action.params:
                        note.archived = bool(action.params.get("archived"))
                    await self.session.flush()
                    await self.session.commit()
                    result.updated_notes += 1
                    result.tools_used.append(action.action_type)

                elif action.action_type == "calendar.create_event":
                    summary = str(action.params.get("summary") or "").strip()
                    start_time = self._parse_dt(action.params.get("start_time"))
                    end_time = self._parse_dt(action.params.get("end_time"))
                    if not summary or not start_time or not end_time:
                        raise ValueError("Calendar event requires summary, start_time, and end_time.")
                    if end_time <= start_time:
                        raise ValueError("Calendar event end_time must be after start_time.")
                    await calendar_service.create_event_in_life_dashboard(
                        user_id,
                        summary=summary,
                        start_time=start_time,
                        end_time=end_time,
                        is_all_day=bool(action.params.get("is_all_day", False)),
                    )
                    result.calendar_created += 1
                    result.tools_used.append(action.action_type)

                elif action.action_type == "calendar.update_event":
                    event_id = int(
                        action.params.get("event_id")
                        or (page_context.selected_entity.calendar_event_id if page_context.selected_entity else 0)
                    )
                    if not event_id:
                        raise ValueError("Select an event before editing it.")
                    stmt = (
                        select(CalendarEvent, GoogleCalendar)
                        .join(GoogleCalendar, CalendarEvent.calendar_id == GoogleCalendar.id)
                        .where(CalendarEvent.id == event_id, CalendarEvent.user_id == user_id)
                    )
                    query = await self.session.execute(stmt)
                    row = query.first()
                    if not row:
                        raise ValueError("Calendar event not found.")
                    event, calendar = row
                    await calendar_service.update_event(
                        event,
                        calendar,
                        summary=action.params.get("summary"),
                        start_time=self._parse_dt(action.params.get("start_time")),
                        end_time=self._parse_dt(action.params.get("end_time")),
                        scope=str(
                            action.params.get("scope")
                            or (
                                page_context.selected_entity.recurrence_scope
                                if page_context.selected_entity
                                else "occurrence"
                            )
                            or "occurrence"
                        ),
                        time_zone=time_zone,
                        is_all_day=bool(action.params["is_all_day"])
                        if "is_all_day" in action.params
                        else None,
                    )
                    result.calendar_updated += 1
                    result.tools_used.append(action.action_type)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[assistant] contextual action failed type={} err={}", action.action_type, exc)
                result.errors.append(f"{action.action_type}: {exc}")
        return result

    def _normalize_action(
        self, raw_action: dict[str, Any], page_context: AssistantPageContext
    ) -> AssistantAction | None:
        action_type = str(raw_action.get("action_type") or "").strip()
        if action_type not in {
            "calendar.create_event",
            "calendar.update_event",
            "projects.create_todo",
            "projects.create_note",
            "projects.update_note",
        }:
            return None
        if page_context.page == "calendar" and not action_type.startswith("calendar."):
            return None
        if page_context.page == "projects" and not action_type.startswith("projects."):
            return None
        params = raw_action.get("params")
        if not isinstance(params, dict):
            params = {}
        normalized: dict[str, Any] = dict(params)
        if action_type == "calendar.update_event" and "event_id" not in normalized:
            if page_context.selected_entity and page_context.selected_entity.calendar_event_id:
                normalized["event_id"] = page_context.selected_entity.calendar_event_id
        if action_type == "projects.create_todo" and "project_id" not in normalized:
            if page_context.selected_entity and page_context.selected_entity.project_id:
                normalized["project_id"] = page_context.selected_entity.project_id
        if action_type in {"projects.create_note", "projects.update_note"}:
            if "project_id" not in normalized and page_context.selected_entity and page_context.selected_entity.project_id:
                normalized["project_id"] = page_context.selected_entity.project_id
            if action_type == "projects.update_note" and "note_id" not in normalized:
                if page_context.selected_entity and page_context.selected_entity.note_id:
                    normalized["note_id"] = page_context.selected_entity.note_id
        return AssistantAction(action_type=action_type, params=normalized)

    def _format_preview_reply(self, page: str, actions: list[AssistantAction]) -> str:
        if not actions:
            if page == "calendar":
                return "I need one more detail before acting, like the event title and time range or which event to edit."
            return "I need a bit more detail, like which note to edit or the todo/note content to add."
        lines = []
        for action in actions:
            if action.action_type == "calendar.create_event":
                lines.append(
                    f"Create event \"{action.params.get('summary', 'Untitled')}\""
                )
            elif action.action_type == "calendar.update_event":
                lines.append("Update selected calendar event")
            elif action.action_type == "projects.create_todo":
                lines.append(f"Add todo \"{action.params.get('text', '')}\"")
            elif action.action_type == "projects.create_note":
                lines.append(f"Create note \"{action.params.get('title', '')}\"")
            elif action.action_type == "projects.update_note":
                lines.append("Update selected project note")
        return "I can do this next:\n- " + "\n- ".join(lines) + "\nConfirm to run these actions."

    def _format_commit_reply(self, result: ContextualExecutionResult) -> str:
        parts: list[str] = []
        if result.calendar_created:
            parts.append(f"created {result.calendar_created} calendar event(s)")
        if result.calendar_updated:
            parts.append(f"updated {result.calendar_updated} calendar event(s)")
        if result.todo_items:
            parts.append(f"added {len(result.todo_items)} todo item(s)")
        if result.created_notes:
            parts.append(f"created {result.created_notes} note(s)")
        if result.updated_notes:
            parts.append(f"updated {result.updated_notes} note(s)")
        if not parts and not result.errors:
            return "No actions were executed."
        if result.errors and not parts:
            return "I could not apply those actions. " + "; ".join(result.errors)
        if result.errors:
            return "Done: " + ", ".join(parts) + f". Some actions failed: {'; '.join(result.errors)}"
        return "Done: " + ", ".join(parts) + "."

    def _parse_dt(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return date_parser.isoparse(text)
        except Exception:
            return None

    def _parse_tags(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        tags: list[str] = []
        for raw_tag in value:
            text = str(raw_tag).strip()
            if text and text not in tags:
                tags.append(text[:64])
        return tags

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

            WHEN TO CALL TOOLS:
            - Call todos.create_items when the user asks to track, remember, add, or create a task — even implicitly.
              Examples: "remind me to ...", "I need to ...", "add ... to my list", "don't let me forget ...", "todo: ..."
            - Call nutrition.log_intake when the user describes food they ate or want to log.
            - When in doubt about whether the user wants a todo created, CALL THE TOOL. It is better to create a task
              the user can delete than to silently ignore their request.

            Respond strictly with JSON in the shape:
            {{"reply_mode":"respond_only|respond_and_call_tools","narrative_intent":"...", "tool_calls":[{{"tool_id":"...", "args":{{...}}}}]}}
            DATA:
            {json.dumps(payload, ensure_ascii=False, default=_json_fallback)}
            """
        )
        try:
            result = await self.client.generate_json(
                prompt,
                response_model=AssistantRouterOutput,
                temperature=0.2,
            )
        except Exception:
            logger.warning("[assistant] router returned invalid payload, defaulting to respond_only")
            return RouterDecision("respond_only", "Reply to the user directly.", [])

        reply_mode = result.data.reply_mode or "respond_only"
        narrative_intent = result.data.narrative_intent or "Respond helpfully."
        calls: list[ToolCall] = []
        for raw_call in result.data.tool_calls:
            tool_id = raw_call.tool_id.strip()
            if not tool_id:
                continue
            calls.append(ToolCall(tool_id=tool_id, args=dict(raw_call.args)))

        return RouterDecision(reply_mode=reply_mode, narrative_intent=narrative_intent, tool_calls=calls)

    async def _execute_tools(self, user_id: int, calls: list[ToolCall]) -> ToolExecutionResult:
        results = ToolExecutionResult()
        for call in calls:
            tool = self.tool_registry.get(call.tool_id)
            if not tool:
                logger.warning("[assistant] unknown tool requested: %s", call.tool_id)
                continue
            try:
                tool_output = await tool.run(user_id, call.args)
            except Exception as exc:  # noqa: BLE001
                logger.exception("[assistant] tool %s failed: %s", call.tool_id, exc)
                tool_output = {"error": str(exc)}
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

            CRITICAL RULE: Only claim you performed actions that actually appear in tool_results.
            - If tool_results.todo_items is empty, do NOT say you added, created, or tracked any task.
            - If tool_results.nutrition_entries is empty, do NOT say you logged any food.
            - If no tools were used (tools_used is empty), do NOT imply you took any action.
            When no action was taken but the user seemed to request one, say so honestly:
            "I wasn't able to create that task — could you try rephrasing?"

            Only reference health metrics, sleep, readiness, or 14-day trends if the user explicitly asked for insights or a summary.
            Otherwise, do not introduce unrelated context; use context only to resolve ambiguities in the user's request.
            If reply_mode is respond_and_call_tools, focus on summarizing the tool outputs.
            Never return JSON—just the natural-language reply.
            Example:
            User: "I ate a banana and remind me to call the bank tomorrow."
            Reply (with tool_results showing both): "Logged the banana and added a reminder to call the bank tomorrow."
            DATA:
            {json.dumps(summary, ensure_ascii=False, default=_json_fallback)}
            """
        )
        result = await self.client.generate_text(prompt, temperature=0.2)
        reply = result.text.strip()
        if not reply:
            reply = "I'm here whenever you're ready to continue."
        return reply

    def _serialize_todo(self, item: Any) -> dict[str, Any]:
        try:
            return TodoItemResponse.model_validate(item).model_dump()
        except Exception:  # pragma: no cover - schema fallback
            return {
                "id": getattr(item, "id", None),
                "project_id": getattr(item, "project_id", None),
                "text": getattr(item, "text", ""),
                "completed": getattr(item, "completed", False),
                "deadline_utc": getattr(item, "deadline_utc", None),
                "deadline_is_date_only": getattr(item, "deadline_is_date_only", False),
                "time_horizon": getattr(item, "time_horizon", "this_week"),
                "is_overdue": False,
                "created_at": getattr(item, "created_at", None),
                "updated_at": getattr(item, "updated_at", None),
            }
