from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.models import Base
from app.db.session import engine
from app.routers import admin, assistant, insights, metrics, nutrition, system, time, user, todos

configure_logging(settings.debug)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics.router, prefix=settings.api_prefix)
app.include_router(insights.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(time.router, prefix=settings.api_prefix)
app.include_router(nutrition.router, prefix=settings.api_prefix)
app.include_router(user.router, prefix=settings.api_prefix)
app.include_router(system.router, prefix=settings.api_prefix)
app.include_router(todos.router, prefix=settings.api_prefix)
app.include_router(assistant.router, prefix=settings.api_prefix)


@app.on_event("startup")
async def startup_event() -> None:
    await _init_database()


async def _init_database() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                """
                INSERT INTO "user" (id, email, display_name, created_at, updated_at)
                VALUES (:id, :email, :name, now(), now())
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    updated_at = now()
                """
            ),
            {"id": 1, "email": "seed@example.com", "name": "Seed User"},
        )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
