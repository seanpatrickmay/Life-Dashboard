from __future__ import annotations

import asyncio
import secrets
import time
from collections import defaultdict
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    _hash_token,
    clear_session_cookie,
    create_user_session,
    get_current_user,
    get_optional_current_user,
    set_session_cookie,
)
from app.core.config import settings
from app.db.models.entities import User, UserRole, UserSession
from app.db.session import get_session
from app.schemas.auth import AuthMeResponse, AuthUserResponse
from app.utils.timezone import eastern_now

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Simple in-memory rate limiter for auth endpoints.
# NOTE: This is per-process only. Multiple uvicorn workers each maintain
# their own store, so effective limits scale with worker count.
# ---------------------------------------------------------------------------
_AUTH_RATE_LIMIT = 10  # max attempts per window
_AUTH_RATE_WINDOW = 60  # window in seconds

_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> None:
    """Raise 429 if *client_ip* has exceeded the auth rate limit."""
    now = time.monotonic()
    window_start = now - _AUTH_RATE_WINDOW
    # Prune old entries and evict empty keys to prevent unbounded growth
    entries = _rate_limit_store[client_ip]
    pruned = [t for t in entries if t > window_start]
    if not pruned:
        _rate_limit_store.pop(client_ip, None)
        return
    _rate_limit_store[client_ip] = pruned
    if len(pruned) >= _AUTH_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later.",
        )
    _rate_limit_store[client_ip].append(now)

OAUTH_STATE_COOKIE = "ld_oauth_state"
OAUTH_REDIRECT_COOKIE = "ld_oauth_redirect"
OAUTH_REMEMBER_COOKIE = "ld_oauth_remember"


def _safe_redirect(target: str | None) -> str:
    if not target:
        return settings.frontend_url
    if target.startswith(settings.frontend_url):
        return target
    return settings.frontend_url


def _oauth_cookie_settings() -> dict[str, Any]:
    return {
        "max_age": 300,
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": settings.session_cookie_samesite,
        "domain": settings.session_cookie_domain,
    }


def _google_auth_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "select_account",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


@router.get("/google/login")
async def google_login(
    request: Request,
    redirect: str | None = Query(None),
    remember_me: bool = Query(False),
) -> Response:
    _check_rate_limit(request.client.host if request.client else "unknown")
    state = secrets.token_urlsafe(24)
    redirect_url = _safe_redirect(redirect)
    response = RedirectResponse(url=_google_auth_url(state))
    response.set_cookie(OAUTH_STATE_COOKIE, state, **_oauth_cookie_settings())
    response.set_cookie(OAUTH_REDIRECT_COOKIE, redirect_url, **_oauth_cookie_settings())
    response.set_cookie(
        OAUTH_REMEMBER_COOKIE,
        "1" if remember_me else "0",
        **_oauth_cookie_settings(),
    )
    return response


async def _exchange_code_for_tokens(code: str) -> dict[str, Any]:
    payload = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()


def _verify_id_token(token: str) -> dict[str, Any]:
    request = google_requests.Request()
    payload = id_token.verify_oauth2_token(token, request, settings.google_client_id)
    if payload.get("aud") != settings.google_client_id:
        raise ValueError("Invalid token audience.")
    return payload


async def _verify_id_token_async(token: str) -> dict[str, Any]:
    # google-auth token verification uses synchronous HTTP under the hood
    # (cert discovery / refresh) and can block the event loop if called directly.
    return await asyncio.to_thread(_verify_id_token, token)


async def _upsert_user(session: AsyncSession, payload: dict[str, Any]) -> User:
    subject = payload.get("sub")
    email = payload.get("email")
    if not subject or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Google profile.")

    stmt = select(User).where(User.google_sub == subject)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    if user is None:
        role = UserRole.ADMIN if email.lower() == settings.admin_email.lower() else UserRole.USER
        user = User(
            email=email,
            display_name=payload.get("name") or payload.get("given_name"),
            google_sub=subject,
            email_verified=bool(payload.get("email_verified")),
            role=role,
        )
        session.add(user)
        try:
            await session.flush()
        except IntegrityError:
            # Concurrent insert for the same user -- fetch the winner's row.
            await session.rollback()
            stmt = select(User).where(User.google_sub == subject)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user is None:
                stmt = select(User).where(User.email == email)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create or locate user after conflict.",
                )
    else:
        if user.google_sub is None:
            user.google_sub = subject
        user.email = email
        user.display_name = payload.get("name") or user.display_name
        user.email_verified = bool(payload.get("email_verified"))
        if user.email.lower() == settings.admin_email.lower() and user.role != UserRole.ADMIN:
            logger.info(
                "Elevating user {} ({}) to admin role (matches ADMIN_EMAIL)",
                user.id,
                user.email,
            )
            user.role = UserRole.ADMIN

    await session.commit()
    await session.refresh(user)
    return user


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    stored_state: str | None = Cookie(None, alias=OAUTH_STATE_COOKIE),
    stored_redirect: str | None = Cookie(None, alias=OAUTH_REDIRECT_COOKIE),
    stored_remember: str | None = Cookie(None, alias=OAUTH_REMEMBER_COOKIE),
) -> Response:
    _check_rate_limit(request.client.host if request.client else "unknown")
    redirect_url = _safe_redirect(stored_redirect)
    if error:
        return RedirectResponse(url=f"{redirect_url}?auth_error={error}")
    if not code or not state or not stored_state or state != stored_state:
        return RedirectResponse(url=f"{redirect_url}?auth_error=invalid_state")

    try:
        tokens = await _exchange_code_for_tokens(code)
    except httpx.HTTPStatusError:
        logger.exception("OAuth token exchange failed (HTTP error)")
        return RedirectResponse(url=f"{redirect_url}?auth_error=token_exchange_failed")
    except Exception:
        logger.exception("OAuth token exchange failed")
        return RedirectResponse(url=f"{redirect_url}?auth_error=token_exchange_failed")
    id_token_value = tokens.get("id_token")
    if not id_token_value:
        return RedirectResponse(url=f"{redirect_url}?auth_error=missing_token")
    try:
        payload = await _verify_id_token_async(id_token_value)
    except ValueError:
        logger.exception("OAuth ID token verification failed (invalid token)")
        return RedirectResponse(url=f"{redirect_url}?auth_error=invalid_token")
    except Exception:
        logger.exception("OAuth ID token verification failed")
        return RedirectResponse(url=f"{redirect_url}?auth_error=invalid_token")

    user = await _upsert_user(session, payload)
    remember_me = stored_remember == "1"
    session_token = await create_user_session(session, user=user, remember_me=remember_me)
    response = RedirectResponse(url=redirect_url)
    set_session_cookie(response, session_token, remember_me=remember_me)
    response.delete_cookie(OAUTH_STATE_COOKIE, domain=settings.session_cookie_domain)
    response.delete_cookie(OAUTH_REDIRECT_COOKIE, domain=settings.session_cookie_domain)
    response.delete_cookie(OAUTH_REMEMBER_COOKIE, domain=settings.session_cookie_domain)
    return response


@router.get("/me", response_model=AuthMeResponse)
async def get_me(
    current_user: User | None = Depends(get_optional_current_user),
) -> AuthMeResponse:
    if current_user is None:
        return AuthMeResponse(user=None)

    return AuthMeResponse(
        user=AuthUserResponse(
            id=current_user.id,
            email=current_user.email,
            display_name=current_user.display_name,
            role=current_user.role.value,
            email_verified=current_user.email_verified,
        )
    )


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: AsyncSession = Depends(get_session),
    token: str | None = Cookie(None, alias=settings.session_cookie_name),
) -> Response:
    if token:
        token_hash = _hash_token(token)
        stmt = select(UserSession).where(UserSession.token_hash == token_hash)
        result = await session.execute(stmt)
        session_obj = result.scalar_one_or_none()
        if session_obj:
            session_obj.revoked_at = eastern_now()
            await session.commit()
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
