"""Pytest configuration and fixtures for doc-serve-server tests."""

import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Set test environment variables before importing app
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["ANTHROPIC_API_KEY"] = "test-key"
os.environ["DEBUG"] = "true"


@pytest.fixture
def temp_docs_dir() -> Generator[Path, None, None]:
    """Create a temporary directory with sample documents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_path = Path(tmpdir)

        # Create sample markdown files
        (docs_path / "doc1.md").write_text(
            "# Introduction\n\nThis is a sample document about Python programming.\n"
            "Python is a versatile language used for web development, data science, "
            "and automation.\n"
        )
        (docs_path / "doc2.md").write_text(
            "# FastAPI Guide\n\nFastAPI is a modern web framework for building APIs.\n"
            "It provides automatic OpenAPI documentation and type validation.\n"
        )
        (docs_path / "subdir").mkdir()
        (docs_path / "subdir" / "doc3.md").write_text(
            "# Advanced Topics\n\nThis document covers advanced programming concepts.\n"
            "Including async/await patterns and dependency injection.\n"
        )

        yield docs_path


@pytest.fixture
def temp_chroma_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for Chroma persistence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_embedding_generator():
    """Mock embedding generator that returns fake embeddings."""
    mock = AsyncMock()

    # Return a fake embedding vector (dimension 3072 to match text-embedding-3-large)
    fake_embedding = [0.1] * 3072
    mock.embed_query.return_value = fake_embedding
    mock.embed_chunks.return_value = [fake_embedding]
    mock.embed_texts.return_value = [fake_embedding]

    return mock


@pytest.fixture
def mock_vector_store():
    """Mock vector store for unit tests."""
    mock = MagicMock()
    mock.is_initialized = True
    mock.initialize = AsyncMock()
    mock.add_documents = AsyncMock(return_value=1)
    mock.similarity_search = AsyncMock(return_value=[])
    mock.get_count = AsyncMock(return_value=0)
    mock.reset = AsyncMock()
    return mock


@pytest.fixture
def app_with_mocks(mock_vector_store, mock_embedding_generator):
    """Create FastAPI app with mocked dependencies."""
    with (
        patch("src.storage.get_vector_store", return_value=mock_vector_store),
        patch(
            "src.storage.initialize_vector_store",
            new_callable=AsyncMock,
            return_value=mock_vector_store,
        ),
        patch(
            "src.indexing.get_embedding_generator",
            return_value=mock_embedding_generator,
        ),
    ):
        from src.api.main import app

        yield app


@pytest.fixture
def client(app_with_mocks) -> Generator[TestClient, None, None]:
    """Create synchronous test client."""
    with TestClient(app_with_mocks) as client:
        yield client


@pytest.fixture
async def async_client(app_with_mocks) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    transport = ASGITransport(app=app_with_mocks)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# Sample test data
@pytest.fixture
def sample_query_request() -> dict:
    """Sample query request payload."""
    return {
        "query": "How do I use FastAPI?",
        "top_k": 5,
        "similarity_threshold": 0.7,
    }


@pytest.fixture
def sample_index_request(temp_docs_dir) -> dict:
    """Sample index request payload."""
    return {
        "folder_path": str(temp_docs_dir),
        "chunk_size": 512,
        "chunk_overlap": 50,
        "recursive": True,
    }
