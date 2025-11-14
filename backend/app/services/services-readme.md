# Services Folder

## Purpose
Hosts business-logic modules that orchestrate repositories, clients, and other infrastructure to implement application workflows.

## File Overview

| File | Description |
| --- | --- |
| `__init__.py` | Exports service classes. |
| `insight_service.py` | Generates and retrieves readiness insights via Vertex AI. |
| `metrics_service.py` | Ingests Garmin data, aggregates daily metrics. |
| `scheduler.py` | APScheduler setup for recurring ingestion jobs. |
| `nutrition_foods_service.py` | High-level operations for nutrition food definitions. |
| `nutrition_goals_service.py` | Computes personalized nutrient targets, scaling rules, and manual adjustments. |
| `nutrition_goal_engine.py` | Core calculator for calorie, macro, and micronutrient targets. |
| `nutrition_intake_service.py` | Logs intake entries and computes goal progress. |
| `user_profile_service.py` | Manages editable user demographics, measurements, and exposes profile payloads. |
| `claude_nutrition_agent.py` | Placeholder Claude integration for nutrition chat logging. |
