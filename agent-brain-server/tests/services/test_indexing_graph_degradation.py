"""Tests for per-job graph build degradation in IndexingService (Phase 64 / GSTAB-01).

When build_from_documents_isolated raises GraphBuildFailedError, the
indexing job must:
  1. Complete with status COMPLETED (not FAILED) -- vector + BM25 already committed.
  2. Log the GraphBuildFailedError at WARNING level.
  3. Still fail the job for non-graph exceptions (narrow catch).
  4. Surface graph_degraded flag and triplet_count == 0 in the job result.

These tests monkeypatch build_from_documents_isolated so no real kuzu db or
subprocess is needed.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_brain_server.models import IndexingStatusEnum
from agent_brain_server.storage.graph_errors import GraphBuildFailedError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_service() -> Any:
    """Build an IndexingService with all I/O mocked out.

    The service is wired so that the main pipeline steps succeed quickly
    (document load, chunk, embed, store) and only the graph build is the
    test subject.

    Key mocking decisions:
    - document_loader.load_files returns 1 fake doc
    - chunker.chunk_documents returns 1 fake chunk (no code files)
    - embedding_generator.embed_chunks is async, returns [[0.1, 0.2, 0.3]]
    - storage_backend: all async methods are AsyncMock
    - bm25_manager.build_index is a sync MagicMock (called via asyncio.to_thread)
    - graph_index_manager.get_status returns a simple MagicMock
    """
    from agent_brain_server.services.indexing_service import IndexingService

    # Storage backend mock -- all async I/O mocked
    storage_backend = MagicMock()
    storage_backend.is_initialized = True
    storage_backend.initialize = AsyncMock()
    storage_backend.get_count = AsyncMock(return_value=3)
    storage_backend.add_chunks = AsyncMock()
    storage_backend.get_embedding_metadata = AsyncMock(return_value=None)
    storage_backend.validate_embedding_compatibility = MagicMock()
    storage_backend.upsert_documents = AsyncMock()
    storage_backend.set_embedding_metadata = AsyncMock()

    # BM25 manager mock -- build_index is sync (called via asyncio.to_thread).
    # Must be set on storage_backend.bm25_manager so the service's __init__
    # picks it up from there (it checks hasattr(storage_backend, 'bm25_manager')).
    bm25_manager = MagicMock()
    bm25_manager.build_index = MagicMock()
    storage_backend.bm25_manager = bm25_manager

    # Document loader mock -- returns 1 fake document (type "doc")
    fake_doc = MagicMock()
    fake_doc.metadata = {"source_type": "doc", "source": "/fake/doc.txt"}
    fake_doc.text = "Alice works at ACME."
    document_loader = MagicMock()
    document_loader.load_files = AsyncMock(return_value=[fake_doc])

    # Chunker mock -- returns 1 fake chunk with proper metadata
    fake_meta = MagicMock()
    fake_meta.to_dict = MagicMock(
        return_value={"source_type": "doc", "source": "/fake/doc.txt"}
    )
    fake_chunk = MagicMock()
    fake_chunk.chunk_id = "chunk-001"
    fake_chunk.text = "Alice works at ACME."
    fake_chunk.metadata = fake_meta
    chunker = MagicMock()
    chunker.chunk_documents = AsyncMock(return_value=[fake_chunk])

    # Embedding generator mock -- embed_chunks is async
    embedding_generator = MagicMock()
    embedding_generator.embed_chunks = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    embedding_generator.get_embedding_dimensions = MagicMock(return_value=3)

    # Graph index manager mock -- get_status called by get_status()
    graph_status_mock = MagicMock()
    graph_status_mock.enabled = True
    graph_status_mock.initialized = True
    graph_status_mock.entity_count = 0
    graph_status_mock.relationship_count = 0
    graph_status_mock.store_type = "kuzu"
    graph_index_manager = MagicMock()
    graph_index_manager.get_status = MagicMock(return_value=graph_status_mock)

    svc = IndexingService(
        storage_backend=storage_backend,
        document_loader=document_loader,
        chunker=chunker,
        embedding_generator=embedding_generator,
        graph_index_manager=graph_index_manager,
    )
    return svc


def _run(coro: Any) -> Any:
    """Run an async coroutine in the test event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Test 1: Graph failure leaves job COMPLETED with vector+BM25 intact
# ---------------------------------------------------------------------------


class TestGraphFailureLeavesJobCompleted:
    """When build_from_documents_isolated raises GraphBuildFailedError,
    the indexing job must complete with status COMPLETED -- NOT FAILED --
    because vector + BM25 indexing already committed."""

    def test_graph_build_failed_error_does_not_fail_job(self) -> None:
        """A GraphBuildFailedError in step 6 leaves job status COMPLETED."""
        from agent_brain_server.models import IndexRequest

        svc = _make_minimal_service()
        request = IndexRequest(folder_path="/fake/docs", recursive=False)

        graph_exc = GraphBuildFailedError(
            "Graph build failed (exit_code=139); set graphrag.store_type=simple",
            exit_code=139,
        )

        with (
            patch(
                "agent_brain_server.services.indexing_service._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.services.indexing_service"
                ".build_from_documents_isolated",
                side_effect=graph_exc,
            ),
        ):
            _run(svc._run_indexing_pipeline(request, job_id="job-degraded-001"))

        assert svc._state.status == IndexingStatusEnum.COMPLETED, (
            f"Job must be COMPLETED after graph degradation, "
            f"got {svc._state.status}"
        )

    def test_job_not_failed_status_on_graph_error(self) -> None:
        """Job status must not be FAILED when only the graph build fails."""
        from agent_brain_server.models import IndexRequest

        svc = _make_minimal_service()
        request = IndexRequest(folder_path="/fake/docs", recursive=False)

        with (
            patch(
                "agent_brain_server.services.indexing_service._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.services.indexing_service"
                ".build_from_documents_isolated",
                side_effect=GraphBuildFailedError("graph failed", exit_code=1),
            ),
        ):
            _run(svc._run_indexing_pipeline(request, job_id="job-degraded-002"))

        assert svc._state.status != IndexingStatusEnum.FAILED


# ---------------------------------------------------------------------------
# Test 2: GraphBuildFailedError is logged at WARNING
# ---------------------------------------------------------------------------


class TestGraphDegradationIsLogged:
    """The GraphBuildFailedError must be logged at WARNING so the operator
    sees the clear degradation reason."""

    def test_graph_degradation_logged_at_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """WARNING log is emitted with the graph failure message."""
        from agent_brain_server.models import IndexRequest

        svc = _make_minimal_service()
        request = IndexRequest(folder_path="/fake/docs", recursive=False)

        with (
            caplog.at_level(logging.WARNING),
            patch(
                "agent_brain_server.services.indexing_service._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.services.indexing_service"
                ".build_from_documents_isolated",
                side_effect=GraphBuildFailedError(
                    "Graph build failed (exit_code=139); store_type=simple",
                    exit_code=139,
                ),
            ),
        ):
            _run(svc._run_indexing_pipeline(request, job_id="job-log-test"))

        # At least one WARNING log must mention graph degradation
        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any(
            "graph" in r.message.lower()
            or "degraded" in r.message.lower()
            or "graph" in str(r.args).lower()
            for r in warning_records
        ), (
            f"Expected a WARNING log mentioning graph degradation. "
            f"Got: {[r.getMessage() for r in warning_records]}"
        )


# ---------------------------------------------------------------------------
# Test 3: Non-graph exceptions still fail the job
# ---------------------------------------------------------------------------


class TestNonGraphExceptionFailsJob:
    """A non-GraphBuildFailedError exception must still mark the job FAILED.
    The catch in step 6 is narrow (graph-only)."""

    def test_vector_store_error_fails_job(self) -> None:
        """A RuntimeError from the vector store (not a graph error) fails the job."""
        from agent_brain_server.models import IndexRequest

        svc = _make_minimal_service()
        # Make the vector store raise an error during upsert (step 4)
        svc.storage_backend.upsert_documents = AsyncMock(
            side_effect=RuntimeError("Vector store connection lost")
        )
        request = IndexRequest(folder_path="/fake/docs", recursive=False)

        with pytest.raises(RuntimeError, match="Vector store connection lost"):
            _run(svc._run_indexing_pipeline(request, job_id="job-vec-fail"))

        assert svc._state.status == IndexingStatusEnum.FAILED

    def test_graph_build_failed_error_does_not_propagate(self) -> None:
        """GraphBuildFailedError must be fully swallowed (not re-raised)."""
        from agent_brain_server.models import IndexRequest

        svc = _make_minimal_service()
        request = IndexRequest(folder_path="/fake/docs", recursive=False)

        with (
            patch(
                "agent_brain_server.services.indexing_service._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.services.indexing_service"
                ".build_from_documents_isolated",
                side_effect=GraphBuildFailedError("graph failed", exit_code=1),
            ),
        ):
            # Must NOT raise -- the exception must be fully handled
            _run(svc._run_indexing_pipeline(request, job_id="job-swallow"))


# ---------------------------------------------------------------------------
# Test 4: Graph degraded marker in job result / status
# ---------------------------------------------------------------------------


class TestGraphDegradedMarkerInStatus:
    """After a degraded graph build, the job result surfaces that the graph
    was skipped this run. Vector/BM25 chunk counts are non-zero."""

    def test_graph_degraded_field_set_on_failure(self) -> None:
        """_state.graph_degraded is True after a GraphBuildFailedError."""
        from agent_brain_server.models import IndexRequest

        svc = _make_minimal_service()
        request = IndexRequest(folder_path="/fake/docs", recursive=False)

        with (
            patch(
                "agent_brain_server.services.indexing_service._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.services.indexing_service"
                ".build_from_documents_isolated",
                side_effect=GraphBuildFailedError("graph failed", exit_code=1),
            ),
        ):
            _run(svc._run_indexing_pipeline(request, job_id="job-marker"))

        assert (
            svc._state.graph_degraded is True
        ), "IndexingState.graph_degraded must be True after graph build failure"

    def test_graph_degraded_in_get_status(self) -> None:
        """get_status() includes 'degraded_last_run': True in the graph_index dict."""
        from agent_brain_server.models import IndexRequest

        svc = _make_minimal_service()
        request = IndexRequest(folder_path="/fake/docs", recursive=False)

        with (
            patch(
                "agent_brain_server.services.indexing_service._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.services.indexing_service"
                ".build_from_documents_isolated",
                side_effect=GraphBuildFailedError("graph failed", exit_code=1),
            ),
        ):
            _run(svc._run_indexing_pipeline(request, job_id="job-status"))

        status = _run(svc.get_status())

        graph_info = status.get("graph_index", {})
        assert graph_info.get("degraded_last_run") is True, (
            f"get_status() must include graph_index.degraded_last_run=True. "
            f"Got: {graph_info}"
        )

    def test_graph_degraded_false_on_success(self) -> None:
        """graph_degraded is False when graph build succeeds."""
        from agent_brain_server.models import IndexRequest

        svc = _make_minimal_service()
        request = IndexRequest(folder_path="/fake/docs", recursive=False)

        with (
            patch(
                "agent_brain_server.services.indexing_service._graphrag_enabled",
                return_value=True,
            ),
            patch(
                "agent_brain_server.services.indexing_service"
                ".build_from_documents_isolated",
                return_value=7,
            ),
        ):
            _run(svc._run_indexing_pipeline(request, job_id="job-success"))

        assert (
            not svc._state.graph_degraded
        ), "graph_degraded must be False after a successful graph build"
