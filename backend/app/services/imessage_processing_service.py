"""Process synced iMessages into workspace knowledge, todos, calendar, and journal."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from inspect import signature
from typing import Any

from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.openai_client import OpenAIResponsesClient
from app.db.models.imessage import (
    IMessageActionAudit,
    IMessageConversation,
    IMessageMessage,
    IMessageProcessingRun,
)
from app.db.models.calendar import CalendarEvent
from app.db.models.journal import JournalEntry
from app.db.models.project import Project
from app.db.models.todo import TodoItem
from app.db.repositories.project_repository import ProjectRepository
from app.db.repositories.todo_repository import TodoRepository
from app.prompts import (
    IMESSAGE_ACTION_DEDUP_PROMPT,
    IMESSAGE_ACTION_EXTRACTION_PROMPT,
    IMESSAGE_ACTION_JUDGE_PROMPT,
    IMESSAGE_CALENDAR_EXTRACTION_PROMPT,
    IMESSAGE_PAGE_MERGE_PROMPT,
    IMESSAGE_PAGE_SELECTION_PROMPT,
    IMESSAGE_PROJECT_INFERENCE_PROMPT,
)
from app.schemas.llm_outputs import (
    IMessageActionExtractionOutput,
    IMessageActionJudgeOutput,
    IMessageCalendarExtractionOutput,
    IMessageDedupDecisionOutput,
    IMessagePageMergeOutput,
    IMessagePageSelectionOutput,
    IMessageProjectInferenceOutput,
)
from app.services.google_calendar_event_service import GoogleCalendarEventService
from app.services.imessage_utils import (
    ProjectCatalogEntry,
    ProjectGuess,
    content_tokens,
    conversation_display_name,
    derive_project_aliases,
    infer_project_match,
    looks_like_completion,
    normalize_message_text,
    should_split_message_cluster,
    stable_fingerprint,
)
from app.services.journal_service import JournalService
from app.services.todo_accomplishment_agent import TodoAccomplishmentAgent
from app.services.workspace_service import WorkspaceService
from app.utils.timezone import resolve_time_zone


PROJECT_CONFIDENCE_THRESHOLD = 0.72
TODO_MATCH_THRESHOLD = 0.62
MAX_PENDING_MESSAGES = 250
MAX_CLUSTER_MESSAGES = 20
MAX_CLUSTER_GAP = timedelta(hours=6)
PROJECT_ROUTER_MIN_CONFIDENCE = 0.32
PROJECT_ROUTER_SKIP_CONFIDENCE = 0.88
PROJECT_ROUTER_MARGIN = 0.18
MAX_DEDUP_CANDIDATES = 8
_HANDLE_LIKE_RE = re.compile(r"@|\d{7,}")
_LEADING_PRONOUN_RE = re.compile(r"^(?:i|we)\s+", re.IGNORECASE)
_TODO_PHRASE_RE = re.compile(
    r"(?:^|\b)(?:i need to|i have to|i should|i will|i'll|i gotta|need to|have to|remember to|remind me to|don't let me forget to|can you|could you|please)\s+(.+)$",
    re.IGNORECASE,
)
_SEND_TARGET_RE = re.compile(r"\bsend\s+(.+?)\s+to\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)", re.IGNORECASE)
_ASK_TARGET_RE = re.compile(r"\bask\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(about|for|to)\s+(.+)$", re.IGNORECASE)
_MEET_WITH_RE = re.compile(r"\bmeet(?:ing)?\s+(?:with\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:to|for)\s+(.+)$", re.IGNORECASE)
_WATCH_RE = re.compile(r"\b(?:decided to watch|watch(?:ing)?|watched)\s+(.+)$", re.IGNORECASE)
_JOURNAL_RECAP_RE = re.compile(
    r"^(?:i|we)\s+(talked to|talked with|had a call with|called|met with|hung out with|decided to watch|watched|saw|planned|booked|submitted|sent|went|worked on|played|decided)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class MessageCluster:
    conversation: IMessageConversation
    messages: list[IMessageMessage]


@dataclass(slots=True)
class JudgmentOutcome:
    approved: bool
    reason: str


@dataclass(slots=True)
class DuplicateDecision:
    is_duplicate: bool
    reason: str
    matched_candidate_type: str | None = None
    matched_candidate_id: int | None = None


def cluster_messages(
    messages: list[IMessageMessage], *, max_cluster_messages: int = MAX_CLUSTER_MESSAGES
) -> list[MessageCluster]:
    by_conversation: dict[int, list[IMessageMessage]] = {}
    conversation_map: dict[int, IMessageConversation] = {}
    for message in messages:
        if not message.conversation_id or message.conversation is None:
            continue
        by_conversation.setdefault(message.conversation_id, []).append(message)
        conversation_map[message.conversation_id] = message.conversation

    clusters: list[MessageCluster] = []
    for conversation_id, items in by_conversation.items():
        ordered = sorted(
            items,
            key=lambda item: (
                item.sent_at_utc or datetime.min.replace(tzinfo=timezone.utc),
                item.id,
            ),
        )
        batch: list[IMessageMessage] = []
        for item in ordered:
            if batch:
                should_split, _ = should_split_message_cluster(
                    batch,
                    item,
                    max_cluster_messages=max_cluster_messages,
                    max_cluster_gap=MAX_CLUSTER_GAP,
                )
                if should_split:
                    clusters.append(
                        MessageCluster(
                            conversation=conversation_map[conversation_id],
                            messages=batch,
                        )
                    )
                    batch = []
            batch.append(item)
        if batch:
            clusters.append(
                MessageCluster(
                    conversation=conversation_map[conversation_id],
                    messages=batch,
                )
            )
    clusters.sort(
        key=lambda cluster: (
            cluster.messages[-1].sent_at_utc or datetime.min.replace(tzinfo=timezone.utc),
            cluster.messages[-1].id,
        )
    )
    return clusters


def choose_best_todo_match(
    *,
    candidate_text: str,
    todos: list[TodoItem],
) -> TodoItem | None:
    target = candidate_text.strip().lower()
    if not target:
        return None
    best: tuple[float, TodoItem | None] = (0.0, None)
    for todo in todos:
        score = SequenceMatcher(None, target, todo.text.lower()).ratio()
        if target in todo.text.lower():
            score += 0.2
        if score > best[0]:
            best = (score, todo)
    return best[1] if best[0] >= TODO_MATCH_THRESHOLD else None


class IMessageProcessingService:
    """Turns synced message clusters into durable dashboard artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.project_repo = ProjectRepository(session)
        self.todo_repo = TodoRepository(session)
        self.journal_service = JournalService(session)
        self.calendar_service = GoogleCalendarEventService(session)
        self.workspace_service = WorkspaceService(session)
        self.todo_accomplishment_agent = TodoAccomplishmentAgent(session)
        try:
            self.client = OpenAIResponsesClient()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[imessage] failed to initialize genai client: {}", exc)
            self.client = None

    async def process_new_messages(
        self,
        user_id: int,
        *,
        time_zone: str = "America/New_York",
        max_messages: int = MAX_PENDING_MESSAGES,
    ) -> IMessageProcessingRun:
        return await self.process_pending_messages(
            user_id=user_id,
            time_zone=time_zone,
            max_messages=max_messages,
        )

    async def process_pending_messages(
        self,
        *,
        user_id: int,
        time_zone: str = "America/New_York",
        max_messages: int = MAX_PENDING_MESSAGES,
    ) -> IMessageProcessingRun:
        run = IMessageProcessingRun(
            user_id=user_id,
            status="running",
            started_at_utc=datetime.now(timezone.utc),
        )
        self.session.add(run)
        await self.session.flush()

        try:
            projects = await self.project_repo.list_for_user(user_id, include_archived=False)
            project_catalog = await self._build_project_catalog(user_id=user_id, projects=projects)
            pending_messages = await self._load_pending_messages(user_id=user_id, max_messages=max_messages)
            run.messages_considered = len(pending_messages)
            if not pending_messages:
                run.status = "completed"
                run.completed_at_utc = datetime.now(timezone.utc)
                run.error_message = "No unprocessed messages."
                await self.session.commit()
                return run

            clusters = cluster_messages(pending_messages)
            for cluster in clusters:
                applied = await self._process_cluster(
                    run=run,
                    cluster=cluster,
                    project_catalog=project_catalog,
                    time_zone=time_zone,
                )
                run.clusters_processed += 1
                run.actions_applied += applied["applied"]
            run.status = "completed"
            run.completed_at_utc = datetime.now(timezone.utc)
            await self.session.commit()
            return run
        except Exception as exc:  # noqa: BLE001
            logger.exception("[imessage] processing failed: {}", exc)
            run.status = "error"
            run.completed_at_utc = datetime.now(timezone.utc)
            run.error_message = str(exc)
            await self.session.commit()
            return run

    async def preview_messages(
        self,
        *,
        user_id: int,
        time_zone: str = "America/New_York",
        max_messages: int = MAX_PENDING_MESSAGES,
        message_scope: str = "all",
        since_utc: datetime | None = None,
        conversation_id: int | None = None,
    ) -> dict[str, Any]:
        projects = await self.project_repo.list_for_user(user_id, include_archived=False)
        project_catalog = await self._build_project_catalog(user_id=user_id, projects=projects)
        preview_messages = await self._load_messages(
            user_id=user_id,
            max_messages=max_messages,
            message_scope=message_scope,
            since_utc=since_utc,
            conversation_id=conversation_id,
        )
        clusters = cluster_messages(preview_messages)

        cluster_previews: list[dict[str, Any]] = []
        total_suggested_actions = 0
        total_approved_actions = 0
        total_rejected_actions = 0
        for cluster in clusters:
            preview = await self._preview_cluster(
                cluster=cluster,
                project_catalog=project_catalog,
                time_zone=time_zone,
                user_id=user_id,
            )
            total_suggested_actions += int(preview["counts"]["suggested"])
            total_approved_actions += int(preview["counts"]["approved"])
            total_rejected_actions += int(preview["counts"]["rejected"])
            cluster_previews.append(preview)

        return {
            "summary": {
                "user_id": user_id,
                "time_zone": time_zone,
                "message_scope": message_scope,
                "messages_considered": len(preview_messages),
                "clusters_considered": len(cluster_previews),
                "suggested_actions": total_suggested_actions,
                "approved_actions": total_approved_actions,
                "rejected_actions": total_rejected_actions,
            },
            "clusters": cluster_previews,
        }

    async def _load_pending_messages(self, *, user_id: int, max_messages: int) -> list[IMessageMessage]:
        return await self._load_messages(
            user_id=user_id,
            max_messages=max_messages,
            message_scope="pending",
        )

    async def _load_messages(
        self,
        *,
        user_id: int,
        max_messages: int,
        message_scope: str,
        since_utc: datetime | None = None,
        conversation_id: int | None = None,
    ) -> list[IMessageMessage]:
        if message_scope not in {"pending", "processed", "all"}:
            raise ValueError(f"Unsupported message scope: {message_scope}")
        stmt = (
            select(IMessageMessage)
            .options(
                selectinload(IMessageMessage.conversation).selectinload(IMessageConversation.participants)
            )
            .where(IMessageMessage.user_id == user_id)
            .order_by(IMessageMessage.sent_at_utc.asc().nullslast(), IMessageMessage.id.asc())
        )
        if message_scope == "pending":
            stmt = stmt.where(IMessageMessage.processed_at_utc.is_(None))
        elif message_scope == "processed":
            stmt = stmt.where(IMessageMessage.processed_at_utc.is_not(None))
        if conversation_id is not None:
            stmt = stmt.where(IMessageMessage.conversation_id == conversation_id)
        if since_utc is not None:
            stmt = stmt.where(
                or_(
                    IMessageMessage.sent_at_utc >= since_utc,
                    (IMessageMessage.sent_at_utc.is_(None) & (IMessageMessage.created_at >= since_utc)),
                )
            )
        if max_messages > 0:
            stmt = stmt.limit(max_messages)
        result = await self.session.execute(stmt)
        messages = list(result.scalars().all())
        if not messages:
            return messages
        if max_messages <= 0:
            return messages
        return await self._extend_message_batch_with_conversation_tail(
            user_id=user_id,
            messages=messages,
            message_scope=message_scope,
            since_utc=since_utc,
            conversation_id=conversation_id,
        )

    async def _extend_message_batch_with_conversation_tail(
        self,
        *,
        user_id: int,
        messages: list[IMessageMessage],
        message_scope: str,
        since_utc: datetime | None = None,
        conversation_id: int | None = None,
    ) -> list[IMessageMessage]:
        last_message = messages[-1]
        if last_message.conversation_id is None or last_message.sent_at_utc is None:
            return messages

        trailing_batch = [
            item
            for item in messages
            if item.conversation_id == last_message.conversation_id
        ]
        if not trailing_batch:
            return messages

        stmt = (
            select(IMessageMessage)
            .options(
                selectinload(IMessageMessage.conversation).selectinload(IMessageConversation.participants)
            )
            .where(
                IMessageMessage.user_id == user_id,
                IMessageMessage.conversation_id == last_message.conversation_id,
                IMessageMessage.sent_at_utc.is_not(None),
                IMessageMessage.sent_at_utc >= last_message.sent_at_utc,
                IMessageMessage.id != last_message.id,
            )
            .order_by(IMessageMessage.sent_at_utc.asc(), IMessageMessage.id.asc())
            .limit(MAX_CLUSTER_MESSAGES)
        )
        if message_scope == "pending":
            stmt = stmt.where(IMessageMessage.processed_at_utc.is_(None))
        elif message_scope == "processed":
            stmt = stmt.where(IMessageMessage.processed_at_utc.is_not(None))
        if since_utc is not None:
            stmt = stmt.where(
                or_(
                    IMessageMessage.sent_at_utc >= since_utc,
                    (IMessageMessage.sent_at_utc.is_(None) & (IMessageMessage.created_at >= since_utc)),
                )
            )
        if conversation_id is not None:
            stmt = stmt.where(IMessageMessage.conversation_id == conversation_id)
        result = await self.session.execute(stmt)
        continuation = list(result.scalars().all())
        if not continuation:
            return messages

        existing_ids = {item.id for item in messages}
        extended = list(messages)
        rolling_cluster = list(trailing_batch)
        for candidate in continuation:
            if candidate.id in existing_ids:
                continue
            should_split, _ = should_split_message_cluster(
                rolling_cluster,
                candidate,
                max_cluster_messages=MAX_CLUSTER_MESSAGES,
                max_cluster_gap=MAX_CLUSTER_GAP,
            )
            if should_split:
                break
            extended.append(candidate)
            rolling_cluster.append(candidate)
            existing_ids.add(candidate.id)
        return extended

    async def _build_project_catalog(
        self,
        *,
        user_id: int,
        projects: list[Project],
    ) -> list[ProjectCatalogEntry]:
        catalog: list[ProjectCatalogEntry] = []
        for project in projects:
            aliases = list(derive_project_aliases(project.name))
            project_page = await self.workspace_service.find_project_page(user_id, project.id)
            if project_page is not None and project_page.title.strip():
                aliases.extend(derive_project_aliases(project_page.title))
            deduped_aliases: list[str] = []
            seen: set[str] = set()
            for alias in aliases:
                lowered = alias.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                deduped_aliases.append(alias)
            catalog.append(
                ProjectCatalogEntry(
                    name=project.name,
                    aliases=tuple(deduped_aliases),
                    notes=project.notes,
                )
            )
        return catalog

    async def _conversation_project_affinities(
        self,
        *,
        user_id: int,
        conversation_id: int,
    ) -> dict[str, float]:
        stmt = (
            select(Project.name, func.count(IMessageActionAudit.id))
            .join(Project, Project.id == IMessageActionAudit.project_id)
            .where(
                IMessageActionAudit.user_id == user_id,
                IMessageActionAudit.conversation_id == conversation_id,
                IMessageActionAudit.project_id.is_not(None),
                IMessageActionAudit.status == "applied",
            )
            .group_by(Project.name)
        )
        result = await self.session.execute(stmt)
        counts = {str(name): int(count or 0) for name, count in result.all()}
        if not counts:
            return {}
        max_count = max(counts.values()) or 1
        return {
            name: count / max_count
            for name, count in counts.items()
        }

    async def _process_cluster(
        self,
        *,
        run: IMessageProcessingRun,
        cluster: MessageCluster,
        project_catalog: list[ProjectCatalogEntry],
        time_zone: str,
    ) -> dict[str, int]:
        payload = await self._build_cluster_payload(
            cluster=cluster,
            project_catalog=project_catalog,
            time_zone=time_zone,
        )
        extracted = await self._extract_actions(payload)
        judged = await self._judge_actions(payload, extracted)
        project = await self._resolve_project(
            cluster=cluster,
            extracted=extracted,
            judged=judged,
            user_id=run.user_id,
        )

        counts = {"applied": 0}
        action_specs = [
            ("todo_creates", "todo.create"),
            ("todo_completions", "todo.complete"),
            ("calendar_creates", "calendar.create"),
            ("journal_entries", "journal.entry"),
            ("workspace_updates", "workspace.update"),
        ]
        for key, action_type in action_specs:
            actions = extracted.get(key) or []
            for index, action in enumerate(actions):
                verdict = self._judge_item(judged, key, index)
                if not verdict.approved:
                    await self._record_non_applied_action(
                        run=run,
                        cluster=cluster,
                        action_type=action_type,
                        action=action,
                        status="rejected",
                        project_id=project.id if project else None,
                        judge_reasoning=verdict.reason,
                    )
                    continue
                duplicate = await self._deduplicate_action(
                    user_id=run.user_id,
                    cluster=cluster,
                    action_type=action_type,
                    action=action,
                    project_id=project.id if project else None,
                    time_zone=time_zone,
                )
                if duplicate.is_duplicate:
                    await self._record_duplicate_action(
                        run=run,
                        cluster=cluster,
                        action_type=action_type,
                        action=action,
                        project_id=project.id if project else None,
                        duplicate=duplicate,
                    )
                    continue
                if key == "todo_creates":
                    applied = await self._apply_todo_create(
                        run=run,
                        cluster=cluster,
                        project_id=project.id if project else None,
                        action=action,
                        time_zone=time_zone,
                    )
                elif key == "todo_completions":
                    applied = await self._apply_todo_completion(
                        run=run,
                        cluster=cluster,
                        project_id=project.id if project else None,
                        action=action,
                        time_zone=time_zone,
                    )
                elif key == "calendar_creates":
                    applied = await self._apply_calendar_create(
                        run=run,
                        cluster=cluster,
                        project_id=project.id if project else None,
                        action=action,
                    )
                elif key == "journal_entries":
                    applied = await self._apply_journal_entry(
                        run=run,
                        cluster=cluster,
                        action=action,
                        time_zone=time_zone,
                    )
                else:
                    applied = await self._apply_workspace_update(
                        run=run,
                        cluster=cluster,
                        project_id=project.id if project else None,
                        action=action,
                    )
                counts["applied"] += int(applied)

        project_inference = extracted.get("project_inference") or {}
        project_verdict = judged.get("project_inference") or {}
        if str(project_inference.get("project_name") or "").strip() and project is None:
            await self._record_non_applied_action(
                run=run,
                cluster=cluster,
                action_type="project.inference",
                action=project_inference,
                status="rejected",
                project_id=None,
                judge_reasoning=str(
                    project_verdict.get("reason")
                    or "Project inference did not clear the confidence threshold."
                ),
            )

        processed_at = datetime.now(timezone.utc)
        for message in cluster.messages:
            message.processed_at_utc = processed_at
        await self.session.flush()
        return counts

    async def _preview_cluster(
        self,
        *,
        cluster: MessageCluster,
        project_catalog: list[ProjectCatalogEntry],
        time_zone: str,
        user_id: int,
    ) -> dict[str, Any]:
        payload = await self._build_cluster_payload(
            cluster=cluster,
            project_catalog=project_catalog,
            time_zone=time_zone,
        )
        extracted = await self._extract_actions(payload)
        judged = await self._judge_actions(payload, extracted)
        project = await self._resolve_project(
            cluster=cluster,
            extracted=extracted,
            judged=judged,
            user_id=user_id,
        )

        actions: list[dict[str, Any]] = []
        action_specs = [
            ("todo_creates", "todo.create"),
            ("todo_completions", "todo.complete"),
            ("calendar_creates", "calendar.create"),
            ("journal_entries", "journal.entry"),
            ("workspace_updates", "workspace.update"),
        ]
        for key, action_type in action_specs:
            for index, action in enumerate(extracted.get(key) or []):
                verdict = self._judge_item(judged, key, index)
                duplicate = None
                final_approved = verdict.approved
                if verdict.approved:
                    duplicate = await self._deduplicate_action(
                        user_id=user_id,
                        cluster=cluster,
                        action_type=action_type,
                        action=action,
                        project_id=project.id if project else None,
                        time_zone=time_zone,
                    )
                    final_approved = not duplicate.is_duplicate
                source_message_ids = self._normalize_action_source_message_ids(
                    cluster.messages,
                    action_type,
                    action,
                )
                source_occurred_at_utc = self._action_source_occurred_at_utc(
                    cluster=cluster,
                    action_type=action_type,
                    action=action,
                    source_message_ids=source_message_ids,
                )
                actions.append(
                    {
                        "action_type": action_type,
                        "approved": final_approved,
                        "judge_approved": verdict.approved,
                        "judge_reasoning": verdict.reason,
                        "dedup_duplicate": bool(duplicate and duplicate.is_duplicate),
                        "dedup_reason": duplicate.reason if duplicate else "",
                        "matched_candidate_type": duplicate.matched_candidate_type if duplicate else None,
                        "matched_candidate_id": duplicate.matched_candidate_id if duplicate else None,
                        "project_id": project.id if project else None,
                        "project_name": project.name if project else None,
                        "source_message_ids": source_message_ids,
                        "source_occurred_at_utc": (
                            source_occurred_at_utc.isoformat() if source_occurred_at_utc else None
                        ),
                        "action": action,
                    }
                )

        project_inference = extracted.get("project_inference") or {}
        project_source_message_ids = self._normalize_action_source_message_ids(
            cluster.messages,
            "project.inference",
            project_inference,
        )
        project_source_occurred_at_utc = self._action_source_occurred_at_utc(
            cluster=cluster,
            action_type="project.inference",
            action=project_inference,
            source_message_ids=project_source_message_ids,
        )
        approved_actions = sum(1 for action in actions if action["approved"])
        rejected_actions = len(actions) - approved_actions
        return {
            "conversation": payload.get("conversation") or {},
            "time_context": payload.get("time_context") or {},
            "messages": payload.get("messages") or [],
            "project_inference": {
                **project_inference,
                "approved": bool((judged.get("project_inference") or {}).get("approved")),
                "judge_reasoning": str((judged.get("project_inference") or {}).get("reason") or ""),
                "resolved_project_id": project.id if project else None,
                "resolved_project_name": project.name if project else None,
                "source_message_ids": project_source_message_ids,
                "source_occurred_at_utc": (
                    project_source_occurred_at_utc.isoformat()
                    if project_source_occurred_at_utc is not None
                    else None
                ),
            },
            "actions": actions,
            "counts": {
                "suggested": len(actions),
                "approved": approved_actions,
                "rejected": rejected_actions,
            },
        }

    async def _build_cluster_payload(
        self,
        *,
        cluster: MessageCluster,
        project_catalog: list[ProjectCatalogEntry],
        time_zone: str,
    ) -> dict[str, Any]:
        open_todos = await self.todo_repo.list_for_user(cluster.conversation.user_id)
        participant_labels = [
            normalize_message_text(item.display_name or item.identifier)
            for item in cluster.conversation.participants
            if normalize_message_text(item.display_name or item.identifier)
        ]
        participant_handles = [
            normalize_message_text(item.identifier)
            for item in cluster.conversation.participants
            if normalize_message_text(item.identifier)
        ]
        conversation_name = conversation_display_name(
            cluster.conversation.display_name,
            cluster.conversation.chat_identifier,
            participant_labels,
        )
        message_texts = [message.text or "" for message in cluster.messages]
        affinities = await self._conversation_project_affinities(
            user_id=cluster.conversation.user_id,
            conversation_id=cluster.conversation.id,
        )
        effective_catalog = [
            ProjectCatalogEntry(
                name=item.name,
                aliases=item.aliases,
                notes=item.notes,
                conversation_affinity=affinities.get(item.name, 0.0),
            )
            for item in project_catalog
        ]
        heuristic_guess = infer_project_match(
            project_catalog=effective_catalog,
            conversation_name=conversation_name,
            participants=participant_handles or participant_labels,
            message_texts=message_texts,
        )
        time_context = self._cluster_time_context(cluster=cluster, time_zone=time_zone)
        return {
            "conversation": {
                "id": cluster.conversation.id,
                "name": conversation_name,
                "chat_identifier": cluster.conversation.chat_identifier,
                "service_name": cluster.conversation.service_name,
                "participants": participant_labels,
                "participant_handles": participant_handles,
            },
            "time_context": time_context,
            "project_candidates": heuristic_guess.candidates[:3],
            "heuristic_project_guess": {
                "project_name": heuristic_guess.project_name,
                "confidence": heuristic_guess.confidence,
                "reason": heuristic_guess.reason,
            },
            "projects": [item.name for item in project_catalog],
            "open_todos": [
                {
                    "id": todo.id,
                    "project_id": todo.project_id,
                    "text": todo.text,
                    "deadline_utc": todo.deadline_utc.isoformat() if todo.deadline_utc else None,
                    "completed": todo.completed,
                }
                for todo in open_todos
                if not todo.completed
            ][:40],
            "messages": [
                {
                    "id": message.id,
                    "sent_at_utc": message.sent_at_utc.isoformat() if message.sent_at_utc else None,
                    "is_from_me": message.is_from_me,
                    "sender": message.sender_label or message.handle_identifier,
                    "text": message.text or "",
                }
                for message in cluster.messages
            ],
        }

    def _message_id(self, message: Any) -> int | None:
        raw = message.get("id") if isinstance(message, dict) else getattr(message, "id", None)
        try:
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    def _message_text(self, message: Any) -> str:
        raw = message.get("text") if isinstance(message, dict) else getattr(message, "text", None)
        return normalize_message_text(raw)

    def _message_is_from_me(self, message: Any) -> bool:
        return bool(message.get("is_from_me") if isinstance(message, dict) else getattr(message, "is_from_me", False))

    def _message_sent_at_utc(self, message: Any) -> datetime | None:
        raw = message.get("sent_at_utc") if isinstance(message, dict) else getattr(message, "sent_at_utc", None)
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        return self._parse_dt(raw)

    def _action_source_query_text(self, action_type: str, action: dict[str, Any]) -> str:
        fields: list[str] = []
        if action_type == "project.inference":
            fields.extend(
                [
                    str(action.get("project_name") or ""),
                    str(action.get("reason") or ""),
                ]
            )
        elif action_type == "todo.create":
            fields.extend([str(action.get("text") or ""), str(action.get("reason") or "")])
        elif action_type == "todo.complete":
            fields.extend([str(action.get("match_text") or ""), str(action.get("reason") or "")])
        elif action_type == "calendar.create":
            fields.extend([str(action.get("summary") or ""), str(action.get("reason") or "")])
        elif action_type == "journal.entry":
            fields.extend([str(action.get("text") or ""), str(action.get("reason") or "")])
        elif action_type == "workspace.update":
            fields.extend(
                [
                    str(action.get("page_title") or ""),
                    str(action.get("search_query") or ""),
                    str(action.get("summary") or ""),
                    str(action.get("reason") or ""),
                ]
            )
        return " ".join(field for field in fields if field).strip()

    def _infer_source_message_ids(
        self,
        messages: list[Any],
        *,
        action_type: str,
        action: dict[str, Any],
    ) -> list[int]:
        if not messages:
            return []
        query_text = self._action_source_query_text(action_type, action)
        query_tokens = content_tokens(query_text)
        ranked: list[tuple[float, int]] = []
        ordered_ids = [message_id for message_id in (self._message_id(message) for message in messages) if message_id is not None]
        for index, message in enumerate(messages):
            message_id = self._message_id(message)
            if message_id is None:
                continue
            text = self._message_text(message)
            message_tokens = content_tokens(text)
            score = float(len(query_tokens & message_tokens))
            lowered_text = text.lower()
            if query_text and query_text.lower() in lowered_text:
                score += 2.0
            if action_type == "todo.complete":
                if looks_like_completion(text):
                    score += 2.0
                if self._message_is_from_me(message):
                    score += 0.5
            elif action_type == "journal.entry":
                if self._message_is_from_me(message):
                    score += 0.6
            elif action_type == "todo.create":
                if self._message_is_from_me(message):
                    score += 0.25
                if "?" in lowered_text and not self._message_is_from_me(message):
                    score += 0.25
            elif action_type == "calendar.create":
                if any(marker in lowered_text for marker in ("am", "pm", "tomorrow", "today", "friday", "monday", "tuesday", "wednesday", "thursday", "saturday", "sunday", "calendar", "meet", "meeting", "deadline")):
                    score += 0.5
            elif action_type == "workspace.update":
                if any(marker in lowered_text for marker in ("agreed", "requires", "keep", "should", "must")):
                    score += 0.3
            elif action_type == "project.inference":
                if str(action.get("project_name") or "").strip().lower() in lowered_text:
                    score += 0.75
            score += max(0.0, 0.1 - (len(messages) - index) * 0.01)
            if score > 0:
                ranked.append((score, message_id))

        if not ranked:
            if action_type in {"project.inference"} and not str(action.get("project_name") or "").strip():
                return []
            if action_type in {"todo.complete", "journal.entry"}:
                user_ids = [self._message_id(message) for message in messages if self._message_is_from_me(message)]
                user_ids = [message_id for message_id in user_ids if message_id is not None]
                if user_ids:
                    return [user_ids[-1]]
            return [ordered_ids[-1]] if ordered_ids else []

        ranked.sort(key=lambda item: (-item[0], ordered_ids.index(item[1])))
        top_score = ranked[0][0]
        selected_ids = [
            message_id
            for score, message_id in ranked
            if score >= max(1.0, top_score * 0.65)
        ][:4]
        ordered_selected = [message_id for message_id in ordered_ids if message_id in set(selected_ids)]
        return ordered_selected or [ranked[0][1]]

    def _normalize_action_source_message_ids(
        self,
        messages: list[Any],
        action_type: str,
        action: dict[str, Any],
    ) -> list[int]:
        if action_type == "project.inference" and not str(action.get("project_name") or "").strip():
            return []
        ordered_ids = [message_id for message_id in (self._message_id(message) for message in messages) if message_id is not None]
        valid_ids = set(ordered_ids)
        normalized: list[int] = []
        raw_source_ids = action.get("source_message_ids")
        if isinstance(raw_source_ids, list):
            for item in raw_source_ids:
                try:
                    message_id = int(item)
                except (TypeError, ValueError):
                    continue
                if message_id not in valid_ids or message_id in normalized:
                    continue
                normalized.append(message_id)
        if normalized:
            return [message_id for message_id in ordered_ids if message_id in set(normalized)]
        return self._infer_source_message_ids(messages, action_type=action_type, action=action)

    def _normalize_project_inference(
        self,
        messages: list[Any],
        project_inference: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = dict(project_inference)
        normalized["source_message_ids"] = self._normalize_action_source_message_ids(
            messages,
            "project.inference",
            normalized,
        )
        return normalized

    def _normalize_action_list(
        self,
        messages: list[Any],
        *,
        action_type: str,
        actions: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(actions, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in actions:
            if not isinstance(item, dict):
                continue
            action = dict(item)
            action["source_message_ids"] = self._normalize_action_source_message_ids(messages, action_type, action)
            normalized.append(action)
        return normalized

    def enrich_action_text(
        self,
        *,
        action_type: str,
        action: dict[str, Any],
        messages: list[Any],
        participant_names: list[str] | None = None,
    ) -> dict[str, Any]:
        enriched = dict(action)
        enriched["source_message_ids"] = self._normalize_action_source_message_ids(messages, action_type, enriched)
        support_messages = self._support_messages_for_action(
            messages=messages,
            action_type=action_type,
            action=enriched,
        )
        if not support_messages:
            return enriched
        participant_names = participant_names or []
        if action_type == "todo.create":
            enriched["text"] = self._enrich_todo_text(
                current=str(enriched.get("text") or ""),
                messages=support_messages,
                participant_names=participant_names,
            )
        elif action_type == "journal.entry":
            enriched["text"] = self._enrich_journal_text(
                current=str(enriched.get("text") or ""),
                messages=support_messages,
                participant_names=participant_names,
            )
        elif action_type == "calendar.create":
            enriched["summary"] = self._enrich_calendar_summary(
                current=str(enriched.get("summary") or ""),
                messages=support_messages,
                participant_names=participant_names,
            )
        return enriched

    def _enrich_extracted_actions(
        self,
        *,
        payload: dict[str, Any],
        extracted: dict[str, Any],
    ) -> dict[str, Any]:
        messages = list(payload.get("messages") or [])
        participant_names = [
            normalize_message_text(item)
            for item in (payload.get("conversation") or {}).get("participants") or []
            if normalize_message_text(item)
        ]
        enriched = dict(extracted)
        for key, action_type in (
            ("todo_creates", "todo.create"),
            ("todo_completions", "todo.complete"),
            ("calendar_creates", "calendar.create"),
            ("journal_entries", "journal.entry"),
            ("workspace_updates", "workspace.update"),
        ):
            enriched[key] = [
                self.enrich_action_text(
                    action_type=action_type,
                    action=action,
                    messages=messages,
                    participant_names=participant_names,
                )
                for action in list(extracted.get(key) or [])
            ]
        return enriched

    async def _deduplicate_action(
        self,
        *,
        user_id: int,
        cluster: MessageCluster,
        action_type: str,
        action: dict[str, Any],
        project_id: int | None,
        time_zone: str,
    ) -> DuplicateDecision:
        if action_type == "todo.complete":
            return DuplicateDecision(is_duplicate=False, reason="Todo completion dedup handled by target completion state.")
        candidates = await self._load_dedup_candidates(
            user_id=user_id,
            cluster=cluster,
            action_type=action_type,
            action=action,
            project_id=project_id,
            time_zone=time_zone,
        )
        if not candidates:
            return DuplicateDecision(is_duplicate=False, reason="No plausible existing candidates found.")

        deterministic = self._deterministic_duplicate_decision(
            action_type=action_type,
            action=action,
            candidates=candidates,
        )
        if deterministic.is_duplicate:
            return deterministic
        if self.client is None:
            return DuplicateDecision(is_duplicate=False, reason="LLM deduplicator unavailable and no hard duplicate matched.")

        source_message_ids = self._normalize_action_source_message_ids(cluster.messages, action_type, action)
        dedup_payload = {
            "action_type": action_type,
            "proposed_action": action,
            "source_message_ids": source_message_ids,
            "source_messages": [
                {
                    "id": message.id,
                    "sent_at_utc": message.sent_at_utc.isoformat() if message.sent_at_utc else None,
                    "is_from_me": message.is_from_me,
                    "sender": message.sender_label or message.handle_identifier,
                    "text": message.text or "",
                }
                for message in cluster.messages
                if not source_message_ids or message.id in set(source_message_ids)
            ],
            "candidates": candidates,
        }
        prompt = IMESSAGE_ACTION_DEDUP_PROMPT.replace(
            "{payload_json}",
            json.dumps(dedup_payload, ensure_ascii=False),
        )
        try:
            parsed = await self._invoke_model(prompt, IMessageDedupDecisionOutput)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[imessage] dedup model failed: {}", exc)
            return DuplicateDecision(is_duplicate=False, reason="Deduplicator returned invalid JSON.")
        is_duplicate = parsed.is_duplicate
        matched_candidate_id = parsed.matched_candidate_id
        matched_candidate_type = (parsed.matched_candidate_type or "").strip() or None
        try:
            matched_candidate_id = int(matched_candidate_id) if matched_candidate_id is not None else None
        except (TypeError, ValueError):
            matched_candidate_id = None
        if not is_duplicate:
            return DuplicateDecision(
                is_duplicate=False,
                reason=parsed.reason or "No duplicate candidate identified.",
            )
        candidate = next(
            (
                item for item in candidates
                if item.get("artifact_id") == matched_candidate_id
                and item.get("artifact_type") == matched_candidate_type
            ),
            None,
        )
        return DuplicateDecision(
            is_duplicate=True,
            reason=parsed.reason or "Existing artifact already represents this action.",
            matched_candidate_type=(candidate or {}).get("artifact_type") or matched_candidate_type,
            matched_candidate_id=(candidate or {}).get("artifact_id") or matched_candidate_id,
        )

    async def _load_dedup_candidates(
        self,
        *,
        user_id: int,
        cluster: MessageCluster,
        action_type: str,
        action: dict[str, Any],
        project_id: int | None,
        time_zone: str,
    ) -> list[dict[str, Any]]:
        if action_type == "todo.create":
            return await self._todo_dedup_candidates(user_id=user_id, action=action, project_id=project_id)
        if action_type == "calendar.create":
            return await self._calendar_dedup_candidates(user_id=user_id, action=action)
        if action_type == "journal.entry":
            occurred_at_utc = self._action_source_occurred_at_utc(
                cluster=cluster,
                action_type=action_type,
                action=action,
            )
            return await self._journal_dedup_candidates(
                user_id=user_id,
                action=action,
                time_zone=time_zone,
                occurred_at_utc=occurred_at_utc,
            )
        if action_type == "workspace.update":
            return await self._workspace_dedup_candidates(user_id=user_id, action=action, project_id=project_id)
        return []

    def _text_similarity(self, left: str | None, right: str | None) -> float:
        return SequenceMatcher(None, normalize_message_text(left).lower(), normalize_message_text(right).lower()).ratio()

    def _token_overlap_score(self, left: str | None, right: str | None) -> float:
        left_tokens = content_tokens(left)
        right_tokens = content_tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / max(min(len(left_tokens), len(right_tokens)), 1)

    def _ranked_text_candidates(
        self,
        *,
        action_text: str,
        candidates: list[dict[str, Any]],
        time_bonus: callable | None = None,
    ) -> list[dict[str, Any]]:
        ranked: list[tuple[float, dict[str, Any]]] = []
        for candidate in candidates:
            candidate_text = str(candidate.get("text") or "")
            similarity = self._text_similarity(action_text, candidate_text)
            overlap = self._token_overlap_score(action_text, candidate_text)
            score = max(similarity, overlap)
            if time_bonus is not None:
                score += float(time_bonus(candidate) or 0.0)
            if score >= 0.18:
                ranked.append((score, candidate))
        ranked.sort(key=lambda item: (-item[0], int(item[1].get("artifact_id") or 0)))
        return [item[1] for item in ranked[:MAX_DEDUP_CANDIDATES]]

    async def _todo_dedup_candidates(
        self,
        *,
        user_id: int,
        action: dict[str, Any],
        project_id: int | None,
    ) -> list[dict[str, Any]]:
        action_text = normalize_message_text(action.get("text"))
        if not action_text:
            return []
        todos = [todo for todo in await self.todo_repo.list_for_user(user_id) if not todo.completed]
        if project_id is not None:
            todos = [todo for todo in todos if todo.project_id == project_id] or todos
        candidates = [
            {
                "artifact_type": "todo",
                "artifact_id": todo.id,
                "project_id": todo.project_id,
                "text": todo.text,
                "deadline_utc": todo.deadline_utc.isoformat() if todo.deadline_utc else None,
                "created_at": todo.created_at.isoformat() if todo.created_at else None,
            }
            for todo in todos
        ]
        return self._ranked_text_candidates(action_text=action_text, candidates=candidates)

    async def _calendar_dedup_candidates(
        self,
        *,
        user_id: int,
        action: dict[str, Any],
    ) -> list[dict[str, Any]]:
        summary = normalize_message_text(action.get("summary"))
        start = self._parse_dt(action.get("start_time"))
        end = self._parse_dt(action.get("end_time"))
        if not summary or start is None or end is None:
            return []
        window_start = start - (timedelta(days=2) if bool(action.get("is_all_day")) else timedelta(hours=12))
        window_end = end + (timedelta(days=2) if bool(action.get("is_all_day")) else timedelta(hours=12))
        stmt = (
            select(CalendarEvent)
            .where(
                CalendarEvent.user_id == user_id,
                or_(CalendarEvent.status.is_(None), CalendarEvent.status != "cancelled"),
                CalendarEvent.start_time.is_not(None),
                CalendarEvent.end_time.is_not(None),
                CalendarEvent.start_time <= window_end,
                CalendarEvent.end_time >= window_start,
            )
            .order_by(CalendarEvent.start_time.asc())
            .limit(30)
        )
        events = list((await self.session.execute(stmt)).scalars().all())
        candidates = [
            {
                "artifact_type": "calendar_event",
                "artifact_id": event.id,
                "text": event.summary or "",
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "is_all_day": bool(event.is_all_day),
            }
            for event in events
        ]

        def _time_bonus(candidate: dict[str, Any]) -> float:
            candidate_start = self._parse_dt(candidate.get("start_time"))
            if candidate_start is None:
                return 0.0
            delta = abs((candidate_start - start).total_seconds())
            if delta <= 900:
                return 0.4
            if delta <= 3600:
                return 0.25
            if delta <= 21600:
                return 0.1
            return 0.0

        return self._ranked_text_candidates(action_text=summary, candidates=candidates, time_bonus=_time_bonus)

    async def _journal_dedup_candidates(
        self,
        *,
        user_id: int,
        action: dict[str, Any],
        time_zone: str,
        occurred_at_utc: datetime | None,
    ) -> list[dict[str, Any]]:
        text = normalize_message_text(action.get("text"))
        if not text:
            return []
        occurred_at = occurred_at_utc or self._parse_dt(action.get("source_occurred_at_utc")) or self._parse_dt(action.get("occurred_at_utc"))
        if occurred_at is None:
            occurred_at = datetime.now(timezone.utc)
        local_date = occurred_at.astimezone(resolve_time_zone(time_zone)).date()
        stmt = (
            select(JournalEntry)
            .where(
                JournalEntry.user_id == user_id,
                JournalEntry.local_date >= (local_date - timedelta(days=1)),
                JournalEntry.local_date <= (local_date + timedelta(days=1)),
            )
            .order_by(JournalEntry.created_at.desc())
            .limit(30)
        )
        entries = list((await self.session.execute(stmt)).scalars().all())
        candidates = [
            {
                "artifact_type": "journal_entry",
                "artifact_id": entry.id,
                "text": entry.text,
                "local_date": entry.local_date.isoformat(),
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }
            for entry in entries
        ]
        return self._ranked_text_candidates(action_text=text, candidates=candidates)

    async def _workspace_dedup_candidates(
        self,
        *,
        user_id: int,
        action: dict[str, Any],
        project_id: int | None,
    ) -> list[dict[str, Any]]:
        if project_id is None:
            return []
        summary = normalize_message_text(action.get("summary"))
        if not summary:
            return []
        stmt = (
            select(IMessageActionAudit)
            .where(
                IMessageActionAudit.user_id == user_id,
                IMessageActionAudit.project_id == project_id,
                IMessageActionAudit.action_type == "workspace.update",
                IMessageActionAudit.status.in_(["applied", "skipped_duplicate_existing", "skipped_duplicate_content"]),
            )
            .order_by(IMessageActionAudit.created_at.desc())
            .limit(30)
        )
        audits = list((await self.session.execute(stmt)).scalars().all())
        candidates = []
        for audit in audits:
            extracted = audit.extracted_payload or {}
            candidate_summary = normalize_message_text(extracted.get("summary"))
            if not candidate_summary:
                continue
            candidates.append(
                {
                    "artifact_type": "workspace_update",
                    "artifact_id": int(audit.target_page_id or audit.id),
                    "text": candidate_summary,
                    "page_title": str(extracted.get("page_title") or ""),
                    "target_page_id": audit.target_page_id,
                    "source_occurred_at_utc": audit.source_occurred_at_utc.isoformat() if audit.source_occurred_at_utc else None,
                }
            )
        return self._ranked_text_candidates(action_text=summary, candidates=candidates)

    def _deterministic_duplicate_decision(
        self,
        *,
        action_type: str,
        action: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> DuplicateDecision:
        if not candidates:
            return DuplicateDecision(is_duplicate=False, reason="No candidates.")
        action_text = normalize_message_text(
            action.get("text") or action.get("summary") or action.get("match_text")
        )
        best_candidate = candidates[0]
        best_score = max(
            self._text_similarity(action_text, best_candidate.get("text")),
            self._token_overlap_score(action_text, best_candidate.get("text")),
        )
        if action_type == "calendar.create":
            proposed_start = self._parse_dt(action.get("start_time"))
            candidate_start = self._parse_dt(best_candidate.get("start_time"))
            if proposed_start and candidate_start and abs((candidate_start - proposed_start).total_seconds()) <= 3600 and best_score >= 0.72:
                return DuplicateDecision(
                    is_duplicate=True,
                    reason="Existing calendar event matches the same commitment closely enough.",
                    matched_candidate_type=str(best_candidate.get("artifact_type") or "calendar_event"),
                    matched_candidate_id=int(best_candidate.get("artifact_id") or 0),
                )
        elif action_type == "todo.create" and best_score >= 0.9:
            return DuplicateDecision(
                is_duplicate=True,
                reason="Existing open todo already captures the same obligation.",
                matched_candidate_type="todo",
                matched_candidate_id=int(best_candidate.get("artifact_id") or 0),
            )
        elif action_type == "journal.entry" and best_score >= 0.9:
            return DuplicateDecision(
                is_duplicate=True,
                reason="Existing journal entry already captures the same experience.",
                matched_candidate_type="journal_entry",
                matched_candidate_id=int(best_candidate.get("artifact_id") or 0),
            )
        elif action_type == "workspace.update" and best_score >= 0.88:
            return DuplicateDecision(
                is_duplicate=True,
                reason="Existing workspace update already captures the same durable fact.",
                matched_candidate_type="workspace_update",
                matched_candidate_id=int(best_candidate.get("artifact_id") or 0),
            )
        return DuplicateDecision(is_duplicate=False, reason="No hard duplicate matched.")

    def _support_messages_for_action(
        self,
        *,
        messages: list[Any],
        action_type: str,
        action: dict[str, Any],
    ) -> list[Any]:
        source_ids = self._normalize_action_source_message_ids(messages, action_type, action)
        if not source_ids:
            return list(messages)
        allowed = set(source_ids)
        selected = [message for message in messages if self._message_id(message) in allowed]
        return selected or list(messages)

    def _detail_score(self, text: str) -> int:
        normalized = normalize_message_text(text)
        if not normalized:
            return 0
        score = len(content_tokens(normalized))
        if re.search(r"\bwith\b|\bto\b|\babout\b|\bfor\b", normalized.lower()):
            score += 1
        if re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", normalized):
            score += 2
        if "heads-up" in normalized.lower():
            score += 1
        return score

    def _looks_like_handle_label(self, value: str | None) -> bool:
        normalized = normalize_message_text(value)
        return bool(normalized and _HANDLE_LIKE_RE.search(normalized))

    def _counterparty_names(self, messages: list[Any], participant_names: list[str]) -> list[str]:
        names: list[str] = []
        for name in participant_names:
            normalized = normalize_message_text(name)
            if not normalized or normalized.lower() == "you" or self._looks_like_handle_label(normalized):
                continue
            if normalized not in names:
                names.append(normalized)
        for message in messages:
            if self._message_is_from_me(message):
                continue
            sender = normalize_message_text(
                message.get("sender") if isinstance(message, dict) else getattr(message, "sender_label", None)
            )
            if not sender or sender.lower() == "you" or self._looks_like_handle_label(sender):
                continue
            if sender not in names:
                names.append(sender)
        return names

    def _sentence_case(self, text: str) -> str:
        normalized = normalize_message_text(text)
        if not normalized:
            return ""
        return normalized[0].upper() + normalized[1:]

    def _cleanup_action_phrase(self, text: str) -> str:
        cleaned = normalize_message_text(text)
        cleaned = re.sub(r"[.?!]+$", "", cleaned)
        cleaned = re.sub(r"\bhu\b", "heads-up", cleaned, flags=re.IGNORECASE)
        return normalize_message_text(cleaned)

    def _todo_text_needs_enrichment(self, text: str) -> bool:
        lowered = normalize_message_text(text).lower()
        if not lowered:
            return True
        if " a show" in lowered:
            return True
        if lowered.startswith("send ") and " to " not in lowered:
            return True
        if lowered.startswith("ask ") and not any(marker in lowered for marker in (" about ", " for ", " to ")):
            return True
        if lowered.startswith("meet ") and " with " not in lowered:
            return True
        return self._detail_score(lowered) <= 3

    def _extract_source_todo_phrase(self, messages: list[Any], participant_names: list[str]) -> str | None:
        counterparties = self._counterparty_names(messages, participant_names)
        for message in reversed(messages):
            text = self._message_text(message)
            if not text:
                continue
            match = _TODO_PHRASE_RE.search(text)
            if match:
                phrase = self._cleanup_action_phrase(match.group(1))
                if phrase:
                    return self._expand_task_phrase(phrase, source_text=text, counterparties=counterparties)
            send_match = _SEND_TARGET_RE.search(text)
            if send_match:
                return self._sentence_case(
                    self._cleanup_action_phrase(f"send {send_match.group(1)} to {send_match.group(2)}")
                )
            ask_match = _ASK_TARGET_RE.search(text)
            if ask_match:
                return self._sentence_case(
                    self._cleanup_action_phrase(
                        f"ask {ask_match.group(1)} {ask_match.group(2)} {ask_match.group(3)}"
                    )
                )
            meet_match = _MEET_WITH_RE.search(text)
            if meet_match:
                return self._sentence_case(
                    self._cleanup_action_phrase(
                        f"meet with {meet_match.group(1)} to {meet_match.group(2)}"
                    )
                )
        return None

    def _expand_task_phrase(self, phrase: str, *, source_text: str, counterparties: list[str]) -> str:
        lowered = phrase.lower()
        candidate = phrase
        send_match = _SEND_TARGET_RE.search(source_text)
        if lowered.startswith("send ") and " to " not in lowered and send_match:
            candidate = f"send {send_match.group(1)} to {send_match.group(2)}"
        ask_match = _ASK_TARGET_RE.search(source_text)
        if lowered.startswith("ask ") and not any(marker in lowered for marker in (" about ", " for ", " to ")) and ask_match:
            candidate = f"ask {ask_match.group(1)} {ask_match.group(2)} {ask_match.group(3)}"
        meet_match = _MEET_WITH_RE.search(source_text)
        if lowered.startswith("meet ") and " with " not in lowered and meet_match:
            candidate = f"meet with {meet_match.group(1)} to {meet_match.group(2)}"
        watch_match = _WATCH_RE.search(source_text)
        if "watch a show" in lowered and watch_match:
            candidate = f"decided to watch {watch_match.group(1)}"
        if candidate.lower().startswith("meet ") and " with " not in candidate.lower() and len(counterparties) == 1:
            remainder = candidate[5:].strip()
            candidate = f"meet with {counterparties[0]} {remainder}".strip()
        return self._sentence_case(self._cleanup_action_phrase(candidate))

    def _enrich_todo_text(self, *, current: str, messages: list[Any], participant_names: list[str]) -> str:
        current_text = self._sentence_case(current)
        candidate = self._extract_source_todo_phrase(messages, participant_names)
        if not candidate:
            return current_text
        if self._todo_text_needs_enrichment(current_text) or self._detail_score(candidate) > self._detail_score(current_text):
            return candidate
        return current_text

    def _extract_source_journal_phrase(self, messages: list[Any], participant_names: list[str]) -> str | None:
        for message in reversed(messages):
            text = self._message_text(message)
            if not text:
                continue
            cleaned = self._cleanup_action_phrase(text)
            if not cleaned:
                continue
            if _JOURNAL_RECAP_RE.search(cleaned):
                cleaned = _LEADING_PRONOUN_RE.sub("", cleaned)
                cleaned = re.sub(r"^talked to\b", "Talked with", cleaned, flags=re.IGNORECASE)
                return self._sentence_case(cleaned)
            if re.match(r"^(finally got|got|submitted|sent|saw|decided to watch|watched|planned|booked)\b", cleaned, re.IGNORECASE):
                return self._sentence_case(cleaned)
        return None

    def _enrich_journal_text(self, *, current: str, messages: list[Any], participant_names: list[str]) -> str:
        current_text = self._sentence_case(current)
        candidate = self._extract_source_journal_phrase(messages, participant_names)
        if not candidate:
            return current_text
        if self._detail_score(candidate) > self._detail_score(current_text) or " a show" in current_text.lower():
            return candidate
        return current_text

    def _enrich_calendar_summary(self, *, current: str, messages: list[Any], participant_names: list[str]) -> str:
        current_text = self._sentence_case(current)
        counterparties = self._counterparty_names(messages, participant_names)
        if not counterparties:
            return current_text
        if any(name.lower() in current_text.lower() for name in counterparties):
            return current_text
        joined = " ".join(self._message_text(message) for message in messages).lower()
        if "dinner" in joined:
            return self._sentence_case(f"Dinner with {counterparties[0]}")
        if "call" in joined:
            return self._sentence_case(f"Call with {counterparties[0]}")
        if "meet" in joined or "meeting" in joined:
            return self._sentence_case(f"Meeting with {counterparties[0]}")
        return current_text

    def _action_prefers_user_messages(self, action_type: str) -> bool:
        return action_type in {"todo.complete", "journal.entry"}

    def _action_source_occurred_at_utc(
        self,
        *,
        cluster: MessageCluster,
        action_type: str,
        action: dict[str, Any],
        source_message_ids: list[int] | None = None,
    ) -> datetime | None:
        message_ids = source_message_ids or self._normalize_action_source_message_ids(
            cluster.messages,
            action_type,
            action,
        )
        if not message_ids and action_type == "project.inference" and not str(action.get("project_name") or "").strip():
            return None
        return self._cluster_reference_time_utc(
            cluster=cluster,
            prefer_user_messages=self._action_prefers_user_messages(action_type),
            source_message_ids=message_ids or None,
        )

    def _cluster_reference_time_utc(
        self,
        *,
        cluster: MessageCluster,
        prefer_user_messages: bool = False,
        source_message_ids: list[int] | None = None,
    ) -> datetime:
        candidate_messages = list(cluster.messages)
        if source_message_ids:
            allowed_ids = set(source_message_ids)
            filtered = [message for message in cluster.messages if message.id in allowed_ids]
            if filtered:
                candidate_messages = filtered
        if prefer_user_messages:
            user_timestamps = [
                message.sent_at_utc
                for message in candidate_messages
                if message.sent_at_utc is not None and bool(message.is_from_me)
            ]
            if user_timestamps:
                return max(user_timestamps)
        timestamps = [message.sent_at_utc for message in candidate_messages if message.sent_at_utc is not None]
        if timestamps:
            return max(timestamps)
        return datetime.now(timezone.utc)

    def _cluster_time_context(self, *, cluster: MessageCluster, time_zone: str) -> dict[str, Any]:
        timestamps = [message.sent_at_utc for message in cluster.messages if message.sent_at_utc is not None]
        zone = resolve_time_zone(time_zone)
        if not timestamps:
            fallback = datetime.now(timezone.utc)
            fallback_local = fallback.astimezone(zone)
            return {
                "time_zone": time_zone,
                "cluster_start_time_utc": fallback.isoformat(),
                "cluster_end_time_utc": fallback.isoformat(),
                "cluster_start_time_local": fallback_local.isoformat(),
                "cluster_end_time_local": fallback_local.isoformat(),
                "relative_time_rule": (
                    "Interpret relative phrases using the message sent_at_utc when available. "
                    "If a message timestamp is missing, fall back to cluster_end_time_local instead of processing time."
                ),
            }
        start_utc = min(timestamps)
        end_utc = max(timestamps)
        return {
            "time_zone": time_zone,
            "cluster_start_time_utc": start_utc.isoformat(),
            "cluster_end_time_utc": end_utc.isoformat(),
            "cluster_start_time_local": start_utc.astimezone(zone).isoformat(),
            "cluster_end_time_local": end_utc.astimezone(zone).isoformat(),
            "relative_time_rule": (
                "Interpret relative phrases such as today, tomorrow, tonight, this afternoon, and next Friday "
                "from the sent_at_utc of the specific message that contains the phrase. "
                "When multiple messages contribute to one action, use the latest relevant confirming message timestamp."
            ),
        }

    async def _extract_project_inference(self, payload: dict[str, Any]) -> dict[str, Any]:
        heuristic = payload.get("heuristic_project_guess") or {}
        candidates = payload.get("project_candidates") or []
        payload_messages = list(payload.get("messages") or [])
        heuristic_guess = ProjectGuess(
            project_name=str(heuristic.get("project_name") or "").strip() or None,
            confidence=float(heuristic.get("confidence") or 0.0),
            reason=str(heuristic.get("reason") or ""),
            candidates=list(candidates) if isinstance(candidates, list) else [],
        )
        if not self._should_use_project_inference_model(heuristic_guess):
            return self._normalize_project_inference(payload_messages, {
                "project_name": heuristic_guess.project_name,
                "confidence": heuristic_guess.confidence,
                "reason": heuristic_guess.reason,
            })

        inference_payload = {
            "conversation": payload.get("conversation") or {},
            "messages": (payload.get("messages") or [])[:8],
            "heuristic_guess": {
                "project_name": heuristic_guess.project_name,
                "confidence": heuristic_guess.confidence,
                "reason": heuristic_guess.reason,
            },
            "project_candidates": heuristic_guess.candidates[:3],
        }
        prompt = IMESSAGE_PROJECT_INFERENCE_PROMPT.replace(
            "{payload_json}",
            json.dumps(inference_payload, ensure_ascii=False),
        )
        try:
            parsed = await self._invoke_model(prompt, IMessageProjectInferenceOutput)
        except Exception:
            return self._normalize_project_inference(payload_messages, {
                "project_name": heuristic_guess.project_name,
                "confidence": heuristic_guess.confidence,
                "reason": heuristic_guess.reason,
            })

        allowed_names = {
            str(item.get("project_name") or "").strip()
            for item in heuristic_guess.candidates
            if isinstance(item, dict)
        }
        project_name = str(parsed.project_name or "").strip()
        invalid_candidate = bool(project_name) and project_name not in allowed_names
        if project_name and project_name not in allowed_names:
            project_name = heuristic_guess.project_name or ""
        try:
            confidence = float(parsed.confidence or 0.0)
        except (TypeError, ValueError):
            confidence = heuristic_guess.confidence
        if invalid_candidate:
            confidence = heuristic_guess.confidence
        if not project_name:
            return self._normalize_project_inference(payload_messages, {
                "project_name": None,
                "confidence": 0.0,
                "reason": parsed.reason or "Project inference model rejected all candidates.",
            })
        return self._normalize_project_inference(payload_messages, {
            "project_name": project_name,
            "confidence": max(0.0, min(0.98, confidence)),
            "reason": parsed.reason or heuristic_guess.reason,
            "source_message_ids": parsed.source_message_ids,
        })

    def _should_use_project_inference_model(self, heuristic_guess: ProjectGuess) -> bool:
        if self.client is None:
            return False
        candidates = heuristic_guess.candidates or []
        if not candidates:
            return False
        top_confidence = float(candidates[0].get("confidence") or 0.0)
        second_confidence = float(candidates[1].get("confidence") or 0.0) if len(candidates) > 1 else 0.0
        if top_confidence < PROJECT_ROUTER_MIN_CONFIDENCE:
            return False
        if top_confidence >= PROJECT_ROUTER_SKIP_CONFIDENCE and top_confidence - second_confidence >= PROJECT_ROUTER_MARGIN:
            return False
        return True

    async def _extract_actions(self, payload: dict[str, Any]) -> dict[str, Any]:
        heuristic = self._heuristic_extract(payload)
        project_inference = await self._extract_project_inference(payload)
        enriched_payload = {
            **payload,
            "project_inference": project_inference,
        }
        calendar_extract = await self._extract_calendar_actions(enriched_payload)
        general_extract = await self._extract_general_actions(enriched_payload, heuristic)
        return {
            **self._enrich_extracted_actions(
                payload=enriched_payload,
                extracted={
                    "project_inference": project_inference,
                    "todo_creates": general_extract.get("todo_creates") or [],
                    "todo_completions": general_extract.get("todo_completions") or [],
                    "calendar_creates": calendar_extract.get("calendar_creates") or [],
                    "journal_entries": general_extract.get("journal_entries") or [],
                    "workspace_updates": general_extract.get("workspace_updates") or [],
                },
            ),
        }

    async def _extract_calendar_actions(self, payload: dict[str, Any]) -> dict[str, Any]:
        heuristic = {"calendar_creates": []}
        if self.client is None:
            return heuristic
        payload_messages = list(payload.get("messages") or [])
        calendar_payload = {
            "conversation": payload.get("conversation") or {},
            "time_context": payload.get("time_context") or {},
            "project_inference": payload.get("project_inference") or {},
            "messages": payload.get("messages") or [],
        }
        prompt = IMESSAGE_CALENDAR_EXTRACTION_PROMPT.replace(
            "{payload_json}",
            json.dumps(calendar_payload, ensure_ascii=False),
        )
        try:
            parsed = await self._invoke_model(prompt, IMessageCalendarExtractionOutput)
        except Exception:
            return heuristic
        return {
            "calendar_creates": self._normalize_action_list(
                payload_messages,
                action_type="calendar.create",
                actions=[item.model_dump() for item in parsed.calendar_creates],
            )
        }

    async def _extract_general_actions(
        self,
        payload: dict[str, Any],
        heuristic: dict[str, Any],
    ) -> dict[str, Any]:
        heuristic_general = {
            "todo_creates": list(heuristic.get("todo_creates") or []),
            "todo_completions": list(heuristic.get("todo_completions") or []),
            "journal_entries": list(heuristic.get("journal_entries") or []),
            "workspace_updates": list(heuristic.get("workspace_updates") or []),
        }
        payload_messages = list(payload.get("messages") or [])
        if self.client is None:
            return {
                key: self._normalize_action_list(
                    payload_messages,
                    action_type=action_type,
                    actions=heuristic_general[key],
                )
                for key, action_type in (
                    ("todo_creates", "todo.create"),
                    ("todo_completions", "todo.complete"),
                    ("journal_entries", "journal.entry"),
                    ("workspace_updates", "workspace.update"),
                )
            }
        prompt = IMESSAGE_ACTION_EXTRACTION_PROMPT.replace(
            "{payload_json}",
            json.dumps(payload, ensure_ascii=False),
        )
        try:
            parsed = await self._invoke_model(prompt, IMessageActionExtractionOutput)
        except Exception:
            return {
                key: self._normalize_action_list(
                    payload_messages,
                    action_type=action_type,
                    actions=heuristic_general[key],
                )
                for key, action_type in (
                    ("todo_creates", "todo.create"),
                    ("todo_completions", "todo.complete"),
                    ("journal_entries", "journal.entry"),
                    ("workspace_updates", "workspace.update"),
                )
            }

        merged = {}
        for key in ("todo_creates", "todo_completions", "journal_entries", "workspace_updates"):
            value = [item.model_dump() for item in getattr(parsed, key)]
            action_type = {
                "todo_creates": "todo.create",
                "todo_completions": "todo.complete",
                "journal_entries": "journal.entry",
                "workspace_updates": "workspace.update",
            }[key]
            merged[key] = self._normalize_action_list(
                payload_messages,
                action_type=action_type,
                actions=value if isinstance(value, list) else heuristic_general[key],
            )
        return merged

    async def _judge_actions(self, payload: dict[str, Any], extracted: dict[str, Any]) -> dict[str, Any]:
        heuristic = self._heuristic_judge(payload, extracted)
        if self.client is None:
            return heuristic
        judge_payload = {
            "cluster": payload,
            "extracted": extracted,
        }
        prompt = IMESSAGE_ACTION_JUDGE_PROMPT.replace(
            "{payload_json}",
            json.dumps(judge_payload, ensure_ascii=False),
        )
        try:
            parsed = await self._invoke_model(prompt, IMessageActionJudgeOutput)
        except Exception:
            return heuristic
        return parsed.model_dump()

    async def _resolve_project(
        self,
        *,
        cluster: MessageCluster,
        extracted: dict[str, Any],
        judged: dict[str, Any],
        user_id: int,
    ):
        project_inference = extracted.get("project_inference") or {}
        judge_project = judged.get("project_inference") or {}
        project_name = str(project_inference.get("project_name") or "").strip()
        confidence = float(project_inference.get("confidence") or 0)
        approved = bool(judge_project.get("approved"))
        if not project_name or confidence < PROJECT_CONFIDENCE_THRESHOLD or not approved:
            return None
        return await self.project_repo.get_by_name_for_user(user_id, project_name)

    def _heuristic_extract(self, payload: dict[str, Any]) -> dict[str, Any]:
        messages = payload.get("messages") or []
        combined_text = " ".join(str(item.get("text") or "") for item in messages)
        guess = payload.get("project_inference") or payload.get("heuristic_project_guess") or {}
        todo_creates: list[dict[str, Any]] = []
        todo_completions: list[dict[str, Any]] = []
        journal_entries: list[dict[str, Any]] = []
        workspace_updates: list[dict[str, Any]] = []

        for pattern in (
            r"(?:need to|have to|remember to|should)\s+([^.!?]+)",
            r"(settle up on [^.!?]+)",
            r"(pay [^.!?]+)",
        ):
            for match in re.findall(pattern, combined_text, flags=re.IGNORECASE):
                text = str(match).strip(" .")
                if text:
                    todo_creates.append(
                        {
                            "text": text[0].upper() + text[1:],
                            "deadline_utc": None,
                            "deadline_is_date_only": False,
                            "reason": "Heuristic obligation extraction from conversation text",
                        }
                    )
        if any(looks_like_completion(item.get("text")) for item in messages if item.get("is_from_me")):
            todo_completions.append(
                {
                    "match_text": "",
                    "reason": "Detected a completion-like outgoing message in the conversation",
                }
            )
        if guess.get("project_name") and float(guess.get("confidence") or 0) >= PROJECT_CONFIDENCE_THRESHOLD:
            for keyword in ("architecture", "design", "spec", "plan"):
                if keyword in combined_text.lower():
                    workspace_updates.append(
                        {
                            "page_title": f"{guess['project_name']} {keyword.title()}",
                            "search_query": keyword,
                            "summary": (
                                f"{keyword.title()} considerations were discussed for {guess['project_name']}. "
                                f"Capture the latest durable decisions and constraints here."
                            ),
                            "reason": "Detected likely project knowledge update from keyword overlap",
                        }
                    )
                    break
        return {
            "project_inference": {
                "project_name": guess.get("project_name"),
                "confidence": guess.get("confidence", 0),
                "reason": guess.get("reason", ""),
            },
            "todo_creates": todo_creates,
            "todo_completions": todo_completions,
            "calendar_creates": [],
            "journal_entries": journal_entries,
            "workspace_updates": workspace_updates,
        }

    def _heuristic_judge(self, payload: dict[str, Any], extracted: dict[str, Any]) -> dict[str, Any]:
        project = extracted.get("project_inference") or {}
        messages = payload.get("messages") or []
        return {
            "project_inference": {
                "approved": bool(project.get("project_name"))
                and float(project.get("confidence") or 0) >= PROJECT_CONFIDENCE_THRESHOLD,
                "reason": "Approved when heuristic project confidence clears threshold.",
            },
            "todo_creates": [
                {
                    "approved": bool(str(item.get("text") or "").strip()),
                    "reason": "Approved when todo text is present.",
                }
                for item in extracted.get("todo_creates") or []
            ],
            "todo_completions": [
                {
                    "approved": any(looks_like_completion(item.get("text")) for item in messages if item.get("is_from_me")),
                    "reason": "Approved when the cluster contains a completion-like outgoing message.",
                }
                for _ in extracted.get("todo_completions") or []
            ],
            "calendar_creates": [
                {
                    "approved": bool(item.get("summary") and item.get("start_time") and item.get("end_time")),
                    "reason": "Approved when the event has summary and explicit times.",
                }
                for item in extracted.get("calendar_creates") or []
            ],
            "journal_entries": [
                {
                    "approved": bool(str(item.get("text") or "").strip()),
                    "reason": "Approved when the journal text is concrete and non-empty.",
                }
                for item in extracted.get("journal_entries") or []
            ],
            "workspace_updates": [
                {
                    "approved": bool(str(item.get("page_title") or "").strip()) and bool(project.get("project_name")),
                    "reason": "Approved only when a project is inferred and the update is named.",
                }
                for item in extracted.get("workspace_updates") or []
            ],
        }

    def _judge_item(self, judged: dict[str, Any], key: str, index: int) -> JudgmentOutcome:
        items = judged.get(key) or []
        if not isinstance(items, list) or index >= len(items) or not isinstance(items[index], dict):
            return JudgmentOutcome(approved=False, reason="No matching judge verdict returned.")
        return JudgmentOutcome(
            approved=bool(items[index].get("approved")),
            reason=str(items[index].get("reason") or ""),
        )

    async def _record_non_applied_action(
        self,
        *,
        run: IMessageProcessingRun,
        cluster: MessageCluster,
        action_type: str,
        action: dict[str, Any],
        status: str,
        project_id: int | None,
        judge_reasoning: str,
    ) -> None:
        fingerprint = stable_fingerprint(
            action_type,
            cluster.conversation.id,
            status,
            json.dumps(action, sort_keys=True, ensure_ascii=True, default=str),
        )
        if await self._audit_exists(run.user_id, fingerprint):
            return
        source_message_ids = self._normalize_action_source_message_ids(
            cluster.messages,
            action_type,
            action,
        )
        source_occurred_at_utc = self._action_source_occurred_at_utc(
            cluster=cluster,
            action_type=action_type,
            action=action,
            source_message_ids=source_message_ids,
        )
        await self._record_action_audit(
            run=run,
            cluster=cluster,
            action_type=action_type,
            fingerprint=fingerprint,
            status=status,
            project_id=project_id,
            action=action,
            judge_reasoning=judge_reasoning,
            supporting_message_ids=source_message_ids,
            source_occurred_at_utc=source_occurred_at_utc,
        )

    async def _record_duplicate_action(
        self,
        *,
        run: IMessageProcessingRun,
        cluster: MessageCluster,
        action_type: str,
        action: dict[str, Any],
        project_id: int | None,
        duplicate: DuplicateDecision,
    ) -> None:
        fingerprint = stable_fingerprint(
            action_type,
            cluster.conversation.id,
            "skipped_duplicate_existing",
            json.dumps(action, sort_keys=True, ensure_ascii=True, default=str),
            duplicate.matched_candidate_type,
            duplicate.matched_candidate_id,
        )
        if await self._audit_exists(run.user_id, fingerprint):
            return
        source_message_ids = self._normalize_action_source_message_ids(
            cluster.messages,
            action_type,
            action,
        )
        source_occurred_at_utc = self._action_source_occurred_at_utc(
            cluster=cluster,
            action_type=action_type,
            action=action,
            source_message_ids=source_message_ids,
        )
        target_kwargs: dict[str, Any] = {}
        if duplicate.matched_candidate_type == "todo":
            target_kwargs["target_todo_id"] = duplicate.matched_candidate_id
        elif duplicate.matched_candidate_type == "calendar_event":
            target_kwargs["target_calendar_event_id"] = duplicate.matched_candidate_id
        elif duplicate.matched_candidate_type == "journal_entry":
            target_kwargs["target_journal_entry_id"] = duplicate.matched_candidate_id
        elif duplicate.matched_candidate_type == "workspace_update":
            target_kwargs["target_page_id"] = duplicate.matched_candidate_id
        await self._record_action_audit(
            run=run,
            cluster=cluster,
            action_type=action_type,
            fingerprint=fingerprint,
            status="skipped_duplicate_existing",
            project_id=project_id,
            action=action,
            judge_reasoning=duplicate.reason,
            supporting_message_ids=source_message_ids,
            source_occurred_at_utc=source_occurred_at_utc,
            applied_payload={
                "matched_candidate_type": duplicate.matched_candidate_type,
                "matched_candidate_id": duplicate.matched_candidate_id,
            },
            **target_kwargs,
        )

    async def _apply_todo_create(
        self,
        *,
        run: IMessageProcessingRun,
        cluster: MessageCluster,
        project_id: int | None,
        action: dict[str, Any],
        time_zone: str,
    ) -> bool:
        text = str(action.get("text") or "").strip()
        if not text:
            return False
        deadline = self._parse_dt(action.get("deadline_utc"))
        source_message_ids = self._normalize_action_source_message_ids(
            cluster.messages,
            "todo.create",
            action,
        )
        created_at = self._action_source_occurred_at_utc(
            cluster=cluster,
            action_type="todo.create",
            action=action,
            source_message_ids=source_message_ids,
        ) or self._cluster_reference_time_utc(cluster=cluster)
        fingerprint = stable_fingerprint(
            "todo.create",
            cluster.conversation.id,
            text.lower(),
            deadline.isoformat() if deadline else None,
        )
        if await self._audit_exists(run.user_id, fingerprint):
            return False
        inbox = await self.project_repo.ensure_inbox_project(run.user_id)
        todo = await self.todo_repo.create_one(
            run.user_id,
            project_id or inbox.id,
            text,
            deadline,
            deadline_is_date_only=bool(action.get("deadline_is_date_only", False)),
            created_at=created_at,
        )
        await self.session.flush()
        if todo.deadline_utc is not None and not todo.completed:
            try:
                from app.services.todo_calendar_link_service import TodoCalendarLinkService

                await TodoCalendarLinkService(self.session).upsert_event_for_todo(todo, time_zone=time_zone)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[imessage] failed to mirror todo deadline to calendar: {}", exc)
        await self._record_action_audit(
            run=run,
            cluster=cluster,
            action_type="todo.create",
            fingerprint=fingerprint,
            status="applied",
            project_id=project_id or inbox.id,
            target_todo_id=todo.id,
            action=action,
            supporting_message_ids=source_message_ids,
            source_occurred_at_utc=created_at,
            applied=True,
        )
        return True

    async def _apply_todo_completion(
        self,
        *,
        run: IMessageProcessingRun,
        cluster: MessageCluster,
        project_id: int | None,
        action: dict[str, Any],
        time_zone: str,
    ) -> bool:
        target = await self._find_todo_to_complete(
            user_id=run.user_id,
            conversation_id=cluster.conversation.id,
            project_id=project_id,
            match_text=str(action.get("match_text") or ""),
        )
        if target is None or target.completed:
            return False
        source_message_ids = self._normalize_action_source_message_ids(
            cluster.messages,
            "todo.complete",
            action,
        )
        completed_at_utc = self._action_source_occurred_at_utc(
            cluster=cluster,
            action_type="todo.complete",
            action=action,
            source_message_ids=source_message_ids,
        )
        fingerprint = stable_fingerprint(
            "todo.complete",
            cluster.conversation.id,
            target.id,
            source_message_ids or [cluster.messages[-1].id],
        )
        if await self._audit_exists(run.user_id, fingerprint):
            return False
        target.mark_completed(True, completed_at_utc=completed_at_utc)
        target.completed_time_zone = time_zone
        if target.completed_at_utc:
            target.completed_local_date = target.completed_at_utc.astimezone(resolve_time_zone(time_zone)).date()
        if not target.accomplishment_text:
            try:
                target.accomplishment_text = await self.todo_accomplishment_agent.rewrite(target.text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[imessage] failed to generate accomplishment text: {}", exc)
                target.accomplishment_text = f"Completed {target.text}".strip()
            target.accomplishment_generated_at_utc = datetime.now(timezone.utc)
        try:
            from app.services.todo_calendar_link_service import TodoCalendarLinkService

            await TodoCalendarLinkService(self.session).unlink_todo(target, delete_event=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[imessage] failed to unlink completed todo from calendar: {}", exc)
        await self._record_action_audit(
            run=run,
            cluster=cluster,
            action_type="todo.complete",
            fingerprint=fingerprint,
            status="applied",
            project_id=target.project_id,
            target_todo_id=target.id,
            action=action,
            supporting_message_ids=source_message_ids,
            source_occurred_at_utc=completed_at_utc,
            applied=True,
        )
        return True

    async def _apply_calendar_create(
        self,
        *,
        run: IMessageProcessingRun,
        cluster: MessageCluster,
        project_id: int | None,
        action: dict[str, Any],
    ) -> bool:
        summary = str(action.get("summary") or "").strip()
        start = self._parse_dt(action.get("start_time"))
        end = self._parse_dt(action.get("end_time"))
        if not summary or start is None or end is None or end <= start:
            return False
        source_message_ids = self._normalize_action_source_message_ids(
            cluster.messages,
            "calendar.create",
            action,
        )
        source_occurred_at_utc = self._action_source_occurred_at_utc(
            cluster=cluster,
            action_type="calendar.create",
            action=action,
            source_message_ids=source_message_ids,
        )
        fingerprint = stable_fingerprint("calendar.create", cluster.conversation.id, summary.lower(), start.isoformat(), end.isoformat())
        if await self._audit_exists(run.user_id, fingerprint):
            return False
        try:
            _, event = await self.calendar_service.create_event_in_life_dashboard(
                run.user_id,
                summary=summary,
                start_time=start,
                end_time=end,
                is_all_day=bool(action.get("is_all_day", False)),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[imessage] calendar create skipped: {}", exc)
            await self._record_action_audit(
                run=run,
                cluster=cluster,
                action_type="calendar.create",
                fingerprint=fingerprint,
                status="skipped_missing_calendar",
                project_id=project_id,
                action=action,
                judge_reasoning=str(exc),
                supporting_message_ids=source_message_ids,
                source_occurred_at_utc=source_occurred_at_utc,
            )
            return False
        await self._record_action_audit(
            run=run,
            cluster=cluster,
            action_type="calendar.create",
            fingerprint=fingerprint,
            status="applied",
            project_id=project_id,
            target_calendar_event_id=event.id,
            action=action,
            supporting_message_ids=source_message_ids,
            source_occurred_at_utc=source_occurred_at_utc,
            applied=True,
        )
        return True

    async def _apply_journal_entry(
        self,
        *,
        run: IMessageProcessingRun,
        cluster: MessageCluster,
        action: dict[str, Any],
        time_zone: str,
    ) -> bool:
        text = str(action.get("text") or "").strip()
        if not text:
            return False
        source_message_ids = self._normalize_action_source_message_ids(
            cluster.messages,
            "journal.entry",
            action,
        )
        occurred_at_utc = self._action_source_occurred_at_utc(
            cluster=cluster,
            action_type="journal.entry",
            action=action,
            source_message_ids=source_message_ids,
        ) or self._cluster_reference_time_utc(cluster=cluster, prefer_user_messages=True)
        local_date = occurred_at_utc.astimezone(resolve_time_zone(time_zone)).date().isoformat()
        fingerprint = stable_fingerprint("journal.entry", cluster.conversation.id, text.lower(), local_date)
        if await self._audit_exists(run.user_id, fingerprint):
            return False
        result = await self.journal_service.add_entry(
            user_id=run.user_id,
            text=text,
            time_zone=time_zone,
            occurred_at_utc=occurred_at_utc,
        )
        entry = result["entry"]
        await self._record_action_audit(
            run=run,
            cluster=cluster,
            action_type="journal.entry",
            fingerprint=fingerprint,
            status="applied",
            target_journal_entry_id=entry.id,
            action=action,
            supporting_message_ids=source_message_ids,
            source_occurred_at_utc=occurred_at_utc,
            applied=True,
        )
        return True

    async def _apply_workspace_update(
        self,
        *,
        run: IMessageProcessingRun,
        cluster: MessageCluster,
        project_id: int | None,
        action: dict[str, Any],
    ) -> bool:
        if project_id is None:
            await self._record_non_applied_action(
                run=run,
                cluster=cluster,
                action_type="workspace.update",
                action=action,
                status="skipped_no_project",
                project_id=None,
                judge_reasoning="Workspace knowledge updates require a confident project inference.",
            )
            return False
        project_page = await self.workspace_service.find_project_page(run.user_id, project_id)
        if project_page is None:
            await self._record_non_applied_action(
                run=run,
                cluster=cluster,
                action_type="workspace.update",
                action=action,
                status="skipped_missing_project_page",
                project_id=project_id,
                judge_reasoning="No workspace project page exists for the inferred project.",
            )
            return False
        fingerprint = stable_fingerprint(
            "workspace.update",
            cluster.conversation.id,
            project_id,
            str(action.get("page_title") or "").lower(),
            str(action.get("summary") or "").lower(),
        )
        if await self._audit_exists(run.user_id, fingerprint):
            return False
        source_message_ids = self._normalize_action_source_message_ids(
            cluster.messages,
            "workspace.update",
            action,
        )
        source_occurred_at_utc = self._action_source_occurred_at_utc(
            cluster=cluster,
            action_type="workspace.update",
            action=action,
            source_message_ids=source_message_ids,
        )
        candidate_pages = await self.workspace_service.list_page_subtree(
            run.user_id,
            project_page.id,
            include_root=False,
        )
        selection = await self._select_page_destination(
            project_page=project_page,
            candidates=[page for page in candidate_pages if page.kind in {"note", "page"}],
            action=action,
        )
        if selection.get("mode") == "skip":
            await self._record_action_audit(
                run=run,
                cluster=cluster,
                action_type="workspace.update",
                fingerprint=fingerprint,
                status="skipped",
                project_id=project_id,
                action=action,
                judge_reasoning=str(selection.get("reason") or "Selection policy skipped the update."),
                supporting_message_ids=source_message_ids,
                source_occurred_at_utc=source_occurred_at_utc,
            )
            return False

        target_page_id: int | None
        applied_payload: dict[str, Any]
        if selection.get("mode") == "create_new":
            created = await self.workspace_service.create_page(
                run.user_id,
                title=str(selection.get("title") or action.get("page_title") or "Project Update").strip(),
                parent_page_id=project_page.id,
                kind="note",
                icon="🧠",
                show_in_sidebar=True,
                extra_json={"engine": {"source": "imessage", "managed": True}},
            )
            target_page_id = created.id
            existing_body = ""
            merged = await self._merge_page_body(
                existing_body=existing_body,
                action=action,
                project_page_title=project_page.title,
            )
            await self.workspace_service.replace_page_body(run.user_id, target_page_id, merged["body"])
            applied_payload = {
                **merged,
                "mode": "create_new",
                "selection_reason": str(selection.get("reason") or ""),
            }
        else:
            target_page_id = int(selection.get("page_id"))
            target_page = next((page for page in candidate_pages if page.id == target_page_id), None)
            if target_page is None:
                await self._record_action_audit(
                    run=run,
                    cluster=cluster,
                    action_type="workspace.update",
                    fingerprint=fingerprint,
                    status="skipped_invalid_target",
                    project_id=project_id,
                    action=action,
                    judge_reasoning="Selected page was not found in the project subtree.",
                    supporting_message_ids=source_message_ids,
                    source_occurred_at_utc=source_occurred_at_utc,
                )
                return False
            if self._is_engine_managed_page(target_page):
                existing_body = await self.workspace_service.get_page_text_body(run.user_id, target_page_id)
                merged = await self._merge_page_body(
                    existing_body=existing_body,
                    action=action,
                    project_page_title=project_page.title,
                )
                await self.workspace_service.replace_page_body(run.user_id, target_page_id, merged["body"])
                applied_payload = {
                    **merged,
                    "mode": "replace_engine_page",
                    "selection_reason": str(selection.get("reason") or ""),
                }
            else:
                appended = await self._append_workspace_update_block(
                    user_id=run.user_id,
                    page_id=target_page_id,
                    text=str(action.get("summary") or "").strip(),
                )
                if not appended:
                    await self._record_action_audit(
                        run=run,
                        cluster=cluster,
                        action_type="workspace.update",
                        fingerprint=fingerprint,
                        status="skipped_duplicate_content",
                        project_id=project_id,
                        action=action,
                        target_page_id=target_page_id,
                        judge_reasoning="The target page already contains the proposed update text.",
                        supporting_message_ids=source_message_ids,
                        source_occurred_at_utc=source_occurred_at_utc,
                    )
                    return False
                applied_payload = {
                    "mode": "append_block",
                    "body": str(action.get("summary") or "").strip(),
                    "title": target_page.title,
                    "reason": "Appended a new block to preserve existing page structure.",
                    "selection_reason": str(selection.get("reason") or ""),
                }
        await self._record_action_audit(
            run=run,
            cluster=cluster,
            action_type="workspace.update",
            fingerprint=fingerprint,
            status="applied",
            project_id=project_id,
            target_page_id=target_page_id,
            action=action,
            applied_payload=applied_payload,
            supporting_message_ids=source_message_ids,
            source_occurred_at_utc=source_occurred_at_utc,
            applied=True,
        )
        return True

    async def _select_page_destination(
        self,
        *,
        project_page,
        candidates: list,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        candidate_payload = [
            {
                "id": page.id,
                "title": page.title,
                "kind": page.kind,
                "description": page.description,
                "engine_managed": self._is_engine_managed_page(page),
                "updated_at": page.updated_at.isoformat() if page.updated_at else None,
            }
            for page in candidates
        ][:25]
        heuristic_match = self._heuristic_page_selection(candidates, action)
        payload = {
            "project_page": {
                "id": project_page.id,
                "title": project_page.title,
            },
            "heuristic": heuristic_match,
            "candidates": candidate_payload,
            "update": action,
        }
        if self.client is None:
            return heuristic_match
        prompt = IMESSAGE_PAGE_SELECTION_PROMPT.replace(
            "{payload_json}",
            json.dumps(payload, ensure_ascii=False),
        )
        try:
            parsed = await self._invoke_model(prompt, IMessagePageSelectionOutput)
        except Exception:
            return heuristic_match
        parsed_payload = parsed.model_dump()
        if parsed.mode in {"update_existing", "create_new", "skip"}:
            if parsed.mode == "update_existing":
                candidate_ids = {page.id for page in candidates}
                if int(parsed.page_id or 0) not in candidate_ids:
                    return heuristic_match
            return parsed_payload
        return heuristic_match

    def _heuristic_page_selection(self, candidates: list, action: dict[str, Any]) -> dict[str, Any]:
        requested_title = str(action.get("page_title") or "").strip().lower()
        search_query = str(action.get("search_query") or "").strip().lower()
        if not requested_title:
            return {"mode": "skip", "page_id": None, "title": None, "reason": "No page title provided."}
        best_score = 0.0
        best_page = None
        for page in candidates:
            title = page.title.strip().lower()
            description = str(page.description or "").strip().lower()
            score = SequenceMatcher(None, requested_title, title).ratio()
            if requested_title in title or title in requested_title:
                score += 0.2
            if search_query and search_query in title:
                score += 0.15
            if search_query and search_query in description:
                score += 0.1
            if self._is_engine_managed_page(page):
                score += 0.05
            if score > best_score:
                best_score = score
                best_page = page
        if best_page is not None and best_score >= 0.72:
            return {
                "mode": "update_existing",
                "page_id": best_page.id,
                "title": None,
                "reason": "Best title similarity match in the project subtree.",
            }
        return {
            "mode": "create_new",
            "page_id": None,
            "title": str(action.get("page_title") or "").strip(),
            "reason": "No strong existing page match found.",
        }

    async def _merge_page_body(
        self,
        *,
        existing_body: str,
        action: dict[str, Any],
        project_page_title: str,
    ) -> dict[str, str]:
        heuristic = {
            "title": str(action.get("page_title") or project_page_title).strip(),
            "body": self._heuristic_merge(existing_body, action),
            "reason": "Heuristic merge fallback.",
        }
        if self.client is None:
            return heuristic
        payload = {
            "project_title": project_page_title,
            "existing_body": existing_body,
            "update": action,
        }
        prompt = IMESSAGE_PAGE_MERGE_PROMPT.replace(
            "{payload_json}",
            json.dumps(payload, ensure_ascii=False),
        )
        try:
            parsed = await self._invoke_model(prompt, IMessagePageMergeOutput)
        except Exception:
            return heuristic
        if parsed.body:
            return {
                "title": (parsed.title or heuristic["title"]).strip(),
                "body": (parsed.body or heuristic["body"]).strip(),
                "reason": parsed.reason or "",
            }
        return heuristic

    def _heuristic_merge(self, existing_body: str, action: dict[str, Any]) -> str:
        summary = str(action.get("summary") or "").strip()
        if not existing_body.strip():
            return summary
        if summary and summary.lower() in existing_body.lower():
            return existing_body
        if not summary:
            return existing_body
        return f"{existing_body.strip()}\n\n{summary}"

    def _is_engine_managed_page(self, page: Any) -> bool:
        extra_json = getattr(page, "extra_json", None)
        if not isinstance(extra_json, dict):
            return False
        engine = extra_json.get("engine")
        return isinstance(engine, dict) and engine.get("source") == "imessage"

    async def _append_workspace_update_block(self, *, user_id: int, page_id: int, text: str) -> bool:
        normalized = text.strip()
        if not normalized:
            return False
        detail = await self.workspace_service.get_page_detail(user_id, page_id)
        if any(block.text_content.strip().lower() == normalized.lower() for block in detail.blocks):
            return False
        if len(detail.blocks) == 1 and not detail.blocks[0].text_content.strip():
            await self.workspace_service.update_block(
                user_id,
                detail.blocks[0].id,
                text_content=normalized,
            )
            return True
        after_block_id = detail.blocks[-1].id if detail.blocks else None
        await self.workspace_service.create_block(
            user_id,
            page_id=page_id,
            after_block_id=after_block_id,
            block_type="paragraph",
            text_content=normalized,
            checked=False,
            data_json=None,
        )
        return True

    async def _find_todo_to_complete(
        self,
        *,
        user_id: int,
        conversation_id: int,
        project_id: int | None,
        match_text: str,
    ) -> TodoItem | None:
        recent_stmt = (
            select(IMessageActionAudit)
            .where(
                IMessageActionAudit.user_id == user_id,
                IMessageActionAudit.conversation_id == conversation_id,
                IMessageActionAudit.action_type == "todo.create",
                IMessageActionAudit.status == "applied",
                IMessageActionAudit.target_todo_id.is_not(None),
            )
            .order_by(IMessageActionAudit.created_at.desc())
            .limit(10)
        )
        recent_result = await self.session.execute(recent_stmt)
        recent_audits = list(recent_result.scalars().all())
        todo_candidates: list[TodoItem] = []
        for audit in recent_audits:
            if audit.target_todo_id is None:
                continue
            todo = await self.todo_repo.get_for_user(user_id, audit.target_todo_id)
            if todo is not None and not todo.completed:
                todo_candidates.append(todo)
        if match_text:
            matched = choose_best_todo_match(candidate_text=match_text, todos=todo_candidates)
            if matched is not None:
                return matched
        if todo_candidates:
            return todo_candidates[0]

        all_todos = await self.todo_repo.list_for_user(user_id)
        open_todos = [todo for todo in all_todos if not todo.completed]
        if project_id is not None:
            open_todos = [todo for todo in open_todos if todo.project_id == project_id] or open_todos
        return choose_best_todo_match(candidate_text=match_text, todos=open_todos)

    async def _audit_exists(self, user_id: int, fingerprint: str) -> bool:
        stmt = select(IMessageActionAudit.id).where(
            IMessageActionAudit.user_id == user_id,
            IMessageActionAudit.action_fingerprint == fingerprint,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def _record_action_audit(
        self,
        *,
        run: IMessageProcessingRun,
        cluster: MessageCluster,
        action_type: str,
        fingerprint: str,
        status: str,
        action: dict[str, Any],
        project_id: int | None = None,
        target_page_id: int | None = None,
        target_todo_id: int | None = None,
        target_calendar_event_id: int | None = None,
        target_journal_entry_id: int | None = None,
        applied_payload: dict[str, Any] | None = None,
        judge_reasoning: str | None = None,
        rationale: str | None = None,
        supporting_message_ids: list[int] | None = None,
        source_occurred_at_utc: datetime | None = None,
        applied: bool = False,
    ) -> None:
        self.session.add(
            IMessageActionAudit(
                user_id=run.user_id,
                processing_run_id=run.id,
                conversation_id=cluster.conversation.id,
                action_type=action_type,
                action_fingerprint=fingerprint,
                status=status,
                project_id=project_id,
                target_page_id=target_page_id,
                target_todo_id=target_todo_id,
                target_calendar_event_id=target_calendar_event_id,
                target_journal_entry_id=target_journal_entry_id,
                supporting_message_ids_json=supporting_message_ids
                if supporting_message_ids is not None
                else [message.id for message in cluster.messages],
                extracted_payload=action,
                applied_payload=applied_payload,
                rationale=rationale or str(action.get("reason") or ""),
                judge_reasoning=judge_reasoning,
                source_occurred_at_utc=source_occurred_at_utc,
                applied_at_utc=datetime.now(timezone.utc) if applied else None,
            )
        )
        await self.session.commit()

    async def _call_model(self, prompt: str, response_model):
        if self.client is None:
            raise ValueError("OpenAI client is not available.")
        result = await self.client.generate_json(
            prompt,
            response_model=response_model,
            temperature=0.0,
        )
        return result.data

    async def _invoke_model(self, prompt: str, response_model: type[BaseModel]):
        model_call = self._call_model
        try:
            parameter_count = len(signature(model_call).parameters)
        except (TypeError, ValueError):
            parameter_count = 2

        if parameter_count <= 1:
            raw_result = await model_call(prompt)
        else:
            raw_result = await model_call(prompt, response_model)

        if isinstance(raw_result, response_model):
            return raw_result
        if isinstance(raw_result, str):
            return response_model.model_validate_json(raw_result)
        if isinstance(raw_result, BaseModel):
            return response_model.model_validate(raw_result.model_dump())
        return response_model.model_validate(raw_result)

    def _parse_dt(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
