"""Phase 7 A4 — full end-to-end: `agent-brain start --uds` actually works.

The reviewer's central finding was that all the Phase 1-5 tests called
``serve_dual`` / ``serve_uds_only`` directly, never the public
``agent-brain start --uds`` path. This test closes that gap by spawning
the server through ``python -m agent_brain_server.api.main`` exactly the
way the CLI does (after Phase 7's start.py change) and probing both
transports against a real bound socket.

Marked ``slow``; runs in ``task before-push`` via the default suite but
takes ~3-5 seconds to spawn + readiness-probe + teardown.
"""

from __future__ import annotations

import os
import shutil
import socket as _socket
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest


def _pick_free_port() -> int:
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for(predicate, *, timeout: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return False


@pytest.fixture
def short_state_dir() -> Generator[Path, None, None]:
    base = Path(tempfile.mkdtemp(prefix="absrv-e2e-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)


def _probe_uds(socket_path: Path, *, timeout_s: float = 3.0) -> bool:
    try:
        transport = httpx.HTTPTransport(uds=str(socket_path))
        with httpx.Client(
            transport=transport,
            base_url="http://agent-brain",
            timeout=timeout_s,
        ) as client:
            resp = client.get("/health/")
            return bool(resp.status_code == 200)
    except Exception:
        return False


def _probe_http(host: str, port: int, *, timeout_s: float = 3.0) -> bool:
    try:
        resp = httpx.get(f"http://{host}:{port}/health/", timeout=timeout_s)
        return bool(resp.status_code == 200)
    except Exception:
        return False


@pytest.mark.slow
def test_agent_brain_serve_dual_bind_subprocess(short_state_dir: Path) -> None:
    """`python -m agent_brain_server.api.main --host ... --port ...` with
    AGENT_BRAIN_UDS=1 in env binds BOTH transports.

    Mirrors what `agent-brain start --uds` does in CLI start.py after the
    Phase 7 wiring fix. Asserts the socket is at mode 0o600 (so
    validate_socket() accepts it) and the parent at 0o700.
    """
    port = _pick_free_port()
    socket_path = short_state_dir / "agent-brain.sock"

    env = os.environ.copy()
    env["AGENT_BRAIN_UDS"] = "1"
    env["AGENT_BRAIN_UDS_PATH"] = str(socket_path)
    env["AGENT_BRAIN_STATE_DIR"] = str(short_state_dir)
    # Issue #199 (199-03): startup gate refuses subprocess without API_KEY.
    # This e2e exercises UDS dual-bind, not auth, so opt out explicitly.
    env["INSECURE_NO_AUTH"] = "true"
    # Strip any inherited API_KEY/AGENT_BRAIN_API_KEY so the subprocess hits
    # the INSECURE_NO_AUTH warning path predictably regardless of dev shell state.
    env.pop("API_KEY", None)
    env.pop("AGENT_BRAIN_API_KEY", None)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agent_brain_server.api.main",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--state-dir",
            str(short_state_dir),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Wait for the socket to appear AND chmod to settle at 0o600.
        assert _wait_for(
            socket_path.exists, timeout=15.0
        ), "Socket never appeared — server failed to start UDS bind"
        assert _wait_for(
            lambda: stat.S_IMODE(os.lstat(socket_path).st_mode) == 0o600,
            timeout=10.0,
        ), (
            f"Socket mode is {stat.S_IMODE(os.lstat(socket_path).st_mode):#o}; "
            "expected 0o600 (uds_bind must chmod post-bind)"
        )

        # Both transports must answer /health/.
        assert _wait_for(
            lambda: _probe_http("127.0.0.1", port), timeout=10.0
        ), "HTTP /health/ never responded"
        assert _probe_uds(socket_path), "UDS /health/ never responded"

        # Parent dir must be 0o700 (validate_socket() requirement).
        parent_mode = stat.S_IMODE(os.lstat(short_state_dir).st_mode)
        assert (
            parent_mode == 0o700
        ), f"Parent dir mode is {parent_mode:#o}; expected 0o700"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)

    # After clean shutdown the socket file is gone.
    assert not socket_path.exists()
