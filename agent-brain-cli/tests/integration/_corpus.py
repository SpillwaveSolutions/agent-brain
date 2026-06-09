"""Shared corpus-seeder for cross-transport equivalence tests.

Phase 57 Plan 02 — extracted helper for ``test_transport_equivalence.py``
(``tests/contract/``). The plan's read_first referenced
``tests/integration/test_smoke_uds.py`` as the canonical pattern, but no
such file existed in the repo yet — this module fills that gap.

The helper launches a REAL ``agent-brain-serve`` subprocess bound to a
UDS socket inside a per-test ``state_dir``, indexes a small corpus by
POSTing to ``/index/``, polls ``/health/status`` until indexing
completes, and yields the state_dir for callers to use. The teardown
sends SIGTERM, waits, escalates to SIGKILL. Best-effort cleanup of
stray ``agent-brain-mcp`` subprocesses also runs (Phase 60 hygiene
target).

NO STUB FALLBACK. Caller skips the test when the prerequisites
(OPENAI_API_KEY, agent-brain-serve binary) are missing — that surfaces
honestly in CI/local-dev as a SKIP, not a false-PASS.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

# Generous timeouts — the first run downloads embedding models / hits
# OpenAI; subsequent runs are cached.
_SERVER_STARTUP_TIMEOUT_S = 60
_INDEXING_TIMEOUT_S = 180
_HEALTH_POLL_INTERVAL_S = 1.0


def prerequisites_available() -> tuple[bool, str]:
    """Cheap precheck so callers can skip cleanly when env is incomplete.

    Returns ``(True, "")`` when every prereq is present. Returns
    ``(False, reason)`` otherwise — the caller passes ``reason`` to
    ``pytest.skip`` so CI logs show why the equivalence test didn't run.

    We deliberately DO NOT auto-stub the corpus — the v3 DoD anchor
    (CLI-MCP-04) is a WIRE-level proof; a stub would only assert that
    the translator agrees with itself.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        return (
            False,
            "OPENAI_API_KEY not set — the v3 DoD anchor requires a real "
            "embedding provider to seed the byte-equivalence corpus.",
        )
    if shutil.which("agent-brain-serve") is None:
        return (
            False,
            "agent-brain-serve not on PATH — install agent-brain-server "
            "into the same Python environment.",
        )
    if shutil.which("agent-brain-mcp") is None:
        return (
            False,
            "agent-brain-mcp not on PATH — install agent-brain-mcp "
            "into the same Python environment.",
        )
    if shutil.which("agent-brain") is None:
        return (
            False,
            "agent-brain CLI not on PATH.",
        )
    return (True, "")


def _find_free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()
    return port


def _poll_health(
    base_url: str,
    deadline: float,
    *,
    require_idle_after_index: bool = False,
) -> dict | None:
    """Poll ``/health/status`` until ready or deadline.

    Returns the parsed dict on success or None on timeout.
    """
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"{base_url}/health/status", timeout=2.0
            ) as resp:
                data = json.loads(resp.read())
                if require_idle_after_index:
                    if not data.get("indexing_in_progress", True) and (
                        data.get("total_documents", 0) > 0
                    ):
                        return data  # type: ignore[no-any-return]
                else:
                    return data  # type: ignore[no-any-return]
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(_HEALTH_POLL_INTERVAL_S)
    return None


def _kill_stray_mcp_subprocesses() -> None:
    """Best-effort cleanup of zombie agent-brain-mcp subprocesses.

    The McpStdioBackend in Pattern A spawns + tears down a subprocess
    per query call. If a test crashes mid-call, a zombie may linger.
    Phase 60 owns proper subprocess hygiene; this is a defense in
    depth for the DoD anchor test fixture teardown.
    """
    try:
        subprocess.run(
            ["pkill", "-f", "agent-brain-mcp"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


@contextmanager
def start_seeded_server(
    state_dir: Path,
    corpus: Mapping[str, str],
) -> Iterator[Path]:
    """Spin up agent-brain-serve over UDS, seed ``corpus``, yield state_dir.

    Args:
        state_dir: A clean directory. ``.agent-brain/`` subdir is
            created inside. Server runs with ``AGENT_BRAIN_STATE_DIR``
            pointing here so subsequent CLI invocations against this
            same ``state_dir`` see the same backend state.
        corpus: ``{relative_path: content}`` mapping. Each entry is
            written to disk under ``state_dir/corpus/`` and the folder
            is indexed via ``POST /index/``.

    Yields:
        The ``state_dir`` (same as the input), now containing
        ``.agent-brain/runtime.json`` and the indexed UDS socket.
    """
    # Layout: <state_dir>/.agent-brain/  (per-project state)
    #         <state_dir>/corpus/        (the docs to index)
    project_state_dir = state_dir / ".agent-brain"
    project_state_dir.mkdir(parents=True, exist_ok=True)
    corpus_dir = state_dir / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    for rel, content in corpus.items():
        (corpus_dir / rel).write_text(content, encoding="utf-8")

    # Pick a port even though we use UDS — agent-brain-serve still
    # binds TCP by default, and we may want to reach it via HTTP for
    # debugging.
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
        # Wait for the server to become responsive.
        deadline = time.time() + _SERVER_STARTUP_TIMEOUT_S
        ready = _poll_health(base_url, deadline)
        if ready is None:
            stderr = b""
            if proc.stderr is not None:
                stderr = proc.stderr.read()
            raise RuntimeError(
                "agent-brain-serve did not become ready within "
                f"{_SERVER_STARTUP_TIMEOUT_S}s. "
                f"stderr={stderr.decode(errors='replace')[:2000]}"
            )

        # Trigger indexing of the seeded corpus folder.
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
