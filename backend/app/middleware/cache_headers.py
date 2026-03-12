"""HTTP cache headers middleware for improved performance."""
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import hashlib
import json


class CacheHeadersMiddleware:
    """Add appropriate cache headers to responses."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next: Callable):
        response = await call_next(request)

        # Skip caching for auth and write operations
        if request.method != "GET" or "/auth" in request.url.path:
            response.headers["Cache-Control"] = "no-store, max-age=0"
            return response

        # Add caching headers based on endpoint
        path = request.url.path

        # Long cache for static data
        if any(path.startswith(p) for p in ["/api/system", "/api/time/zones"]):
            response.headers["Cache-Control"] = "public, max-age=86400"  # 24 hours

        # Medium cache for user-specific but relatively stable data
        elif any(path.startswith(p) for p in ["/api/projects", "/api/user/profile"]):
            response.headers["Cache-Control"] = "private, max-age=300"  # 5 minutes

        # Short cache for frequently changing data
        elif any(path.startswith(p) for p in ["/api/todos", "/api/metrics", "/api/insights"]):
            response.headers["Cache-Control"] = "private, max-age=60"  # 1 minute

        # No cache for real-time data
        elif any(path.startswith(p) for p in ["/api/calendar", "/api/journal"]):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"

        # Default short cache
        else:
            response.headers["Cache-Control"] = "private, max-age=30"

        # Add ETag for conditional requests
        if hasattr(response, "body"):
            try:
                # Generate ETag from response body
                body_hash = hashlib.md5(response.body).hexdigest()
                response.headers["ETag"] = f'"{body_hash}"'

                # Check if client has matching ETag
                if request.headers.get("If-None-Match") == f'"{body_hash}"':
                    # Return 304 Not Modified
                    return Response(status_code=304, headers=response.headers)
            except:
                pass  # Skip ETag if body can't be hashed

        return response


def add_cache_headers(app):
    """Add cache headers middleware to FastAPI app."""
    app.add_middleware(CacheHeadersMiddleware)