"""Phase 3 TDD: ``DocServeClient.from_httpx`` classmethod.

Pins the new construction seam that lets the transport selector pass in a
UDS-backed ``httpx.Client`` without changing any of the existing 13
``DocServeClient`` methods. Plan §4.4, §13.

RED until ``DocServeClient.from_httpx`` lands in
``agent_brain_cli/client/api_client.py``.
"""

from __future__ import annotations

import httpx
import pytest

from agent_brain_cli.client.api_client import DocServeClient


class TestFromHttpxClassmethod:
    """``DocServeClient.from_httpx(client)`` builds a wrapper that
    uses the provided httpx.Client for every request."""

    def test_returns_doc_serve_client_instance(self) -> None:
        client = httpx.Client()
        wrapped = DocServeClient.from_httpx(client)
        assert isinstance(wrapped, DocServeClient)

    def test_uses_provided_httpx_client_for_requests(self) -> None:
        """A MockTransport routed httpx.Client proves the wrapper does not
        construct its own client internally."""
        calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "healthy",
                    "message": "fake",
                    "version": "10.0.7",
                    "timestamp": "2026-01-01T00:00:00Z",
                },
            )

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport, base_url="http://wrapped")
        wrapped = DocServeClient.from_httpx(client)
        with wrapped:
            health = wrapped.health()
        # The provided client (not a fresh one) handled the request.
        assert len(calls) == 1
        assert health.status == "healthy"

    def test_close_closes_provided_client(self) -> None:
        """Context-manager exit must close the same httpx.Client we passed in,
        otherwise the UDS transport leaks file descriptors."""
        client = httpx.Client()
        wrapped = DocServeClient.from_httpx(client)
        with wrapped:
            assert not client.is_closed
        assert client.is_closed

    def test_base_url_honors_provided_client(self) -> None:
        """The wrapper must not override the inner client's base_url —
        for UDS that's ``http://agent-brain``; we must not mangle it."""
        client = httpx.Client(base_url="http://agent-brain")
        wrapped = DocServeClient.from_httpx(client)
        try:
            # Must accept the inner client's URL space.
            assert str(wrapped._client.base_url) in (
                "http://agent-brain",
                "http://agent-brain/",
            )
        finally:
            wrapped.close()

    def test_existing_init_still_works(self) -> None:
        """Backwards compat: the original ``DocServeClient(base_url=...)``
        constructor must keep working unchanged for HTTP callers."""
        c = DocServeClient(base_url="http://127.0.0.1:9000")
        try:
            assert c.base_url == "http://127.0.0.1:9000"
        finally:
            c.close()


class TestFromHttpxErrorMapping:
    """Errors from the inner httpx.Client must still surface as
    ``ConnectionError`` / ``ServerError`` like the existing client."""

    def test_500_raises_server_error(self) -> None:
        from agent_brain_cli.client.api_client import ServerError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "boom"})

        transport = httpx.MockTransport(handler)
        client = httpx.Client(transport=transport, base_url="http://wrapped")
        wrapped = DocServeClient.from_httpx(client)
        with wrapped:
            with pytest.raises(ServerError) as ei:
                wrapped.health()
        assert ei.value.status_code == 500
