"""Session-scoped harness fixtures for the Phase 61/62 framework adapter matrix.

This conftest provides:

- ``seeded_mcp_server`` (session-scoped): spins up ONE real
  ``agent-brain-serve`` with an indexed tiny corpus (FRAMEWORK_CORPUS from
  _harness.py). All 5 framework smoke tests share this single server so the
  expensive embedding/indexing run happens only once per pytest session.

- ``http_mcp_listener`` (function-scoped factory): Popens the REAL
  ``agent-brain-mcp --transport http`` binary on a free loopback port, polls
  ``/healthz`` until 200, yields ``http://127.0.0.1:<port>/mcp``, and tears
  down with SIGTERM → wait(grace) → SIGKILL (Phase 60 contract). Used by the
  FRAME-01 ``MCPServerStreamableHttp`` leg.

- ``pytest_collection_modifyitems``: auto-tags every test under
  ``framework-matrix/`` with ``pytest.mark.framework`` so individual test
  files don't have to declare it manually.

- ``_orphan_guard`` (session-scoped, autouse): snapshots child PIDs at
  session start; at teardown, calls ``assert_no_orphans`` to prove zero
  agent-brain subprocesses survived the entire matrix run.

Seeding logic mirrors agent-brain-cli/tests/integration/_corpus.py
(start_seeded_server + prerequisites_available + _find_free_port +
_poll_health) — inlined here because framework-matrix has no package root
and must not import across package boundaries.

DO NOT model seeding on agent-brain-mcp/tests/e2e/conftest.py — its
indexed_server fixture is an unimplemented Phase-4 stub that calls
pytest.skip() and yields {}.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from collections.abc import Callable, Generator, Iterator
from pathlib import Path
from typing import Any

import pytest

from _harness import (
    FRAMEWORK_CORPUS,
    assert_no_orphans,
    _children_pids,
)

# ---------------------------------------------------------------------------
# Timeout constants (generous — first run downloads models / hits OpenAI).
# ---------------------------------------------------------------------------
_SERVER_STARTUP_TIMEOUT_S = 60
_INDEXING_TIMEOUT_S = 180
_HEALTH_POLL_INTERVAL_S = 1.0
_HTTP_LISTENER_STARTUP_TIMEOUT_S = 30
_HTTP_LISTENER_GRACE_S = 5.0


# ---------------------------------------------------------------------------
# Prerequisites check — mirrors _corpus.py:prerequisites_available()
# ---------------------------------------------------------------------------


def prerequisites_available() -> tuple[bool, str]:
    """Return (ok, reason) for the full set of integration test requirements.

    Returns ``(True, "")`` when every prerequisite is present.  Returns
    ``(False, reason)`` when something is missing — the caller passes
    ``reason`` to ``pytest.skip`` so CI logs show why the test skipped.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return (
            False,
            "OPENAI_API_KEY not set — the framework matrix requires a real "
            "embedding provider to seed the corpus so search_documents "
            "returns non-empty results.",
        )
    if shutil.which("agent-brain-serve") is None:
        return (
            False,
            "agent-brain-serve not on PATH — install agent-brain-server "
            "into the active Python environment.",
        )
    if shutil.which("agent-brain-mcp") is None:
        return (
            False,
            "agent-brain-mcp not on PATH — install agent-brain-mcp "
            "(agent-brain-ag-mcp on PyPI) into the active Python environment.",
        )
    return (True, "")


# ---------------------------------------------------------------------------
# Free-port helper — mirrors _corpus.py:_find_free_port()
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    """Bind to port 0 on loopback and return the assigned port number."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


# ---------------------------------------------------------------------------
# Health poll — mirrors _corpus.py:_poll_health()
# ---------------------------------------------------------------------------


def _poll_health(
    base_url: str,
    deadline: float,
    *,
    require_idle_after_index: bool = False,
) -> dict[str, Any] | None:
    """Poll ``/health/status`` until ready or deadline.

    Returns the parsed response dict on success, or ``None`` on timeout.
    """
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"{base_url}/health/status", timeout=2.0
            ) as resp:
                data: dict[str, Any] = json.loads(resp.read())
                if require_idle_after_index:
                    if not data.get("indexing_in_progress", True) and (
                        data.get("total_documents", 0) > 0
                    ):
                        return data
                else:
                    return data
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(_HEALTH_POLL_INTERVAL_S)
    return None


# ---------------------------------------------------------------------------
# Stray MCP subprocess cleanup — mirrors _corpus.py:_kill_stray_mcp_subprocesses()
# ---------------------------------------------------------------------------


def _kill_stray_mcp_subprocesses() -> None:
    """Best-effort cleanup of zombie agent-brain-mcp subprocesses."""
    try:
        subprocess.run(
            ["pkill", "-f", "agent-brain-mcp"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


# ---------------------------------------------------------------------------
# Seeded-server context manager — mirrors _corpus.py:start_seeded_server()
# ---------------------------------------------------------------------------


@contextmanager
def start_seeded_server(
    state_dir: Path,
    corpus: dict[str, str],
) -> Iterator[Path]:
    """Spin up agent-brain-serve over UDS, seed corpus, yield state_dir.

    Mirrors agent-brain-cli/tests/integration/_corpus.py:start_seeded_server
    EXACTLY — do not model this on agent-brain-mcp/tests/e2e/conftest.py,
    which has an unimplemented stub.

    Args:
        state_dir: Clean directory; ``.agent-brain/`` created inside.
        corpus: ``{relative_path: content}`` mapping written under
            ``state_dir/corpus/`` and indexed via ``POST /index/``.

    Yields:
        ``state_dir`` — now containing ``.agent-brain/runtime.json`` and
        the live UDS socket.
    """
    project_state_dir = state_dir / ".agent-brain"
    project_state_dir.mkdir(parents=True, exist_ok=True)
    corpus_dir = state_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    for rel, content in corpus.items():
        (corpus_dir / rel).write_text(content, encoding="utf-8")

    port = _find_free_port()
    socket_path = project_state_dir / "agent-brain.sock"

    env = {
        **os.environ,
        "AGENT_BRAIN_STATE_DIR": str(project_state_dir),
        "AGENT_BRAIN_UDS": "1",
        "AGENT_BRAIN_UDS_PATH": str(socket_path),
        "API_PORT": str(port),
        "API_HOST": "127.0.0.1",
    }
    base_url = f"http://127.0.0.1:{port}"

    proc = subprocess.Popen(
        ["agent-brain-serve"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.time() + _SERVER_STARTUP_TIMEOUT_S
        ready = _poll_health(base_url, deadline)
        if ready is None:
            stderr = b""
            if proc.stderr is not None:
                stderr = proc.stderr.read()
            raise RuntimeError(
                f"agent-brain-serve did not become ready within "
                f"{_SERVER_STARTUP_TIMEOUT_S}s. "
                f"stderr={stderr.decode(errors='replace')[:2000]}"
            )

        # Trigger indexing of the corpus folder.
        req = urllib.request.Request(
            f"{base_url}/index/",
            data=json.dumps(
                {
                    "folder_path": str(corpus_dir),
                    "force": False,
                    "recursive": True,
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:1000]
            raise RuntimeError(f"POST /index/ failed: {e.code} {body}") from e

        # Wait for indexing to complete.
        deadline = time.time() + _INDEXING_TIMEOUT_S
        indexed = _poll_health(base_url, deadline, require_idle_after_index=True)
        if indexed is None:
            raise RuntimeError(
                f"indexing did not complete within {_INDEXING_TIMEOUT_S}s"
            )

        yield state_dir
    finally:
        if proc.poll() is None:
            try:
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        _kill_stray_mcp_subprocesses()


# ---------------------------------------------------------------------------
# Session-scoped orphan-guard fixture (autouse).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _orphan_guard() -> Generator[None, None, None]:
    """Snapshot child PIDs at session start; assert no orphans at teardown.

    Uses the psutil children-delta pattern from Phase 60's orphan stress
    test. If psutil is unavailable the guard is a no-op (graceful degradation).
    """
    self_pid = os.getpid()
    baseline = _children_pids(self_pid)
    yield
    assert_no_orphans(self_pid, baseline)


# ---------------------------------------------------------------------------
# Session-scoped seeded server fixture.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def seeded_mcp_server() -> Generator[Path, None, None]:
    """Spin up ONE real agent-brain-serve with an indexed FRAMEWORK_CORPUS.

    Session-scoped so the expensive indexing run happens once and all 5
    framework smoke tests share the same server.

    Skips the test when OPENAI_API_KEY or required binaries are missing.

    Yields:
        state_dir (Path) — the session temp directory whose
        ``.agent-brain/`` subdir contains the live UDS socket.
    """
    ok, reason = prerequisites_available()
    if not ok:
        pytest.skip(reason)

    # Use an AF_UNIX-safe short path (avoid macOS 104-char socket limit).
    state_dir = Path(tempfile.mkdtemp(prefix="abfwm-"))

    with start_seeded_server(state_dir, FRAMEWORK_CORPUS) as sd:
        yield sd


# ---------------------------------------------------------------------------
# Function-scoped HTTP MCP listener factory fixture.
# ---------------------------------------------------------------------------


def _start_http_listener(agent_brain_state: str) -> tuple[subprocess.Popen[bytes], str]:
    """Start agent-brain-mcp --transport http and return (proc, mcp_url).

    Polls /healthz until 200 or raises RuntimeError on timeout.

    Args:
        agent_brain_state: The .agent-brain state directory path string.

    Returns:
        A 2-tuple (proc, mcp_url) where proc is the running Popen and
        mcp_url is ``http://127.0.0.1:<port>/mcp``.

    Raises:
        RuntimeError: when the process exits before /healthz is ready or
            when the startup timeout is exceeded.
    """
    port = _find_free_port()

    env = {
        **os.environ,
        "AGENT_BRAIN_STATE_DIR": agent_brain_state,
    }

    cmd = [
        "agent-brain-mcp",
        "--transport", "http",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--backend", "uds",
        "--state-dir", agent_brain_state,
    ]

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    url_base = f"http://127.0.0.1:{port}"
    url_health = f"{url_base}/healthz"
    mcp_url = f"{url_base}/mcp"

    # Poll /healthz until 200 or deadline.
    deadline = time.time() + _HTTP_LISTENER_STARTUP_TIMEOUT_S
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            stderr = b""
            if proc.stderr is not None:
                stderr = proc.stderr.read()
            raise RuntimeError(
                f"agent-brain-mcp --transport http died before /healthz: "
                f"{stderr.decode(errors='replace')[:2000]}"
            )
        try:
            with urllib.request.urlopen(url_health, timeout=0.5) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(0.1)

    if not ready:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        raise RuntimeError(
            f"agent-brain-mcp --transport http did not become ready on "
            f"port {port} within {_HTTP_LISTENER_STARTUP_TIMEOUT_S}s"
        )

    return proc, mcp_url


def _stop_http_listener(proc: subprocess.Popen[bytes]) -> None:
    """Tear down an HTTP listener process. Phase 60 contract: SIGTERM → wait → SIGKILL.

    DO NOT use SIGINT — SIGTERM is the correct first signal per Phase 60.

    Args:
        proc: The running agent-brain-mcp process to terminate.
    """
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=_HTTP_LISTENER_GRACE_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture
def http_mcp_listener(
    seeded_mcp_server: Path,
) -> Generator[Callable[[], str], None, None]:
    """Yield a factory callable that starts a live agent-brain-mcp --transport http listener.

    The factory pattern allows the test to CALL ``http_mcp_listener()`` with
    parens to start the real binary and receive the MCP URL string. This makes
    it unambiguous that the listener IS started (vs. being injected as a
    bare-fixture value that the test might silently never use). Per Plan 61-02:
    ``url = http_mcp_listener()`` — always call with parens.

    The factory may be called multiple times within a single test (each call
    starts a new listener on a different free port). All started processes are
    terminated at fixture teardown using SIGTERM → wait(grace) → SIGKILL
    (Phase 60 contract). SIGINT is intentionally NOT used.

    This fixture is the FRAME-01 streamable-http leg's server provider.

    Args:
        seeded_mcp_server: Session-scoped fixture yielding state_dir Path for
            the live agent-brain-serve with indexed FRAMEWORK_CORPUS.

    Yields:
        A zero-argument callable that starts a new HTTP listener and returns
        ``http://127.0.0.1:<port>/mcp``.
    """
    agent_brain_state = str(seeded_mcp_server / ".agent-brain")
    started_procs: list[subprocess.Popen[bytes]] = []

    def factory() -> str:
        proc, mcp_url = _start_http_listener(agent_brain_state)
        started_procs.append(proc)
        return mcp_url

    try:
        yield factory
    finally:
        for proc in started_procs:
            _stop_http_listener(proc)


# ---------------------------------------------------------------------------
# Auto-mark every test under framework-matrix/ with pytest.mark.framework.
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Auto-tag every test collected from framework-matrix/ with the marker.

    Individual test files in framework-matrix/ do not need to declare
    ``@pytest.mark.framework`` — this hook applies it globally so the
    ``addopts = -m framework`` filter in pytest.ini selects them automatically.
    """
    marker = pytest.mark.framework
    for item in items:
        # item.fspath is the test file's absolute path (legacy API).
        # item.path is the pathlib.Path equivalent (pytest ≥ 7.0).
        try:
            item_path = item.path
        except AttributeError:
            item_path = Path(str(item.fspath))

        # Tag any test whose file path contains "framework-matrix".
        if "framework-matrix" in str(item_path):
            item.add_marker(marker)
