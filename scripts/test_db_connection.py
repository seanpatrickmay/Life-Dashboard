"""Simple DB connection workflow test."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

host_url = os.getenv("DATABASE_URL_HOST")
if host_url:
    os.environ["DATABASE_URL"] = host_url

sys.path.append(str(ROOT / "backend"))

from app.db.session import AsyncSessionLocal  # type: ignore  # noqa: E402


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("select now()"))
        print("Connected!", result.scalar_one())


if __name__ == "__main__":
    asyncio.run(main())
