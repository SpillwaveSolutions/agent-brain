"""FRAME-05: Autogen/AG2 McpWorkbench smoke test.

Connects to agent-brain-mcp over stdio using autogen_ext.tools.mcp.McpWorkbench
with StdioServerParams, lists tools to verify the MCP handshake, calls
search_documents with the canonical smoke query, and asserts a non-empty result
against the seeded corpus.

This test is keyless (no model provider required) — we exercise only the
McpWorkbench connection layer (the MCP stdio primitive), NOT any agent or
conversation loop.  The server is provided by the session-scoped
``seeded_mcp_server`` fixture from conftest.py.

Distribution note: McpWorkbench ships in ``autogen-ext[mcp]`` (Microsoft's
autogen-ext package), NOT in the AG2 fork or pyautogen.  The correct import is
``from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams``.

Run (from repo root):
    sh framework-matrix/bootstrap_venv.sh autogen
    framework-matrix/autogen/.venv/bin/pytest framework-matrix/autogen/ -m framework -v
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
async def test_autogen_search_returns_results(seeded_mcp_server: Path) -> None:
    """FRAME-05: Autogen McpWorkbench connects and returns non-empty results.

    Steps:
    1. Build stdio launch params from the session-scoped seeded server state dir.
    2. Create a StdioServerParams with those params.
    3. Create a McpWorkbench with those params and open via ``async with wb:``.
    4. Call ``wb.list_tools()`` — assert search_documents is in the list.
    5. Call ``wb.call_tool(SMOKE_TOOL, SMOKE_ARGS)``.
    6. Assert the result has >= 1 result via assert_non_empty_search.
    """
    from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams  # noqa: PLC0415

    command, args, env = stdio_server_params(seeded_mcp_server)

    params = StdioServerParams(command=command, args=args, env=env)

    async with McpWorkbench(server_params=params) as wb:
        # Verify the MCP handshake succeeded and search_documents is available.
        tools = await wb.list_tools()
        tool_names = [
            t.name
            if hasattr(t, "name")
            else (t.get("name") if isinstance(t, dict) else str(t))
            for t in tools
        ]
        assert SMOKE_TOOL in tool_names, (
            f"Expected tool '{SMOKE_TOOL}' in MCP tool list but got: {tool_names}"
        )

        # Call search_documents against the seeded corpus.
        result = await wb.call_tool(SMOKE_TOOL, SMOKE_ARGS)
        assert_non_empty_search(result)
