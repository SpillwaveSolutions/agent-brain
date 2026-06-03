"""Phase 53 Plan 03: SDK round-trip smoke over the HTTP transport.

This is the HTTP-01 end-to-end proof. Spawns the MCP server in a
subprocess with ``--transport http``, drives the official MCP Python
SDK's :func:`mcp.client.streamable_http.streamablehttp_client` against
it for a full initialize → tools/list → resources/list → prompts/list
→ tools/call cycle, and asserts the v1-equivalent surface (7 tools, 5
resources, 6 prompts) is identical to the stdio transport.

Also pins the Phase 53 D-01 + Plan 03 contract that ``serverInfo._meta``
carries BOTH transport axis labels (``agentBrainBackendTransport`` +
``agentBrainListenTransport``) — the public-contract counterpart of
Plan 01's in-process ``server._agent_brain_*_transport`` attributes.

Marked ``e2e_http`` and excluded from the default fast path. Run via
``task mcp:smoke:http``.
"""

from __future__ import annotations

from typing import Any

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Module-level marker so every test in this file is opt-in.
pytestmark = pytest.mark.e2e_http


# The seven v1 tools advertised by both stdio and HTTP transports.
# Phase 53 D-18 forbids drift toward Phase 52 (subscriptions) or
# Phase 54 (9 new tools) surface; pinning the exact set keeps this
# milestone-isolated.
_EXPECTED_V1_TOOL_NAMES = frozenset(
    {
        "search_documents",
        "query_count",
        "index_folder",
        "get_job",
        "list_jobs",
        "cancel_job",
        "server_health",
    }
)


@pytest.mark.asyncio
async def test_http_round_trip_lists_v1_surface(
    mcp_http_subprocess: Any, free_loopback_port: int
) -> None:
    """Full SDK round-trip over HTTP — initialize + 3 listings + tool call.

    Acceptance criteria (Plan 03):

    * 7 v1 tools advertised over HTTP, matching the stdio set.
    * 5 v1 resources (the static ``corpus://*`` quintet — Phase 51
      ``resources/templates/list`` is a separate response and is NOT
      counted here per the SDK semantics).
    * 6 v1 prompts.
    * ``serverInfo._meta`` (Plan 03 wiring) carries both transport
      axis labels.
    * ``call_tool("server_health", {})`` returns ``structuredContent``.
    """
    with mcp_http_subprocess():
        url = f"http://127.0.0.1:{free_loopback_port}/mcp"
        # The SDK's streamablehttp_client yields a tuple whose third
        # element is a session-id factory in mcp 1.12.x; using ``*_``
        # absorbs any future trailing elements so the test is robust
        # to additive SDK signature evolution (per Plan 03 risk #1).
        async with streamablehttp_client(url) as (read, write, *_):
            async with ClientSession(read, write) as session:
                init_result = await session.initialize()
                tools_result = await session.list_tools()
                resources_result = await session.list_resources()
                prompts_result = await session.list_prompts()
                health_result = await session.call_tool("server_health", {})

    # ----- v1 surface assertions (D-18 isolation guard) -----
    tool_names = {t.name for t in tools_result.tools}
    assert tool_names == _EXPECTED_V1_TOOL_NAMES, (
        f"HTTP tool surface drifted from v1 — got {sorted(tool_names)}; "
        f"expected {sorted(_EXPECTED_V1_TOOL_NAMES)}"
    )
    assert len(resources_result.resources) == 5, (
        f"resources/list returned {len(resources_result.resources)} entries; "
        f"v1 surface is 5 (corpus://config/status/health/providers/folders)"
    )
    assert len(prompts_result.prompts) == 6, (
        f"prompts/list returned {len(prompts_result.prompts)} entries; "
        f"v1 surface is 6"
    )

    # ----- serverInfo._meta carries both axis labels (Plan 03 wire wiring) -----
    server_info = init_result.serverInfo
    # ``Implementation`` doesn't declare ``_meta`` as a named field —
    # it lives in ``model_extra`` because the SDK type has
    # ``model_config = ConfigDict(extra="allow")``. Attribute access via
    # the SDK type works because Pydantic's ``__getattr__`` falls back
    # to ``model_extra`` for unset names.
    meta_raw: Any = getattr(server_info, "_meta", None)
    if meta_raw is None and server_info.model_extra is not None:
        meta_raw = server_info.model_extra.get("_meta")
    assert isinstance(meta_raw, dict), (
        f"serverInfo._meta missing or wrong type; "
        f"got {type(meta_raw).__name__} on {server_info!r}"
    )
    assert meta_raw.get("agentBrainListenTransport") == "http", (
        f"agentBrainListenTransport must be 'http' over the HTTP transport; "
        f"got {meta_raw!r}"
    )
    assert "agentBrainBackendTransport" in meta_raw, (
        f"agentBrainBackendTransport missing from serverInfo._meta; "
        f"got {meta_raw!r}"
    )

    # ----- tool call survived end-to-end -----
    assert (
        health_result.structuredContent is not None
    ), "call_tool('server_health') returned no structuredContent"
