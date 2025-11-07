# Database Folder

## Purpose
Provides the persistence layer: SQLAlchemy models, repositories, and session/engine management for the application.

## File Overview

| Path | Description |
| --- | --- |
| `__init__.py` | Package marker. |
| `models/` | SQLAlchemy model base classes and entity definitions. |
| `repositories/` | Data access helpers for reading/writing metrics and activities. |
| `session.py` | Creates the async SQLAlchemy engine and session factory. |
