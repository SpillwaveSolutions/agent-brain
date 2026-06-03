"""Phase 4 test: ``prompts/get`` expands each prompt (plan §12.3 #18)."""

from __future__ import annotations

import httpx
import mcp.types as types
import pytest
from mcp import McpError

from agent_brain_mcp.errors import INVALID_PARAMS
from agent_brain_mcp.server import build_server


async def _get_prompt(
    server, name: str, arguments: dict[str, str] | None
) -> types.GetPromptResult:
    handler = server.request_handlers[types.GetPromptRequest]
    req = types.GetPromptRequest(
        method="prompts/get",
        params=types.GetPromptRequestParams(name=name, arguments=arguments),
    )
    result = await handler(req)
    return result.root


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("find-callers", {"symbol": "QueryService"}),
        ("find-implementation", {"feature": "hybrid retrieval"}),
        ("explain-architecture", {"folder": "agent-brain-server", "depth": "2"}),
        ("compare-search-modes", {"query": "embedding cache"}),
        ("onboard-to-codebase", {"area": "indexing"}),
        ("onboard-to-codebase", {}),  # area is optional
        ("audit-indexed-folders", {}),
    ],
)
@pytest.mark.asyncio
async def test_prompt_expands_to_messages(
    name: str, arguments: dict[str, str], fake_httpx_client: httpx.Client
) -> None:
    server, _ = build_server(fake_httpx_client)
    result = await _get_prompt(server, name, arguments)
    assert result.description
    assert len(result.messages) >= 1
    msg = result.messages[0]
    assert msg.role == "user"
    assert isinstance(msg.content, types.TextContent)
    assert len(msg.content.text) > 50  # non-trivial prompt body


class TestPromptArgumentValidation:
    """Plan §12.3 #18 — missing required args rejected with clear error."""

    @pytest.mark.asyncio
    async def test_find_callers_missing_symbol_rejected(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server, _ = build_server(fake_httpx_client)
        with pytest.raises(McpError) as ei:
            await _get_prompt(server, "find-callers", {})
        assert ei.value.error.code == INVALID_PARAMS
        assert "symbol" in ei.value.error.message.lower()

    @pytest.mark.asyncio
    async def test_unknown_prompt_rejected(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server, _ = build_server(fake_httpx_client)
        with pytest.raises(McpError) as ei:
            await _get_prompt(server, "not-a-real-prompt", {})
        assert ei.value.error.code == INVALID_PARAMS
