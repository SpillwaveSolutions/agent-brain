"""Hybrid search contract tests for backend alignment.

These tests validate that hybrid search behavior is reasonable for each backend
and that cross-backend results overlap meaningfully for the same query/data.
"""

from __future__ import annotations

from typing import Any

import os
import pytest
from llama_index.core.schema import TextNode

from agent_brain_server.storage.chroma.backend import ChromaBackend
from agent_brain_server.storage.protocol import SearchResult

pytestmark = pytest.mark.asyncio

HYBRID_DOCS = [
    (
        "doc-1",
        "Python programming language",
        [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    ),
    (
        "doc-2",
        "FastAPI web framework",
        [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    ),
    (
        "doc-3",
        "PostgreSQL database system",
        [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    ),
    (
        "doc-4",
        "ChromaDB vector store",
        [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
    ),
    (
        "doc-5",
        "pytest testing framework",
        [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
    ),
]

QUERY_EMBEDDING = [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def _postgres_available() -> bool:
    try:
        import asyncpg  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("DATABASE_URL"))


def _build_bm25_index_if_needed(
    storage_backend: Any,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    if not isinstance(storage_backend, ChromaBackend):
        return

    nodes = [
        TextNode(text=document, id_=chunk_id, metadata=metadata)
        for chunk_id, document, metadata in zip(ids, documents, metadatas, strict=True)
    ]
    storage_backend.bm25_manager.build_index(nodes)


async def _seed_documents(storage_backend: Any) -> None:
    ids = [doc_id for doc_id, _, _ in HYBRID_DOCS]
    documents = [text for _, text, _ in HYBRID_DOCS]
    embeddings = [embedding for _, _, embedding in HYBRID_DOCS]
    metadatas = [{"source_type": "doc", "sequence": i} for i in range(len(ids))]

    await storage_backend.upsert_documents(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    _build_bm25_index_if_needed(storage_backend, ids, documents, metadatas)


def _rrf_fuse(
    vector_results: list[SearchResult],
    keyword_results: list[SearchResult],
    top_k: int,
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
    rrf_k: int = 60,
) -> list[SearchResult]:
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


async def _hybrid_search(storage_backend: Any, top_k: int = 5) -> list[SearchResult]:
    if hasattr(storage_backend, "hybrid_search_with_rrf"):
        return await storage_backend.hybrid_search_with_rrf(
            query="Python programming",
            query_embedding=QUERY_EMBEDDING,
            top_k=top_k,
        )

    vector_results = await storage_backend.vector_search(
        query_embedding=QUERY_EMBEDDING,
        top_k=top_k,
        similarity_threshold=0.0,
    )
    keyword_results = await storage_backend.keyword_search(
        query="Python programming",
        top_k=top_k,
    )
    return _rrf_fuse(vector_results, keyword_results, top_k=top_k)


async def test_hybrid_search_returns_results(storage_backend: Any) -> None:
    await _seed_documents(storage_backend)

    results = await _hybrid_search(storage_backend, top_k=5)

    assert results
    assert all(isinstance(result, SearchResult) for result in results)
    assert all(0.0 <= result.score <= 1.0 for result in results)


async def test_keyword_search_returns_relevant_results(storage_backend: Any) -> None:
    await _seed_documents(storage_backend)

    results = await storage_backend.keyword_search(
        query="Python programming",
        top_k=5,
    )

    assert results
    assert "python" in results[0].text.lower()


@pytest.mark.postgres
@pytest.mark.skipif(not _postgres_available(), reason="DATABASE_URL not set")
async def test_hybrid_search_cross_backend_similarity(
    chroma_backend: ChromaBackend,
    postgres_backend: Any,
) -> None:
    await _seed_documents(chroma_backend)
    await _seed_documents(postgres_backend)

    chroma_results = await _hybrid_search(chroma_backend, top_k=5)
    postgres_results = await _hybrid_search(postgres_backend, top_k=5)

    chroma_ids = {result.chunk_id for result in chroma_results}
    postgres_ids = {result.chunk_id for result in postgres_results}

    similarity = len(chroma_ids & postgres_ids) / len(chroma_ids | postgres_ids)

    assert similarity >= 0.6
