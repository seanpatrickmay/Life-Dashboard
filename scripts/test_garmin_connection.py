from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

sys.path.append(str(ROOT / "backend"))

from app.clients.garmin_client import GarminClient  # type: ignore  # noqa: E402

def main() -> None:
    client = GarminClient()
    client.authenticate()
    profile = client.client.get_user_profile()
    print(json.dumps(profile, indent=2))


if __name__ == "__main__":
    main()
