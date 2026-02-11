"""Unit tests for ChromaDB backend adapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from llama_index.core.schema import NodeWithScore, TextNode

from agent_brain_server.storage.chroma.backend import ChromaBackend
from agent_brain_server.storage.protocol import (
    EmbeddingMetadata,
    SearchResult,
    StorageBackendProtocol,
    StorageError,
)
from agent_brain_server.storage.vector_store import (
    EmbeddingMetadata as VectorStoreEmbeddingMetadata,
)
from agent_brain_server.storage.vector_store import (
    SearchResult as VectorStoreSearchResult,
)


@pytest.fixture
def mock_vector_store():
    """Create mock VectorStoreManager."""
    mock = MagicMock()
    mock.is_initialized = True
    mock.initialize = AsyncMock()
    mock.upsert_documents = AsyncMock(return_value=5)
    mock.similarity_search = AsyncMock(return_value=[])
    mock.get_count = AsyncMock(return_value=100)
    mock.get_by_id = AsyncMock(return_value={"text": "test", "metadata": {}})
    mock.reset = AsyncMock()
    mock.get_embedding_metadata = AsyncMock(return_value=None)
    mock.set_embedding_metadata = AsyncMock()
    mock.validate_embedding_compatibility = MagicMock()
    return mock


@pytest.fixture
def mock_bm25_manager():
    """Create mock BM25IndexManager."""
    mock = MagicMock()
    mock.initialize = MagicMock()
    mock.search_with_filters = AsyncMock(return_value=[])
    mock.reset = MagicMock()
    return mock


@pytest.fixture
def chroma_backend(mock_vector_store, mock_bm25_manager):
    """Create ChromaBackend with mocked dependencies."""
    return ChromaBackend(
        vector_store=mock_vector_store,
        bm25_manager=mock_bm25_manager,
    )


class TestChromaBackendConstruction:
    """Test ChromaBackend construction and initialization."""

    def test_constructor_with_provided_managers(
        self, mock_vector_store, mock_bm25_manager
    ):
        """Test ChromaBackend accepts provided managers."""
        backend = ChromaBackend(
            vector_store=mock_vector_store,
            bm25_manager=mock_bm25_manager,
        )
        assert backend.vector_store is mock_vector_store
        assert backend.bm25_manager is mock_bm25_manager

    def test_constructor_uses_singletons_when_none(self):
        """Test ChromaBackend uses get_vector_store/get_bm25_manager when None."""
        backend = ChromaBackend(vector_store=None, bm25_manager=None)
        # Should not be None (singletons created)
        assert backend.vector_store is not None
        assert backend.bm25_manager is not None

    def test_is_initialized_delegates_to_vector_store(
        self, mock_vector_store, mock_bm25_manager
    ):
        """Test is_initialized property delegates to vector store."""
        mock_vector_store.is_initialized = True
        backend = ChromaBackend(mock_vector_store, mock_bm25_manager)
        assert backend.is_initialized is True

        mock_vector_store.is_initialized = False
        assert backend.is_initialized is False


class TestChromaBackendInitialization:
    """Test initialization logic."""

    @pytest.mark.asyncio
    async def test_initialize_calls_both_managers(
        self, chroma_backend, mock_vector_store, mock_bm25_manager
    ):
        """Test initialize delegates to both vector store and BM25 manager."""
        await chroma_backend.initialize()

        mock_vector_store.initialize.assert_called_once()
        mock_bm25_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_raises_storage_error_on_failure(
        self, chroma_backend, mock_vector_store
    ):
        """Test initialize wraps exceptions as StorageError."""
        mock_vector_store.initialize.side_effect = Exception("Chroma init failed")

        with pytest.raises(StorageError) as exc_info:
            await chroma_backend.initialize()

        assert "Failed to initialize ChromaBackend" in str(exc_info.value)
        assert exc_info.value.backend == "chroma"


class TestVectorSearch:
    """Test vector similarity search."""

    @pytest.mark.asyncio
    async def test_vector_search_delegates_to_vector_store(
        self, chroma_backend, mock_vector_store
    ):
        """Test vector_search calls similarity_search and converts results."""
        mock_vector_store.similarity_search.return_value = [
            VectorStoreSearchResult(
                text="test document",
                metadata={"key": "value"},
                score=0.95,
                chunk_id="chunk_1",
            )
        ]

        results = await chroma_backend.vector_search(
            query_embedding=[0.1, 0.2, 0.3],
            top_k=5,
            similarity_threshold=0.7,
            where={"source_type": "doc"},
        )

        mock_vector_store.similarity_search.assert_called_once_with(
            query_embedding=[0.1, 0.2, 0.3],
            top_k=5,
            similarity_threshold=0.7,
            where={"source_type": "doc"},
        )

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].text == "test document"
        assert results[0].score == 0.95
        assert results[0].chunk_id == "chunk_1"

    @pytest.mark.asyncio
    async def test_vector_search_raises_storage_error_on_failure(
        self, chroma_backend, mock_vector_store
    ):
        """Test vector_search wraps exceptions as StorageError."""
        mock_vector_store.similarity_search.side_effect = Exception("Search failed")

        with pytest.raises(StorageError) as exc_info:
            await chroma_backend.vector_search([0.1], 5, 0.7)

        assert "Vector search failed" in str(exc_info.value)
        assert exc_info.value.backend == "chroma"


class TestKeywordSearch:
    """Test BM25 keyword search with score normalization."""

    @pytest.mark.asyncio
    async def test_keyword_search_normalizes_scores(
        self, chroma_backend, mock_bm25_manager
    ):
        """Test keyword_search normalizes BM25 scores to 0-1 range."""
        # Mock BM25 results with raw scores
        mock_bm25_manager.search_with_filters.return_value = [
            NodeWithScore(
                node=TextNode(text="result 1", id_="chunk_1", metadata={"key": "val1"}),
                score=10.0,
            ),
            NodeWithScore(
                node=TextNode(text="result 2", id_="chunk_2", metadata={"key": "val2"}),
                score=5.0,
            ),
            NodeWithScore(
                node=TextNode(text="result 3", id_="chunk_3", metadata={"key": "val3"}),
                score=2.5,
            ),
        ]

        results = await chroma_backend.keyword_search(
            query="test query",
            top_k=5,
            source_types=["doc"],
            languages=["python"],
        )

        mock_bm25_manager.search_with_filters.assert_called_once_with(
            query="test query",
            top_k=5,
            source_types=["doc"],
            languages=["python"],
        )

        # Verify scores are normalized to 0-1 (max=10.0)
        assert len(results) == 3
        assert results[0].score == 1.0  # 10.0 / 10.0
        assert results[1].score == 0.5  # 5.0 / 10.0
        assert results[2].score == 0.25  # 2.5 / 10.0

    @pytest.mark.asyncio
    async def test_keyword_search_empty_results(
        self, chroma_backend, mock_bm25_manager
    ):
        """Test keyword_search returns empty list for no results."""
        mock_bm25_manager.search_with_filters.return_value = []

        results = await chroma_backend.keyword_search("test", 5)

        assert results == []

    @pytest.mark.asyncio
    async def test_keyword_search_zero_scores(self, chroma_backend, mock_bm25_manager):
        """Test keyword_search handles all-zero scores gracefully."""
        mock_bm25_manager.search_with_filters.return_value = [
            NodeWithScore(
                node=TextNode(text="result 1", id_="chunk_1"),
                score=0.0,
            ),
        ]

        results = await chroma_backend.keyword_search("test", 5)

        assert len(results) == 1
        assert results[0].score == 0.0

    @pytest.mark.asyncio
    async def test_keyword_search_raises_storage_error_on_failure(
        self, chroma_backend, mock_bm25_manager
    ):
        """Test keyword_search wraps exceptions as StorageError."""
        mock_bm25_manager.search_with_filters.side_effect = Exception("BM25 failed")

        with pytest.raises(StorageError) as exc_info:
            await chroma_backend.keyword_search("test", 5)

        assert "Keyword search failed" in str(exc_info.value)


class TestDocumentOperations:
    """Test document counting and retrieval."""

    @pytest.mark.asyncio
    async def test_get_count_delegates_to_vector_store(
        self, chroma_backend, mock_vector_store
    ):
        """Test get_count delegates to vector store."""
        mock_vector_store.get_count.return_value = 42

        count = await chroma_backend.get_count(where={"source_type": "doc"})

        mock_vector_store.get_count.assert_called_once_with(
            where={"source_type": "doc"}
        )
        assert count == 42

    @pytest.mark.asyncio
    async def test_get_by_id_delegates_to_vector_store(
        self, chroma_backend, mock_vector_store
    ):
        """Test get_by_id delegates to vector store."""
        mock_vector_store.get_by_id.return_value = {
            "text": "test content",
            "metadata": {"key": "value"},
        }

        result = await chroma_backend.get_by_id("chunk_123")

        mock_vector_store.get_by_id.assert_called_once_with("chunk_123")
        assert result["text"] == "test content"

    @pytest.mark.asyncio
    async def test_upsert_documents_delegates_to_vector_store(
        self, chroma_backend, mock_vector_store
    ):
        """Test upsert_documents delegates to vector store (not BM25)."""
        mock_vector_store.upsert_documents.return_value = 3

        count = await chroma_backend.upsert_documents(
            ids=["id1", "id2", "id3"],
            embeddings=[[0.1], [0.2], [0.3]],
            documents=["doc1", "doc2", "doc3"],
            metadatas=[{}, {}, {}],
        )

        mock_vector_store.upsert_documents.assert_called_once()
        assert count == 3


class TestReset:
    """Test reset operation."""

    @pytest.mark.asyncio
    async def test_reset_calls_both_managers(
        self, chroma_backend, mock_vector_store, mock_bm25_manager
    ):
        """Test reset delegates to both vector store and BM25 manager."""
        await chroma_backend.reset()

        mock_vector_store.reset.assert_called_once()
        mock_bm25_manager.reset.assert_called_once()


class TestEmbeddingMetadata:
    """Test embedding metadata operations."""

    @pytest.mark.asyncio
    async def test_get_embedding_metadata_converts_to_protocol_type(
        self, chroma_backend, mock_vector_store
    ):
        """Test get_embedding_metadata converts types."""
        mock_vector_store.get_embedding_metadata.return_value = (
            VectorStoreEmbeddingMetadata(
                provider="openai",
                model="text-embedding-3-large",
                dimensions=3072,
            )
        )

        metadata = await chroma_backend.get_embedding_metadata()

        assert isinstance(metadata, EmbeddingMetadata)
        assert metadata.provider == "openai"
        assert metadata.model == "text-embedding-3-large"
        assert metadata.dimensions == 3072

    @pytest.mark.asyncio
    async def test_get_embedding_metadata_returns_none_when_not_set(
        self, chroma_backend, mock_vector_store
    ):
        """Test get_embedding_metadata returns None when no metadata stored."""
        mock_vector_store.get_embedding_metadata.return_value = None

        metadata = await chroma_backend.get_embedding_metadata()

        assert metadata is None

    @pytest.mark.asyncio
    async def test_set_embedding_metadata_delegates_to_vector_store(
        self, chroma_backend, mock_vector_store
    ):
        """Test set_embedding_metadata delegates to vector store."""
        await chroma_backend.set_embedding_metadata(
            provider="openai",
            model="text-embedding-3-large",
            dimensions=3072,
        )

        mock_vector_store.set_embedding_metadata.assert_called_once_with(
            provider="openai",
            model="text-embedding-3-large",
            dimensions=3072,
        )

    def test_validate_embedding_compatibility_delegates_to_vector_store(
        self, chroma_backend, mock_vector_store
    ):
        """Test validate_embedding_compatibility delegates to vector store."""
        stored = EmbeddingMetadata(provider="openai", model="test", dimensions=1536)

        chroma_backend.validate_embedding_compatibility(
            provider="openai",
            model="test",
            dimensions=1536,
            stored_metadata=stored,
        )

        mock_vector_store.validate_embedding_compatibility.assert_called_once()


class TestProtocolCompliance:
    """Test that ChromaBackend satisfies StorageBackendProtocol."""

    def test_isinstance_check(self, chroma_backend):
        """Test that ChromaBackend satisfies isinstance check with protocol."""
        # Protocol is runtime_checkable, so isinstance should work
        assert isinstance(chroma_backend, StorageBackendProtocol)
