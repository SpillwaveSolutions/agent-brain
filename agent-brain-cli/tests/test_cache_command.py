"""Tests for cache CLI commands."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli
from agent_brain_cli.client import ConnectionError, ServerError


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


def make_mock_client(
    cache_status_data: dict | None = None,
    clear_cache_data: dict | None = None,
) -> MagicMock:
    """Build a mock DocServeClient configured for cache tests."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    mock_client.cache_status.return_value = cache_status_data or {
        "entry_count": 250,
        "mem_entries": 100,
        "hit_rate": 0.75,
        "hits": 750,
        "misses": 250,
        "size_bytes": 3145728,  # 3 MB
    }
    mock_client.clear_cache.return_value = clear_cache_data or {
        "count": 250,
        "size_bytes": 3145728,
        "size_mb": 3.0,
    }
    return mock_client


class TestCacheGroupHelp:
    """Tests for cache command group help."""

    def test_cache_group_help(self, runner: CliRunner) -> None:
        """cache --help shows status and clear subcommands."""
        result = runner.invoke(cli, ["cache", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output
        assert "clear" in result.output
        assert "embedding cache" in result.output.lower()

    def test_cache_status_help(self, runner: CliRunner) -> None:
        """cache status --help shows --json and --url options."""
        result = runner.invoke(cli, ["cache", "status", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output
        assert "--url" in result.output

    def test_cache_clear_help(self, runner: CliRunner) -> None:
        """cache clear --help shows --yes option."""
        result = runner.invoke(cli, ["cache", "clear", "--help"])
        assert result.exit_code == 0
        assert "--yes" in result.output


class TestCacheStatusCommand:
    """Tests for 'cache status' subcommand."""

    @patch("agent_brain_cli.commands.cache.DocServeClient")
    def test_cache_status_default_output(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """cache status shows Rich table with cache metrics."""
        mock_client_class.return_value = make_mock_client()
        result = runner.invoke(cli, ["cache", "status"])
        assert result.exit_code == 0
        # Should display key metrics
        assert "250" in result.output  # entry_count
        assert "75" in result.output  # hit_rate 75%

    @patch("agent_brain_cli.commands.cache.DocServeClient")
    def test_cache_status_json_output(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """cache status --json outputs valid JSON with expected keys."""
        expected_data = {
            "entry_count": 100,
            "mem_entries": 50,
            "hit_rate": 0.8,
            "hits": 800,
            "misses": 200,
            "size_bytes": 1048576,
        }
        mock_client_class.return_value = make_mock_client(
            cache_status_data=expected_data
        )
        result = runner.invoke(cli, ["cache", "status", "--json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["entry_count"] == 100
        assert parsed["hit_rate"] == 0.8
        assert parsed["hits"] == 800

    @patch("agent_brain_cli.commands.cache.DocServeClient")
    def test_cache_status_connection_error(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """cache status exits 1 when server is not running."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.cache_status.side_effect = ConnectionError(
            "Unable to connect to server"
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["cache", "status"])
        assert result.exit_code == 1
        assert "Connection Error" in result.output

    @patch("agent_brain_cli.commands.cache.DocServeClient")
    def test_cache_status_json_connection_error(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """cache status --json outputs error JSON on connection failure."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.cache_status.side_effect = ConnectionError("Server down")
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["cache", "status", "--json"])
        assert result.exit_code == 1
        parsed = json.loads(result.output)
        assert "error" in parsed


class TestCacheClearCommand:
    """Tests for 'cache clear' subcommand."""

    @patch("agent_brain_cli.commands.cache.DocServeClient")
    def test_cache_clear_with_yes_flag(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """cache clear --yes clears without prompting."""
        mock_client_class.return_value = make_mock_client()
        result = runner.invoke(cli, ["cache", "clear", "--yes"])
        assert result.exit_code == 0
        assert "250" in result.output  # count cleared
        assert "3.0" in result.output  # MB freed

    @patch("agent_brain_cli.commands.cache.DocServeClient")
    def test_cache_clear_requires_confirmation(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """cache clear without --yes prompts for confirmation showing entry count."""
        mock_client_class.return_value = make_mock_client()
        # Answer 'n' to abort
        result = runner.invoke(cli, ["cache", "clear"], input="n\n")
        assert result.exit_code == 0
        # Prompt should mention entry count
        assert "250" in result.output  # entry count in prompt
        assert "Aborted" in result.output

    @patch("agent_brain_cli.commands.cache.DocServeClient")
    def test_cache_clear_confirm_yes(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """cache clear confirmed with 'y' executes the clear."""
        mock_client_class.return_value = make_mock_client()
        result = runner.invoke(cli, ["cache", "clear"], input="y\n")
        assert result.exit_code == 0
        assert "Cleared" in result.output

    @patch("agent_brain_cli.commands.cache.DocServeClient")
    def test_cache_clear_connection_error(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """cache clear exits 1 on connection error."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.clear_cache.side_effect = ConnectionError("Server down")
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["cache", "clear", "--yes"])
        assert result.exit_code == 1
        assert "Connection Error" in result.output

    @patch("agent_brain_cli.commands.cache.DocServeClient")
    def test_cache_clear_server_error(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """cache clear exits 1 on server error."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.clear_cache.side_effect = ServerError(
            "Server error", status_code=500, detail="Internal error"
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["cache", "clear", "--yes"])
        assert result.exit_code == 1
        assert "Server Error" in result.output
