"""Phase 7 integration: post-bind chmod + long-path fallback.

Reviewer findings for ``feat/mcp-uds-transport``:

- A2 — ``serve_dual``/``serve_uds_only`` must chmod the socket to ``0o600``
  after uvicorn binds; today the socket inherits the umask (~0o755) and
  the client-side ``validate_socket()`` rejects it.
- A3 — When the canonical socket path exceeds the platform limit
  (104 bytes on macOS/BSD), the bind helper must fall back to
  ``/tmp/agent-brain-<hash>.sock`` and write a pointer file inside the
  state dir so clients resolve the correct path.

These tests live in ``integration/`` so they exercise the real uvicorn
bind path, not a mock. They share the ``threading + httpx`` pattern from
``test_uds_dual_bind.py``.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import socket as _socket
import stat
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
        return {"status": "healthy"}

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
    base = Path(tempfile.mkdtemp(prefix="absrv-p7-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


class TestPostBindChmod:
    """A2 — socket must come out 0o600 *without* the test chmod'ing it.

    The existing ``test_uds_dual_bind.py`` line 94 does the chmod
    manually, masking the bug. After Phase 7, the bind helper does it
    automatically and the assertion below holds.
    """

    def test_serve_dual_chmods_socket_to_0600(self, short_state_dir: Path) -> None:
        from agent_brain_server.api import uds_bind as bind_mod

        socket_path = short_state_dir / "agent-brain.sock"
        port = _pick_free_port()
        app = _stub_app()
        holders: dict[str, object] = {}

        def _run() -> None:
            asyncio.run(
                bind_mod.serve_dual(
                    app,
                    host="127.0.0.1",
                    port=port,
                    socket_path=socket_path,
                    server_holder=holders,
                )
            )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        try:
            assert _wait_for(socket_path.exists, timeout=5.0)
            # Give the chmod task one extra beat to run.
            assert _wait_for(
                lambda: stat.S_IMODE(os.lstat(socket_path).st_mode) == 0o600,
                timeout=3.0,
            ), (
                f"Socket mode is {stat.S_IMODE(os.lstat(socket_path).st_mode):#o}, "
                "expected 0o600 (bind helper must chmod post-bind)"
            )
        finally:
            for key in ("server_tcp", "server_uds"):
                srv = holders.get(key)
                if srv is not None:
                    srv.should_exit = True  # type: ignore[attr-defined]
            thread.join(timeout=5.0)

    def test_serve_uds_only_chmods_socket_to_0600(self, short_state_dir: Path) -> None:
        from agent_brain_server.api import uds_bind as bind_mod

        socket_path = short_state_dir / "agent-brain.sock"
        app = _stub_app()
        holders: dict[str, object] = {}

        def _run() -> None:
            asyncio.run(
                bind_mod.serve_uds_only(
                    app, socket_path=socket_path, server_holder=holders
                )
            )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        try:
            assert _wait_for(socket_path.exists, timeout=5.0)
            assert _wait_for(
                lambda: stat.S_IMODE(os.lstat(socket_path).st_mode) == 0o600,
                timeout=3.0,
            ), (
                f"Socket mode is {stat.S_IMODE(os.lstat(socket_path).st_mode):#o}, "
                "expected 0o600"
            )
        finally:
            srv = holders.get("server")
            if srv is not None:
                srv.should_exit = True  # type: ignore[attr-defined]
            thread.join(timeout=5.0)


class TestLongPathFallback:
    """A3 — long socket path triggers pointer-file fallback to /tmp.

    The canonical socket path is ``<state_dir>/agent-brain.sock``; when
    that exceeds 104 bytes (macOS sun_path limit), the bind helper must
    bind to ``/tmp/agent-brain-<sha256[:8]>.sock`` and write
    ``<state_dir>/agent-brain.sock.path`` containing the real path.
    """

    def test_resolve_bind_path_short_path_returns_canonical(
        self, short_state_dir: Path
    ) -> None:
        from agent_brain_server.api import uds_bind as bind_mod

        bind_path, used_fallback = bind_mod.resolve_bind_path(short_state_dir)
        assert bind_path == short_state_dir / "agent-brain.sock"
        assert used_fallback is False
        assert not (short_state_dir / "agent-brain.sock.path").exists()

    def test_resolve_bind_path_long_path_writes_pointer(
        self, short_state_dir: Path
    ) -> None:
        from agent_brain_server.api import uds_bind as bind_mod

        # Build a state dir with a path long enough to exceed the limit
        # by nesting deep directories.
        nested = short_state_dir / ("x" * 80) / ("y" * 80)
        nested.mkdir(parents=True, exist_ok=True)
        os.chmod(nested, 0o700)

        bind_path, used_fallback = bind_mod.resolve_bind_path(nested)
        assert used_fallback is True
        assert str(bind_path).startswith("/tmp/agent-brain-")
        assert bind_path.suffix == ".sock"

        pointer = nested / "agent-brain.sock.path"
        assert pointer.is_file()
        assert pointer.read_text().strip() == str(bind_path)

        # Hash must be deterministic per state_dir.
        digest = hashlib.sha256(str(nested.resolve()).encode("utf-8")).hexdigest()[:8]
        assert bind_path.name == f"agent-brain-{digest}.sock"


class TestRunHonorsUdsEnv:
    """A1 — server's run() must branch on AGENT_BRAIN_UDS / _ONLY env vars.

    Today run() unconditionally calls uvicorn.run(host=..., port=...),
    ignoring UDS env vars set by `agent-brain start --uds`. Phase 7 must
    delegate to uds_bind helpers in that case.
    """

    def test_run_uds_only_calls_serve_uds_only(
        self, short_state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_brain_server.api import main as main_mod

        called: dict[str, object] = {}

        def _fake_serve_uds_only(app, *, socket_path, **kwargs):  # type: ignore[no-untyped-def]
            called["uds_only"] = True
            called["socket_path"] = socket_path

            async def _noop() -> None:
                return None

            return _noop()

        def _fake_uvicorn_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            called["uvicorn_run"] = True

        monkeypatch.setattr(main_mod.uds_bind, "serve_uds_only", _fake_serve_uds_only)
        monkeypatch.setattr(main_mod.uvicorn, "run", _fake_uvicorn_run)
        monkeypatch.setenv("AGENT_BRAIN_UDS_ONLY", "1")
        monkeypatch.setenv("AGENT_BRAIN_UDS", "1")
        monkeypatch.setenv(
            "AGENT_BRAIN_UDS_PATH", str(short_state_dir / "agent-brain.sock")
        )
        # Issue #199 (199-03): startup gate refuses without API_KEY. This
        # test exercises UDS dispatch only, so opt out of auth explicitly.
        monkeypatch.setenv("INSECURE_NO_AUTH", "true")

        main_mod.run(host="127.0.0.1", port=8765, state_dir=str(short_state_dir))

        assert called.get("uds_only") is True
        assert (
            called.get("uvicorn_run") is None
        ), "uvicorn.run must NOT be called when AGENT_BRAIN_UDS_ONLY=1"

    def test_run_uds_dual_calls_serve_dual(
        self, short_state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_brain_server.api import main as main_mod

        called: dict[str, object] = {}

        def _fake_serve_dual(app, *, host, port, socket_path, **kwargs):  # type: ignore[no-untyped-def]
            called["dual"] = True
            called["host"] = host
            called["port"] = port
            called["socket_path"] = socket_path

            async def _noop() -> None:
                return None

            return _noop()

        def _fake_uvicorn_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            called["uvicorn_run"] = True

        monkeypatch.setattr(main_mod.uds_bind, "serve_dual", _fake_serve_dual)
        monkeypatch.setattr(main_mod.uvicorn, "run", _fake_uvicorn_run)
        monkeypatch.setenv("AGENT_BRAIN_UDS", "1")
        monkeypatch.delenv("AGENT_BRAIN_UDS_ONLY", raising=False)
        monkeypatch.setenv(
            "AGENT_BRAIN_UDS_PATH", str(short_state_dir / "agent-brain.sock")
        )
        monkeypatch.setenv(
            "INSECURE_NO_AUTH", "true"
        )  # Issue #199 — UDS dispatch test, not auth

        main_mod.run(host="127.0.0.1", port=8765, state_dir=str(short_state_dir))

        assert called.get("dual") is True
        assert called.get("host") == "127.0.0.1"
        assert called.get("port") == 8765
        assert called.get("uvicorn_run") is None

    def test_run_no_uds_env_calls_uvicorn_normally(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sanity: no AGENT_BRAIN_UDS env → existing uvicorn.run path."""
        from agent_brain_server.api import main as main_mod

        called: dict[str, object] = {}

        def _fake_uvicorn_run(*args, **kwargs):  # type: ignore[no-untyped-def]
            called["uvicorn_run"] = True

        monkeypatch.setattr(main_mod.uvicorn, "run", _fake_uvicorn_run)
        monkeypatch.delenv("AGENT_BRAIN_UDS", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_UDS_ONLY", raising=False)
        monkeypatch.setenv(
            "INSECURE_NO_AUTH", "true"
        )  # Issue #199 — dispatch test, not auth

        main_mod.run(host="127.0.0.1", port=8765)

        assert called.get("uvicorn_run") is True


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
    except Exception:
        return False
