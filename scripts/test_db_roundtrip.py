#!/usr/bin/env python3
"""Round-trip DB sanity test."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

host_db_url = os.getenv("DATABASE_URL_HOST")
if host_db_url:
    os.environ["DATABASE_URL"] = host_db_url

sys.path.append(str(ROOT / "backend"))

from app.db.session import AsyncSessionLocal  # type: ignore  # noqa: E402
from app.db.models.entities import IngestionRun  # type: ignore  # noqa: E402
from app.utils.timezone import eastern_now  # type: ignore  # noqa: E402


async def main() -> None:
    async with AsyncSessionLocal() as session:
        test_run = IngestionRun(
            started_at=eastern_now(),
            completed_at=None,
            status="test_roundtrip",
            message="Temporary record to verify store + fetch workflow.",
            activities_ingested=7,
        )

        async with session.begin():
            session.add(test_run)
            await session.flush()
            inserted_id = test_run.id
            print(f"Inserted IngestionRun id={inserted_id}")

        fetched = await session.get(IngestionRun, inserted_id)
        if fetched is None:
            raise RuntimeError("Failed to fetch the test record back from the database.")

        print(
            "Fetched record:",
            {
                "id": fetched.id,
                "status": fetched.status,
                "started_at": fetched.started_at.isoformat(),
                "activities_ingested": fetched.activities_ingested,
            },
        )

        await session.delete(fetched)
        await session.commit()
        print("Cleaned up the test record.")


if __name__ == "__main__":
    asyncio.run(main())
