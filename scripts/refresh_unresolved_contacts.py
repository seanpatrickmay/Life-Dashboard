"""Re-resolve iMessage contacts that still show as raw phone numbers.

Usage:
    cd backend && python -m scripts.refresh_unresolved_contacts

Or from repo root:
    python scripts/refresh_unresolved_contacts.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the backend package is importable when run from repo root.
backend_root = Path(__file__).resolve().parent.parent / "backend"
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


async def main(user_id: int = 1) -> None:
    from app.db.session import AsyncSessionLocal
    from app.services.imessage_contact_service import IMessageContactResolver

    async with AsyncSessionLocal() as session:
        resolver = IMessageContactResolver(session)
        count = await resolver.refresh_unresolved_contacts(user_id=user_id)
        await session.commit()

    print(f"Resolved {count} previously-unresolved contact(s).")


if __name__ == "__main__":
    uid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(main(user_id=uid))
