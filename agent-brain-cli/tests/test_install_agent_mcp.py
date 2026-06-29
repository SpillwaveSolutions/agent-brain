"""Tests for `install-agent --with-mcp` MCP registration wiring."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_brain_cli.commands.install_agent import install_agent_command


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """Minimal canonical plugin directory (mirrors test_install_agent)."""
    root = tmp_path / "plugin"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "agent-brain", "version": "1.0.0"})
    )
    cmds = root / "commands"
    cmds.mkdir()
    (cmds / "agent-brain-search.md").write_text(
        "---\nname: agent-brain-search\n"
        "description: Search docs\nparameters: []\nskills: []\n"
        "---\nSearch body."
    )
    return root


def _install(runner: CliRunner, plugin_dir: Path, project: Path, *extra: str):
    return runner.invoke(
        install_agent_command,
        [
            "--agent",
            "claude",
            "--plugin-dir",
            str(plugin_dir),
            "--path",
            str(project),
            *extra,
        ],
    )


class TestInstallAgentWithMcp:
    def test_default_does_not_register_mcp(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = _install(runner, plugin_dir, tmp_path)
        assert result.exit_code == 0
        assert not (tmp_path / ".mcp.json").exists()

    def test_with_mcp_writes_project_mcp_json(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = _install(runner, plugin_dir, tmp_path, "--with-mcp")
        assert result.exit_code == 0
        config = tmp_path / ".mcp.json"
        assert config.exists()
        data = json.loads(config.read_text())
        entry = data["mcpServers"]["agent-brain"]
        assert entry["command"] == "agent-brain-mcp"
        # State dir points at the project's .agent-brain (absolute).
        state_dir = Path(entry["env"]["AGENT_BRAIN_STATE_DIR"])
        assert state_dir.is_absolute()
        assert state_dir.name == ".agent-brain"

    def test_with_mcp_dry_run_writes_nothing(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = _install(runner, plugin_dir, tmp_path, "--with-mcp", "--dry-run")
        assert result.exit_code == 0
        assert not (tmp_path / ".mcp.json").exists()

    def test_with_mcp_oauth_injects_client_auth(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = _install(
            runner, plugin_dir, tmp_path, "--with-mcp", "--mcp-auth", "oauth"
        )
        assert result.exit_code == 0
        data = json.loads((tmp_path / ".mcp.json").read_text())
        env = data["mcpServers"]["agent-brain"]["env"]
        assert env["AGENT_BRAIN_MCP_AUTH"] == "oauth"

    def test_with_mcp_json_output_reports_registration(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = _install(runner, plugin_dir, tmp_path, "--with-mcp", "--json")
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["mcp_registration"]["action"] == "created"
        assert payload["mcp_registration"]["server_name"] == "agent-brain"

    def test_with_mcp_unsupported_runtime_warns_but_succeeds(
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
                "--with-mcp",
            ],
        )
        # Non-fatal: install still succeeds, but no config written and a clear note.
        assert result.exit_code == 0
        assert not (tmp_path / ".mcp.json").exists()
        assert not (tmp_path / "opencode.json").exists()
        assert "mcp" in result.output.lower()


class TestInstallAgentOpenCodeWithMcp:
    """OpenCode auto-registration writes the project-root `opencode.json`."""

    def _install_opencode(
        self, runner: CliRunner, plugin_dir: Path, project: Path, *extra: str
    ):
        return runner.invoke(
            install_agent_command,
            [
                "--agent",
                "opencode",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(project),
                *extra,
            ],
        )

    def test_default_does_not_register_mcp(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = self._install_opencode(runner, plugin_dir, tmp_path)
        assert result.exit_code == 0
        assert not (tmp_path / "opencode.json").exists()

    def test_with_mcp_writes_project_opencode_json(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = self._install_opencode(runner, plugin_dir, tmp_path, "--with-mcp")
        assert result.exit_code == 0
        # OpenCode reads project config from the project-root opencode.json.
        config = tmp_path / "opencode.json"
        assert config.exists()
        data = json.loads(config.read_text())
        entry = data["mcp"]["agent-brain"]
        assert entry["command"][0] == "agent-brain-mcp"
        assert entry["type"] == "local"
        state_dir = Path(entry["environment"]["AGENT_BRAIN_STATE_DIR"])
        assert state_dir.is_absolute()
        assert state_dir.name == ".agent-brain"

    def test_with_mcp_dry_run_writes_nothing(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = self._install_opencode(
            runner, plugin_dir, tmp_path, "--with-mcp", "--dry-run"
        )
        assert result.exit_code == 0
        assert not (tmp_path / "opencode.json").exists()

    def test_with_mcp_json_output_reports_registration(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        result = self._install_opencode(
            runner, plugin_dir, tmp_path, "--with-mcp", "--json"
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["mcp_registration"]["action"] == "created"
        assert payload["mcp_registration"]["server_name"] == "agent-brain"
        assert payload["mcp_registration"]["path"].endswith("opencode.json")
