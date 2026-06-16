"""Tests for oauth_handlers: redirect_handler + LoopbackCallbackServer.

Phase 69 Plan 02 — TDD suite.

Covers:
- LoopbackCallbackServer binds an OS-assigned (ephemeral) port.
- redirect_uri property returns "http://127.0.0.1:<port>/callback".
- A real GET to the bound port with code+state returns ("code", "state") via
  wait_for_callback() and the response body contains the close-tab message.
- A GET with code but no state returns ("abc123", None).
- build_redirect_handler opens the browser (injectable) + writes URL to stream.
- build_callback_handler wraps wait_for_callback on the given server.
"""

from __future__ import annotations

import asyncio
import io
import threading
import urllib.request
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _do_get(url: str) -> tuple[int, str]:
    """Issue a blocking GET and return (status, body)."""
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read().decode()


def _do_get_in_thread(url: str, results: list[Any]) -> None:
    """Run _do_get in a thread, store result in *results*."""
    try:
        results.append(_do_get(url))
    except Exception as exc:  # pragma: no cover
        results.append(exc)


# ---------------------------------------------------------------------------
# LoopbackCallbackServer – port binding
# ---------------------------------------------------------------------------


class TestLoopbackCallbackServerBinding:
    """Server binds on an OS-assigned port; redirect_uri is deterministic."""

    def test_port_is_nonzero_after_bind(self) -> None:
        from agent_brain_mcp.oauth.oauth_handlers import LoopbackCallbackServer

        with LoopbackCallbackServer() as srv:
            assert srv.port != 0
            assert isinstance(srv.port, int)

    def test_redirect_uri_shape(self) -> None:
        from agent_brain_mcp.oauth.oauth_handlers import LoopbackCallbackServer

        with LoopbackCallbackServer() as srv:
            uri = srv.redirect_uri
            assert uri.startswith("http://127.0.0.1:")
            assert uri.endswith("/callback")
            # Port embedded correctly
            assert str(srv.port) in uri

    def test_custom_host_and_path(self) -> None:
        from agent_brain_mcp.oauth.oauth_handlers import LoopbackCallbackServer

        with LoopbackCallbackServer(host="127.0.0.1", path="/done") as srv:
            assert srv.redirect_uri.endswith("/done")


# ---------------------------------------------------------------------------
# LoopbackCallbackServer – callback capture
# ---------------------------------------------------------------------------


class TestLoopbackCallbackCapture:
    """wait_for_callback() returns (code, state) from a simulated GET."""

    def test_code_and_state_captured(self) -> None:
        from agent_brain_mcp.oauth.oauth_handlers import LoopbackCallbackServer

        with LoopbackCallbackServer() as srv:
            results: list[Any] = []
            # Fire the GET in a background thread so the event loop is free
            t = threading.Thread(
                target=_do_get_in_thread,
                args=(f"{srv.redirect_uri}?code=abc123&state=xyz", results),
            )
            t.start()
            code, state = asyncio.run(srv.wait_for_callback())
            t.join(timeout=5)

        assert code == "abc123"
        assert state == "xyz"
        # HTTP response body must contain the close-tab message
        assert len(results) == 1
        http_status, body = results[0]
        assert http_status == 200
        assert "close" in body.lower() or "authentication" in body.lower()

    def test_no_state_returns_none(self) -> None:
        from agent_brain_mcp.oauth.oauth_handlers import LoopbackCallbackServer

        with LoopbackCallbackServer() as srv:
            results: list[Any] = []
            t = threading.Thread(
                target=_do_get_in_thread,
                args=(f"{srv.redirect_uri}?code=abc123", results),
            )
            t.start()
            code, state = asyncio.run(srv.wait_for_callback())
            t.join(timeout=5)

        assert code == "abc123"
        assert state is None

    def test_missing_code_raises(self) -> None:
        from agent_brain_mcp.oauth.oauth_handlers import LoopbackCallbackServer

        with LoopbackCallbackServer() as srv:
            # GET with no code param
            results: list[Any] = []
            t = threading.Thread(
                target=_do_get_in_thread,
                args=(f"{srv.redirect_uri}?state=xyz", results),
            )
            t.start()
            with pytest.raises(RuntimeError, match="no authorization code"):
                asyncio.run(srv.wait_for_callback())
            t.join(timeout=5)


# ---------------------------------------------------------------------------
# build_redirect_handler
# ---------------------------------------------------------------------------


class TestBuildRedirectHandler:
    """redirect_handler opens browser (injectable) and writes URL to stream."""

    def test_opener_called_once_with_url(self) -> None:
        from agent_brain_mcp.oauth.oauth_handlers import build_redirect_handler

        calls: list[str] = []
        stream = io.StringIO()

        handler = build_redirect_handler(opener=lambda u: calls.append(u) or True, stream=stream)
        asyncio.run(handler("https://example.com/auth"))

        assert calls == ["https://example.com/auth"]

    def test_url_written_to_stream(self) -> None:
        from agent_brain_mcp.oauth.oauth_handlers import build_redirect_handler

        stream = io.StringIO()
        handler = build_redirect_handler(opener=lambda u: True, stream=stream)
        asyncio.run(handler("https://example.com/auth?code=x"))

        output = stream.getvalue()
        assert "https://example.com/auth?code=x" in output

    def test_opener_exception_does_not_propagate(self) -> None:
        """A headless environment with no browser must not crash."""
        from agent_brain_mcp.oauth.oauth_handlers import build_redirect_handler

        def boom(url: str) -> bool:
            raise OSError("no browser")

        stream = io.StringIO()
        handler = build_redirect_handler(opener=boom, stream=stream)
        # Should not raise
        asyncio.run(handler("https://example.com/auth"))
        # URL still written before attempt
        assert "https://example.com/auth" in stream.getvalue()

    def test_default_stream_is_stderr(self) -> None:
        """build_redirect_handler with no args defaults stream to sys.stderr."""
        from agent_brain_mcp.oauth.oauth_handlers import build_redirect_handler
        import sys

        # Just check it's constructable and the closure runs without TypeError
        handler = build_redirect_handler(opener=lambda u: True)
        # Redirect sys.stderr temporarily
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            asyncio.run(handler("https://example.com/test"))
            written = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        assert "https://example.com/test" in written


# ---------------------------------------------------------------------------
# build_callback_handler
# ---------------------------------------------------------------------------


class TestBuildCallbackHandler:
    """build_callback_handler wraps wait_for_callback on the given server."""

    def test_returns_code_and_state(self) -> None:
        from agent_brain_mcp.oauth.oauth_handlers import (
            LoopbackCallbackServer,
            build_callback_handler,
        )

        with LoopbackCallbackServer() as srv:
            handler = build_callback_handler(srv)
            results: list[Any] = []
            t = threading.Thread(
                target=_do_get_in_thread,
                args=(f"{srv.redirect_uri}?code=tok&state=s1", results),
            )
            t.start()
            code, state = asyncio.run(handler())
            t.join(timeout=5)

        assert code == "tok"
        assert state == "s1"


# ---------------------------------------------------------------------------
# __init__.py export surface
# ---------------------------------------------------------------------------


class TestOAuthPackageExports:
    """Verify all three symbols are importable from agent_brain_mcp.oauth."""

    def test_build_redirect_handler_exported(self) -> None:
        from agent_brain_mcp.oauth import build_redirect_handler  # noqa: F401

    def test_loopback_callback_server_exported(self) -> None:
        from agent_brain_mcp.oauth import LoopbackCallbackServer  # noqa: F401

    def test_build_callback_handler_exported(self) -> None:
        from agent_brain_mcp.oauth import build_callback_handler  # noqa: F401

    def test_file_token_storage_still_exported(self) -> None:
        """69-01 export must not be disturbed."""
        from agent_brain_mcp.oauth import FileTokenStorage  # noqa: F401
