from __future__ import annotations

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import engine


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security response headers to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


from app.routers import (
  admin,
  assistant,
  auth,
  calendar,
  garmin,
  insights,
  journal,
  metrics,
  news,
  nutrition,
  projects,
  system,
  time,
  user,
  todos,
  todos_batch,
  workspace,
)

configure_logging(settings.debug)

app = FastAPI(title=settings.app_name)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
if not origins:
    origins = [settings.frontend_url]

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(garmin.router, prefix=settings.api_prefix)
app.include_router(metrics.router, prefix=settings.api_prefix)
app.include_router(insights.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(time.router, prefix=settings.api_prefix)
app.include_router(news.router, prefix=settings.api_prefix)
app.include_router(nutrition.router, prefix=settings.api_prefix)
app.include_router(user.router, prefix=settings.api_prefix)
app.include_router(system.router, prefix=settings.api_prefix)
app.include_router(todos.router, prefix=settings.api_prefix)
app.include_router(todos_batch.router, prefix=settings.api_prefix)
app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(workspace.router, prefix=settings.api_prefix)
app.include_router(calendar.router, prefix=settings.api_prefix)
app.include_router(assistant.router, prefix=settings.api_prefix)
app.include_router(journal.router, prefix=settings.api_prefix)


@app.on_event("startup")
async def startup_event() -> None:
    await _init_database()


async def _init_database() -> None:
    # Schema changes are applied by Alembic in the container entrypoint.
    # Running DDL here can block startup indefinitely behind unrelated read locks.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, email, display_name, role, email_verified, created_at, updated_at)
                VALUES (:id, :email, :name, :role, false, now(), now())
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    role = EXCLUDED.role,
                    email_verified = EXCLUDED.email_verified,
                    updated_at = now()
                """
            ),
            {"id": 1, "email": settings.admin_email, "name": "Admin", "role": "admin"},
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
