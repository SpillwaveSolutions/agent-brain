"""Phase 4 / Phase 54 test: ``tools/list`` advertises the expected tool set.

Phase 54 staged landings:
* Plan 02 bumped 7 (v1) → 11 (v1 + 4 read-only).
* Plan 03 bumped 11 → 15 (added add_documents, inject_documents,
  remove_folder, clear_cache).
* Plan 04 bumps 15 → 16 (adds wait_for_job — the only progress-emitting
  tool in v2).

After Plan 04, the registry is at its final v2 count. This module now
asserts the EXACT count of 16 plus the single ``emits_progress=True``
entry (``wait_for_job``). Phase 55's contract-test suite owns the final
spec-conformance pin.
"""

from __future__ import annotations

import httpx
import pytest

from agent_brain_mcp.server import build_server
from agent_brain_mcp.tools import TOOL_REGISTRY

# v1 base set — every entry below MUST exist after Phase 54 lands.
V1_TOOLS = {
    "search_documents",
    "query_count",
    "index_folder",
    "get_job",
    "list_jobs",
    "cancel_job",
    "server_health",
}

# Phase 54 Plan 02 read-only additions.
PHASE_54_READ_ONLY_TOOLS = {
    "explain_result",
    "list_folders",
    "cache_status",
    "list_file_types",
}

# Phase 54 Plan 03 mutating additions.
PHASE_54_MUTATING_TOOLS = {
    "add_documents",
    "inject_documents",
    "remove_folder",
    "clear_cache",
}

# Phase 54 Plan 04 progress-emitting addition (final v2 entry).
PHASE_54_PROGRESS_TOOLS = {
    "wait_for_job",
}

# Final v2 set — 7 + 4 + 4 + 1 = 16. This is the exact-count contract
# after Phase 54 Plan 04 lands; Phase 55's parameterized contract test
# pins it again against the official MCP SDK schema.
EXPECTED_TOOLS = (
    V1_TOOLS
    | PHASE_54_READ_ONLY_TOOLS
    | PHASE_54_MUTATING_TOOLS
    | PHASE_54_PROGRESS_TOOLS
)


class TestToolsList:
    def test_registry_has_exactly_sixteen_tools(self) -> None:
        # Phase 54 Plan 04 → 16 tools (7 v1 + 4 read-only + 4 mutating +
        # 1 progress-emitting). This is the final v2 count.
        assert len(TOOL_REGISTRY) == 16
        # All 16 expected names registered.
        assert set(TOOL_REGISTRY.keys()) == EXPECTED_TOOLS

    def test_only_wait_for_job_emits_progress(self) -> None:
        """Pin the discrimination: 1 async progress-emitting tool, 15 sync."""
        emits = {name for name, spec in TOOL_REGISTRY.items() if spec.emits_progress}
        assert emits == {"wait_for_job"}

    @pytest.mark.asyncio
    async def test_list_tools_handler_returns_exactly_sixteen(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server, _ = build_server(fake_httpx_client)
        # The decorator stores the handler in server.request_handlers.
        import mcp.types as types

        handler = server.request_handlers[types.ListToolsRequest]
        req = types.ListToolsRequest(method="tools/list")
        result = await handler(req)
        tools = result.root.tools
        assert len(tools) == 16
        assert {t.name for t in tools} == EXPECTED_TOOLS

    @pytest.mark.asyncio
    async def test_each_tool_has_input_schema(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        import mcp.types as types

        server, _ = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListToolsRequest]
        result = await handler(types.ListToolsRequest(method="tools/list"))
        for tool in result.root.tools:
            assert isinstance(tool.inputSchema, dict)
            assert tool.inputSchema.get("type") == "object"

    @pytest.mark.asyncio
    async def test_each_tool_has_output_schema(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        import mcp.types as types

        server, _ = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListToolsRequest]
        result = await handler(types.ListToolsRequest(method="tools/list"))
        for tool in result.root.tools:
            assert tool.outputSchema is not None
            assert tool.outputSchema.get("type") == "object"

    @pytest.mark.asyncio
    async def test_cancel_job_has_destructive_hint(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        import mcp.types as types

        server, _ = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListToolsRequest]
        result = await handler(types.ListToolsRequest(method="tools/list"))
        cancel = next(t for t in result.root.tools if t.name == "cancel_job")
        assert cancel.annotations is not None
        assert cancel.annotations.destructiveHint is True

    @pytest.mark.asyncio
    async def test_search_documents_is_read_only(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        import mcp.types as types

        server, _ = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListToolsRequest]
        result = await handler(types.ListToolsRequest(method="tools/list"))
        search = next(t for t in result.root.tools if t.name == "search_documents")
        assert search.annotations is not None
        assert search.annotations.readOnlyHint is True
        assert search.annotations.openWorldHint is True
