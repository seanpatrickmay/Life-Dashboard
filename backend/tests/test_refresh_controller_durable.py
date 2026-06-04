"""Tests for the durable refresh controllers backed by the job_run table.

Covers:
1. Cooldown is durable via the DB row (running → cooldown → allowed again).
2. Queue dispatch: request_refresh enqueues the correct job name + payload.
3. Migration drift guard: job_run migration creates exactly the ORM model's columns.
4. Routers unchanged: the RefreshJobStatus shape is preserved.

The real pipeline bodies (metrics, digest) are never executed here.
JobQueue is replaced with a FakeJobQueue that records enqueue calls.
"""
from __future__ import annotations

import asyncio
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.base import Base
from app.db.models import job_run as _job_run_module  # noqa: F401 (registers model)
from app.db.models.job_run import JobRun
from app.workers.tasks import (
    DigestRefreshController,
    RefreshJobStatus,
    VisitRefreshController,
)

# ---------------------------------------------------------------------------
# Path to the migration file
# ---------------------------------------------------------------------------
_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260604_job_run.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):  # noqa: ANN001, ANN201
    return asyncio.run(coro)


class FakeJobQueue:
    """Records enqueue calls without running any handler."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def enqueue(self, name: str, payload: dict) -> None:
        self.calls.append((name, payload))


# ---------------------------------------------------------------------------
# In-memory SQLite session fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def session():
    """Yields a real async SQLAlchemy session backed by in-memory SQLite."""

    async def _make():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[JobRun.__table__],
            )
        maker = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
        return maker, engine

    maker, engine = run(_make())

    async def _session_ctx():
        async with maker() as s:
            yield s

    gen = _session_ctx()
    sess = run(gen.__anext__())
    yield sess
    try:
        run(gen.aclose())
    except StopAsyncIteration:
        pass
    run(engine.dispose())


# ---------------------------------------------------------------------------
# 1. VisitRefreshController: running → already running → cooldown → allowed again
# ---------------------------------------------------------------------------

class TestVisitRefreshControllerDurability:
    def test_first_request_starts_job(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_queue = FakeJobQueue()
        monkeypatch.setattr("app.workers.tasks.get_job_queue", lambda: fake_queue)

        ctrl = VisitRefreshController()

        status: RefreshJobStatus = run(ctrl.request_refresh(session, user_id=1))

        assert status.job_started is True
        assert status.running is True
        assert status.message == "Refresh started."
        assert len(fake_queue.calls) == 1
        assert fake_queue.calls[0] == ("visit_refresh", {"user_id": 1})

    def test_second_request_while_running_is_blocked(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_queue = FakeJobQueue()
        monkeypatch.setattr("app.workers.tasks.get_job_queue", lambda: fake_queue)

        ctrl = VisitRefreshController()
        run(ctrl.request_refresh(session, user_id=1))

        status2: RefreshJobStatus = run(ctrl.request_refresh(session, user_id=1))

        assert status2.job_started is False
        assert "already running" in (status2.message or "").lower()
        # No additional enqueue
        assert len(fake_queue.calls) == 1

    def test_cooldown_blocks_after_completion(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_queue = FakeJobQueue()
        monkeypatch.setattr("app.workers.tasks.get_job_queue", lambda: fake_queue)

        ctrl = VisitRefreshController()
        run(ctrl.request_refresh(session, user_id=1))

        # Simulate job completion: set running=False, next_allowed_at in the future
        async def _complete():
            from sqlalchemy import select
            result = await session.execute(select(JobRun).where(JobRun.id == "visit_refresh"))
            row = result.scalar_one()
            row.running = False
            row.next_allowed_at = datetime.now(tz=timezone.utc) + timedelta(hours=1)
            await session.commit()

        run(_complete())

        status3: RefreshJobStatus = run(ctrl.request_refresh(session, user_id=1))
        assert status3.job_started is False
        assert "cooldown" in (status3.message or "").lower()

    def test_allowed_after_cooldown_expires(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_queue = FakeJobQueue()
        monkeypatch.setattr("app.workers.tasks.get_job_queue", lambda: fake_queue)

        ctrl = VisitRefreshController()
        run(ctrl.request_refresh(session, user_id=1))

        # Simulate completion with next_allowed_at in the past
        async def _complete_in_past():
            from sqlalchemy import select
            result = await session.execute(select(JobRun).where(JobRun.id == "visit_refresh"))
            row = result.scalar_one()
            row.running = False
            row.next_allowed_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
            await session.commit()

        run(_complete_in_past())

        # Patch eastern_now to return a time past next_allowed_at
        past_next = datetime.now(tz=timezone.utc) + timedelta(days=1)
        monkeypatch.setattr("app.workers.tasks.eastern_now", lambda: past_next)

        status4: RefreshJobStatus = run(ctrl.request_refresh(session, user_id=1))
        assert status4.job_started is True


# ---------------------------------------------------------------------------
# 2. DigestRefreshController: same durability checks + force flag
# ---------------------------------------------------------------------------

class TestDigestRefreshControllerDurability:
    def test_first_request_starts_digest(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_queue = FakeJobQueue()
        monkeypatch.setattr("app.workers.tasks.get_job_queue", lambda: fake_queue)

        ctrl = DigestRefreshController()
        status = run(ctrl.request_refresh(session))

        assert status.job_started is True
        assert fake_queue.calls == [("digest_refresh", {})]

    def test_second_request_blocked_while_running(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_queue = FakeJobQueue()
        monkeypatch.setattr("app.workers.tasks.get_job_queue", lambda: fake_queue)

        ctrl = DigestRefreshController()
        run(ctrl.request_refresh(session))
        status2 = run(ctrl.request_refresh(session))

        assert status2.job_started is False
        assert len(fake_queue.calls) == 1

    def test_force_bypasses_cooldown(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_queue = FakeJobQueue()
        monkeypatch.setattr("app.workers.tasks.get_job_queue", lambda: fake_queue)

        ctrl = DigestRefreshController()
        run(ctrl.request_refresh(session))

        # Simulate completion with future cooldown
        async def _complete():
            from sqlalchemy import select
            result = await session.execute(select(JobRun).where(JobRun.id == "digest_refresh"))
            row = result.scalar_one()
            row.running = False
            row.next_allowed_at = datetime.now(tz=timezone.utc) + timedelta(hours=5)
            await session.commit()

        run(_complete())

        # Force=True bypasses cooldown even when next_allowed_at is in future
        status_forced = run(ctrl.request_refresh(session, force=True))
        assert status_forced.job_started is True
        assert len(fake_queue.calls) == 2


# ---------------------------------------------------------------------------
# 3. Queue dispatch: correct job names and payloads
# ---------------------------------------------------------------------------

class TestQueueDispatch:
    def test_visit_enqueues_visit_refresh_with_user_id(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_queue = FakeJobQueue()
        monkeypatch.setattr("app.workers.tasks.get_job_queue", lambda: fake_queue)

        ctrl = VisitRefreshController()
        run(ctrl.request_refresh(session, user_id=42))

        assert fake_queue.calls == [("visit_refresh", {"user_id": 42})]

    def test_digest_enqueues_digest_refresh_with_empty_payload(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_queue = FakeJobQueue()
        monkeypatch.setattr("app.workers.tasks.get_job_queue", lambda: fake_queue)

        ctrl = DigestRefreshController()
        run(ctrl.request_refresh(session))

        assert fake_queue.calls == [("digest_refresh", {})]


# ---------------------------------------------------------------------------
# 4. Migration drift guard
# ---------------------------------------------------------------------------

def _load_migration_module():
    """Load the job_run migration as a module."""
    spec = importlib.util.spec_from_file_location(
        "migration_20260604_job_run",
        _MIGRATION_PATH,
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _apply_migration_to_sqlite() -> sa.engine.Engine:
    """Create a fresh SQLite engine, apply only the job_run migration, and return it."""
    mod = _load_migration_module()
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        op_proxy = Operations(ctx)
        op_proxy._install_proxy()
        try:
            mod.upgrade()
        finally:
            op_proxy._remove_proxy()
    return engine


def test_migration_creates_all_model_columns() -> None:
    """The job_run migration must create exactly the columns that JobRun declares.

    This test applies the migration DDL (NOT Base.metadata.create_all) against
    a fresh SQLite database and asserts column parity with the ORM model.
    It would FAIL if created_at or updated_at were missing from the migration.
    """
    engine = _apply_migration_to_sqlite()

    with engine.connect() as conn:
        inspector = sa.inspect(conn)
        migrated_cols = {c["name"] for c in inspector.get_columns("job_run")}

    model_cols = {c.name for c in JobRun.__table__.columns}

    assert migrated_cols == model_cols, (
        f"Migration column drift detected!\n"
        f"  Migration created: {sorted(migrated_cols)}\n"
        f"  Model declares:    {sorted(model_cols)}\n"
        f"  Missing in migration: {sorted(model_cols - migrated_cols)}\n"
        f"  Extra in migration:   {sorted(migrated_cols - model_cols)}"
    )


def test_migration_includes_created_at_and_updated_at() -> None:
    """Regression test: explicitly assert created_at and updated_at are in the migration."""
    engine = _apply_migration_to_sqlite()

    with engine.connect() as conn:
        inspector = sa.inspect(conn)
        col_names = {c["name"] for c in inspector.get_columns("job_run")}

    assert "created_at" in col_names, "created_at missing from job_run migration"
    assert "updated_at" in col_names, "updated_at missing from job_run migration"


# ---------------------------------------------------------------------------
# 5. RefreshJobStatus shape preservation
# ---------------------------------------------------------------------------

def test_refresh_job_status_has_expected_fields() -> None:
    """RefreshJobStatus must expose the fields the router schemas expect."""
    now = datetime.now(tz=timezone.utc)
    status = RefreshJobStatus(
        job_started=True,
        running=True,
        last_started_at=now,
        last_completed_at=None,
        next_allowed_at=None,
        cooldown_seconds=1800,
        message="Refresh started.",
        last_error=None,
    )
    d = status.__dict__
    assert d["job_started"] is True
    assert d["running"] is True
    assert d["last_started_at"] == now
    assert d["cooldown_seconds"] == 1800
    assert "message" in d
    assert "last_error" in d


def test_visit_controller_cooldown_constant() -> None:
    ctrl = VisitRefreshController()
    assert ctrl._cooldown == timedelta(minutes=30)


def test_digest_controller_cooldown_constant() -> None:
    ctrl = DigestRefreshController()
    assert ctrl._cooldown == timedelta(hours=6)
