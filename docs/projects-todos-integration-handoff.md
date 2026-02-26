# Projects + Todos Integration Handoff

This document is for a **separate app** that should read/write the same Projects/Todos data used by Life Dashboard.

## 1) Fastest Path (Recommended)

Use the existing backend API (`backend/app/main.py`) instead of direct SQL for writes.

Why:
- It enforces business rules (Inbox handling, project deletion behavior, suggestions cleanup).
- It preserves side effects (calendar link updates, suggestion generation, accomplishment text on completion).
- It is already used by the current frontend (`frontend/src/services/api.ts`).

Base API prefix: `/api` (from `backend/app/core/config.py`).

Core routes:
- `GET /api/projects/board`
- `POST /api/projects`
- `PATCH /api/projects/{project_id}`
- `DELETE /api/projects/{project_id}`
- `POST /api/projects/suggestions/recompute`
- `DELETE /api/projects/suggestions/{todo_id}`
- `GET /api/todos`
- `POST /api/todos`
- `PATCH /api/todos/{todo_id}`
- `DELETE /api/todos/{todo_id}`

## 2) Auth Model (Critical)

The API uses **session cookie auth**, not bearer tokens.

- Cookie name defaults to `ld_session` (`SESSION_COOKIE_NAME`).
- Most project/todo endpoints require authenticated user via `get_current_user`.
- Login endpoints:
  - `GET /api/auth/google/login`
  - `GET /api/auth/google/callback`
  - `GET /api/auth/me`
  - `POST /api/auth/logout`

For another app, easiest options:
1. Reuse the same backend/auth flow and cookie domain policy, or
2. Build a small backend-for-frontend that proxies authenticated requests to Life Dashboard API.

## 3) Data Contracts Used by Current Frontend

Reference: `frontend/src/services/api.ts`, `backend/app/schemas/projects.py`, `backend/app/schemas/todos.py`.

### ProjectBoardResponse (`GET /api/projects/board`)

```json
{
  "projects": [
    {
      "id": 1,
      "name": "Inbox",
      "notes": null,
      "archived": false,
      "sort_order": -100,
      "created_at": "2026-02-26T16:00:00Z",
      "updated_at": "2026-02-26T16:00:00Z",
      "open_count": 3,
      "completed_count": 4
    }
  ],
  "todos": [
    {
      "id": 101,
      "project_id": 1,
      "text": "Call insurance",
      "completed": false,
      "deadline_utc": "2026-03-01T15:00:00Z",
      "deadline_is_date_only": false,
      "is_overdue": false,
      "created_at": "2026-02-26T16:00:00Z",
      "updated_at": "2026-02-26T16:00:00Z"
    }
  ],
  "suggestions": [
    {
      "todo_id": 101,
      "suggested_project_name": "Health",
      "confidence": 0.64,
      "reason": "Matched keyword 'insurance'"
    }
  ]
}
```

### Create/Update payloads

- `POST /api/projects`
  - `{ "name": string, "notes"?: string|null, "sort_order"?: number }`
- `PATCH /api/projects/{id}`
  - `{ "name"?: string, "notes"?: string|null, "archived"?: boolean, "sort_order"?: number }`
- `POST /api/todos`
  - `{ "text": string, "project_id"?: number, "deadline_utc"?: string|null, "deadline_is_date_only"?: boolean, "time_zone"?: string }`
- `PATCH /api/todos/{id}`
  - `{ "text"?: string, "project_id"?: number, "deadline_utc"?: string|null, "deadline_is_date_only"?: boolean, "completed"?: boolean, "time_zone"?: string }`

## 4) Business Rules You Must Preserve

From `backend/app/routers/projects.py`, `backend/app/routers/todos.py`, repositories/services:

- Every user has an Inbox project; created automatically if missing (`ensure_inbox_project`).
- Project names are treated as case-insensitive unique per user by repository checks.
- `Inbox` cannot be archived or deleted.
- Deleting a project reassigns its todos to Inbox, then deletes the project.
- Creating/updating todo text queues project-suggestion background processing.
- Updating todo `project_id` clears any suggestion for that todo.
- Completing a todo can generate accomplishment text and updates completion metadata.
- Deadline changes can trigger calendar event sync/unlink side effects.

## 5) Current Suggestion Grouping Behavior

From `backend/app/prompts/llm_prompts.py` + `todo_project_suggestion_service.py`:

- Prompt explicitly avoids micro-buckets like “Personal Appointments / Self Care / Groceries / Daily Routines”.
- Such items should map to **`Personal`**.
- Auto-apply threshold: confidence `>= 0.75`; otherwise suggestion is stored in `todo_project_suggestion`.
- If model call fails, keyword heuristics are used.

## 6) Direct DB Schema (If You Must Query Neon Directly)

Primary tables for this feature:

### `project`
- `id` (PK)
- `user_id` (FK -> `user.id`)
- `name` (varchar 255)
- `notes` (text nullable)
- `archived` (bool, indexed)
- `sort_order` (int)
- `created_at`, `updated_at`
- Unique constraint: `(user_id, name)` (`uq_project_user_name`)

### `todo_item`
- `id` (PK)
- `user_id` (FK -> `user.id`)
- `project_id` (FK -> `project.id`, indexed, non-null)
- `text` (varchar 512)
- `completed` (bool indexed)
- `deadline_utc` (timestamptz nullable indexed)
- `deadline_is_date_only` (bool)
- `completed_at_utc` (timestamptz nullable)
- `completed_local_date` (date nullable indexed)
- `completed_time_zone` (varchar 64 nullable)
- `accomplishment_text` (text nullable)
- `accomplishment_generated_at_utc` (timestamptz nullable)
- `created_at`, `updated_at`

### `todo_project_suggestion`
- `id` (PK)
- `user_id` (FK -> `user.id`, indexed)
- `todo_id` (FK -> `todo_item.id`, indexed, unique)
- `suggested_project_name` (varchar 255)
- `confidence` (float)
- `reason` (text nullable)
- `created_at`, `updated_at`

Migration source of truth: `backend/migrations/versions/20260314_projects_page.py`.

## 7) Important Gap: “Project Goals”

There is currently **no dedicated `project_goal` table or API**.

If your new app needs explicit project-level goals, choose one:
- **Option A (minimal):** represent goals as todos in that project.
- **Option B (new feature):** add `project_goal` table + API in Life Dashboard backend, then consume it from both apps.

## 8) Local/Prod DB Topology

Current repo is configured for external Postgres (Neon recommended) via `.env`:
- `DATABASE_URL` (async URL, runtime)
- `DATABASE_URL_HOST` (sync URL, scripts/startup checks)
- `DATABASE_URL_MIGRATIONS` (sync URL for Alembic)

Docker Compose (`docker/docker-compose.yml`) no longer runs local Postgres service.

## 9) Environment Variables Another App Will Need

At minimum, if consuming API:
- `LIFE_DASHBOARD_API_BASE_URL` (e.g., `http://localhost:8000` or prod API origin)
- Cookie/session alignment:
  - `SESSION_COOKIE_NAME` (default `ld_session`)
  - CORS and domain alignment on Life Dashboard backend (`CORS_ORIGINS`, `SESSION_COOKIE_DOMAIN`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`)

If querying Neon directly:
- `NEON_DATABASE_URL` (prefer read/write role with least privilege)

## 10) Copy/Paste Verification Checklist

Use these checks before building UI:

1. Auth works:
   - `GET /api/auth/me` returns current user.
2. Read board:
   - `GET /api/projects/board` returns projects + todos + suggestions.
3. Create project:
   - `POST /api/projects` creates row and appears in board.
4. Create todo:
   - `POST /api/todos` with `project_id` adds todo.
5. Move todo:
   - `PATCH /api/todos/{id}` with new `project_id` updates grouping.
6. Delete project:
   - `DELETE /api/projects/{id}` reassigns todos to Inbox.
7. Suggestions:
   - `POST /api/projects/suggestions/recompute` returns `scheduled_count`.

## 11) Files to Read First (for another Codex agent)

- `backend/app/routers/projects.py`
- `backend/app/routers/todos.py`
- `backend/app/db/models/project.py`
- `backend/app/db/models/todo.py`
- `backend/app/db/repositories/project_repository.py`
- `backend/app/services/todo_project_suggestion_service.py`
- `backend/app/prompts/llm_prompts.py`
- `frontend/src/services/api.ts`
- `frontend/src/hooks/useProjectBoard.ts`
- `frontend/src/pages/Projects.tsx`
- `backend/migrations/versions/20260314_projects_page.py`

