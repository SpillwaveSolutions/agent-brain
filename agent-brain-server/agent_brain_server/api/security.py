"""Bearer-token authentication for protected routers (Issues #179 + #199).

``verify_bearer_token`` is the canonical FastAPI dependency as of 199-02.
It enforces RFC 6750 ``Authorization: Bearer <token>`` on every gated router
and also accepts the deprecated ``X-API-Key`` header (from PR #195) with a
one-time deprecation log so existing callers keep working through one
release window.

Resolution rules:

* If ``settings.INSECURE_NO_AUTH`` is True, the dependency is a no-op (loud
  warning belongs to the startup gate, not the per-request path).
* If ``settings.API_KEY`` is unset, the dependency is a no-op so loopback
  single-user dev keeps its zero-config experience. The startup gate in
  :mod:`agent_brain_server.api.main` decides when an unset key is allowed
  (loopback only — non-loopback startup refuses).
* Otherwise, a request must carry ``Authorization: Bearer <token>``
  (preferred) OR the deprecated ``X-API-Key`` header. Both are compared in
  constant time against ``settings.API_KEY``. Mismatch → 401 with
  ``WWW-Authenticate: Bearer`` per RFC 6750.

The ``Settings`` validator backfills ``API_KEY`` from the legacy
``AGENT_BRAIN_API_KEY`` env var (see
:mod:`agent_brain_server.config.settings`), so callers who haven't migrated
their env vars yet still produce a non-None ``API_KEY`` at runtime.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import Header, HTTPException, status

from agent_brain_server.config.settings import get_settings

logger = logging.getLogger(__name__)

_BEARER_PREFIX = "bearer "


async def verify_bearer_token(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency that gates a router on a Bearer-token match.

    Accepts ``Authorization: Bearer <token>`` (preferred, RFC 6750) and the
    deprecated ``X-API-Key`` header. No-op when ``API_KEY`` is unset or
    ``INSECURE_NO_AUTH`` is True (loopback dev default + explicit opt-out).
    """
    settings = get_settings()

    if settings.INSECURE_NO_AUTH:
        return

    if settings.API_KEY is None:
        return

    expected = settings.API_KEY.get_secret_value()

    # Bearer scheme first — canonical per RFC 6750.
    if authorization is not None:
        if authorization[: len(_BEARER_PREFIX)].lower() == _BEARER_PREFIX:
            token = authorization[len(_BEARER_PREFIX) :].strip()
            if secrets.compare_digest(token, expected):
                return
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            )
        # Authorization header present but not Bearer — malformed for our scheme.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use the Bearer scheme",
            headers={"WWW-Authenticate": 'Bearer error="invalid_request"'},
        )

    # Fallback: deprecated X-API-Key header (PR #195 compatibility).
    if x_api_key is not None:
        if secrets.compare_digest(x_api_key, expected):
            logger.warning(
                "X-API-Key header is deprecated; switch to 'Authorization: "
                "Bearer <token>'. Support will be removed in a future release. "
                "(Issue #199)"
            )
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing credentials. Use 'Authorization: Bearer <token>'.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Backwards-compatible alias. Older imports of ``verify_api_key`` (and the
# test_auth_enforcement.py structural check that pre-dates 199-02) keep
# resolving to the same callable so external code doesn't break during the
# deprecation window. New router code MUST import ``verify_bearer_token``.
verify_api_key = verify_bearer_token
