"""FRAME-02 smoke test: LangChain via langchain-mcp-adapters against agent-brain-mcp.

Connects to agent-brain-mcp over stdio using MultiServerMCPClient, surfaces the
search_documents tool through the LangChain adapter layer, invokes it with the
canonical smoke query, and asserts a non-empty result against the seeded corpus.

Key design decisions:
- Keyless: no LLM/model API key required — test drives the MCP adapter directly,
  NOT an agent/chat-model loop.
- Stdio only: MultiServerMCPClient transport="stdio".
- <30s: session-scoped seeded_mcp_server guarantees server is already running.
- Orphan-free: teardown is handled by the seeded_mcp_server fixture (Phase 60
  contract); MultiServerMCPClient uses mcp SDK stdio_client internally.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure framework-matrix/ is on sys.path so conftest imports from _harness work
# when this test is run in isolation (e.g. after bootstrap_venv.sh).
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
async def test_langchain_search_returns_results(seeded_mcp_server: Path) -> None:
    """FRAME-02: LangChain connects via langchain-mcp-adapters, calls search_documents.

    Steps:
    1. Build stdio_server_params from the session-scoped seeded server.
    2. Open MultiServerMCPClient with stdio transport.
    3. Load tools via client.get_tools().
    4. Locate search_documents in the returned BaseTool list.
    5. Invoke it directly (no LLM loop — keyless).
    6. Assert non-empty result via assert_non_empty_search.

    Skips cleanly when seeded_mcp_server skips (OPENAI_API_KEY absent or binaries
    missing) — the fixture calls pytest.skip() before yielding.
    """
    from langchain_mcp_adapters.client import MultiServerMCPClient

    command, args, env = stdio_server_params(seeded_mcp_server)

    async with MultiServerMCPClient(
        {
            "agent-brain": {
                "command": command,
                "args": args,
                "transport": "stdio",
                "env": env,
            }
        }
    ) as client:
        tools = await client.get_tools()

        # Locate search_documents in the returned LangChain BaseTool list.
        search_tool = next(
            (t for t in tools if t.name == SMOKE_TOOL),
            None,
        )
        assert search_tool is not None, (
            f"search_documents tool not found in tool list. "
            f"Available: {[t.name for t in tools]}"
        )

        # Invoke directly — no LLM agent loop required (keyless).
        result = await search_tool.ainvoke(SMOKE_ARGS)

    # Normalize the LangChain ToolMessage/str result and assert >=1 hit.
    assert_non_empty_search(result)
