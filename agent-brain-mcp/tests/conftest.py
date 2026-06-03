"""Shared pytest fixtures for agent-brain-mcp tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

# Default backend responses used by most tests. Individual tests can
# pass their own ``responses`` dict to override one or more paths.
_DEFAULT_RESPONSES: dict[tuple[str, str], dict[str, Any]] = {
    ("GET", "/health/"): {
        "status": "healthy",
        "message": "ok",
        "version": "10.0.7",
        "mode": "project",
        "instance_id": "test123",
    },
    ("GET", "/health/status"): {
        "total_documents": 42,
        "total_chunks": 420,
        "indexing_in_progress": False,
        "current_job_id": None,
        "progress_percent": 0.0,
        "indexed_folders": ["/tmp/test"],
    },
    ("GET", "/health/config"): {
        "storage_backend": "chroma",
        "stores": {"vector": True, "bm25": True, "graph": False},
        "reranker_enabled": False,
        "embedding_model": "text-embedding-3-large",
        "rerank_model": None,
        "graph_extractor": None,
        "watcher_running": False,
    },
    ("GET", "/health/providers"): {
        "config_source": None,
        "strict_mode": False,
        "validation_errors": [],
        "providers": [],
        "timestamp": "2026-05-28T00:00:00Z",
    },
    ("GET", "/query/count"): {"total_documents": 42, "total_chunks": 420},
    ("POST", "/query/"): {
        "query": "test",
        "mode": "hybrid",
        "total_results": 1,
        "query_time_ms": 12.3,
        "results": [
            {
                "text": "hit",
                "source": "/tmp/test/file.py",
                "score": 0.99,
                "chunk_id": "chunk_001",
                "metadata": {"line": 1},
            }
        ],
    },
    ("POST", "/index/"): {
        "job_id": "job_abc",
        "status": "queued",
        "message": "Folder queued for indexing",
    },
    ("GET", "/index/jobs/job_abc"): {
        "job_id": "job_abc",
        "status": "running",
        "progress_percent": 50.0,
        "message": "Processing...",
    },
    # Phase 51 (51-01) job:// resource fixtures. The detailed body
    # mirrors a real JobDetailResponse so the read shape contract is
    # validated end-to-end through the parameterized dispatcher.
    ("GET", "/index/jobs/job_51_full"): {
        "job_id": "job_51_full",
        "status": "running",
        "progress_percent": 73.5,
        "message": "Indexing /tmp/repo (147 / 200 files)",
        "folder_path": "/tmp/repo",
        "started_at": "2026-06-03T05:00:00Z",
        "updated_at": "2026-06-03T05:02:34Z",
        "files_processed": 147,
        "files_total": 200,
    },
    ("GET", "/index/jobs/"): {
        "jobs": [
            {"job_id": "j1", "status": "completed", "progress_percent": 100.0},
            {"job_id": "j2", "status": "running", "progress_percent": 30.0},
        ]
    },
    ("DELETE", "/index/jobs/job_abc"): {
        "cancelled": True,
        "message": "Job cancelled",
    },
    ("GET", "/index/folders/"): {
        "folders": [
            {
                "folder_path": "/tmp/test",
                "chunk_count": 420,
                "last_indexed": "2026-05-28T00:00:00Z",
                "watch_mode": "off",
                "watch_debounce_seconds": 30,
            }
        ]
    },
}


def make_httpx_client(
    *,
    responses: dict[tuple[str, str], dict[str, Any]] | None = None,
    status_overrides: dict[tuple[str, str], int] | None = None,
    error_paths: dict[tuple[str, str], Exception] | None = None,
) -> httpx.Client:
    """Build an httpx.Client whose MockTransport returns the given JSON
    or raises the given exceptions.

    Args:
        responses: Override default JSON responses by (METHOD, path).
        status_overrides: Force a specific HTTP status for a (METHOD, path).
        error_paths: Raise a transport-level exception for a path.
    """
    merged = dict(_DEFAULT_RESPONSES)
    if responses:
        merged.update(responses)
    overrides = status_overrides or {}
    errors = error_paths or {}

    def handler(request: httpx.Request) -> httpx.Response:
        key = (request.method, request.url.path)
        if key in errors:
            raise errors[key]
        status = overrides.get(key, 200)
        body = merged.get(key, {"detail": f"not configured: {key}"})
        return httpx.Response(status, json=body)

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url="http://test-agent-brain")


@pytest.fixture
def mock_client_factory() -> Callable[..., httpx.Client]:
    """Pytest fixture returning the make_httpx_client factory."""
    return make_httpx_client


@pytest.fixture
def fake_httpx_client() -> httpx.Client:
    """A default httpx.Client wired to default responses."""
    return make_httpx_client()
