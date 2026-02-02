"""Unit tests for Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from agent_brain_server.models import (
    HealthStatus,
    IndexingState,
    IndexingStatus,
    IndexingStatusEnum,
    IndexRequest,
    IndexResponse,
    QueryRequest,
    QueryResponse,
    QueryResult,
)


class TestHealthModels:
    """Tests for health status models."""

    def test_health_status_valid(self):
        """Test creating a valid HealthStatus."""
        status = HealthStatus(
            status="healthy",
            message="Server is running",
        )
        assert status.status == "healthy"
        assert status.message == "Server is running"
        assert status.version == "2.0.0"
        assert isinstance(status.timestamp, datetime)

    def test_health_status_all_statuses(self):
        """Test all valid health status values."""
        for status_value in ["healthy", "indexing", "degraded", "unhealthy"]:
            status = HealthStatus(status=status_value)
            assert status.status == status_value

    def test_health_status_invalid_status(self):
        """Test that invalid status values are rejected."""
        with pytest.raises(ValidationError):
            HealthStatus(status="invalid_status")

    def test_indexing_status_defaults(self):
        """Test IndexingStatus default values."""
        status = IndexingStatus()
        assert status.total_documents == 0
        assert status.total_chunks == 0
        assert status.indexing_in_progress is False
        assert status.current_job_id is None
        assert status.progress_percent == 0.0
        assert status.indexed_folders == []

    def test_indexing_status_with_values(self):
        """Test IndexingStatus with populated values."""
        status = IndexingStatus(
            total_documents=100,
            total_chunks=500,
            indexing_in_progress=True,
            current_job_id="job_123",
            progress_percent=50.5,
            indexed_folders=["/docs", "/notes"],
        )
        assert status.total_documents == 100
        assert status.total_chunks == 500
        assert status.progress_percent == 50.5

    def test_indexing_status_progress_bounds(self):
        """Test progress_percent validation bounds."""
        # Valid bounds
        IndexingStatus(progress_percent=0.0)
        IndexingStatus(progress_percent=100.0)

        # Invalid bounds
        with pytest.raises(ValidationError):
            IndexingStatus(progress_percent=-1.0)
        with pytest.raises(ValidationError):
            IndexingStatus(progress_percent=101.0)


class TestIndexModels:
    """Tests for indexing request/response models."""

    def test_index_request_valid(self, temp_docs_dir):
        """Test creating a valid IndexRequest."""
        request = IndexRequest(
            folder_path=str(temp_docs_dir),
            chunk_size=512,
            chunk_overlap=50,
            recursive=True,
        )
        assert request.folder_path == str(temp_docs_dir)
        assert request.chunk_size == 512
        assert request.recursive is True

    def test_index_request_defaults(self):
        """Test IndexRequest default values."""
        request = IndexRequest(folder_path="/some/path")
        assert request.chunk_size == 512
        assert request.chunk_overlap == 50
        assert request.recursive is True

    def test_index_request_chunk_size_bounds(self):
        """Test chunk_size validation bounds."""
        # Valid
        IndexRequest(folder_path="/path", chunk_size=128)
        IndexRequest(folder_path="/path", chunk_size=2048)

        # Invalid
        with pytest.raises(ValidationError):
            IndexRequest(folder_path="/path", chunk_size=100)
        with pytest.raises(ValidationError):
            IndexRequest(folder_path="/path", chunk_size=3000)

    def test_index_request_empty_path_rejected(self):
        """Test that empty folder_path is rejected."""
        with pytest.raises(ValidationError):
            IndexRequest(folder_path="")

    def test_index_response_valid(self):
        """Test creating a valid IndexResponse."""
        response = IndexResponse(
            job_id="job_abc123",
            status="started",
            message="Indexing started",
        )
        assert response.job_id == "job_abc123"
        assert response.status == "started"

    def test_indexing_state_progress_percent(self):
        """Test IndexingState progress calculation."""
        state = IndexingState(
            total_documents=100,
            processed_documents=50,
        )
        assert state.progress_percent == 50.0

    def test_indexing_state_progress_zero_docs(self):
        """Test progress with zero documents."""
        state = IndexingState(total_documents=0, processed_documents=0)
        assert state.progress_percent == 0.0

    def test_indexing_status_enum_values(self):
        """Test IndexingStatusEnum values."""
        assert IndexingStatusEnum.IDLE.value == "idle"
        assert IndexingStatusEnum.INDEXING.value == "indexing"
        assert IndexingStatusEnum.COMPLETED.value == "completed"
        assert IndexingStatusEnum.FAILED.value == "failed"


class TestQueryModels:
    """Tests for query request/response models."""

    def test_query_request_valid(self):
        """Test creating a valid QueryRequest."""
        request = QueryRequest(
            query="How do I use Python?",
            top_k=10,
            similarity_threshold=0.8,
        )
        assert request.query == "How do I use Python?"
        assert request.top_k == 10
        assert request.similarity_threshold == 0.8

    def test_query_request_defaults(self):
        """Test QueryRequest default values."""
        request = QueryRequest(query="test query")
        assert request.top_k == 5
        assert request.similarity_threshold == 0.7

    def test_query_request_query_length_bounds(self):
        """Test query length validation."""
        # Valid
        QueryRequest(query="a")
        QueryRequest(query="x" * 1000)

        # Invalid - empty
        with pytest.raises(ValidationError):
            QueryRequest(query="")

        # Invalid - too long
        with pytest.raises(ValidationError):
            QueryRequest(query="x" * 1001)

    def test_query_request_top_k_bounds(self):
        """Test top_k validation bounds."""
        # Valid
        QueryRequest(query="test", top_k=1)
        QueryRequest(query="test", top_k=50)

        # Invalid
        with pytest.raises(ValidationError):
            QueryRequest(query="test", top_k=0)
        with pytest.raises(ValidationError):
            QueryRequest(query="test", top_k=51)

    def test_query_request_threshold_bounds(self):
        """Test similarity_threshold validation bounds."""
        # Valid
        QueryRequest(query="test", similarity_threshold=0.0)
        QueryRequest(query="test", similarity_threshold=1.0)

        # Invalid
        with pytest.raises(ValidationError):
            QueryRequest(query="test", similarity_threshold=-0.1)
        with pytest.raises(ValidationError):
            QueryRequest(query="test", similarity_threshold=1.1)

    def test_query_result_valid(self):
        """Test creating a valid QueryResult."""
        result = QueryResult(
            text="Sample text content",
            source="docs/sample.md",
            score=0.95,
            chunk_id="chunk_123",
            metadata={"page": 1},
        )
        assert result.text == "Sample text content"
        assert result.source == "docs/sample.md"
        assert result.score == 0.95
        assert result.chunk_id == "chunk_123"
        assert result.metadata == {"page": 1}

    def test_query_response_valid(self):
        """Test creating a valid QueryResponse."""
        result = QueryResult(
            text="content",
            source="file.md",
            score=0.9,
            chunk_id="c1",
        )
        response = QueryResponse(
            results=[result],
            query_time_ms=125.5,
            total_results=1,
        )
        assert len(response.results) == 1
        assert response.query_time_ms == 125.5
        assert response.total_results == 1

    def test_query_response_empty_results(self):
        """Test QueryResponse with empty results."""
        response = QueryResponse(
            results=[],
            query_time_ms=50.0,
            total_results=0,
        )
        assert response.results == []
        assert response.total_results == 0
