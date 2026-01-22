# Clients Folder

## Purpose
Wrappers for external services used by the backend (e.g., Garmin Connect, Vertex AI). These clients encapsulate authentication and API calls so services can depend on a consistent interface.

## File Overview

| File | Description |
| --- | --- |
| `__init__.py` | Exports available clients. |
| `garmin_client.py` | Handles Garmin Connect authentication, activity/metric retrieval. |
| `google_calendar_client.py` | Async wrapper for Google Calendar list/create/update APIs. |
| `vertex_client.py` | Handles Vertex AI generative model initialization and text generation. |
