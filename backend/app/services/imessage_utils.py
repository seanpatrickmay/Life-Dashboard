"""Shared helpers for iMessage sync + processing."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import json
import re
from typing import Any, Sequence


APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=UTC)
_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_PRINTABLE_BLOB_RE = re.compile(rb"[\x20-\x7E]{2,}")
_ARCHIVE_CONTENT_RE = re.compile(
    r"NSString(?:\+.)?(.+?)(?=(?:(?:NS)?Dictionary|__kIM|NSNumber|NSValue|$))",
    re.DOTALL,
)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1F\x7F]+")
_COMPLETION_RE = re.compile(
    r"\b(done|completed|paid|sent|handled|took care of it|finished|resolved)\b",
    re.IGNORECASE,
)
_CLUSTER_BOUNDARY_CUE_RE = re.compile(
    r"^\s*(switching gears|on another note|another thing|different topic|separately|side note|unrelated|btw|by the way)\b",
    re.IGNORECASE,
)
_LOW_SIGNAL_TEXT_RE = re.compile(
    r"^(ok|okay|sounds good|sgtm|thanks|thank you|yep|yes|cool|perfect|great|got it|works for me)[.!]*$",
    re.IGNORECASE,
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "but",
    "by",
    "can",
    "for",
    "from",
    "get",
    "got",
    "have",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "just",
    "lets",
    "me",
    "my",
    "need",
    "of",
    "on",
    "or",
    "our",
    "should",
    "that",
    "the",
    "this",
    "to",
    "too",
    "up",
    "we",
    "with",
    "you",
    "your",
}
_INTENT_LEXICONS = {
    "calendar": {
        "calendar",
        "call",
        "confirmed",
        "meet",
        "meeting",
        "review",
        "schedule",
        "scheduled",
        "tomorrow",
        "tonight",
        "walkthrough",
        "zoom",
    },
    "finance": {
        "budget",
        "invoice",
        "paid",
        "pay",
        "quote",
        "reimburse",
        "splitwise",
        "venmo",
    },
    "knowledge": {
        "architecture",
        "constraints",
        "county",
        "design",
        "permit",
        "pdf",
        "plan",
        "rollout",
        "spec",
        "vendor",
    },
    "completion": {
        "completed",
        "done",
        "finished",
        "handled",
        "paid",
        "resolved",
        "sent",
    },
}
_ARCHIVE_STRING_TOKENS = {
    "streamtyped",
    "NSMutableAttributedString",
    "NSAttributedString",
    "NSObject",
    "NSMutableString",
    "NSString",
    "NSDictionary",
    "NSNumber",
    "NSValue",
    "__kIMMessagePartAttributeName",
    "__kIMCalendarEventAttributeName",
    "__kIMOneTimeCodeAttributeName",
    "bplist00",
}
_REACTION_ASSOCIATED_TYPES = {2000, 2001, 2002, 2003, 2004, 2005, 3000}


@dataclass
class ProjectGuess:
    project_name: str | None
    confidence: float
    reason: str
    candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectCatalogEntry:
    name: str
    aliases: tuple[str, ...] = ()
    notes: str | None = None
    conversation_affinity: float = 0.0


@dataclass(frozen=True)
class ProjectCandidate:
    project_name: str
    score: float
    reasons: tuple[str, ...]
    aliases: tuple[str, ...]


def apple_timestamp_to_datetime(value: int | float | str | None) -> datetime | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        raw = int(value)
    except (TypeError, ValueError):
        return None
    for divisor in (1_000_000_000, 1_000_000, 1_000, 1):
        candidate = APPLE_EPOCH + timedelta(seconds=raw / divisor)
        if 2005 <= candidate.year <= 2100:
            return candidate
    return None


def normalize_message_text(text: str | None) -> str:
    if not text:
        return ""
    sanitized = text.replace("\uFFFC", " ").replace("\x00", " ")
    return _WHITESPACE_RE.sub(" ", sanitized.strip())


def extract_attributed_body_text(blob: bytes | bytearray | memoryview | None) -> str | None:
    if blob is None:
        return None
    if isinstance(blob, memoryview):
        raw = blob.tobytes()
    elif isinstance(blob, bytearray):
        raw = bytes(blob)
    else:
        raw = blob

    candidates: list[str] = []
    seen: set[str] = set()

    def _push_candidate(text: str) -> None:
        if not text:
            return
        if text in _ARCHIVE_STRING_TOKENS or text.startswith("__kIM"):
            return
        if re.fullmatch(r"[A-F0-9-]{16,}", text):
            return
        if text.startswith("chat") and text[4:].isdigit():
            return
        cleaned = _CONTROL_CHAR_RE.sub(" ", text)
        cleaned = cleaned.strip()
        cleaned = re.sub(r"^\+.(?=[A-Za-z\"'])", "", cleaned)
        cleaned = re.sub(r"(?:\s+|\n+)iI(?:\s+\S{1,2})?$", "", cleaned)
        cleaned = normalize_message_text(cleaned)
        if not cleaned:
            return
        if cleaned in _ARCHIVE_STRING_TOKENS or cleaned.startswith("__kIM"):
            return
        lowered = cleaned.lower()
        if lowered in {"nsattributedstring", "nsmutablestring", "nsstring", "nsobject"}:
            return
        if lowered in seen:
            return
        seen.add(lowered)
        candidates.append(cleaned)

    decoded = raw.decode("utf-8", errors="ignore")
    for match in _ARCHIVE_CONTENT_RE.findall(decoded):
        _push_candidate(match.strip())
    if candidates:
        return "\n".join(candidates)

    for match in _PRINTABLE_BLOB_RE.findall(raw):
        text = match.decode("utf-8", errors="ignore").strip()
        _push_candidate(text)

    if not candidates:
        return None
    return "\n".join(candidates)


def extract_message_text(
    plain_text: str | None,
    *,
    attributed_body: bytes | bytearray | memoryview | None = None,
    associated_message_type: int | None = None,
    item_type: int | None = None,
) -> str | None:
    normalized_plain = normalize_message_text(plain_text)
    if normalized_plain:
        return normalized_plain
    if associated_message_type is not None and int(associated_message_type) in _REACTION_ASSOCIATED_TYPES:
        return None
    if item_type is not None and int(item_type) != 0:
        return None
    normalized_attributed = normalize_message_text(extract_attributed_body_text(attributed_body))
    return normalized_attributed or None


def message_preview(text: str | None, *, max_chars: int = 160) -> str:
    normalized = normalize_message_text(text)
    if not normalized:
        return ""
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "…"


def conversation_display_name(
    display_name: str | None,
    chat_identifier: str | None,
    participants: list[str] | None,
) -> str:
    if display_name and display_name.strip():
        return display_name.strip()
    if chat_identifier and chat_identifier.strip():
        return chat_identifier.strip()
    clean_participants = [item.strip() for item in participants or [] if item and item.strip()]
    if clean_participants:
        return ", ".join(clean_participants[:3])
    return "Untitled Conversation"


def stable_fingerprint(action_type: str, *parts: Any) -> str:
    payload = {"action_type": action_type, "parts": list(parts)}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def looks_like_completion(text: str | None) -> bool:
    return bool(_COMPLETION_RE.search(normalize_message_text(text)))


def derive_project_aliases(name: str) -> tuple[str, ...]:
    normalized_name = normalize_message_text(name)
    tokens = [token for token in _TOKEN_RE.findall(normalized_name.lower()) if token]
    aliases: list[str] = []
    if normalized_name:
        aliases.append(normalized_name)
    if tokens:
        aliases.append(" ".join(tokens))
    if len(tokens) >= 2:
        aliases.append("".join(token[0] for token in tokens).upper())
    seen: set[str] = set()
    ordered: list[str] = []
    for alias in aliases:
        clean = normalize_message_text(alias)
        if not clean:
            continue
        lowered = clean.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(clean)
    return tuple(ordered)


def content_tokens(text: str | None) -> set[str]:
    normalized = normalize_message_text(text).lower()
    return {
        token
        for token in _TOKEN_RE.findall(normalized)
        if token and token not in _STOPWORDS and len(token) > 1
    }


def message_intent_tags(text: str | None) -> set[str]:
    tokens = content_tokens(text)
    tags: set[str] = set()
    for tag, vocabulary in _INTENT_LEXICONS.items():
        if tokens & vocabulary:
            tags.add(tag)
    return tags


def should_split_message_cluster(
    batch: Sequence[Any],
    next_message: Any,
    *,
    max_cluster_messages: int,
    max_cluster_gap: timedelta,
) -> tuple[bool, str]:
    if not batch:
        return False, "empty_cluster"
    if len(batch) >= max_cluster_messages:
        return True, "max_cluster_messages"

    previous_timestamp = getattr(batch[-1], "sent_at_utc", None)
    next_timestamp = getattr(next_message, "sent_at_utc", None)
    if (
        previous_timestamp is not None
        and next_timestamp is not None
        and next_timestamp - previous_timestamp > max_cluster_gap
    ):
        return True, "time_gap_exceeded"

    next_text = normalize_message_text(getattr(next_message, "text", None))
    if not next_text or _LOW_SIGNAL_TEXT_RE.match(next_text):
        return False, "low_signal_follow_up"

    recent_texts = [
        normalize_message_text(getattr(item, "text", None))
        for item in batch[-4:]
        if normalize_message_text(getattr(item, "text", None))
    ]
    if not recent_texts:
        return False, "no_recent_text"

    current_tokens = content_tokens(next_text)
    if len(current_tokens) < 3:
        return False, "not_enough_content_tokens"

    recent_tokens = set().union(*(content_tokens(text) for text in recent_texts))
    if len(recent_tokens) < 3:
        return False, "not_enough_recent_context"

    overlap = len(current_tokens & recent_tokens) / max(min(len(current_tokens), len(recent_tokens)), 1)
    recent_intents = set().union(*(message_intent_tags(text) for text in recent_texts))
    current_intents = message_intent_tags(next_text)
    if _CLUSTER_BOUNDARY_CUE_RE.search(next_text) and overlap < 0.18:
        return True, "explicit_topic_boundary"
    if overlap < 0.08 and recent_intents and current_intents and recent_intents.isdisjoint(current_intents):
        return True, "semantic_topic_shift"
    return False, "same_topic"


def infer_project_candidates(
    *,
    project_catalog: Sequence[ProjectCatalogEntry],
    conversation_name: str | None,
    participants: list[str] | None,
    message_texts: list[str],
) -> list[ProjectCandidate]:
    conversation_text = normalize_message_text(conversation_name).lower()
    message_blob = " ".join(normalize_message_text(text) for text in message_texts).lower()
    participant_blob = " ".join(item.strip().lower() for item in participants or [] if item and item.strip())
    conversation_tokens = content_tokens(conversation_name)
    message_tokens = set().union(*(content_tokens(text) for text in message_texts))
    participant_tokens = content_tokens(participant_blob)

    candidates: list[ProjectCandidate] = []
    for entry in project_catalog:
        aliases = entry.aliases or derive_project_aliases(entry.name)
        alias_tokens = set().union(*(content_tokens(alias) for alias in aliases))
        if not alias_tokens:
            continue

        score = 0.0
        reasons: list[str] = []
        normalized_affinity = max(0.0, min(1.0, entry.conversation_affinity))
        if normalized_affinity > 0:
            score += 0.46 * normalized_affinity
            reasons.append("previous approved actions in this conversation mapped to the project")

        for alias in aliases:
            lowered_alias = alias.lower()
            if len(lowered_alias) >= 4 and lowered_alias == conversation_text:
                score += 0.62
                reasons.append(f"conversation title exactly matches alias '{alias}'")
                break
            if len(lowered_alias) >= 4 and lowered_alias in conversation_text:
                score += 0.54
                reasons.append(f"conversation title contains alias '{alias}'")
                break
            if len(lowered_alias) >= 4 and lowered_alias in message_blob:
                score += 0.32
                reasons.append(f"messages mention alias '{alias}'")
                break
            if len(lowered_alias) <= 3 and lowered_alias and lowered_alias in conversation_tokens:
                score += 0.2
                reasons.append(f"conversation title contains shorthand alias '{alias}'")
                break

        conversation_overlap = len(alias_tokens & conversation_tokens) / max(len(alias_tokens), 1)
        if conversation_overlap > 0:
            score += min(0.32, 0.32 * conversation_overlap)
            reasons.append("conversation title shares project vocabulary")

        message_overlap = len(alias_tokens & message_tokens) / max(len(alias_tokens), 1)
        if message_overlap > 0:
            score += min(0.24, 0.24 * message_overlap)
            reasons.append("messages share project vocabulary")

        participant_overlap = len(alias_tokens & participant_tokens) / max(len(alias_tokens), 1)
        if participant_overlap > 0:
            score += min(0.06, 0.06 * participant_overlap)
            reasons.append("participants overlap with project shorthand")

        if entry.notes:
            note_tokens = content_tokens(entry.notes)
            if note_tokens:
                note_overlap = len(note_tokens & message_tokens) / max(min(len(note_tokens), len(message_tokens) or 1), 1)
                if note_overlap > 0:
                    score += min(0.12, 0.12 * note_overlap)
                    reasons.append("messages overlap with project notes vocabulary")

        if score <= 0:
            continue
        candidates.append(
            ProjectCandidate(
                project_name=entry.name,
                score=min(0.98, score),
                reasons=tuple(reasons),
                aliases=tuple(aliases),
            )
        )

    return sorted(candidates, key=lambda item: (-item.score, item.project_name.lower()))


def infer_project_match(
    *,
    project_names: list[str] | None = None,
    project_catalog: Sequence[ProjectCatalogEntry] | None = None,
    conversation_name: str | None,
    participants: list[str] | None,
    message_texts: list[str],
) -> ProjectGuess:
    catalog = list(project_catalog or ())
    if not catalog:
        catalog = [
            ProjectCatalogEntry(name=name, aliases=derive_project_aliases(name))
            for name in (project_names or [])
        ]
    candidates = infer_project_candidates(
        project_catalog=catalog,
        conversation_name=conversation_name,
        participants=participants,
        message_texts=message_texts,
    )
    serialized_candidates = [
        {
            "project_name": candidate.project_name,
            "confidence": round(candidate.score, 4),
            "reasons": list(candidate.reasons),
            "aliases": list(candidate.aliases),
        }
        for candidate in candidates[:5]
    ]
    if not candidates or candidates[0].score < 0.24:
        return ProjectGuess(
            project_name=None,
            confidence=0.0,
            reason="No strong project signals found in the conversation metadata or messages",
            candidates=serialized_candidates,
        )
    best = candidates[0]
    return ProjectGuess(
        project_name=best.project_name,
        confidence=best.score,
        reason="; ".join(best.reasons[:3]) or "Top weighted project candidate",
        candidates=serialized_candidates,
    )
