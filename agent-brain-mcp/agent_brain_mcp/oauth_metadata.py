"""OAuth 2.1 discovery document builders for the MCP server (Phase 66 Plan 02).

This module provides two config-derived builder functions that generate the
RFC-compliant discovery documents the MCP server must advertise as public,
unauthenticated routes (OAUTH-02 / OAUTH-03).

Phase 66 only adds the discovery documents and their public routes; NO token
issuance, NO /authorize, /token, /register, or jwks routes are added here.

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"AS / RS / Public-Route Boundary"
  §"Canonical Resource URI Contract"
  §"Scope-to-Tool Mapping" (the 4 locked agent-brain:* scopes)
  §"Mount-Order Constraint (Critical)" (Risk 3 — routes precede auth middleware)

FORWARD-REFERENCE NOTE
----------------------
The OASM document (``build_oasm_document``) advertises four endpoints
(authorization_endpoint, token_endpoint, registration_endpoint, jwks_uri).
Phase 66 does NOT implement those routes — they are FORWARD-REFERENCES to
routes Phase 67 will add (``/authorize``, ``/token``, ``/register``,
``/.well-known/jwks.json``). The OASM document is spec-valid now per
RFC 8414 §2 — a server MAY advertise metadata before the endpoints are
reachable. Compliant MCP clients perform the OAuth dance by following these
URIs; Phase 67 makes them resolve.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Locked scope list (design doc §"Scope-to-Tool Mapping" — MUST NOT change
# without a schema migration; copy verbatim per plan).
# ---------------------------------------------------------------------------

_SCOPES_SUPPORTED: list[str] = [
    "agent-brain:read",
    "agent-brain:index",
    "agent-brain:admin",
    "agent-brain:subscribe",
]


def build_prm_document(
    *,
    resource: str,
    authorization_servers: list[str],
) -> dict[str, object]:
    """Build the RFC 9728 Protected Resource Metadata (PRM) document.

    Returns a JSON-serializable dict suitable for a 200 response from
    ``GET /.well-known/oauth-protected-resource`` (and its path-suffixed
    variant ``/.well-known/oauth-protected-resource/mcp``).

    The ``scopes_supported`` list is LOCKED to the four agent-brain:*
    scopes defined in the design doc §"Scope-to-Tool Mapping". Do NOT
    add, remove, or reorder entries without a corresponding schema migration.

    RFC 9728 §3.2 required fields:
      - resource: the canonical resource URI (AGENT_BRAIN_OAUTH_RESOURCE)
      - authorization_servers: list of authorization server issuer URIs
        (must be non-empty; at minimum the MCP server's own base URL)
      - scopes_supported: the scopes this resource accepts

    Args:
        resource: The canonical resource URI for this MCP server
            (``AGENT_BRAIN_OAUTH_RESOURCE`` env var or request base URL
            fallback). Must be an absolute URI with a scheme (https://…).
        authorization_servers: Non-empty list of authorization server
            issuer URIs. In the co-located AS+RS shape this is
            ``[base_url]``. In the split AS shape this is
            ``[AGENT_BRAIN_OAUTH_ISSUER]``.

    Returns:
        A dict with keys ``resource``, ``authorization_servers``, and
        ``scopes_supported`` — ready for ``JSONResponse(doc)``.
    """
    return {
        "resource": resource,
        "authorization_servers": authorization_servers,
        "scopes_supported": list(_SCOPES_SUPPORTED),
    }


def build_oasm_document(
    *,
    issuer: str,
    base_url: str,
) -> dict[str, object]:
    """Build the RFC 8414 Authorization Server Metadata (OASM) document.

    Returns a JSON-serializable dict suitable for a 200 response from
    ``GET /.well-known/oauth-authorization-server``.

    FORWARD-REFERENCE ENDPOINTS (Phase 67 adds these routes)
    --------------------------------------------------------
    The following fields point to routes that Phase 67 adds. The OASM
    document is spec-valid per RFC 8414 §2 even while these endpoints do
    not yet resolve — the spec permits advertising metadata before the
    endpoints are live:

      - ``authorization_endpoint``:  ``{issuer}/authorize``     ← Phase 67
      - ``token_endpoint``:          ``{issuer}/token``          ← Phase 67
      - ``registration_endpoint``:   ``{issuer}/register``       ← Phase 67
      - ``jwks_uri``:  ``{issuer}/.well-known/jwks.json``        ← Phase 67

    Phase 66 only: Phase 66 does NOT add /authorize, /token, /register, or
    /.well-known/jwks.json routes — those arrive in Phase 67.

    S256-ONLY PKCE (non-negotiable)
    --------------------------------
    ``code_challenge_methods_supported`` is hardcoded to ``["S256"]``
    per the MCP Authorization 2025-11-25 spec (PKCE S256 is REQUIRED;
    plain is explicitly prohibited). Absence or an empty list causes
    compliant MCP SDK clients to abort the OAuth dance silently
    (design doc ROADMAP SC#2 — "OASM must advertise S256").
    Do NOT change this value.

    Args:
        issuer: The authorization server issuer URI. All endpoint URIs
            are derived from this (``{issuer}/authorize``, etc.).
            Typically ``AGENT_BRAIN_OAUTH_ISSUER`` if set, otherwise
            the MCP server's own base URL (co-located AS+RS shape).
        base_url: The MCP server's request base URL (used only as a
            fallback when ``issuer`` is absent — callers SHOULD pass
            the same value as ``issuer`` when falling back, so the
            endpoints resolve correctly in the co-located shape).

    Returns:
        A dict with RFC 8414 OASM fields — ready for
        ``JSONResponse(doc)``.
    """
    # In the co-located AS+RS shape ``issuer`` and ``base_url`` are the
    # same value. In the split AS shape ``issuer`` is the external AS URI
    # and ``base_url`` is the MCP server's URL (for fallback only).
    _ = base_url  # base_url reserved for future split-AS routing; not used
    # when issuer is already resolved by the caller.

    return {
        "issuer": issuer,
        # FORWARD-REFERENCE to Phase 67 routes (see module docstring):
        "authorization_endpoint": f"{issuer}/authorize",
        "token_endpoint": f"{issuer}/token",
        "registration_endpoint": f"{issuer}/register",
        "jwks_uri": f"{issuer}/.well-known/jwks.json",
        # S256-ONLY — hardcoded-from-spec (MCP Authorization 2025-11-25,
        # PKCE S256 required). Absence = compliant clients abort.
        # DO NOT REMOVE or change to ["plain", "S256"].
        "code_challenge_methods_supported": ["S256"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "response_types_supported": ["code"],
    }


__all__: list[str] = [
    "build_oasm_document",
    "build_prm_document",
]
