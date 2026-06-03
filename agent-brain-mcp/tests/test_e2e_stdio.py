"""Phase 4 test: end-to-end via the official MCP Python SDK client.

Plan §12.3 #19 — verifies the entire stdio handshake works against an
external MCP client (not just our internal handler registrations).

These tests are marked ``e2e`` and are excluded from the default ``task
mcp:test`` run. Run with ``task mcp:e2e``.

Instead of starting agent-brain-serve, we run a tiny test server
subprocess that wires our ``build_server`` + a MockTransport httpx
client — proving the MCP wire protocol works end-to-end without
needing a live Agent Brain backend.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


_FAKE_SERVER_SCRIPT = """
import asyncio
import os
import httpx

from agent_brain_mcp.server import build_server, run_stdio

# Phase 51 Plan 04 — sandbox root is injected via env so the per-test
# tmp_path can be passed in; default keeps v1 tests working.
_SANDBOX_ROOT = os.environ.get("E2E_SANDBOX_ROOT", "/tmp/x")

# Inline the responses the e2e tests need.
_RESPONSES = {
    ("GET", "/health/"): {
        # Phase 51 Plan 04: bumped to 10.2.0 to match the new
        # MIN_BACKEND_VERSION floor. Even though this fake server
        # uses build_server() (not main_async()) and skips the
        # startup version check, the version surfaces in corpus://
        # config — keep it aligned with reality.
        "status": "healthy", "version": "10.2.0",
        "message": "ok", "mode": "project", "instance_id": "e2e",
    },
    ("GET", "/health/status"): {
        "total_documents": 42, "total_chunks": 420,
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
        "timestamp": "2026-05-28T00:00:00Z",
    },
    ("GET", "/query/count"): {"total_documents": 42, "total_chunks": 420},
    ("POST", "/query/"): {
        "query": "test", "mode": "hybrid",
        "total_results": 1, "query_time_ms": 12.3,
        "results": [{"text": "hit", "source": "/x", "score": 0.99,
                     "chunk_id": "c", "metadata": {}}],
    },
    ("GET", "/index/folders/"): {
        "folders": [{"folder_path": _SANDBOX_ROOT, "chunk_count": 1,
                     "last_indexed": "2026-05-28", "watch_mode": "off",
                     "watch_debounce_seconds": 30}],
    },
    # Phase 51 Plan 04 e2e fixtures — chunk://, graph-entity://, job://
    # are all backed by the FastAPI server through ApiClient.
    ("GET", "/query/chunk/stub-chunk-id"): {
        "chunk_id": "stub-chunk-id",
        "parent_doc_id": "doc-stub",
        "source": _SANDBOX_ROOT + "/stub.py",
        "content": "def stub():\\n    pass\\n",
        "summary": "Stub function.",
        "folder_id": _SANDBOX_ROOT,
        "token_count": 4,
        "language": "python",
    },
    ("GET", "/graph/entity/Function/stub-name"): {
        "entity": {
            "type": "Function",
            "id": "stub-name",
            "properties": {"module": "stub"},
        },
        "neighbors": {"incoming": [], "outgoing": []},
    },
    ("GET", "/index/jobs/stub-job-id"): {
        "job_id": "stub-job-id",
        "status": "completed",
        "progress_percent": 100.0,
        "message": "Done.",
    },
}


def _handler(request: httpx.Request) -> httpx.Response:
    key = (request.method, request.url.path)
    body = _RESPONSES.get(key, {"detail": f"not configured: {key}"})
    return httpx.Response(200, json=body)


async def main():
    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://e2e",
    )
    server, manager = build_server(client)
    await run_stdio(server, manager)


if __name__ == "__main__":
    asyncio.run(main())
"""


@pytest.fixture
def fake_server_module(tmp_path: Path) -> Path:
    """Write a self-contained test server we can launch as a subprocess."""
    script = tmp_path / "fake_mcp_server.py"
    script.write_text(_FAKE_SERVER_SCRIPT)
    return script


@pytest.mark.asyncio
async def test_initialize_lists_tools_resources_prompts(
    fake_server_module: Path,
) -> None:
    """Full handshake: initialize → tools/list → resources/list → prompts/list."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    project_root = Path(__file__).resolve().parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_server_module)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "agent-brain"

            tools = await session.list_tools()
            # Phase 54 Plan 04 brings the registry to its final v2 count
            # of 16 (7 v1 + 9 Phase 54 tools). This e2e asserts the live
            # ``tools/list`` wire shape matches that count — the
            # tools/list registry pin lives in ``tests/test_tools_list.py``.
            assert len(tools.tools) == 16

            resources = await session.list_resources()
            assert len(resources.resources) == 5

            prompts = await session.list_prompts()
            assert len(prompts.prompts) == 6


@pytest.mark.asyncio
async def test_e2e_tool_call_returns_structured(
    fake_server_module: Path,
) -> None:
    """Call query_count and verify both content and structuredContent surface."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    project_root = Path(__file__).resolve().parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_server_module)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("query_count", {})
            assert len(result.content) >= 1
            assert result.structuredContent is not None
            assert result.structuredContent["total_documents"] == 42


@pytest.mark.asyncio
async def test_e2e_resource_read(fake_server_module: Path) -> None:
    """Read corpus://folders end-to-end."""
    import json

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from pydantic import AnyUrl

    project_root = Path(__file__).resolve().parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_server_module)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource(AnyUrl("corpus://folders"))
            assert len(result.contents) == 1
            body = json.loads(result.contents[0].text)  # type: ignore[union-attr]
            assert "folders" in body


@pytest.mark.asyncio
async def test_e2e_prompt_get(fake_server_module: Path) -> None:
    """Get the onboard-to-codebase prompt end-to-end."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    project_root = Path(__file__).resolve().parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_server_module)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.get_prompt("onboard-to-codebase", {})
            assert len(result.messages) >= 1
            assert result.description


@pytest.mark.asyncio
async def test_e2e_templates_list_and_read_all_schemes(
    fake_server_module: Path, tmp_path: Path
) -> None:
    """Phase 51 Plan 04 — end-to-end SDK exercise of URI-05 + all 4 schemes.

    Drives the real ``agent-brain-mcp`` MCP wire protocol through the
    official MCP Python SDK against our fake-backend subprocess:

    1. ``initialize`` (handshake).
    2. ``resources/templates/list`` — assert all four expected templates
       are advertised with the exact ``uriTemplate`` strings from Phase
       51 CONTEXT decision B.
    3. ``resources/read chunk://stub-chunk-id`` — assert success
       (fake backend serves a stub ChunkRecord).
    4. ``resources/read graph-entity://Function/stub-name`` — assert
       success (fake backend serves a stub GraphEntityRecord).
    5. ``resources/read job://stub-job-id`` — assert success (fake
       backend serves a stub JobDetailResponse).
    6. ``resources/read file://<tmp_path>/stub.txt`` — assert success
       (real filesystem read inside the sandbox root injected via
       ``E2E_SANDBOX_ROOT``).

    This is the closing-out test for URI-05: it proves the templates
    discovery flow + per-scheme reads work over the real MCP wire
    protocol, not just through internal handler invocation.
    """
    import json

    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from pydantic import AnyUrl

    # Create a real sandbox root with a file the file:// read can target.
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    stub_file = sandbox / "stub.txt"
    stub_file.write_text("hello from e2e\n")

    project_root = Path(__file__).resolve().parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_server_module)],
        cwd=str(project_root),
        env={
            "PYTHONPATH": str(project_root),
            "E2E_SANDBOX_ROOT": str(sandbox),
        },
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # (2) resources/templates/list returns 4 templates with the
            # exact strings from CONTEXT decision B.
            templates_result = await session.list_resource_templates()
            advertised = {t.uriTemplate for t in templates_result.resourceTemplates}
            assert advertised == {
                "chunk://{chunk_id}",
                "graph-entity://{type}/{id}",
                "job://{job_id}",
                "file://{+path}",
            }
            # mimeType: 3 JSON schemes + 1 None for file.
            by_template = {
                t.uriTemplate: t.mimeType for t in templates_result.resourceTemplates
            }
            assert by_template["chunk://{chunk_id}"] == "application/json"
            assert by_template["graph-entity://{type}/{id}"] == "application/json"
            assert by_template["job://{job_id}"] == "application/json"
            assert by_template["file://{+path}"] is None

            # (3) chunk:// read — JSON body round-trips through the
            # parameterized dispatcher.
            chunk_result = await session.read_resource(AnyUrl("chunk://stub-chunk-id"))
            assert len(chunk_result.contents) == 1
            chunk_body = json.loads(chunk_result.contents[0].text)  # type: ignore[union-attr]
            assert chunk_body["chunk_id"] == "stub-chunk-id"
            assert chunk_body["language"] == "python"

            # (4) graph-entity:// read — entity + 1-hop neighbors.
            graph_result = await session.read_resource(
                AnyUrl("graph-entity://Function/stub-name")
            )
            assert len(graph_result.contents) == 1
            graph_body = json.loads(graph_result.contents[0].text)  # type: ignore[union-attr]
            assert graph_body["entity"]["type"] == "Function"
            assert graph_body["entity"]["id"] == "stub-name"
            assert graph_body["neighbors"]["incoming"] == []

            # (5) job:// read — JobDetailResponse passthrough.
            job_result = await session.read_resource(AnyUrl("job://stub-job-id"))
            assert len(job_result.contents) == 1
            job_body = json.loads(job_result.contents[0].text)  # type: ignore[union-attr]
            assert job_body["job_id"] == "stub-job-id"
            assert job_body["status"] == "completed"

            # (6) file:// read — real filesystem read inside the sandbox
            # root reported by the stubbed /index/folders/ endpoint.
            file_uri = f"file://{stub_file}"
            file_result = await session.read_resource(AnyUrl(file_uri))
            assert len(file_result.contents) == 1
            # text/plain → ReadResourceContents.text carries the body.
            assert file_result.contents[0].text == "hello from e2e\n"  # type: ignore[union-attr]
