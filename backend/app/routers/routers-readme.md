# Routers Folder

## Purpose
Contains FastAPI router modules that expose HTTP endpoints grouped by domain (metrics, insights, admin utilities).

## File Overview

| File | Description |
| --- | --- |
| `__init__.py` | Exports router registration helpers. |
| `assistant.py` | Monet assistant chat endpoint that orchestrates Claude-based tools. |
| `admin.py` | Admin/internal endpoints (e.g., readiness checks). |
| `insights.py` | Insight retrieval API endpoints. |
| `metrics.py` | Metrics retrieval API endpoints. |
| `time.py` | Returns current US-Eastern time & moment for scene sync. |
| `nutrition.py` | Nutrition ingredients, recipes, goals, scaling rules, intake endpoints, and Claude chat stub. |
| `todos.py` | To-do item APIs and Claude-powered creation endpoint. |
| `user.py` | User profile endpoints for demographics and personal settings. |
| `system.py` | Visit-triggered refresh endpoint and status checks. |
