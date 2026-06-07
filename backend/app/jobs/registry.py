from __future__ import annotations

from typing import Awaitable, Callable

_HANDLERS: dict[str, Callable[[dict], Awaitable[None]]] = {}


def job(name: str) -> Callable:
    """Decorator that registers an async function as the handler for *name*."""

    def deco(fn: Callable[[dict], Awaitable[None]]) -> Callable[[dict], Awaitable[None]]:
        _HANDLERS[name] = fn
        return fn

    return deco


def get_handler(name: str) -> Callable[[dict], Awaitable[None]]:
    if name not in _HANDLERS:
        raise KeyError(f"no job handler registered for {name!r}")
    return _HANDLERS[name]


def registered_jobs() -> list[str]:
    return sorted(_HANDLERS)
