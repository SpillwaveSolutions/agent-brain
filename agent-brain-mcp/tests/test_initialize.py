"""Phase 4 test: MCP server initialization + capability advertisement.

Maps to plan §6.1, §12.3 #8 — capabilities flags must match exactly
(``tools.listChanged: false``, ``resources.subscribe: false``, etc.).
"""

from __future__ import annotations

import httpx

from agent_brain_mcp import __version__
from agent_brain_mcp.server import SERVER_NAME, build_server


class TestServerConstruction:
    def test_build_server_returns_named_server(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        assert server.name == SERVER_NAME

    def test_build_server_records_version(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        assert server.version == __version__


class TestCapabilityAdvertisement:
    """Capabilities the SDK emits during initialize must match plan §6.1."""

    def test_capabilities_have_no_subscriptions(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        from mcp.server.lowlevel import NotificationOptions

        server = build_server(fake_httpx_client)
        caps = server.get_capabilities(
            notification_options=NotificationOptions(
                prompts_changed=False,
                resources_changed=False,
                tools_changed=False,
            ),
            experimental_capabilities={},
        )

        assert caps.tools is not None
        assert caps.tools.listChanged is False

        assert caps.resources is not None
        assert caps.resources.subscribe is False
        assert caps.resources.listChanged is False

        assert caps.prompts is not None
        assert caps.prompts.listChanged is False
