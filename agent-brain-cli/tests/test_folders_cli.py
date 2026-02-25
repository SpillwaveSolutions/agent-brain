"""Tests for folders CLI commands."""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli
from agent_brain_cli.client import ConnectionError, FolderInfo, ServerError


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


def _make_mock_client(folders: list[FolderInfo] | None = None) -> MagicMock:
    """Create a mock DocServeClient context manager."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    if folders is not None:
        mock_client.list_folders.return_value = folders
    return mock_client


class TestFoldersListCommand:
    """Tests for 'agent-brain folders list' command."""

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_list_folders_with_results(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test listing folders when folders are indexed."""
        folders = [
            FolderInfo(
                folder_path="/home/user/docs",
                chunk_count=42,
                last_indexed="2026-02-24T12:00:00+00:00",
            ),
            FolderInfo(
                folder_path="/home/user/src",
                chunk_count=100,
                last_indexed="2026-02-24T13:00:00+00:00",
            ),
        ]
        mock_client = _make_mock_client(folders)
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "list"])

        assert result.exit_code == 0
        assert "/home/user/docs" in result.output
        assert "42" in result.output
        assert "/home/user/src" in result.output
        assert "100" in result.output

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_list_folders_empty(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test listing folders when no folders are indexed."""
        mock_client = _make_mock_client([])
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "list"])

        assert result.exit_code == 0
        assert "No folders indexed yet" in result.output

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_list_folders_json_output(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test listing folders with --json flag."""
        folders = [
            FolderInfo(
                folder_path="/home/user/docs",
                chunk_count=10,
                last_indexed="2026-02-24T12:00:00+00:00",
            ),
        ]
        mock_client = _make_mock_client(folders)
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "folders" in data
        assert len(data["folders"]) == 1
        assert data["folders"][0]["folder_path"] == "/home/user/docs"
        assert data["folders"][0]["chunk_count"] == 10

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_list_folders_connection_error(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test listing folders when server is unreachable."""
        mock_client = _make_mock_client()
        mock_client.list_folders.side_effect = ConnectionError("Cannot connect")
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "list"])

        assert result.exit_code == 1
        assert "Connection Error" in result.output

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_list_folders_server_error(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test listing folders when server returns error."""
        mock_client = _make_mock_client()
        mock_client.list_folders.side_effect = ServerError(
            "Internal error", status_code=500, detail="Something went wrong"
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "list"])

        assert result.exit_code == 1
        assert "Server Error" in result.output

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_list_folders_json_connection_error(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test listing folders --json when server is unreachable."""
        mock_client = _make_mock_client()
        mock_client.list_folders.side_effect = ConnectionError("Cannot connect")
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "list", "--json"])

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data


class TestFoldersRemoveCommand:
    """Tests for 'agent-brain folders remove' command."""

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_remove_folder_with_yes_flag(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test removing a folder with --yes flag (no prompt)."""
        mock_client = _make_mock_client()
        mock_client.delete_folder.return_value = {
            "folder_path": "/home/user/docs",
            "chunks_deleted": 42,
            "message": "Folder removed",
        }
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "remove", "/home/user/docs", "--yes"])

        assert result.exit_code == 0
        assert "42" in result.output
        mock_client.delete_folder.assert_called_once()

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_remove_folder_prompt_confirm(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test removing a folder with confirmation prompt (answer yes)."""
        mock_client = _make_mock_client()
        mock_client.delete_folder.return_value = {
            "folder_path": "/home/user/docs",
            "chunks_deleted": 5,
            "message": "Done",
        }
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli,
            ["folders", "remove", "/home/user/docs"],
            input="y\n",
        )

        assert result.exit_code == 0
        assert "5" in result.output

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_remove_folder_prompt_abort(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test aborting folder removal at confirmation prompt."""
        mock_client = _make_mock_client()
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli,
            ["folders", "remove", "/home/user/docs"],
            input="n\n",
        )

        assert result.exit_code != 0
        mock_client.delete_folder.assert_not_called()

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_remove_folder_not_found(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test removing a folder that is not indexed (404)."""
        mock_client = _make_mock_client()
        mock_client.delete_folder.side_effect = ServerError(
            "Not found", status_code=404, detail="Folder not found"
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "remove", "/missing/path", "--yes"])

        assert result.exit_code == 1
        assert "not indexed" in result.output or "not found" in result.output.lower()

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_remove_folder_conflict(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test removing a folder with active indexing job (409)."""
        mock_client = _make_mock_client()
        mock_client.delete_folder.side_effect = ServerError(
            "Conflict", status_code=409, detail="Active job running"
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "remove", "/home/user/docs", "--yes"])

        assert result.exit_code == 1
        assert "Conflict" in result.output or "active" in result.output.lower()

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_remove_folder_json_output(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test removing a folder with --json flag."""
        delete_result = {
            "folder_path": "/home/user/docs",
            "chunks_deleted": 42,
            "message": "Folder removed",
        }
        mock_client = _make_mock_client()
        mock_client.delete_folder.return_value = delete_result
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli, ["folders", "remove", "/home/user/docs", "--yes", "--json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["chunks_deleted"] == 42

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_remove_folder_connection_error(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test removing a folder when server is unreachable."""
        mock_client = _make_mock_client()
        mock_client.delete_folder.side_effect = ConnectionError("Cannot connect")
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["folders", "remove", "/home/user/docs", "--yes"])

        assert result.exit_code == 1
        assert "Connection Error" in result.output


class TestFoldersAddCommand:
    """Tests for 'agent-brain folders add' command."""

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_add_folder(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Test adding/indexing a folder."""
        mock_client = _make_mock_client()
        mock_client.index.return_value = MagicMock(
            job_id="job-123",
            status="queued",
            message=None,
        )
        mock_client_class.return_value = mock_client

        with runner.isolated_filesystem():
            import os

            os.makedirs("testdocs", exist_ok=True)
            result = runner.invoke(cli, ["folders", "add", "testdocs"])

        assert result.exit_code == 0
        assert "job-123" in result.output or "queued" in result.output
        mock_client.index.assert_called_once()

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_add_folder_with_include_code(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test adding a folder with --include-code flag."""
        mock_client = _make_mock_client()
        mock_client.index.return_value = MagicMock(
            job_id="job-456",
            status="queued",
            message=None,
        )
        mock_client_class.return_value = mock_client

        with runner.isolated_filesystem():
            import os

            os.makedirs("srccode", exist_ok=True)
            result = runner.invoke(cli, ["folders", "add", "srccode", "--include-code"])

        assert result.exit_code == 0
        call_kwargs = mock_client.index.call_args
        assert call_kwargs[1].get("include_code") is True

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_add_folder_json_output(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test adding a folder with --json flag."""
        mock_client = _make_mock_client()
        mock_client.index.return_value = MagicMock(
            job_id="job-789",
            status="queued",
            message="Job created",
        )
        mock_client_class.return_value = mock_client

        with runner.isolated_filesystem():
            import os

            os.makedirs("jsontest", exist_ok=True)
            result = runner.invoke(cli, ["folders", "add", "jsontest", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "job_id" in data
        assert data["job_id"] == "job-789"

    @patch("agent_brain_cli.commands.folders.DocServeClient")
    def test_add_folder_connection_error(
        self, mock_client_class: MagicMock, runner: CliRunner
    ) -> None:
        """Test adding a folder when server is unreachable."""
        mock_client = _make_mock_client()
        mock_client.index.side_effect = ConnectionError("Cannot connect")
        mock_client_class.return_value = mock_client

        with runner.isolated_filesystem():
            import os

            os.makedirs("errordocs", exist_ok=True)
            result = runner.invoke(cli, ["folders", "add", "errordocs"])

        assert result.exit_code == 1
        assert "Connection Error" in result.output


class TestFoldersHelp:
    """Tests for folders --help output."""

    def test_folders_help(self, runner: CliRunner) -> None:
        """Test 'agent-brain folders --help' output."""
        result = runner.invoke(cli, ["folders", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output
        assert "add" in result.output
        assert "remove" in result.output

    def test_folders_list_help(self, runner: CliRunner) -> None:
        """Test 'agent-brain folders list --help' output."""
        result = runner.invoke(cli, ["folders", "list", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output

    def test_folders_add_help(self, runner: CliRunner) -> None:
        """Test 'agent-brain folders add --help' output."""
        result = runner.invoke(cli, ["folders", "add", "--help"])
        assert result.exit_code == 0
        assert "FOLDER_PATH" in result.output
        assert "--include-code" in result.output

    def test_folders_remove_help(self, runner: CliRunner) -> None:
        """Test 'agent-brain folders remove --help' output."""
        result = runner.invoke(cli, ["folders", "remove", "--help"])
        assert result.exit_code == 0
        assert "--yes" in result.output
        assert "FOLDER_PATH" in result.output
