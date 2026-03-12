"""
Quick Speed Fixes for Life-Dashboard
Run these code changes for immediate performance improvements
"""

# ========================================
# 1. FIX N+1 QUERIES - backend/app/db/repositories/todo_repository.py
# ========================================

# BEFORE (N+1 Problem):
"""
async def list_for_user(self, user_id: int, local_date: date | None = None) -> list[TodoItem]:
    stmt = select(TodoItem).where(TodoItem.user_id == user_id)
    # Missing eager loading causes N+1 queries!
"""

# AFTER (Fixed with eager loading):
from sqlalchemy.orm import selectinload

async def list_for_user(self, user_id: int, local_date: date | None = None) -> list[TodoItem]:
    stmt = (
        select(TodoItem)
        .options(
            selectinload(TodoItem.project),  # Load project in same query
            selectinload(TodoItem.calendar_link),  # Load calendar link
            selectinload(TodoItem.project_suggestion)  # Load suggestions
        )
        .where(TodoItem.user_id == user_id)
    )
    if local_date is not None:
        stmt = stmt.where(
            or_(TodoItem.completed.is_(False), TodoItem.completed_local_date == local_date)
        )
    # Add ordering for index usage
    stmt = stmt.order_by(TodoItem.completed.asc(), TodoItem.created_at.desc())

    result = await self.session.execute(stmt)
    return list(result.scalars().all())

# ========================================
# 2. ADD SIMPLE CACHING - backend/app/routers/metrics.py
# ========================================

# Add at top of file:
from functools import lru_cache
from datetime import datetime, timedelta
import hashlib

# Simple in-memory cache for personal use
_cache = {}
_cache_timestamps = {}
CACHE_TTL = 300  # 5 minutes

def get_cached_or_compute(cache_key: str, compute_func, ttl: int = CACHE_TTL):
    """Simple caching helper"""
    now = datetime.now()

    # Check if cached and not expired
    if cache_key in _cache and cache_key in _cache_timestamps:
        if (now - _cache_timestamps[cache_key]).seconds < ttl:
            return _cache[cache_key]

    # Compute and cache
    result = compute_func()
    _cache[cache_key] = result
    _cache_timestamps[cache_key] = now
    return result

# Update the daily metrics endpoint:
@router.get("/daily")
async def daily_metrics(
    range_days: int = 30,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DailyMetricResponse]:
    # Create cache key
    cache_key = f"metrics:{current_user.id}:{range_days}"

    async def compute():
        cutoff = eastern_today() - timedelta(days=range_days - 1)
        repo = MetricsRepository(session)
        service = MetricsService(session)
        records = await repo.list_metrics_since(current_user.id, cutoff)
        return await service.hydrate_daily_metrics(records, cutoff, current_user.id)

    # Try cache first
    if cache_key in _cache:
        return _cache[cache_key]

    # Compute and cache
    result = await compute()
    _cache[cache_key] = result
    _cache_timestamps[cache_key] = datetime.now()

    return result

# ========================================
# 3. ADD PAGINATION - backend/app/routers/todos.py
# ========================================

from fastapi import Query

@router.get("/", response_model=list[TodoResponse])
async def list_todos(
    local_date: date | None = None,
    # Add pagination parameters
    limit: int = Query(default=50, le=200),  # Max 200 items
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TodoResponse]:
    repo = TodoRepository(session)

    # Modify repository method to support pagination
    stmt = (
        select(TodoItem)
        .options(
            selectinload(TodoItem.project),
            selectinload(TodoItem.calendar_link)
        )
        .where(TodoItem.user_id == current_user.id)
    )

    if local_date is not None:
        stmt = stmt.where(
            or_(TodoItem.completed.is_(False), TodoItem.completed_local_date == local_date)
        )

    # Add pagination
    stmt = stmt.order_by(TodoItem.completed.asc(), TodoItem.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)

    result = await session.execute(stmt)
    items = list(result.scalars().all())

    now_utc = datetime.now(UTC)
    return [_todo_response(item, now_utc) for item in items]

# ========================================
# 4. OPTIMIZE INSIGHT GENERATION - backend/app/services/insight_service.py
# ========================================

# Add caching to expensive AI calls:
class InsightService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._insight_cache = {}
        self._cache_ttl = timedelta(hours=6)  # Cache for 6 hours

    async def get_or_generate_insight(self, user_id: int, local_date: date) -> Insight:
        cache_key = f"{user_id}:{local_date}"

        # Check cache first
        if cache_key in self._insight_cache:
            cached_insight, cached_time = self._insight_cache[cache_key]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_insight

        # Check database
        repo = InsightRepository(self.session)
        existing = await repo.get_by_date(user_id, local_date)

        if existing and not self._should_regenerate(existing):
            # Cache and return
            self._insight_cache[cache_key] = (existing, datetime.now())
            return existing

        # Generate new insight (expensive operation)
        new_insight = await self._generate_insight(user_id, local_date)

        # Cache it
        self._insight_cache[cache_key] = (new_insight, datetime.now())
        return new_insight

# ========================================
# 5. FRONTEND BUNDLE OPTIMIZATION - frontend/vite.config.ts
# ========================================

# Update vite.config.ts:
"""
import { defineConfig, splitVendorChunkPlugin } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    react(),
    splitVendorChunkPlugin()  // Split vendor chunks
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Split large dependencies into separate chunks
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['styled-components', 'framer-motion'],
          'chart-vendor': ['recharts'],
          'utils': ['date-fns', 'axios']
        }
      }
    },
    // Increase chunk size warning limit for personal app
    chunkSizeWarningLimit: 1000
  }
})
"""

# ========================================
# 6. QUICK DATABASE CONNECTION POOL FIX - backend/app/db/session.py
# ========================================

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import QueuePool

# Optimized for single user (smaller pool)
engine = create_async_engine(
    settings.database_url,
    echo=False,  # Turn off SQL logging for speed
    pool_size=5,  # Smaller pool for single user
    max_overflow=5,  # Less overflow needed
    pool_pre_ping=True,  # Keep connections alive
    pool_recycle=3600,  # Recycle after 1 hour

    # PostgreSQL optimizations
    connect_args={
        "server_settings": {
            "jit": "off",  # Disable JIT for faster short queries
        },
        "command_timeout": 60,
    }
)

# ========================================
# 7. MONITORING: Add simple timing decorator
# ========================================

import time
import logging

logger = logging.getLogger(__name__)

def timeit(func):
    """Simple timing decorator to find slow functions"""
    async def wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        duration = (time.time() - start) * 1000  # Convert to ms

        if duration > 100:  # Log if slower than 100ms
            logger.warning(f"{func.__name__} took {duration:.2f}ms")

        return result
    return wrapper

# Use it on suspicious endpoints:
@router.get("/daily")
@timeit  # Add this to measure
async def daily_metrics(...):
    pass