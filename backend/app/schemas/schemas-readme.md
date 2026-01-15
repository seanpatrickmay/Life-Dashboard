# Schemas Folder

## Purpose
Defines Pydantic models used for request validation and response serialization across the API.

## File Overview

| File | Description |
| --- | --- |
| `__init__.py` | Exports schema modules. |
| `assistant.py` | Request/response payloads for the Monet assistant chat endpoint. |
| `admin.py` | Schemas for admin endpoints (health/readiness). |
| `auth.py` | Schemas for Google OAuth session responses. |
| `garmin.py` | Schemas for Garmin connection requests and status responses. |
| `insights.py` | Schemas for insight responses. |
| `journal.py` | Schemas for journal entry input, day summaries, and week statuses. |
| `metrics.py` | Schemas for metrics overview/daily responses. |
| `nutrition.py` | Schemas for nutrition foods, goals, intake summaries, and Claude chat. |
| `todos.py` | Schemas for per-user to-do items and Claude-powered creation. |
| `system.py` | Status payloads for background refresh triggers. |
