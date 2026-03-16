"""Tests for the agent-brain uninstall command."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli
from agent_brain_cli.commands.uninstall import uninstall_command


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


class TestUninstallRemovesDirs:
    """Tests for directory removal behavior."""

    def test_removes_global_dirs(self, runner: CliRunner, tmp_path: Path) -> None:
        """Creates fake dirs at XDG + legacy paths, verify removed."""
        xdg_config = tmp_path / "config" / "agent-brain"
        xdg_config.mkdir(parents=True)
        xdg_state = tmp_path / "state" / "agent-brain"
        xdg_state.mkdir(parents=True)
        legacy = tmp_path / ".agent-brain"
        legacy.mkdir()

        with (
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_config_dir",
                return_value=xdg_config,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_state_dir",
                return_value=xdg_state,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.LEGACY_DIR",
                new=legacy,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_registry_path",
                return_value=xdg_state / "registry.json",
            ),
        ):
            result = runner.invoke(uninstall_command, ["--yes"])

        assert result.exit_code == 0
        assert not xdg_config.exists()
        assert not xdg_state.exists()
        assert not legacy.exists()

    def test_nothing_to_remove(self, runner: CliRunner, tmp_path: Path) -> None:
        """No dirs exist — verify clean exit with 'Nothing to remove' message."""
        xdg_config = tmp_path / "config" / "agent-brain"
        xdg_state = tmp_path / "state" / "agent-brain"
        legacy = tmp_path / ".agent-brain"

        # None of these exist

        with (
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_config_dir",
                return_value=xdg_config,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_state_dir",
                return_value=xdg_state,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.LEGACY_DIR",
                new=legacy,
            ),
        ):
            result = runner.invoke(uninstall_command, ["--yes"])

        assert result.exit_code == 0
        assert "nothing to remove" in result.output.lower()

    def test_does_not_touch_project_dirs(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Does NOT remove any .claude/agent-brain/ project directories."""
        xdg_config = tmp_path / "config" / "agent-brain"
        xdg_config.mkdir(parents=True)
        xdg_state = tmp_path / "state" / "agent-brain"
        xdg_state.mkdir(parents=True)
        legacy = tmp_path / ".agent-brain"

        # Create a project-level .claude/agent-brain dir
        project_dir = tmp_path / "myproject" / ".claude" / "agent-brain"
        project_dir.mkdir(parents=True)
        (project_dir / "config.json").write_text('{"port": 8000}')

        with (
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_config_dir",
                return_value=xdg_config,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_state_dir",
                return_value=xdg_state,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.LEGACY_DIR",
                new=legacy,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_registry_path",
                return_value=xdg_state / "registry.json",
            ),
        ):
            result = runner.invoke(uninstall_command, ["--yes"])

        assert result.exit_code == 0
        # Project dir should still exist
        assert project_dir.exists()
        assert (project_dir / "config.json").exists()


class TestUninstallConfirmation:
    """Tests for confirmation prompt behavior."""

    def test_confirmation_prompt_aborts_on_n(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Without --yes, prompts for confirmation; 'n' aborts without removing."""
        xdg_config = tmp_path / "config" / "agent-brain"
        xdg_config.mkdir(parents=True)
        xdg_state = tmp_path / "state" / "agent-brain"
        legacy = tmp_path / ".agent-brain"

        with (
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_config_dir",
                return_value=xdg_config,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_state_dir",
                return_value=xdg_state,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.LEGACY_DIR",
                new=legacy,
            ),
        ):
            result = runner.invoke(uninstall_command, input="n\n")

        assert result.exit_code == 0
        # Dirs should NOT be removed
        assert xdg_config.exists()
        assert "aborted" in result.output.lower()

    def test_yes_flag_skips_prompt(self, runner: CliRunner, tmp_path: Path) -> None:
        """--yes skips confirmation and proceeds directly."""
        xdg_config = tmp_path / "config" / "agent-brain"
        xdg_config.mkdir(parents=True)
        xdg_state = tmp_path / "state" / "agent-brain"
        legacy = tmp_path / ".agent-brain"

        with (
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_config_dir",
                return_value=xdg_config,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_state_dir",
                return_value=xdg_state,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.LEGACY_DIR",
                new=legacy,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_registry_path",
                return_value=xdg_state / "registry.json",
            ),
        ):
            result = runner.invoke(uninstall_command, ["--yes"])

        assert result.exit_code == 0
        assert not xdg_config.exists()


class TestUninstallServerStop:
    """Tests for server auto-stop behavior."""

    def test_stops_servers_first(self, runner: CliRunner, tmp_path: Path) -> None:
        """Reads registry with PIDs, sends SIGTERM before removing dirs."""
        xdg_config = tmp_path / "config" / "agent-brain"
        xdg_config.mkdir(parents=True)
        xdg_state = tmp_path / "state" / "agent-brain"
        xdg_state.mkdir(parents=True)
        legacy = tmp_path / ".agent-brain"

        # Create registry with a PID
        registry_path = xdg_state / "registry.json"
        fake_pid = 99999
        state_dir = tmp_path / "myproject" / ".claude" / "agent-brain"
        state_dir.mkdir(parents=True)
        runtime_file = state_dir / "runtime.json"
        runtime_file.write_text(
            json.dumps({"pid": fake_pid, "base_url": "http://127.0.0.1:8000"})
        )

        registry = {
            str(tmp_path / "myproject"): {
                "state_dir": str(state_dir),
                "project_name": "myproject",
            }
        }
        registry_path.write_text(json.dumps(registry))

        killed_pids: list[int] = []

        def fake_kill(pid: int, sig: int) -> None:
            killed_pids.append(pid)

        with (
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_config_dir",
                return_value=xdg_config,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_state_dir",
                return_value=xdg_state,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.LEGACY_DIR",
                new=legacy,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_registry_path",
                return_value=registry_path,
            ),
            patch("os.kill", side_effect=fake_kill),
        ):
            result = runner.invoke(uninstall_command, ["--yes"])

        assert result.exit_code == 0
        assert fake_pid in killed_pids


class TestUninstallJsonOutput:
    """Tests for JSON output mode."""

    def test_json_output(self, runner: CliRunner, tmp_path: Path) -> None:
        """--yes --json outputs JSON dict with removed list."""
        xdg_config = tmp_path / "config" / "agent-brain"
        xdg_config.mkdir(parents=True)
        xdg_state = tmp_path / "state" / "agent-brain"
        xdg_state.mkdir(parents=True)
        legacy = tmp_path / ".agent-brain"
        legacy.mkdir()

        with (
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_config_dir",
                return_value=xdg_config,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_xdg_state_dir",
                return_value=xdg_state,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.LEGACY_DIR",
                new=legacy,
            ),
            patch(
                "agent_brain_cli.commands.uninstall.get_registry_path",
                return_value=xdg_state / "registry.json",
            ),
        ):
            result = runner.invoke(uninstall_command, ["--yes", "--json"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "removed" in output
        assert "servers_stopped" in output
        assert isinstance(output["removed"], list)
        assert len(output["removed"]) > 0


class TestUninstallRegistration:
    """Tests for command registration in CLI."""

    def test_command_registered_in_cli(self, runner: CliRunner) -> None:
        """agent-brain uninstall --help shows the command."""
        result = runner.invoke(cli, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "--yes" in result.output
        assert "--json" in result.output
