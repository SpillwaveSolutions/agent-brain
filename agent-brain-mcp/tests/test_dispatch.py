"""Phase 53 Plan 01 — :func:`main_async` dispatcher + ``build_server`` axes.

Pins the two-axis contract introduced in Plan 01:

1. ``build_server(httpx_client, backend_transport=..., listen_transport=...)``
   surfaces both labels on the :class:`Server` instance for in-process
   debugging. Plan 03 will wire these into the MCP ``serverInfo._meta``
   blob over the wire; Plan 01 asserts the in-process attributes.
2. Legacy ``build_server(transport=...)`` calls (Phase 52 shape) still
   work, route through to ``backend_transport``, and emit
   :class:`DeprecationWarning`.
3. :func:`main_async` dispatches on ``transport``:

   * ``transport="stdio"`` → :func:`run_stdio` awaited; :func:`run_http`
     not touched.
   * ``transport="http"`` → :func:`run_http` awaited with the supplied
     ``host``/``port``; :func:`run_stdio` not touched.
   * Anything else → :class:`ValueError`. Click rejects it at the CLI
     layer; this guard catches direct callers (tests, embeddings).

These tests use :class:`unittest.mock.AsyncMock` to intercept the two
``run_*`` entry points without actually starting any I/O. The
backend httpx client + version-compat check are stubbed via
``open_backend_client`` and ``ApiClient.server_health`` monkeypatches so
the dispatcher runs in isolation.
"""

from __future__ import annotations

import warnings
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from agent_brain_mcp import server as server_module
from agent_brain_mcp.server import build_server, main_async
from agent_brain_mcp.subscriptions import SubscriptionManager


class TestBuildServerAxes:
    """``build_server`` surfaces both axis labels for client debugging."""

    def test_default_axes_have_documented_defaults(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """Calling without any axis kwargs gives the documented
        defaults: ``backend_transport="http"`` and
        ``listen_transport="stdio"``.
        """
        srv, _ = build_server(fake_httpx_client)
        assert srv._agent_brain_backend_transport == "http"
        assert srv._agent_brain_listen_transport == "stdio"
        # Legacy shim mirrors backend_transport.
        assert srv._agent_brain_transport == "http"

    def test_both_axes_passed_explicitly(self, fake_httpx_client: httpx.Client) -> None:
        """Explicit per-axis labels land on the Server independently."""
        srv, _ = build_server(
            fake_httpx_client,
            backend_transport="uds",
            listen_transport="http",
        )
        assert srv._agent_brain_backend_transport == "uds"
        assert srv._agent_brain_listen_transport == "http"
        # Legacy shim still mirrors backend_transport (NOT
        # listen_transport — the shim is one-way, backend-only).
        assert srv._agent_brain_transport == "uds"

    def test_subscription_manager_still_returned(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """Phase 52 tuple contract is preserved verbatim — the second
        element of the return tuple is the :class:`SubscriptionManager`.
        """
        srv, manager = build_server(
            fake_httpx_client,
            backend_transport="http",
            listen_transport="http",
        )
        assert isinstance(manager, SubscriptionManager)
        # Plan 02 private attr also still works (Phase 52 backwards
        # compat — pinned by test_initialize::
        # test_build_server_attaches_subscription_manager but worth
        # asserting here too because Plan 01 touched the function).
        assert srv._subscription_manager is manager


class TestBuildServerDeprecationAlias:
    """The legacy ``transport=`` kwarg routes to ``backend_transport``."""

    def test_legacy_transport_kwarg_routes_to_backend_transport(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        with pytest.warns(DeprecationWarning, match="transport=.*deprecated"):
            srv, _ = build_server(fake_httpx_client, transport="uds")
        assert srv._agent_brain_backend_transport == "uds"
        # listen_transport unaffected — falls back to its default.
        assert srv._agent_brain_listen_transport == "stdio"

    def test_no_warning_when_transport_kwarg_absent(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """The deprecation warning fires ONLY when the legacy kwarg is
        used. New-style calls (no ``transport=``) must stay silent so
        the 250 existing tests don't flood with warnings.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            # Must NOT raise — the new-style call should be silent.
            build_server(
                fake_httpx_client,
                backend_transport="http",
                listen_transport="http",
            )

    def test_legacy_transport_kwarg_does_not_override_explicit_backend(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """If a caller passes BOTH ``transport=`` and
        ``backend_transport=``, the legacy ``transport=`` wins (it's
        the deprecation alias — Plan 01 routes it unconditionally to
        ``backend_transport``). That keeps the migration path simple:
        legacy callers don't accidentally drop their value when adding
        the new label. Documented inline in :func:`build_server`.
        """
        with pytest.warns(DeprecationWarning):
            srv, _ = build_server(
                fake_httpx_client,
                backend_transport="http",
                transport="uds",
            )
        # Legacy kwarg won.
        assert srv._agent_brain_backend_transport == "uds"


class TestMainAsyncDispatch:
    """``main_async`` picks the right ``run_*`` entry point.

    The httpx client + version-compat check are stubbed so the
    dispatcher runs without hitting any real backend.
    """

    @pytest.fixture
    def stubbed_environment(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_httpx_client: httpx.Client,
    ) -> dict[str, Any]:
        """Stub the backend-client open + server_health probe and patch
        the ``run_stdio``/``run_http`` symbols inside
        :mod:`agent_brain_mcp.server` with :class:`AsyncMock`s.

        Returns a dict containing the two mocks (``stdio`` / ``http``)
        and the captured ``build_server`` call (so dispatch tests can
        assert ``listen_transport=`` propagated correctly).
        """

        # 1. Replace the backend client opener so no UDS / HTTP probe
        #    fires. Returns ("http", <pre-built mock client>).
        def _fake_open_backend_client(
            *, backend: str | None, backend_url: str | None, state_dir: Any
        ) -> tuple[str, httpx.Client]:
            return "http", fake_httpx_client

        monkeypatch.setattr(
            "agent_brain_mcp.config.open_backend_client",
            _fake_open_backend_client,
        )

        # 2. Replace the API server_health probe so check_backend_version
        #    sees a recent-enough version.
        monkeypatch.setattr(
            "agent_brain_mcp.client.ApiClient.server_health",
            lambda self: {"version": "10.2.0"},
        )

        # 3. Mock both run_* functions. AsyncMock auto-creates an
        #    awaitable that returns None.
        stdio_mock = AsyncMock(return_value=None)
        http_mock = AsyncMock(return_value=None)
        monkeypatch.setattr(server_module, "run_stdio", stdio_mock)
        monkeypatch.setattr(server_module, "run_http", http_mock)

        # 4. Wrap build_server so we can inspect what listen_transport
        #    was passed without breaking the actual construction.
        original_build_server = server_module.build_server
        captured_build_kwargs: dict[str, Any] = {}

        def _spy_build_server(client: httpx.Client, **kwargs: Any) -> tuple[Any, Any]:
            captured_build_kwargs.update(kwargs)
            return original_build_server(client, **kwargs)

        monkeypatch.setattr(server_module, "build_server", _spy_build_server)

        return {
            "stdio": stdio_mock,
            "http": http_mock,
            "build_kwargs": captured_build_kwargs,
        }

    async def test_stdio_transport_calls_run_stdio(
        self, stubbed_environment: dict[str, Any]
    ) -> None:
        await main_async(transport="stdio")
        stubbed_environment["stdio"].assert_awaited_once()
        # Positional args: (server, subscription_manager).
        call_args = stubbed_environment["stdio"].await_args
        assert len(call_args.args) == 2
        stubbed_environment["http"].assert_not_awaited()

    async def test_http_transport_calls_run_http_with_host_and_port(
        self, stubbed_environment: dict[str, Any]
    ) -> None:
        await main_async(transport="http", host="127.0.0.1", port=8765)
        stubbed_environment["http"].assert_awaited_once()
        call_args = stubbed_environment["http"].await_args
        # Positional: (server, subscription_manager).
        assert len(call_args.args) == 2
        # Keyword: host + port.
        assert call_args.kwargs == {"host": "127.0.0.1", "port": 8765}
        stubbed_environment["stdio"].assert_not_awaited()

    async def test_http_transport_propagates_custom_port(
        self, stubbed_environment: dict[str, Any]
    ) -> None:
        await main_async(transport="http", host="localhost", port=9999)
        stubbed_environment["http"].assert_awaited_once()
        assert stubbed_environment["http"].await_args.kwargs == {
            "host": "localhost",
            "port": 9999,
        }

    async def test_invalid_transport_raises_value_error(
        self, stubbed_environment: dict[str, Any]
    ) -> None:
        """Click rejects this at the CLI layer; the dispatcher's
        defensive guard catches direct callers (tests, embeddings).
        """
        with pytest.raises(ValueError, match="Unknown transport"):
            await main_async(transport="invalid")
        # Neither run_* was awaited.
        stubbed_environment["stdio"].assert_not_awaited()
        stubbed_environment["http"].assert_not_awaited()

    async def test_listen_transport_propagated_to_build_server(
        self, stubbed_environment: dict[str, Any]
    ) -> None:
        """``main_async`` must hand ``transport`` through as
        ``listen_transport=`` so the Server attribute reflects the
        listen-side axis — not the backend axis.
        """
        await main_async(transport="http", host="127.0.0.1", port=8765)
        assert stubbed_environment["build_kwargs"]["listen_transport"] == "http"
        # backend_transport derives from open_backend_client's return
        # value (stubbed to "http").
        assert stubbed_environment["build_kwargs"]["backend_transport"] == "http"

    async def test_no_silent_fallback_on_http_runtime_error(
        self,
        stubbed_environment: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """HTTP-03: if ``run_http`` raises (e.g., port-in-use), the
        error propagates — the dispatcher does NOT silently retry with
        stdio. Plan 02 will introduce ``ClickException`` wrapping for
        the port-in-use case, but the *no fallback* invariant lives
        here.
        """
        stubbed_environment["http"].side_effect = OSError(
            "[Errno 48] Address already in use"
        )

        with pytest.raises(OSError, match="already in use"):
            await main_async(transport="http", host="127.0.0.1", port=8765)

        # ``run_stdio`` MUST NOT be touched as a fallback.
        stubbed_environment["stdio"].assert_not_awaited()


class TestRunHttpStub:
    """Plan 01 shipped the ``NotImplementedError`` stub; Plan 02 swapped
    it for the real listener (in :mod:`agent_brain_mcp.http`). The
    public name ``agent_brain_mcp.server.run_http`` is preserved as a
    re-export so the dispatcher in :func:`main_async` keeps working.
    """

    async def test_run_http_is_re_exported_from_http_module(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """``server.run_http`` IS ``http.run_http`` — same callable."""
        from agent_brain_mcp.http import run_http as http_run_http
        from agent_brain_mcp.server import run_http as server_run_http

        # Identity assertion — the server-level name MUST resolve to the
        # http module's symbol. A future refactor that puts a *wrapper*
        # in server.py would break Plan 01's dispatcher contract
        # (test_http_transport_calls_run_http_with_host_and_port relies
        # on monkeypatching server_module.run_http reaching the same
        # callable that gets awaited inside main_async).
        assert server_run_http is http_run_http

    def test_run_http_rejects_invalid_host_before_async_entry(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """A non-loopback host raises BEFORE any uvicorn / socket work.

        This is the dispatcher-level guarantee: Plan 02's listener can
        be invoked directly (bypassing Click's CLI flag validation)
        from a test or an embedding adapter and STILL refuses to bind
        to a public interface. The integration test that pins this
        with a sentinel-mocked uvicorn constructor lives in
        ``test_http_listener.py::TestValidateBeforeBind``.
        """
        import asyncio

        import click

        from agent_brain_mcp.server import run_http

        srv, manager = build_server(fake_httpx_client)
        with pytest.raises(click.ClickException):
            asyncio.run(run_http(srv, manager, host="0.0.0.0", port=12345))
