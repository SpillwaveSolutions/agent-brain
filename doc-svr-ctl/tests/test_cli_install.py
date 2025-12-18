"""Tests for CLI entry point installation and functionality."""

from doc_svr_ctl import __version__
from doc_svr_ctl.cli import cli


class TestCLIEntryPoint:
    """Test CLI entry point is properly configured and functional."""

    def test_cli_function_importable(self):
        """T012: Verify cli() function can be imported from doc_svr_ctl.cli."""
        assert callable(cli), "cli should be a callable function"

    def test_cli_is_click_group(self):
        """Verify cli is a Click command group."""
        import click

        assert isinstance(cli, click.core.Group), "cli should be a Click Group"

    def test_version_importable(self):
        """Verify __version__ can be imported."""
        assert __version__ is not None
        assert isinstance(__version__, str)
        assert __version__ == "1.0.0"


class TestCLIHelpFlag:
    """Test --help flag functionality."""

    def test_help_flag_returns_usage(self):
        """T010: Verify --help returns expected output."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        assert (
            result.exit_code == 0
        ), f"--help should exit with 0, got {result.exit_code}"
        assert "Usage:" in result.output, "--help should show usage"
        assert "Doc-Serve CLI" in result.output, "--help should show description"

    def test_help_shows_subcommands(self):
        """Verify --help lists available subcommands."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])

        # Check for expected subcommands
        assert "status" in result.output, "Should list 'status' command"
        assert "query" in result.output, "Should list 'query' command"
        assert "index" in result.output, "Should list 'index' command"
        assert "reset" in result.output, "Should list 'reset' command"


class TestCLIVersionFlag:
    """Test --version flag functionality."""

    def test_version_flag_returns_version(self):
        """T011: Verify --version returns version string."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert (
            result.exit_code == 0
        ), f"--version should exit with 0, got {result.exit_code}"
        assert (
            "1.0.0" in result.output
        ), f"Should show version 1.0.0, got: {result.output}"


class TestCLISubcommands:
    """Test that subcommands are registered and callable."""

    def test_status_command_exists(self):
        """Verify status subcommand is registered."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--help"])

        assert result.exit_code == 0, "status --help should work"

    def test_query_command_exists(self):
        """Verify query subcommand is registered."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["query", "--help"])

        assert result.exit_code == 0, "query --help should work"

    def test_index_command_exists(self):
        """Verify index subcommand is registered."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["index", "--help"])

        assert result.exit_code == 0, "index --help should work"

    def test_reset_command_exists(self):
        """Verify reset subcommand is registered."""
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(cli, ["reset", "--help"])

        assert result.exit_code == 0, "reset --help should work"
