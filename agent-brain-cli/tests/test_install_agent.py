"""Tests for the install-agent CLI command."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli
from agent_brain_cli.commands.install_agent import install_agent_command


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """Create a minimal canonical plugin directory."""
    root = tmp_path / "plugin"
    root.mkdir()

    manifest = root / ".claude-plugin"
    manifest.mkdir()
    (manifest / "plugin.json").write_text(
        json.dumps({"name": "agent-brain", "version": "1.0.0"})
    )

    cmds = root / "commands"
    cmds.mkdir()
    (cmds / "agent-brain-search.md").write_text(
        "---\nname: agent-brain-search\n"
        "description: Search docs\nparameters: []\nskills: []\n"
        "---\nSearch in .claude/agent-brain/data."
    )

    agents = root / "agents"
    agents.mkdir()
    (agents / "search-assistant.md").write_text(
        "---\nname: search-assistant\n"
        "description: Helps search\ntriggers: []\nskills: []\n"
        "---\nAgent body."
    )

    skills = root / "skills" / "using-agent-brain"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\nname: using-agent-brain\n"
        "description: Search skill\n"
        "allowed-tools:\n  - Bash\n  - Read\n"
        "metadata:\n  version: '1.0'\n"
        "---\nSkill body."
    )

    return root


class TestInstallAgentCommand:
    """Tests for install-agent command."""

    def test_claude_project_install(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "claude",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "installed" in result.output.lower()
        target = tmp_path / ".claude" / "plugins" / "agent-brain"
        assert (target / "commands" / "agent-brain-search.md").exists()

    def test_opencode_project_install(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "opencode",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        target = tmp_path / ".opencode" / "plugins" / "agent-brain"
        assert (target / "commands" / "agent-brain-search.md").exists()

    def test_gemini_project_install(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "gemini",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        target = tmp_path / ".gemini" / "plugins" / "agent-brain"
        assert (target / "commands" / "agent-brain-search.md").exists()

    def test_dry_run(self, runner: CliRunner, plugin_dir: Path, tmp_path: Path) -> None:
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "claude",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "dry run" in result.output.lower()
        # Should NOT actually create files
        target = tmp_path / ".claude" / "plugins" / "agent-brain"
        assert not target.exists()

    def test_dry_run_json(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "claude",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
                "--dry-run",
                "--json",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["dry_run"] is True
        assert output["file_count"] > 0
        assert output["agent"] == "claude"

    def test_json_output(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            install_agent_command,
            [
                "--agent",
                "claude",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
                "--json",
            ],
        )
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["status"] == "installed"
        assert output["files_created"] > 0

    def test_missing_plugin_dir(self, runner: CliRunner, tmp_path: Path) -> None:
        with patch(
            "agent_brain_cli.commands.install_agent._find_plugin_dir",
            return_value=None,
        ):
            result = runner.invoke(
                install_agent_command,
                ["--agent", "claude", "--path", str(tmp_path)],
            )
        assert result.exit_code == 1
        assert "could not find" in result.output.lower()

    def test_path_replacement_in_output(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        """Verify .claude/agent-brain is replaced with .agent-brain."""
        runner.invoke(
            install_agent_command,
            [
                "--agent",
                "claude",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(tmp_path),
            ],
        )
        target = tmp_path / ".claude" / "plugins" / "agent-brain"
        cmd_file = target / "commands" / "agent-brain-search.md"
        content = cmd_file.read_text()
        assert ".agent-brain" in content
        assert ".claude/agent-brain" not in content


class TestInstallAgentCLIIntegration:
    """Integration tests via the main CLI entry point."""

    def test_command_registered(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert "install-agent" in result.output

    def test_help_output(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["install-agent", "--help"])
        assert result.exit_code == 0
        assert "--agent" in result.output
        assert "--dry-run" in result.output
        assert "--json" in result.output
