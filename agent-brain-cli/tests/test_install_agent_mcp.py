"""Tests for `install-agent --with-mcp` MCP registration wiring."""

import json
import tempfile
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

    def test_dry_run_does_not_escape_the_sandbox(
        self,
        runner: CliRunner,
        plugin_dir: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The OpenCode converter writes opencode.json at target.parent.parent.

        During a dry-run the converter runs against a throwaway temp dir; if
        that temp dir is shallow, ``parent.parent`` escapes to an ancestor
        outside the sandbox (in CI that resolves to "/" → PermissionError).
        Pinning the dry-run temp dir to a known-shallow location reproduces the
        escape deterministically: the stray opencode.json must NOT land above
        the sandbox.
        """
        project = tmp_path / "project"
        project.mkdir()
        sandbox = tmp_path / "outer" / "sandbox"
        sandbox.mkdir(parents=True)

        class _FixedTempDir:
            def __enter__(self) -> str:
                return str(sandbox)

            def __exit__(self, *exc: object) -> bool:
                return False

        monkeypatch.setattr(
            tempfile, "TemporaryDirectory", lambda *a, **k: _FixedTempDir()
        )

        result = self._install_opencode(
            runner, plugin_dir, project, "--with-mcp", "--dry-run"
        )

        assert result.exit_code == 0
        # `sandbox` is `<tmp_path>/outer/sandbox`, so the converter's
        # `target.parent.parent` is `<tmp_path>` — pre-fix the stray
        # opencode.json escapes to there. With the sandbox mirrored, every
        # write stays under `sandbox`, so nothing escapes.
        assert not (tmp_path / "opencode.json").exists()
        # And the dry-run never touches the real project root.
        assert not (project / "opencode.json").exists()


class TestInstallAgentCodexWithMcp:
    """Codex auto-registration writes `$CODEX_HOME/config.toml` (TOML)."""

    def _install_codex(
        self,
        runner: CliRunner,
        plugin_dir: Path,
        project: Path,
        codex_home: Path,
        *extra: str,
    ):
        return runner.invoke(
            install_agent_command,
            [
                "--agent",
                "codex",
                "--plugin-dir",
                str(plugin_dir),
                "--path",
                str(project),
                *extra,
            ],
            env={"CODEX_HOME": str(codex_home)},
        )

    def test_default_does_not_register_mcp(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        project = tmp_path / "proj"
        project.mkdir()
        codex_home = tmp_path / ".codex"
        result = self._install_codex(runner, plugin_dir, project, codex_home)
        assert result.exit_code == 0
        assert not (codex_home / "config.toml").exists()

    def test_with_mcp_writes_codex_config_toml(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        import tomlkit

        project = tmp_path / "proj"
        project.mkdir()
        codex_home = tmp_path / ".codex"
        result = self._install_codex(
            runner, plugin_dir, project, codex_home, "--with-mcp"
        )
        assert result.exit_code == 0
        config = codex_home / "config.toml"
        assert config.exists()
        doc = tomlkit.parse(config.read_text())
        entry = doc["mcp_servers"]["agent-brain"]
        assert entry["command"] == "agent-brain-mcp"
        state_dir = Path(entry["env"]["AGENT_BRAIN_STATE_DIR"])
        assert state_dir.is_absolute()
        assert state_dir.name == ".agent-brain"

    def test_with_mcp_dry_run_writes_nothing(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        project = tmp_path / "proj"
        project.mkdir()
        codex_home = tmp_path / ".codex"
        result = self._install_codex(
            runner, plugin_dir, project, codex_home, "--with-mcp", "--dry-run"
        )
        assert result.exit_code == 0
        assert not (codex_home / "config.toml").exists()

    def test_with_mcp_json_output_reports_registration(
        self, runner: CliRunner, plugin_dir: Path, tmp_path: Path
    ) -> None:
        project = tmp_path / "proj"
        project.mkdir()
        codex_home = tmp_path / ".codex"
        result = self._install_codex(
            runner, plugin_dir, project, codex_home, "--with-mcp", "--json"
        )
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["mcp_registration"]["action"] == "created"
        assert payload["mcp_registration"]["server_name"] == "agent-brain"
        assert payload["mcp_registration"]["path"].endswith("config.toml")
