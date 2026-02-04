"""Tests for CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli
from agent_brain_cli.client import ConnectionError


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


class TestCLIHelp:
    """Tests for CLI help and version."""

    def test_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Agent Brain CLI" in result.output
        assert "status" in result.output
        assert "query" in result.output

    def test_version(self, runner):
        """Test --version flag."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "3.0.0" in result.output


class TestStatusCommand:
    """Tests for status command."""

    @patch("agent_brain_cli.commands.status.DocServeClient")
    def test_status_healthy(self, mock_client_class, runner):
        """Test status command when server is healthy."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_health = MagicMock()
        mock_health.status = "healthy"
        mock_health.message = "Server ready"
        mock_health.version = "1.1.0"

        mock_status = MagicMock()
        mock_status.total_documents = 100
        mock_status.total_chunks = 500
        mock_status.indexing_in_progress = False
        mock_status.current_job_id = None
        mock_status.progress_percent = 0.0
        mock_status.indexed_folders = ["/docs"]
        mock_status.last_indexed_at = "2024-12-15"

        mock_client.health.return_value = mock_health
        mock_client.status.return_value = mock_status
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 0
        assert "HEALTHY" in result.output or "healthy" in result.output.lower()

    @patch("agent_brain_cli.commands.status.DocServeClient")
    def test_status_json_output(self, mock_client_class, runner):
        """Test status command with JSON output."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_health = MagicMock()
        mock_health.status = "healthy"
        mock_health.message = "Ready"
        mock_health.version = "1.1.0"

        mock_status = MagicMock()
        mock_status.total_documents = 50
        mock_status.total_chunks = 250
        mock_status.indexing_in_progress = False
        mock_status.progress_percent = 0.0
        mock_status.indexed_folders = []

        mock_client.health.return_value = mock_health
        mock_client.status.return_value = mock_status
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["status", "--json"])

        assert result.exit_code == 0
        import json

        output = json.loads(result.output)
        assert output["health"]["status"] == "healthy"
        assert output["indexing"]["total_documents"] == 50

    @patch("agent_brain_cli.commands.status.DocServeClient")
    def test_status_connection_error(self, mock_client_class, runner):
        """Test status command when server unreachable."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.health.side_effect = ConnectionError("Connection refused")
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["status"])

        assert result.exit_code == 1
        assert "Connection Error" in result.output


class TestQueryCommand:
    """Tests for query command."""

    @patch("agent_brain_cli.commands.query.DocServeClient")
    def test_query_with_results(self, mock_client_class, runner):
        """Test query command with results."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.text = "Sample result text"
        mock_result.source = "docs/test.md"
        mock_result.score = 0.92
        mock_result.chunk_id = "chunk_123"
        mock_result.metadata = {}

        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_response.query_time_ms = 50.0
        mock_response.total_results = 1

        mock_client.query.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["query", "test search"])

        assert result.exit_code == 0
        assert "Found 1 results" in result.output
        assert "docs/test.md" in result.output

    @patch("agent_brain_cli.commands.query.DocServeClient")
    def test_query_no_results(self, mock_client_class, runner):
        """Test query command with no results."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.results = []
        mock_response.query_time_ms = 10.0
        mock_response.total_results = 0

        mock_client.query.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["query", "nonexistent"])

        assert result.exit_code == 0
        assert "No matching documents" in result.output

    @patch("agent_brain_cli.commands.query.DocServeClient")
    def test_query_json_output(self, mock_client_class, runner):
        """Test query command with JSON output."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_result = MagicMock()
        mock_result.text = "Result"
        mock_result.source = "test.md"
        mock_result.score = 0.9
        mock_result.chunk_id = "c1"

        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_response.query_time_ms = 25.0
        mock_response.total_results = 1

        mock_client.query.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["query", "test", "--json"])

        assert result.exit_code == 0
        import json

        output = json.loads(result.output)
        assert output["query"] == "test"
        assert output["total_results"] == 1


class TestIndexCommand:
    """Tests for index command."""

    @patch("agent_brain_cli.commands.index.DocServeClient")
    def test_index_success(self, mock_client_class, runner, tmp_path):
        """Test index command success."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.job_id = "job_test123"
        mock_response.status = "started"
        mock_response.message = "Indexing started"

        mock_client.index.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Create a temp directory to index
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        result = runner.invoke(cli, ["index", str(docs_dir)])

        assert result.exit_code == 0
        assert "Indexing started" in result.output
        assert "job_test123" in result.output

    def test_index_invalid_path(self, runner):
        """Test index command with invalid path."""
        result = runner.invoke(cli, ["index", "/nonexistent/path"])

        assert result.exit_code != 0
        # Click validates path exists


class TestResetCommand:
    """Tests for reset command."""

    @patch("agent_brain_cli.commands.reset.DocServeClient")
    def test_reset_with_yes_flag(self, mock_client_class, runner):
        """Test reset command with --yes flag."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        mock_response = MagicMock()
        mock_response.job_id = "reset"
        mock_response.status = "completed"
        mock_response.message = "Index cleared"

        mock_client.reset.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["reset", "--yes"])

        assert result.exit_code == 0
        assert "reset successfully" in result.output

    def test_reset_without_confirmation(self, runner):
        """Test reset command prompts for confirmation."""
        result = runner.invoke(cli, ["reset"], input="n\n")

        assert "Aborted" in result.output
