# Claude Code History Integration

## Overview

Integrate Claude Code conversation logs into the Life Dashboard to automatically track development activity. An hourly sync job reads session logs from `~/.claude/`, uses an LLM to summarize what was accomplished, and populates two surfaces:

1. **Journal** — one entry per project per day summarizing Claude Code work, fed into the existing journal compilation pipeline
2. **Projects** — per-project activity feed showing what was done, plus a living project state summary with next steps

## Data Source

Claude Code stores conversation logs at `~/.claude/`:

- **`history.jsonl`** — lightweight global index. Each line: `{ display: str, timestamp: int (Unix ms), project: str (real path), sessionId?: str }`. Note: ~1.5% of entries lack `sessionId` (early usage); these are skipped.
- **`projects/{encoded-path}/{sessionId}.jsonl`** — full conversation logs per session per project. Entries use ISO 8601 timestamps.
- **`sessions/{pid}.json`** — active session metadata: `{ pid, sessionId, cwd, startedAt (Unix ms), kind }`

**Directory encoding:** Lossy — `/`, spaces, and `.` are all replaced with `-`. This encoding **cannot be reversed**. The real project path is always read from `history.jsonl`'s `project` field or from `cwd` inside session JSONL entries. The encoded directory name is only used to locate session files on disk.

**Session JSONL entry types:** `user`, `assistant`, `system`, `progress`, `file-history-snapshot`, `queue-operation`, `pr-link`, `last-prompt`. There is no standalone `tool-use` type — tool use is embedded within `assistant` entries as `tool_use` content blocks in `message.content[]`.

**Message structure differences:**
- User messages: `{ type: "user", message: { role: "user", content: <string> } }` — content is a plain string
- Assistant messages: `{ type: "assistant", message: { role: "assistant", content: [{type: "thinking", ...}, {type: "text", ...}, {type: "tool_use", ...}] } }` — content is an array of typed blocks

## Architecture

### Pipeline Flow

```
launchd (hourly, StartInterval: 3600)
  → scripts/run_claude_code_sync.sh (mutex + env detection)
    → scripts/sync_claude_code.py --user-id 1 --time-zone America/New_York
      → ClaudeCodeSyncService.find_unprocessed_sessions()
          Read history.jsonl + scan projects/ directory for session files
          Compare against ClaudeCodeSyncCursor table
          Filter out active sessions (see Active Session Detection)
      → For each unprocessed/updated session:
          → ClaudeCodeSyncService.read_session(session_id, project_path)
              Read session JSONL from disk, extract relevant content
              Apply content filtering (see Privacy section)
          → ClaudeCodeProcessingService.process_session(session_content)
              LLM summarizes → ProjectActivity (upsert) + JournalEntry
          → ClaudeCodeProjectResolver.resolve(project_path)
              Path → Project record (match or auto-create)
          → Update ClaudeCodeSyncCursor
      → For each project with new activities today:
          → ClaudeCodeProcessingService.regenerate_project_state(project_id)
              LLM synthesizes current state + next steps from recent activity
```

### Session Discovery

Two complementary discovery mechanisms:

1. **`history.jsonl`** — primary index. Provides `project` (real path) and `sessionId` for most sessions.
2. **Directory scan** — fallback. Scan `~/.claude/projects/` for `.jsonl` files not found in `history.jsonl`. For these, extract `cwd` from the first entry inside the JSONL to get the real project path.

This ensures sessions that were not recorded in `history.jsonl` are still discovered.

### Active Session Detection

A session is considered active (and skipped) if:
1. Any file in `~/.claude/sessions/` contains a matching `sessionId`, AND
2. The PID listed in that file is still running (verified via `kill -0 {pid}`)

As a staleness fallback: if the last entry in a session JSONL is older than 6 hours, treat it as complete regardless of PID file status (covers crashed sessions that didn't clean up).

### Services

| Service | Responsibility |
|---------|---------------|
| `ClaudeCodeSyncService` | Reads `history.jsonl` + session JSONL files, manages sync cursors, detects new/updated sessions |
| `ClaudeCodeProcessingService` | LLM summarization, creates `ProjectActivity` + `JournalEntry`, regenerates project state |
| `ClaudeCodeProjectResolver` | Maps Claude Code directory paths to `Project` records, auto-creates when needed |

### Session Content Extraction

From each session JSONL, extract:
- **User messages** (`type: "user"`) — what was requested. Content is a plain string in `message.content`.
- **Assistant text responses** (`type: "assistant"`) — what was done. Parse `message.content[]` for blocks with `type: "text"`. Also extract `tool_use` blocks to identify files edited, bash commands run, and git operations.
- **Metadata** — `gitBranch`, `timestamp`, `cwd` from entry-level fields.

**Skip:** `type: "thinking"` content blocks, `progress` entries, `file-history-snapshot` entries, `system` entries, subagent logs (files under `{sessionId}/subagents/`).

**Extraction algorithm for long sessions:**

Sessions can be very large (up to 37MB). To produce an ~8K token LLM input window:

1. Collect all user messages (typically short, high signal)
2. Collect assistant text blocks (skip thinking, skip raw tool output)
3. Extract a structured tool-use summary: list of `(tool_name, file_path or command)` tuples from `tool_use` blocks — not the full input/output
4. If total exceeds 8K tokens: keep first 3 exchanges + last 3 exchanges + all git-related tool uses (commit messages, branch operations)
5. **Supplement with git log**: Run `git log --since={session_start} --until={session_end} --oneline` for the project directory to capture commits made during the session. This is structured, reliable, and privacy-safe.

If 8K proves insufficient for quality summaries, increase to 12-16K after testing.

### Privacy & Content Filtering

Before sending session content to the LLM, apply content filtering:

1. **Strip environment variables**: Remove lines matching `*_KEY=...`, `*_SECRET=...`, `*_TOKEN=...`, `*_URL=...`, `DATABASE_URL=...`, `PASSWORD=...` patterns
2. **Exclude sensitive file reads**: Skip tool output from files matching `.env`, `credentials`, `secrets`, `*.pem`, `*.key`
3. **Mask URLs with credentials**: Replace `://user:pass@` patterns with `://***@`

The git log supplement (item 5 in extraction) is inherently privacy-safe since it only contains commit messages and hashes.

### LLM Prompt Strategy

**Session summarization** — extract from session content:
1. **Summary** (1-3 sentences): Plain language description of what was accomplished
2. **Structured details:**
   - Files modified (from tool_use blocks)
   - Git branch / commits (from metadata + git log)
   - Key decisions or trade-offs
   - Category: `feature`, `bugfix`, `refactor`, `debugging`, `planning`, `research`, `config`

**Project state regeneration** — from recent activity history:
1. **Status**: What the project is and its current state
2. **Recent focus**: What's been worked on lately
3. **Next steps**: Inferred from recent session context (discussed but not done, open questions, planned work)

### Project Auto-Recognition

1. Read the real project path from `history.jsonl`'s `project` field (or `cwd` from session JSONL for directory-scan discoveries)
2. Extract the last meaningful path segment as the project name (e.g., `/Users/seanmay/Desktop/Current Projects/Life-Dashboard` → `"Life-Dashboard"`)
3. Case-insensitive match against existing `Project.name`
4. No match → auto-create new `Project` with that name
5. Sessions with no project path, or paths that resolve to non-project directories (e.g., home directory) → assigned to `"General"` project
6. **Project directory heuristic**: To distinguish real projects from parent directories, check for project markers (`.git`, `package.json`, `pyproject.toml`, `Cargo.toml`) at the resolved path. Paths without markers are treated as "General".

No LLM needed for project recognition — purely path-based.

### Journal Integration

Each sync run creates one `JournalEntry` per project per day via `JournalService.add_entry()`. If a project had 3 sessions today, the journal entry summarizes all 3 sessions' work for that project.

These entries feed into the existing journal compilation pipeline alongside manual entries, calendar events, and completed todos. The journal compiler groups and deduplicates them as usual.

**Deduplication strategy:** Add a `source` column to `JournalEntry` (nullable, values: `"claude_code"`, `"imessage"`, `null` for manual). Before creating a journal entry, query for an existing entry with `source="claude_code"` matching the same project name substring and `local_date`. If found, update its text. If not, create new.

This avoids the lifecycle problem where the journal compiler deletes entries after compilation — by tagging entries with a source, the sync can always find and update its own entries. The existing `source_hash` mechanism in the compiler will detect the changed entry text and trigger recompilation.

## Data Models

### New Table: `claude_code_sync_cursor`

| Column | Type | Notes |
|--------|------|-------|
| `id` | int | PK |
| `user_id` | int | FK → user, indexed |
| `session_id` | str | Claude Code UUID |
| `project_path` | str | Real project directory path (from history.jsonl) |
| `last_processed_at_utc` | datetime | Timestamp of last JSONL entry processed |
| `entry_count` | int | Number of JSONL entries processed |
| `file_mtime` | float | File modification time (from os.path.getmtime) for cheap change detection |
| `created_at_utc` | datetime | |
| `updated_at_utc` | datetime | |

Unique constraint: `(user_id, session_id)`

Change detection: Compare `file_mtime` first (cheap filesystem call). Only read the JSONL if mtime has changed.

### New Table: `project_activity`

| Column | Type | Notes |
|--------|------|-------|
| `id` | int | PK |
| `user_id` | int | FK → user, indexed |
| `project_id` | int | FK → project, indexed |
| `local_date` | date | indexed |
| `session_id` | str | Source Claude Code session UUID |
| `summary` | str | LLM-generated plain language summary |
| `details_json` | dict | Structured: files, branches, commits, category |
| `source_project_path` | str | Real project directory path |
| `created_at_utc` | datetime | |
| `updated_at_utc` | datetime | |

Unique constraint: `(user_id, session_id)` — enables upsert when re-processing updated sessions.
Composite index: `(user_id, project_id, local_date)` — for activity feed queries.

### Altered Table: `project`

| Column | Type | Notes |
|--------|------|-------|
| `+ state_summary_json` | dict, nullable | LLM-generated: status, recent focus, next steps |
| `+ state_updated_at_utc` | datetime, nullable | When state was last regenerated |

### Altered Table: `journal_entry`

| Column | Type | Notes |
|--------|------|-------|
| `+ source` | str, nullable | `"claude_code"`, `"imessage"`, or null (manual) |

### Pydantic Schema Updates

- `ProjectResponse` in `backend/app/schemas/projects.py`: add `state_summary_json` and `state_updated_at_utc` fields
- New `ProjectActivityResponse` schema for activity endpoints
- `User` model in `backend/app/db/models/entities.py`: add relationship declarations for `ClaudeCodeSyncCursor` and `ProjectActivity`

### Migration

Single Alembic migration adding:
- `claude_code_sync_cursor` table
- `project_activity` table
- `project.state_summary_json` column (nullable)
- `project.state_updated_at_utc` column (nullable)
- `journal_entry.source` column (nullable)

All new columns are nullable so existing rows are unaffected.

## Frontend

### Projects Page Changes

The existing Projects page (`Projects.tsx`, 4340 lines) is a workspace/wiki system with sidebar, pages, blocks, and drag-and-drop. The new activity feed and project state integrate into this existing architecture:

Each project view shows three sections:
1. **Current State** — rendered from `Project.state_summary_json`. Shows project status, recent focus, and next steps. Displays `state_updated_at_utc` as a freshness indicator (e.g., "Updated 2 hours ago" or "Last updated 3 weeks ago" with faded styling for stale summaries).
2. **Activity Log** — reverse-chronological list of `ProjectActivity` entries. Each shows: date, summary, category badge, expandable details (files, branch, commits). Grouped by date.
3. **Todos** — existing todo cards scoped to that project. No changes to existing functionality.

### All-Projects View

When no project is selected, show a unified activity feed across all projects. Each entry includes its project name. Supports date range filtering (`since` / `until` params).

### Auto-Created Projects

Appear in the sidebar automatically when first processed. No manual setup.

## Scheduling

### Entry Script: `scripts/sync_claude_code.py`

Same pattern as `sync_imessage.py`:
- Args: `--user-id`, `--time-zone`, `--claude-dir` (default `~/.claude`)
- Connects to PostgreSQL directly (same DB URL as backend)
- Calls sync service then processing service
- Logs results

### Shell Wrapper: `scripts/run_claude_code_sync.sh`

- Mutex lock via `mkdir` (consistent with existing `run_imessage_sync.sh` pattern)
- Detects Python environment (poetry venv)
- Delegates to `sync_claude_code.py`

### launchd Plist: `scripts/com.life_dashboard.claude_code_sync.plist.template`

- `StartInterval: 3600` (hourly)
- Logs: `/tmp/life_dashboard_claude_code_sync.log` and `.err.log`
- Label: `com.life_dashboard.claude_code_sync`

## API Endpoints

### New Endpoints (Projects Router)

- **`GET /api/projects/{project_id}/activities`** — paginated activity feed for a project
  - Query params: `page`, `per_page`, `since`, `until` (date filters)
  - Returns: list of `ProjectActivityResponse` with summary, details, date

- **`GET /api/projects/activities`** — unified activity feed across all projects
  - Query params: `page`, `per_page`, `since`, `until`
  - Returns: list of `ProjectActivityResponse` with project name included

### Modified Endpoints

- **`GET /api/projects/board`** — add `state_summary_json` and `state_updated_at_utc` to project response objects

## Error Handling

- **Missing/corrupt JSONL files**: Skip session, log warning, don't update cursor
- **LLM failure**: Skip session, retry on next run (cursor not advanced)
- **Project creation race**: Use `get_or_create` pattern with unique constraint
- **Active sessions**: Skip per Active Session Detection rules above
- **Stale PID files**: 6-hour staleness fallback treats old sessions as complete
- **Retry/backfill**: If LLM service is down, sessions remain unprocessed and are retried on subsequent runs (cursor-based, no data loss)

## Known Limitations

- Sessions without `sessionId` in `history.jsonl` (~1.5%) are skipped
- Hourly sync means up to 60 minutes of lag before activity appears
- Project state summaries become stale if no new activity — UI shows freshness indicator
- The 8K token extraction window may miss important context in the middle of very long sessions; git log supplementation mitigates this

## Testing

- Unit tests for project path extraction from real paths
- Unit tests for session content extraction (JSONL parsing, token limiting, privacy filtering)
- Unit tests for active session detection logic
- Integration test for full pipeline with fixture JSONL files
- Frontend component tests for activity feed rendering
- Alembic migration up/down test
