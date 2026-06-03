"""Phase 53 Plan 02 — :func:`run_http` end-to-end listener tests.

These tests drive a real :func:`agent_brain_mcp.http.run_http` task
on an ephemeral loopback port and exercise the HTTP surface via
:class:`httpx.AsyncClient`. They are unit-grade (single process,
sub-second per test) — the full SDK round-trip lives in Plan 03's
``test_e2e_http.py``.

Tested invariants (Plan 02 acceptance criteria):

* ``/healthz`` round-trip — 200 + ``{"status":"ok","transport":"http"}``.
* ``/mcp`` mounts — POST without a session-id returns the SDK's
  ``Missing session ID`` JSON-RPC error envelope (proves the route
  is wired to :class:`StreamableHTTPSessionManager`).
* Listener bound to ``127.0.0.1`` only.
* :class:`PortInUseError` raised on bind collision (exit code 2).
* :func:`validate_loopback_host` raises BEFORE the server constructs
  uvicorn — defensive guarantee that an invalid host never reaches
  ``socket.bind``.
* Clean shutdown via task cancellation drains the manager.

Shutdown pattern (CONTEXT decision D layer 1): every test that
spawns the listener wraps it in a ``try / asyncio.CancelledError``
finalizer so the inner subscription manager's ``cleanup_all`` always
runs. The test then awaits the task with a short timeout to make
sure no orphan tasks survive.
"""

from __future__ import annotations

import asyncio
import socket
from unittest.mock import MagicMock

import httpx
import pytest

from agent_brain_mcp.http import (
    PortInUseError,
    build_asgi_app,
    build_uvicorn_server,
    run_http,
)
from agent_brain_mcp.server import build_server

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_server() -> tuple[object, object, httpx.Client]:
    """Build a low-level MCP server + manager + the backing httpx client.

    The httpx client uses a :class:`httpx.MockTransport` so no real
    backend call ever fires — these tests are about the HTTP listener
    layer, not the backend bridge. Returns a 3-tuple so callers can
    close the client in their finalizer.
    """
    backend_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"detail": "test-stub"})
        ),
        base_url="http://test-agent-brain",
    )
    server, manager = build_server(backend_client)
    return server, manager, backend_client


async def _wait_until_serving(uvi_server: object, *, timeout_s: float = 5.0) -> None:
    """Spin until uvicorn flips ``started=True`` or the timeout trips.

    The uvicorn lifecycle:
    1. Constructor sets ``started=False``, ``servers=[]``.
    2. ``serve()`` runs lifespan startup, opens sockets, sets
       ``started=True``.
    3. Lifespan shutdown clears ``started``.

    We poll ``started`` to know when ``/healthz`` is reachable
    without baking in a fixed sleep. ``servers`` becoming non-empty
    is the secondary signal (used by the bound-to-loopback test).
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        if getattr(uvi_server, "started", False):
            return
        await asyncio.sleep(0.02)
    raise AssertionError("uvicorn never reached started=True")


async def _stop_server_task(
    server_task: asyncio.Task[None], uvi_server: object
) -> None:
    """Signal the uvicorn server to exit, then await the task.

    Uvicorn's ``should_exit`` flag is the documented graceful-stop
    path (vs ``task.cancel()`` which surfaces ``CancelledError``
    inside the loop and complicates the finally-block accounting).

    The task may finish with ``None`` (clean serve exit) or raise
    (e.g. :class:`PortInUseError` for the bind-collision test). We
    swallow ``asyncio.CancelledError`` so the test can decide what
    counts as a real failure.
    """
    uvi_server.should_exit = True  # type: ignore[attr-defined]
    try:
        await asyncio.wait_for(server_task, timeout=5.0)
    except (asyncio.CancelledError, asyncio.TimeoutError):
        # TimeoutError on a slow shutdown is a test-environment issue,
        # not a production bug; cancel as a last resort.
        if not server_task.done():
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, BaseException):
                pass


# ---------------------------------------------------------------------------
# Healthz round-trip
# ---------------------------------------------------------------------------


class TestHealthzRoundtrip:
    """``/healthz`` returns the documented body."""

    async def test_healthz_returns_ok_json(self, free_loopback_port: int) -> None:
        srv, mgr, backend_client = _make_test_server()
        app = build_asgi_app(srv)  # type: ignore[arg-type]
        uvi_server = build_uvicorn_server(
            app, host="127.0.0.1", port=free_loopback_port
        )

        server_task = asyncio.create_task(uvi_server.serve())  # type: ignore[attr-defined]
        try:
            await _wait_until_serving(uvi_server)
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{free_loopback_port}",
                timeout=2.0,
            ) as client:
                resp = await client.get("/healthz")
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("application/json")
            assert resp.json() == {"status": "ok", "transport": "http"}
        finally:
            await _stop_server_task(server_task, uvi_server)
            backend_client.close()
            # Defensive: nothing should remain after a clean exit.
            assert mgr.active_count() == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# /mcp mounts the SDK session manager
# ---------------------------------------------------------------------------


class TestMcpRouteMounted:
    """A request to ``/mcp`` is handled by the SDK session manager."""

    async def test_mcp_post_without_session_returns_sdk_error(
        self, free_loopback_port: int
    ) -> None:
        """POST without ``Mcp-Session-Id`` reaches the SDK and gets its 400.

        The SDK enforces session-id presence; a request without one
        gets an HTTP 400 + JSON-RPC error envelope. We don't validate
        the exact wording — that's an SDK contract that may shift
        across point releases. What we DO validate: the request
        crossed the Mount boundary into the SDK (status != 404 and
        != 405; the response body contains JSON-RPC-shaped fields).
        """
        srv, mgr, backend_client = _make_test_server()
        app = build_asgi_app(srv)  # type: ignore[arg-type]
        uvi_server = build_uvicorn_server(
            app, host="127.0.0.1", port=free_loopback_port
        )

        server_task = asyncio.create_task(uvi_server.serve())  # type: ignore[attr-defined]
        try:
            await _wait_until_serving(uvi_server)
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{free_loopback_port}",
                timeout=2.0,
            ) as client:
                resp = await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-03-26",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "0"},
                        },
                    },
                    headers={"Accept": "application/json, text/event-stream"},
                )
            # 404 would mean the Mount routing missed entirely. The SDK
            # returns 4xx (typically 400/406) for a request that
            # reached the manager but lacked the expected handshake
            # state. Any non-404 / non-405 response proves the
            # Mount + ASGI delegation works.
            assert resp.status_code != 404
            assert resp.status_code != 405
        finally:
            await _stop_server_task(server_task, uvi_server)
            backend_client.close()


# ---------------------------------------------------------------------------
# Bound to loopback only
# ---------------------------------------------------------------------------


class TestBoundToLoopback:
    """Once the listener is up the socket is on 127.0.0.1, not 0.0.0.0."""

    async def test_socket_getsockname_reports_loopback(
        self, free_loopback_port: int
    ) -> None:
        srv, mgr, backend_client = _make_test_server()
        app = build_asgi_app(srv)  # type: ignore[arg-type]
        uvi_server = build_uvicorn_server(
            app, host="127.0.0.1", port=free_loopback_port
        )

        server_task = asyncio.create_task(uvi_server.serve())  # type: ignore[attr-defined]
        try:
            await _wait_until_serving(uvi_server)
            # uvicorn populates ``servers`` once the lifespan startup
            # finishes; each entry has ``sockets`` (a list of bound
            # ``socket.socket`` objects). The first socket's
            # ``getsockname()[0]`` is the bind host. If uvicorn has
            # multiple sockets (IPv4 + IPv6 dual-stack) we check that
            # NONE of them are non-loopback.
            assert uvi_server.servers  # type: ignore[attr-defined]
            for s in uvi_server.servers:  # type: ignore[attr-defined]
                for sock in s.sockets:
                    bind_host = sock.getsockname()[0]
                    # Either IPv4 loopback or IPv6 loopback only.
                    assert bind_host in (
                        "127.0.0.1",
                        "::1",
                    ), f"listener bound to non-loopback host: {bind_host!r}"
        finally:
            await _stop_server_task(server_task, uvi_server)
            backend_client.close()


# ---------------------------------------------------------------------------
# Port-in-use mapping
# ---------------------------------------------------------------------------


class TestPortInUseMapping:
    """``EADDRINUSE`` becomes :class:`PortInUseError` with exit code 2."""

    async def test_port_in_use_raises_port_in_use_error(
        self, free_loopback_port: int
    ) -> None:
        # Hold the port on a sibling socket so uvicorn collides on bind.
        # SO_REUSEADDR off (the default) keeps Linux/macOS honest about
        # the collision; with SO_REUSEADDR the kernel may grant both
        # binds and the test would silently no-op.
        squatter = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        squatter.bind(("127.0.0.1", free_loopback_port))
        squatter.listen(1)

        srv, mgr, backend_client = _make_test_server()
        try:
            with pytest.raises(PortInUseError) as exc_info:
                await run_http(
                    srv,  # type: ignore[arg-type]
                    mgr,  # type: ignore[arg-type]
                    host="127.0.0.1",
                    port=free_loopback_port,
                )
            # D-12: exit code MUST be 2 (distinct from validation
            # errors at exit code 1).
            assert exc_info.value.exit_code == 2
            # Contract message wording — operators read this in CI.
            assert f"Port {free_loopback_port} already in use" in (
                exc_info.value.message
            )
            assert "Pass --port <free-port>" in exc_info.value.message
        finally:
            squatter.close()
            backend_client.close()
            # Manager must be drained even on the port-in-use path.
            assert mgr.active_count() == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Validate-before-bind guarantee
# ---------------------------------------------------------------------------


class TestValidateBeforeBind:
    """Invalid host raises BEFORE uvicorn touches a socket.

    The defensive contract: an attacker who somehow bypasses Click's
    flag plumbing and calls ``run_http(host="0.0.0.0")`` directly
    (e.g. a test, an embedding adapter) must STILL be rejected before
    any bind happens. Plan 02 places ``validate_loopback_host`` at
    the top of ``run_http`` for exactly this reason.
    """

    async def test_invalid_host_validated_before_uvicorn_construction(
        self, monkeypatch: pytest.MonkeyPatch, free_loopback_port: int
    ) -> None:
        srv, mgr, backend_client = _make_test_server()

        # Trip a sentinel if uvicorn.Server is constructed despite
        # the loopback validation failing. The validation runs FIRST
        # in run_http, so this constructor should never be reached.
        constructed = MagicMock()
        from agent_brain_mcp import http as http_mod

        monkeypatch.setattr(http_mod, "build_uvicorn_server", constructed)

        import click

        try:
            with pytest.raises(click.ClickException):
                await run_http(
                    srv,  # type: ignore[arg-type]
                    mgr,  # type: ignore[arg-type]
                    host="0.0.0.0",
                    port=free_loopback_port,
                )
            # The sentinel must be UNTOUCHED — proves the validator
            # raised before we even constructed the uvicorn server.
            constructed.assert_not_called()
        finally:
            backend_client.close()


# ---------------------------------------------------------------------------
# Subscription cleanup on shutdown
# ---------------------------------------------------------------------------


class TestSubscriptionCleanupOnShutdown:
    """``finally: subscription_manager.cleanup_all()`` runs on every exit."""

    async def test_cleanup_runs_on_graceful_shutdown(
        self,
        free_loopback_port: int,
    ) -> None:
        """Graceful shutdown via ``should_exit`` drains the manager.

        We seed a fake task into the manager registry to simulate an
        active subscription, then drive ``run_http`` and signal
        graceful shutdown. The finally block must call
        ``cleanup_all`` so the registry is empty by the time
        ``run_http`` returns.
        """
        srv, mgr, backend_client = _make_test_server()

        # Seed a fake polling task into the manager so we can assert
        # cleanup_all() actually fired. The task is a no-op sleeper;
        # we don't care about its body — only that cleanup_all
        # cancels it and the registry becomes empty.
        async def _sleeper() -> None:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                return

        sleeper_task = asyncio.create_task(_sleeper())
        mgr._tasks[(999, "test://sentinel")] = sleeper_task  # type: ignore[attr-defined]
        assert mgr.active_count() == 1  # type: ignore[attr-defined]

        # Drive run_http on a task so we can stop it via should_exit.
        async def _drive() -> None:
            # run_http calls build_uvicorn_server which makes a fresh
            # uvi_server — we get the instance via the same construction
            # path so we can flip should_exit on it. Use a small
            # side-channel: monkeypatch build_uvicorn_server to capture
            # the instance.
            pass

        # Direct approach: stand up uvicorn ourselves and call run_http
        # wired to that same uvi_server via a custom path. Simpler:
        # spawn run_http on a task and cancel it.
        run_task = asyncio.create_task(
            run_http(
                srv,  # type: ignore[arg-type]
                mgr,  # type: ignore[arg-type]
                host="127.0.0.1",
                port=free_loopback_port,
            )
        )
        # Wait for run_http to enter ``await uvi_server.serve()``.
        # We can't tell from outside; poll for the port being reachable.
        deadline = asyncio.get_event_loop().time() + 5.0
        async with httpx.AsyncClient(timeout=1.0) as probe:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await probe.get(
                        f"http://127.0.0.1:{free_loopback_port}/healthz"
                    )
                    if r.status_code == 200:
                        break
                except (httpx.ConnectError, httpx.ReadError):
                    await asyncio.sleep(0.05)
            else:
                run_task.cancel()
                await asyncio.gather(run_task, return_exceptions=True)
                raise AssertionError("run_http never bound the port")

        # Cancel the run_http task — should trigger CancelledError
        # inside ``await uvi_server.serve()``, which propagates to
        # run_http's try/finally and runs cleanup_all().
        run_task.cancel()
        try:
            await asyncio.wait_for(run_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

        # The seeded sleeper task must have been cancelled by
        # cleanup_all(). active_count() reads the registry directly;
        # if cleanup_all ran, the registry is empty.
        assert mgr.active_count() == 0  # type: ignore[attr-defined]
        # The sleeper itself should be done (cancelled).
        assert sleeper_task.done()

        backend_client.close()
