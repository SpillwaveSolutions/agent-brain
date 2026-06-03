"""Phase 53 Plan 02 — defensive pin on DNS-rebinding-protection wiring.

Phase 53 D-09 mandates that the MCP HTTP listener uses the SDK's
DNS-rebinding protection with the loopback-only ``allowed_hosts`` /
``allowed_origins`` lists. The :class:`FastMCP` class auto-enables this
in its ``__init__`` at ``mcp/server/fastmcp/server.py:177-183``, but
the bare :class:`mcp.server.streamable_http_manager.StreamableHTTPSessionManager`
does NOT — so the ``run_http`` wiring passes ``security_settings``
explicitly.

Why this file exists (risk register #3 in 53-PLAN.md): the SDK is on
a fast cadence; if a future bump silently changes the
:class:`TransportSecuritySettings` constructor shape, or stops
accepting ``security_settings`` on :class:`StreamableHTTPSessionManager`,
Plan 02's listener would either:

* fail to construct at startup (loud — caught at boot), or
* construct WITHOUT loopback protection (silent — bad).

This test catches the silent-degrade case by exercising the same
arguments :func:`agent_brain_mcp.http.build_asgi_app` uses to wire the
session manager and asserting it doesn't raise.

The plan's original spec for this test wanted to introspect the
manager's actual ``allowed_hosts`` / ``allowed_origins`` lists, but
the SDK doesn't expose those at the manager surface — they're held by
the inner :class:`StreamableHTTPServerTransport` which is created
per-session. We pin the *upstream contract* (constructor accepts our
args; the helper produces the expected payload) and defer per-session
introspection to Phase 55's SDK contract sweep.
"""

from __future__ import annotations

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from agent_brain_mcp.http import loopback_transport_security


class TestLoopbackTransportSecurityHelper:
    """The helper produces the SDK-default loopback-only payload."""

    def test_dns_rebinding_protection_enabled(self) -> None:
        """``enable_dns_rebinding_protection`` MUST default to True.

        If a future SDK version flips the default to ``False``, our
        helper must keep emitting ``True`` — anyone calling
        :func:`loopback_transport_security` expects the protection
        ON, not at the mercy of upstream defaults.
        """
        settings = loopback_transport_security()
        assert settings.enable_dns_rebinding_protection is True

    def test_allowed_hosts_match_fastmcp_default(self) -> None:
        """Mirror the FastMCP auto-enable defaults verbatim.

        Reference: ``mcp/server/fastmcp/server.py:177-183``. If FastMCP
        widens this list (e.g. adds ``[::1]:*`` variants) we should
        widen too — until then, this is the canonical loopback set.
        """
        settings = loopback_transport_security()
        assert settings.allowed_hosts == [
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
        ]

    def test_allowed_origins_match_fastmcp_default(self) -> None:
        """Mirror the FastMCP auto-enable defaults for Origin headers."""
        settings = loopback_transport_security()
        assert settings.allowed_origins == [
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
        ]


class TestSessionManagerAcceptsLoopbackSettings:
    """Defensive smoke against silent SDK regression on the wiring shape.

    Risk #3 in 53-PLAN.md: if the SDK renames
    ``security_settings``, drops the kwarg, or changes the
    :class:`TransportSecuritySettings` shape, this test catches it at
    construction time rather than letting the listener silently bind
    without protection.
    """

    def test_session_manager_constructs_with_loopback_security_settings(
        self,
    ) -> None:
        """The exact arguments :func:`build_asgi_app` uses must work.

        Uses ``app=None`` because the manager doesn't dereference the
        app object at construction time — only when handling a
        request. This isolates the test from the (slow) full
        :func:`agent_brain_mcp.server.build_server` path.
        """
        settings = loopback_transport_security()
        # If this raises, the SDK's StreamableHTTPSessionManager API
        # changed and run_http will fail at startup. Catch it here at
        # the unit-test layer so the diagnostic is clear.
        manager = StreamableHTTPSessionManager(
            app=None,  # type: ignore[arg-type]
            event_store=None,
            json_response=False,
            stateless=False,
            security_settings=settings,
        )
        assert manager is not None

    def test_transport_security_settings_constructor_accepts_our_shape(
        self,
    ) -> None:
        """Defensive pin on the :class:`TransportSecuritySettings` kwargs.

        Three kwargs are load-bearing for v2: ``enable_dns_rebinding_protection``,
        ``allowed_hosts``, ``allowed_origins``. If the SDK renames any of
        them, this test fails — the wiring helper must be updated to
        match, and Plan 02's :func:`loopback_transport_security` updated
        in lockstep.
        """
        settings = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=[
                "http://127.0.0.1:*",
                "http://localhost:*",
                "http://[::1]:*",
            ],
        )
        assert settings.enable_dns_rebinding_protection is True
        assert "127.0.0.1:*" in settings.allowed_hosts
        assert "http://127.0.0.1:*" in settings.allowed_origins
