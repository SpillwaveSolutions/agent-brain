"""OAuth 2.1 client provider factory for McpHttpBackend (Phase 69 Plan 03).

This module assembles the SDK ``OAuthClientProvider`` used by
``McpHttpBackend._get_auth()`` to drive the client-side OAuth 2.1 dance.

The factory wires together three Phase 69 pieces:

* ``FileTokenStorage`` (Plan 01) — persists the token + DCR result at
  ``state_dir/mcp-oauth-tokens.json`` with mode ``0o600`` so that Pattern A
  (fresh subprocess per CLI call) reuses the cached token without
  re-triggering the browser login.
* ``build_redirect_handler`` + ``LoopbackCallbackServer`` +
  ``build_callback_handler`` (Plan 02) — the browser-open UX + ephemeral
  loopback HTTP server that captures the authorization code.
* ``OAuthClientProvider`` (SDK) + ``OAuthClientMetadata`` (SDK) — the SDK
  drives PKCE S256, PRM/OASM discovery, DCR, token exchange, and silent
  refresh; this factory just supplies the constructor arguments.

Context decisions (69-CONTEXT.md):
  A. Opt-in, default OFF. When OAuth is not enabled, this module is never
     imported (preserves lazy-import budget for HTTP/UDS-only invocations).
  A. DCR (Dynamic Client Registration) — no ``client_metadata_url``; the
     co-located AS (Phase 67) supports DCR; a local CLI cannot host a CIMD
     HTTPS doc.
  A. Scopes: the full union the CLI needs (read + index + admin) so any
     command works after a single login.
  A. Dance timeout: 300 s (SDK default, passed explicitly for clarity).

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Client side -- mcp.client.auth"
  §"Client-Side Token Storage: FileTokenStorage chmod 0o600 Required (Pattern A)"
  §"Additional Probe: FileTokenStorage chmod 0o600"
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.client.auth.oauth2 import OAuthClientProvider

# ---------------------------------------------------------------------------
# Locked scope union (read + index + admin)
#
# "agent-brain:subscribe" is intentionally omitted from the client request;
# the CLI subscription commands are not gated by OAuth in Phase 69.  The
# server may downscope or ignore extra scopes — requesting the broader set
# here is safe (Context decision A).
# ---------------------------------------------------------------------------

CLIENT_SCOPES = "agent-brain:read agent-brain:index agent-brain:admin"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_oauth_client_provider(
    server_url: str,
    state_dir: Path,
) -> OAuthClientProvider:
    """Assemble the SDK OAuthClientProvider for the client-side OAuth dance.

    All SDK imports are kept *inside* this function so that agent-brain-mcp
    processes that use HTTP/UDS transport only (no OAuth) never pay the cost
    of importing the MCP OAuth machinery.

    The loopback server is bound eagerly (before DCR) so that the ephemeral
    port is known at registration time and ``OAuthClientMetadata.redirect_uris``
    carries the correct ``http://127.0.0.1:<port>/callback`` URI.

    Args:
        server_url: The full URL of the MCP server being connected to, e.g.
            ``"http://127.0.0.1:9999/mcp"``.  Passed through to the SDK as
            ``OAuthClientProvider(server_url=...)``.
        state_dir: Project state directory.  ``FileTokenStorage`` writes
            ``state_dir/mcp-oauth-tokens.json`` with mode ``0o600``.  The
            directory need not exist yet — it is created on the first write.

    Returns:
        A configured ``OAuthClientProvider`` instance (implements
        ``httpx.Auth``) that drives the PKCE S256 dance against the server
        at *server_url*.

    Note:
        The loopback server only handles a request during an interactive
        dance.  When the token cache is warm the SDK never invokes the
        callback and the server simply sits idle, bound to its ephemeral port,
        until the provider is garbage-collected.
    """
    # Lazy imports — keep the module-level footprint at zero for non-OAuth
    # code paths (preserves the established deferred-import pattern from
    # client.py and the rest of McpHttpBackend).
    from mcp.client.auth.oauth2 import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata

    from agent_brain_mcp.oauth.oauth_handlers import (
        LoopbackCallbackServer,
        build_callback_handler,
        build_redirect_handler,
    )
    from agent_brain_mcp.oauth.token_storage import FileTokenStorage

    # 1. Bind the loopback server NOW so redirect_uri is known before DCR.
    #    The loopback server only handles a request during an interactive dance;
    #    if the token cache is warm the SDK never invokes the callback and the
    #    server simply sits idle bound to a port.
    server = LoopbackCallbackServer()

    # 2. Assemble the OAuthClientMetadata for DCR.
    #    redirect_uris is required (Field(..., min_length=1)); the string
    #    redirect_uri coerces to AnyUrl via Pydantic.
    #    scope is a space-delimited string per RFC 7591 §2.
    metadata = OAuthClientMetadata(
        redirect_uris=[server.redirect_uri],  # type: ignore[list-item]
        scope=CLIENT_SCOPES,
    )

    # 3. FileTokenStorage at state_dir/mcp-oauth-tokens.json (Plan 01).
    storage = FileTokenStorage(state_dir)

    # 4. Browser-open redirect handler + loopback callback handler (Plan 02).
    redirect = build_redirect_handler()
    callback = build_callback_handler(server)

    # 5. Assemble the provider.
    #    DCR path: client_metadata_url is NOT passed (Context decision A).
    #    Timeout: 300.0 s (SDK default, passed explicitly per decision A).
    return OAuthClientProvider(
        server_url=server_url,
        client_metadata=metadata,
        storage=storage,
        redirect_handler=redirect,
        callback_handler=callback,
        timeout=300.0,
    )
