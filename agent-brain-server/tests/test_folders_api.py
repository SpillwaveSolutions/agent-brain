"""Tests for the /index/folders API router."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_brain_server.api.routers.folders import router
from agent_brain_server.services.folder_manager import FolderRecord


def _make_record(
    folder_path: str = "/test/folder",
    chunk_count: int = 10,
    last_indexed: str = "2026-02-24T01:00:00+00:00",
    chunk_ids: list[str] | None = None,
) -> FolderRecord:
    """Helper to create FolderRecord fixtures."""
    return FolderRecord(
        folder_path=folder_path,
        chunk_count=chunk_count,
        last_indexed=last_indexed,
        chunk_ids=chunk_ids if chunk_ids is not None else ["chunk1", "chunk2"],
    )


def _create_app(
    folder_records: list[FolderRecord] | None = None,
    running_job_folder: str | None = None,
    stats_running: int = 0,
    raise_delete_error: bool = False,
) -> FastAPI:
    """Create a test FastAPI app with mocked state."""
    app = FastAPI()
    app.include_router(router, prefix="/index/folders")

    # Mock FolderManager
    mock_folder_manager = AsyncMock()
    mock_folder_manager.list_folders = AsyncMock(return_value=folder_records or [])
    mock_folder_manager.get_folder = AsyncMock(
        return_value=folder_records[0] if folder_records else None
    )
    mock_folder_manager.remove_folder = AsyncMock(
        return_value=folder_records[0] if folder_records else None
    )

    # Mock JobService
    mock_queue_stats = MagicMock()
    mock_queue_stats.running = stats_running

    mock_job_service = AsyncMock()
    mock_job_service.get_queue_stats = AsyncMock(return_value=mock_queue_stats)

    # Mock the store's get_running_job
    mock_running_job = None
    if running_job_folder is not None:
        mock_running_job = MagicMock()
        mock_running_job.folder_path = running_job_folder

    mock_store = AsyncMock()
    mock_store.get_running_job = AsyncMock(return_value=mock_running_job)
    mock_job_service.store = mock_store

    # Mock StorageBackend
    mock_storage = AsyncMock()
    if raise_delete_error:
        mock_storage.delete_by_ids = AsyncMock(
            side_effect=RuntimeError("Delete failed")
        )
        mock_storage.delete_by_metadata = AsyncMock(
            side_effect=RuntimeError("Delete failed")
        )
    else:
        mock_storage.delete_by_ids = AsyncMock(return_value=2)
        mock_storage.delete_by_metadata = AsyncMock(return_value=0)

    # Set app state
    app.state.folder_manager = mock_folder_manager
    app.state.job_service = mock_job_service
    app.state.storage_backend = mock_storage

    return app


class TestListFolders:
    """Tests for GET /index/folders."""

    def test_get_folders_empty(self) -> None:
        """GET returns empty list when no folders are indexed."""
        app = _create_app(folder_records=[])
        client = TestClient(app)

        response = client.get("/index/folders/")

        assert response.status_code == 200
        data = response.json()
        assert data["folders"] == []
        assert data["total"] == 0

    def test_get_folders_with_records(self) -> None:
        """GET returns folders with correct fields."""
        records = [
            _make_record(
                folder_path="/test/folder1",
                chunk_count=42,
                last_indexed="2026-02-24T01:00:00+00:00",
            ),
            _make_record(
                folder_path="/test/folder2",
                chunk_count=128,
                last_indexed="2026-02-24T00:30:00+00:00",
            ),
        ]
        app = _create_app(folder_records=records)

        # Update mock to return both records
        app.state.folder_manager.list_folders = AsyncMock(return_value=records)

        client = TestClient(app)
        response = client.get("/index/folders/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["folders"]) == 2

        folder1 = data["folders"][0]
        assert folder1["folder_path"] == "/test/folder1"
        assert folder1["chunk_count"] == 42
        assert folder1["last_indexed"] == "2026-02-24T01:00:00+00:00"

    def test_get_folders_response_model(self) -> None:
        """GET response matches FolderListResponse schema."""
        records = [_make_record()]
        app = _create_app(folder_records=records)
        app.state.folder_manager.list_folders = AsyncMock(return_value=records)
        client = TestClient(app)

        response = client.get("/index/folders/")

        assert response.status_code == 200
        data = response.json()
        assert "folders" in data
        assert "total" in data
        # Each folder must have required fields
        for folder in data["folders"]:
            assert "folder_path" in folder
            assert "chunk_count" in folder
            assert "last_indexed" in folder


class TestRemoveFolder:
    """Tests for DELETE /index/folders."""

    def test_delete_folder_success_with_chunk_ids(self) -> None:
        """DELETE returns success when folder found and chunk IDs available."""
        record = _make_record(chunk_ids=["c1", "c2", "c3"])
        app = _create_app(folder_records=[record])
        app.state.folder_manager.get_folder = AsyncMock(return_value=record)
        app.state.storage_backend.delete_by_ids = AsyncMock(return_value=3)
        client = TestClient(app)

        response = client.request(
            "DELETE",
            "/index/folders/",
            json={"folder_path": str(Path(record.folder_path).resolve())},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["chunks_deleted"] == 3
        assert data["folder_path"] == str(Path(record.folder_path).resolve())
        assert "Successfully removed" in data["message"]

    def test_delete_folder_success_fallback_metadata(self) -> None:
        """DELETE uses metadata fallback when no chunk_ids stored."""
        record = _make_record(chunk_ids=[])
        app = _create_app(folder_records=[record])
        app.state.folder_manager.get_folder = AsyncMock(return_value=record)
        # Override the delete_by_metadata mock to return a specific count
        app.state.storage_backend.delete_by_metadata = AsyncMock(return_value=5)
        # Ensure delete_by_ids is NOT called (empty chunk_ids → metadata fallback)
        app.state.storage_backend.delete_by_ids = AsyncMock(return_value=99)
        client = TestClient(app)

        response = client.request(
            "DELETE",
            "/index/folders/",
            json={"folder_path": str(Path(record.folder_path).resolve())},
        )

        assert response.status_code == 200
        # delete_by_ids should NOT have been called (empty chunk_ids)
        app.state.storage_backend.delete_by_ids.assert_not_called()
        # delete_by_metadata should have been called
        app.state.storage_backend.delete_by_metadata.assert_called_once()

    def test_delete_folder_not_found_returns_404(self) -> None:
        """DELETE returns 404 when folder not in index."""
        app = _create_app(folder_records=[])
        app.state.folder_manager.get_folder = AsyncMock(return_value=None)
        client = TestClient(app)

        response = client.request(
            "DELETE",
            "/index/folders/",
            json={"folder_path": "/nonexistent/folder"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_folder_active_job_returns_409(self) -> None:
        """DELETE returns 409 when active indexing job exists for folder."""
        folder_path = "/test/active-folder"
        record = _make_record(folder_path=folder_path)
        # The running job has same folder path
        app = _create_app(
            folder_records=[record],
            running_job_folder=folder_path,
            stats_running=1,
        )
        client = TestClient(app)

        response = client.request(
            "DELETE",
            "/index/folders/",
            json={"folder_path": folder_path},
        )

        assert response.status_code == 409
        assert "active" in response.json()["detail"].lower()

    def test_delete_folder_running_job_different_folder_succeeds(self) -> None:
        """DELETE succeeds when running job is for a different folder."""
        folder_path = "/test/target-folder"
        record = _make_record(folder_path=folder_path)
        # Running job is for a different folder
        app = _create_app(
            folder_records=[record],
            running_job_folder="/test/other-folder",
            stats_running=1,
        )
        app.state.folder_manager.get_folder = AsyncMock(return_value=record)
        app.state.storage_backend.delete_by_ids = AsyncMock(return_value=2)
        client = TestClient(app)

        response = client.request(
            "DELETE",
            "/index/folders/",
            json={"folder_path": folder_path},
        )

        assert response.status_code == 200

    def test_delete_folder_storage_error_returns_500(self) -> None:
        """DELETE returns 500 when storage backend raises an error."""
        record = _make_record()
        app = _create_app(folder_records=[record], raise_delete_error=True)
        app.state.folder_manager.get_folder = AsyncMock(return_value=record)
        client = TestClient(app)

        response = client.request(
            "DELETE",
            "/index/folders/",
            json={"folder_path": record.folder_path},
        )

        assert response.status_code == 500

    def test_delete_folder_removes_from_manager(self) -> None:
        """DELETE calls folder_manager.remove_folder after chunk deletion."""
        record = _make_record(chunk_ids=["c1"])
        app = _create_app(folder_records=[record])
        app.state.folder_manager.get_folder = AsyncMock(return_value=record)
        app.state.storage_backend.delete_by_ids = AsyncMock(return_value=1)
        client = TestClient(app)

        client.request(
            "DELETE",
            "/index/folders/",
            json={"folder_path": record.folder_path},
        )

        # Verify remove_folder was called
        app.state.folder_manager.remove_folder.assert_called_once()

    def test_delete_folder_no_running_jobs_skips_job_check(self) -> None:
        """DELETE skips job check when no running jobs (stats.running == 0)."""
        record = _make_record()
        app = _create_app(folder_records=[record], stats_running=0)
        app.state.folder_manager.get_folder = AsyncMock(return_value=record)
        app.state.storage_backend.delete_by_ids = AsyncMock(return_value=2)
        client = TestClient(app)

        response = client.request(
            "DELETE",
            "/index/folders/",
            json={"folder_path": record.folder_path},
        )

        assert response.status_code == 200
        # get_running_job should NOT be called when stats.running == 0
        app.state.job_service.store.get_running_job.assert_not_called()
