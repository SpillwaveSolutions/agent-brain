"""Parametrized contract tests for ``StorageBackendProtocol.get_chunk_by_id``.

These tests assert the v2-design-doc §2.3 ChunkRecord contract holds
identically for both backends (ChromaDB always; Postgres skipped without
``DATABASE_URL``).

The Postgres path also covers a small performance-style assertion: lookup
against a fixture corpus with >=1,000 chunks must complete in <50 ms,
matching the O(1) primary-key index contract the plan locks.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from agent_brain_server.models.query import ChunkRecord

pytestmark = pytest.mark.asyncio

# Vector embedding dimensions match the contract-conftest provider config
# (dimensions: 8 — see _write_provider_config in tests/contract/conftest.py).
BASE_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]

# v2 design doc §2.3 — locked field set on ChunkRecord. Drift here means
# the wire shape changed; downstream MCP Phase 51 work breaks if a field
# is added/removed without coordination.
EXPECTED_CHUNK_RECORD_FIELDS: set[str] = {
    "chunk_id",
    "parent_doc_id",
    "source",
    "content",
    "summary",
    "folder_id",
    "token_count",
    "language",
}


def _chunk_metadata(
    *,
    source: str,
    summary: str | None = None,
    language: str | None = None,
    token_count: int | None = None,
) -> dict[str, Any]:
    """Build a metadata dict matching how IndexingService writes chunks."""
    meta: dict[str, Any] = {"source_type": "doc", "source": source}
    if summary is not None:
        meta["section_summary"] = summary
    if language is not None:
        meta["language"] = language
    if token_count is not None:
        meta["token_count"] = token_count
    return meta


class TestGetChunkByIdContract:
    """Cross-backend contract suite for ``get_chunk_by_id``."""

    async def test_returns_chunk_record_when_found(
        self,
        storage_backend: Any,
    ) -> None:
        """Existing chunk_id returns a populated ChunkRecord."""
        chunk_id = "chunk-known-1"
        source = "/tmp/docs/intro.md"

        await storage_backend.upsert_documents(
            ids=[chunk_id],
            embeddings=[BASE_EMBEDDING],
            documents=["Hello, world. This is the content."],
            metadatas=[
                _chunk_metadata(
                    source=source,
                    summary="An intro section.",
                    token_count=42,
                )
            ],
        )

        record = await storage_backend.get_chunk_by_id(chunk_id)

        assert record is not None
        assert isinstance(record, ChunkRecord)
        assert record.chunk_id == chunk_id
        assert record.content == "Hello, world. This is the content."
        assert record.source == source
        # parent_doc_id falls back to source when not explicitly set.
        assert record.parent_doc_id == source
        # folder_id falls back to dirname(source) when not explicitly set.
        assert record.folder_id == "/tmp/docs"
        assert record.summary == "An intro section."
        assert record.token_count == 42
        # Language defaults to None for doc chunks.
        assert record.language is None

    async def test_returns_none_when_missing(self, storage_backend: Any) -> None:
        """Unknown chunk_id returns None (no exception)."""
        record = await storage_backend.get_chunk_by_id("does-not-exist")
        assert record is None

    async def test_field_set_matches_design_doc(
        self,
        storage_backend: Any,
    ) -> None:
        """``ChunkRecord.model_dump()`` keys must equal v2 design doc §2.3."""
        chunk_id = "chunk-shape-check"
        source = "/tmp/code/auth.py"

        await storage_backend.upsert_documents(
            ids=[chunk_id],
            embeddings=[BASE_EMBEDDING],
            documents=["def authenticate(user): ..."],
            metadatas=[
                _chunk_metadata(source=source, language="python", token_count=8)
            ],
        )

        record = await storage_backend.get_chunk_by_id(chunk_id)
        assert record is not None

        dumped = record.model_dump()
        assert set(dumped.keys()) == EXPECTED_CHUNK_RECORD_FIELDS
        # Critical: embedding MUST NOT leak into the response shape.
        assert "embedding" not in dumped

    async def test_language_propagates_for_code_chunks(
        self,
        storage_backend: Any,
    ) -> None:
        """``language`` flows through for code chunks."""
        chunk_id = "chunk-code-1"
        source = "/tmp/src/app.ts"

        await storage_backend.upsert_documents(
            ids=[chunk_id],
            embeddings=[BASE_EMBEDDING],
            documents=["export const x = 1;"],
            metadatas=[
                _chunk_metadata(
                    source=source, language="typescript", token_count=6
                )
            ],
        )

        record = await storage_backend.get_chunk_by_id(chunk_id)
        assert record is not None
        assert record.language == "typescript"


class TestGetChunkByIdPerformance:
    """Postgres-only performance assertion on the O(1) primary-key lookup."""

    async def test_lookup_under_50ms_on_1k_corpus(
        self,
        postgres_backend: Any,
    ) -> None:
        """Lookup against >=1,000 chunks completes in <50 ms (PK-index path).

        Skipped automatically when Postgres is unavailable (the
        ``postgres_backend`` fixture handles the skip).
        """
        corpus_size = 1_000
        ids = [f"perf-chunk-{i:04d}" for i in range(corpus_size)]
        documents = [f"content for chunk {i}" for i in range(corpus_size)]
        embeddings = [BASE_EMBEDDING for _ in range(corpus_size)]
        metadatas = [
            _chunk_metadata(
                source=f"/tmp/perf/file_{i:04d}.md", token_count=4
            )
            for i in range(corpus_size)
        ]

        await postgres_backend.upsert_documents(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        target_id = ids[corpus_size // 2]

        # Warm up to avoid first-call connection-pool variance.
        await postgres_backend.get_chunk_by_id(target_id)

        start = time.perf_counter()
        record = await postgres_backend.get_chunk_by_id(target_id)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        assert record is not None
        assert record.chunk_id == target_id
        assert elapsed_ms < 50.0, (
            f"Postgres get_chunk_by_id took {elapsed_ms:.2f}ms on a "
            f"{corpus_size}-chunk corpus; expected <50ms via PK index."
        )
