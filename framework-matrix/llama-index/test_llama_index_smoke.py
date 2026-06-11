"""FRAME-03 smoke test: LlamaIndex via llama-index-tools-mcp against agent-brain-mcp.

Connects to agent-brain-mcp over stdio using BasicMCPClient + McpToolSpec,
surfaces the search_documents tool as a LlamaIndex FunctionTool, calls it with
the canonical smoke query, and asserts a non-empty result against the seeded
corpus.

Key design decisions:
- Keyless: no LLM/embedding API key required — test drives the MCP adapter layer
  only (BasicMCPClient + McpToolSpec), NOT an agent or LLM loop.
- Stdio only: BasicMCPClient(command, args=args, env=env) for stdio transport.
- <30s: session-scoped seeded_mcp_server guarantees server is already running.
- Orphan-free: teardown is owned by the seeded_mcp_server fixture (Phase 60
  contract); BasicMCPClient manages its own stdio subprocess lifetime.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure framework-matrix/ is on sys.path so _harness imports work when this
# test is run in isolation after bootstrap_venv.sh.
_FM_DIR = Path(__file__).resolve().parent.parent
if str(_FM_DIR) not in sys.path:
    sys.path.insert(0, str(_FM_DIR))

from _harness import (  # noqa: E402 — after sys.path fix
    SMOKE_ARGS,
    SMOKE_TOOL,
    assert_non_empty_search,
    stdio_server_params,
)

pytestmark = pytest.mark.framework


@pytest.mark.asyncio
async def test_llama_index_search_returns_results(seeded_mcp_server: Path) -> None:
    """FRAME-03: LlamaIndex connects via llama-index-tools-mcp, calls search_documents.

    Steps:
    1. Build stdio_server_params from the session-scoped seeded server.
    2. Construct BasicMCPClient for stdio (command, args, env).
    3. Wrap in McpToolSpec and call to_tool_list_async().
    4. Locate search_documents in the returned FunctionTool list (exact match
       first; substring fallback if the adapter prefixes tool names).
    5. Call tool.acall(**SMOKE_ARGS) — no LLM loop (keyless).
    6. Assert non-empty result via assert_non_empty_search.

    Skips cleanly when seeded_mcp_server skips (OPENAI_API_KEY absent or binaries
    missing) — the fixture calls pytest.skip() before yielding.
    """
    from llama_index.tools.mcp import BasicMCPClient, McpToolSpec

    command, args, env = stdio_server_params(seeded_mcp_server)

    mcp_client = BasicMCPClient(command, args=args, env=env)
    tool_spec = McpToolSpec(client=mcp_client)
    tools = await tool_spec.to_tool_list_async()

    # Locate search_documents — exact match preferred; substring fallback in
    # case the adapter prefixes/suffixes tool names.
    search_tool = next(
        (t for t in tools if t.metadata.name == SMOKE_TOOL),
        None,
    )
    if search_tool is None:
        # Substring fallback: accept the first tool whose name contains SMOKE_TOOL.
        search_tool = next(
            (t for t in tools if SMOKE_TOOL in t.metadata.name),
            None,
        )
    assert search_tool is not None, (
        f"search_documents tool not found in tool list. "
        f"Available: {[t.metadata.name for t in tools]}"
    )

    # Call the FunctionTool directly — no LLM agent loop required (keyless).
    result = await search_tool.acall(**SMOKE_ARGS)

    # Normalize the LlamaIndex ToolOutput / raw_output shape and assert >=1 hit.
    assert_non_empty_search(result)
