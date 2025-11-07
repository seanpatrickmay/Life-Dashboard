# Backend App Folder

## Purpose
Contains the FastAPI application code: configuration, database access, service layer, HTTP routers, and supporting utilities.

## File Overview

| Path | Description |
| --- | --- |
| `clients/` | Integrations with external services (e.g., Garmin, Vertex). |
| `core/` | Configuration, logging setup, shared constants. |
| `db/` | SQLAlchemy models, repositories, and session management. |
| `main.py` | FastAPI app factory, middleware registration, router mounting. |
| `routers/` | API route definitions grouped by domain. |
| `schemas/` | Pydantic request/response models. |
| `services/` | Business logic that coordinates repositories and clients. |
| `utils/` | Shared helper utilities. |
| `workers/` | Background tasks and scheduled jobs. |
