#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

async def main() -> None:
    raw = os.getenv("DATABASE_URL_HOST") or os.getenv("DATABASE_URL")
    if not raw:
        raise RuntimeError("DATABASE_URL or DATABASE_URL_HOST must be set")

    url = raw.replace("+asyncpg", "")
    conn = await asyncpg.connect(url)
    value = await conn.fetchval("SELECT now()")
    await conn.close()
    print("Connected!", value)

if __name__ == "__main__":
    asyncio.run(main())
