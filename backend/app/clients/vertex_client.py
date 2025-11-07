"""Vertex AI text generation helper using Gemini."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import vertexai
from google.oauth2 import service_account
from loguru import logger
from vertexai.generative_models import GenerativeModel

from app.core.config import settings


def _resolve_sa_path() -> Path:
    """
    Resolve a usable service-account JSON path.
    Prefers the in-container mount (VERTEX_SERVICE_ACCOUNT_JSON) and falls back to host paths for local runs.
    """
    candidates: list[str] = []
    for value in (
        os.environ.get("VERTEX_SERVICE_ACCOUNT_JSON"),
        settings.vertex_sa_path,
        os.environ.get("VERTEX_SERVICE_ACCOUNT_JSON_HOST"),
        settings.vertex_service_account_json_host,
    ):
        if value and value not in candidates:
            candidates.append(value)

    for raw_path in candidates:
        path = Path(raw_path).expanduser()
        if path.exists():
            return path

    raise FileNotFoundError(
        "Vertex service account file not found. Set VERTEX_SERVICE_ACCOUNT_JSON "
        "to the container mount (/secrets/vertex-service-account.json) or "
        "VERTEX_SERVICE_ACCOUNT_JSON_HOST to the host file path. Checked paths: "
        f"{', '.join(candidates) if candidates else 'none provided'}"
    )


def init_vertex() -> GenerativeModel:
    sa_path = _resolve_sa_path()
    credentials = service_account.Credentials.from_service_account_file(sa_path)
    logger.info("Loaded Vertex service account credentials from {}", sa_path)
    vertexai.init(
        project=settings.vertex_project_id,
        location=settings.vertex_location,
        credentials=credentials,
    )
    model = GenerativeModel(settings.vertex_model_name)
    return model


class VertexClient:
    def __init__(self) -> None:
        self.model = init_vertex()

    async def generate_text(self, prompt: str) -> tuple[str, Optional[int]]:
        logger.info("Calling Vertex AI: model={}", settings.vertex_model_name)

        def _predict() -> tuple[str, Optional[int]]:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 30000,
                    "top_k": 40,
                    "top_p": 0.95,
                },
            )
            parts = response.candidates[0].content.parts if response.candidates else []
            logger.debug(
                "Vertex raw parts count=%s, types=%s",
                len(parts),
                [getattr(part, "mime_type", getattr(part, "text", type(part).__name__)) for part in parts],
            )
            text = getattr(response, "text", None)
            if not text and parts:
                text = "\n".join(part.text for part in parts if getattr(part, "text", None))
            token_info = getattr(response, "usage_metadata", None)
            total_tokens = getattr(token_info, "total_token_count", None)
            return text, total_tokens

        text, tokens = await asyncio.to_thread(_predict)
        return text, tokens
