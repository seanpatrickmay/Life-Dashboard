"""Centralized configuration using Pydantic settings."""
from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings pulled from environment variables."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    app_name: str = "Life Dashboard API"
    api_prefix: str = "/api"
    debug: bool = False

    # Database
    database_url: str = Field(..., env="DATABASE_URL")

    # Garmin
    garmin_email: str | None = Field(None, env="GARMIN_EMAIL")
    garmin_password: str | None = Field(None, env="GARMIN_PASSWORD")
    garmin_tokens_dir: str = Field("/data/garmin", env="GARMIN_TOKENS_DIR")
    garmin_tokens_dir_host: str | None = Field(None, env="GARMIN_TOKENS_DIR_HOST")
    garmin_page_size: int = Field(100, env="GARMIN_PAGE_SIZE")
    garmin_max_activities: int = Field(400, env="GARMIN_MAX_ACTIVITIES")

    # Vertex AI
    vertex_project_id: str = Field(..., env="VERTEX_PROJECT_ID")
    vertex_location: str = Field("us-central1", env="VERTEX_LOCATION")
    vertex_model_name: str = Field("gemini-2.5-flash", env="VERTEX_MODEL_NAME")
    vertex_sa_path: str | None = Field(None, env="VERTEX_SERVICE_ACCOUNT_JSON")
    vertex_service_account_json_host: str | None = Field(None, env="VERTEX_SERVICE_ACCOUNT_JSON_HOST")

    # Scheduler / Admin
    readiness_admin_token: str = Field(..., env="READINESS_ADMIN_TOKEN")
    ingestion_hour_local: int = Field(5, env="INGESTION_HOUR_LOCAL")

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
