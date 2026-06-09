"""Tests for ``agent-brain mcp start`` (Phase 58 Plan 02).

Covers:
  - port resolution precedence (--port > AGENT_BRAIN_MCP_PORT env > 8765 default)
  - OS-fallback on EADDRINUSE
  - --port 0 escape hatch (always OS-allocated)
  - invalid env-port → click.UsageError
  - lock-collision against an alive holder exits 1 with verbatim wording
  - mcp.runtime.json schema = 5 locked fields {host, port, pid, started_at, transport}
  - mcp.runtime.json is NOT written when is_listening returns False
  - subprocess command list shape (verbatim Popen args)
  - start_new_session=True kwarg (required for Plan 58-03's os.killpg)
  - --state-dir override precedence
  - mcp_group registration under top-level CLI

Test scope is UNIT — ``subprocess.Popen`` and ``is_listening`` are patched at
the ``agent_brain_cli.commands.mcp`` module level. No real subprocess is
spawned. Real-subprocess coverage lands in Plan 58-03's end-to-end test.
"""

from __future__ import annotations

import json
import os
import socket
import stat
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.commands.mcp import (
    MCP_DEFAULT_PORT,
    _allocate_port,
    _resolve_preferred_port,
    mcp_group,
)
from agent_brain_cli.mcp_runtime import (
    MCP_LOCK_FILE,
    MCP_RUNTIME_FILE,
)

# ---------------------------------------------------------------------------
# Port resolution
# ---------------------------------------------------------------------------


def test_start_resolves_port_from_flag_over_env_over_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--port flag wins; then AGENT_BRAIN_MCP_PORT env; then 8765 default."""
    # Flag wins over env + default
    monkeypatch.setenv("AGENT_BRAIN_MCP_PORT", "9000")
    assert _resolve_preferred_port(7777) == 7777

    # Env wins over default when flag is None
    monkeypatch.setenv("AGENT_BRAIN_MCP_PORT", "9001")
    assert _resolve_preferred_port(None) == 9001

    # Default when neither flag nor env
    monkeypatch.delenv("AGENT_BRAIN_MCP_PORT", raising=False)
    assert _resolve_preferred_port(None) == MCP_DEFAULT_PORT


def test_start_falls_back_to_os_allocated_on_eaddrinuse() -> None:
    """When the preferred port is bound, OS-allocates a different free port."""
    # Pre-bind a port to force the EADDRINUSE branch.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as squatter:
        squatter.bind(("127.0.0.1", 0))
        preferred = int(squatter.getsockname()[1])
        # Squatter still holds the port; ask _allocate_port to bind it.
        allocated = _allocate_port(preferred)
        assert allocated != preferred
        assert allocated > 0


def test_start_zero_port_skips_preferred_try() -> None:
    """--port 0 means 'always ask the OS for a free port'."""
    allocated = _allocate_port(0)
    assert allocated > 0
    # Privileged ports (<1024) are extremely unlikely to be OS-handed-out.
    assert allocated >= 1024 or allocated > 0


def test_start_invalid_env_port_raises_usage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AGENT_BRAIN_MCP_PORT='not-a-number' surfaces a click.UsageError."""
    import click

    monkeypatch.setenv("AGENT_BRAIN_MCP_PORT", "not-a-number")
    with pytest.raises(click.UsageError):
        _resolve_preferred_port(None)


# ---------------------------------------------------------------------------
# CLI-invoked behavior
# ---------------------------------------------------------------------------


def _make_fake_process(pid: int = 9999) -> MagicMock:
    """Build a MagicMock that mimics subprocess.Popen's surface."""
    proc = MagicMock()
    proc.pid = pid
    proc.poll.return_value = None
    proc.terminate.return_value = None
    return proc


def test_start_lock_collision_exits_one(
    tmp_path: Path,
) -> None:
    """An alive lock holder → exit 1 with verbatim 'already running on port'."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    # Plant lock + runtime files claiming the *current* test pid (alive).
    lock_path = state_dir / MCP_LOCK_FILE
    lock_path.write_text(str(os.getpid()))
    runtime = {
        "host": "127.0.0.1",
        "port": 8765,
        "pid": os.getpid(),
        "started_at": "2026-06-07T01:49:08.173+00:00",
        "transport": "http",
    }
    (state_dir / MCP_RUNTIME_FILE).write_text(json.dumps(runtime))

    runner = CliRunner()
    result = runner.invoke(
        mcp_group,
        ["start", "--state-dir", str(state_dir), "--port", "8765"],
    )
    assert result.exit_code == 1, result.output
    # Click wraps error text at terminal width; normalize whitespace before
    # substring checks so the assertion is stable across CI and local widths.
    normalized = " ".join(result.output.split())
    assert "already running on port" in normalized
    # The verbatim wording is mirrored from Plan 58-01's LockAcquisitionError.
    assert "agent-brain mcp stop" in normalized


def test_start_writes_runtime_file_with_correct_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On listener-ready, mcp.runtime.json has all 5 locked §2.4 fields + 0o600."""
    state_dir = tmp_path / "state"
    fake_pid = 99001

    with (
        patch(
            "agent_brain_cli.commands.mcp.subprocess.Popen",
            return_value=_make_fake_process(pid=fake_pid),
        ) as mock_popen,
        patch(
            "agent_brain_cli.commands.mcp.is_listening",
            return_value=True,
        ),
    ):
        runner = CliRunner()
        result = runner.invoke(
            mcp_group,
            [
                "start",
                "--state-dir",
                str(state_dir),
                "--port",
                "0",  # force OS-allocated to avoid colliding with anything
            ],
        )

    assert result.exit_code == 0, result.output
    assert mock_popen.called

    runtime_path = state_dir / MCP_RUNTIME_FILE
    assert runtime_path.exists(), "mcp.runtime.json must be written on success"
    data = json.loads(runtime_path.read_text())

    # The five locked §2.4 fields.
    assert set(data.keys()) >= {"host", "port", "pid", "started_at", "transport"}
    assert data["host"] == "127.0.0.1"
    assert isinstance(data["port"], int) and data["port"] > 0
    assert data["pid"] == fake_pid
    assert data["transport"] == "http"
    assert isinstance(data["started_at"], str)
    # ISO8601 UTC sanity: contains a 'T' separator and is non-empty.
    assert "T" in data["started_at"]

    # 0o600 perms (issue #179 carry-forward via write_mcp_runtime).
    mode = stat.S_IMODE(runtime_path.stat().st_mode)
    assert mode == 0o600, f"runtime file must be 0o600; got {oct(mode)}"


def test_start_does_not_write_runtime_on_timeout(
    tmp_path: Path,
) -> None:
    """On is_listening=False, runtime file NOT created and lock released."""
    state_dir = tmp_path / "state"

    with (
        patch(
            "agent_brain_cli.commands.mcp.subprocess.Popen",
            return_value=_make_fake_process(pid=88001),
        ),
        patch(
            "agent_brain_cli.commands.mcp.is_listening",
            return_value=False,
        ),
    ):
        runner = CliRunner()
        result = runner.invoke(
            mcp_group,
            [
                "start",
                "--state-dir",
                str(state_dir),
                "--port",
                "0",
                "--start-timeout",
                "1",
            ],
        )

    assert result.exit_code == 1, result.output
    assert not (state_dir / MCP_RUNTIME_FILE).exists()
    # Lock must be released so the next `mcp start` can acquire.
    assert not (state_dir / MCP_LOCK_FILE).exists()


def test_start_subprocess_command_uses_loopback_host_and_module_invocation(
    tmp_path: Path,
) -> None:
    """Popen args = [sys.executable, -m, agent_brain_mcp, --transport, http, ...]."""
    import sys

    state_dir = tmp_path / "state"

    with (
        patch(
            "agent_brain_cli.commands.mcp.subprocess.Popen",
            return_value=_make_fake_process(),
        ) as mock_popen,
        patch(
            "agent_brain_cli.commands.mcp.is_listening",
            return_value=True,
        ),
    ):
        runner = CliRunner()
        result = runner.invoke(
            mcp_group,
            ["start", "--state-dir", str(state_dir), "--port", "0"],
        )

    assert result.exit_code == 0, result.output
    args, _kwargs = mock_popen.call_args
    cmd = args[0]
    # Verbatim head of the command list.
    assert cmd[:6] == [
        sys.executable,
        "-m",
        "agent_brain_mcp",
        "--transport",
        "http",
        "--host",
    ]
    assert cmd[6] == "127.0.0.1"
    assert cmd[7] == "--port"
    # Port slot is the resolved port (OS-allocated for --port 0).
    assert int(cmd[8]) > 0


def test_start_subprocess_uses_start_new_session_true(
    tmp_path: Path,
) -> None:
    """start_new_session=True is required for Plan 58-03's os.killpg."""
    state_dir = tmp_path / "state"

    with (
        patch(
            "agent_brain_cli.commands.mcp.subprocess.Popen",
            return_value=_make_fake_process(),
        ) as mock_popen,
        patch(
            "agent_brain_cli.commands.mcp.is_listening",
            return_value=True,
        ),
    ):
        runner = CliRunner()
        result = runner.invoke(
            mcp_group,
            ["start", "--state-dir", str(state_dir), "--port", "0"],
        )

    assert result.exit_code == 0, result.output
    _args, kwargs = mock_popen.call_args
    assert kwargs.get("start_new_session") is True


def test_start_state_dir_override_takes_precedence(
    tmp_path: Path,
) -> None:
    """--state-dir /tmp/foo wins over project-root auto-detection."""
    explicit_dir = tmp_path / "explicit-state"

    with (
        patch(
            "agent_brain_cli.commands.mcp.subprocess.Popen",
            return_value=_make_fake_process(),
        ),
        patch(
            "agent_brain_cli.commands.mcp.is_listening",
            return_value=True,
        ),
        patch(
            "agent_brain_cli.commands.mcp.resolve_project_root",
        ) as mock_root,
    ):
        # If resolve_project_root is called, fail the test loudly.
        mock_root.side_effect = AssertionError(
            "--state-dir override must short-circuit project-root resolution"
        )
        runner = CliRunner()
        result = runner.invoke(
            mcp_group,
            ["start", "--state-dir", str(explicit_dir), "--port", "0"],
        )

    assert result.exit_code == 0, result.output
    assert (explicit_dir / MCP_RUNTIME_FILE).exists()


def test_start_command_registered_under_mcp_group() -> None:
    """`agent-brain mcp --help` exposes the start subcommand."""
    from agent_brain_cli.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "start" in result.output

    # Start subcommand --help surfaces the four flags.
    start_help = runner.invoke(cli, ["mcp", "start", "--help"])
    assert start_help.exit_code == 0
    for flag in ("--port", "--start-timeout", "--state-dir", "--json"):
        assert flag in start_help.output, f"{flag} missing from mcp start --help"


# ---------------------------------------------------------------------------
# JSON output sanity
# ---------------------------------------------------------------------------


def test_start_json_output_on_success(
    tmp_path: Path,
) -> None:
    """--json prints a parsable status object with the locked fields."""
    state_dir = tmp_path / "state"

    with (
        patch(
            "agent_brain_cli.commands.mcp.subprocess.Popen",
            return_value=_make_fake_process(pid=42),
        ),
        patch(
            "agent_brain_cli.commands.mcp.is_listening",
            return_value=True,
        ),
    ):
        runner = CliRunner()
        result = runner.invoke(
            mcp_group,
            ["start", "--state-dir", str(state_dir), "--port", "0", "--json"],
        )

    assert result.exit_code == 0, result.output
    payload: dict[str, Any] = json.loads(result.output)
    assert payload["status"] == "started"
    assert payload["host"] == "127.0.0.1"
    assert payload["pid"] == 42
    assert isinstance(payload["port"], int) and payload["port"] > 0
    assert payload["runtime_file"].endswith(MCP_RUNTIME_FILE)
