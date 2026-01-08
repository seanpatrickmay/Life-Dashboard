# Database Repositories Folder

## Purpose
Implements data-access helpers that encapsulate SQLAlchemy queries and mutations for the persistence layer.

## File Overview

| File | Description |
| --- | --- |
| `__init__.py` | Exports repository classes. |
| `activity_repository.py` | CRUD helpers for user activities. |
| `metrics_repository.py` | CRUD helpers for daily metrics and insight linkage. |
| `nutrition_ingredients_repository.py` | Nutrition ingredient/profile + recipe persistence helpers. |
| `nutrition_goals_repository.py` | Accessor for nutrient definitions, goal snapshots, and scaling rule assignments. |
| `nutrition_intake_repository.py` | Logging and querying of nutrition intake entries. |
| `todo_repository.py` | CRUD helpers for per-user to-do items with deadline-aware ordering. |
