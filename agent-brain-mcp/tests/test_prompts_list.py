"""Phase 4 test: ``prompts/list`` advertises exactly 6 (plan §12.3 #18)."""

from __future__ import annotations

import httpx
import mcp.types as types
import pytest

from agent_brain_mcp.prompts import PROMPT_REGISTRY
from agent_brain_mcp.server import build_server

EXPECTED_PROMPTS = {
    "find-callers",
    "find-implementation",
    "explain-architecture",
    "compare-search-modes",
    "onboard-to-codebase",
    "audit-indexed-folders",
}


class TestPromptsList:
    def test_registry_has_six_prompts(self) -> None:
        assert len(PROMPT_REGISTRY) == 6
        assert set(PROMPT_REGISTRY.keys()) == EXPECTED_PROMPTS

    @pytest.mark.asyncio
    async def test_list_prompts_returns_six(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListPromptsRequest]
        result = await handler(types.ListPromptsRequest(method="prompts/list"))
        prompts = result.root.prompts
        assert len(prompts) == 6
        assert {p.name for p in prompts} == EXPECTED_PROMPTS

    @pytest.mark.asyncio
    async def test_each_prompt_advertises_arguments(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListPromptsRequest]
        result = await handler(types.ListPromptsRequest(method="prompts/list"))
        for p in result.root.prompts:
            # arguments may be empty (audit-indexed-folders) but must be a list.
            assert p.arguments is not None
            assert isinstance(p.arguments, list)
