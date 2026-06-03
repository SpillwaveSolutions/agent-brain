"""MCP server initialization + capability advertisement.

Phase 4 (v1) pinned ``resources.subscribe: False`` in this test.
Phase 52 (Plan 02) flips the assertion to ``True`` — the v2 server
advertises subscriptions in the ``initialize`` capabilities so clients
that understand the v2 wire shape light up the subscription path.

The flip is implemented by a wrapper around ``Server.get_capabilities``
in :func:`agent_brain_mcp.server.build_server` (the MCP SDK 1.12.x
hardcodes ``subscribe=False`` at ``mcp/server/lowlevel/server.py:211``
with no opt-in knob, so a method-level patch is the surgical fix —
documented inline in build_server).
"""

from __future__ import annotations

import httpx

from agent_brain_mcp import __version__
from agent_brain_mcp.server import SERVER_NAME, build_server


class TestServerConstruction:
    def test_build_server_returns_named_server(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server, _ = build_server(fake_httpx_client)
        assert server.name == SERVER_NAME

    def test_build_server_records_version(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server, _ = build_server(fake_httpx_client)
        assert server.version == __version__

    def test_build_server_attaches_subscription_manager(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """Plan 04 tuple shape: ``build_server`` returns
        ``(server, manager)``; the same :class:`SubscriptionManager`
        instance is ALSO attached as ``server._subscription_manager``
        for backwards compatibility with Plan 02's pin (callers that
        haven't been migrated to the tuple shape yet still see the
        private attr). Plan 04+ consumers should prefer unpacking.
        """
        from agent_brain_mcp.subscriptions import SubscriptionManager

        result = build_server(fake_httpx_client)
        # Plan 04 contract — tuple unpacking.
        assert isinstance(result, tuple)
        assert len(result) == 2
        server, manager = result
        assert isinstance(manager, SubscriptionManager)
        assert manager.active_count() == 0

        # Plan 02 backwards-compat — private attr is the SAME object.
        private_attr = getattr(server, "_subscription_manager", None)
        assert private_attr is manager


class TestCapabilityAdvertisement:
    """Capabilities the SDK emits during ``initialize``.

    Phase 52 inverts the original v1 assertion: ``resources.subscribe``
    is now advertised as ``True``. Listchanged stays driven by
    :class:`NotificationOptions.resources_changed` (still False — the
    v2 milestone does not commit to a resourceListChanged notification
    pipeline; that's a future scope).
    """

    def test_capabilities_advertise_subscriptions(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        from mcp.server.lowlevel import NotificationOptions

        server, _ = build_server(fake_httpx_client)
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

        # Phase 52 wire shape — subscribe is True so v2 clients know
        # they can call resources/subscribe + listen for
        # notifications/resources/updated. listChanged stays driven by
        # the explicit NotificationOptions flag (still False).
        assert caps.resources is not None
        assert caps.resources.subscribe is True
        assert caps.resources.listChanged is False

        assert caps.prompts is not None
        assert caps.prompts.listChanged is False

    def test_capabilities_subscribe_independent_of_resources_changed_flag(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """``resources.subscribe`` flip is independent of
        ``resources_changed`` — flipping the latter to True (a future
        listChanged opt-in) must NOT silently flip subscribe back to
        False. Pins the wrapper's contract.
        """
        from mcp.server.lowlevel import NotificationOptions

        server, _ = build_server(fake_httpx_client)
        caps = server.get_capabilities(
            notification_options=NotificationOptions(
                prompts_changed=False,
                resources_changed=True,  # hypothetical future flip
                tools_changed=False,
            ),
            experimental_capabilities={},
        )
        assert caps.resources is not None
        assert caps.resources.subscribe is True
        assert caps.resources.listChanged is True
