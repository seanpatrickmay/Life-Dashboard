"""Centralized configuration using Pydantic settings."""
from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse, urlunparse
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings pulled from environment variables."""

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    app_name: str = "Life Dashboard API"
    api_prefix: str = "/api"
    debug: bool = False

    # Database
    database_url: str = Field(..., env="DATABASE_URL")

    # Environment
    environment: str = Field("local", env="APP_ENV")

    # Auth / Google OAuth (environment-aware)
    google_client_id_local: str | None = Field(None, env="GOOGLE_CLIENT_ID_LOCAL")
    google_client_secret_local: str | None = Field(None, env="GOOGLE_CLIENT_SECRET_LOCAL")
    google_redirect_uri_local: str | None = Field(None, env="GOOGLE_REDIRECT_URI_LOCAL")
    google_client_id_prod: str | None = Field(None, env="GOOGLE_CLIENT_ID_PROD")
    google_client_secret_prod: str | None = Field(None, env="GOOGLE_CLIENT_SECRET_PROD")
    google_redirect_uri_prod: str | None = Field(None, env="GOOGLE_REDIRECT_URI_PROD")
    google_client_id_override: str | None = Field(None, env="GOOGLE_CLIENT_ID")
    google_client_secret_override: str | None = Field(None, env="GOOGLE_CLIENT_SECRET")
    google_redirect_uri_override: str | None = Field(None, env="GOOGLE_REDIRECT_URI")
    google_calendar_redirect_uri_local: str | None = Field(
        None, env="GOOGLE_CALENDAR_REDIRECT_URI_LOCAL"
    )
    google_calendar_redirect_uri_prod: str | None = Field(
        None, env="GOOGLE_CALENDAR_REDIRECT_URI_PROD"
    )
    google_calendar_redirect_uri_override: str | None = Field(
        None, env="GOOGLE_CALENDAR_REDIRECT_URI"
    )
    google_calendar_webhook_url_override: str | None = Field(
        None, env="GOOGLE_CALENDAR_WEBHOOK_URL"
    )
    google_calendar_token_encryption_key: str | None = Field(
        None, env="GOOGLE_CALENDAR_TOKEN_ENCRYPTION_KEY"
    )
    admin_email: str = Field(..., env="ADMIN_EMAIL")
    frontend_url: str = Field(..., env="FRONTEND_URL")
    session_cookie_name: str = Field("ld_session", env="SESSION_COOKIE_NAME")
    session_cookie_domain: str | None = Field(None, env="SESSION_COOKIE_DOMAIN")
    session_cookie_secure: bool = Field(True, env="SESSION_COOKIE_SECURE")
    session_cookie_samesite: str = Field("lax", env="SESSION_COOKIE_SAMESITE")
    session_ttl_hours: int = Field(12, env="SESSION_TTL_HOURS")
    session_ttl_days: int = Field(30, env="SESSION_TTL_DAYS")
    cors_origins: str = Field("", env="CORS_ORIGINS")

    # Garmin
    garmin_email: str | None = Field(None, env="GARMIN_EMAIL")
    garmin_password: str | None = Field(None, env="GARMIN_PASSWORD")
    garmin_tokens_dir: str = Field("/data/garmin", env="GARMIN_TOKENS_DIR")
    garmin_tokens_dir_host: str | None = Field(None, env="GARMIN_TOKENS_DIR_HOST")
    garmin_password_encryption_key: str = Field(..., env="GARMIN_PASSWORD_ENCRYPTION_KEY")
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

    def _select_google_value(
        self,
        *,
        override: str | None,
        local: str | None,
        prod: str | None,
        label: str,
    ) -> str:
        if override:
            return override
        env = (self.environment or "local").lower()
        if env in {"prod", "production"}:
            if prod:
                return prod
            raise ValueError(f"{label} is required for production environment.")
        if local:
            return local
        raise ValueError(f"{label} is required for local environment.")

    def _replace_path(self, url: str, new_path: str) -> str:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))

    def _base_origin(self, url: str) -> str:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))

    @computed_field
    @property
    def google_client_id(self) -> str:
        return self._select_google_value(
            override=self.google_client_id_override,
            local=self.google_client_id_local,
            prod=self.google_client_id_prod,
            label="GOOGLE_CLIENT_ID",
        )

    @computed_field
    @property
    def google_client_secret(self) -> str:
        return self._select_google_value(
            override=self.google_client_secret_override,
            local=self.google_client_secret_local,
            prod=self.google_client_secret_prod,
            label="GOOGLE_CLIENT_SECRET",
        )

    @computed_field
    @property
    def google_redirect_uri(self) -> str:
        return self._select_google_value(
            override=self.google_redirect_uri_override,
            local=self.google_redirect_uri_local,
            prod=self.google_redirect_uri_prod,
            label="GOOGLE_REDIRECT_URI",
        )

    @computed_field
    @property
    def google_calendar_redirect_uri(self) -> str:
        if (
            self.google_calendar_redirect_uri_override
            or self.google_calendar_redirect_uri_local
            or self.google_calendar_redirect_uri_prod
        ):
            return self._select_google_value(
                override=self.google_calendar_redirect_uri_override,
                local=self.google_calendar_redirect_uri_local,
                prod=self.google_calendar_redirect_uri_prod,
                label="GOOGLE_CALENDAR_REDIRECT_URI",
            )
        return self._replace_path(self.google_redirect_uri, "/api/calendar/google/callback")

    @computed_field
    @property
    def google_calendar_webhook_url(self) -> str:
        if self.google_calendar_webhook_url_override:
            return self.google_calendar_webhook_url_override
        base = self._base_origin(self.google_calendar_redirect_uri)
        return f"{base}/api/calendar/google/webhook"

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
