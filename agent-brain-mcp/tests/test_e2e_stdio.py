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
import httpx

from agent_brain_mcp.server import build_server, run_stdio

# Inline the responses the e2e tests need.
_RESPONSES = {
    ("GET", "/health/"): {
        "status": "healthy", "version": "10.0.7",
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
        "folders": [{"folder_path": "/tmp/x", "chunk_count": 1,
                     "last_indexed": "2026-05-28", "watch_mode": "off",
                     "watch_debounce_seconds": 30}],
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
    server = build_server(client)
    await run_stdio(server)


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
            assert len(tools.tools) == 7

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
