"""Tests for the inject CLI command."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.cli import cli
from agent_brain_cli.client import ConnectionError, ServerError


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def tmp_folder(tmp_path: Path) -> str:
    """Create a temporary folder to use as the index target."""
    return str(tmp_path)


@pytest.fixture
def tmp_script(tmp_path: Path) -> str:
    """Create a temporary Python script file."""
    script = tmp_path / "enrich.py"
    script.write_text("def process_chunk(chunk: dict) -> dict:\n    return chunk\n")
    return str(script)


@pytest.fixture
def tmp_metadata(tmp_path: Path) -> str:
    """Create a temporary JSON metadata file."""
    meta = tmp_path / "metadata.json"
    meta.write_text('{"project": "my-project", "version": "1.0"}')
    return str(meta)


def _make_mock_client(mock_class: MagicMock) -> MagicMock:
    """Configure a mock DocServeClient with standard context manager behaviour."""
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    mock_response = MagicMock()
    mock_response.job_id = "job-inject-123"
    mock_response.status = "queued"
    mock_response.message = None
    mock_client.index.return_value = mock_response
    mock_class.return_value = mock_client
    return mock_client


class TestInjectCommandScript:
    """Tests for --script option."""

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_with_script_sends_injector_script(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject --script sends injector_script to client.index()."""
        mock_client = _make_mock_client(mock_client_class)

        result = runner.invoke(cli, ["inject", "--script", tmp_script, tmp_folder])

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.index.call_args[1]
        assert call_kwargs["injector_script"] == str(Path(tmp_script).resolve())
        assert call_kwargs["folder_metadata_file"] is None
        assert call_kwargs["dry_run"] is False

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_with_folder_metadata_sends_folder_metadata_file(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_metadata: str,
    ) -> None:
        """inject --folder-metadata sends folder_metadata_file to client.index()."""
        mock_client = _make_mock_client(mock_client_class)

        result = runner.invoke(
            cli, ["inject", "--folder-metadata", tmp_metadata, tmp_folder]
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.index.call_args[1]
        assert call_kwargs["folder_metadata_file"] == str(Path(tmp_metadata).resolve())
        assert call_kwargs["injector_script"] is None
        assert call_kwargs["dry_run"] is False

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_with_both_script_and_folder_metadata(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
        tmp_metadata: str,
    ) -> None:
        """inject with both --script and --folder-metadata sends both params."""
        mock_client = _make_mock_client(mock_client_class)

        result = runner.invoke(
            cli,
            [
                "inject",
                "--script",
                tmp_script,
                "--folder-metadata",
                tmp_metadata,
                tmp_folder,
            ],
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.index.call_args[1]
        assert call_kwargs["injector_script"] == str(Path(tmp_script).resolve())
        assert call_kwargs["folder_metadata_file"] == str(Path(tmp_metadata).resolve())

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_dry_run_sends_dry_run_true(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject --dry-run --script sends dry_run=True to client.index()."""
        mock_client = _make_mock_client(mock_client_class)
        mock_client.index.return_value.message = "Validated 3 chunks, 2 keys injected"

        result = runner.invoke(
            cli, ["inject", "--dry-run", "--script", tmp_script, tmp_folder]
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.index.call_args[1]
        assert call_kwargs["dry_run"] is True
        assert "Dry-run" in result.output or "dry" in result.output.lower()


class TestInjectCommandValidation:
    """Tests for inject command validation."""

    def test_inject_without_script_or_folder_metadata_exits_2(
        self,
        runner: CliRunner,
        tmp_folder: str,
    ) -> None:
        """inject without --script or --folder-metadata exits with code 2."""
        result = runner.invoke(cli, ["inject", tmp_folder])
        assert result.exit_code == 2
        assert (
            "--script" in result.output
            or "folder-metadata" in result.output
            or "must be provided" in result.output
        )

    def test_inject_without_script_or_folder_metadata_json_error(
        self,
        runner: CliRunner,
        tmp_folder: str,
    ) -> None:
        """inject without options with --json outputs JSON error and exits 2."""
        result = runner.invoke(cli, ["inject", "--json", tmp_folder])
        assert result.exit_code == 2


class TestInjectCommandOptions:
    """Tests for inject command inheriting index options."""

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_inherits_chunk_size_option(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject passes --chunk-size to client.index()."""
        mock_client = _make_mock_client(mock_client_class)

        result = runner.invoke(
            cli,
            ["inject", "--script", tmp_script, "--chunk-size", "256", tmp_folder],
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.index.call_args[1]
        assert call_kwargs["chunk_size"] == 256

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_inherits_include_code_option(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject passes --include-code to client.index()."""
        mock_client = _make_mock_client(mock_client_class)

        result = runner.invoke(
            cli,
            ["inject", "--script", tmp_script, "--include-code", tmp_folder],
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.index.call_args[1]
        assert call_kwargs["include_code"] is True

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_inherits_no_recursive_option(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject passes --no-recursive to client.index() as recursive=False."""
        mock_client = _make_mock_client(mock_client_class)

        result = runner.invoke(
            cli,
            ["inject", "--script", tmp_script, "--no-recursive", tmp_folder],
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.index.call_args[1]
        assert call_kwargs["recursive"] is False

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_inherits_include_type_option(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject passes --include-type to client.index() as include_types list."""
        mock_client = _make_mock_client(mock_client_class)

        result = runner.invoke(
            cli,
            [
                "inject",
                "--script",
                tmp_script,
                "--include-type",
                "python,docs",
                tmp_folder,
            ],
        )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.index.call_args[1]
        assert call_kwargs["include_types"] == ["python", "docs"]


class TestInjectCommandJsonOutput:
    """Tests for inject command JSON output."""

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_json_output(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject --json outputs valid JSON with job_id, status, folder."""
        _make_mock_client(mock_client_class)

        result = runner.invoke(
            cli,
            ["inject", "--script", tmp_script, "--json", tmp_folder],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "job_id" in data
        assert "status" in data
        assert "folder" in data
        assert "dry_run" in data
        assert data["job_id"] == "job-inject-123"
        assert data["dry_run"] is False

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_dry_run_json_output(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject --dry-run --json outputs JSON with dry_run=True."""
        mock_client = _make_mock_client(mock_client_class)
        mock_client.index.return_value.status = "completed"
        mock_client.index.return_value.job_id = "dry_run"

        result = runner.invoke(
            cli,
            ["inject", "--dry-run", "--script", tmp_script, "--json", tmp_folder],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["dry_run"] is True


class TestInjectCommandErrorHandling:
    """Tests for inject command error handling."""

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_connection_error(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject exits with code 1 on ConnectionError."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.index.side_effect = ConnectionError("Cannot connect")
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["inject", "--script", tmp_script, tmp_folder])

        assert result.exit_code == 1
        assert "Connection Error" in result.output or "error" in result.output.lower()

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_server_error(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject exits with code 1 on ServerError."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.index.side_effect = ServerError(
            "Server error", status_code=500, detail="Internal error"
        )
        mock_client_class.return_value = mock_client

        result = runner.invoke(cli, ["inject", "--script", tmp_script, tmp_folder])

        assert result.exit_code == 1
        assert "Server Error" in result.output or "error" in result.output.lower()

    @patch("agent_brain_cli.commands.inject.DocServeClient")
    def test_inject_connection_error_json(
        self,
        mock_client_class: MagicMock,
        runner: CliRunner,
        tmp_folder: str,
        tmp_script: str,
    ) -> None:
        """inject --json outputs JSON error on ConnectionError."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.index.side_effect = ConnectionError("Cannot connect")
        mock_client_class.return_value = mock_client

        result = runner.invoke(
            cli, ["inject", "--script", tmp_script, "--json", tmp_folder]
        )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert "error" in data
