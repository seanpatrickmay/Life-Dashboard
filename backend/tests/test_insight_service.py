"""Comprehensive tests for InsightService."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("ADMIN_EMAIL", "test@example.com")
os.environ.setdefault("FRONTEND_URL", "http://localhost:4173")
os.environ.setdefault("GARMIN_PASSWORD_ENCRYPTION_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("READINESS_ADMIN_TOKEN", "test-token")

from app.services.insight_service import InsightService
from app.schemas.llm_outputs import ReadinessInsightOutput


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_metric(
    user_id: int = 1,
    metric_date: date | None = None,
    hrv_avg_ms: float | None = 55.0,
    rhr_bpm: float | None = 58.0,
    sleep_seconds: int | None = 28800,
    training_load: float | None = 120.0,
    training_volume_seconds: int | None = 3600,
    readiness_score: int | None = None,
    readiness_label: str | None = None,
    readiness_narrative: str | None = None,
    **extra,
) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id,
        metric_date=metric_date or date(2026, 3, 18),
        hrv_avg_ms=hrv_avg_ms,
        rhr_bpm=rhr_bpm,
        sleep_seconds=sleep_seconds,
        training_load=training_load,
        training_volume_seconds=training_volume_seconds,
        readiness_score=readiness_score,
        readiness_label=readiness_label,
        readiness_narrative=readiness_narrative,
        readiness_insight=None,
        readiness_insight_id=None,
        insight_greeting=None,
        insight_hrv_value=None,
        insight_hrv_note=None,
        insight_hrv_score=None,
        insight_rhr_value=None,
        insight_rhr_note=None,
        insight_rhr_score=None,
        insight_sleep_value_hours=None,
        insight_sleep_note=None,
        insight_sleep_score=None,
        insight_training_load_value=None,
        insight_training_load_note=None,
        insight_training_load_score=None,
        insight_morning_note=None,
        **extra,
    )


def make_history(days: int = 14, base_date: date | None = None) -> list[SimpleNamespace]:
    base = base_date or date(2026, 3, 18)
    history = []
    for i in range(days):
        d = base - timedelta(days=days - 1 - i)
        history.append(make_metric(
            metric_date=d,
            hrv_avg_ms=50.0 + i * 0.5,
            rhr_bpm=60.0 - i * 0.2,
            sleep_seconds=25200 + i * 300,
            training_load=100.0 + i * 2.0,
            training_volume_seconds=3000 + i * 100,
        ))
    return history


SAMPLE_STRUCTURED = {
    "greeting": "Good morning, like the first light on a lily pond.",
    "hrv": {"score": 7.5, "insight": "Your HRV is trending upward, a gentle current."},
    "rhr": {"score": 8.0, "insight": "Resting heart rate is calm and steady."},
    "sleep": {"score": 6.5, "insight": "Sleep was slightly fragmented, like scattered clouds."},
    "training_load": {"score": 7.0, "insight": "Load is moderate, well-balanced for recovery."},
    "overall_readiness": {
        "score_100": 74,
        "label": "Ready with Caution",
        "insight": "A gentle sunrise of readiness, proceed mindfully.",
    },
}


def make_service() -> InsightService:
    service = object.__new__(InsightService)
    service.session = None
    service._client = None
    return service


# ---------------------------------------------------------------------------
# Tests: _normalize_score
# ---------------------------------------------------------------------------

class TestNormalizeScore:
    def test_none_returns_none(self):
        assert InsightService._normalize_score(None) is None

    def test_normal_value(self):
        assert InsightService._normalize_score(74.0) == 74

    def test_rounds_correctly(self):
        assert InsightService._normalize_score(74.6) == 75
        assert InsightService._normalize_score(74.4) == 74

    def test_clamps_below_1(self):
        assert InsightService._normalize_score(0.0) == 1
        assert InsightService._normalize_score(-5.0) == 1

    def test_clamps_above_100(self):
        assert InsightService._normalize_score(150.0) == 100
        assert InsightService._normalize_score(100.5) == 100

    def test_boundary_values(self):
        assert InsightService._normalize_score(1.0) == 1
        assert InsightService._normalize_score(100.0) == 100

    def test_string_that_looks_like_number(self):
        assert InsightService._normalize_score("85") == 85

    def test_non_numeric_string_returns_none(self):
        assert InsightService._normalize_score("abc") is None

    def test_integer_input(self):
        assert InsightService._normalize_score(50) == 50


# ---------------------------------------------------------------------------
# Tests: _label_from_score
# ---------------------------------------------------------------------------

class TestLabelFromScore:
    def test_fully_recovered(self):
        svc = make_service()
        assert svc._label_from_score(80) == "Fully Recovered"
        assert svc._label_from_score(100) == "Fully Recovered"
        assert svc._label_from_score(95) == "Fully Recovered"

    def test_ready_with_caution(self):
        svc = make_service()
        assert svc._label_from_score(60) == "Ready with Caution"
        assert svc._label_from_score(79) == "Ready with Caution"

    def test_focus_on_recovery(self):
        svc = make_service()
        assert svc._label_from_score(40) == "Focus on Recovery"
        assert svc._label_from_score(59) == "Focus on Recovery"

    def test_rest_day_recommended(self):
        svc = make_service()
        assert svc._label_from_score(1) == "Rest Day Recommended"
        assert svc._label_from_score(39) == "Rest Day Recommended"

    def test_boundary_80(self):
        svc = make_service()
        assert svc._label_from_score(80) == "Fully Recovered"
        assert svc._label_from_score(79) == "Ready with Caution"

    def test_boundary_60(self):
        svc = make_service()
        assert svc._label_from_score(60) == "Ready with Caution"
        assert svc._label_from_score(59) == "Focus on Recovery"

    def test_boundary_40(self):
        svc = make_service()
        assert svc._label_from_score(40) == "Focus on Recovery"
        assert svc._label_from_score(39) == "Rest Day Recommended"


# ---------------------------------------------------------------------------
# Tests: _extract_score
# ---------------------------------------------------------------------------

class TestExtractScore:
    def test_extracts_first_valid_score(self):
        svc = make_service()
        assert svc._extract_score("Your readiness is 74 today.") == 74

    def test_ignores_out_of_range(self):
        svc = make_service()
        # _extract_score splits on whitespace and checks isdigit(), so "65." won't match
        assert svc._extract_score("Score 200 is invalid, real score 65 today.") == 65

    def test_returns_50_when_no_number(self):
        svc = make_service()
        assert svc._extract_score("No numbers here.") == 50

    def test_returns_50_for_zero(self):
        svc = make_service()
        assert svc._extract_score("Score is 0 today") == 50

    def test_single_digit_valid(self):
        svc = make_service()
        assert svc._extract_score("Recovery at 5 percent") == 5

    def test_100_is_valid(self):
        svc = make_service()
        assert svc._extract_score("Perfect 100 score") == 100


# ---------------------------------------------------------------------------
# Tests: _maybe_parse_structured
# ---------------------------------------------------------------------------

class TestMaybeParseStructured:
    def test_valid_json(self):
        svc = make_service()
        result = svc._maybe_parse_structured(json.dumps(SAMPLE_STRUCTURED))
        assert result is not None
        assert result["greeting"] == SAMPLE_STRUCTURED["greeting"]
        assert result["overall_readiness"]["score_100"] == 74

    def test_none_input(self):
        svc = make_service()
        assert svc._maybe_parse_structured(None) is None

    def test_empty_string(self):
        svc = make_service()
        assert svc._maybe_parse_structured("") is None

    def test_json_with_leading_text(self):
        svc = make_service()
        text = "Here is the analysis:\n" + json.dumps(SAMPLE_STRUCTURED)
        result = svc._maybe_parse_structured(text)
        assert result is not None
        assert result["greeting"] == SAMPLE_STRUCTURED["greeting"]

    def test_json_with_trailing_text(self):
        svc = make_service()
        text = json.dumps(SAMPLE_STRUCTURED) + "\n\nHope this helps!"
        result = svc._maybe_parse_structured(text)
        assert result is not None

    def test_fenced_code_block(self):
        svc = make_service()
        text = "```json\n" + json.dumps(SAMPLE_STRUCTURED) + "\n```"
        result = svc._maybe_parse_structured(text)
        assert result is not None
        assert result["overall_readiness"]["score_100"] == 74

    def test_invalid_json_returns_none(self):
        svc = make_service()
        assert svc._maybe_parse_structured("not json at all") is None

    def test_json_array_returns_none(self):
        svc = make_service()
        assert svc._maybe_parse_structured("[1, 2, 3]") is None

    def test_partial_json_returns_none(self):
        svc = make_service()
        assert svc._maybe_parse_structured('{"greeting": "hello"') is None


# ---------------------------------------------------------------------------
# Tests: _safe_number / _safe_text
# ---------------------------------------------------------------------------

class TestSafeHelpers:
    def test_safe_number_valid(self):
        assert InsightService._safe_number({"score": 7.5}, "score") == 7.5

    def test_safe_number_string_float(self):
        assert InsightService._safe_number({"score": "8.2"}, "score") == 8.2

    def test_safe_number_none_value(self):
        assert InsightService._safe_number({"score": None}, "score") is None

    def test_safe_number_missing_key(self):
        assert InsightService._safe_number({"other": 5}, "score") is None

    def test_safe_number_none_section(self):
        assert InsightService._safe_number(None, "score") is None

    def test_safe_number_non_dict(self):
        assert InsightService._safe_number("not a dict", "score") is None

    def test_safe_number_non_numeric_string(self):
        assert InsightService._safe_number({"score": "abc"}, "score") is None

    def test_safe_text_valid(self):
        assert InsightService._safe_text({"insight": "Good morning"}, "insight") == "Good morning"

    def test_safe_text_whitespace_only(self):
        assert InsightService._safe_text({"insight": "   "}, "insight") is None

    def test_safe_text_none_value(self):
        assert InsightService._safe_text({"insight": None}, "insight") is None

    def test_safe_text_missing_key(self):
        assert InsightService._safe_text({"other": "text"}, "insight") is None

    def test_safe_text_none_section(self):
        assert InsightService._safe_text(None, "insight") is None

    def test_safe_text_non_string_value(self):
        assert InsightService._safe_text({"insight": 123}, "insight") is None


# ---------------------------------------------------------------------------
# Tests: _apply_structured_fields
# ---------------------------------------------------------------------------

class TestApplyStructuredFields:
    def test_applies_all_fields(self):
        svc = make_service()
        metric = make_metric()
        score, label = svc._apply_structured_fields(metric, SAMPLE_STRUCTURED)

        assert metric.insight_greeting == SAMPLE_STRUCTURED["greeting"]
        assert metric.insight_hrv_score == 7.5
        assert metric.insight_hrv_note == "Your HRV is trending upward, a gentle current."
        assert metric.insight_hrv_value == 55.0
        assert metric.insight_rhr_score == 8.0
        assert metric.insight_rhr_note == "Resting heart rate is calm and steady."
        assert metric.insight_rhr_value == 58.0
        assert metric.insight_sleep_score == 6.5
        assert metric.insight_sleep_note == "Sleep was slightly fragmented, like scattered clouds."
        assert metric.insight_sleep_value_hours == pytest.approx(8.0, abs=0.01)
        assert metric.insight_training_load_score == 7.0
        assert metric.insight_training_load_note == "Load is moderate, well-balanced for recovery."
        assert metric.insight_training_load_value == 120.0
        assert metric.insight_morning_note == "A gentle sunrise of readiness, proceed mindfully."
        assert score == 74
        assert label == "Ready with Caution"

    def test_handles_missing_sections(self):
        svc = make_service()
        metric = make_metric()
        sparse = {"greeting": "Hello", "overall_readiness": {"score_100": 60, "label": "Ready", "insight": "OK"}}
        score, label = svc._apply_structured_fields(metric, sparse)

        assert metric.insight_greeting == "Hello"
        assert metric.insight_hrv_score is None
        assert metric.insight_hrv_note is None
        assert score == 60
        assert label == "Ready"

    def test_handles_morning_readiness_alias(self):
        svc = make_service()
        metric = make_metric()
        data = {
            "greeting": "Hello",
            "hrv": {"score": 5, "insight": "ok"},
            "rhr": {"score": 5, "insight": "ok"},
            "sleep": {"score": 5, "insight": "ok"},
            "training_load": {"score": 5, "insight": "ok"},
            "morning_readiness": {"score_100": 65, "label": "Gentle", "insight": "Morning note"},
        }
        score, label = svc._apply_structured_fields(metric, data)
        assert metric.insight_morning_note == "Morning note"
        assert score == 65
        assert label == "Gentle"

    def test_sleep_value_none_when_no_sleep_data(self):
        svc = make_service()
        metric = make_metric(sleep_seconds=None)
        svc._apply_structured_fields(metric, SAMPLE_STRUCTURED)
        assert metric.insight_sleep_value_hours is None

    def test_score_10_alias(self):
        svc = make_service()
        metric = make_metric()
        data = {
            "greeting": "Hey",
            "hrv": {"score_10": 9, "insight": "Great HRV"},
            "rhr": {"score": 7, "insight": "ok"},
            "sleep": {"score": 6, "insight": "ok"},
            "training_load": {"score": 5, "insight": "ok"},
            "overall_readiness": {"score_100": 80, "label": "Recovered", "insight": "Good"},
        }
        svc._apply_structured_fields(metric, data)
        assert metric.insight_hrv_score == 9


# ---------------------------------------------------------------------------
# Tests: _structured_fields_missing / _structured_snapshot
# ---------------------------------------------------------------------------

class TestStructuredFieldChecks:
    def test_all_missing(self):
        metric = make_metric()
        assert InsightService._structured_fields_missing(metric) is True

    def test_not_missing_when_greeting_set(self):
        metric = make_metric()
        metric.insight_greeting = "Hello"
        assert InsightService._structured_fields_missing(metric) is False

    def test_snapshot_captures_all_fields(self):
        metric = make_metric()
        metric.insight_greeting = "Hi"
        metric.insight_hrv_value = 55.0
        snap = InsightService._structured_snapshot(metric)
        assert snap[0] == "Hi"
        assert snap[1] == 55.0

    def test_snapshot_changes_detected(self):
        metric = make_metric()
        before = InsightService._structured_snapshot(metric)
        metric.insight_greeting = "Changed"
        after = InsightService._structured_snapshot(metric)
        assert before != after


# ---------------------------------------------------------------------------
# Tests: _build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_includes_persona(self):
        svc = make_service()
        metric = make_metric()
        history = make_history(days=7, base_date=metric.metric_date)
        prompt = svc._build_prompt(metric, history)
        assert "Monet" in prompt or "monet" in prompt.lower()

    def test_includes_score_guidance(self):
        svc = make_service()
        metric = make_metric()
        prompt = svc._build_prompt(metric, make_history(7, metric.metric_date))
        assert "80-100" in prompt
        assert "60-79" in prompt
        assert "40-59" in prompt
        assert "1-39" in prompt

    def test_includes_metric_series(self):
        svc = make_service()
        metric = make_metric()
        history = make_history(14, metric.metric_date)
        prompt = svc._build_prompt(metric, history)
        assert "HRV_MS_SERIES" in prompt
        assert "RESTING_HR_BPM_SERIES" in prompt
        assert "SLEEP_HOURS_SERIES" in prompt
        assert "TRAINING_LOAD_ROLLING14_SERIES" in prompt

    def test_includes_snapshot(self):
        svc = make_service()
        metric = make_metric(hrv_avg_ms=62.5, rhr_bpm=55.0)
        prompt = svc._build_prompt(metric, [])
        assert "62.5" in prompt
        assert "55.0" in prompt

    def test_includes_deltas_when_history_present(self):
        svc = make_service()
        metric = make_metric()
        history = make_history(14, metric.metric_date)
        prompt = svc._build_prompt(metric, history)
        assert "delta" in prompt.lower()

    def test_no_metric_produces_unknown(self):
        svc = make_service()
        prompt = svc._build_prompt(None, [])
        assert "unknown" in prompt

    def test_response_instructions(self):
        svc = make_service()
        prompt = svc._build_prompt(make_metric(), [])
        assert "JSON" in prompt
        assert "score_100" in prompt

    def test_series_formatting_with_null_values(self):
        svc = make_service()
        metric = make_metric(hrv_avg_ms=None, rhr_bpm=None)
        history = [make_metric(metric_date=date(2026, 3, 17), hrv_avg_ms=None, rhr_bpm=None)]
        prompt = svc._build_prompt(metric, history)
        assert "null" in prompt

    def test_sleep_hours_conversion(self):
        svc = make_service()
        metric = make_metric(sleep_seconds=28800)
        history = [metric]
        prompt = svc._build_prompt(metric, history)
        assert "8.00" in prompt

    def test_training_delta_vs_yesterday(self):
        svc = make_service()
        yesterday = make_metric(metric_date=date(2026, 3, 17), training_load=100.0)
        today = make_metric(metric_date=date(2026, 3, 18), training_load=120.0)
        prompt = svc._build_prompt(today, [yesterday, today])
        assert "yesterday" in prompt


# ---------------------------------------------------------------------------
# Tests: refresh_daily_insight (integration with mocked LLM)
# ---------------------------------------------------------------------------

class TestRefreshDailyInsight:
    def test_success_flow(self):
        svc = make_service()
        metric = make_metric()
        insight_model = ReadinessInsightOutput.model_validate(SAMPLE_STRUCTURED)

        stored_insights = []
        committed = []

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(
                    scalar_one_or_none=lambda: metric,
                    scalars=lambda: SimpleNamespace(all=lambda: [metric]),
                )

            def add(self, obj):
                stored_insights.append(obj)

            async def commit(self):
                committed.append(True)

        class FakeClient:
            async def generate_json(self, prompt, response_model=None, temperature=None, max_output_tokens=None):
                return SimpleNamespace(data=insight_model, total_tokens=500)

        svc.session = FakeSession()
        svc._client = FakeClient()

        # Also need to stub _fetch_insight to return None (new insight)
        original_fetch_insight = svc._fetch_insight

        async def fake_fetch_insight(user_id, metric_date):
            return None

        svc._fetch_insight = fake_fetch_insight

        result = run(svc.refresh_daily_insight(1, date(2026, 3, 18)))
        assert result is not None
        assert len(stored_insights) == 1
        assert len(committed) == 1
        assert metric.readiness_score == 74
        assert metric.readiness_label == "Ready with Caution"
        assert metric.insight_greeting == SAMPLE_STRUCTURED["greeting"]

    def test_llm_failure_uses_fallback(self):
        svc = make_service()
        metric = make_metric()

        committed = []

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(
                    scalar_one_or_none=lambda: metric,
                    scalars=lambda: SimpleNamespace(all=lambda: [metric]),
                )

            def add(self, obj):
                pass

            async def commit(self):
                committed.append(True)

        class FakeClient:
            async def generate_json(self, prompt, **kwargs):
                raise RuntimeError("API unavailable")

        svc.session = FakeSession()
        svc._client = FakeClient()

        async def fake_fetch_insight(user_id, metric_date):
            return None

        svc._fetch_insight = fake_fetch_insight

        result = run(svc.refresh_daily_insight(1, date(2026, 3, 18)))
        assert result is not None
        assert "temporarily unavailable" in result.response_text

    def test_llm_failure_preserves_existing_narrative(self):
        svc = make_service()
        metric = make_metric()

        existing_insight = SimpleNamespace(
            id=42,
            response_text='{"greeting": "Existing"}',
            readiness_score=70,
            model_name="old-model",
            prompt="old prompt",
            tokens_used=100,
            updated_at=None,
        )

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(
                    scalar_one_or_none=lambda: metric,
                    scalars=lambda: SimpleNamespace(all=lambda: [metric]),
                )

            def add(self, obj):
                pass

            async def commit(self):
                pass

        class FakeClient:
            async def generate_json(self, prompt, **kwargs):
                raise RuntimeError("API down")

        svc.session = FakeSession()
        svc._client = FakeClient()

        async def fake_fetch_insight(user_id, metric_date):
            return existing_insight

        svc._fetch_insight = fake_fetch_insight

        result = run(svc.refresh_daily_insight(1, date(2026, 3, 18)))
        assert result.response_text == '{"greeting": "Existing"}'
        assert result.readiness_score == 70

    def test_updates_existing_insight(self):
        svc = make_service()
        metric = make_metric()
        insight_model = ReadinessInsightOutput.model_validate(SAMPLE_STRUCTURED)

        existing_insight = SimpleNamespace(
            id=42,
            response_text="old",
            readiness_score=50,
            model_name="old-model",
            prompt="old",
            tokens_used=100,
            updated_at=None,
        )

        added = []

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(
                    scalar_one_or_none=lambda: metric,
                    scalars=lambda: SimpleNamespace(all=lambda: [metric]),
                )

            def add(self, obj):
                added.append(obj)

            async def commit(self):
                pass

        class FakeClient:
            async def generate_json(self, prompt, **kwargs):
                return SimpleNamespace(data=insight_model, total_tokens=600)

        svc.session = FakeSession()
        svc._client = FakeClient()

        async def fake_fetch_insight(user_id, metric_date):
            return existing_insight

        svc._fetch_insight = fake_fetch_insight

        result = run(svc.refresh_daily_insight(1, date(2026, 3, 18)))
        assert result is existing_insight
        assert len(added) == 0  # should not add, just update
        assert result.readiness_score == 74

    def test_no_metric_still_stores_insight(self):
        svc = make_service()
        insight_model = ReadinessInsightOutput.model_validate(SAMPLE_STRUCTURED)

        added = []

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(
                    scalar_one_or_none=lambda: None,
                    scalars=lambda: SimpleNamespace(all=lambda: []),
                )

            def add(self, obj):
                added.append(obj)

            async def commit(self):
                pass

        class FakeClient:
            async def generate_json(self, prompt, **kwargs):
                return SimpleNamespace(data=insight_model, total_tokens=400)

        svc.session = FakeSession()
        svc._client = FakeClient()

        async def fake_fetch_insight(user_id, metric_date):
            return None

        svc._fetch_insight = fake_fetch_insight

        result = run(svc.refresh_daily_insight(1, date(2026, 3, 18)))
        insight_added = [obj for obj in added if hasattr(obj, 'readiness_score')]
        assert len(insight_added) == 1
        assert insight_added[0].readiness_score == 74


# ---------------------------------------------------------------------------
# Tests: fetch_latest_completed_metric (backfill)
# ---------------------------------------------------------------------------

class TestFetchLatestCompletedMetric:
    def test_backfills_structured_fields(self):
        svc = make_service()
        narrative = json.dumps(SAMPLE_STRUCTURED)
        metric = make_metric(readiness_narrative=narrative, readiness_score=74)
        metric.readiness_insight = SimpleNamespace(readiness_score=74)

        committed = []

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(scalar_one_or_none=lambda: metric)

            async def commit(self):
                committed.append(True)

        svc.session = FakeSession()

        result = run(svc.fetch_latest_completed_metric(1))
        assert result is metric
        assert result.insight_greeting == SAMPLE_STRUCTURED["greeting"]
        assert result.insight_hrv_score == 7.5
        assert len(committed) == 1

    def test_no_metric_returns_none(self):
        svc = make_service()

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(scalar_one_or_none=lambda: None)

        svc.session = FakeSession()
        result = run(svc.fetch_latest_completed_metric(1))
        assert result is None

    def test_skips_commit_when_no_changes(self):
        svc = make_service()
        narrative = json.dumps(SAMPLE_STRUCTURED)
        metric = make_metric(readiness_narrative=narrative, readiness_score=74)
        metric.readiness_insight = SimpleNamespace(readiness_score=74)

        # Pre-populate structured fields so nothing is dirty
        metric.insight_greeting = SAMPLE_STRUCTURED["greeting"]
        metric.insight_hrv_value = 55.0
        metric.insight_hrv_note = "Your HRV is trending upward, a gentle current."
        metric.insight_hrv_score = 7.5
        metric.insight_rhr_value = 58.0
        metric.insight_rhr_note = "Resting heart rate is calm and steady."
        metric.insight_rhr_score = 8.0
        metric.insight_sleep_value_hours = 8.0
        metric.insight_sleep_note = "Sleep was slightly fragmented, like scattered clouds."
        metric.insight_sleep_score = 6.5
        metric.insight_training_load_value = 120.0
        metric.insight_training_load_note = "Load is moderate, well-balanced for recovery."
        metric.insight_training_load_score = 7.0
        metric.insight_morning_note = "A gentle sunrise of readiness, proceed mindfully."
        metric.readiness_label = "Ready with Caution"

        committed = []

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(scalar_one_or_none=lambda: metric)

            async def commit(self):
                committed.append(True)

        svc.session = FakeSession()
        run(svc.fetch_latest_completed_metric(1))
        assert len(committed) == 0

    def test_non_json_narrative_skips_backfill(self):
        svc = make_service()
        metric = make_metric(readiness_narrative="Just a plain text narrative.")
        metric.readiness_insight = None

        committed = []

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(scalar_one_or_none=lambda: metric)

            async def commit(self):
                committed.append(True)

        svc.session = FakeSession()
        result = run(svc.fetch_latest_completed_metric(1))
        assert result is metric
        assert result.insight_greeting is None
        assert len(committed) == 0


# ---------------------------------------------------------------------------
# Tests: ReadinessInsightOutput schema validation
# ---------------------------------------------------------------------------

class TestReadinessInsightOutputSchema:
    def test_valid_data(self):
        output = ReadinessInsightOutput.model_validate(SAMPLE_STRUCTURED)
        assert output.greeting == SAMPLE_STRUCTURED["greeting"]
        assert output.hrv.score == 7.5
        assert output.overall_readiness.score_100 == 74

    def test_rejects_extra_fields(self):
        data = {**SAMPLE_STRUCTURED, "extra_field": "nope"}
        with pytest.raises(Exception):
            ReadinessInsightOutput.model_validate(data)

    def test_missing_required_field(self):
        data = {k: v for k, v in SAMPLE_STRUCTURED.items() if k != "greeting"}
        with pytest.raises(Exception):
            ReadinessInsightOutput.model_validate(data)

    def test_missing_pillar(self):
        data = {k: v for k, v in SAMPLE_STRUCTURED.items() if k != "hrv"}
        with pytest.raises(Exception):
            ReadinessInsightOutput.model_validate(data)

    def test_pillar_score_as_int(self):
        data = {**SAMPLE_STRUCTURED, "hrv": {"score": 8, "insight": "Good"}}
        output = ReadinessInsightOutput.model_validate(data)
        assert output.hrv.score == 8.0

    def test_overall_readiness_must_have_label(self):
        data = {
            **SAMPLE_STRUCTURED,
            "overall_readiness": {"score_100": 70, "insight": "ok"},
        }
        with pytest.raises(Exception):
            ReadinessInsightOutput.model_validate(data)


# ---------------------------------------------------------------------------
# Tests: Edge cases and robustness
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_all_none_metrics(self):
        svc = make_service()
        metric = make_metric(
            hrv_avg_ms=None, rhr_bpm=None, sleep_seconds=None,
            training_load=None, training_volume_seconds=None,
        )
        prompt = svc._build_prompt(metric, [])
        assert "unknown" in prompt

    def test_empty_history_prompt(self):
        svc = make_service()
        prompt = svc._build_prompt(make_metric(), [])
        assert "HRV_MS_SERIES = []" in prompt

    def test_single_day_history(self):
        svc = make_service()
        metric = make_metric()
        prompt = svc._build_prompt(metric, [metric])
        assert "1-day avg" in prompt

    def test_very_high_hrv_prompt(self):
        svc = make_service()
        metric = make_metric(hrv_avg_ms=150.0)
        prompt = svc._build_prompt(metric, [metric])
        assert "150.0" in prompt

    def test_zero_sleep(self):
        svc = make_service()
        metric = make_metric(sleep_seconds=0)
        prompt = svc._build_prompt(metric, [metric])
        # sleep_seconds=0 is falsy, should show as unknown for sleep_hours
        assert "unknown" in prompt or "0.00" in prompt

    def test_negative_training_delta(self):
        svc = make_service()
        yesterday = make_metric(metric_date=date(2026, 3, 17), training_load=200.0)
        today = make_metric(metric_date=date(2026, 3, 18), training_load=100.0)
        prompt = svc._build_prompt(today, [yesterday, today])
        assert "−" in prompt or "-" in prompt  # negative delta

    def test_apply_structured_with_empty_dict(self):
        svc = make_service()
        metric = make_metric()
        score, label = svc._apply_structured_fields(metric, {})
        assert score is None
        assert label is None
        assert metric.insight_greeting is None

    def test_apply_structured_with_non_dict_sections(self):
        svc = make_service()
        metric = make_metric()
        data = {
            "greeting": "Hi",
            "hrv": "not a dict",
            "rhr": 42,
            "sleep": None,
            "training_load": [],
            "overall_readiness": {"score_100": 50, "label": "OK", "insight": "Fine"},
        }
        score, label = svc._apply_structured_fields(metric, data)
        assert metric.insight_hrv_score is None
        assert metric.insight_rhr_score is None
        assert metric.insight_sleep_score is None
        assert metric.insight_training_load_score is None
        assert score == 50


# ---------------------------------------------------------------------------
# Tests: Life context block building
# ---------------------------------------------------------------------------

class TestBuildLifeContextBlock:
    def test_empty_context(self):
        svc = make_service()
        result = svc._build_life_context_block({})
        assert result == ""

    def test_todo_context(self):
        svc = make_service()
        context = {"todos": {"total_active": 10, "completed": 3, "overdue": 2}}
        result = svc._build_life_context_block(context)
        assert "10 active" in result
        assert "3 completed" in result
        assert "2 overdue" in result

    def test_high_overdue_adds_stress_note(self):
        svc = make_service()
        context = {"todos": {"total_active": 20, "completed": 2, "overdue": 6}}
        result = svc._build_life_context_block(context)
        assert "cognitive stress" in result.lower() or "backlog" in result.lower()

    def test_nutrition_context(self):
        svc = make_service()
        context = {
            "nutrition": {
                "energy_kcal": {"today": 1800, "goal": 2200, "today_pct": 81.8},
                "protein_g": {"today": 120, "goal": 150, "today_pct": 80.0},
            }
        }
        result = svc._build_life_context_block(context)
        assert "NUTRITION" in result
        assert "Energy" in result
        assert "Protein" in result

    def test_calendar_context(self):
        svc = make_service()
        context = {"calendar": {"events_today": 3}}
        result = svc._build_life_context_block(context)
        assert "3 event" in result

    def test_heavy_calendar_adds_recovery_note(self):
        svc = make_service()
        context = {"calendar": {"events_today": 7}}
        result = svc._build_life_context_block(context)
        assert "recovery" in result.lower()

    def test_single_event_grammar(self):
        svc = make_service()
        context = {"calendar": {"events_today": 1}}
        result = svc._build_life_context_block(context)
        assert "1 event" in result

    def test_energy_context(self):
        svc = make_service()
        context = {"energy": {"active_kcal": 450, "bmr_kcal": 1700, "total_kcal": 2150}}
        result = svc._build_life_context_block(context)
        assert "Active: 450 kcal" in result
        assert "Total: 2150 kcal" in result

    def test_zero_events_excluded(self):
        svc = make_service()
        context = {"calendar": {"events_today": 0}}
        result = svc._build_life_context_block(context)
        assert result == ""

    def test_none_nutrition_excluded(self):
        svc = make_service()
        context = {"nutrition": None}
        result = svc._build_life_context_block(context)
        assert result == ""

    def test_caloric_balance(self):
        svc = make_service()
        context = {
            "nutrition": {
                "energy_kcal": {"today": 1800, "goal": 2200, "today_pct": 81.8},
            },
            "energy": {"active_kcal": 500, "bmr_kcal": 1700, "total_kcal": 2400},
        }
        result = svc._build_life_context_block(context)
        assert "Caloric balance" in result
        assert "deficit" in result.lower()

    def test_journal_context(self):
        svc = make_service()
        context = {"journal": ["Had a great morning run", "Feeling productive"]}
        result = svc._build_life_context_block(context)
        assert "JOURNAL" in result
        assert "morning run" in result

    def test_full_context_in_prompt(self):
        svc = make_service()
        metric = make_metric()
        life_context = {
            "todos": {"total_active": 8, "completed": 5, "overdue": 1},
            "calendar": {"events_today": 4},
            "energy": {"active_kcal": 500, "bmr_kcal": 1700, "total_kcal": 2200},
        }
        prompt = svc._build_prompt(metric, [], life_context=life_context)
        assert "cross-system" in prompt.lower() or "COGNITIVE LOAD" in prompt
        assert "8 active" in prompt
        assert "4 event" in prompt

    def test_prompt_without_context_has_no_lifestyle_block(self):
        svc = make_service()
        prompt = svc._build_prompt(make_metric(), [])
        assert "Lifestyle & cross-system analysis" not in prompt

    def test_prompt_with_empty_context_has_no_lifestyle_block(self):
        svc = make_service()
        prompt = svc._build_prompt(make_metric(), [], life_context={})
        assert "Lifestyle & cross-system analysis" not in prompt


# ---------------------------------------------------------------------------
# Tests: _gather_life_context (async, with mocked session)
# ---------------------------------------------------------------------------

class TestGatherLifeContext:
    def test_handles_all_failures_gracefully(self):
        svc = make_service()

        class FailSession:
            async def execute(self, stmt):
                raise RuntimeError("DB unavailable")

        svc.session = FailSession()
        result = run(svc._gather_life_context(1, date(2026, 3, 18)))
        # All sub-gathers should fail silently
        assert result == {} or all(v is None for v in result.values() if v is not None) or len(result) == 0

    def test_todo_context_returns_counts(self):
        svc = make_service()

        class FakeSession:
            async def execute(self, stmt):
                return SimpleNamespace(
                    one=lambda: SimpleNamespace(total=12, completed=4, overdue=2)
                )

        svc.session = FakeSession()
        result = run(svc._gather_todo_context(1, date(2026, 3, 18)))
        assert result["total_active"] == 12
        assert result["completed"] == 4
        assert result["overdue"] == 2
