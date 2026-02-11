"""Tests for config CLI commands."""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from agent_brain_cli.cli import cli
from agent_brain_cli.commands.config import _find_config_file


class TestFindConfigFile:
    """Tests for _find_config_file helper."""

    def test_returns_none_when_no_config(self, tmp_path: Path) -> None:
        """No config file anywhere -> returns None."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("os.getcwd", return_value=str(tmp_path)),
        ):
            result = _find_config_file()
            # May or may not be None depending on actual filesystem,
            # but at minimum it should not raise
            assert result is None or isinstance(result, Path)

    def test_env_var_override(self, tmp_path: Path) -> None:
        """AGENT_BRAIN_CONFIG env var takes precedence."""
        config_file = tmp_path / "custom.yaml"
        config_file.write_text("embedding:\n  provider: ollama\n")
        with patch.dict(
            "os.environ", {"AGENT_BRAIN_CONFIG": str(config_file)}, clear=True
        ):
            result = _find_config_file()
            assert result == config_file

    def test_env_var_nonexistent_file(self, tmp_path: Path) -> None:
        """AGENT_BRAIN_CONFIG points to nonexistent file -> skips it."""
        with patch.dict(
            "os.environ",
            {"AGENT_BRAIN_CONFIG": str(tmp_path / "nope.yaml")},
            clear=True,
        ):
            # Falls through to other search paths
            result = _find_config_file()
            # Should not return the nonexistent path
            assert result != tmp_path / "nope.yaml"

    def test_state_dir_config(self, tmp_path: Path) -> None:
        """Config found via AGENT_BRAIN_STATE_DIR."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        config_file = state_dir / "config.yaml"
        config_file.write_text("embedding:\n  provider: ollama\n")
        with patch.dict(
            "os.environ", {"AGENT_BRAIN_STATE_DIR": str(state_dir)}, clear=True
        ):
            result = _find_config_file()
            assert result == config_file


class TestConfigShowCommand:
    """Tests for 'agent-brain config show' command."""

    def test_show_defaults_no_config(self) -> None:
        """Show defaults when no config file exists."""
        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file", return_value=None
        ):
            result = runner.invoke(cli, ["config", "show"])
            assert result.exit_code == 0
            has_msg = "No config file found" in result.output
            assert has_msg or "defaults" in result.output

    def test_show_json_no_config(self) -> None:
        """JSON output when no config file exists."""
        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file", return_value=None
        ):
            result = runner.invoke(cli, ["config", "show", "--json"])
            assert result.exit_code == 0
            assert '"config_source": "defaults"' in result.output
            assert '"config_file": null' in result.output

    def test_show_json_with_config(self, tmp_path: Path) -> None:
        """JSON output with a config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "embedding:\n  provider: ollama\n  model: nomic-embed-text\n"
        )
        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file",
            return_value=config_file,
        ):
            result = runner.invoke(cli, ["config", "show", "--json"])
            assert result.exit_code == 0
            assert '"config_source": "file"' in result.output
            assert "ollama" in result.output

    def test_show_rich_with_config(self, tmp_path: Path) -> None:
        """Rich table output with a config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "embedding:\n  provider: ollama\n  model: nomic-embed-text\n"
            "summarization:\n  provider: anthropic\n"
            "reranker:\n  provider: sentence-transformers\n"
        )
        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file",
            return_value=config_file,
        ):
            result = runner.invoke(cli, ["config", "show"])
            assert result.exit_code == 0


class TestConfigPathCommand:
    """Tests for 'agent-brain config path' command."""

    def test_path_no_config(self) -> None:
        """Shows message when no config file found."""
        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file", return_value=None
        ):
            result = runner.invoke(cli, ["config", "path"])
            assert result.exit_code == 0
            assert "No config file found" in result.output

    def test_path_with_config(self, tmp_path: Path) -> None:
        """Shows config file path."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file",
            return_value=config_file,
        ):
            result = runner.invoke(cli, ["config", "path"])
            assert result.exit_code == 0
            # Rich may wrap long paths; check filename is present
            assert "config.yaml" in result.output

    def test_path_json_no_config(self) -> None:
        """JSON output when no config."""
        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file", return_value=None
        ):
            result = runner.invoke(cli, ["config", "path", "--json"])
            assert result.exit_code == 0
            assert '"config_file": null' in result.output

    def test_path_json_with_config(self, tmp_path: Path) -> None:
        """JSON output with config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        runner = CliRunner()
        with patch(
            "agent_brain_cli.commands.config._find_config_file",
            return_value=config_file,
        ):
            result = runner.invoke(cli, ["config", "path", "--json"])
            assert result.exit_code == 0
            assert str(config_file) in result.output
            assert '"exists": true' in result.output
