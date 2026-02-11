"""Tests for embedding metadata storage and validation."""

import pytest

from agent_brain_server.providers.exceptions import ProviderMismatchError
from agent_brain_server.storage.vector_store import (
    EmbeddingMetadata,
    VectorStoreManager,
)


class TestEmbeddingMetadata:
    """Tests for EmbeddingMetadata dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        metadata = EmbeddingMetadata(
            provider="openai",
            model="text-embedding-3-large",
            dimensions=3072,
        )
        result = metadata.to_dict()
        assert result == {
            "provider": "openai",
            "model": "text-embedding-3-large",
            "dimensions": 3072,
        }

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "embedding_provider": "ollama",
            "embedding_model": "nomic-embed-text",
            "embedding_dimensions": 768,
        }
        metadata = EmbeddingMetadata.from_dict(data)
        assert metadata.provider == "ollama"
        assert metadata.model == "nomic-embed-text"
        assert metadata.dimensions == 768

    def test_from_dict_missing_keys(self) -> None:
        """Test handling of missing keys."""
        data = {}
        metadata = EmbeddingMetadata.from_dict(data)
        assert metadata.provider == "unknown"
        assert metadata.model == "unknown"
        assert metadata.dimensions == 0


class TestVectorStoreValidation:
    """Tests for embedding validation methods."""

    def test_validate_compatible(self) -> None:
        """Test validation passes when metadata matches."""
        store = VectorStoreManager()
        stored = EmbeddingMetadata("openai", "text-embedding-3-large", 3072)

        # Should not raise
        store.validate_embedding_compatibility(
            provider="openai",
            model="text-embedding-3-large",
            dimensions=3072,
            stored_metadata=stored,
        )

    def test_validate_dimension_mismatch(self) -> None:
        """Test validation fails on dimension mismatch."""
        store = VectorStoreManager()
        stored = EmbeddingMetadata("openai", "text-embedding-3-large", 3072)

        with pytest.raises(ProviderMismatchError) as exc_info:
            store.validate_embedding_compatibility(
                provider="ollama",
                model="nomic-embed-text",
                dimensions=768,
                stored_metadata=stored,
            )

        assert "Provider mismatch" in str(exc_info.value)
        assert "openai" in str(exc_info.value)
        assert "ollama" in str(exc_info.value)

    def test_validate_provider_mismatch_same_dimensions(self) -> None:
        """Test validation fails on provider mismatch even with same dimensions."""
        store = VectorStoreManager()
        # Both Cohere and some Ollama models can have 1024 dimensions
        stored = EmbeddingMetadata("cohere", "embed-english-v3.0", 1024)

        with pytest.raises(ProviderMismatchError):
            store.validate_embedding_compatibility(
                provider="ollama",
                model="mxbai-embed-large",
                dimensions=1024,
                stored_metadata=stored,
            )

    def test_validate_no_stored_metadata(self) -> None:
        """Test validation passes when no metadata exists (new index)."""
        store = VectorStoreManager()

        # Should not raise
        store.validate_embedding_compatibility(
            provider="openai",
            model="text-embedding-3-large",
            dimensions=3072,
            stored_metadata=None,
        )
