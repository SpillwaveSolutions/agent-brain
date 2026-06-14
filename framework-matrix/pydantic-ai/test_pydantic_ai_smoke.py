"""FRAME-04: Pydantic AI MCPServerStdio smoke test.

Connects to agent-brain-mcp over stdio using pydantic_ai.mcp.MCPServerStdio,
lists tools to verify the MCP handshake, calls search_documents with the
canonical smoke query, and asserts a non-empty result against the seeded corpus.

This test is keyless (no LLM/model provider required) — we exercise only the
MCPServerStdio connection layer, NOT any agent run loop.  The server is
provided by the session-scoped ``seeded_mcp_server`` fixture from conftest.py.

Run (from repo root):
    sh framework-matrix/bootstrap_venv.sh pydantic-ai
    framework-matrix/pydantic-ai/.venv/bin/pytest framework-matrix/pydantic-ai/ -m framework -v
"""

from __future__ import annotations

import sys
import os

import pytest

# ---------------------------------------------------------------------------
# Canonical smoke-test helpers from the shared harness.
# framework-matrix/ is the pytest rootdir (pytest.ini lives there), so
# _harness is importable without a package prefix when tests run through
# the per-framework .venv which has framework-matrix/ on sys.path via
# pytest's rootdir discovery.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _harness import (  # noqa: E402
    SMOKE_ARGS,
    SMOKE_QUERY,
    SMOKE_TOOL,
    assert_non_empty_search,
    stdio_server_params,
)

from pathlib import Path

# pytest.mark.framework is applied globally by conftest.py's
# pytest_collection_modifyitems, but also set here explicitly for clarity.
pytestmark = pytest.mark.framework


@pytest.mark.asyncio
async def test_pydantic_ai_search_returns_results(seeded_mcp_server: Path) -> None:
    """FRAME-04: Pydantic AI MCPServerStdio connects and returns non-empty results.

    Steps:
    1. Build stdio launch params from the session-scoped seeded server state dir.
    2. Create a MCPServerStdio instance with those params.
    3. Open a connection via ``async with server:``.
    4. Call ``server.list_tools()`` — assert search_documents is in the list.
    5. Call ``server.call_tool(SMOKE_TOOL, SMOKE_ARGS)``.
    6. Assert the result has >= 1 result via assert_non_empty_search.
    """
    from pydantic_ai.mcp import MCPServerStdio  # noqa: PLC0415

    command, args, env = stdio_server_params(seeded_mcp_server)

    server = MCPServerStdio(command, args=args, env=env)
    async with server:
        # Verify the MCP handshake succeeded and search_documents is available.
        tools = await server.list_tools()
        tool_names = [
            t.name if hasattr(t, "name") else (t.get("name") if isinstance(t, dict) else str(t))
            for t in tools
        ]
        assert SMOKE_TOOL in tool_names, (
            f"Expected tool '{SMOKE_TOOL}' in MCP tool list but got: {tool_names}"
        )

        # Call search_documents against the seeded corpus.
        result = await server.call_tool(SMOKE_TOOL, SMOKE_ARGS)
        assert_non_empty_search(result)
