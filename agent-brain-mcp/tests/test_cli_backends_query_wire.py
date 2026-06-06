"""Phase 57 Plan 02 — wire-level tests for McpStdioBackend.query +
McpHttpBackend.query.

The two backend classes ship as skeletons in Plan 56-03 (their
``query()`` methods raise ``NotImplementedError("Wired in Phase 57+")``).
This plan replaces those bodies with real ``asyncio.run``-internal
sync-facade implementations that drive the MCP SDK's
``stdio_client`` / ``streamablehttp_client`` against the
``search_documents`` MCP tool.

These tests exercise the wire path against a fake MCP server subprocess
(stdio leg) and a real ``agent-brain-mcp --transport http`` subprocess
(http leg). The stdio leg runs in the fast pre-push gate; the http leg
is opt-in via the ``e2e_http`` marker per the existing
``test_transport_selection.py`` precedent.
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
    QueryResponse,
    QueryResult,
)

from agent_brain_mcp.client import McpHttpBackend, McpStdioBackend  # noqa: E402

# ---------------------------------------------------------------------------
# Stdio fake-server script — mirrors tests/test_e2e_stdio.py shape but
# captures the call_tool args into a file so the tests can assert on
# them after the subprocess exits.
# ---------------------------------------------------------------------------

_FAKE_STDIO_SERVER_SCRIPT = r"""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

from agent_brain_mcp.server import build_server, run_stdio

# Where to log the search_documents tool args for test assertions.
_LOG_PATH = Path(os.environ["TEST_QUERY_LOG_PATH"])
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_INVOCATION_COUNT_PATH = Path(os.environ["TEST_INVOCATION_COUNT_PATH"])
_INVOCATION_COUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
# Bump invocation count by appending a single byte; tests count file size.
with _INVOCATION_COUNT_PATH.open("ab") as _f:
    _f.write(b"x")


_QUERY_RESPONSE = {
    "query": "echo",
    "mode": "hybrid",
    "total_results": 2,
    "query_time_ms": 12.3,
    "results": [
        {
            "text": "first result with echo",
            "source": "/tmp/seed/a.md",
            "score": 0.95,
            "chunk_id": "chunk-a",
            "metadata": {"language": "md"},
        },
        {
            "text": "second result with echo",
            "source": "/tmp/seed/b.md",
            "score": 0.85,
            "chunk_id": "chunk-b",
            "metadata": {"language": "md"},
        },
    ],
}

_DEFAULT_RESPONSES = {
    ("GET", "/health/"): {
        "status": "healthy",
        "version": "10.2.0",
        "message": "ok",
        "mode": "project",
        "instance_id": "wire-test",
    },
    ("GET", "/health/status"): {
        "total_documents": 2,
        "total_chunks": 2,
        "indexing_in_progress": False,
        "current_job_id": None,
        "progress_percent": 0.0,
        "indexed_folders": [],
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
    ("GET", "/query/count"): {"total_documents": 2, "total_chunks": 2},
    ("GET", "/index/folders/"): {
        "folders": [
            {
                "folder_path": "/tmp/seed",
                "chunk_count": 2,
                "last_indexed": "2026-06-06",
                "watch_mode": "off",
                "watch_debounce_seconds": 30,
            }
        ]
    },
}


def _handler(request):
    if request.method == "POST" and request.url.path == "/query/":
        # The search_documents MCP tool POSTs the query body verbatim.
        # Log it for the test to inspect.
        body = json.loads(request.content.decode())
        with _LOG_PATH.open("a") as f:
            f.write(json.dumps(body) + "\n")
        return httpx.Response(200, json=_QUERY_RESPONSE)
    key = (request.method, request.url.path)
    body = _DEFAULT_RESPONSES.get(key, {"detail": f"not configured: {key}"})
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
    script = tmp_path / "fake_stdio_query_server.py"
    script.write_text(_FAKE_STDIO_SERVER_SCRIPT)
    return script


@pytest.fixture
def query_log_path(tmp_path: Path) -> Path:
    return tmp_path / "query_log.jsonl"


@pytest.fixture
def invocation_count_path(tmp_path: Path) -> Path:
    return tmp_path / "invocations.bin"


def _stdio_backend(
    fake_stdio_server_script: Path,
    query_log_path: Path,
    invocation_count_path: Path,
) -> McpStdioBackend:
    """Build a McpStdioBackend that launches the fake server.

    The McpStdioBackend tacks ``--transport stdio`` onto whatever args
    it was given, so to make it run our fake script we pass the script
    path as the first arg (the subprocess will be ``python <script>
    --transport stdio`` — the script ignores the trailing arg).
    """
    project_root = Path(__file__).resolve().parent.parent
    return McpStdioBackend(
        command=[sys.executable, str(fake_stdio_server_script)],
        cwd=str(project_root),
        env={
            "PYTHONPATH": str(project_root),
            "TEST_QUERY_LOG_PATH": str(query_log_path),
            "TEST_INVOCATION_COUNT_PATH": str(invocation_count_path),
        },
    )


# ---------------------------------------------------------------------------
# Stdio backend tests (fast path — runs in task before-push)
# ---------------------------------------------------------------------------


def test_stdio_query_returns_populated_query_response(
    fake_stdio_server_script: Path,
    query_log_path: Path,
    invocation_count_path: Path,
) -> None:
    """McpStdioBackend.query('test') returns a real QueryResponse — NOT
    NotImplementedError."""
    backend = _stdio_backend(
        fake_stdio_server_script, query_log_path, invocation_count_path
    )
    response = backend.query("test")
    assert isinstance(response, QueryResponse)
    assert response.total_results == 2
    assert len(response.results) == 2
    assert isinstance(response.results[0], QueryResult)
    assert response.results[0].chunk_id == "chunk-a"


def test_stdio_query_default_args_propagate_to_search_documents(
    fake_stdio_server_script: Path,
    query_log_path: Path,
    invocation_count_path: Path,
) -> None:
    """Default query args land on the wire as the expected dict.

    Defaults from BackendClient Protocol: top_k=5, similarity_threshold=0.7,
    mode='hybrid', alpha=0.5, explain=False.
    """
    backend = _stdio_backend(
        fake_stdio_server_script, query_log_path, invocation_count_path
    )
    backend.query("test")

    # The fake server logs the /query/ POST body — read it.
    logged = query_log_path.read_text().strip().splitlines()
    assert len(logged) == 1, f"expected one POST, got {len(logged)}: {logged!r}"
    import json as _json

    payload = _json.loads(logged[0])
    assert payload["query"] == "test"
    assert payload["top_k"] == 5
    assert payload["similarity_threshold"] == 0.7
    assert payload["mode"] == "hybrid"
    assert payload["alpha"] == 0.5
    assert payload.get("explain", False) is False


def test_stdio_query_non_default_args_propagate(
    fake_stdio_server_script: Path,
    query_log_path: Path,
    invocation_count_path: Path,
) -> None:
    """Non-default query args propagate verbatim through the MCP tool call."""
    backend = _stdio_backend(
        fake_stdio_server_script, query_log_path, invocation_count_path
    )
    backend.query(
        "test",
        top_k=3,
        mode="semantic",
        source_types=["python"],
        explain=True,
    )

    logged = query_log_path.read_text().strip().splitlines()
    assert len(logged) == 1
    import json as _json

    payload = _json.loads(logged[0])
    assert payload["query"] == "test"
    assert payload["top_k"] == 3
    assert payload["mode"] == "semantic"
    assert payload.get("source_types") == ["python"]
    assert payload["explain"] is True


def test_stdio_query_populates_results_when_corpus_matches(
    fake_stdio_server_script: Path,
    query_log_path: Path,
    invocation_count_path: Path,
) -> None:
    """Result list is populated when the (fake) corpus has matching docs."""
    backend = _stdio_backend(
        fake_stdio_server_script, query_log_path, invocation_count_path
    )
    response = backend.query("echo")
    assert len(response.results) >= 1
    # The fake server returns deterministic results — first one has
    # source /tmp/seed/a.md.
    sources = {r.source for r in response.results}
    assert "/tmp/seed/a.md" in sources


def test_stdio_query_spawns_fresh_subprocess_per_call(
    fake_stdio_server_script: Path,
    query_log_path: Path,
    invocation_count_path: Path,
) -> None:
    """Pattern A (asyncio.run per call) means each query call spawns a
    fresh subprocess (CONTEXT decision; Phase 60 hygiene refinement
    target).
    """
    backend = _stdio_backend(
        fake_stdio_server_script, query_log_path, invocation_count_path
    )
    backend.query("test")
    backend.query("test")
    backend.query("test")

    # The fake server's first action is to append one byte to the
    # invocation count file. Three calls -> file size 3.
    assert invocation_count_path.stat().st_size == 3


# ---------------------------------------------------------------------------
# HTTP backend tests (opt-in via -m e2e_http — needs subprocess fixture)
# ---------------------------------------------------------------------------

# Custom HTTP fake-server script that DOES register POST /query/ — the
# conftest.py's _FAKE_HTTP_SERVER_SCRIPT is GET-only by design (it's
# wired for the v1 surface smoke tests). For these wire tests we need
# the query path to actually answer with a populated response.
_FAKE_HTTP_QUERY_SERVER_SCRIPT = r"""
import asyncio
import os
import sys

import httpx

from agent_brain_mcp.http import run_http
from agent_brain_mcp.server import build_server

_QUERY_RESPONSE = {
    "query": "echo",
    "mode": "hybrid",
    "total_results": 1,
    "query_time_ms": 12.3,
    "results": [
        {
            "text": "hit",
            "source": "/tmp/seed/a.md",
            "score": 0.95,
            "chunk_id": "chunk-a",
            "metadata": {"language": "md"},
        },
    ],
}

_RESPONSES = {
    ("GET", "/health/"): {
        "status": "healthy", "version": "10.2.0",
        "message": "ok", "mode": "project", "instance_id": "wire-http",
    },
    ("GET", "/health/status"): {
        "total_documents": 1, "total_chunks": 1,
        "indexing_in_progress": False, "current_job_id": None,
        "progress_percent": 0.0, "indexed_folders": [],
    },
    ("GET", "/health/config"): {
        "storage_backend": "chroma",
        "stores": {"vector": True, "bm25": True, "graph": False},
        "reranker_enabled": False,
        "embedding_model": "text-embedding-3-large",
        "rerank_model": None, "graph_extractor": None,
        "watcher_running": False,
    },
    ("GET", "/health/providers"): {
        "config_source": None, "strict_mode": False,
        "validation_errors": [], "providers": [],
        "timestamp": "2026-06-06T00:00:00Z",
    },
    ("GET", "/query/count"): {"total_documents": 1, "total_chunks": 1},
    ("POST", "/query/"): _QUERY_RESPONSE,
    ("GET", "/index/folders/"): {
        "folders": [{"folder_path": "/tmp/seed", "chunk_count": 1,
                     "last_indexed": "2026-06-06", "watch_mode": "off",
                     "watch_debounce_seconds": 30}],
    },
}


def _handler(request):
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
def fake_http_query_server_script(tmp_path: Path) -> Path:
    script = tmp_path / "fake_http_query_server.py"
    script.write_text(_FAKE_HTTP_QUERY_SERVER_SCRIPT)
    return script


@pytest.mark.e2e_http
def test_http_query_returns_populated_query_response(
    fake_http_query_server_script: Path,
    free_loopback_port: int,
) -> None:
    """McpHttpBackend.query('echo') returns a real QueryResponse — NOT
    NotImplementedError."""
    # Reuse the same subprocess pattern as conftest's mcp_http_subprocess,
    # but point it at our wire-test fake server.
    import os
    import signal
    import subprocess
    import sys
    import time

    project_root = Path(__file__).resolve().parent.parent
    env = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "AGENT_BRAIN_MCP_E2E_HOST": "127.0.0.1",
        "AGENT_BRAIN_MCP_E2E_PORT": str(free_loopback_port),
    }
    proc = subprocess.Popen(
        [sys.executable, str(fake_http_query_server_script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(project_root),
    )
    try:
        # Wait for /healthz
        import httpx as _httpx

        url_health = f"http://127.0.0.1:{free_loopback_port}/healthz"
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if proc.poll() is not None:
                stderr = proc.stderr.read() if proc.stderr else b""
                raise RuntimeError(
                    f"HTTP server died before ready: "
                    f"{stderr.decode(errors='replace')}"
                )
            try:
                r = _httpx.get(url_health, timeout=0.5)
                if r.status_code == 200:
                    break
            except _httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            proc.terminate()
            raise RuntimeError("HTTP server did not become ready")

        url = f"http://127.0.0.1:{free_loopback_port}/mcp"
        backend = McpHttpBackend(url=url)
        response = backend.query("echo")
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    assert isinstance(response, QueryResponse)
    assert response.total_results == 1
    assert len(response.results) == 1
    assert response.results[0].chunk_id == "chunk-a"


@pytest.mark.e2e_http
def test_http_query_routes_to_search_documents_tool(
    fake_http_query_server_script: Path,
    free_loopback_port: int,
) -> None:
    """The HTTP backend uses the same ``search_documents`` tool as stdio.

    Indirect proof — if the wrong tool name were used, the MCP server
    would return a tool-not-found error rather than a populated
    QueryResponse.
    """
    import os
    import signal
    import subprocess
    import sys
    import time

    project_root = Path(__file__).resolve().parent.parent
    env = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "AGENT_BRAIN_MCP_E2E_HOST": "127.0.0.1",
        "AGENT_BRAIN_MCP_E2E_PORT": str(free_loopback_port),
    }
    proc = subprocess.Popen(
        [sys.executable, str(fake_http_query_server_script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(project_root),
    )
    try:
        import httpx as _httpx

        url_health = f"http://127.0.0.1:{free_loopback_port}/healthz"
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if proc.poll() is not None:
                stderr = proc.stderr.read() if proc.stderr else b""
                raise RuntimeError(
                    f"HTTP server died before ready: "
                    f"{stderr.decode(errors='replace')}"
                )
            try:
                r = _httpx.get(url_health, timeout=0.5)
                if r.status_code == 200:
                    break
            except _httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            proc.terminate()
            raise RuntimeError("HTTP server did not become ready")

        url = f"http://127.0.0.1:{free_loopback_port}/mcp"
        backend = McpHttpBackend(url=url)
        response = backend.query("echo", top_k=3)
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    assert isinstance(response, QueryResponse)
    assert response.results, "search_documents must return at least one result"


@pytest.mark.e2e_http
def test_http_query_unreachable_url_raises_not_not_implemented() -> None:
    """A connection failure surfaces from the MCP SDK — NOT
    NotImplementedError. (Port 1 is conventionally reserved on Unix.)"""
    backend = McpHttpBackend(url="http://127.0.0.1:1/mcp")
    with pytest.raises(Exception) as exc_info:
        backend.query("test")
    # The exact error class depends on the SDK, but it MUST NOT be
    # NotImplementedError — that would mean we never replaced the
    # sentinel.
    assert not isinstance(exc_info.value, NotImplementedError)
