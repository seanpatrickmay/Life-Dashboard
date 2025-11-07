# Scripts

Utilities for bootstrapping databases, debugging Garmin ingestion, and generating Monet assets.

## File Overview

| Script | Description |
| --- | --- |
| `bootstrap_db.py` | Creates baseline tables/sample rows for a fresh database. |
| `debug_metrics.py` | Dumps recent metric records for inspection. |
| `debug_output/` | Scratch directory for logs/artifacts produced by the debug scripts. |
| `generate_pixel_assets.py` | Deterministically renders the Monet pixel sprites in `frontend/src/assets/pixels/`. |
| `manual_ingest.py` | CLI runner that triggers the Garmin ingest workflow on demand. |
| `sanity_db.py` | Lightweight database sanity check (confirms connectivity + expected tables). |
| `test_db_connection.py` / `test_db_roundtrip.py` | Connectivity and roundtrip CRUD tests for the DB. |
| `test_garmin_connection.py` | Verifies Garmin API credentials and fetch capability. |
