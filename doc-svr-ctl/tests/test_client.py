"""Tests for the API client."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from doc_svr_ctl.client import ConnectionError, DocServeClient, ServerError


class TestDocServeClient:
    """Tests for DocServeClient."""

    def test_client_init_defaults(self):
        """Test client initialization with defaults."""
        client = DocServeClient()
        assert client.base_url == "http://127.0.0.1:8000"
        assert client.timeout == 30.0
        client.close()

    def test_client_init_custom_url(self):
        """Test client initialization with custom URL."""
        client = DocServeClient(base_url="http://localhost:9000/")
        assert client.base_url == "http://localhost:9000"  # Trailing slash removed
        client.close()

    def test_client_context_manager(self):
        """Test client as context manager."""
        with DocServeClient() as client:
            assert client is not None

    @patch("httpx.Client.request")
    def test_health_success(self, mock_request):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "message": "Server ready",
            "version": "1.0.0",
            "timestamp": "2024-12-15T10:00:00Z",
        }
        mock_request.return_value = mock_response

        with DocServeClient() as client:
            health = client.health()

        assert health.status == "healthy"
        assert health.message == "Server ready"
        assert health.version == "1.0.0"

    @patch("httpx.Client.request")
    def test_status_success(self, mock_request):
        """Test successful status check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "total_documents": 100,
            "total_chunks": 500,
            "indexing_in_progress": False,
            "current_job_id": None,
            "progress_percent": 0.0,
            "last_indexed_at": "2024-12-15T10:00:00Z",
            "indexed_folders": ["/docs"],
        }
        mock_request.return_value = mock_response

        with DocServeClient() as client:
            status = client.status()

        assert status.total_documents == 100
        assert status.total_chunks == 500
        assert status.indexing_in_progress is False
        assert status.indexed_folders == ["/docs"]

    @patch("httpx.Client.request")
    def test_query_success(self, mock_request):
        """Test successful query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "text": "Sample result",
                    "source": "docs/test.md",
                    "score": 0.92,
                    "chunk_id": "chunk_123",
                    "metadata": {},
                }
            ],
            "query_time_ms": 50.0,
            "total_results": 1,
        }
        mock_request.return_value = mock_response

        with DocServeClient() as client:
            response = client.query("test query")

        assert response.total_results == 1
        assert len(response.results) == 1
        assert response.results[0].text == "Sample result"
        assert response.results[0].score == 0.92

    @patch("httpx.Client.request")
    def test_query_empty_results(self, mock_request):
        """Test query with no results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [],
            "query_time_ms": 10.0,
            "total_results": 0,
        }
        mock_request.return_value = mock_response

        with DocServeClient() as client:
            response = client.query("nonexistent")

        assert response.total_results == 0
        assert response.results == []

    @patch("httpx.Client.request")
    def test_index_success(self, mock_request):
        """Test successful index request."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {
            "job_id": "job_abc123",
            "status": "started",
            "message": "Indexing started",
        }
        mock_request.return_value = mock_response

        with DocServeClient() as client:
            response = client.index("/path/to/docs")

        assert response.job_id == "job_abc123"
        assert response.status == "started"

    @patch("httpx.Client.request")
    def test_reset_success(self, mock_request):
        """Test successful reset."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "reset",
            "status": "completed",
            "message": "Index reset successfully",
        }
        mock_request.return_value = mock_response

        with DocServeClient() as client:
            response = client.reset()

        assert response.status == "completed"

    @patch("httpx.Client.request")
    def test_connection_error(self, mock_request):
        """Test connection error handling."""
        mock_request.side_effect = httpx.ConnectError("Connection refused")

        with DocServeClient() as client:
            with pytest.raises(ConnectionError) as exc_info:
                client.health()

        assert "Unable to connect" in str(exc_info.value)

    @patch("httpx.Client.request")
    def test_timeout_error(self, mock_request):
        """Test timeout error handling."""
        mock_request.side_effect = httpx.TimeoutException("Timeout")

        with DocServeClient() as client:
            with pytest.raises(ConnectionError) as exc_info:
                client.health()

        assert "timed out" in str(exc_info.value)

    @patch("httpx.Client.request")
    def test_server_error(self, mock_request):
        """Test server error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Internal error"}
        mock_request.return_value = mock_response

        with DocServeClient() as client:
            with pytest.raises(ServerError) as exc_info:
                client.health()

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal error"

    @patch("httpx.Client.request")
    def test_server_error_409_conflict(self, mock_request):
        """Test 409 conflict error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.json.return_value = {"detail": "Indexing already in progress"}
        mock_request.return_value = mock_response

        with DocServeClient() as client:
            with pytest.raises(ServerError) as exc_info:
                client.index("/docs")

        assert exc_info.value.status_code == 409
        assert "already in progress" in exc_info.value.detail
