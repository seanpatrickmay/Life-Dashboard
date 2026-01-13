from __future__ import annotations

import os
from pathlib import Path

from google import genai
from google.oauth2 import service_account

from app.core.config import settings


def _resolve_sa_path() -> Path | None:
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

    return None


def build_genai_client(*, http_options=None) -> genai.Client:
    api_key = os.environ.get("GOOGLE_API_KEY")
    kwargs: dict[str, object] = {}
    if http_options:
        kwargs["http_options"] = http_options
    if api_key:
        kwargs["api_key"] = api_key
        return genai.Client(**kwargs)

    kwargs.update(
        {
            "vertexai": True,
            "project": settings.vertex_project_id,
            "location": settings.vertex_location,
        }
    )
    sa_path = _resolve_sa_path()
    if sa_path:
        kwargs["credentials"] = service_account.Credentials.from_service_account_file(
            sa_path
        )
    return genai.Client(**kwargs)
