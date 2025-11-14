# Database Models Folder

## Purpose
Defines the SQLAlchemy ORM base and entity classes representing database tables.

## File Overview

| File | Description |
| --- | --- |
| `__init__.py` | Exports model classes. |
| `base.py` | Declarative base class used by all models. |
| `entities.py` | Core entities (User, Activity, DailyMetric) plus profile, measurement, and daily energy tables. |
| `nutrition.py` | Nutrition-specific ORM models, including nutrient definitions, goals, scaling rules, and intake data. |
