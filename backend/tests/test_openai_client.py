from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace

from pydantic import BaseModel

backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost/life_dashboard_test")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("FRONTEND_URL", "http://localhost:4173")
os.environ.setdefault("GARMIN_PASSWORD_ENCRYPTION_KEY", "test-key")
os.environ.setdefault("READINESS_ADMIN_TOKEN", "test-token")

from app.clients.openai_client import OpenAIResponsesClient  # noqa: E402


class ExampleResponse(BaseModel):
    value: str


class FakeResponsesAPI:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, object]] = []
        self.parse_calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return SimpleNamespace(output_text="hello", usage=SimpleNamespace(total_tokens=12))

    async def parse(self, **kwargs):
        self.parse_calls.append(kwargs)
        return SimpleNamespace(
            output_text='{"value":"ok"}',
            output_parsed=ExampleResponse(value="ok"),
            usage=SimpleNamespace(total_tokens=34),
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponsesAPI()


def test_gpt5_requests_omit_temperature() -> None:
    fake_client = FakeOpenAIClient()
    client = OpenAIResponsesClient(client=fake_client, model_name="gpt-5-mini")

    text_result = asyncio.run(client.generate_text("hello", temperature=0.7, max_output_tokens=120))
    structured_result = asyncio.run(
        client.generate_json(
            "hello",
            response_model=ExampleResponse,
            temperature=0.3,
            max_output_tokens=80,
        )
    )

    assert text_result.text == "hello"
    assert structured_result.data.value == "ok"
    assert "temperature" not in fake_client.responses.create_calls[0]
    assert "temperature" not in fake_client.responses.parse_calls[0]
    assert fake_client.responses.create_calls[0]["max_output_tokens"] == 120
    assert fake_client.responses.parse_calls[0]["max_output_tokens"] == 80


def test_non_gpt5_requests_preserve_temperature() -> None:
    fake_client = FakeOpenAIClient()
    client = OpenAIResponsesClient(client=fake_client, model_name="gpt-4.1-mini")

    asyncio.run(client.generate_text("hello", temperature=0.6))
    asyncio.run(client.generate_json("hello", response_model=ExampleResponse, temperature=0.1))

    assert fake_client.responses.create_calls[0]["temperature"] == 0.6
    assert fake_client.responses.parse_calls[0]["temperature"] == 0.1
