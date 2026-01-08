# Services Folder

## Purpose
Hosts business-logic modules that orchestrate repositories, clients, and other infrastructure to implement application workflows.

## File Overview

| File | Description |
| --- | --- |
| `__init__.py` | Exports service classes. |
| `monet_assistant.py` | Monet chat orchestrator that routes user messages to Claude-backed tools. |
| `monet_context_service.py` | Builds the 14-day per-user context blob consumed by the Monet assistant. |
| `nutrition_units.py` | Helpers for normalizing household food units before logging intake. |
| `insight_service.py` | Generates and retrieves readiness insights via Vertex AI. |
| `metrics_service.py` | Ingests Garmin data, aggregates daily metrics. |
| `nutrition_ingredients_service.py` | High-level operations for nutrition ingredient definitions. |
| `nutrition_recipes_service.py` | CRUD + derived nutrients for recipe compositions. |
| `nutrition_goals_service.py` | Computes personalized nutrient targets, scaling rules, and manual adjustments. |
| `nutrition_goal_engine.py` | Core calculator for calorie, macro, and micronutrient targets. |
| `nutrition_intake_service.py` | Logs intake entries and computes goal progress. |
| `user_profile_service.py` | Manages editable user demographics, measurements, and exposes profile payloads. |
| `claude_nutrition_agent.py` | Placeholder Claude integration for nutrition chat logging. |
| `claude_todo_agent.py` | Claude-style agent that turns natural language into structured to-do items. |
