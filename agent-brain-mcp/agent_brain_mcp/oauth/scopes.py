"""Per-tool OAuth scope primitives for the Agent Brain MCP Resource Server.

This module is the implementation of OAUTH-06 SC#4 ("scope-to-tool single source of
truth") for the helper / exception layer consumed by the dispatch guard in Plan 02.

Design doc references:
  - docs/plans/2026-06-14-mcp-v4-oauth-design.md §"Scope-to-Tool Mapping"
  - docs/plans/2026-06-14-mcp-v4-oauth-design.md §"Insufficient Scope Response"

The 4 locked scopes (Phase 65/66, advertised in PRM/OASM):
  agent-brain:read      — read-only tool calls and resource reads
  agent-brain:index     — indexing / mutation tool calls
  agent-brain:admin     — destructive / administrative tool calls
  agent-brain:subscribe — subscription channel access (corpus://, job://)

``require_scope()`` is the sole enforcement primitive.  It is a pure function
over (required, token_scopes) — intentionally free of env / request context so
it is trivially unit-testable and verifier-independent.  Phase 70 swaps the
verifier without touching this helper.

Plan 02 (pre-dispatch ASGI guard in server.py) reads the granted scopes from
``request.state.auth`` (BearerAuthBackend populates it via LocalRs256Verifier),
calls ``require_scope()``, and — on ``InsufficientScopeError`` — emits:

    HTTP 403 Forbidden
    WWW-Authenticate: Bearer error="insufficient_scope",
                             scope="<REQUIRED scope>",
                             resource_metadata="<PRM url>"

The ``scope`` field in the header names the **required** scope (not the token's);
Plan 02 reads it from ``InsufficientScopeError.required``.
"""

from __future__ import annotations

__all__ = ["VALID_SCOPES", "InsufficientScopeError", "require_scope"]

# ---------------------------------------------------------------------------
# Locked scope strings — must byte-match http.py ``_OAUTH_SCOPES``
# (Phase 65/66 lock; advertised in PRM/OASM already).
# ---------------------------------------------------------------------------

VALID_SCOPES: frozenset[str] = frozenset(
    {
        "agent-brain:read",
        "agent-brain:index",
        "agent-brain:admin",
        "agent-brain:subscribe",
    }
)


# ---------------------------------------------------------------------------
# InsufficientScopeError
# ---------------------------------------------------------------------------


class InsufficientScopeError(Exception):
    """Raised by ``require_scope`` when a token lacks the required scope.

    Plan 02's pre-dispatch guard catches this and emits:

        HTTP 403  WWW-Authenticate: Bearer error="insufficient_scope",
                                           scope="<required>", ...

    The ``.required`` attribute names the scope the token MUST have (not the
    set of scopes the token carries).  The ``WWW-Authenticate`` ``scope``
    field mirrors this value so the client knows which scope to request via
    step-up.

    Attributes:
        required: The scope the token was required to carry.
        token_scopes: The scopes the token actually carried (for logging).
    """

    def __init__(self, required: str, *, token_scopes: list[str] | None = None) -> None:
        """Initialise with the required scope and optional token scope list.

        Args:
            required: The scope that the token was required to carry but did not.
                This value is carried to the ``WWW-Authenticate`` response header
                as ``scope="<required>"``.
            token_scopes: The scopes the token actually carried.  Used for
                diagnostic logging only — not surfaced to the client.  Defaults
                to an empty list when omitted.
        """
        self.required: str = required
        self.token_scopes: list[str] = token_scopes or []
        super().__init__(f"insufficient_scope: requires {required}")


# ---------------------------------------------------------------------------
# require_scope — the single enforcement primitive
# ---------------------------------------------------------------------------


def require_scope(required: str, token_scopes: list[str]) -> None:
    """Raise ``InsufficientScopeError`` if the required scope is not granted.

    This is a pure, side-effect-free function.  It reads no environment
    variables and holds no request context — call it from any sync or async
    context.

    Args:
        required: The scope the current operation requires.  Must be one of
            ``VALID_SCOPES``.
        token_scopes: The scopes granted to the token (extracted from the
            JWT ``scope`` claim by ``LocalRs256Verifier``).  An empty list
            triggers ``InsufficientScopeError`` for every ``required`` value
            (deny-by-default — no implicit trust for unscoped tokens).

    Returns:
        None when ``required in token_scopes``.

    Raises:
        InsufficientScopeError: When ``required`` is absent from
            ``token_scopes`` (including the empty-list case).
            ``exc.required`` names the REQUIRED scope for the
            ``WWW-Authenticate`` response header.

    Example::

        # Read-only call — passes
        require_scope("agent-brain:read", access_token.scopes)

        # Privileged call — raises if token only has :read
        try:
            require_scope("agent-brain:admin", access_token.scopes)
        except InsufficientScopeError as exc:
            # exc.required == "agent-brain:admin"
            return build_403_response(exc.required, prm_url)
    """
    if required not in token_scopes:
        raise InsufficientScopeError(required, token_scopes=token_scopes)
