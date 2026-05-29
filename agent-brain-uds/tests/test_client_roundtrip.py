"""End-to-end UDS roundtrip test for ``agent_brain_uds.client``.

Spawns a minimal Starlette ASGI app via uvicorn bound to a real UDS socket,
opens a client via :func:`make_client`, and verifies the HTTP roundtrip.

This is the smallest possible proof that the entire stack works end-to-end
on the bench host. Plan §12.3 acceptance #5 (CLI parity) builds on top of
this in Phase 3.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from agent_brain_uds.client import make_async_client, make_client


def _build_app() -> Starlette:
    async def health(_request: object) -> JSONResponse:
        return JSONResponse({"status": "healthy", "from": "uds-stub"})

    return Starlette(routes=[Route("/health/", health)])


class _UvicornThread(threading.Thread):
    """Run uvicorn in a background thread so the test can drive requests."""

    def __init__(self, app: Starlette, socket_path: Path) -> None:
        super().__init__(daemon=True)
        self._config = uvicorn.Config(
            app=app,
            uds=str(socket_path),
            log_level="warning",
            lifespan="off",
        )
        self._server = uvicorn.Server(self._config)

    def run(self) -> None:  # noqa: D401 — Thread.run override
        asyncio.run(self._server.serve())

    def stop(self) -> None:
        self._server.should_exit = True


@pytest.fixture
def uds_server(short_tmp: Path) -> Generator[Path, None, None]:
    """Bind a stub uvicorn app to a UDS socket in short_tmp with mode 0600.

    Uses ``short_tmp`` (a ``/tmp/abuds-*`` path) instead of pytest's
    ``tmp_path`` because the latter exceeds the 104-byte ``AF_UNIX`` limit
    on macOS.
    """
    os.chmod(short_tmp, 0o700)
    socket_path = short_tmp / "agent-brain.sock"

    thread = _UvicornThread(_build_app(), socket_path)
    thread.start()

    # Wait for uvicorn to actually bind (up to 5s).
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if socket_path.exists():
            # Lock down perms — uvicorn binds with the umask default.
            os.chmod(socket_path, 0o600)
            break
        time.sleep(0.05)
    else:  # pragma: no cover — defensive
        thread.stop()
        thread.join(timeout=2)
        pytest.fail(f"uvicorn did not create socket at {socket_path}")

    try:
        yield socket_path
    finally:
        thread.stop()
        thread.join(timeout=2)
        if socket_path.exists():
            socket_path.unlink()


def test_sync_client_roundtrip(uds_server: Path) -> None:
    client = make_client(socket_path=uds_server)
    try:
        response = client.get("/health/")
        assert response.status_code == 200
        body = response.json()
        assert body == {"status": "healthy", "from": "uds-stub"}
    finally:
        client.close()


def test_sync_client_uses_sentinel_base_url(uds_server: Path) -> None:
    client = make_client(socket_path=uds_server)
    try:
        assert str(client.base_url) == "http://agent-brain"
    finally:
        client.close()


async def test_async_client_roundtrip(uds_server: Path) -> None:
    client = make_async_client(socket_path=uds_server)
    try:
        response = await client.get("/health/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    finally:
        await client.aclose()


def test_client_validates_socket_on_construction(tmp_path: Path) -> None:
    """A bad socket should fail eagerly in ``make_client``, not on first request."""
    from agent_brain_uds.errors import SocketNotFoundError

    bogus = tmp_path / "nope.sock"
    with pytest.raises(SocketNotFoundError):
        make_client(socket_path=bogus)


def test_client_resolves_via_env(
    uds_server: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``AGENT_BRAIN_UDS_PATH`` is honored when no explicit path given."""
    monkeypatch.setenv("AGENT_BRAIN_UDS_PATH", str(uds_server))
    client = make_client()
    try:
        response = client.get("/health/")
        assert response.status_code == 200
    finally:
        client.close()


def test_httpx_transport_is_uds(uds_server: Path) -> None:
    """Sanity: the client's transport really is a UDS HTTPTransport."""
    client = make_client(socket_path=uds_server)
    try:
        transport = client._transport  # type: ignore[attr-defined]
        assert isinstance(transport, httpx.HTTPTransport)
    finally:
        client.close()
