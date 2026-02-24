"""Unit tests for storage protocol and types."""

import pytest

from agent_brain_server.storage.protocol import (
    EmbeddingMetadata,
    SearchResult,
    StorageBackendProtocol,
    StorageError,
)


def test_search_result_creation() -> None:
    """Test SearchResult dataclass creation and field access."""
    result = SearchResult(
        text="Test document content",
        metadata={"source": "test.py", "type": "code"},
        score=0.85,
        chunk_id="chunk_123",
    )

    assert result.text == "Test document content"
    assert result.metadata == {"source": "test.py", "type": "code"}
    assert result.score == 0.85
    assert result.chunk_id == "chunk_123"


def test_search_result_score_range() -> None:
    """Test SearchResult accepts scores in various ranges.

    Note: Protocol documents 0-1 normalization but doesn't enforce it
    at the dataclass level. Enforcement happens in backend implementations.
    """
    # Valid 0-1 range
    result1 = SearchResult(text="doc", metadata={}, score=0.5, chunk_id="1")
    assert result1.score == 0.5

    # Outside range is technically valid (no validation)
    result2 = SearchResult(text="doc", metadata={}, score=1.5, chunk_id="2")
    assert result2.score == 1.5

    result3 = SearchResult(text="doc", metadata={}, score=-0.1, chunk_id="3")
    assert result3.score == -0.1


def test_embedding_metadata_creation() -> None:
    """Test EmbeddingMetadata dataclass creation."""
    metadata = EmbeddingMetadata(
        provider="openai",
        model="text-embedding-3-large",
        dimensions=3072,
    )

    assert metadata.provider == "openai"
    assert metadata.model == "text-embedding-3-large"
    assert metadata.dimensions == 3072


def test_embedding_metadata_to_dict() -> None:
    """Test EmbeddingMetadata.to_dict() serialization."""
    metadata = EmbeddingMetadata(
        provider="ollama",
        model="nomic-embed-text",
        dimensions=768,
    )

    result = metadata.to_dict()

    assert result == {
        "embedding_provider": "ollama",
        "embedding_model": "nomic-embed-text",
        "embedding_dimensions": 768,
    }


def test_embedding_metadata_from_dict() -> None:
    """Test EmbeddingMetadata.from_dict() deserialization."""
    data = {
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": 1536,
    }

    metadata = EmbeddingMetadata.from_dict(data)

    assert metadata.provider == "openai"
    assert metadata.model == "text-embedding-3-small"
    assert metadata.dimensions == 1536


def test_embedding_metadata_from_dict_missing_keys() -> None:
    """Test EmbeddingMetadata.from_dict() with missing keys uses defaults."""
    data = {}

    metadata = EmbeddingMetadata.from_dict(data)

    assert metadata.provider == "unknown"
    assert metadata.model == "unknown"
    assert metadata.dimensions == 0


def test_embedding_metadata_roundtrip() -> None:
    """Test EmbeddingMetadata to_dict/from_dict roundtrip."""
    original = EmbeddingMetadata(
        provider="anthropic",
        model="claude-embeddings-v1",
        dimensions=1024,
    )

    # Roundtrip
    serialized = original.to_dict()
    restored = EmbeddingMetadata.from_dict(serialized)

    assert restored.provider == original.provider
    assert restored.model == original.model
    assert restored.dimensions == original.dimensions


def test_storage_error_creation() -> None:
    """Test StorageError exception creation."""
    error = StorageError("Test error message")

    assert error.message == "Test error message"
    assert error.backend is None
    assert str(error) == "Test error message"


def test_storage_error_with_backend() -> None:
    """Test StorageError with backend identifier."""
    error = StorageError("Connection failed", backend="postgres")

    assert error.message == "Connection failed"
    assert error.backend == "postgres"
    assert str(error) == "Connection failed"


def test_storage_error_inheritance() -> None:
    """Test StorageError inherits from Exception."""
    error = StorageError("Test")

    assert isinstance(error, Exception)

    # Can be caught as StorageError (more specific than Exception)
    with pytest.raises(StorageError):
        raise error


class MockCompleteBackend:
    """Mock backend implementing all protocol methods."""

    @property
    def is_initialized(self) -> bool:
        return True

    async def initialize(self) -> None:
        pass

    async def upsert_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, any]],
    ) -> int:
        return len(ids)

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float,
        where: dict[str, any] | None = None,
    ) -> list[SearchResult]:
        return []

    async def keyword_search(
        self,
        query: str,
        top_k: int,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> list[SearchResult]:
        return []

    async def get_count(self, where: dict[str, any] | None = None) -> int:
        return 0

    async def get_by_id(self, chunk_id: str) -> dict[str, any] | None:
        return None

    async def reset(self) -> None:
        pass

    async def get_embedding_metadata(self) -> EmbeddingMetadata | None:
        return None

    async def set_embedding_metadata(
        self,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        pass

    def validate_embedding_compatibility(
        self,
        provider: str,
        model: str,
        dimensions: int,
        stored_metadata: EmbeddingMetadata | None,
    ) -> None:
        pass

    async def delete_by_metadata(
        self,
        where: dict[str, any],
    ) -> int:
        return 0


def test_protocol_complete_implementation() -> None:
    """Test that mock class with all methods satisfies protocol."""
    mock = MockCompleteBackend()

    # Protocol is runtime_checkable, so isinstance should work
    assert isinstance(mock, StorageBackendProtocol)


class MockIncompleteBackend:
    """Mock backend missing required methods."""

    @property
    def is_initialized(self) -> bool:
        return True

    async def initialize(self) -> None:
        pass

    # Missing other required methods


def test_protocol_incomplete_implementation() -> None:
    """Test that incomplete mock does NOT satisfy protocol."""
    mock = MockIncompleteBackend()

    # This should NOT satisfy the protocol
    # Note: runtime_checkable only checks for method existence, not signatures
    # Since we're missing most methods, this should fail
    assert not isinstance(mock, StorageBackendProtocol)
