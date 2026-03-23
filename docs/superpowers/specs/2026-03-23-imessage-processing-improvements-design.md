# iMessage Processing Improvements — Design Spec

**Date:** 2026-03-23
**Status:** Approved (autonomous mode)

## Problem Statement

Audit of 250 recent messages across 18 conversations revealed:
1. **Irrelevant actions applied** — system produces low-value journal entries (mechanical actions like "added X to GC"), mis-extractions ("md" parsed as doctor instead of Maryland)
2. **Journal over-generation** — 3 separate entries for one short book-club conversation
3. **Project inference too conservative** — chat named "Comic CV Project 🚀" can't link to its own project (0.65 confidence, threshold 0.72)
4. **103 skipped calendar events** — Google Calendar connection expired
5. **Contact resolution gaps** — some contacts display as raw phone numbers

## Changes

### Change 1: Relevancy Checker (post-extraction, pre-apply gate)

**Location:** `backend/app/services/imessage_processing_service.py`

**New function:** `_score_action_relevance(action_type, action, cluster, project, all_cluster_actions) -> float`

Deterministic scorer (no LLM calls), returns 0.0–1.0:

**Substance score (0.4 weight):**
- Action text length < 15 chars and no named entities → 0.2
- Action text is a restatement of a message reaction (Liked, Loved, Emphasized) → 0.1
- Action contains concrete noun + verb (decision, commitment, event) → 0.8
- Default: 0.5

**Coherence score (0.3 weight):**
- Calendar action from `conversation_type == "business"` (short codes, automated) → 0.1
- Todo from group chat where user didn't volunteer → 0.2
- Journal from conversation with < 3 substantive messages → 0.3
- Action type matches conversation intent tags → 0.9
- Default: 0.5

**Novelty score (0.3 weight):**
- This is the Nth action of same type from same cluster: score = 1.0 / N
- Action text overlaps >60% tokens with another action from same cluster → 0.2
- Default: 1.0

**Integration point:** In `_process_cluster()`, after `_judge_actions()` loop, before `_apply_*()`:
```python
relevance = self._score_action_relevance(action_type, action, cluster, project, all_actions)
if relevance < 0.45:
    await self._record_action_audit(status="rejected_low_relevance", ...)
    continue
```

**New status value:** `"rejected_low_relevance"` added to the status enum for `imessage_action_audit`.

### Change 2: Journal Consolidation

**Location:** `backend/app/services/imessage_processing_service.py`, within `_process_cluster()`

After extraction, before judge:
1. If a cluster produces N > 1 journal entries, merge them:
   - Concatenate texts with " · " separator
   - Keep the earliest `source_occurred_at_utc`
   - Union the `supporting_message_ids`
   - Combine rationales
2. Result: at most 1 journal entry per cluster

This is simpler and more reliable than trying to have the LLM produce fewer entries.

### Change 3: Project Inference from Conversation Name

**Location:** `backend/app/services/imessage_processing_service.py`, `_resolve_project()`

Before the existing LLM-based project inference:
1. Get `conversation.display_name`
2. Normalize: strip emoji, lowercase, remove common words ("project", "group", "chat")
3. Fuzzy-match against all project names using `SequenceMatcher.ratio()`
4. If best match ratio > 0.6 → assign that project with confidence 0.90
5. Skip LLM inference entirely for this action

This catches "Comic CV Project 🚀" → "Comic Book CV Project" and similar.

### Change 4: Contact Re-resolution

**Location:** New utility `backend/app/services/imessage_contact_service.py` — add `refresh_unresolved_contacts()` method

1. Query `imessage_contact_identity` where `resolved_name IS NULL`
2. For each, re-run `_resolve_from_contacts()` against macOS Contacts DB
3. Update resolved_name if found
4. Also update `imessage_participant.display_name` for matching identifiers

**Trigger:** Can be called manually via `scripts/refresh_contacts.py` or added to the processing pipeline as a periodic step.

### Change 5: Conversation Context in Extraction Prompt

**Location:** `backend/app/services/imessage_processing_service.py`, payload construction in `_build_extraction_payload()`

Add to the payload dict sent to the LLM:
```python
"conversation_context": {
    "type": classify_conversation_type(conversation),  # personal/group/business
    "display_name": conversation.display_name,
    "topic_hints": _infer_topic_hints(messages),  # travel, work, social, etc.
}
```

**New function:** `_infer_topic_hints(messages) -> list[str]`
- Scan message texts for topic keywords:
  - "flight", "airport", "boarding", "travel", "hotel" → "travel"
  - "meeting", "standup", "sprint", "deploy" → "work"
  - "dinner", "game night", "party", "drinks" → "social"
- Return top 2-3 topic tags

This gives the LLM context so "i go md early tmr" in a travel conversation is understood as Maryland, not a medical appointment.

## Testing Strategy

- **Relevancy checker:** Unit tests with real action payloads from the audit (Owen Graff beach convo, book club 3-entry case, rideshare notifications). Verify scores match expected thresholds.
- **Journal consolidation:** Test that N entries from one cluster merge to 1. Test edge cases (0 entries, 1 entry, entries with very different topics).
- **Project inference from name:** Test fuzzy matching with emoji-heavy names, partial matches, no matches.
- **Contact re-resolution:** Test with mock Contacts DB fixture.
- **Conversation context:** Test topic hint inference against known message sets.

## Non-Goals

- No database migrations — all changes use existing columns (`status` field already supports arbitrary strings)
- No frontend changes — all backend processing pipeline modifications
- No changes to the LLM prompts themselves (except adding conversation_context to the payload)
- No changes to the sync pipeline (only processing pipeline)
