"""Phase 58-03 end-to-end: mcp start → query (no --mcp-url) → mcp stop.

Drives the full v3 discovery happy path against a real subprocess to
prove CLI-MCP-08 (file written by start AND read by McpHttpBackend
discovery) closes end-to-end AND CLI-MCP-10 (stop cleans up).

Skips gracefully without OPENAI_API_KEY — translator-shape equality
would only prove the dispatcher agrees with itself, not WIRE equality
against a seeded backend. (Mirrors Plan 57-02's DoD anchor skip.)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; cannot drive real backend")


def _require_mcp_pkg() -> None:
    try:
        import agent_brain_mcp  # noqa: F401
    except ImportError:
        pytest.skip("agent-brain-mcp not importable")


def _require_psutil() -> None:
    try:
        import psutil  # noqa: F401
    except ImportError:
        pytest.skip("psutil not importable")


def _run(
    cmd: list[str],
    env: dict[str, str],
    timeout: float = 30.0,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Wrap subprocess.run with a useful failure message."""
    return subprocess.run(
        cmd,
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def test_mcp_start_query_stop_round_trip(tmp_path: Path) -> None:
    """start → discovery-based query → stop completes without --mcp-url."""
    _require_openai_key()
    _require_mcp_pkg()
    _require_psutil()

    # Import the Plan 57-02 corpus seeder. Late import keeps the
    # opt-in pytest mark from importing httpx at collection time.
    from tests.integration._corpus import start_seeded_server

    state_dir = tmp_path / ".agent-brain"
    state_dir.mkdir()
    env = {**os.environ, "AGENT_BRAIN_STATE_DIR": str(state_dir)}

    # Seed a UDS-backed agent-brain-server (Plan 57-02 helper).
    with start_seeded_server(state_dir, corpus={"echo": "Echo doc seed."}):
        # 1) mcp start with --port 0 so the OS picks an idle port.
        start_proc = _run(
            [
                sys.executable,
                "-m",
                "agent_brain_cli",
                "mcp",
                "start",
                "--state-dir",
                str(state_dir),
                "--port",
                "0",
                "--start-timeout",
                "20",
                "--json",
            ],
            env=env,
        )
        assert start_proc.returncode == 0, (
            f"mcp start failed: stdout={start_proc.stdout!r} "
            f"stderr={start_proc.stderr!r}"
        )
        start_payload = json.loads(start_proc.stdout)
        assert start_payload["status"] == "started"
        assert start_payload["host"] == "127.0.0.1"
        assert isinstance(start_payload["port"], int) and start_payload["port"] > 0

        # 2) mcp.runtime.json contains the locked 5-field schema.
        runtime_path = state_dir / "mcp.runtime.json"
        assert runtime_path.exists(), "mcp.runtime.json not written"
        runtime = json.loads(runtime_path.read_text())
        for field in ("host", "port", "pid", "started_at", "transport"):
            assert field in runtime, f"missing field {field} in {runtime}"
        assert runtime["host"] == "127.0.0.1"
        assert runtime["transport"] == "http"
        mode = runtime_path.stat().st_mode & 0o777
        assert mode == 0o600, f"runtime file perms {oct(mode)} not 0o600"

        try:
            # 3) query via --transport mcp --mcp-transport http WITHOUT --mcp-url.
            # The CLI must auto-discover from mcp.runtime.json.
            query_proc = _run(
                [
                    sys.executable,
                    "-m",
                    "agent_brain_cli",
                    "--transport",
                    "mcp",
                    "--mcp-transport",
                    "http",
                    "query",
                    "echo",
                    "--json",
                ],
                env=env,
            )
            assert query_proc.returncode == 0, (
                f"discovery-based query failed: "
                f"stdout={query_proc.stdout!r} stderr={query_proc.stderr!r}"
            )
            # JSON parses + has chunks-shaped output. Don't pin contents —
            # the byte-equivalence DoD is Plan 57-02's job.
            query_payload = json.loads(query_proc.stdout)
            assert isinstance(query_payload, dict)

        finally:
            # 4) mcp stop — must clean up runtime + lock even on test failure.
            stop_proc = _run(
                [
                    sys.executable,
                    "-m",
                    "agent_brain_cli",
                    "mcp",
                    "stop",
                    "--state-dir",
                    str(state_dir),
                    "--json",
                ],
                env=env,
            )
            assert stop_proc.returncode == 0, (
                f"mcp stop failed: stdout={stop_proc.stdout!r} "
                f"stderr={stop_proc.stderr!r}"
            )
            # 5) runtime + lock gone after stop.
            assert not runtime_path.exists(), "mcp.runtime.json not cleaned up"
            lock_path = state_dir / "agent-brain-mcp.lock"
            assert not lock_path.exists(), "lock file not released"


def test_mcp_stop_idempotent_when_nothing_running(tmp_path: Path) -> None:
    """stop with no runtime exits 0 — does not require OPENAI_API_KEY."""
    _require_psutil()
    state_dir = tmp_path / ".agent-brain"
    state_dir.mkdir()
    env = {**os.environ, "AGENT_BRAIN_STATE_DIR": str(state_dir)}
    proc = _run(
        [
            sys.executable,
            "-m",
            "agent_brain_cli",
            "mcp",
            "stop",
            "--state-dir",
            str(state_dir),
            "--json",
        ],
        env=env,
    )
    assert proc.returncode == 0, (
        f"stop should be idempotent: stdout={proc.stdout!r} " f"stderr={proc.stderr!r}"
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == "not_running"


def test_discovery_error_wording_matches_section_3_5(tmp_path: Path) -> None:
    """No url, no runtime → CLI fails with verbatim §3.5 wording.

    Cheap to run (no OPENAI_API_KEY, no real server) — proves the
    no-silent-fallback contract from outside the process.

    Runs with cwd=tmp_path so the dispatcher's state-dir resolution
    chain lands inside the clean tmp_path (the developer machine may
    have its own ``.agent-brain/mcp.runtime.json`` higher up — that
    would defeat the §3.5 wording assertion). Also strips
    AGENT_BRAIN_MCP_URL and AGENT_BRAIN_MCP_TRANSPORT env vars so the
    test is hermetic.
    """
    state_dir = tmp_path / ".agent-brain"
    state_dir.mkdir()
    # Strip every var that would route the query around the MCP dispatcher.
    # AGENT_BRAIN_URL is honored by query's --url envvar — leaving it set
    # silently routes through the HTTP path and defeats the §3.5 check.
    stripped_env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "AGENT_BRAIN_MCP_URL",
            "AGENT_BRAIN_MCP_TRANSPORT",
            "AGENT_BRAIN_URL",
            "AGENT_BRAIN_TRANSPORT",
        }
    }
    env = {**stripped_env, "AGENT_BRAIN_STATE_DIR": str(state_dir)}
    proc = _run(
        [
            sys.executable,
            "-m",
            "agent_brain_cli",
            "--transport",
            "mcp",
            "--mcp-transport",
            "http",
            "query",
            "anything",
        ],
        env=env,
        timeout=15.0,
        cwd=tmp_path,
    )
    assert proc.returncode == 2, (
        f"expected exit 2 (UsageError); got {proc.returncode}. "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    combined = proc.stdout + proc.stderr
    assert (
        "discovery file not found at" in combined
    ), f"§3.5 wording missing from CLI output: {combined!r}"
    assert (
        "run 'agent-brain mcp start' or pass --mcp-url" in combined
    ), f"§3.5 hint missing from CLI output: {combined!r}"
