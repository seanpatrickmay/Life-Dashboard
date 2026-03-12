"""Enhanced security configuration and utilities."""
from typing import Optional
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
import jwt
from slowapi import Limiter
from slowapi.util import get_remote_address

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Security constants
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"
MIN_PASSWORD_LENGTH = 12
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class SecurityConfig:
    """Security configuration settings."""

    # CSRF Protection
    CSRF_TOKEN_LENGTH = 32
    CSRF_HEADER_NAME = "X-CSRF-Token"

    # Session Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = True  # Set to True in production with HTTPS
    SESSION_COOKIE_SAMESITE = "lax"

    # Headers
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    }


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(length)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets security requirements."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"

    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"

    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"

    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"

    # Check for common passwords (simplified check)
    common_passwords = ["password", "12345678", "qwerty", "admin", "letmein"]
    if password.lower() in common_passwords:
        return False, "Password is too common"

    return True, "Password is strong"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token with expiration."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    # Use a secure secret key from environment variables
    secret_key = secrets.token_urlsafe(32)  # Should come from settings
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def generate_csrf_token() -> str:
    """Generate a CSRF protection token."""
    return secrets.token_urlsafe(SecurityConfig.CSRF_TOKEN_LENGTH)


def verify_csrf_token(token: str, session_token: str) -> bool:
    """Verify CSRF token matches session."""
    return hmac.compare_digest(token, session_token)


class RateLimitMiddleware:
    """Rate limiting middleware for authentication endpoints."""

    def __init__(self):
        self.attempts = {}
        self.lockouts = {}

    def check_rate_limit(self, identifier: str) -> bool:
        """Check if identifier is rate limited."""
        now = datetime.utcnow()

        # Check if currently locked out
        if identifier in self.lockouts:
            lockout_until = self.lockouts[identifier]
            if now < lockout_until:
                return False
            else:
                # Lockout expired, reset
                del self.lockouts[identifier]
                if identifier in self.attempts:
                    del self.attempts[identifier]

        # Track attempts
        if identifier not in self.attempts:
            self.attempts[identifier] = []

        # Clean old attempts (outside 15 min window)
        cutoff = now - timedelta(minutes=15)
        self.attempts[identifier] = [
            attempt for attempt in self.attempts[identifier]
            if attempt > cutoff
        ]

        # Check if too many attempts
        if len(self.attempts[identifier]) >= MAX_LOGIN_ATTEMPTS:
            self.lockouts[identifier] = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            return False

        # Record this attempt
        self.attempts[identifier].append(now)
        return True


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent XSS."""
    if not text:
        return ""

    # Truncate to max length
    text = text[:max_length]

    # Remove potentially dangerous characters
    dangerous_chars = ["<", ">", "&", '"', "'", "/", "\\"]
    for char in dangerous_chars:
        text = text.replace(char, "")

    return text.strip()


def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


class SecureHeaders:
    """Middleware to add security headers to all responses."""

    async def __call__(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        for header, value in SecurityConfig.SECURITY_HEADERS.items():
            response.headers[header] = value

        return response


# Input validation schemas with strict typing
from pydantic import BaseModel, validator, constr, EmailStr


class SecureUserCreate(BaseModel):
    """Secure user creation with validation."""
    email: EmailStr
    password: constr(min_length=12, max_length=128)

    @validator('password')
    def validate_password(cls, v):
        is_valid, message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(message)
        return v


class SecureLoginRequest(BaseModel):
    """Secure login request with validation."""
    email: EmailStr
    password: constr(min_length=1, max_length=128)
    csrf_token: Optional[str] = None