"""Phase 57 Plan 03 — wire-level tests for the remaining 10 BackendClient
methods on McpStdioBackend + McpHttpBackend.

Plan 57-02 wired `query()` on both backends. Plan 57-03 wires the
remaining 10 methods per the design doc §2.3 method↔wire mapping:
`health`, `status`, `index`, `list_folders`, `delete_folder`,
`list_jobs`, `get_job`, `cancel_job`, `cache_status`, `clear_cache`.

`reset()` on both backends STAYS a deliberate NotImplementedError with
the verbatim §3.5 / §4-risks wording from CONTEXT.md §decisions —
covered by `test_*_reset_raises_verbatim_not_implemented_error` below.

These tests follow the wire-test fake-server pattern established by
Plan 57-02's `test_cli_backends_query_wire.py`: a self-contained Python
script wires `build_server` to an `httpx.MockTransport`; the test
spawns that script as a subprocess and asserts on the captured tool
arguments + the returned dataclass / dict shape.

The stdio leg runs in the fast pre-push gate; the http leg is opt-in
via the ``e2e_http`` marker per the existing precedent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The agent_brain_cli dataclasses live in a sibling package; the
# importorskip protects the test from environments that only have
# agent-brain-mcp installed (cf. Plan 56-03 conftest).
pytest.importorskip("agent_brain_cli.client.api_client")

from agent_brain_cli.client.api_client import (  # noqa: E402
    FolderInfo,
    HealthStatus,
    IndexingStatus,
    IndexResponse,
)

from agent_brain_mcp.client import McpHttpBackend, McpStdioBackend  # noqa: E402

# ---------------------------------------------------------------------------
# Fake-server script — registers tool + resource handlers and logs each
# inbound HTTP request to a file so the tests can assert on what the
# MCP server's handlers received (post-tool-dispatch the server hits
# the backing REST API via the wrapped httpx client, so logging the
# HTTP path + body proves the right tool was dispatched).
# ---------------------------------------------------------------------------

_FAKE_STDIO_SERVER_SCRIPT = r"""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from agent_brain_mcp.server import build_server, run_stdio

_LOG_PATH = Path(os.environ["TEST_WIRE_LOG_PATH"])
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


# Default response bodies for each path the test scenarios exercise.
_RESPONSES = {
    ("GET", "/health/"): {
        "status": "healthy",
        "version": "10.2.0",
        "message": "ok",
        "mode": "project",
        "instance_id": "wire-test",
        "timestamp": "2026-06-06T00:00:00Z",
    },
    ("GET", "/health/status"): {
        "total_documents": 7,
        "total_chunks": 42,
        "indexing_in_progress": False,
        "current_job_id": None,
        "progress_percent": 0.0,
        "indexed_folders": ["/tmp/seed"],
        "last_indexed_at": "2026-06-06T00:00:00Z",
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
        "timestamp": "2026-06-06T00:00:00Z",
    },
    ("GET", "/query/count"): {"total_documents": 7, "total_chunks": 42},
    ("GET", "/index/folders/"): {
        "folders": [
            {
                "folder_path": "/tmp/seed",
                "chunk_count": 42,
                "last_indexed": "2026-06-06",
                "watch_mode": "off",
                "watch_debounce_seconds": 30,
            },
            {
                "folder_path": "/tmp/other",
                "chunk_count": 3,
                "last_indexed": "2026-06-05",
                "watch_mode": "auto",
                "watch_debounce_seconds": 5,
            },
        ]
    },
    ("DELETE", "/index/folders/"): {
        "folder_path": "/tmp/seed",
        "chunks_deleted": 42,
        "message": "removed",
    },
    ("GET", "/index/jobs/"): {
        "jobs": [
            {"job_id": "job-a", "status": "completed"},
            {"job_id": "job-b", "status": "running"},
        ]
    },
    ("GET", "/index/jobs/job-123"): {
        "job_id": "job-123",
        "status": "completed",
        "progress_percent": 100.0,
    },
    ("DELETE", "/index/jobs/job-123"): {
        "job_id": "job-123",
        "cancelled": True,
        "message": "ok",
    },
    # cache_status output schema requires: hits, misses, hit_rate,
    # mem_entries, entry_count, size_bytes (all int/float, ge=0).
    ("GET", "/index/cache/"): {
        "hits": 10,
        "misses": 2,
        "hit_rate": 0.833,
        "mem_entries": 5,
        "entry_count": 5,
        "size_bytes": 1024,
    },
    # clear_cache output schema requires: count, size_bytes, size_mb.
    ("DELETE", "/index/cache/"): {
        "count": 5,
        "size_bytes": 1024,
        "size_mb": 0.001,
    },
    ("POST", "/index/"): {
        "job_id": "job-new",
        "status": "queued",
        "message": "enqueued",
        "folder_path": "/path/to/folder",
    },
}


def _handler(request):
    # Log every request so the tests can assert on path + method + body.
    body_raw = request.content.decode() if request.content else ""
    entry = {
        "method": request.method,
        "path": request.url.path,
        "query": str(request.url.query.decode()) if request.url.query else "",
        "body": body_raw,
    }
    with _LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    key = (request.method, request.url.path)
    body = _RESPONSES.get(key, {"detail": "not configured: " + str(key)})
    return httpx.Response(200, json=body)


async def main():
    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://wire-test",
    )
    server, manager = build_server(client)
    try:
        await run_stdio(server, manager)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
"""


@pytest.fixture
def fake_stdio_server_script(tmp_path: Path) -> Path:
    script = tmp_path / "fake_stdio_methods_server.py"
    script.write_text(_FAKE_STDIO_SERVER_SCRIPT)
    return script


@pytest.fixture
def wire_log_path(tmp_path: Path) -> Path:
    return tmp_path / "wire_log.jsonl"


def _stdio_backend(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> McpStdioBackend:
    """Build a McpStdioBackend that launches the fake server."""
    project_root = Path(__file__).resolve().parent.parent
    return McpStdioBackend(
        command=[sys.executable, str(fake_stdio_server_script)],
        cwd=str(project_root),
        env={
            "PYTHONPATH": str(project_root),
            "TEST_WIRE_LOG_PATH": str(wire_log_path),
        },
    )


def _read_log(wire_log_path: Path) -> list[dict]:
    import json as _json

    if not wire_log_path.exists():
        return []
    return [
        _json.loads(line) for line in wire_log_path.read_text().splitlines() if line
    ]


# ===========================================================================
# Task 1: 6 read-only methods on McpStdioBackend
# ===========================================================================


def test_stdio_health_returns_health_status_dataclass(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.health() returns a populated HealthStatus dataclass
    (wire: call_tool('server_health', {})).
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.health()
    assert isinstance(result, HealthStatus)
    assert result.status == "healthy"
    assert result.version == "10.2.0"
    # Indirect wire-shape proof: the server_health tool hits GET /health/.
    log = _read_log(wire_log_path)
    paths = {(e["method"], e["path"]) for e in log}
    assert ("GET", "/health/") in paths


def test_stdio_status_returns_indexing_status_dataclass(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.status() returns a populated IndexingStatus dataclass
    (wire: read_resource(AnyUrl('corpus://status'))).
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.status()
    assert isinstance(result, IndexingStatus)
    assert result.total_documents == 7
    assert result.total_chunks == 42
    assert result.indexing_in_progress is False
    assert result.indexed_folders == ["/tmp/seed"]
    # Indirect wire-shape proof: corpus://status resource hits GET /health/status.
    log = _read_log(wire_log_path)
    paths = {(e["method"], e["path"]) for e in log}
    assert ("GET", "/health/status") in paths


def test_stdio_list_folders_returns_folder_info_list(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.list_folders() returns list[FolderInfo]
    (wire: read_resource(AnyUrl('corpus://folders'))).
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.list_folders()
    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(f, FolderInfo) for f in result)
    assert result[0].folder_path == "/tmp/seed"
    assert result[0].chunk_count == 42
    assert result[1].watch_mode == "auto"
    # Indirect wire-shape proof: corpus://folders resource hits GET
    # /index/folders/.
    log = _read_log(wire_log_path)
    paths = {(e["method"], e["path"]) for e in log}
    assert ("GET", "/index/folders/") in paths


def test_stdio_get_job_returns_dict(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.get_job('job-123') returns dict
    (wire: read_resource(AnyUrl('job://job-123'))).
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.get_job("job-123")
    assert isinstance(result, dict)
    assert result["job_id"] == "job-123"
    assert result["status"] == "completed"
    # Indirect wire-shape proof: job://<id> resource hits GET /index/jobs/<id>.
    log = _read_log(wire_log_path)
    paths = {(e["method"], e["path"]) for e in log}
    assert ("GET", "/index/jobs/job-123") in paths


def test_stdio_list_jobs_returns_dict_list(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.list_jobs(limit=5) returns list[dict] from
    `result.structuredContent['jobs']` (wire: call_tool('list_jobs',
    {'limit': 5})).
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.list_jobs(limit=5)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["job_id"] == "job-a"
    # Indirect wire-shape proof: list_jobs tool hits GET /index/jobs/
    # with limit param.
    log = _read_log(wire_log_path)
    list_job_entries = [
        e for e in log if e["method"] == "GET" and e["path"] == "/index/jobs/"
    ]
    assert list_job_entries, "list_jobs tool must hit GET /index/jobs/"
    # limit should propagate into the query string.
    assert "limit=5" in list_job_entries[0]["query"]


def test_stdio_cache_status_returns_dict(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.cache_status() returns dict
    (wire: call_tool('cache_status', {})).
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.cache_status()
    assert isinstance(result, dict)
    assert result.get("hits") == 10
    assert result.get("misses") == 2
    assert result.get("hit_rate") == pytest.approx(0.833)
    # Indirect wire-shape proof: cache_status tool hits GET /index/cache/.
    log = _read_log(wire_log_path)
    paths = {(e["method"], e["path"]) for e in log}
    assert ("GET", "/index/cache/") in paths


# ===========================================================================
# Task 2: 4 mutating methods on McpStdioBackend + reset() sentinel
# ===========================================================================


def test_stdio_index_routes_to_index_folder_when_no_injector(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.index(path) with no injector_script routes to the
    `index_folder` MCP tool which POSTs to /index/.
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.index("/path/to/folder")
    assert isinstance(result, IndexResponse)
    assert result.job_id == "job-new"
    assert result.status == "queued"
    log = _read_log(wire_log_path)
    post_index = [e for e in log if e["method"] == "POST" and e["path"] == "/index/"]
    assert post_index, "index_folder tool must POST /index/"
    # The MCP server forwards the request body verbatim.
    import json as _json

    body = _json.loads(post_index[0]["body"])
    assert body["folder_path"] == "/path/to/folder"
    # injector_script must NOT be present when omitted.
    assert "injector_script" not in body


def test_stdio_index_routes_to_inject_documents_when_injector_set(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.index(path, injector_script='x.py') routes through
    the `inject_documents` MCP tool — same /index/ endpoint, but the
    body carries the injector_script field.
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.index("/path/to/folder", injector_script="enrich.py")
    assert isinstance(result, IndexResponse)
    log = _read_log(wire_log_path)
    post_index = [e for e in log if e["method"] == "POST" and e["path"] == "/index/"]
    assert post_index, "inject_documents tool must POST /index/"
    import json as _json

    body = _json.loads(post_index[0]["body"])
    assert body["folder_path"] == "/path/to/folder"
    assert body["injector_script"] == "enrich.py"


def test_stdio_delete_folder_routes_to_remove_folder_tool(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.delete_folder('/x') routes to the `remove_folder`
    MCP tool, which DELETEs /index/folders/.
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.delete_folder("/tmp/seed")
    assert isinstance(result, dict)
    assert result.get("chunks_deleted") == 42
    log = _read_log(wire_log_path)
    delete_entries = [
        e for e in log if e["method"] == "DELETE" and e["path"] == "/index/folders/"
    ]
    assert delete_entries, "remove_folder tool must DELETE /index/folders/"
    import json as _json

    body = _json.loads(delete_entries[0]["body"])
    assert body["folder_path"] == "/tmp/seed"


def test_stdio_cancel_job_routes_to_cancel_job_tool(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.cancel_job('job-123') routes to the `cancel_job`
    MCP tool, which DELETEs /index/jobs/<id>.
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.cancel_job("job-123")
    assert isinstance(result, dict)
    assert result.get("job_id") == "job-123"
    assert result.get("cancelled") is True
    log = _read_log(wire_log_path)
    paths = {(e["method"], e["path"]) for e in log}
    assert ("DELETE", "/index/jobs/job-123") in paths


def test_stdio_clear_cache_routes_to_clear_cache_tool(
    fake_stdio_server_script: Path, wire_log_path: Path
) -> None:
    """McpStdioBackend.clear_cache() routes to the `clear_cache` MCP tool
    (which requires confirm=True per Phase 54 destructive-op guard) →
    DELETE /index/cache/.
    """
    backend = _stdio_backend(fake_stdio_server_script, wire_log_path)
    result = backend.clear_cache()
    assert isinstance(result, dict)
    # ClearCacheOutput schema: count, size_bytes, size_mb.
    assert result.get("count") == 5
    assert result.get("size_bytes") == 1024
    log = _read_log(wire_log_path)
    paths = {(e["method"], e["path"]) for e in log}
    assert ("DELETE", "/index/cache/") in paths


def test_stdio_reset_raises_verbatim_not_implemented_error() -> None:
    """McpStdioBackend.reset() raises NotImplementedError with the
    verbatim CONTEXT.md §decisions wording.

    The wording is locked: any drift breaks the v3 design-doc contract
    that operators get a clear pointer to the alternate transport.
    """
    backend = McpStdioBackend(command="dummy")
    expected_message = (
        "--transport mcp does not support reset; use --transport uds "
        "or http (no reset_index MCP tool in v2; v3 Phase 57+ open "
        "decision per design doc §4 risks)"
    )
    with pytest.raises(NotImplementedError) as exc_info:
        backend.reset()
    assert str(exc_info.value) == expected_message


# ===========================================================================
# Task 3: HTTP backend mirrors — uses real subprocess + e2e_http marker.
# Mirrors all 11 stdio tests above.
# ===========================================================================

_FAKE_HTTP_METHODS_SERVER_SCRIPT = r"""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from agent_brain_mcp.http import run_http
from agent_brain_mcp.server import build_server

_LOG_PATH = Path(os.environ["TEST_WIRE_LOG_PATH"])
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


_RESPONSES = {
    ("GET", "/health/"): {
        "status": "healthy",
        "version": "10.2.0",
        "message": "ok",
        "mode": "project",
        "instance_id": "wire-http",
        "timestamp": "2026-06-06T00:00:00Z",
    },
    ("GET", "/health/status"): {
        "total_documents": 7,
        "total_chunks": 42,
        "indexing_in_progress": False,
        "current_job_id": None,
        "progress_percent": 0.0,
        "indexed_folders": ["/tmp/seed"],
        "last_indexed_at": "2026-06-06T00:00:00Z",
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
        "timestamp": "2026-06-06T00:00:00Z",
    },
    ("GET", "/query/count"): {"total_documents": 7, "total_chunks": 42},
    ("GET", "/index/folders/"): {
        "folders": [
            {
                "folder_path": "/tmp/seed",
                "chunk_count": 42,
                "last_indexed": "2026-06-06",
                "watch_mode": "off",
                "watch_debounce_seconds": 30,
            }
        ]
    },
    ("DELETE", "/index/folders/"): {
        "folder_path": "/tmp/seed",
        "chunks_deleted": 42,
        "message": "removed",
    },
    ("GET", "/index/jobs/"): {
        "jobs": [{"job_id": "job-a", "status": "completed"}]
    },
    ("GET", "/index/jobs/job-456"): {
        "job_id": "job-456",
        "status": "completed",
        "progress_percent": 100.0,
    },
    ("DELETE", "/index/jobs/job-456"): {
        "job_id": "job-456",
        "cancelled": True,
        "message": "ok",
    },
    ("GET", "/index/cache/"): {
        "hits": 10,
        "misses": 2,
        "hit_rate": 0.833,
        "mem_entries": 5,
        "entry_count": 5,
        "size_bytes": 1024,
    },
    ("DELETE", "/index/cache/"): {
        "count": 5,
        "size_bytes": 1024,
        "size_mb": 0.001,
    },
    ("POST", "/index/"): {
        "job_id": "job-new-http",
        "status": "queued",
        "message": "enqueued",
        "folder_path": "/path/to/folder",
    },
}


def _handler(request):
    body_raw = request.content.decode() if request.content else ""
    entry = {
        "method": request.method,
        "path": request.url.path,
        "query": str(request.url.query.decode()) if request.url.query else "",
        "body": body_raw,
    }
    with _LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")

    key = (request.method, request.url.path)
    body = _RESPONSES.get(key, {"detail": "not configured: " + str(key)})
    return httpx.Response(200, json=body)


async def main():
    host = os.environ["AGENT_BRAIN_MCP_E2E_HOST"]
    port = int(os.environ["AGENT_BRAIN_MCP_E2E_PORT"])
    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://wire-http",
    )
    server, manager = build_server(
        client, backend_transport="http", listen_transport="http"
    )
    try:
        await run_http(server, manager, host=host, port=port)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
"""


@pytest.fixture
def fake_http_methods_server_script(tmp_path: Path) -> Path:
    script = tmp_path / "fake_http_methods_server.py"
    script.write_text(_FAKE_HTTP_METHODS_SERVER_SCRIPT)
    return script


def _wait_for_http_ready(proc, port: int, log_path: Path) -> None:
    """Poll /healthz until the fake HTTP server is ready."""
    import time

    import httpx as _httpx

    url_health = f"http://127.0.0.1:{port}/healthz"
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if proc.poll() is not None:
            stderr = proc.stderr.read() if proc.stderr else b""
            raise RuntimeError(
                "HTTP server died before ready: " + stderr.decode(errors="replace")
            )
        try:
            r = _httpx.get(url_health, timeout=0.5)
            if r.status_code == 200:
                return
        except _httpx.HTTPError:
            pass
        time.sleep(0.1)
    proc.terminate()
    raise RuntimeError("HTTP server did not become ready")


def _stop_http(proc) -> None:
    import signal
    import subprocess as _subprocess

    if proc.poll() is None:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=3.0)
        except _subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def _spawn_http_server(script: Path, port: int, log_path: Path):
    import os
    import subprocess
    import sys as _sys

    project_root = Path(__file__).resolve().parent.parent
    env = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "AGENT_BRAIN_MCP_E2E_HOST": "127.0.0.1",
        "AGENT_BRAIN_MCP_E2E_PORT": str(port),
        "TEST_WIRE_LOG_PATH": str(log_path),
    }
    proc = subprocess.Popen(
        [_sys.executable, str(script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(project_root),
    )
    _wait_for_http_ready(proc, port, log_path)
    return proc


@pytest.mark.e2e_http
def test_http_health_returns_health_status_dataclass(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.health()
    finally:
        _stop_http(proc)
    assert isinstance(result, HealthStatus)
    assert result.status == "healthy"
    assert result.version == "10.2.0"


@pytest.mark.e2e_http
def test_http_status_returns_indexing_status_dataclass(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.status()
    finally:
        _stop_http(proc)
    assert isinstance(result, IndexingStatus)
    assert result.total_documents == 7
    assert result.indexed_folders == ["/tmp/seed"]


@pytest.mark.e2e_http
def test_http_list_folders_returns_folder_info_list(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.list_folders()
    finally:
        _stop_http(proc)
    assert isinstance(result, list)
    assert all(isinstance(f, FolderInfo) for f in result)
    assert len(result) == 1
    assert result[0].folder_path == "/tmp/seed"


@pytest.mark.e2e_http
def test_http_get_job_returns_dict(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.get_job("job-456")
    finally:
        _stop_http(proc)
    assert isinstance(result, dict)
    assert result["job_id"] == "job-456"


@pytest.mark.e2e_http
def test_http_list_jobs_returns_dict_list(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.list_jobs(limit=3)
    finally:
        _stop_http(proc)
    assert isinstance(result, list)
    assert len(result) == 1


@pytest.mark.e2e_http
def test_http_cache_status_returns_dict(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.cache_status()
    finally:
        _stop_http(proc)
    assert isinstance(result, dict)
    assert result.get("hits") == 10


@pytest.mark.e2e_http
def test_http_index_routes_to_index_folder_when_no_injector(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.index("/path/to/folder")
    finally:
        _stop_http(proc)
    assert isinstance(result, IndexResponse)
    assert result.job_id == "job-new-http"


@pytest.mark.e2e_http
def test_http_index_routes_to_inject_documents_when_injector_set(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.index("/path/to/folder", injector_script="enrich.py")
    finally:
        _stop_http(proc)
    assert isinstance(result, IndexResponse)
    # Indirect proof: log must carry injector_script in the POST body.
    import json as _json

    log = _read_log(wire_log_path)
    post_index = [e for e in log if e["method"] == "POST" and e["path"] == "/index/"]
    assert post_index, "inject_documents tool must POST /index/"
    body = _json.loads(post_index[0]["body"])
    assert body["injector_script"] == "enrich.py"


@pytest.mark.e2e_http
def test_http_delete_folder_routes_to_remove_folder_tool(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.delete_folder("/tmp/seed")
    finally:
        _stop_http(proc)
    assert isinstance(result, dict)
    assert result.get("chunks_deleted") == 42


@pytest.mark.e2e_http
def test_http_cancel_job_routes_to_cancel_job_tool(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.cancel_job("job-456")
    finally:
        _stop_http(proc)
    assert isinstance(result, dict)
    assert result.get("cancelled") is True


@pytest.mark.e2e_http
def test_http_clear_cache_routes_to_clear_cache_tool(
    fake_http_methods_server_script: Path,
    wire_log_path: Path,
    free_loopback_port: int,
) -> None:
    proc = _spawn_http_server(
        fake_http_methods_server_script, free_loopback_port, wire_log_path
    )
    try:
        backend = McpHttpBackend(url=f"http://127.0.0.1:{free_loopback_port}/mcp")
        result = backend.clear_cache()
    finally:
        _stop_http(proc)
    assert isinstance(result, dict)
    assert result.get("count") == 5


def test_http_reset_raises_verbatim_not_implemented_error() -> None:
    """McpHttpBackend.reset() raises the SAME verbatim NotImplementedError
    as McpStdioBackend.reset() — duplicate string literal, by design.
    """
    backend = McpHttpBackend(url="http://127.0.0.1:9999/mcp")
    expected_message = (
        "--transport mcp does not support reset; use --transport uds "
        "or http (no reset_index MCP tool in v2; v3 Phase 57+ open "
        "decision per design doc §4 risks)"
    )
    with pytest.raises(NotImplementedError) as exc_info:
        backend.reset()
    assert str(exc_info.value) == expected_message
