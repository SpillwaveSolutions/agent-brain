"""Tests for --watch and --debounce flags on folders add command."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.client.api_client import FolderInfo, IndexResponse
from agent_brain_cli.commands.folders import add_folder_cmd, list_folders_cmd


@pytest.fixture()
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture()
def mock_index_response() -> IndexResponse:
    """Create a mock IndexResponse."""
    return IndexResponse(job_id="job_abc123", status="pending", message="Job queued")


class TestFoldersAddWatchFlags:
    """Test --watch and --debounce flags on 'folders add' command."""

    def test_watch_auto_flag(
        self,
        runner: CliRunner,
        mock_index_response: IndexResponse,
        tmp_path: object,
    ) -> None:
        """--watch auto passes watch_mode='auto' to client.index()."""
        with patch(
            "agent_brain_cli.commands.folders.DocServeClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.index = MagicMock(return_value=mock_index_response)
            mock_client_cls.return_value = mock_client

            result = runner.invoke(
                add_folder_cmd,
                [str(tmp_path), "--watch", "auto", "--url", "http://test:8000"],
            )

            assert result.exit_code == 0
            mock_client.index.assert_called_once()
            call_kwargs = mock_client.index.call_args
            assert call_kwargs.kwargs.get("watch_mode") == "auto"

    def test_watch_off_flag(
        self,
        runner: CliRunner,
        mock_index_response: IndexResponse,
        tmp_path: object,
    ) -> None:
        """--watch off passes watch_mode='off' to client.index()."""
        with patch(
            "agent_brain_cli.commands.folders.DocServeClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.index = MagicMock(return_value=mock_index_response)
            mock_client_cls.return_value = mock_client

            result = runner.invoke(
                add_folder_cmd,
                [str(tmp_path), "--watch", "off", "--url", "http://test:8000"],
            )

            assert result.exit_code == 0
            call_kwargs = mock_client.index.call_args
            assert call_kwargs.kwargs.get("watch_mode") == "off"

    def test_debounce_flag(
        self,
        runner: CliRunner,
        mock_index_response: IndexResponse,
        tmp_path: object,
    ) -> None:
        """--debounce passes watch_debounce_seconds to client.index()."""
        with patch(
            "agent_brain_cli.commands.folders.DocServeClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.index = MagicMock(return_value=mock_index_response)
            mock_client_cls.return_value = mock_client

            result = runner.invoke(
                add_folder_cmd,
                [
                    str(tmp_path),
                    "--watch",
                    "auto",
                    "--debounce",
                    "10",
                    "--url",
                    "http://test:8000",
                ],
            )

            assert result.exit_code == 0
            call_kwargs = mock_client.index.call_args
            assert call_kwargs.kwargs.get("watch_debounce_seconds") == 10

    def test_no_watch_flag_passes_none(
        self,
        runner: CliRunner,
        mock_index_response: IndexResponse,
        tmp_path: object,
    ) -> None:
        """Without --watch, watch_mode is None."""
        with patch(
            "agent_brain_cli.commands.folders.DocServeClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.index = MagicMock(return_value=mock_index_response)
            mock_client_cls.return_value = mock_client

            result = runner.invoke(
                add_folder_cmd,
                [str(tmp_path), "--url", "http://test:8000"],
            )

            assert result.exit_code == 0
            call_kwargs = mock_client.index.call_args
            assert call_kwargs.kwargs.get("watch_mode") is None
            assert call_kwargs.kwargs.get("watch_debounce_seconds") is None


class TestFoldersListWatchColumns:
    """Test that folders list shows Watch column."""

    def test_list_shows_watch_column(self, runner: CliRunner) -> None:
        """Folders list table includes Watch column."""
        mock_folders = [
            FolderInfo(
                folder_path="/tmp/docs",
                chunk_count=42,
                last_indexed="2026-03-07T00:00:00",
                watch_mode="auto",
            ),
            FolderInfo(
                folder_path="/tmp/src",
                chunk_count=100,
                last_indexed="2026-03-07T00:00:00",
                watch_mode="off",
            ),
        ]

        with patch(
            "agent_brain_cli.commands.folders.DocServeClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_folders = MagicMock(return_value=mock_folders)
            mock_client_cls.return_value = mock_client

            result = runner.invoke(list_folders_cmd, ["--url", "http://test:8000"])

            assert result.exit_code == 0
            assert "Watch" in result.output

    def test_list_json_includes_watch_fields(self, runner: CliRunner) -> None:
        """Folders list --json output includes watch_mode."""
        mock_folders = [
            FolderInfo(
                folder_path="/tmp/docs",
                chunk_count=42,
                last_indexed="2026-03-07T00:00:00",
                watch_mode="auto",
                watch_debounce_seconds=10,
            ),
        ]

        with patch(
            "agent_brain_cli.commands.folders.DocServeClient"
        ) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.list_folders = MagicMock(return_value=mock_folders)
            mock_client_cls.return_value = mock_client

            result = runner.invoke(
                list_folders_cmd, ["--url", "http://test:8000", "--json"]
            )

            assert result.exit_code == 0
            data = json.loads(result.output)
            folder = data["folders"][0]
            assert folder["watch_mode"] == "auto"
            assert folder["watch_debounce_seconds"] == 10
