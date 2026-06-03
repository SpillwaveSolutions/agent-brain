"""Phase 54 Plan 01 — ApiClient method contracts for 5 new routes.

Mirrors the v1 ``MockTransport`` pattern from ``conftest.make_httpx_client``:
each test wires an :class:`httpx.MockTransport` handler that captures the
request method, path, query string, and body, then asserts on the captured
request shape.

The 5 methods under test:

* :meth:`ApiClient.add_documents` → ``POST /index/add?force=<bool>``
* :meth:`ApiClient.inject_documents` → ``POST /index/?force=<bool>``
  (same endpoint as v1 ``index_folder``; differentiator is the request
  body always carries ``injector_script`` and/or ``folder_metadata_file``
  — that policy lives in the MCP handler, not the client, so this test
  only proves the route + body passthrough)
* :meth:`ApiClient.cache_status` → ``GET /index/cache/``
* :meth:`ApiClient.clear_cache` → ``DELETE /index/cache/``
* :meth:`ApiClient.delete_folder` → ``DELETE /index/folders/`` with
  body (NOT query/path)
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from agent_brain_mcp.client import ApiClient


def _make_capturing_client(
    response_body: dict[str, Any],
    response_status: int = 200,
) -> tuple[httpx.Client, list[httpx.Request]]:
    """Return (client, captured_requests). The list is appended in-place
    every time ``handler`` runs, so tests inspect it after calling.
    """
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(response_status, json=response_body)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://test-agent-brain")
    return client, captured


# ----------------------------- add_documents ----------------------------


class TestAddDocuments:
    def test_posts_to_index_add(self) -> None:
        client, captured = _make_capturing_client(
            {"job_id": "j1", "status": "queued", "message": "ok"}
        )
        api = ApiClient(client)
        body = {"folder_path": "/abs/repo/docs"}
        result = api.add_documents(body)
        assert result == {"job_id": "j1", "status": "queued", "message": "ok"}
        assert len(captured) == 1
        req = captured[0]
        assert req.method == "POST"
        assert req.url.path == "/index/add"
        # No force query when force=False (default)
        assert "force" not in dict(req.url.params)
        # Body round-trips verbatim
        assert json.loads(req.content) == body

    def test_force_true_sets_query_param(self) -> None:
        client, captured = _make_capturing_client(
            {"job_id": "j", "status": "queued", "message": "ok"}
        )
        api = ApiClient(client)
        api.add_documents({"folder_path": "/x"}, force=True)
        req = captured[0]
        assert req.url.path == "/index/add"
        assert dict(req.url.params) == {"force": "true"}

    def test_no_allow_external_query_param(self) -> None:
        """Defense-in-depth — even if a caller smuggled allow_external into
        the body, the *route* the method targets is /index/add (which
        ignores allow_external server-side per #180). The method MUST NOT
        construct ?allow_external= in any path."""
        client, captured = _make_capturing_client({"job_id": "j", "status": "queued"})
        api = ApiClient(client)
        api.add_documents({"folder_path": "/x", "allow_external": True}, force=True)
        req = captured[0]
        assert "allow_external" not in dict(req.url.params)


# ----------------------------- inject_documents -------------------------


class TestInjectDocuments:
    def test_posts_to_index_root(self) -> None:
        """inject_documents hits the SAME endpoint as v1 index_folder; the
        differentiator is the body, not the URL."""
        client, captured = _make_capturing_client(
            {"job_id": "j", "status": "queued", "message": "ok"}
        )
        api = ApiClient(client)
        body = {
            "folder_path": "/abs/repo",
            "injector_script": "/abs/repo/inject.py",
        }
        api.inject_documents(body)
        req = captured[0]
        assert req.method == "POST"
        assert req.url.path == "/index/"
        assert "force" not in dict(req.url.params)
        assert json.loads(req.content) == body

    def test_force_true_sets_query_param(self) -> None:
        client, captured = _make_capturing_client({"job_id": "j", "status": "queued"})
        api = ApiClient(client)
        api.inject_documents(
            {"folder_path": "/x", "injector_script": "/i.py"},
            force=True,
        )
        req = captured[0]
        assert req.url.path == "/index/"
        assert dict(req.url.params) == {"force": "true"}

    def test_dry_run_body_passes_through(self) -> None:
        """The MCP handler sets dry_run=True in the body; the client only
        needs to pass it through unmolested."""
        client, captured = _make_capturing_client(
            {"job_id": "dry_run", "status": "completed", "message": "report"}
        )
        api = ApiClient(client)
        body = {
            "folder_path": "/x",
            "injector_script": "/i.py",
            "dry_run": True,
        }
        result = api.inject_documents(body)
        assert result["job_id"] == "dry_run"
        assert json.loads(captured[0].content)["dry_run"] is True


# ----------------------------- cache_status / clear_cache ---------------


class TestCacheStatus:
    def test_gets_index_cache(self) -> None:
        body = {
            "hits": 10,
            "misses": 2,
            "hit_rate": 0.83,
            "mem_entries": 12,
            "entry_count": 1234,
            "size_bytes": 4096,
        }
        client, captured = _make_capturing_client(body)
        api = ApiClient(client)
        result = api.cache_status()
        assert result == body
        req = captured[0]
        assert req.method == "GET"
        assert req.url.path == "/index/cache/"
        assert req.content == b""


class TestClearCache:
    def test_deletes_index_cache(self) -> None:
        body = {"count": 42, "size_bytes": 4096, "size_mb": 0.0039}
        client, captured = _make_capturing_client(body)
        api = ApiClient(client)
        result = api.clear_cache()
        assert result == body
        req = captured[0]
        assert req.method == "DELETE"
        assert req.url.path == "/index/cache/"
        # Unconditional — no confirm body required; the MCP handler enforces
        # the Literal[True] confirm at the schema layer.
        assert req.content == b""


# ----------------------------- delete_folder ----------------------------


class TestDeleteFolder:
    def test_deletes_index_folders_with_body(self) -> None:
        """FolderDeleteRequest is a request *body*, not a query parameter."""
        body = {
            "folder_path": "/abs/repo/docs",
            "chunks_deleted": 42,
            "message": "ok",
        }
        client, captured = _make_capturing_client(body)
        api = ApiClient(client)
        result = api.delete_folder({"folder_path": "/abs/repo/docs"})
        assert result == body
        req = captured[0]
        assert req.method == "DELETE"
        assert req.url.path == "/index/folders/"
        # JSON body MUST be present — server route declares FolderDeleteRequest
        # as the request body.
        assert json.loads(req.content) == {"folder_path": "/abs/repo/docs"}


# ----------------------------- error-path passthrough --------------------


class TestErrorPathsPassThroughExistingPipeline:
    """Smoke-prove that the 5 new methods route HTTP failures through the
    existing raise_for_status pipeline — no per-method error mapping needed
    (CONTEXT decision G). We use 404 as a representative because cache_status
    is a GET and 4xx will fire ``McpError`` via :func:`errors.raise_for_status`.
    """

    def test_cache_status_404_raises(self) -> None:
        from mcp.shared.exceptions import McpError

        client, _ = _make_capturing_client({"detail": "not found"}, response_status=404)
        api = ApiClient(client)
        with pytest.raises(McpError):
            api.cache_status()

    def test_delete_folder_409_raises(self) -> None:
        """409 active-job-for-folder (FOLD-07) surfaces as McpError."""
        from mcp.shared.exceptions import McpError

        client, _ = _make_capturing_client(
            {"detail": "job active for folder"}, response_status=409
        )
        api = ApiClient(client)
        with pytest.raises(McpError):
            api.delete_folder({"folder_path": "/x"})
