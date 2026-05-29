"""Phase 2 TDD integration: ``serve_dual()`` binds HTTP AND UDS in one process.

Maps to plan §12.3 acceptance #3 — "Dual-bind serves both HTTP and UDS in
one process; SIGTERM removes the socket." This is the proper integration
test the spike script ``scripts/spike_dual_bind.py`` already proved at the
architecture level.

RED until Phase 2 ships ``agent_brain_server/api/uds_bind.serve_dual``.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket as _socket
import tempfile
import threading
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI


def _stub_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health/")
    async def health() -> dict[str, object]:
        return {"status": "healthy", "from": "dual_bind_integration"}

    return app


def _pick_free_port() -> int:
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for(predicate, *, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def short_state_dir() -> Generator[Path, None, None]:
    base = Path(tempfile.mkdtemp(prefix="absrv-dual-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


class TestDualBindIntegration:
    """One process, two transports, shared lifespan."""

    def test_dual_bind_responds_on_both_transports(self, short_state_dir: Path) -> None:
        """HTTP /health/ and UDS /health/ must both return healthy
        simultaneously after serve_dual() starts."""
        socket_path = short_state_dir / "agent-brain.sock"
        port = _pick_free_port()
        app = _stub_app()

        from agent_brain_server.api import uds_bind as bind_mod

        server_holders: dict[str, object] = {}

        def _run() -> None:
            asyncio.run(
                bind_mod.serve_dual(
                    app,
                    host="127.0.0.1",
                    port=port,
                    socket_path=socket_path,
                    server_holder=server_holders,
                )
            )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        try:
            assert _wait_for(
                socket_path.exists, timeout=5.0
            ), f"UDS socket not created at {socket_path}"
            os.chmod(socket_path, 0o600)

            # HTTP probe
            assert _wait_for(
                lambda: _probe_http_healthy("127.0.0.1", port), timeout=5.0
            ), "HTTP /health/ never responded healthy"

            # UDS probe
            assert _probe_uds_healthy(
                socket_path
            ), "UDS /health/ did not respond healthy"
        finally:
            for key in ("server_tcp", "server_uds"):
                srv = server_holders.get(key)
                if srv is not None:
                    srv.should_exit = True  # type: ignore[attr-defined]
            thread.join(timeout=5.0)

    def test_sigterm_cleans_up_both_and_socket_file(
        self, short_state_dir: Path
    ) -> None:
        """After clean shutdown, the socket file must be unlinked."""
        socket_path = short_state_dir / "agent-brain.sock"
        port = _pick_free_port()
        app = _stub_app()

        from agent_brain_server.api import uds_bind as bind_mod

        server_holders: dict[str, object] = {}

        def _run() -> None:
            asyncio.run(
                bind_mod.serve_dual(
                    app,
                    host="127.0.0.1",
                    port=port,
                    socket_path=socket_path,
                    server_holder=server_holders,
                )
            )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        try:
            assert _wait_for(socket_path.exists, timeout=5.0)
        finally:
            for key in ("server_tcp", "server_uds"):
                srv = server_holders.get(key)
                if srv is not None:
                    srv.should_exit = True  # type: ignore[attr-defined]
            thread.join(timeout=5.0)

        # The socket file is gone after shutdown.
        assert not socket_path.exists()


def _probe_http_healthy(host: str, port: int) -> bool:
    try:
        response = httpx.get(f"http://{host}:{port}/health/", timeout=3.0)
        return (
            response.status_code == 200 and response.json().get("status") == "healthy"
        )
    except Exception:  # noqa: BLE001 — probe; surface as False
        return False


def _probe_uds_healthy(socket_path: Path) -> bool:
    try:
        transport = httpx.HTTPTransport(uds=str(socket_path))
        with httpx.Client(
            transport=transport, base_url="http://agent-brain", timeout=3.0
        ) as client:
            response = client.get("/health/")
            return (
                response.status_code == 200
                and response.json().get("status") == "healthy"
            )
    except Exception:  # noqa: BLE001
        return False
