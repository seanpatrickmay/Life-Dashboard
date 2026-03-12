# Security Improvements Implementation

## Immediate Actions (Day 1)

### 1. Credential Rotation & Management

#### Step 1: Create new .env.example without sensitive data
```bash
# .env.example
DATABASE_URL=postgresql://user:password@host:5432/dbname
GARMIN_EMAIL=your_email@example.com
GARMIN_PASSWORD=your_secure_password
ADMIN_TOKEN=generate_with_secrets.token_urlsafe(32)
OPENAI_API_KEY=sk-...
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
ENCRYPTION_KEY=generate_with_fernet.generate_key()
FALLBACK_ENCRYPTION_KEYS=[]
```

#### Step 2: Implement Secret Manager Integration
```python
# backend/app/core/secrets.py
import boto3
from typing import Optional
from functools import lru_cache

class SecretsManager:
    def __init__(self):
        self.client = boto3.client('secretsmanager')
        self._cache = {}

    @lru_cache(maxsize=100)
    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieve secret from AWS Secrets Manager with caching"""
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            return response['SecretString']
        except Exception as e:
            print(f"Error retrieving secret {secret_name}: {e}")
            return None

    def get_database_url(self) -> str:
        """Construct database URL from secrets"""
        db_password = self.get_secret('life-dashboard/db/password')
        db_host = self.get_secret('life-dashboard/db/host')
        db_user = self.get_secret('life-dashboard/db/user')
        db_name = self.get_secret('life-dashboard/db/name')

        return f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"

secrets_manager = SecretsManager()
```

#### Step 3: Update Configuration
```python
# backend/app/core/config.py
from .secrets import secrets_manager
import os

class Settings(BaseSettings):
    # Use environment variable with fallback to secrets manager
    database_url: str = Field(
        default_factory=lambda: os.getenv('DATABASE_URL') or secrets_manager.get_database_url()
    )

    garmin_password: str = Field(
        default_factory=lambda: secrets_manager.get_secret('life-dashboard/garmin/password')
    )

    openai_api_key: str = Field(
        default_factory=lambda: secrets_manager.get_secret('life-dashboard/openai/key')
    )

    # Generate strong admin token if not set
    admin_token: str = Field(
        default_factory=lambda: secrets_manager.get_secret('life-dashboard/admin/token')
                                or secrets.token_urlsafe(32)
    )
```

### 2. CORS Configuration Fix

```python
# backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Define allowed origins based on environment
if settings.environment == "production":
    origins = [
        "https://life-dashboard.yourdomain.com",
        "https://www.life-dashboard.yourdomain.com"
    ]
else:
    origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Total-Count"],
    max_age=3600,
)
```

### 3. Add Security Headers

```python
# backend/app/middleware/security.py
from fastapi import Request
from fastapi.responses import Response
import uuid

async def security_headers_middleware(request: Request, call_next):
    # Generate request ID for tracking
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)

    # Add security headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Remove server header
    response.headers.pop("Server", None)

    return response

# In main.py
app.middleware("http")(security_headers_middleware)
```

### 4. Implement Rate Limiting

```python
# backend/app/middleware/rate_limiting.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from redis import asyncio as redis
import json

# Create limiter with Redis backend
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per hour"],
    storage_uri="redis://localhost:6379",
    headers_enabled=True
)

# Custom rate limit for authentication endpoints
auth_limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["5 per minute", "20 per hour"],
    storage_uri="redis://localhost:6379"
)

# Add to main.py
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Apply to specific routes
@router.post("/auth/login")
@limiter.limit("5 per minute")
async def login(request: Request, ...):
    pass
```

### 5. Add Dependency Scanning

```yaml
# .github/workflows/security.yml
name: Security Scanning

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight

jobs:
  dependency-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Python Security Check
        run: |
          pip install safety
          safety check --json > safety-report.json

      - name: Node Security Check
        run: |
          cd frontend
          npm audit --json > npm-audit.json

      - name: Upload Security Reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            safety-report.json
            npm-audit.json

  sast-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run Bandit Security Scan
        run: |
          pip install bandit
          bandit -r backend/ -f json -o bandit-report.json

      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: auto
```

### 6. Implement Audit Logging

```python
# backend/app/services/audit_service.py
from datetime import datetime, UTC
from typing import Optional, Any
import json
from app.db.models import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession

class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        user_id: Optional[int],
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        """Log security-relevant events"""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.now(UTC)
        )

        self.session.add(audit_log)
        await self.session.commit()

    async def log_authentication(
        self,
        user_id: Optional[int],
        success: bool,
        method: str,
        ip_address: str,
        user_agent: str,
        failure_reason: Optional[str] = None
    ):
        """Log authentication attempts"""
        await self.log_event(
            user_id=user_id,
            action="AUTH_ATTEMPT",
            resource_type="authentication",
            resource_id=method,
            details={
                "success": success,
                "method": method,
                "failure_reason": failure_reason
            },
            ip_address=ip_address,
            user_agent=user_agent
        )

    async def log_data_access(
        self,
        user_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: str
    ):
        """Log data access for compliance"""
        await self.log_event(
            user_id=user_id,
            action=f"DATA_{action.upper()}",
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address
        )

# Create audit log table
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50), index=True)
    resource_type: Mapped[str] = mapped_column(String(50), index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(255))
    details: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )

    # Add index for common queries
    __table_args__ = (
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_action_timestamp', 'action', 'timestamp'),
    )
```

## Week 1 Actions

### 7. Session Security Improvements

```python
# backend/app/services/auth_service.py
import secrets
from datetime import datetime, timedelta, UTC
from typing import Optional
import hashlib
from redis import asyncio as redis

class EnhancedAuthService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.session_ttl = timedelta(hours=24)
        self.remember_me_ttl = timedelta(days=30)

    async def create_session(
        self,
        user_id: int,
        remember_me: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Create secure session with metadata"""
        # Generate cryptographically secure token
        token = secrets.token_urlsafe(48)
        session_id = hashlib.sha256(token.encode()).hexdigest()

        # Store session data in Redis
        session_data = {
            "user_id": user_id,
            "created_at": datetime.now(UTC).isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "remember_me": remember_me
        }

        ttl = self.remember_me_ttl if remember_me else self.session_ttl

        await self.redis.setex(
            f"session:{session_id}",
            int(ttl.total_seconds()),
            json.dumps(session_data)
        )

        # Track active sessions per user
        await self.redis.sadd(f"user_sessions:{user_id}", session_id)

        return token

    async def validate_session(
        self,
        token: str,
        ip_address: Optional[str] = None
    ) -> Optional[dict]:
        """Validate session with additional security checks"""
        session_id = hashlib.sha256(token.encode()).hexdigest()

        session_data = await self.redis.get(f"session:{session_id}")
        if not session_data:
            return None

        data = json.loads(session_data)

        # Optional: Verify IP address hasn't changed
        if ip_address and data.get("ip_address") != ip_address:
            # Log suspicious activity
            await self.log_security_event(
                "SESSION_IP_MISMATCH",
                user_id=data["user_id"],
                details={"original_ip": data.get("ip_address"), "current_ip": ip_address}
            )

        # Refresh session TTL on activity
        ttl = self.remember_me_ttl if data.get("remember_me") else self.session_ttl
        await self.redis.expire(f"session:{session_id}", int(ttl.total_seconds()))

        return data

    async def invalidate_all_sessions(self, user_id: int):
        """Invalidate all sessions for a user (e.g., on password change)"""
        session_keys = await self.redis.smembers(f"user_sessions:{user_id}")

        for session_id in session_keys:
            await self.redis.delete(f"session:{session_id}")

        await self.redis.delete(f"user_sessions:{user_id}")

    async def cleanup_expired_sessions(self):
        """Periodic cleanup of expired session references"""
        # This would be run as a scheduled job
        pass
```

### 8. Input Validation Enhancement

```python
# backend/app/schemas/validators.py
from pydantic import BaseModel, validator, Field
from typing import Optional
import re
from datetime import datetime, date
import bleach

class SanitizationMixin:
    """Mixin for input sanitization"""

    @staticmethod
    def sanitize_html(value: str) -> str:
        """Remove potentially dangerous HTML"""
        return bleach.clean(
            value,
            tags=['b', 'i', 'u', 'em', 'strong', 'p', 'br'],
            strip=True
        )

    @staticmethod
    def sanitize_filename(value: str) -> str:
        """Sanitize filename to prevent directory traversal"""
        # Remove any path components
        value = value.replace('/', '').replace('\\', '').replace('..', '')
        # Keep only alphanumeric, dash, underscore, and dot
        return re.sub(r'[^a-zA-Z0-9._-]', '', value)

class TodoCreateRequest(BaseModel, SanitizationMixin):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    deadline_utc: Optional[datetime] = None
    project_id: Optional[int] = None

    @validator('title')
    def sanitize_title(cls, v):
        # Remove any HTML tags and trim whitespace
        v = cls.sanitize_html(v)
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v

    @validator('description')
    def sanitize_description(cls, v):
        if v:
            return cls.sanitize_html(v)
        return v

    @validator('deadline_utc')
    def validate_deadline(cls, v):
        if v and v < datetime.now(UTC):
            raise ValueError("Deadline cannot be in the past")
        return v

class MetricsQueryParams(BaseModel):
    start_date: date
    end_date: date
    metrics: list[str] = Field(default_factory=list)

    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError("End date must be after start date")

        # Prevent requesting too much data
        if 'start_date' in values:
            delta = v - values['start_date']
            if delta.days > 365:
                raise ValueError("Date range cannot exceed 365 days")

        return v

    @validator('metrics')
    def validate_metrics(cls, v):
        allowed_metrics = {
            'hrv', 'resting_hr', 'sleep_hours', 'training_load',
            'recovery_score', 'stress_level', 'activity_minutes'
        }

        invalid = set(v) - allowed_metrics
        if invalid:
            raise ValueError(f"Invalid metrics: {invalid}")

        return v
```

### 9. Secure File Upload Handling

```python
# backend/app/services/file_service.py
import hashlib
import magic
from pathlib import Path
from typing import Optional
import aiofiles
import uuid

class SecureFileService:
    ALLOWED_MIME_TYPES = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/gif': ['.gif'],
        'application/pdf': ['.pdf'],
        'text/plain': ['.txt'],
        'text/csv': ['.csv']
    }

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self, upload_dir: Path):
        self.upload_dir = upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save_uploaded_file(
        self,
        file_content: bytes,
        original_filename: str,
        user_id: int
    ) -> dict:
        """Securely save uploaded file with validation"""

        # Check file size
        if len(file_content) > self.MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds {self.MAX_FILE_SIZE} bytes")

        # Verify MIME type
        mime = magic.from_buffer(file_content, mime=True)
        if mime not in self.ALLOWED_MIME_TYPES:
            raise ValueError(f"File type {mime} not allowed")

        # Generate secure filename
        file_hash = hashlib.sha256(file_content).hexdigest()[:16]
        file_id = uuid.uuid4().hex
        extension = Path(original_filename).suffix.lower()

        # Verify extension matches MIME type
        if extension not in self.ALLOWED_MIME_TYPES.get(mime, []):
            raise ValueError("File extension doesn't match content type")

        # Create user-specific directory
        user_dir = self.upload_dir / str(user_id)
        user_dir.mkdir(exist_ok=True)

        # Save file with secure name
        secure_filename = f"{file_id}_{file_hash}{extension}"
        file_path = user_dir / secure_filename

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)

        # Store metadata in database
        return {
            "file_id": file_id,
            "original_name": original_filename,
            "secure_name": secure_filename,
            "mime_type": mime,
            "size": len(file_content),
            "hash": file_hash,
            "path": str(file_path)
        }

    def verify_file_access(
        self,
        user_id: int,
        file_path: Path
    ) -> bool:
        """Verify user has access to file"""
        # Ensure file is within user's directory
        user_dir = self.upload_dir / str(user_id)
        try:
            file_path.resolve().relative_to(user_dir.resolve())
            return True
        except ValueError:
            return False
```

## Security Testing Implementation

```python
# backend/tests/test_security.py
import pytest
from httpx import AsyncClient
from unittest.mock import patch
import secrets

@pytest.mark.asyncio
class TestSecurityFeatures:

    async def test_sql_injection_prevention(self, client: AsyncClient):
        """Test that SQL injection attempts are blocked"""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "1; UPDATE users SET role='admin' WHERE id=1"
        ]

        for payload in malicious_inputs:
            response = await client.get(f"/api/todos?search={payload}")
            # Should handle safely without executing SQL
            assert response.status_code in [200, 400]

            # Verify database wasn't affected
            check_response = await client.get("/api/health")
            assert check_response.status_code == 200

    async def test_xss_prevention(self, client: AsyncClient, auth_headers):
        """Test that XSS attempts are sanitized"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(XSS)'>"
        ]

        for payload in xss_payloads:
            response = await client.post(
                "/api/todos",
                json={"title": payload, "description": payload},
                headers=auth_headers
            )

            if response.status_code == 200:
                data = response.json()
                # Verify script tags were removed
                assert "<script>" not in data["title"]
                assert "javascript:" not in data["title"]

    async def test_authentication_required(self, client: AsyncClient):
        """Test that protected endpoints require authentication"""
        protected_endpoints = [
            "/api/todos",
            "/api/metrics/daily",
            "/api/projects",
            "/api/calendar/events"
        ]

        for endpoint in protected_endpoints:
            response = await client.get(endpoint)
            assert response.status_code == 401

    async def test_rate_limiting(self, client: AsyncClient):
        """Test that rate limiting is enforced"""
        # Make many rapid requests
        for i in range(10):
            response = await client.post(
                "/api/auth/login",
                json={"email": f"test{i}@example.com", "password": "wrong"}
            )

        # Should be rate limited after threshold
        assert response.status_code == 429
        assert "Retry-After" in response.headers

    async def test_secure_headers(self, client: AsyncClient):
        """Test that security headers are present"""
        response = await client.get("/api/health")

        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "X-Request-ID" in response.headers
        assert "Server" not in response.headers

    async def test_session_invalidation(self, client: AsyncClient, auth_service):
        """Test that sessions can be invalidated"""
        # Create session
        token = await auth_service.create_session(user_id=1)

        # Verify it works
        session = await auth_service.validate_session(token)
        assert session is not None

        # Invalidate all sessions
        await auth_service.invalidate_all_sessions(user_id=1)

        # Verify session no longer works
        session = await auth_service.validate_session(token)
        assert session is None

    async def test_password_complexity(self, client: AsyncClient):
        """Test password complexity requirements"""
        weak_passwords = [
            "password",
            "12345678",
            "abc123",
            "qwerty"
        ]

        for password in weak_passwords:
            response = await client.post(
                "/api/auth/register",
                json={"email": "test@example.com", "password": password}
            )
            assert response.status_code == 400
            assert "password" in response.json()["detail"].lower()
```

## Security Monitoring Dashboard

```python
# backend/app/services/security_monitoring.py
from collections import defaultdict
from datetime import datetime, timedelta, UTC
from typing import Dict, List
import asyncio
from sqlalchemy import select, func
from app.db.models import AuditLog

class SecurityMonitor:
    def __init__(self, session, redis_client):
        self.session = session
        self.redis = redis_client
        self.alert_thresholds = {
            "failed_logins": 5,
            "session_hijack_attempts": 2,
            "rate_limit_violations": 10,
            "suspicious_file_uploads": 3
        }

    async def get_security_metrics(self) -> dict:
        """Get current security metrics for monitoring"""
        now = datetime.now(UTC)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        metrics = {
            "last_hour": await self._get_metrics_for_period(hour_ago, now),
            "last_24h": await self._get_metrics_for_period(day_ago, now),
            "active_sessions": await self._count_active_sessions(),
            "blocked_ips": await self._get_blocked_ips(),
            "recent_threats": await self._get_recent_threats()
        }

        return metrics

    async def _get_metrics_for_period(self, start: datetime, end: datetime) -> dict:
        """Get security metrics for a specific time period"""
        stmt = (
            select(
                AuditLog.action,
                func.count(AuditLog.id).label("count")
            )
            .where(AuditLog.timestamp.between(start, end))
            .group_by(AuditLog.action)
        )

        result = await self.session.execute(stmt)

        metrics = defaultdict(int)
        for row in result:
            metrics[row.action] = row.count

        return dict(metrics)

    async def check_for_anomalies(self, user_id: int) -> List[str]:
        """Check for security anomalies for a user"""
        anomalies = []

        # Check for multiple login locations
        recent_ips = await self._get_recent_ips(user_id)
        if len(recent_ips) > 3:
            anomalies.append(f"Multiple login locations detected: {recent_ips}")

        # Check for unusual activity times
        activity_hours = await self._get_activity_hours(user_id)
        if self._is_unusual_pattern(activity_hours):
            anomalies.append("Unusual activity pattern detected")

        # Check for rapid API calls
        api_rate = await self._get_api_call_rate(user_id)
        if api_rate > 100:  # calls per minute
            anomalies.append(f"High API call rate: {api_rate}/min")

        return anomalies

    async def generate_security_report(self) -> dict:
        """Generate comprehensive security report"""
        return {
            "metrics": await self.get_security_metrics(),
            "top_threats": await self._get_top_threats(),
            "vulnerable_users": await self._get_vulnerable_users(),
            "recommendations": await self._generate_recommendations()
        }
```

This comprehensive security implementation addresses all critical vulnerabilities and provides a robust foundation for protecting your Life-Dashboard application.