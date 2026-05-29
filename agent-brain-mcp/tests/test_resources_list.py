"""Phase 4 test: ``resources/list`` advertises exactly 5 (plan §12.3 #17)."""

from __future__ import annotations

import httpx
import mcp.types as types
import pytest

from agent_brain_mcp.resources import RESOURCE_REGISTRY
from agent_brain_mcp.server import build_server

EXPECTED_URIS = {
    "corpus://config",
    "corpus://status",
    "corpus://health",
    "corpus://providers",
    "corpus://folders",
}


class TestResourcesList:
    def test_registry_has_five_resources(self) -> None:
        assert len(RESOURCE_REGISTRY) == 5
        assert set(RESOURCE_REGISTRY.keys()) == EXPECTED_URIS

    @pytest.mark.asyncio
    async def test_list_resources_returns_five(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListResourcesRequest]
        result = await handler(types.ListResourcesRequest(method="resources/list"))
        resources = result.root.resources
        assert len(resources) == 5
        # AnyUrl renders with a trailing slash for scheme-only URIs;
        # compare on the registered form.
        advertised = {str(r.uri).rstrip("/") for r in resources}
        expected = {u.rstrip("/") for u in EXPECTED_URIS}
        assert advertised == expected

    @pytest.mark.asyncio
    async def test_each_resource_has_json_mime(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListResourcesRequest]
        result = await handler(types.ListResourcesRequest(method="resources/list"))
        for r in result.root.resources:
            assert r.mimeType == "application/json"
