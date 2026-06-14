"""FRAME-01: OpenAI Agents SDK smoke tests — MCPServerStdio + MCPServerStreamableHttp.

Tests that the OpenAI Agents SDK MCP adapter layer connects to agent-brain-mcp,
discovers the search_documents tool, calls it against the seeded FRAMEWORK_CORPUS,
and asserts a non-empty result list.

Two transport legs:
  1. test_stdio_search_returns_results — MCPServerStdio (subprocess stdio)
  2. test_streamable_http_search_returns_results — MCPServerStreamableHttp (loopback HTTP)

Design constraints:
  - Keyless: no OpenAI/Anthropic API key required; the MCP adapter layer is exercised
    directly (connect → list_tools → call_tool). No Runner.run() / agent loop.
  - Offline: only live dependency is the spawned agent-brain-serve + agent-brain-mcp.
  - <30s per test: seeded_mcp_server is session-scoped so indexing happens once;
    per-test cost is one connect + one tool call.
  - Orphan-free: the session-scoped _orphan_guard in conftest.py asserts zero
    agent-brain subprocesses survive at teardown.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

# Ensure the framework-matrix root is on the path so _harness imports resolve
# when pytest is invoked with the openai-agents/.venv Python (which won't have
# framework-matrix/ in sys.path by default).
_FM_ROOT = Path(__file__).resolve().parent.parent
if str(_FM_ROOT) not in sys.path:
    sys.path.insert(0, str(_FM_ROOT))

from _harness import (
    SMOKE_ARGS,
    SMOKE_TOOL,
    assert_non_empty_search,
    stdio_server_params,
)

# Mark every test in this module as opt-in framework tests.
# The conftest.py pytest_collection_modifyitems hook also auto-adds this
# marker — belt-and-suspenders so the marks are visible in --collect-only.
pytestmark = pytest.mark.framework


# ---------------------------------------------------------------------------
# Test 1: MCPServerStdio — connect via subprocess stdio transport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stdio_search_returns_results(seeded_mcp_server: Path) -> None:
    """MCPServerStdio connects to agent-brain-mcp, calls search_documents.

    Verifies:
    - MCPServerStdio can connect to agent-brain-mcp via stdio transport.
    - list_tools() returns a tool named search_documents.
    - call_tool("search_documents", {"query": SMOKE_QUERY}) returns ≥1 result
      against the seeded FRAMEWORK_CORPUS.

    Args:
        seeded_mcp_server: Session-scoped fixture from conftest.py that yields
            the state_dir Path for a live agent-brain-serve with indexed corpus.
    """
    from agents.mcp import MCPServerStdio  # type: ignore[import]

    command, args, env = stdio_server_params(seeded_mcp_server)

    server = MCPServerStdio(
        name="agent-brain-mcp-stdio",
        params={
            "command": command,
            "args": args,
            "env": env,
        },
    )
    async with server:
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert SMOKE_TOOL in tool_names, (
            f"search_documents not found in tool list: {tool_names}"
        )

        result = await server.call_tool(SMOKE_TOOL, SMOKE_ARGS)
        assert_non_empty_search(result)


# ---------------------------------------------------------------------------
# Test 2: MCPServerStreamableHttp — connect via loopback HTTP transport
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streamable_http_search_returns_results(
    http_mcp_listener: Callable[[], str],
) -> None:
    """MCPServerStreamableHttp connects to agent-brain-mcp, calls search_documents.

    Verifies:
    - MCPServerStreamableHttp can connect to the real agent-brain-mcp --transport http
      binary started by the http_mcp_listener fixture.
    - list_tools() returns a tool named search_documents.
    - call_tool("search_documents", {"query": SMOKE_QUERY}) returns ≥1 result
      against the seeded FRAMEWORK_CORPUS.

    NOTE: http_mcp_listener is a FACTORY fixture from conftest.py. You MUST call
    it with parens — ``url = http_mcp_listener()`` — to start the real
    agent-brain-mcp --transport http binary and get back the URL. Injecting the
    bare fixture without calling it never starts the HTTP listener.

    Args:
        http_mcp_listener: Function-scoped factory fixture from conftest.py.
            Call with ``http_mcp_listener()`` to start the listener and receive
            ``http://127.0.0.1:<port>/mcp``.
    """
    from agents.mcp import MCPServerStreamableHttp  # type: ignore[import]

    url = http_mcp_listener()

    server = MCPServerStreamableHttp(
        name="agent-brain-mcp-http",
        params={"url": url},
    )
    async with server:
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]
        assert SMOKE_TOOL in tool_names, (
            f"search_documents not found in tool list: {tool_names}"
        )

        result = await server.call_tool(SMOKE_TOOL, SMOKE_ARGS)
        assert_non_empty_search(result)
