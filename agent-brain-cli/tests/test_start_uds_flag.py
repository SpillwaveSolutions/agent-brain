"""Phase 2 TDD: ``agent-brain start --uds`` / ``--uds-only`` CLI flags.

These flags don't influence the CLI's own behavior — they just pass through
``AGENT_BRAIN_UDS=1`` / ``AGENT_BRAIN_UDS_ONLY=1`` (and recorded via runtime.json
``socket_path``) so the server boots with the right bind. We assert on the
subprocess env, not on real server boot.

Maps to plan §12.3 acceptance #3 (supporting) and Phase 3 acceptance #7
(``--uds-only`` collision). RED until Phase 2 ships the flags.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.commands.init import init_command
from agent_brain_cli.commands.start import start_command


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def initialized_project(tmp_path: Path, runner: CliRunner) -> Path:
    """A project that's already been `agent-brain init`'d."""
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'test'\n")
    result = runner.invoke(init_command, ["--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    return tmp_path


def _popen_env_capture(popen_calls: list[dict[str, str]]):
    """Build a Popen mock that captures the env arg into popen_calls."""
    fake_process = MagicMock()
    fake_process.pid = 99999
    fake_process.poll.return_value = None

    def _fake_popen(cmd, env=None, **kwargs):  # type: ignore[no-untyped-def]
        popen_calls.append(dict(env or {}))
        return fake_process

    return _fake_popen


class TestUdsFlag:
    """``--uds`` enables dual bind without disabling HTTP."""

    def test_uds_flag_exists(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """``agent-brain start --help`` mentions --uds."""
        result = runner.invoke(start_command, ["--help"])
        assert result.exit_code == 0
        assert "--uds" in result.output

    def test_uds_flag_passes_env_to_server(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """``--uds`` results in AGENT_BRAIN_UDS=1 in the spawned env."""
        popen_calls: list[dict[str, str]] = []
        with (
            patch(
                "agent_brain_cli.commands.start.subprocess.Popen",
                side_effect=_popen_env_capture(popen_calls),
            ),
            patch("agent_brain_cli.commands.start.check_health", return_value=True),
        ):
            result = runner.invoke(
                start_command,
                ["--path", str(initialized_project), "--uds", "--json"],
            )

        assert result.exit_code == 0, result.output
        assert popen_calls, "subprocess.Popen was not called"
        env = popen_calls[-1]
        assert env.get("AGENT_BRAIN_UDS") == "1"
        # Plain --uds keeps HTTP bound alongside UDS
        assert env.get("AGENT_BRAIN_UDS_ONLY") in (None, "0", "")


class TestUdsOnlyFlag:
    """``--uds-only`` disables the TCP bind entirely."""

    def test_uds_only_flag_exists(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        result = runner.invoke(start_command, ["--help"])
        assert "--uds-only" in result.output

    def test_uds_only_implies_uds(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """``--uds-only`` sets both AGENT_BRAIN_UDS=1 and AGENT_BRAIN_UDS_ONLY=1."""
        popen_calls: list[dict[str, str]] = []
        with (
            patch(
                "agent_brain_cli.commands.start.subprocess.Popen",
                side_effect=_popen_env_capture(popen_calls),
            ),
            patch("agent_brain_cli.commands.start.check_health", return_value=True),
        ):
            result = runner.invoke(
                start_command,
                ["--path", str(initialized_project), "--uds-only", "--json"],
            )

        assert result.exit_code == 0, result.output
        env = popen_calls[-1]
        assert env.get("AGENT_BRAIN_UDS") == "1"
        assert env.get("AGENT_BRAIN_UDS_ONLY") == "1"


class TestDefaultBehaviorUnchanged:
    """Without ``--uds``, env is unchanged from today's behavior."""

    def test_no_uds_env_when_flag_absent(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        popen_calls: list[dict[str, str]] = []
        with (
            patch(
                "agent_brain_cli.commands.start.subprocess.Popen",
                side_effect=_popen_env_capture(popen_calls),
            ),
            patch("agent_brain_cli.commands.start.check_health", return_value=True),
        ):
            result = runner.invoke(
                start_command,
                ["--path", str(initialized_project), "--json"],
            )

        assert result.exit_code == 0, result.output
        env = popen_calls[-1]
        # The new env vars must be absent (or "0") when the flag is not used —
        # bit-for-bit identical behavior for existing users.
        assert env.get("AGENT_BRAIN_UDS") in (None, "0", "")
        assert env.get("AGENT_BRAIN_UDS_ONLY") in (None, "0", "")


class TestRuntimeSocketPath:
    """When --uds is set, runtime.json gains ``socket_path``."""

    def test_runtime_json_includes_socket_path_with_uds(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        """Server start with --uds populates runtime.json::socket_path."""
        popen_calls: list[dict[str, str]] = []
        with (
            patch(
                "agent_brain_cli.commands.start.subprocess.Popen",
                side_effect=_popen_env_capture(popen_calls),
            ),
            patch("agent_brain_cli.commands.start.check_health", return_value=True),
        ):
            result = runner.invoke(
                start_command,
                ["--path", str(initialized_project), "--uds", "--json"],
            )

        assert result.exit_code == 0, result.output
        runtime_path = initialized_project / ".agent-brain" / "runtime.json"
        assert runtime_path.exists()
        runtime = json.loads(runtime_path.read_text())
        assert "socket_path" in runtime
        assert runtime["socket_path"], "socket_path must be a non-empty string"


class TestJsonOutputIncludesSocketPath:
    """``--uds --json`` output reports the socket path so callers can connect."""

    def test_json_output_includes_socket_path(
        self, runner: CliRunner, initialized_project: Path
    ) -> None:
        with (
            patch(
                "agent_brain_cli.commands.start.subprocess.Popen",
                side_effect=_popen_env_capture([]),
            ),
            patch("agent_brain_cli.commands.start.check_health", return_value=True),
        ):
            result = runner.invoke(
                start_command,
                ["--path", str(initialized_project), "--uds", "--json"],
            )

        assert result.exit_code == 0, result.output
        try:
            data = json.loads(result.output)
        except json.JSONDecodeError as exc:
            pytest.fail(f"--json output not valid JSON: {result.output!r} ({exc})")
        assert "socket_path" in data
