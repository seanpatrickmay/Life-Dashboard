# Performance Optimization Implementation Guide

## Phase 2: Backend Performance & Database Optimization (Week 2-3)

### 1. Database Index Implementation

#### Immediate Index Creation Script
```sql
-- Run these indexes IMMEDIATELY for instant performance gains
-- Each index targets critical query patterns identified in the audit

-- 1. Todo queries optimization
CREATE INDEX CONCURRENTLY idx_todo_user_completed_deadline
ON todo_item (user_id, completed, deadline_utc)
WHERE deadline_utc IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_todo_user_status_project
ON todo_item (user_id, completed, project_id)
WHERE project_id IS NOT NULL;

-- 2. iMessage processing optimization
CREATE INDEX CONCURRENTLY idx_imessage_conversation_user_last_message
ON imessage_conversation (user_id, last_message_at_utc DESC);

CREATE INDEX CONCURRENTLY idx_imessage_message_conversation_sent_at
ON imessage_message (conversation_id, sent_at_utc DESC);

CREATE INDEX CONCURRENTLY idx_imessage_processing_run_user_created
ON imessage_processing_run (user_id, created_at DESC);

-- 3. Metrics queries optimization
CREATE INDEX CONCURRENTLY idx_daily_metric_user_date
ON dailymetric (user_id, metric_date DESC);

CREATE INDEX CONCURRENTLY idx_training_status_user_day
ON trainingstatus (user_id, day DESC);

CREATE INDEX CONCURRENTLY idx_insight_user_local_date
ON insight (user_id, local_date DESC);

-- 4. Calendar optimization
CREATE INDEX CONCURRENTLY idx_calendar_event_user_start_time
ON calendar_event (user_id, start_time_utc DESC)
WHERE deleted IS FALSE;

-- 5. Workspace queries
CREATE INDEX CONCURRENTLY idx_workspace_page_user_kind
ON workspace_page (user_id, kind, created_at DESC);

CREATE INDEX CONCURRENTLY idx_project_note_user_project
ON project_note (user_id, project_id, created_at DESC);

-- 6. Audit and security
CREATE INDEX CONCURRENTLY idx_audit_user_timestamp
ON audit_logs (user_id, timestamp DESC);

CREATE INDEX CONCURRENTLY idx_audit_action_timestamp
ON audit_logs (action, timestamp DESC);
```

#### Monitor Index Usage
```sql
-- Script to monitor index usage and identify missing indexes
CREATE OR REPLACE VIEW index_usage_stats AS
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    CASE
        WHEN idx_scan = 0 THEN 'UNUSED'
        WHEN idx_scan < 100 THEN 'RARELY USED'
        WHEN idx_scan < 1000 THEN 'MODERATELY USED'
        ELSE 'HEAVILY USED'
    END AS usage_category
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Find missing indexes based on sequential scans
CREATE OR REPLACE VIEW missing_indexes AS
SELECT
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    seq_scan::float / NULLIF(idx_scan + seq_scan, 0) * 100 AS seq_scan_percentage,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS table_size
FROM pg_stat_user_tables
WHERE seq_scan > 1000
    AND seq_scan > idx_scan * 2
ORDER BY seq_scan DESC;
```

### 2. Service Decomposition - Breaking Down the Monolith

#### Step 1: Extract IMessage Clustering Service
```python
# backend/app/services/imessage/clustering_service.py
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN

@dataclass
class MessageCluster:
    id: str
    messages: List[dict]
    start_time: datetime
    end_time: datetime
    participants: List[str]
    summary: Optional[str] = None
    confidence_score: float = 0.0

class IMessageClusteringService:
    """Focused service for message clustering"""

    MAX_CLUSTER_GAP = timedelta(hours=6)
    MIN_CLUSTER_SIZE = 2

    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=100, stop_words='english')

    async def cluster_messages(
        self,
        messages: List[dict],
        time_threshold: Optional[timedelta] = None
    ) -> List[MessageCluster]:
        """Cluster messages by time and content similarity"""

        if not messages:
            return []

        time_threshold = time_threshold or self.MAX_CLUSTER_GAP

        # Sort messages by time
        sorted_messages = sorted(messages, key=lambda m: m['sent_at_utc'])

        # Time-based clustering first
        time_clusters = self._cluster_by_time(sorted_messages, time_threshold)

        # Content-based refinement for each time cluster
        refined_clusters = []
        for cluster in time_clusters:
            if len(cluster) > 10:  # Only refine large clusters
                subclusters = self._cluster_by_content(cluster)
                refined_clusters.extend(subclusters)
            else:
                refined_clusters.append(cluster)

        # Convert to MessageCluster objects
        return [self._create_cluster_object(msgs, idx)
                for idx, msgs in enumerate(refined_clusters)]

    def _cluster_by_time(
        self,
        messages: List[dict],
        threshold: timedelta
    ) -> List[List[dict]]:
        """Cluster messages based on time gaps"""

        clusters = []
        current_cluster = [messages[0]]

        for msg in messages[1:]:
            time_gap = msg['sent_at_utc'] - current_cluster[-1]['sent_at_utc']

            if time_gap <= threshold:
                current_cluster.append(msg)
            else:
                if len(current_cluster) >= self.MIN_CLUSTER_SIZE:
                    clusters.append(current_cluster)
                current_cluster = [msg]

        # Add last cluster
        if len(current_cluster) >= self.MIN_CLUSTER_SIZE:
            clusters.append(current_cluster)

        return clusters

    def _cluster_by_content(
        self,
        messages: List[dict],
        eps: float = 0.5
    ) -> List[List[dict]]:
        """Refine clustering using content similarity"""

        texts = [msg.get('text', '') for msg in messages]

        if not any(texts):
            return [messages]

        # Vectorize messages
        try:
            X = self.vectorizer.fit_transform(texts)

            # Use DBSCAN for clustering
            clustering = DBSCAN(eps=eps, min_samples=2, metric='cosine')
            labels = clustering.fit_predict(X)

            # Group messages by cluster
            clusters = {}
            for idx, label in enumerate(labels):
                if label == -1:  # Noise points
                    continue
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(messages[idx])

            return list(clusters.values()) if clusters else [messages]

        except Exception as e:
            # Fallback to original cluster if content analysis fails
            return [messages]

    def _create_cluster_object(
        self,
        messages: List[dict],
        cluster_id: int
    ) -> MessageCluster:
        """Convert message list to MessageCluster object"""

        participants = list(set(
            msg.get('sender_name', 'Unknown')
            for msg in messages
        ))

        return MessageCluster(
            id=f"cluster_{cluster_id}",
            messages=messages,
            start_time=messages[0]['sent_at_utc'],
            end_time=messages[-1]['sent_at_utc'],
            participants=participants,
            confidence_score=self._calculate_confidence(messages)
        )

    def _calculate_confidence(self, messages: List[dict]) -> float:
        """Calculate clustering confidence score"""

        if len(messages) < 2:
            return 0.0

        # Factors: message count, time consistency, participant consistency
        score = min(1.0, len(messages) / 10)  # More messages = higher confidence

        # Time consistency
        time_gaps = []
        for i in range(1, len(messages)):
            gap = (messages[i]['sent_at_utc'] - messages[i-1]['sent_at_utc']).total_seconds()
            time_gaps.append(gap)

        if time_gaps:
            avg_gap = np.mean(time_gaps)
            std_gap = np.std(time_gaps)
            time_consistency = 1.0 - min(1.0, std_gap / (avg_gap + 1))
            score = (score + time_consistency) / 2

        return round(score, 2)
```

#### Step 2: Extract Action Extraction Service
```python
# backend/app/services/imessage/action_extractor.py
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import asyncio
import json
from openai import AsyncOpenAI

@dataclass
class ExtractedAction:
    type: str  # 'todo', 'event', 'reminder', 'note'
    title: str
    description: Optional[str]
    deadline: Optional[datetime]
    priority: Optional[str]
    confidence: float
    source_messages: List[str]
    metadata: Dict[str, Any]

class IMessageActionExtractor:
    """Focused service for extracting actions from message clusters"""

    def __init__(self, openai_client: AsyncOpenAI):
        self.client = openai_client
        self.batch_size = 5  # Process clusters in batches

    async def extract_actions_batch(
        self,
        clusters: List[MessageCluster]
    ) -> List[ExtractedAction]:
        """Extract actions from multiple clusters efficiently"""

        # Process in batches for better performance
        all_actions = []

        for i in range(0, len(clusters), self.batch_size):
            batch = clusters[i:i + self.batch_size]

            # Parallel extraction for batch
            tasks = [self._extract_from_cluster(cluster) for cluster in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and flatten results
            for result in batch_results:
                if isinstance(result, list):
                    all_actions.extend(result)

        return all_actions

    async def _extract_from_cluster(
        self,
        cluster: MessageCluster
    ) -> List[ExtractedAction]:
        """Extract actions from a single cluster"""

        # Prepare context from messages
        context = self._prepare_context(cluster)

        # Generate prompt
        prompt = self._create_extraction_prompt(context)

        try:
            # Call LLM with structured output
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=1000
            )

            # Parse response
            content = response.choices[0].message.content
            data = json.loads(content)

            # Convert to ExtractedAction objects
            return [self._parse_action(action_data, cluster)
                    for action_data in data.get('actions', [])]

        except Exception as e:
            print(f"Error extracting actions from cluster: {e}")
            return []

    def _prepare_context(self, cluster: MessageCluster) -> str:
        """Prepare message context for LLM"""

        # Limit to most relevant messages
        messages = cluster.messages[:20]  # Cap at 20 messages

        context_lines = []
        for msg in messages:
            sender = msg.get('sender_name', 'Unknown')
            text = msg.get('text', '')
            time = msg.get('sent_at_utc').strftime('%I:%M %p')
            context_lines.append(f"[{time}] {sender}: {text}")

        return "\n".join(context_lines)

    def _create_extraction_prompt(self, context: str) -> str:
        """Create prompt for action extraction"""

        return f"""
        Analyze this conversation and extract any actionable items:

        {context}

        Extract:
        1. Todos/tasks mentioned
        2. Events or appointments
        3. Reminders
        4. Important notes

        For each action, provide:
        - type: todo/event/reminder/note
        - title: brief description
        - description: detailed context if available
        - deadline: if mentioned (ISO format)
        - priority: high/medium/low
        - confidence: 0.0-1.0

        Return as JSON with 'actions' array.
        """

    SYSTEM_PROMPT = """
    You are an AI assistant that extracts actionable items from conversations.
    Be conservative - only extract clear, actionable items.
    Return valid JSON always.
    """

    def _parse_action(
        self,
        action_data: dict,
        cluster: MessageCluster
    ) -> ExtractedAction:
        """Parse action data into ExtractedAction object"""

        return ExtractedAction(
            type=action_data.get('type', 'note'),
            title=action_data.get('title', ''),
            description=action_data.get('description'),
            deadline=self._parse_deadline(action_data.get('deadline')),
            priority=action_data.get('priority', 'medium'),
            confidence=float(action_data.get('confidence', 0.5)),
            source_messages=[msg['id'] for msg in cluster.messages[:5]],
            metadata={
                'cluster_id': cluster.id,
                'participants': cluster.participants,
                'extracted_at': datetime.now(UTC).isoformat()
            }
        )

    def _parse_deadline(self, deadline_str: Optional[str]) -> Optional[datetime]:
        """Parse deadline string to datetime"""

        if not deadline_str:
            return None

        try:
            return datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
        except:
            return None
```

#### Step 3: Create Orchestrator Service
```python
# backend/app/services/imessage/processing_orchestrator.py
from typing import List, Optional
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.imessage.clustering_service import IMessageClusteringService
from app.services.imessage.action_extractor import IMessageActionExtractor
from app.services.imessage.todo_matcher import IMessageTodoMatcher
from app.db.repositories.imessage_repository import IMessageRepository
from app.db.repositories.todo_repository import TodoRepository

class IMessageProcessingOrchestrator:
    """Orchestrates the iMessage processing pipeline"""

    def __init__(
        self,
        session: AsyncSession,
        clustering_service: IMessageClusteringService,
        action_extractor: IMessageActionExtractor,
        todo_matcher: IMessageTodoMatcher
    ):
        self.session = session
        self.clustering = clustering_service
        self.extractor = action_extractor
        self.matcher = todo_matcher
        self.imessage_repo = IMessageRepository(session)
        self.todo_repo = TodoRepository(session)

    async def process_pending_messages(
        self,
        user_id: int,
        batch_size: int = 100
    ) -> dict:
        """Orchestrate the full processing pipeline"""

        processing_stats = {
            'messages_processed': 0,
            'clusters_created': 0,
            'actions_extracted': 0,
            'todos_created': 0,
            'errors': []
        }

        try:
            # Step 1: Load pending messages in batches
            offset = 0
            all_clusters = []
            all_actions = []

            while True:
                messages = await self.imessage_repo.get_unprocessed_messages(
                    user_id=user_id,
                    limit=batch_size,
                    offset=offset
                )

                if not messages:
                    break

                processing_stats['messages_processed'] += len(messages)

                # Step 2: Cluster messages
                clusters = await self.clustering.cluster_messages(messages)
                all_clusters.extend(clusters)
                processing_stats['clusters_created'] += len(clusters)

                # Mark messages as processing
                message_ids = [msg['id'] for msg in messages]
                await self.imessage_repo.mark_as_processing(message_ids)

                offset += batch_size

                # Yield control to prevent blocking
                await asyncio.sleep(0.01)

            # Step 3: Extract actions from all clusters (batched)
            if all_clusters:
                actions = await self.extractor.extract_actions_batch(all_clusters)
                all_actions.extend(actions)
                processing_stats['actions_extracted'] = len(actions)

            # Step 4: Match and create todos
            if all_actions:
                todos = await self._process_actions(user_id, all_actions)
                processing_stats['todos_created'] = len(todos)

            # Step 5: Mark messages as processed
            await self.imessage_repo.mark_all_as_processed(user_id)

            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            processing_stats['errors'].append(str(e))
            raise

        return processing_stats

    async def _process_actions(
        self,
        user_id: int,
        actions: List[ExtractedAction]
    ) -> List[dict]:
        """Process extracted actions into todos"""

        created_todos = []

        # Get existing todos for matching
        existing_todos = await self.todo_repo.list_for_user(user_id)

        for action in actions:
            if action.type != 'todo':
                continue

            # Check if similar todo exists
            if not await self.matcher.is_duplicate(action, existing_todos):
                todo_data = {
                    'user_id': user_id,
                    'title': action.title,
                    'description': action.description,
                    'deadline_utc': action.deadline,
                    'priority': action.priority,
                    'source': 'imessage',
                    'metadata': action.metadata
                }

                todo = await self.todo_repo.create(**todo_data)
                created_todos.append(todo)
                existing_todos.append(todo)  # Add to list for duplicate detection

        return created_todos
```

### 3. Implement Caching Layer

#### Redis Cache Configuration
```python
# backend/app/core/cache.py
import redis.asyncio as redis
import json
import hashlib
from typing import Optional, Any, Callable
from functools import wraps
from datetime import timedelta

class CacheManager:
    """Centralized cache management with Redis"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.default_ttl = timedelta(minutes=5)

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        value = await self.redis.get(key)
        if value:
            return json.loads(value)
        return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[timedelta] = None
    ) -> None:
        """Set value in cache with TTL"""
        ttl = ttl or self.default_ttl
        await self.redis.setex(
            key,
            int(ttl.total_seconds()),
            json.dumps(value, default=str)
        )

    async def delete(self, key: str) -> None:
        """Delete key from cache"""
        await self.redis.delete(key)

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching pattern"""
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor=cursor,
                match=pattern,
                count=100
            )
            if keys:
                await self.redis.delete(*keys)
            if cursor == 0:
                break

    def cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate consistent cache key"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

# Cache decorator
def cached(
    ttl: timedelta = timedelta(minutes=5),
    key_prefix: Optional[str] = None
):
    """Decorator for caching function results"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache = kwargs.pop('_cache', None)
            if not cache:
                return await func(*args, **kwargs)

            prefix = key_prefix or f"{func.__module__}.{func.__name__}"
            key = cache.cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl)

            return result

        return wrapper
    return decorator
```

#### Apply Caching to Heavy Operations
```python
# backend/app/services/metrics_service.py
from app.core.cache import CacheManager, cached
from datetime import timedelta

class MetricsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cache = CacheManager()

    @cached(ttl=timedelta(minutes=15), key_prefix="metrics_overview")
    async def get_metrics_overview(
        self,
        user_id: int,
        range_days: int = 30,
        _cache: Optional[CacheManager] = None
    ) -> dict:
        """Get cached metrics overview"""

        # This expensive computation is now cached
        cutoff = eastern_today() - timedelta(days=range_days - 1)

        metrics = await self._fetch_metrics(user_id, cutoff)
        trends = await self._calculate_trends(metrics)
        insights = await self._generate_insights(metrics, trends)

        return {
            'metrics': metrics,
            'trends': trends,
            'insights': insights,
            'generated_at': datetime.now(UTC)
        }

    async def invalidate_user_cache(self, user_id: int):
        """Invalidate all cache entries for a user"""
        await self.cache.invalidate_pattern(f"*user:{user_id}*")

    @cached(ttl=timedelta(hours=1), key_prefix="training_load")
    async def get_training_load_analysis(
        self,
        user_id: int,
        _cache: Optional[CacheManager] = None
    ) -> dict:
        """Get cached training load analysis"""

        # Complex calculation cached for 1 hour
        recent_activities = await self._fetch_activities(user_id, days=14)
        load_metrics = self._calculate_training_load(recent_activities)
        recovery_status = self._assess_recovery(load_metrics)

        return {
            'current_load': load_metrics['current'],
            'optimal_range': load_metrics['optimal_range'],
            'recovery_status': recovery_status,
            'recommendations': self._generate_recommendations(load_metrics)
        }
```

### 4. Connection Pool Optimization

```python
# backend/app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Optimized engine configuration
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug and settings.log_sql,
    future=True,

    # Connection pool settings - CRITICAL for performance
    poolclass=QueuePool,
    pool_size=20,  # Number of persistent connections
    max_overflow=30,  # Additional connections under load
    pool_timeout=30,  # Timeout waiting for connection
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_pre_ping=True,  # Test connections before using

    # Query optimization
    query_cache_size=1200,  # Cache compiled SQL statements

    # PostgreSQL specific optimizations
    connect_args={
        "server_settings": {
            "application_name": "life_dashboard",
            "jit": "off",  # Disable JIT for short queries
            "shared_preload_libraries": "pg_stat_statements",
        },
        "command_timeout": 60,
        "prepared_statement_cache_size": 0,  # Disable if using PgBouncer
        "prepared_statement_name_func": lambda: f"stmt_{uuid.uuid4().hex[:8]}"
    }
)

# Session factory with optimized settings
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
    autoflush=False,  # Control flushing manually
    autocommit=False
)

# Connection pool monitoring
async def get_pool_status():
    """Get current connection pool status"""
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total": pool.total()
    }

# Health check endpoint
async def check_database_health():
    """Verify database connectivity and pool health"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            pool_status = await get_pool_status()

            return {
                "status": "healthy",
                "pool": pool_status,
                "response_time_ms": result.execution_options.get('execution_time_ms')
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}
```

### 5. API Response Optimization

#### Implement Pagination
```python
# backend/app/schemas/pagination.py
from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel, Field

T = TypeVar('T')

class PaginationParams(BaseModel):
    page: int = Field(default=0, ge=0)
    page_size: int = Field(default=50, ge=1, le=100)
    sort_by: Optional[str] = None
    sort_order: str = Field(default="desc", regex="^(asc|desc)$")

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        page_size: int
    ) -> "PaginatedResponse[T]":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size
        )
```

#### Apply to Routes
```python
# backend/app/routers/metrics.py
from app.schemas.pagination import PaginationParams, PaginatedResponse

@router.get("/daily", response_model=PaginatedResponse[DailyMetricResponse])
async def daily_metrics(
    range_days: int = Query(default=30, le=90),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    cache: CacheManager = Depends(get_cache)
) -> PaginatedResponse[DailyMetricResponse]:
    """Get paginated daily metrics with caching"""

    # Generate cache key including pagination
    cache_key = cache.cache_key(
        "daily_metrics",
        user_id=current_user.id,
        range_days=range_days,
        page=pagination.page,
        page_size=pagination.page_size
    )

    # Try cache first
    cached_result = await cache.get(cache_key)
    if cached_result:
        return PaginatedResponse[DailyMetricResponse](**cached_result)

    # Fetch from database with pagination
    cutoff = eastern_today() - timedelta(days=range_days - 1)
    repo = MetricsRepository(session)

    # Get total count
    total = await repo.count_metrics_since(current_user.id, cutoff)

    # Get paginated data
    records = await repo.list_metrics_since_paginated(
        current_user.id,
        cutoff,
        offset=pagination.page * pagination.page_size,
        limit=pagination.page_size,
        sort_by=pagination.sort_by or "metric_date",
        sort_order=pagination.sort_order
    )

    # Convert to response models
    items = [DailyMetricResponse.from_orm(record) for record in records]

    response = PaginatedResponse.create(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )

    # Cache for 5 minutes
    await cache.set(cache_key, response.dict(), ttl=timedelta(minutes=5))

    return response
```

### 6. Background Job Optimization

```python
# backend/app/services/background_jobs.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import logging

logger = logging.getLogger(__name__)

class BackgroundJobManager:
    """Optimized background job management"""

    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        # Configure job stores
        jobstores = {
            'default': RedisJobStore(
                host='localhost',
                port=6379,
                db=1,
                job_pickle_protocol=4
            )
        }

        # Configure executors with connection pooling
        executors = {
            'default': AsyncIOExecutor(),
            'high_priority': AsyncIOExecutor(),
        }

        # Job defaults
        job_defaults = {
            'coalesce': True,  # Coalesce missed jobs
            'max_instances': 1,  # Prevent duplicate runs
            'misfire_grace_time': 300  # 5 minute grace period
        }

        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='America/New_York'
        )

        # Add event listeners
        self.scheduler.add_listener(
            self._job_executed,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._job_error,
            EVENT_JOB_ERROR
        )

    async def start(self):
        """Start the scheduler"""
        self.scheduler.start()
        await self._schedule_recurring_jobs()

    async def _schedule_recurring_jobs(self):
        """Schedule all recurring jobs"""

        # Data ingestion jobs
        self.scheduler.add_job(
            self._ingest_all_user_data,
            'cron',
            hour=5,
            minute=0,
            id='daily_ingestion',
            replace_existing=True
        )

        # Cache warming
        self.scheduler.add_job(
            self._warm_cache,
            'interval',
            hours=1,
            id='cache_warming',
            replace_existing=True
        )

        # Database maintenance
        self.scheduler.add_job(
            self._database_maintenance,
            'cron',
            hour=3,
            minute=0,
            day_of_week='sun',
            id='weekly_maintenance',
            replace_existing=True
        )

    async def _ingest_all_user_data(self):
        """Ingest data for all active users"""

        async with AsyncSessionLocal() as session:
            # Get active users
            users = await session.execute(
                select(User).where(
                    User.is_active == True,
                    User.last_active > datetime.now() - timedelta(days=7)
                )
            )

            # Process in batches
            batch_size = 10
            user_list = users.scalars().all()

            for i in range(0, len(user_list), batch_size):
                batch = user_list[i:i + batch_size]

                # Schedule parallel ingestion
                tasks = [
                    self._ingest_user_data(user.id)
                    for user in batch
                ]

                await asyncio.gather(*tasks, return_exceptions=True)

    async def _warm_cache(self):
        """Pre-warm cache with frequently accessed data"""

        cache = CacheManager()

        async with AsyncSessionLocal() as session:
            # Get recently active users
            recent_users = await session.execute(
                select(User.id).where(
                    User.last_active > datetime.now() - timedelta(hours=24)
                ).limit(100)
            )

            for user_id in recent_users.scalars():
                # Pre-cache dashboard data
                metrics_service = MetricsService(session)
                await metrics_service.get_metrics_overview(
                    user_id,
                    range_days=7,
                    _cache=cache
                )

    async def _database_maintenance(self):
        """Perform database maintenance tasks"""

        async with AsyncSessionLocal() as session:
            # Update statistics
            await session.execute(text("ANALYZE;"))

            # Clean old audit logs
            cutoff = datetime.now() - timedelta(days=90)
            await session.execute(
                delete(AuditLog).where(AuditLog.timestamp < cutoff)
            )

            # Vacuum analyze specific tables
            await session.execute(text("VACUUM ANALYZE dailymetric;"))
            await session.execute(text("VACUUM ANALYZE todo_item;"))

            await session.commit()

    def _job_executed(self, event):
        """Log successful job execution"""
        logger.info(
            f"Job {event.job_id} executed successfully. "
            f"Runtime: {event.retval:.2f}s"
        )

    def _job_error(self, event):
        """Log job errors"""
        logger.error(
            f"Job {event.job_id} failed: {event.exception}",
            exc_info=event.exception
        )
```

## Performance Monitoring Dashboard

```python
# backend/app/services/performance_monitor.py
import time
import psutil
import asyncio
from typing import Dict, List
from contextlib import asynccontextmanager
from sqlalchemy import text

class PerformanceMonitor:
    """Real-time performance monitoring"""

    def __init__(self):
        self.metrics = []
        self.slow_queries = []

    @asynccontextmanager
    async def track_request(self, endpoint: str):
        """Track API request performance"""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        try:
            yield
        finally:
            duration = (time.time() - start_time) * 1000  # ms
            memory_used = (psutil.Process().memory_info().rss / 1024 / 1024) - start_memory

            self.metrics.append({
                'endpoint': endpoint,
                'duration_ms': duration,
                'memory_mb': memory_used,
                'timestamp': time.time()
            })

            # Alert on slow requests
            if duration > 1000:  # > 1 second
                logger.warning(f"Slow request: {endpoint} took {duration:.2f}ms")

    async def get_database_performance(self, session: AsyncSession) -> Dict:
        """Get database performance metrics"""

        # Query cache hit rate
        cache_stats = await session.execute(
            text("""
                SELECT
                    sum(heap_blks_hit)::float /
                    NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100 AS cache_hit_rate
                FROM pg_statio_user_tables;
            """)
        )

        # Active connections
        connections = await session.execute(
            text("""
                SELECT
                    state,
                    COUNT(*) as count
                FROM pg_stat_activity
                GROUP BY state;
            """)
        )

        # Slow queries
        slow_queries = await session.execute(
            text("""
                SELECT
                    query,
                    mean_exec_time,
                    calls
                FROM pg_stat_statements
                WHERE mean_exec_time > 100
                ORDER BY mean_exec_time DESC
                LIMIT 10;
            """)
        )

        return {
            'cache_hit_rate': cache_stats.scalar() or 0,
            'connections': {row.state: row.count for row in connections},
            'slow_queries': [
                {
                    'query': row.query[:100],
                    'avg_time_ms': row.mean_exec_time,
                    'calls': row.calls
                }
                for row in slow_queries
            ]
        }

    async def get_system_metrics(self) -> Dict:
        """Get system resource metrics"""

        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory': {
                'used_mb': psutil.virtual_memory().used / 1024 / 1024,
                'percent': psutil.virtual_memory().percent
            },
            'disk': {
                'used_gb': psutil.disk_usage('/').used / 1024 / 1024 / 1024,
                'percent': psutil.disk_usage('/').percent
            },
            'network': {
                'bytes_sent': psutil.net_io_counters().bytes_sent,
                'bytes_recv': psutil.net_io_counters().bytes_recv
            }
        }

# Add monitoring endpoint
@router.get("/performance")
async def get_performance_metrics(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_admin_user)
):
    """Get system performance metrics (admin only)"""

    monitor = PerformanceMonitor()

    return {
        'database': await monitor.get_database_performance(session),
        'system': await monitor.get_system_metrics(),
        'cache': await get_pool_status(),
        'timestamp': datetime.now(UTC)
    }
```

This comprehensive performance optimization guide provides immediate database improvements through indexing, service decomposition to break down the monolithic architecture, caching strategies to reduce load, and monitoring tools to track performance gains.