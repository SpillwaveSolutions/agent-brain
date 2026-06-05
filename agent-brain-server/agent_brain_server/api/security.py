"""API key authentication dependency for protected routers (Issue #179).

When ``settings.AGENT_BRAIN_API_KEY`` is empty, ``verify_api_key`` is a no-op
so single-user loopback dev keeps its current zero-config experience. When the
setting is non-empty, the dependency requires an ``X-API-Key`` request header
whose value matches the setting in constant time.

The startup gate in :mod:`agent_brain_server.api.main` enforces that
``AGENT_BRAIN_API_KEY`` is set whenever the server binds to anything other than
``127.0.0.1``; this module only enforces the per-request check.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from agent_brain_server.config.settings import get_settings


async def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency that gates a router on an API key match.

    No-op when ``AGENT_BRAIN_API_KEY`` is empty (loopback dev default).
    """
    expected = get_settings().AGENT_BRAIN_API_KEY
    if not expected:
        return

    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
