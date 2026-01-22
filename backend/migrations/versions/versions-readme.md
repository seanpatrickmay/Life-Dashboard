# versions-readme

## Purpose
Stores Alembic migration scripts that evolve the backend schema over time.

## File Overview
| File / Module | Description |
| --- | --- |
| `20250120_auth_garmin_quota.py` | Adds auth, Garmin quota, and related schema updates. |
| `20251217_initial_reset.py` | Initial reset migration for baseline schema. |
| `20260113_sync_user_sequence.py` | Aligns user ID sequence with existing data. |
| `20260201_journal_entries.py` | Adds journal entry and summary tables. |
| `20260310_calendar_sync.py` | Adds Google Calendar sync tables and todo date-only flag. |
| `20260311_add_todo_deadline_date_only.py` | Ensures the todo date-only flag exists after sync migration. |
