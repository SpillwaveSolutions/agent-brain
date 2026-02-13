"""Service-level E2E tests for PostgreSQL backend with live database.

These tests validate the complete PostgreSQL-backed workflow by instantiating
the backend directly, seeding documents, querying, and verifying cross-backend
consistency with ChromaDB.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from llama_index.core.schema import TextNode

from agent_brain_server.config.provider_config import clear_settings_cache
from agent_brain_server.indexing.bm25_index import BM25IndexManager
from agent_brain_server.storage.chroma.backend import ChromaBackend
from agent_brain_server.storage.postgres.backend import PostgresBackend
from agent_brain_server.storage.postgres.config import PostgresConfig
from agent_brain_server.storage.protocol import SearchResult
from agent_brain_server.storage.vector_store import VectorStoreManager


def _postgres_available() -> bool:
    """Check if PostgreSQL is available for testing."""
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("DATABASE_URL"))


pytestmark = [
    pytest.mark.postgres,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not _postgres_available(),
        reason="PostgreSQL not available (requires DATABASE_URL and asyncpg)",
    ),
]


@pytest.fixture
async def postgres_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[PostgresBackend, None]:
    """Create PostgresBackend with live database connection."""
    # Write minimal provider config for 8-dimensional embeddings
    config_path = tmp_path / "provider-config.yaml"
    config_path.write_text("embedding:\n  params:\n    dimensions: 8\n")

    # Set config path and clear cache
    monkeypatch.setenv("AGENT_BRAIN_CONFIG", str(config_path))
    clear_settings_cache()

    # Import providers to trigger registration
    import agent_brain_server.providers  # noqa: F401

    # Create PostgreSQL backend
    config = PostgresConfig.from_database_url(os.environ["DATABASE_URL"])
    backend = PostgresBackend(config=config)
    await backend.initialize()

    yield backend

    # Teardown: reset and close
    await backend.reset()
    await backend.close()
    clear_settings_cache()


class TestPostgresE2E:
    """End-to-end tests for PostgreSQL backend."""

    async def test_full_workflow_index_and_query(
        self, postgres_backend: PostgresBackend, tmp_path: Path
    ) -> None:
        """Test complete workflow: seed documents, verify count, execute search.

        Validates Success Criteria #1: E2E test seeds real documents into live
        PostgreSQL via upsert_documents and queries via vector_search return
        relevant results with valid scores.
        """
        # Seed 5 documents with deterministic 8-dim embeddings
        ids = ["py-001", "js-002", "rs-003", "go-004", "ts-005"]
        embeddings = [
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # Python
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # JavaScript
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],  # Rust
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],  # Go
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],  # TypeScript
        ]
        documents = [
            "Python programming language with dynamic typing and extensive libraries",
            "JavaScript development for web applications and Node.js runtime",
            "Rust memory safety without garbage collection using ownership",
            "Go concurrency with goroutines and channels for scalable systems",
            "TypeScript adds static types to JavaScript for better tooling",
        ]
        metadatas = [
            {"language": "python", "category": "general"},
            {"language": "javascript", "category": "web"},
            {"language": "rust", "category": "systems"},
            {"language": "go", "category": "backend"},
            {"language": "typescript", "category": "web"},
        ]

        # Upsert documents into PostgreSQL
        await postgres_backend.upsert_documents(ids, embeddings, documents, metadatas)

        # Verify count
        count = await postgres_backend.get_count()
        assert count == 5, f"Expected 5 documents, got {count}"

        # Execute vector search with deterministic query embedding
        query_embedding = [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        results = await postgres_backend.vector_search(
            query_embedding=query_embedding,
            top_k=5,
            similarity_threshold=0.0,
        )

        # Assert results are valid
        assert results, "Expected non-empty search results"
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(
            0.0 <= r.score <= 1.0 for r in results
        ), f"Scores out of range: {[r.score for r in results]}"

        # Top result should be Python (closest to query embedding)
        assert (
            results[0].chunk_id == "py-001"
        ), f"Expected py-001 as top result, got {results[0].chunk_id}"

    async def test_health_postgres_pool_metrics(
        self, postgres_backend: PostgresBackend
    ) -> None:
        """Test connection pool metrics returned by get_pool_status.

        Validates Success Criteria #4: Pool metrics test validates
        get_pool_status() returns expected keys with valid values.
        """
        metrics = await postgres_backend.connection_manager.get_pool_status()

        # Assert expected keys present
        assert isinstance(metrics, dict), f"Expected dict, got {type(metrics)}"
        assert "status" in metrics, "Missing 'status' key"
        assert (
            metrics["status"] == "active"
        ), f"Expected active, got {metrics['status']}"

        # Assert pool metrics keys
        expected_keys = {"pool_size", "checked_in", "checked_out", "overflow", "total"}
        assert expected_keys.issubset(
            metrics.keys()
        ), f"Missing keys: {expected_keys - metrics.keys()}"

        # Assert values are valid
        assert metrics["pool_size"] >= 0, "pool_size must be non-negative"
        assert metrics["checked_in"] >= 0, "checked_in must be non-negative"
        assert metrics["checked_out"] >= 0, "checked_out must be non-negative"
        assert metrics["overflow"] >= 0, "overflow must be non-negative"
        assert metrics["total"] >= metrics["pool_size"], "total must be >= pool_size"
        assert (
            metrics["total"] == metrics["pool_size"] + metrics["overflow"]
        ), "total should equal pool_size + overflow"

    async def test_document_persistence_across_operations(
        self, postgres_backend: PostgresBackend, tmp_path: Path
    ) -> None:
        """Test documents persist correctly across multiple operations.

        Validates that data persists in PostgreSQL and accumulates correctly
        through multiple upsert operations.
        """
        # Seed 3 initial documents
        ids_batch1 = ["doc-a", "doc-b", "doc-c"]
        embeddings_batch1 = [
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]
        documents_batch1 = [
            "First batch document A",
            "First batch document B",
            "First batch document C",
        ]
        metadatas_batch1 = [
            {"batch": 1, "idx": 0},
            {"batch": 1, "idx": 1},
            {"batch": 1, "idx": 2},
        ]

        await postgres_backend.upsert_documents(
            ids_batch1, embeddings_batch1, documents_batch1, metadatas_batch1
        )

        # Verify count after first batch
        count1 = await postgres_backend.get_count()
        assert count1 == 3, f"Expected 3 documents after first batch, got {count1}"

        # Verify retrieval works
        query_embedding = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        results1 = await postgres_backend.vector_search(
            query_embedding=query_embedding,
            top_k=3,
            similarity_threshold=0.0,
        )
        assert results1, "Expected results after first batch"
        assert len(results1) == 3, f"Expected 3 results, got {len(results1)}"

        # Seed 2 more documents
        ids_batch2 = ["doc-d", "doc-e"]
        embeddings_batch2 = [
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        ]
        documents_batch2 = [
            "Second batch document D",
            "Second batch document E",
        ]
        metadatas_batch2 = [
            {"batch": 2, "idx": 0},
            {"batch": 2, "idx": 1},
        ]

        await postgres_backend.upsert_documents(
            ids_batch2, embeddings_batch2, documents_batch2, metadatas_batch2
        )

        # Verify count after second batch
        count2 = await postgres_backend.get_count()
        assert count2 == 5, f"Expected 5 documents after second batch, got {count2}"


class TestCrossBackendConsistency:
    """Cross-backend consistency tests comparing ChromaDB and PostgreSQL."""

    async def test_hybrid_search_similarity_chroma_vs_postgres(
        self, postgres_backend: PostgresBackend, tmp_path: Path
    ) -> None:
        """Test hybrid search results overlap between ChromaDB and PostgreSQL.

        Validates Success Criteria #2: Cross-backend consistency test confirms
        60%+ Jaccard overlap in top-5 hybrid results between ChromaDB and PostgreSQL.
        """
        # Create ChromaDB backend
        chroma_vector_store = VectorStoreManager()
        chroma_vector_store.persist_dir = str(tmp_path / "chroma")

        chroma_bm25_manager = BM25IndexManager()
        chroma_bm25_manager.persist_dir = str(tmp_path / "bm25")

        chroma_backend = ChromaBackend(
            vector_store=chroma_vector_store, bm25_manager=chroma_bm25_manager
        )
        await chroma_backend.initialize()

        try:
            # Seed identical data into both backends
            ids = ["doc-1", "doc-2", "doc-3", "doc-4", "doc-5"]
            embeddings = [
                [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            ]
            documents = [
                "Python programming language",
                "FastAPI web framework",
                "PostgreSQL database system",
                "ChromaDB vector store",
                "pytest testing framework",
            ]
            metadatas = [{"source_type": "doc", "sequence": i} for i in range(len(ids))]

            # Upsert to both backends
            await chroma_backend.upsert_documents(ids, embeddings, documents, metadatas)
            await postgres_backend.upsert_documents(
                ids, embeddings, documents, metadatas
            )

            # Build BM25 index for ChromaDB
            nodes = [
                TextNode(text=doc, id_=chunk_id, metadata=meta)
                for chunk_id, doc, meta in zip(ids, documents, metadatas, strict=True)
            ]
            chroma_backend.bm25_manager.build_index(nodes)

            # Execute hybrid search on both backends
            query_text = "Python programming"
            query_embedding = [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

            # PostgreSQL hybrid search
            postgres_results = await postgres_backend.hybrid_search_with_rrf(
                query=query_text,
                query_embedding=query_embedding,
                top_k=5,
            )

            # ChromaDB hybrid search (manual RRF fusion)
            chroma_vector_results = await chroma_backend.vector_search(
                query_embedding=query_embedding,
                top_k=5,
                similarity_threshold=0.0,
            )
            chroma_keyword_results = await chroma_backend.keyword_search(
                query=query_text,
                top_k=5,
            )
            chroma_results = self._rrf_fuse(
                chroma_vector_results, chroma_keyword_results, top_k=5
            )

            # Extract top-5 chunk_ids
            postgres_ids = {result.chunk_id for result in postgres_results[:5]}
            chroma_ids = {result.chunk_id for result in chroma_results[:5]}

            # Calculate Jaccard similarity
            intersection = len(postgres_ids & chroma_ids)
            union = len(postgres_ids | chroma_ids)
            similarity = intersection / union if union > 0 else 0.0

            assert similarity >= 0.6, (
                f"Expected >= 60% overlap, got {similarity:.1%} "
                f"(postgres: {postgres_ids}, chroma: {chroma_ids})"
            )

        finally:
            await chroma_backend.reset()

    def _rrf_fuse(
        self,
        vector_results: list[SearchResult],
        keyword_results: list[SearchResult],
        top_k: int,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        rrf_k: int = 60,
    ) -> list[SearchResult]:
        """Perform RRF fusion on vector and keyword search results."""
        rrf_scores: dict[str, float] = {}
        result_map: dict[str, SearchResult] = {}

        for rank, result in enumerate(vector_results):
            rrf_scores[result.chunk_id] = rrf_scores.get(result.chunk_id, 0.0) + (
                vector_weight / (rank + rrf_k)
            )
            result_map[result.chunk_id] = result

        for rank, result in enumerate(keyword_results):
            rrf_scores[result.chunk_id] = rrf_scores.get(result.chunk_id, 0.0) + (
                keyword_weight / (rank + rrf_k)
            )
            if result.chunk_id not in result_map:
                result_map[result.chunk_id] = result

        if not rrf_scores:
            return []

        sorted_ids = sorted(
            rrf_scores.keys(),
            key=lambda chunk_id: rrf_scores[chunk_id],
            reverse=True,
        )[:top_k]

        max_rrf = max(rrf_scores.values()) or 1.0
        return [
            SearchResult(
                text=result_map[chunk_id].text,
                metadata=result_map[chunk_id].metadata,
                score=rrf_scores[chunk_id] / max_rrf,
                chunk_id=chunk_id,
            )
            for chunk_id in sorted_ids
        ]
