"""Phase 2 TDD: ``agent_brain_server.api.uds_bind`` helpers.

Maps to plan §12.3 acceptance #3 (small slice — the unit-level test that
``serve_uds_only`` actually binds a socket and SIGTERM unlinks it). The
full dual-bind integration test lives in
``tests/integration/test_uds_dual_bind.py``.

RED until Phase 2 ships ``agent_brain_server/api/uds_bind.py``.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from agent_brain_server.api.uds_bind import (
    serve_uds_only,  # noqa: F401 — collection-time smoke that the symbol exists
)


def _stub_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health/")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "from": "uds_bind_unit"}

    return app


@pytest.fixture
def short_state_dir() -> Generator[Path, None, None]:
    """A /tmp-rooted dir, short enough for AF_UNIX paths on macOS."""
    base = Path(tempfile.mkdtemp(prefix="absrv-uds-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        import shutil

        shutil.rmtree(base, ignore_errors=True)


def _wait_for(predicate, *, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class TestServeUdsOnly:
    """``serve_uds_only(app, socket_path)`` binds AF_UNIX only."""

    def test_binds_and_responds(self, short_state_dir: Path) -> None:
        """Spawn the helper in a thread, assert UDS /health/ returns 200,
        then trigger shutdown via the returned server's should_exit flag."""
        socket_path = short_state_dir / "agent-brain.sock"
        app = _stub_app()

        from agent_brain_server.api import uds_bind as bind_mod

        # Pattern: serve_uds_only returns a (server, awaitable) tuple so
        # the caller can flip should_exit from another thread. Equivalent
        # API will be defined in Phase 2; this test pins the contract.
        server_holder: dict[str, object] = {}

        def _run() -> None:
            asyncio.run(
                bind_mod.serve_uds_only(
                    app,
                    socket_path=socket_path,
                    server_holder=server_holder,
                )
            )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        try:
            assert _wait_for(
                socket_path.exists, timeout=5.0
            ), f"socket not created at {socket_path}"
            os.chmod(socket_path, 0o600)

            transport = httpx.HTTPTransport(uds=str(socket_path))
            with httpx.Client(
                transport=transport, base_url="http://agent-brain", timeout=3.0
            ) as client:
                response = client.get("/health/")
                assert response.status_code == 200
                assert response.json()["status"] == "healthy"
        finally:
            server = server_holder.get("server")
            if server is not None:
                server.should_exit = True  # type: ignore[attr-defined]
            thread.join(timeout=5.0)

    def test_unlinks_socket_on_shutdown(self, short_state_dir: Path) -> None:
        """The socket file must be removed when serve_uds_only returns."""
        socket_path = short_state_dir / "agent-brain.sock"
        app = _stub_app()

        from agent_brain_server.api import uds_bind as bind_mod

        server_holder: dict[str, object] = {}

        def _run() -> None:
            asyncio.run(
                bind_mod.serve_uds_only(
                    app,
                    socket_path=socket_path,
                    server_holder=server_holder,
                )
            )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        try:
            assert _wait_for(socket_path.exists, timeout=5.0)
        finally:
            server = server_holder.get("server")
            if server is not None:
                server.should_exit = True  # type: ignore[attr-defined]
            thread.join(timeout=5.0)

        # The socket file must be gone — uvicorn unlinks, our helper guards.
        assert not socket_path.exists()

    def test_raises_when_parent_dir_missing(self, short_state_dir: Path) -> None:
        """If the parent dir doesn't exist, fail loud rather than guess."""
        socket_path = short_state_dir / "does-not-exist" / "agent-brain.sock"
        app = _stub_app()

        from agent_brain_server.api import uds_bind as bind_mod

        with pytest.raises((FileNotFoundError, OSError)):
            asyncio.run(bind_mod.serve_uds_only(app, socket_path=socket_path))
