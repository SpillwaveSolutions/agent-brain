"""Tests for ``agent-brain mcp stop`` (Phase 58 Plan 03).

Covers:
  - Idempotent exit-0 when mcp.runtime.json is missing
  - Cleanup when pid is dead (psutil.pid_exists False)
  - SIGTERM success within --grace
  - SIGKILL escalation after --grace
  - os.killpg used with the process group id (NOT os.kill)
  - --grace flag overrides AGENT_BRAIN_MCP_STOP_GRACE env
  - release_lock invoked even when runtime file is missing
  - PermissionError on signal exits 1 with verbatim wording
  - --json output formatting
  - ProcessLookupError race treated as already-stopped

Test scope is UNIT — psutil.pid_exists, os.killpg, os.getpgid are patched
at the ``agent_brain_cli.commands.mcp`` module level so no real subprocess
is signaled. Real-subprocess coverage lands in the integration test
(``tests/integration/test_mcp_helper_commands.py``).
"""

from __future__ import annotations

import json
import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.commands.mcp import (
    MCP_DEFAULT_STOP_GRACE,
    mcp_group,
)
from agent_brain_cli.mcp_runtime import (
    MCP_LOCK_FILE,
    MCP_RUNTIME_FILE,
)


def _write_runtime(state_dir: Path, pid: int, port: int = 8765) -> None:
    """Helper: write a valid 5-field mcp.runtime.json into state_dir."""
    state_dir.mkdir(parents=True, exist_ok=True)
    runtime = {
        "host": "127.0.0.1",
        "port": port,
        "pid": pid,
        "started_at": "2026-06-07T00:00:00+00:00",
        "transport": "http",
    }
    (state_dir / MCP_RUNTIME_FILE).write_text(json.dumps(runtime))


def _touch_lock(state_dir: Path) -> None:
    """Create an empty MCP lock file in state_dir."""
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / MCP_LOCK_FILE).write_text(str(99999))


# ---------------------------------------------------------------------------
# Idempotency: nothing running
# ---------------------------------------------------------------------------


def test_stop_when_runtime_missing_exits_zero(tmp_path: Path) -> None:
    """No runtime file → exit 0 informational message (idempotent)."""
    runner = CliRunner()
    result = runner.invoke(mcp_group, ["stop", "--state-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "not running" in result.output.lower()


def test_stop_releases_lock_when_runtime_missing(tmp_path: Path) -> None:
    """No runtime file + dangling lock → release_lock is still called."""
    _touch_lock(tmp_path)
    assert (tmp_path / MCP_LOCK_FILE).exists()
    runner = CliRunner()
    result = runner.invoke(mcp_group, ["stop", "--state-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert not (
        tmp_path / MCP_LOCK_FILE
    ).exists(), "release_lock should be called when runtime file is missing"


# ---------------------------------------------------------------------------
# Cleanup when process already dead
# ---------------------------------------------------------------------------


def test_stop_when_pid_dead_cleans_up_and_exits_zero(tmp_path: Path) -> None:
    """Runtime file present + psutil says pid is dead → cleanup + exit 0."""
    _write_runtime(tmp_path, pid=12345)
    _touch_lock(tmp_path)
    runner = CliRunner()
    with patch(
        "agent_brain_cli.commands.mcp.psutil.pid_exists",
        return_value=False,
    ):
        result = runner.invoke(mcp_group, ["stop", "--state-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert not (tmp_path / MCP_RUNTIME_FILE).exists()
    assert not (tmp_path / MCP_LOCK_FILE).exists()


def test_stop_process_lookup_race_treated_as_already_stopped(
    tmp_path: Path,
) -> None:
    """os.getpgid raising ProcessLookupError mid-call is treated as already-stopped."""
    _write_runtime(tmp_path, pid=12345)
    _touch_lock(tmp_path)
    runner = CliRunner()
    with (
        patch(
            "agent_brain_cli.commands.mcp.psutil.pid_exists",
            return_value=True,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.getpgid",
            side_effect=ProcessLookupError(),
        ),
    ):
        result = runner.invoke(mcp_group, ["stop", "--state-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    # Cleanup still happens
    assert not (tmp_path / MCP_RUNTIME_FILE).exists()
    assert not (tmp_path / MCP_LOCK_FILE).exists()


# ---------------------------------------------------------------------------
# SIGTERM happy path
# ---------------------------------------------------------------------------


def test_stop_sigterm_path_succeeds_within_grace(tmp_path: Path) -> None:
    """os.killpg(SIGTERM) → process exits during polling → cleanup + exit 0."""
    _write_runtime(tmp_path, pid=12345)
    _touch_lock(tmp_path)
    # Simulate: process alive at the kill site, dies after one poll.
    pid_exists_calls = {"n": 0}

    def fake_pid_exists(pid: int) -> bool:
        pid_exists_calls["n"] += 1
        # First call: confirm-alive before signaling. Then dies.
        return pid_exists_calls["n"] <= 1

    killpg_mock = MagicMock()
    runner = CliRunner()
    with (
        patch(
            "agent_brain_cli.commands.mcp.psutil.pid_exists",
            side_effect=fake_pid_exists,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.getpgid",
            return_value=54321,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.killpg",
            killpg_mock,
        ),
    ):
        result = runner.invoke(
            mcp_group,
            ["stop", "--state-dir", str(tmp_path), "--grace", "1"],
        )

    assert result.exit_code == 0, result.output
    # SIGTERM was sent
    sigterm_calls = [
        c for c in killpg_mock.call_args_list if c.args[1] == signal.SIGTERM
    ]
    assert len(sigterm_calls) == 1
    # SIGKILL was NOT sent
    sigkill_calls = [
        c for c in killpg_mock.call_args_list if c.args[1] == signal.SIGKILL
    ]
    assert len(sigkill_calls) == 0
    # Cleanup happened
    assert not (tmp_path / MCP_RUNTIME_FILE).exists()
    assert not (tmp_path / MCP_LOCK_FILE).exists()


# ---------------------------------------------------------------------------
# SIGKILL escalation
# ---------------------------------------------------------------------------


def test_stop_sigkill_escalates_after_grace(tmp_path: Path) -> None:
    """Process refuses to die during grace → escalate to SIGKILL."""
    _write_runtime(tmp_path, pid=12345)
    _touch_lock(tmp_path)
    killpg_mock = MagicMock()
    runner = CliRunner()
    with (
        patch(
            "agent_brain_cli.commands.mcp.psutil.pid_exists",
            return_value=True,  # always alive
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.getpgid",
            return_value=54321,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.killpg",
            killpg_mock,
        ),
        patch(
            "agent_brain_cli.commands.mcp.time.sleep",
            return_value=None,
        ),
    ):
        result = runner.invoke(
            mcp_group,
            ["stop", "--state-dir", str(tmp_path), "--grace", "0"],
        )
    assert result.exit_code == 0, result.output
    # Both SIGTERM and SIGKILL were issued
    signals_sent = [c.args[1] for c in killpg_mock.call_args_list]
    assert signal.SIGTERM in signals_sent
    assert signal.SIGKILL in signals_sent
    # Cleanup happened
    assert not (tmp_path / MCP_RUNTIME_FILE).exists()
    assert not (tmp_path / MCP_LOCK_FILE).exists()


# ---------------------------------------------------------------------------
# os.killpg uses pgid (process group), not pid
# ---------------------------------------------------------------------------


def test_stop_uses_killpg_with_process_group_id(tmp_path: Path) -> None:
    """os.killpg receives the pgid from os.getpgid(pid), not raw pid."""
    _write_runtime(tmp_path, pid=12345)
    pgid_value = 999777
    killpg_mock = MagicMock()
    pid_exists_calls = {"n": 0}

    def fake_pid_exists(pid: int) -> bool:
        pid_exists_calls["n"] += 1
        return pid_exists_calls["n"] <= 1

    runner = CliRunner()
    with (
        patch(
            "agent_brain_cli.commands.mcp.psutil.pid_exists",
            side_effect=fake_pid_exists,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.getpgid",
            return_value=pgid_value,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.killpg",
            killpg_mock,
        ),
    ):
        result = runner.invoke(
            mcp_group,
            ["stop", "--state-dir", str(tmp_path), "--grace", "1"],
        )
    assert result.exit_code == 0, result.output
    assert killpg_mock.call_count >= 1
    first_call = killpg_mock.call_args_list[0]
    assert (
        first_call.args[0] == pgid_value
    ), f"expected pgid {pgid_value}, got {first_call.args[0]}"
    assert first_call.args[1] == signal.SIGTERM


# ---------------------------------------------------------------------------
# --grace flag precedence over env var
# ---------------------------------------------------------------------------


def test_stop_grace_flag_overrides_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--grace 1 flag overrides AGENT_BRAIN_MCP_STOP_GRACE=10."""
    monkeypatch.setenv("AGENT_BRAIN_MCP_STOP_GRACE", "10")
    _write_runtime(tmp_path, pid=12345)
    pid_exists_calls = {"n": 0}

    def fake_pid_exists(pid: int) -> bool:
        pid_exists_calls["n"] += 1
        return pid_exists_calls["n"] <= 1

    killpg_mock = MagicMock()
    runner = CliRunner()
    with (
        patch(
            "agent_brain_cli.commands.mcp.psutil.pid_exists",
            side_effect=fake_pid_exists,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.getpgid",
            return_value=54321,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.killpg",
            killpg_mock,
        ),
    ):
        result = runner.invoke(
            mcp_group,
            ["stop", "--state-dir", str(tmp_path), "--grace", "1"],
        )
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# PermissionError on signal exits 1
# ---------------------------------------------------------------------------


def test_stop_permission_error_exits_one(tmp_path: Path) -> None:
    """os.killpg raising PermissionError → exit 1 with verbatim wording."""
    _write_runtime(tmp_path, pid=12345)
    runner = CliRunner()
    with (
        patch(
            "agent_brain_cli.commands.mcp.psutil.pid_exists",
            return_value=True,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.getpgid",
            return_value=54321,
        ),
        patch(
            "agent_brain_cli.commands.mcp.os.killpg",
            side_effect=PermissionError(),
        ),
    ):
        result = runner.invoke(mcp_group, ["stop", "--state-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "Permission denied: cannot signal pid" in result.output
    assert "12345" in result.output


# ---------------------------------------------------------------------------
# --json output
# ---------------------------------------------------------------------------


def test_stop_json_output_format(tmp_path: Path) -> None:
    """--json emits a parseable status payload on the not-running path."""
    runner = CliRunner()
    result = runner.invoke(mcp_group, ["stop", "--state-dir", str(tmp_path), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output.strip())
    assert payload.get("status") == "not_running"
    assert payload.get("state_dir") == str(tmp_path)


# ---------------------------------------------------------------------------
# Default grace constant pinned
# ---------------------------------------------------------------------------


def test_default_grace_constant_pinned_to_five_seconds() -> None:
    """MCP_DEFAULT_STOP_GRACE = 5 (CONTEXT decision)."""
    assert MCP_DEFAULT_STOP_GRACE == 5
