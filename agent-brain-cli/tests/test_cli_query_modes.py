"""Tests for CLI query modes and options."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


class TestCLIQueryModes:
    """Tests for query command with different modes and alpha."""

    @patch("agent_brain_cli.commands.query.open_client")
    def test_query_bm25_mode(self, mock_client_class, runner):
        """Test query command with --mode bm25."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.results = []
        mock_response.query_time_ms = 10.0
        mock_response.total_results = 0
        mock_client.query.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["query", "test", "--mode", "bm25"])

        assert result.exit_code == 0
        # Verify query was called with mode='bm25'
        mock_client.query.assert_called_once()
        args, kwargs = mock_client.query.call_args
        assert kwargs["mode"] == "bm25"

    @patch("agent_brain_cli.commands.query.open_client")
    def test_query_hybrid_alpha(self, mock_client_class, runner):
        """Test query command with --mode hybrid and --alpha."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.results = []
        mock_response.query_time_ms = 10.0
        mock_response.total_results = 0
        mock_client.query.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli, ["query", "test", "--mode", "hybrid", "--alpha", "0.8"]
        )

        assert result.exit_code == 0
        # Verify query was called with mode='hybrid' and alpha=0.8
        mock_client.query.assert_called_once()
        args, kwargs = mock_client.query.call_args
        assert kwargs["mode"] == "hybrid"
        assert kwargs["alpha"] == 0.8

    def test_query_invalid_mode(self, runner):
        """Test query command with an invalid mode choice."""
        result = runner.invoke(cli, ["query", "test", "--mode", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value for" in result.output
        assert "'invalid' is not one of" in result.output
