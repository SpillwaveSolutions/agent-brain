"""Fictional auth module used only by the E2E tiny-corpus fixture.

The graph extractor should see ``QueryService.verify_token`` as a call
target — this is what powers the find-callers prompt E2E test.
"""

from __future__ import annotations

from .query_service import QueryService


class AuthError(Exception):
    """Base class for auth failures."""


class MalformedTokenError(AuthError):
    """Token format invalid."""


class ExpiredTokenError(AuthError):
    """Token expired."""


class UnknownTokenError(AuthError):
    """Token not recognized by storage."""


def authenticate(token: str, *, query_service: QueryService) -> str:
    """Authenticate a token against the QueryService.

    Returns the user_id on success, raises an ``AuthError`` subclass on
    failure.
    """
    if not token:
        raise MalformedTokenError("empty token")
    user_id = query_service.verify_token(token)
    if user_id is None:
        raise UnknownTokenError(token)
    return user_id
