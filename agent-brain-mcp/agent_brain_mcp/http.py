"""Streamable HTTP listener for the MCP server (Phase 53 Plan 02).

This module replaces Plan 01's :func:`run_http` stub with a working
in-process uvicorn server that mounts the MCP SDK's
:class:`mcp.server.streamable_http_manager.StreamableHTTPSessionManager`
at ``/mcp`` and serves a tiny ``/healthz`` probe alongside it.

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
"""

from __future__ import annotations

import contextlib
import logging
import socket
import time
from collections.abc import AsyncIterator
from typing import Any, Final

import click
import uvicorn
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from .subscriptions import SubscriptionManager

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

    Layout:

    * ``GET /healthz`` → JSON ``{"status": "ok", "transport": "http"}``
      (D-07 probe — operators curl-check without driving the MCP
      handshake).
    * ``GET /mcp/subscriptions`` → JSON describing active subscription
      state (HOUSE-01 debug endpoint). No token required; loopback-only.
      Reports ``active_count 0`` and empty ``subscriptions`` when
      ``subscription_manager`` is ``None`` (backward-compat default).
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

    return Starlette(
        routes=[
            Route(HEALTHZ_PATH, healthz, methods=["GET"]),
            # SUBSCRIPTIONS_PATH must be registered BEFORE the /mcp Mount so
            # Starlette matches the specific /mcp/subscriptions Route first
            # (Mounts are greedy sub-path catchers; Routes take priority in
            # list order).
            Route(SUBSCRIPTIONS_PATH, subscriptions_debug, methods=["GET"]),
            Mount(MCP_MOUNT_PATH, app=mcp_asgi_app),
        ],
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
    "LOOPBACK_REJECTION_MESSAGE",
    "MCP_MOUNT_PATH",
    "SUBSCRIPTIONS_PATH",
    "PortInUseError",
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
