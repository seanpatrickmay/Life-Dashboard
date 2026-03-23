from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace

from app.db.repositories.journal_repository import JournalRepository


def run(coro):
    return asyncio.run(coro)


class FakeSession:
    def __init__(self) -> None:
        self.executed: list[object] = []
        self.summary_result = SimpleNamespace(user_id=1, local_date=date(2025, 12, 23))

    async def execute(self, stmt):  # noqa: ANN001
        self.executed.append(stmt)
        return FakeResult(self.summary_result)


class FakeResult:
    def __init__(self, value) -> None:  # noqa: ANN001
        self.value = value

    def scalar_one(self):  # noqa: ANN201
        return self.value


def test_delete_entries_for_day_nulls_imessage_audit_refs_before_delete() -> None:
    session = FakeSession()
    repo = JournalRepository(session)

    run(repo.delete_entries_for_day(1, date(2025, 12, 23)))

    statements = [str(stmt) for stmt in session.executed]
    assert len(statements) == 2
    assert any("UPDATE imessage_action_audit SET target_journal_entry_id" in stmt for stmt in statements)
    assert any("DELETE FROM journal_entry" in stmt for stmt in statements)
    assert statements.index(next(stmt for stmt in statements if "UPDATE imessage_action_audit SET target_journal_entry_id" in stmt)) < statements.index(next(stmt for stmt in statements if "DELETE FROM journal_entry" in stmt))


def test_upsert_summary_uses_on_conflict_unique_key() -> None:
    session = FakeSession()
    repo = JournalRepository(session)

    summary = run(
        repo.upsert_summary(
            user_id=1,
            local_date=date(2025, 12, 23),
            time_zone="America/New_York",
            status="final",
            summary_json={"groups": []},
            source_hash="abc123",
            finalized_at=None,
            model_name="gpt-test-journal",
            version="v3",
        )
    )

    statements = [str(stmt) for stmt in session.executed]
    assert "ON CONFLICT ON CONSTRAINT uq_journal_day_summary_user_date DO UPDATE" in statements[0]
    assert summary is session.summary_result
