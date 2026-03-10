# Clients Folder

## Purpose
Wrappers for external services used by the backend (e.g., Garmin Connect, OpenAI). These clients encapsulate authentication and API calls so services can depend on a consistent interface.

## File Overview

| File | Description |
| --- | --- |
| `__init__.py` | Exports available clients. |
| `garmin_client.py` | Handles Garmin Connect authentication, activity/metric retrieval. |
| `google_calendar_client.py` | Async wrapper for Google Calendar list/create/update APIs. |
| `openai_client.py` | Handles OpenAI Responses API initialization plus text, structured-output, and web-search calls. |
