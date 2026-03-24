"""Application-level exception types used across services and routers."""

from __future__ import annotations


class NotFoundException(Exception):
    """Raised when a requested resource does not exist.

    Services should raise this instead of ``ValueError`` for not-found
    conditions so that routers can distinguish 404 from 400.
    """
