"""Streamable HTTP listener for the MCP server (Phase 53 Plan 02).

This module replaces Plan 01's :func:`run_http` stub with a working
in-process uvicorn server that mounts the MCP SDK's
:class:`mcp.server.streamable_http_manager.StreamableHTTPSessionManager`
at ``/mcp`` and serves a tiny ``/healthz`` probe alongside it.

Phase 68 Plan 02 additions (OAUTH-06 SC#2/SC#3):
* ``ScopeEnforcementMiddleware`` — a pre-dispatch ASGI guard that buffers
  the JSON-RPC request body (handling multi-part ``http.request`` frames),
  maps ``method(+params.name)`` to a required scope, reads the granted
  scopes from ``scope["user"].scopes`` (set by AuthenticationMiddleware),
  and on insufficient scope emits HTTP **403** with
  ``WWW-Authenticate: Bearer error="insufficient_scope"`` BEFORE the
  session manager runs. Engages only in oauth mode.
* The guard is wired INSIDE ``AuthenticationMiddleware`` (so
  ``scope["user"]`` is set before it reads scopes) and INSIDE
  ``RequireAuthMiddleware`` (so unauthenticated requests still 401 first):
  ``RequireAuthMiddleware(
      AuthenticationMiddleware(ScopeEnforcementMiddleware(...), ...),
      required_scopes=[], ...
  )``
  The none/basic mount stays the bare ``Mount(MCP_MOUNT_PATH, mcp_asgi_app)``.

Design decisions cross-referenced from
``.planning/phases/53-streamable-http-transport/53-CONTEXT.md``:

* **D-05 / D-06** — Lean on the MCP SDK's built-in Streamable HTTP
  support; run uvicorn in-process (no subprocess orchestration).
* **D-07** — Mount path is ``/mcp``; ``/healthz`` lives alongside it.
* **D-08** — Hard whitelist on ``--host``: only ``127.0.0.1``,
  ``localhost``, and ``::1`` are accepted. No ``--allow-public-bind``
  escape hatch (auth is v4).
* **D-09** — Pass an explicit ``security_settings`` to the SDK's
  :class:`StreamableHTTPSessionManager` mirroring the FastMCP
  defaults at ``mcp/server/fastmcp/server.py:177-183``: DNS rebinding
  protection on with the loopback-only ``allowed_hosts`` /
  ``allowed_origins`` lists. The SDK's :class:`FastMCP` auto-enables
  this in its ``__init__``, but the lower-level
  :class:`StreamableHTTPSessionManager` does NOT — so the
  ``run_http`` path wires it explicitly.
* **D-10** — Emit a startup banner naming the bind address, mount
  path, and the no-auth warning.
* **D-12** — Wrap ``OSError`` (``EADDRINUSE``: macOS errno 48 / Linux
  errno 98) at the uvicorn ``serve()`` call site as a
  :class:`PortInUseError` (a :class:`click.ClickException` subclass
  with ``exit_code = 2``).

Phase 52 carry-forward (CONTEXT decision D, layer 1): :func:`run_http`
inherits :func:`agent_brain_mcp.server.run_stdio`'s symmetric
``try / finally`` shape and calls
:meth:`SubscriptionManager.cleanup_all` on every exit path so no
polling task survives a server exit (graceful shutdown, SIGINT,
port-in-use, unhandled exception).

Phase 67 Plan 04 additions (OAUTH-05 / OAUTH-08 RS half):
* ``GET /.well-known/jwks.json`` — auth-exempt public JWKS route
  (SDK gap: mcp SDK does NOT ship a JWKS endpoint). Serves the
  process-lifetime RS256 public key as a public-only JWKS document.
* ``create_auth_routes()`` — SDK AS route set (/authorize, /token,
  /register, /.well-known/oauth-authorization-server) added to the
  auth-exempt ``routes=[...]`` list ABOVE the ``/mcp`` Mount.
* ``/authorize`` PKCE front-handler — a thin auth-exempt
  :class:`starlette.routing.Route` that calls
  :func:`agent_brain_mcp.oauth.provider.reject_non_s256_pkce` BEFORE
  delegating to the SDK authorize handler. This is the live PKCE
  S256-only enforcement gate (ROADMAP SC#1). The front-handler Route
  is placed BEFORE the SDK's ``/authorize`` Route in the list so
  Starlette's first-match semantics ensure the pre-check always runs.
* ``RequireAuthMiddleware`` + ``BearerAuthBackend`` — wrap ONLY the
  ``/mcp`` Mount when ``AGENT_BRAIN_AUTH=oauth``. The ``/mcp`` Mount
  is wrapped:
  ``RequireAuthMiddleware(
      AuthenticationMiddleware(mcp_app, BearerAuthBackend(...)),
      required_scopes=[],   # Phase 68 fills this
      resource_metadata_url=<PRM url>)``
  The remaining routes stay auth-exempt.

OASM reconciliation note: Phase 66 ships a hand-rolled OASM handler at
``OASM_PATH``. Phase 67's ``create_auth_routes()`` also emits its own
``/.well-known/oauth-authorization-server`` route. We keep BOTH in the
routes list; Starlette uses first-match, so the Phase 66 hand-rolled
handler wins for ``OASM_PATH`` (consistent Phase 66 document format).
The SDK metadata route is also present as a harmless second entry that
never matches because the first route takes precedence. This keeps the
Phase 66 OASM test green without any changes.
"""

from __future__ import annotations

import contextlib
import json
import logging
import socket
import time
from collections.abc import AsyncIterator, MutableMapping
from typing import Any, Final

import click
import uvicorn
from mcp.server.auth.middleware.bearer_auth import (
    BearerAuthBackend,
    RequireAuthMiddleware,
)
from mcp.server.auth.routes import create_auth_routes
from mcp.server.auth.settings import ClientRegistrationOptions
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from . import config as _config
from . import oauth_metadata as _oauth_metadata
from .oauth.scopes import InsufficientScopeError, require_scope
from .subscriptions import SubscriptionManager
from .tools import TOOL_SCOPE_REQUIREMENTS

logger = logging.getLogger(__name__)

# --- Public constants (load-bearing in tests) -----------------------------

ALLOWED_LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset(
    {"127.0.0.1", "localhost", "::1"}
)
"""Hosts accepted by :func:`validate_loopback_host` (Phase 53 D-08)."""

MCP_MOUNT_PATH: Final[str] = "/mcp"
"""Path the MCP Streamable HTTP transport is mounted at (Phase 53 D-07)."""

HEALTHZ_PATH: Final[str] = "/healthz"
"""Liveness probe path returning ``{"status":"ok","transport":"http"}``."""

SUBSCRIPTIONS_PATH: Final[str] = "/mcp/subscriptions"
"""Debug introspection path for active MCP subscription state (HOUSE-01).

Returns 200 + JSON with ``transport``, ``server_uptime_s``, ``active_count``,
and a ``subscriptions`` array. Each entry has a truncated ``session_id``
(8-char hex), ``uri``, ``cadence_s``, ``started_at``, ``last_notified_at``.

Security model: loopback-only, no token required — same trust model as
``/healthz`` and the existing no-auth banner. This endpoint is intentionally
unauthenticated; auth is deferred to v4 (OAUTH-01).

**stdio transport:** The stdio listener has no HTTP server, so this endpoint
does not exist under stdio mode. Operators needing the debug view must run
the HTTP transport (``agent-brain mcp start --transport http``). No shim is
provided — there is no HTTP listener to mount the route on under stdio.
"""

# OAuth 2.1 well-known discovery paths (Phase 66 Plan 02 — OAUTH-02 / OAUTH-03).
# These routes are AUTH-EXEMPT public endpoints required by the MCP Authorization
# spec (2025-11-25).  They MUST precede any future RequireAuthMiddleware wrap
# (see MOUNT-ORDER CONTRACT comment in build_asgi_app).
PRM_PATH: Final[str] = "/.well-known/oauth-protected-resource"
"""RFC 9728 Protected Resource Metadata discovery path (OAUTH-02)."""

PRM_PATH_SUFFIXED: Final[str] = "/.well-known/oauth-protected-resource/mcp"
"""RFC 9728 resource-path-insertion variant — returns the same PRM document."""

OASM_PATH: Final[str] = "/.well-known/oauth-authorization-server"
"""RFC 8414 Authorization Server Metadata discovery path (OAUTH-03)."""

JWKS_PATH: Final[str] = "/.well-known/jwks.json"
"""JWKS endpoint path — serves the RS256 public key (Phase 67 Plan 04, OAUTH-04).

The MCP SDK does NOT ship a built-in JWKS endpoint — this is a documented
SDK gap (design doc §"SDK Gap: No Built-In JWKS Endpoint"). Phase 67
hand-rolls this auth-exempt route to expose the in-process signing key so
RS-only deployments and Phase 70 split AS/RS clients can fetch the public key.
"""

# 4 agent-brain scopes advertised in PRM/OASM (Phase 66 CONTEXT, locked)
_OAUTH_SCOPES: Final[list[str]] = [
    "agent-brain:read",
    "agent-brain:index",
    "agent-brain:admin",
    "agent-brain:subscribe",
]

# Exact error message wording — pinned by tests.
LOOPBACK_REJECTION_MESSAGE: Final[str] = (
    "--host must be one of {127.0.0.1, localhost, ::1} "
    "(auth is deferred to v4; binding to public interfaces is unsafe in v2)"
)

# DNS-rebinding-protection defaults mirror the FastMCP auto-enable rule at
# ``mcp/server/fastmcp/server.py:177-183`` — same allowed_hosts /
# allowed_origins lists for the loopback case.
_LOOPBACK_ALLOWED_HOSTS: Final[list[str]] = [
    "127.0.0.1:*",
    "localhost:*",
    "[::1]:*",
]
_LOOPBACK_ALLOWED_ORIGINS: Final[list[str]] = [
    "http://127.0.0.1:*",
    "http://localhost:*",
    "http://[::1]:*",
]


class PortInUseError(click.ClickException):
    """Raised when uvicorn cannot bind because the port is already in use.

    Phase 53 D-12 mandates exit code 2 (distinct from Click's default
    exit code 1 used for generic usage errors) so callers — including
    Plan 03's smoke harness — can distinguish "port collision" from
    "bad CLI args" without parsing stderr.
    """

    exit_code = 2


class ScopeEnforcementMiddleware:
    """Pre-dispatch per-tool OAuth scope guard for POST /mcp (Phase 68, design Risk 4).

    Buffers the JSON-RPC request body (handling multi-part ``http.request``
    frames), maps ``method(+params.name)`` to a required scope, reads the
    caller's granted scopes off ``scope["user"].scopes`` (set by the wrapping
    ``AuthenticationMiddleware``), and on insufficient scope emits HTTP 403 +
    ``WWW-Authenticate: Bearer error="insufficient_scope"`` WITHOUT calling the
    downstream app. On sufficient scope (or a non-scoped method) it replays the
    buffered body to the downstream app. Engages only in oauth mode.

    Rationale: the MCP low-level server's ``_handle_request()`` catches every
    handler exception and returns it as a JSON-RPC error inside an HTTP 200
    (mcp/server/lowlevel/server.py ~lines 785-788). An ``InsufficientScopeError``
    raised inside ``call_tool`` / ``read_resource`` / ``get_prompt`` /
    ``handle_subscribe`` therefore NEVER propagates out to an outer ASGI
    middleware — the client would see HTTP 200 + JSON-RPC error, violating
    SC#2/SC#3 which require HTTP 403. The 403 MUST be decided and emitted
    BEFORE the session manager runs.

    Composition contract (Phase 68 LOCKED):
    ``RequireAuthMiddleware(                       # outermost — 401 if no token
        AuthenticationMiddleware(                  # sets scope["user"]
            ScopeEnforcementMiddleware(...),       # INSIDE Auth; sees scope["user"]
            backend=BearerAuthBackend(verifier),
        ),
        required_scopes=[],                        # mount-wide empty; guard is per-tool
        resource_metadata_url=<PRM url>,
    )``
    """

    def __init__(self, app: Any, *, resource_metadata_url: str) -> None:
        """Initialise the middleware.

        Args:
            app: The wrapped ASGI application (the raw ``mcp_asgi_app`` callable).
            resource_metadata_url: The RFC 9728 Protected Resource Metadata URL
                for this server (= ``AGENT_BRAIN_OAUTH_RESOURCE``). Included in
                the ``WWW-Authenticate`` header's ``resource_metadata`` field so
                the client can discover the AS and request a higher scope.
        """
        self.app = app
        self.resource_metadata_url = resource_metadata_url

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI entry point — guard POST /mcp in oauth mode; pass through otherwise.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive callable (request body / events).
            send: The ASGI send callable (response headers / body).
        """
        # Pass through anything that is not an in-oauth-mode POST to /mcp.
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or _config.resolve_auth_mode() != _config.AuthMode.oauth
        ):
            await self.app(scope, receive, send)
            return

        # 1) Buffer the full request body (handle multi-part http.request
        #    frames).  The MCP SDK typically sends a single frame, but the
        #    ASGI spec allows ``more_body=True`` chains from proxies / test
        #    clients.
        body = b""
        more = True
        messages: list[MutableMapping[str, Any]] = []
        while more:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more = message.get("more_body", False)
            elif message["type"] == "http.disconnect":
                more = False

        # 2) Build a replay receive() so the downstream app still sees the
        #    same frames — the body must be consumed by the session manager.
        replay = iter(messages)

        async def replay_receive() -> MutableMapping[str, Any]:
            try:
                return next(replay)
            except StopIteration:
                # After buffered frames are exhausted, defer to the real
                # receive (handles any follow-up events e.g. disconnect).
                return await receive()

        # 3) Decide the required scope from the JSON-RPC body.
        required = self._required_scope(body)
        if required is None:
            # Non-scoped method / unparseable body / unknown tool name →
            # let dispatch handle it (unknown tool → JSON-RPC INVALID_PARAMS,
            # NOT a false 403).
            await self.app(scope, replay_receive, send)
            return

        # 4) Read granted scopes set by AuthenticationMiddleware (BearerAuthBackend
        #    stores the AccessToken on scope["user"]; .scopes is the list of
        #    granted scope strings from the JWT "scope" claim).
        user = scope.get("user")
        granted = list(getattr(user, "scopes", []) or [])

        # 5) Enforce. require_scope raises InsufficientScopeError on failure.
        try:
            require_scope(required, granted)
        except InsufficientScopeError as exc:
            await self._send_403(send, required=exc.required)
            return

        # 6) Sufficient scope → downstream with the replayed body.
        await self.app(scope, replay_receive, send)

    def _required_scope(self, body: bytes) -> str | None:
        """Map a JSON-RPC body to the required scope, or None for non-scoped methods.

        Args:
            body: The raw JSON-RPC request body bytes.

        Returns:
            The required scope string, or ``None`` if no scope check is
            needed (non-scoped method, malformed body, unknown tool name).
        """
        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            return None
        # JSON-RPC batch is a list; scope-check is per the MCP single-request shape.
        if not isinstance(payload, dict):
            return None
        method = payload.get("method")
        params = payload.get("params") or {}
        if method == "tools/call":
            name = params.get("name")
            if not name:
                return None
            # Unknown tool name → None (let dispatch surface INVALID_PARAMS,
            # NOT a false 403 from the guard).
            return TOOL_SCOPE_REQUIREMENTS.get(name)
        if method == "resources/read":
            return "agent-brain:read"
        if method == "resources/subscribe":
            return "agent-brain:subscribe"
        if method == "prompts/get":
            return "agent-brain:read"
        # initialize, tools/list, resources/list, prompts/list, ping,
        # notifications, etc. → no scope check; pass through untouched.
        return None

    async def _send_403(self, send: Send, *, required: str) -> None:
        """Emit an HTTP 403 Forbidden response with the insufficient_scope header.

        Args:
            send: The ASGI send callable.
            required: The scope the token was required to carry. Placed in the
                ``scope`` field of the ``WWW-Authenticate`` header so the client
                knows which scope to request via step-up.
        """
        www = (
            f'Bearer error="insufficient_scope", '
            f'scope="{required}", '
            f'resource_metadata="{self.resource_metadata_url}"'
        )
        payload = json.dumps(
            {
                "error": "insufficient_scope",
                "error_description": f"Required scope: {required}",
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode()),
                    (b"www-authenticate", www.encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})


def loopback_transport_security() -> TransportSecuritySettings:
    """Return the loopback-only DNS-rebinding-protection settings.

    Mirrors the FastMCP auto-enable defaults at
    ``mcp/server/fastmcp/server.py:177-183`` for ``host in
    ("127.0.0.1", "localhost", "::1")``. Exposed at module level so the
    ``test_dns_rebinding.py`` defensive test can build the same
    settings and assert the SDK accepts them without raising.
    """
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(_LOOPBACK_ALLOWED_HOSTS),
        allowed_origins=list(_LOOPBACK_ALLOWED_ORIGINS),
    )


def validate_loopback_host(host: str) -> None:
    """Reject any ``--host`` outside the loopback whitelist (HTTP-02).

    Phase 53 D-08 mandates a hard whitelist with no escape hatch — auth
    is the only acceptable gate for a non-loopback bind, and auth is
    v4 (OAUTH-01).

    Args:
        host: The candidate bind host.

    Raises:
        click.ClickException: with :data:`LOOPBACK_REJECTION_MESSAGE`
            if ``host`` is not in :data:`ALLOWED_LOOPBACK_HOSTS`. The
            exception's default ``exit_code = 1`` is appropriate here:
            this is a usage-error class, distinct from the
            port-in-use case (exit 2 via :class:`PortInUseError`).
    """
    if host not in ALLOWED_LOOPBACK_HOSTS:
        raise click.ClickException(LOOPBACK_REJECTION_MESSAGE)


def build_asgi_app(
    server: Server,
    subscription_manager: SubscriptionManager | None = None,
) -> Starlette:
    """Compose the Starlette ASGI app served by :func:`run_http`.

    Phase 66 Plan 02 additions (OAUTH-02 / OAUTH-03):
    * ``GET /.well-known/oauth-protected-resource`` → RFC 9728 PRM JSON
    * ``GET /.well-known/oauth-protected-resource/mcp`` → same PRM document
      (RFC 9728 resource-path-insertion variant)
    * ``GET /.well-known/oauth-authorization-server`` → RFC 8414 OASM JSON

    Layout:

    * ``GET /healthz`` → JSON ``{"status": "ok", "transport": "http"}``
      (D-07 probe — operators curl-check without driving the MCP
      handshake).
    * ``GET /mcp/subscriptions`` → JSON describing active subscription
      state (HOUSE-01 debug endpoint). No token required; loopback-only.
      Reports ``active_count 0`` and empty ``subscriptions`` when
      ``subscription_manager`` is ``None`` (backward-compat default).
    * ``GET /.well-known/oauth-*`` → public OAuth discovery documents
      (auth-exempt; mounted ABOVE /mcp per mount-order contract).
    * ``/mcp`` (Mount) → MCP SDK's
      :class:`StreamableHTTPSessionManager.handle_request` (raw ASGI
      callable; Mount routes any sub-path including the bare ``/mcp``
      to the handler). Must be registered AFTER the specific
      ``/mcp/subscriptions`` Route so Starlette matches the Route first.

    The session manager's lifecycle is bound to Starlette's lifespan
    so the MCP session task group is created/torn-down with the ASGI
    server. This is the same shape FastMCP uses at
    ``mcp/server/fastmcp/server.py:1044`` for its own streamable HTTP
    app.

    The session manager is given an explicit ``security_settings``
    blob — D-09. The bare-bones :class:`StreamableHTTPSessionManager`
    does NOT auto-enable DNS rebinding protection (only
    :class:`FastMCP` does, in its own ``__init__``), so the
    ``run_http`` path wires it here.

    Phase 66 startup gate: :func:`agent_brain_mcp.config.check_auth_startup_gate`
    is called at the TOP of this function so invalid ``AGENT_BRAIN_AUTH``
    or oauth-mode missing ``AGENT_BRAIN_OAUTH_RESOURCE`` exits code 2 at
    app-build time rather than silently producing a broken app.

    Args:
        server: The configured low-level MCP :class:`Server` from
            :func:`agent_brain_mcp.server.build_server`.
        subscription_manager: The :class:`SubscriptionManager` paired
            with ``server``. When provided, ``GET /mcp/subscriptions``
            reads its :meth:`~SubscriptionManager.snapshot` for
            live data. Defaults to ``None`` for backward compatibility
            with callers that build the ASGI app without a manager.

    Returns:
        A Starlette ``ASGI`` app suitable for ``uvicorn.Server(
        uvicorn.Config(app, ...))``.
    """
    # Capture a monotonic timestamp at app-build time so server_uptime_s
    # reflects time since the ASGI app was composed (a proxy for server
    # start time that is always available without global state).
    started_monotonic = time.monotonic()

    # --- Phase 66 startup gate (OAUTH-09 / Plan 01) -------------------------
    # Validate AGENT_BRAIN_AUTH + AGENT_BRAIN_OAUTH_RESOURCE BEFORE building
    # any routes. On misconfiguration this calls sys.exit(2) — the app never
    # reaches the route-construction block below.
    _config.check_auth_startup_gate()

    mcp_session_manager = StreamableHTTPSessionManager(
        app=server,
        event_store=None,
        json_response=False,
        stateless=False,
        security_settings=loopback_transport_security(),
    )

    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "transport": "http"})

    async def subscriptions_debug(_request: Request) -> JSONResponse:
        """Return a JSON-serializable snapshot of active subscriptions.

        No auth required — loopback-only, same trust model as ``/healthz``.
        Does NOT exist under stdio transport (no HTTP listener there).
        """
        snap = (
            subscription_manager.snapshot()
            if subscription_manager is not None
            else {"active_count": 0, "subscriptions": []}
        )
        return JSONResponse(
            {
                "transport": "http",
                "server_uptime_s": time.monotonic() - started_monotonic,
                "active_count": snap["active_count"],
                "subscriptions": snap["subscriptions"],
            }
        )

    async def oauth_protected_resource(request: Request) -> JSONResponse:
        """Serve RFC 9728 PRM document (auth-exempt — discovery-first contract).

        Returns the Protected Resource Metadata document for this MCP server.
        The document is live in ALL auth modes (none/basic/oauth) so that
        compliant MCP clients can always discover the resource's capabilities.

        When AGENT_BRAIN_OAUTH_RESOURCE is unset (none/basic mode), the
        resource field falls back to the request's own base URL so the
        document remains well-formed and the route returns 200.
        """
        resource_env, issuer_env = _config.resolve_oauth_settings()
        base_url = str(request.base_url).rstrip("/")
        resource = resource_env or base_url
        auth_servers = [issuer_env or base_url]
        doc = _oauth_metadata.build_prm_document(
            resource=resource,
            authorization_servers=auth_servers,
        )
        return JSONResponse(doc)

    async def oauth_authorization_server(request: Request) -> JSONResponse:
        """Serve RFC 8414 OASM document (auth-exempt — discovery-first contract).

        Returns the Authorization Server Metadata document. When
        AGENT_BRAIN_OAUTH_ISSUER is unset (co-located AS+RS shape), the
        issuer falls back to the MCP server's own base URL.

        NOTE: The OASM advertises forward-reference endpoint URIs for
        /authorize, /token, /register, and /.well-known/jwks.json — routes
        Phase 67 adds. The document is RFC 8414-valid even while those
        endpoints do not yet resolve (Phase 66 scope boundary).

        OASM reconciliation (Phase 67): create_auth_routes() also emits its
        own /.well-known/oauth-authorization-server route. We keep the Phase 66
        hand-rolled handler FIRST in the routes list so Starlette's first-match
        semantics serve the consistent Phase 66 document format. The SDK's
        metadata route is also present but never matches this path.
        """
        _, issuer_env = _config.resolve_oauth_settings()
        base_url = str(request.base_url).rstrip("/")
        issuer = issuer_env or base_url
        doc = _oauth_metadata.build_oasm_document(
            issuer=issuer,
            base_url=base_url,
        )
        return JSONResponse(doc)

    async def jwks_document(_request: Request) -> JSONResponse:
        """Serve the RS256 public JWKS document (auth-exempt, Phase 67 OAUTH-04).

        The MCP SDK does NOT ship a built-in JWKS endpoint (documented SDK gap).
        This hand-rolled route exposes the process-lifetime RS256 public key so:
        1. The OASM ``jwks_uri`` forward-reference resolves (Phase 66/67 contract).
        2. The Resource Server verifier and Phase 70 remote JwksTokenVerifier can
           fetch the public key.

        SECURITY: serves a PUBLIC-ONLY JWKS document (no private key material).
        The SigningKey.jwks_dict is pre-computed at startup with only n/e fields.
        """
        from agent_brain_mcp.oauth.keys import get_or_create_signing_key

        sk = get_or_create_signing_key()
        return JSONResponse(sk.jwks_dict)

    async def mcp_asgi_app(scope: Scope, receive: Receive, send: Send) -> None:
        # Thin wrapper around the raw-ASGI callable on the session
        # manager. ``Mount(..., app=callable)`` accepts any ASGI3
        # callable; FastMCP wraps this in a small class
        # (StreamableHTTPASGIApp) — we keep it as a module-level
        # function for testability.
        await mcp_session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        # ``mcp_session_manager.run()`` is the SDK's documented lifespan
        # contract (see its docstring): create the task group on
        # entry, drain it on exit. The manager can only be run once
        # per instance — fine for our single-process listener.
        # ``@asynccontextmanager`` wraps the async generator so
        # Starlette's lifespan kwarg accepts it as an
        # ``AsyncContextManager`` per its type signature.
        async with mcp_session_manager.run():
            yield

    # --- Build the auth-exempt routes list (MOUNT-ORDER CONTRACT) ----------
    # MOUNT-ORDER CONTRACT (design doc Risk 3):
    # well-known + healthz + AS routes are AUTH-EXEMPT and MUST precede
    # any RequireAuthMiddleware wrap (Phase 67 / OAUTH-05). Reversing this
    # deadlocks the OAuth dance — a client asking
    # /.well-known/oauth-protected-resource would itself need a token it
    # cannot yet obtain.
    #
    # Phase 67 additions — still auth-exempt, before the /mcp Mount:
    #   1. JWKS_PATH route (SDK gap workaround)
    #   2. /authorize PKCE pre-check front-handler (ROADMAP SC#1)
    #   3. create_auth_routes() SDK set (authorize/token/register/oasm)
    #
    # The /authorize front-handler MUST be placed BEFORE create_auth_routes()
    # in the list so Starlette's first-match semantics ensure the PKCE
    # pre-check runs before the SDK's own authorize handler for every request.
    # Approach: front-route-first (Route("/authorize", precheck, ...) before
    # the SDK Route("/authorize", sdk_handler, ...)).

    auth_mode = _config.resolve_auth_mode()
    resource_env, issuer_env = _config.resolve_oauth_settings()

    exempt_routes: list[Any] = [
        Route(HEALTHZ_PATH, healthz, methods=["GET"]),
        # Phase 64 (HOUSE-01): /mcp/subscriptions debug endpoint. Auth-exempt,
        # loopback-only. MUST be registered BEFORE the greedy /mcp Mount (appended
        # last) so Starlette first-match serves the specific Route, not the Mount.
        Route(SUBSCRIPTIONS_PATH, subscriptions_debug, methods=["GET"]),
        # Phase 66 OASM hand-rolled handler — MUST precede create_auth_routes()
        # output because Starlette first-match wins. This preserves the Phase 66
        # document format and keeps test_well_known_routes.py green.
        Route(OASM_PATH, oauth_authorization_server, methods=["GET"]),
        Route(PRM_PATH, oauth_protected_resource, methods=["GET"]),
        Route(PRM_PATH_SUFFIXED, oauth_protected_resource, methods=["GET"]),
        # Phase 67: JWKS public key route (auth-exempt, SDK gap)
        Route(JWKS_PATH, jwks_document, methods=["GET"]),
    ]

    if auth_mode is _config.AuthMode.oauth and resource_env:
        # Resolve issuer: env var or fall back to resource base URL
        from urllib.parse import urlparse

        parsed = urlparse(resource_env)
        base_url_from_resource = (
            f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else resource_env
        )
        issuer: str = issuer_env or base_url_from_resource

        # Build the provider + SDK AS routes
        from agent_brain_mcp.oauth.keys import get_or_create_signing_key
        from agent_brain_mcp.oauth.provider import (
            AgentBrainAuthServerProvider,
            reject_non_s256_pkce,
        )
        from agent_brain_mcp.oauth.tokens import token_store

        sk = get_or_create_signing_key()
        provider = AgentBrainAuthServerProvider(
            signing_key=sk,
            store=token_store,
            issuer=issuer,
            resource=resource_env,
        )
        sdk_auth_routes = create_auth_routes(
            provider=provider,
            issuer_url=AnyHttpUrl(issuer),
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=list(_OAUTH_SCOPES),
                default_scopes=["agent-brain:read"],
            ),
        )

        # Extract the SDK's /authorize handler so the pre-check can delegate
        # to it. The SDK route list order is: oasm, /authorize, /token,
        # /register. Find by path attribute.
        sdk_authorize_handler: Any = None
        for sdk_route in sdk_auth_routes:
            if getattr(sdk_route, "path", None) == "/authorize":
                sdk_authorize_handler = sdk_route.endpoint
                break

        async def authorize_pkce_precheck(request: Request) -> Any:
            """Auth-exempt /authorize PKCE front-handler (ROADMAP SC#1).

            Calls reject_non_s256_pkce(request.query_params) BEFORE delegating
            to the SDK authorize handler. This is the live PKCE S256-only gate
            (plan §"pkce_live_wiring_note").

            For GET requests the PKCE params are in query_params.
            For POST requests the SDK reads params from the query string too
            (the /authorize endpoint uses GET redirects per OAuth 2.1).

            Return behaviour:
            - plain / method-absent / challenge-absent → 400 invalid_request
            - valid S256 → pass through to the SDK authorize handler
            """
            from mcp.server.auth.provider import AuthorizeError

            try:
                reject_non_s256_pkce(request.query_params)
            except AuthorizeError as exc:
                # Return the exact error body the plan requires
                return JSONResponse(
                    {
                        "error": exc.error,
                        "error_description": exc.error_description or "",
                    },
                    status_code=400,
                )

            # Valid S256 — delegate to the SDK authorize handler
            if sdk_authorize_handler is not None:
                return await sdk_authorize_handler(request)
            # Fallback if SDK handler not found (should not happen)
            return JSONResponse(
                {"error": "server_error", "error_description": "AS unavailable"},
                status_code=500,
            )

        # /authorize PKCE pre-check front-handler MUST precede the SDK route
        # so first-match picks up the pre-check for ALL /authorize requests.
        exempt_routes.append(
            Route("/authorize", authorize_pkce_precheck, methods=["GET", "POST"])
        )
        # Add the remaining SDK AS routes (token, register, SDK's oasm)
        # The SDK's /authorize route is now shadowed by the front-handler above.
        exempt_routes.extend(sdk_auth_routes)

        # Build the /mcp mount wrapped with auth middleware
        # Composition (inside-out):
        #   1. mcp_asgi_app — the raw MCP session handler
        #   2. AuthenticationMiddleware(backend=BearerAuthBackend) — sets
        #      scope["user"] = AuthenticatedUser when token is valid
        #   3. RequireAuthMiddleware — checks scope["user"] is AuthenticatedUser,
        #      returns 401+WWW-Authenticate if not.
        # required_scopes=[] in Phase 67 — scope enforcement is Phase 68.
        from agent_brain_mcp.oauth.verifier import build_local_verifier

        prm_url_str = resource_env  # PRM URL is the resource URI per RFC 9728
        verifier = build_local_verifier(issuer_override=issuer)
        backend = BearerAuthBackend(token_verifier=verifier)
        # Phase 68 Plan 02 (deviation fix — Rule 1 Auto-Fix):
        # The plan's LOCKED composition had RequireAuthMiddleware OUTSIDE
        # AuthenticationMiddleware, but Starlette ASGI middleware runs
        # outer-first: RequireAuthMiddleware would always see scope["user"]
        # as None (before AuthenticationMiddleware sets it) and return 401
        # for every request including valid tokens.
        #
        # CORRECT ordering (matching the MCP SDK's FastMCP pattern at
        # mcp/server/fastmcp/server.py ~lines 860-914):
        #   AuthenticationMiddleware  ← outermost; runs first; sets scope["user"]
        #     RequireAuthMiddleware   ← 401 if not AuthenticatedUser
        #       ScopeEnforcementMiddleware  ← 403 on insufficient scope
        #         mcp_asgi_app             ← session manager
        auth_mcp_app = AuthenticationMiddleware(
            RequireAuthMiddleware(
                ScopeEnforcementMiddleware(
                    mcp_asgi_app,
                    resource_metadata_url=prm_url_str,
                ),
                required_scopes=[],  # mount-wide empty; per-tool scope = guard
                resource_metadata_url=AnyHttpUrl(prm_url_str),
            ),
            backend=backend,
        )
        mcp_mount: Any = Mount(MCP_MOUNT_PATH, app=auth_mcp_app)
    else:
        # none / basic modes — /mcp mount is unwrapped (behavior unchanged)
        mcp_mount = Mount(MCP_MOUNT_PATH, app=mcp_asgi_app)

    exempt_routes.append(mcp_mount)

    return Starlette(
        routes=exempt_routes,
        lifespan=lifespan,
    )


def _probe_port_available(host: str, port: int) -> None:
    """Raise :class:`PortInUseError` if ``(host, port)`` is already bound.

    Uvicorn's :meth:`uvicorn.Server.serve` catches ``OSError`` on
    ``loop.create_server`` and calls :func:`sys.exit(1)` rather than
    propagating — that swallows the errno information AND short-
    circuits our ``finally`` block before it can run the subscription
    cleanup hook. By probing the port ourselves BEFORE handing off to
    uvicorn we get a clean :class:`PortInUseError` with the right
    ``exit_code`` AND the cleanup hook runs symmetrically.

    The probe binds-and-closes a one-shot socket. There IS a TOCTOU
    window between the close here and uvicorn's bind, but it's
    measured in microseconds. The production failure mode if a process
    steals the port in that window is a clean :class:`SystemExit(1)`
    from uvicorn — still no silent fallback, just a slightly noisier
    error than the clean Plan 02 path.

    Args:
        host: The bind host (already loopback-validated).
        port: The TCP port.

    Raises:
        PortInUseError: if the port is already in use (errno 48 on
            macOS / errno 98 on Linux). Exit code 2 per D-12.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((host, port))
    except OSError as e:
        if e.errno in (48, 98):
            raise PortInUseError(
                f"Port {port} already in use. Pass --port <free-port> "
                "or stop the conflicting process."
            ) from e
        # Anything else: surface verbatim so the operator sees the
        # real bind failure mode. No silent mapping.
        raise


def build_uvicorn_server(app: Starlette, *, host: str, port: int) -> uvicorn.Server:
    """Build the in-process uvicorn server wrapping ``app``.

    Factored out of :func:`run_http` so the listener tests can
    introspect the bound socket via
    ``uvicorn.Server.servers[0].sockets`` without driving the
    full ``serve()`` lifecycle.

    Args:
        app: The Starlette ASGI app from :func:`build_asgi_app`.
        host: Loopback host (already validated).
        port: TCP port (already validated by Click's
            :class:`click.IntRange`).

    Returns:
        Configured but not-yet-started :class:`uvicorn.Server`.
    """
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        lifespan="on",
        # Silence access logs by default — the MCP SDK already emits
        # request-level logging, and uvicorn access logs duplicate
        # every healthz probe noisily.
        access_log=False,
    )
    return uvicorn.Server(config)


async def run_http(
    server: Server,
    subscription_manager: SubscriptionManager,
    *,
    host: str,
    port: int,
) -> None:
    """Serve the MCP server over Streamable HTTP on ``host:port``.

    This is Plan 02's replacement for Plan 01's
    :class:`NotImplementedError` stub.

    Lifecycle:

    1. Validate ``host`` against the loopback whitelist (D-08). A
       rejection here raises BEFORE any socket bind — verified by
       ``test_http_listener.py::test_invalid_host_validated_before_bind``.
    2. Build the Starlette app + the in-process uvicorn server.
    3. Log the startup banner (D-10) so operators see the no-auth
       warning in both stdout and aggregated log shippers.
    4. ``await server.serve()``. On ``EADDRINUSE`` (macOS errno 48 /
       Linux errno 98) catch and re-raise as :class:`PortInUseError`
       with the contract message (D-12). Any other ``OSError``
       propagates verbatim — failures other than port collision are
       not silently mapped.
    5. In ``finally``, drain polling tasks via
       :meth:`SubscriptionManager.cleanup_all`. Mirrors
       :func:`agent_brain_mcp.server.run_stdio`'s try/finally shape so
       no polling task survives an HTTP server exit (graceful
       shutdown, SIGINT, port-in-use, mid-loop exception). Phase 52
       CONTEXT decision D, layer 1 — extended verbatim to the HTTP
       transport per the v2 design doc §3.3.1.

    Args:
        server: The configured low-level MCP :class:`Server` from
            :func:`agent_brain_mcp.server.build_server`.
        subscription_manager: The :class:`SubscriptionManager` paired
            with ``server`` (second tuple element of ``build_server``).
            Cleaned up on every exit path.
        host: Loopback host — one of ``127.0.0.1`` / ``localhost`` /
            ``::1`` per D-08.
        port: TCP port to bind. Click's :class:`click.IntRange(1,
            65535)` validates this at the CLI layer.

    Raises:
        click.ClickException: if ``host`` is not loopback
            (:data:`LOOPBACK_REJECTION_MESSAGE`, exit code 1).
        PortInUseError: if the port is already in use (exit code 2).
        OSError: any other low-level bind failure (propagated
            verbatim — no silent fallback).
    """
    validate_loopback_host(host)

    # Pre-flight port check. Uvicorn's ``serve()`` catches OSError on
    # bind and calls ``sys.exit(1)`` (see uvicorn/server.py:169-172),
    # which swallows the errno AND short-circuits our finally block
    # (SystemExit propagates upward before subscription_manager.cleanup_all
    # runs). By probing the port ourselves first we get a clean
    # PortInUseError + the finally block always fires.
    try:
        _probe_port_available(host, port)
    except PortInUseError:
        # Run the cleanup hook even though we never reached uvicorn
        # — symmetry matters: callers expect the manager state to be
        # quiescent after run_http returns/raises, regardless of how
        # far execution got.
        subscription_manager.cleanup_all()
        raise

    app = build_asgi_app(server, subscription_manager)
    uvi_server = build_uvicorn_server(app, host=host, port=port)

    # Banner per D-10. Format string is pinned by the acceptance
    # criteria — operators (and the grep-in-logs verification step)
    # rely on the literal substring "loopback only, no auth".
    logger.info(
        "MCP server listening on http://%s:%d%s (loopback only, no auth "
        "— do NOT expose this port)",
        host,
        port,
        MCP_MOUNT_PATH,
    )

    try:
        await uvi_server.serve()
    except OSError as e:
        # Defense-in-depth: in the extreme TOCTOU case where another
        # process grabs the port between _probe_port_available and
        # uvicorn's own bind, uvicorn raises SystemExit(1) (NOT
        # OSError) — but this branch catches the case where uvicorn's
        # behavior changes upstream and starts propagating OSError
        # directly.
        if e.errno in (48, 98):
            raise PortInUseError(
                f"Port {port} already in use. Pass --port <free-port> "
                "or stop the conflicting process."
            ) from e
        raise
    finally:
        cleaned = subscription_manager.cleanup_all()
        if cleaned:
            logger.info(
                "subscription cleanup: cancelled %d polling task(s) on "
                "HTTP server exit",
                cleaned,
            )


# Re-export hook for ``agent_brain_mcp.server.run_http``. The
# ``Any`` annotation here is a no-op — the real names are visible
# above. Kept so ``from agent_brain_mcp.http import *`` advertises
# the public surface deterministically.
# Phase 53 Plan 03: alias ``_probe_port_available`` as a public name so
# the CLI (which hoists the probe earlier to dodge ``BackendUnavailable``
# masking real misconfigurations) doesn't import the underscore-prefixed
# name. The Plan 02 implementation keeps the leading-underscore name
# in this module for in-process callers; this alias is the cross-module
# public surface.
probe_port_available = _probe_port_available


__all__: list[str] = [
    "ALLOWED_LOOPBACK_HOSTS",
    "HEALTHZ_PATH",
    "JWKS_PATH",
    "LOOPBACK_REJECTION_MESSAGE",
    "MCP_MOUNT_PATH",
    "OASM_PATH",
    "PRM_PATH",
    "PRM_PATH_SUFFIXED",
    "SUBSCRIPTIONS_PATH",
    "PortInUseError",
    "ScopeEnforcementMiddleware",
    "build_asgi_app",
    "build_uvicorn_server",
    "loopback_transport_security",
    "probe_port_available",
    "run_http",
    "validate_loopback_host",
]

# Silence unused-import warnings for ``Any`` — kept in the import
# block so future typed helpers have it without re-importing.
_ = Any
