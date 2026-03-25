"""Historical completion reconciliation for iMessage-created todos."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.imessage import IMessageActionAudit, IMessageMessage
from app.db.models.todo import TodoItem
from app.db.repositories.todo_repository import TodoRepository
from app.services.imessage_utils import content_tokens, looks_like_completion, normalize_message_text, stable_fingerprint
from app.services.todo_accomplishment_agent import TodoAccomplishmentAgent
from app.utils.timezone import resolve_time_zone


_GENERIC_COMPLETION_MESSAGES = {
    "done",
    "done.",
    "done!",
    "done!!",
    "all done",
    "all done.",
    "all set",
    "all set.",
    "all good",
    "all good.",
    "got it",
    "got it.",
    "got it done",
    "got it done.",
    "handled it",
    "handled it.",
    "took care of it",
    "took care of it.",
    "finished it",
    "finished it.",
    "sent it",
    "sent it.",
    "paid it",
    "paid it.",
    "booked it",
    "booked it.",
    "reserved it",
    "reserved it.",
    "settled up",
    "settled up.",
    "squared up",
    "squared up.",
    "yep did it",
    "yeah i did",
    "yeah i did.",
}
_ACTION_UPDATE_RE = re.compile(
    r"^(?:i\s+)?(?:asked|booked|called|emailed|met|replied|scheduled|submitted|texted|told)\b",
    re.IGNORECASE,
)
_GENERIC_TASK_TOKENS = {
    "ask",
    "asked",
    "book",
    "booked",
    "call",
    "called",
    "message",
    "messaged",
    "pay",
    "paid",
    "plan",
    "planned",
    "reply",
    "replied",
    "research",
    "researched",
    "send",
    "sent",
    "tell",
    "text",
    "texted",
    "watch",
    "watched",
}
_TOKEN_CANONICAL_MAP = {
    "asked": "ask",
    "booked": "book",
    "called": "call",
    "messaged": "message",
    "paid": "pay",
    "planned": "plan",
    "replied": "reply",
    "researching": "research",
    "researched": "research",
    "sending": "send",
    "sent": "send",
    "talked": "talk",
    "telling": "tell",
    "texted": "text",
    "watched": "watch",
    "went": "go",
}
_FOLLOWUP_WINDOW = timedelta(days=21)


@dataclass(slots=True, frozen=True)
class HistoricalTodoCompletionProposal:
    todo_id: int
    conversation_id: int
    source_audit_id: int
    completion_message_id: int
    completed_at_utc: datetime
    completion_message_text: str
    score: float
    reason: str


class IMessageTodoReconciliationService:
    """Find and apply historical completions for iMessage-created todos."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.todo_repo = TodoRepository(session)
        self.todo_accomplishment_agent = TodoAccomplishmentAgent()

    async def list_completion_proposals(
        self,
        *,
        user_id: int,
        after_audit_id: int = 0,
        limit: int = 0,
        batch_size: int = 100,
        since_utc: datetime | None = None,
        max_followup_messages: int = 200,
    ) -> list[HistoricalTodoCompletionProposal]:
        proposals: list[HistoricalTodoCompletionProposal] = []
        processed = 0
        cursor = after_audit_id

        while True:
            stmt = (
                select(IMessageActionAudit)
                .where(
                    IMessageActionAudit.user_id == user_id,
                    IMessageActionAudit.action_type == "todo.create",
                    IMessageActionAudit.status == "applied",
                    IMessageActionAudit.target_todo_id.is_not(None),
                    IMessageActionAudit.conversation_id.is_not(None),
                    IMessageActionAudit.id > cursor,
                )
                .order_by(IMessageActionAudit.id.asc())
                .limit(batch_size)
            )
            if since_utc is not None:
                stmt = stmt.where(
                    or_(
                        IMessageActionAudit.source_occurred_at_utc >= since_utc,
                        (
                            IMessageActionAudit.source_occurred_at_utc.is_(None)
                            & (IMessageActionAudit.created_at >= since_utc)
                        ),
                    )
                )
            audits = list((await self.session.execute(stmt)).scalars().all())
            if not audits:
                break

            for audit in audits:
                cursor = audit.id
                processed += 1
                if limit and processed > limit:
                    return proposals
                if audit.target_todo_id is None or audit.conversation_id is None:
                    continue
                todo = await self.todo_repo.get_for_user(user_id, audit.target_todo_id)
                if todo is None or todo.completed:
                    continue
                proposal = await self._build_proposal_for_audit(
                    user_id=user_id,
                    todo=todo,
                    audit=audit,
                    max_followup_messages=max_followup_messages,
                )
                if proposal is not None:
                    proposals.append(proposal)
            if limit and processed >= limit:
                break

        return proposals

    async def apply_proposal(
        self,
        *,
        user_id: int,
        proposal: HistoricalTodoCompletionProposal,
        time_zone: str,
    ) -> bool:
        todo = await self.todo_repo.get_for_user(user_id, proposal.todo_id)
        if todo is None or todo.completed:
            return False
        fingerprint = stable_fingerprint(
            "todo.complete.reconcile",
            proposal.conversation_id,
            proposal.todo_id,
            proposal.completion_message_id,
        )
        if await self._completion_audit_exists(user_id=user_id, fingerprint=fingerprint):
            return False

        todo.mark_completed(True, completed_at_utc=proposal.completed_at_utc)
        todo.completed_time_zone = time_zone
        todo.completed_local_date = proposal.completed_at_utc.astimezone(
            resolve_time_zone(time_zone)
        ).date()
        if not todo.accomplishment_text:
            try:
                todo.accomplishment_text = await self.todo_accomplishment_agent.rewrite(todo.text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[imessage][todo-reconcile] failed to generate accomplishment: {}", exc)
                todo.accomplishment_text = f"Completed {todo.text}".strip()
            todo.accomplishment_generated_at_utc = datetime.now(timezone.utc)

        try:
            from app.services.todo_calendar_link_service import TodoCalendarLinkService

            await TodoCalendarLinkService(self.session).unlink_todo(todo, delete_event=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[imessage][todo-reconcile] failed to unlink calendar event: {}", exc)

        self.session.add(
            IMessageActionAudit(
                user_id=user_id,
                processing_run_id=None,
                conversation_id=proposal.conversation_id,
                action_type="todo.complete",
                action_fingerprint=fingerprint,
                status="applied",
                project_id=todo.project_id,
                target_todo_id=todo.id,
                supporting_message_ids_json=[proposal.completion_message_id],
                extracted_payload={
                    "match_text": todo.text,
                    "reason": proposal.reason,
                    "source_message_ids": [proposal.completion_message_id],
                },
                applied_payload={
                    "todo_id": todo.id,
                    "completed_at_utc": proposal.completed_at_utc.isoformat(),
                    "reason": proposal.reason,
                },
                rationale=proposal.reason,
                judge_reasoning="Applied by historical todo reconciliation script.",
                source_occurred_at_utc=proposal.completed_at_utc,
                applied_at_utc=datetime.now(timezone.utc),
            )
        )
        return True

    async def _build_proposal_for_audit(
        self,
        *,
        user_id: int,
        todo: TodoItem,
        audit: IMessageActionAudit,
        max_followup_messages: int,
    ) -> HistoricalTodoCompletionProposal | None:
        if audit.conversation_id is None:
            return None
        created_at = audit.source_occurred_at_utc or todo.created_at
        if created_at is None:
            return None
        messages = await self._load_followup_messages(
            user_id=user_id,
            conversation_id=audit.conversation_id,
            created_at=created_at,
            max_followup_messages=max_followup_messages,
        )
        if not messages:
            return None

        open_count = await self._open_todo_count_for_conversation(
            user_id=user_id,
            conversation_id=audit.conversation_id,
        )
        best_message: IMessageMessage | None = None
        best_score = 0.0
        best_reason = ""
        for message in messages:
            score, reason = score_completion_match(
                todo_text=todo.text,
                message_text=message.text,
                is_from_me=message.is_from_me,
                open_todos_in_conversation=open_count,
            )
            if score > best_score:
                best_message = message
                best_score = score
                best_reason = reason
        if best_message is None or best_message.sent_at_utc is None:
            return None
        return HistoricalTodoCompletionProposal(
            todo_id=todo.id,
            conversation_id=audit.conversation_id,
            source_audit_id=audit.id,
            completion_message_id=best_message.id,
            completed_at_utc=best_message.sent_at_utc,
            completion_message_text=normalize_message_text(best_message.text),
            score=best_score,
            reason=best_reason,
        )

    async def _load_followup_messages(
        self,
        *,
        user_id: int,
        conversation_id: int,
        created_at: datetime,
        max_followup_messages: int,
    ) -> list[IMessageMessage]:
        stmt = (
            select(IMessageMessage)
            .where(
                IMessageMessage.user_id == user_id,
                IMessageMessage.conversation_id == conversation_id,
                IMessageMessage.sent_at_utc.is_not(None),
                IMessageMessage.sent_at_utc > created_at,
                IMessageMessage.sent_at_utc <= created_at + _FOLLOWUP_WINDOW,
                or_(
                    IMessageMessage.text.is_not(None),
                    IMessageMessage.normalized_text.is_not(None),
                ),
            )
            .order_by(IMessageMessage.sent_at_utc.asc(), IMessageMessage.id.asc())
            .limit(max_followup_messages)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def _open_todo_count_for_conversation(self, *, user_id: int, conversation_id: int) -> int:
        stmt = (
            select(func.count(TodoItem.id))
            .select_from(IMessageActionAudit)
            .join(TodoItem, TodoItem.id == IMessageActionAudit.target_todo_id)
            .where(
                IMessageActionAudit.user_id == user_id,
                IMessageActionAudit.conversation_id == conversation_id,
                IMessageActionAudit.action_type == "todo.create",
                IMessageActionAudit.status == "applied",
                TodoItem.completed.is_(False),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def _completion_audit_exists(self, *, user_id: int, fingerprint: str) -> bool:
        stmt = select(IMessageActionAudit.id).where(
            IMessageActionAudit.user_id == user_id,
            IMessageActionAudit.action_fingerprint == fingerprint,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None


def score_completion_match(
    *,
    todo_text: str,
    message_text: str | None,
    is_from_me: bool,
    open_todos_in_conversation: int,
) -> tuple[float, str]:
    normalized_message = normalize_message_text(message_text)
    if not is_from_me or not normalized_message:
        return 0.0, "Completion evidence must come from an outgoing message with text."
    explicit_completion = looks_like_completion(normalized_message)
    bare_confirmation = normalized_message.lower() in _GENERIC_COMPLETION_MESSAGES
    action_update = bool(_ACTION_UPDATE_RE.search(normalized_message))
    if not explicit_completion and not bare_confirmation and not action_update:
        return 0.0, "Message does not contain completion-like language."

    todo_tokens = _canonical_tokens(todo_text)
    message_tokens = _canonical_tokens(normalized_message)
    if not todo_tokens and not bare_confirmation:
        return 0.0, "Todo does not contain enough specific content to match safely."

    overlap = todo_tokens & message_tokens
    overlap_ratio = len(overlap) / max(len(todo_tokens), 1)
    score = 0.0
    reasons: list[str] = []

    if explicit_completion:
        score += 0.34
        reasons.append("outgoing message uses completion language")
    elif action_update:
        score += 0.24
        reasons.append("outgoing message sounds like a first-person action update")
    if overlap_ratio > 0:
        score += min(0.46, overlap_ratio * 0.7)
        reasons.append(f"shares specific todo details: {', '.join(sorted(overlap))}")
    if any(token in message_tokens for token in _named_tokens(todo_text)):
        score += 0.12
        reasons.append("includes the same person or subject token")
    if bare_confirmation and open_todos_in_conversation <= 1:
        score += 0.22
        reasons.append("single open todo in the conversation makes a short confirmation safe enough")
    if normalize_message_text(todo_text).lower() in normalized_message.lower():
        score += 0.2
        reasons.append("message repeats the todo phrasing directly")

    threshold = 0.58
    if bare_confirmation and open_todos_in_conversation <= 1:
        threshold = 0.52
    if score < threshold:
        return 0.0, "; ".join(reasons) or "Not enough overlap with the original todo."
    return score, "; ".join(reasons)


def _canonical_tokens(text: str | None) -> set[str]:
    tokens = content_tokens(text)
    normalized: set[str] = set()
    for token in tokens:
        mapped = _TOKEN_CANONICAL_MAP.get(token, token)
        if mapped in _GENERIC_TASK_TOKENS:
            continue
        normalized.add(mapped)
    return normalized


def _named_tokens(text: str | None) -> set[str]:
    normalized = normalize_message_text(text)
    tokens = {token for token in normalized.split() if token[:1].isupper() and len(token) > 2}
    lower_named = {token.lower().strip(".,!?") for token in tokens}
    return {token for token in lower_named if token}
