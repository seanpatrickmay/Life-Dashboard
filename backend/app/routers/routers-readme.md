# Routers Folder

## Purpose
Contains FastAPI router modules that expose HTTP endpoints grouped by domain (metrics, insights, admin utilities).

## File Overview

| File | Description |
| --- | --- |
| `__init__.py` | Exports router registration helpers. |
| `admin.py` | Admin/internal endpoints (e.g., readiness checks). |
| `insights.py` | Insight retrieval API endpoints. |
| `metrics.py` | Metrics retrieval API endpoints. |
