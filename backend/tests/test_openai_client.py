from __future__ import annotations

import asyncio
from types import SimpleNamespace

from pydantic import BaseModel

from app.clients.openai_client import OpenAIResponsesClient


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
