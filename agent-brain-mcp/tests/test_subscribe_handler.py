"""Unit + integration tests for Phase 52 Plan 02 subscribe/unsubscribe handlers.

Drives the ``@server.subscribe_resource()`` / ``@server.unsubscribe_resource()``
handlers through the MCP SDK's in-memory transport
(``mcp.shared.memory.create_connected_server_and_client_session``).

Covered behaviors:

* URI normalization (trailing-slash strip mirrors ``read_resource``).
* ``unknown_uri`` rejection — URI scheme is not in ``RESOURCE_REGISTRY``
  AND not in ``PARAMETERIZED_SCHEMES``.
* ``not_subscribable`` rejection — URI is a known resource but the
  scheme has no entry in ``SUBSCRIPTION_POLICIES`` (e.g.,
  ``corpus://config``, ``chunk://X``).
* ``duplicate_subscribe`` rejection — same ``(session, uri)`` pair
  cannot subscribe twice in a row.
* Positive path — subscribe → ack → unsubscribe → ack via a
  ``monkeypatch.setitem`` stub policy for ``corpus://status``.
* Idempotent unsubscribe — unsubscribing a URI we never subscribed
  to acks cleanly (MCP spec semantic, Plan 02 acceptance).

The stub policy uses ``interval_s=3600`` so no poll fires during the
ack-only test scenarios. The test for an "actual change" payload is
deferred to Phase 52 Plan 03 (per-URI policies) and Plan 04 (full e2e
with cleanup hook); Plan 02 stops at the wire-shape ack.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_connected_server_and_client_session
from pydantic import AnyUrl

from agent_brain_mcp.errors import INVALID_PARAMS
from agent_brain_mcp.server import _is_known_uri, _normalize_uri, build_server
from agent_brain_mcp.subscriptions import (
    SUBSCRIPTION_POLICIES,
    SubscriptionPolicy,
)

# --- Pure-function unit tests (no SDK harness) -----------------------------


class TestUriNormalization:
    """``_normalize_uri`` must mirror the trailing-slash rule in
    ``read_resource`` so the subscribe handler keys against the same
    canonical URI string as the resource registry."""

    def test_strips_single_trailing_slash(self) -> None:
        assert _normalize_uri("job://abc/") == "job://abc"
        assert _normalize_uri("corpus://status/") == "corpus://status"

    def test_preserves_uri_with_no_trailing_slash(self) -> None:
        assert _normalize_uri("job://abc") == "job://abc"
        assert _normalize_uri("corpus://status") == "corpus://status"

    def test_preserves_empty_netloc_double_slash(self) -> None:
        # ``job://`` (no id, empty netloc) is preserved verbatim so the
        # downstream registry lookup surfaces ``unknown_uri`` properly
        # rather than collapsing to ``job:``.
        assert _normalize_uri("job://") == "job://"

    def test_accepts_pydantic_anyurl(self) -> None:
        # The SDK delivers ``AnyUrl``; we accept both ``str`` and
        # ``AnyUrl`` so unit tests can be agnostic.
        assert _normalize_uri(AnyUrl("corpus://status")) == "corpus://status"


class TestIsKnownUri:
    """``_is_known_uri`` recognizes (a) static ``corpus://*`` exact
    matches and (b) any URI whose scheme is in
    :data:`PARAMETERIZED_SCHEMES`."""

    def test_recognizes_static_corpus_uri(self) -> None:
        assert _is_known_uri("corpus://status") is True
        assert _is_known_uri("corpus://folders") is True
        assert _is_known_uri("corpus://config") is True  # in registry, not subscribable

    def test_recognizes_parameterized_scheme(self) -> None:
        # Note: per-id validity is NOT checked here — that's the job of
        # the polling fetcher (Plan 03). The subscribe handler only
        # gates on "is the scheme recognized".
        assert _is_known_uri("job://abc") is True
        assert _is_known_uri("chunk://xyz") is True
        assert _is_known_uri("graph-entity://Function/foo") is True
        assert _is_known_uri("file:///tmp/x.txt") is True

    def test_rejects_unknown_scheme(self) -> None:
        assert _is_known_uri("bogus://x") is False
        assert _is_known_uri("http://example.com") is False

    def test_rejects_uri_without_scheme(self) -> None:
        assert _is_known_uri("notauri") is False
        assert _is_known_uri("") is False


# --- Integration tests via the in-memory MCP transport ---------------------


class _StubPolicy:
    """In-memory stub satisfying :class:`SubscriptionPolicy` Protocol.

    Plan 03 ships real dataclasses for the three v2 subscribable URIs;
    Plan 02 tests use this lightweight stub so the wire handler's
    dispatch logic can be exercised without Plan 03's HTTP cadences.

    interval_s=3600 (1h) — guarantees no poll fires during the
    ack-only tests. The fetcher returns a fixed dict if invoked, so
    the test still passes if asyncio happens to schedule one tick.
    """

    uri_pattern: str
    interval_s: float
    drop_keys: frozenset[str] | None
    build_fetcher: Callable[[Any, str], Callable[[], Awaitable[dict[str, Any]]]]

    def __init__(self, uri_pattern: str, interval_s: float = 3600.0) -> None:
        self.uri_pattern = uri_pattern
        self.interval_s = interval_s
        self.drop_keys = None  # use DEFAULT_DROP_KEYS

        async def _fetch() -> dict[str, Any]:
            return {"stub": True, "uri_pattern": uri_pattern}

        def _factory(_api: Any, _uri: str) -> Callable[[], Awaitable[dict[str, Any]]]:
            return _fetch

        self.build_fetcher = _factory


class TestSubscribeHandlerDispatch:
    """End-to-end (in-process) dispatch tests via the MCP SDK harness.

    Each test inlines the ``async with create_connected_server_and_client_session``
    block. Pulling it into a fixture causes anyio's task-group lifecycle
    to span tasks (the fixture's enter/exit run in different anyio tasks
    than the test body), which trips a ``RuntimeError`` in anyio's
    cancel-scope guard. Inlining keeps the entire harness lifecycle on
    one task — cleaner than fiddling with ``pytest_asyncio.fixture``
    scopes.
    """

    async def test_subscribe_unknown_uri_rejected(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as client:
            with pytest.raises(McpError) as exc:
                await client.subscribe_resource(AnyUrl("bogus://x"))
        assert exc.value.error.code == INVALID_PARAMS
        assert isinstance(exc.value.error.data, dict)
        assert exc.value.error.data["reason"] == "unknown_uri"
        assert exc.value.error.data["uri"] == "bogus://x"

    async def test_subscribe_not_subscribable_static_uri_rejected(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """``corpus://config`` is in the registry but not subscribable —
        no policy is registered for it. Plan 02's registry is empty
        until Plan 03 lands; this test pins the *not_subscribable*
        branch independent of Plan 03's specific policy set."""
        server = build_server(fake_httpx_client)
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as client:
            with pytest.raises(McpError) as exc:
                await client.subscribe_resource(AnyUrl("corpus://config"))
        assert exc.value.error.code == INVALID_PARAMS
        assert isinstance(exc.value.error.data, dict)
        assert exc.value.error.data["reason"] == "not_subscribable"
        assert exc.value.error.data["uri"] == "corpus://config"

    async def test_subscribe_not_subscribable_parameterized_uri_rejected(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """``chunk://`` is a recognized parameterized scheme but never
        subscribable per CONTEXT decision G (content-addressed, no
        time-varying signal). Even after Plan 03 lands, ``chunk://``
        will not have a policy."""
        server = build_server(fake_httpx_client)
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as client:
            with pytest.raises(McpError) as exc:
                await client.subscribe_resource(AnyUrl("chunk://xyz"))
        assert exc.value.error.code == INVALID_PARAMS
        assert isinstance(exc.value.error.data, dict)
        assert exc.value.error.data["reason"] == "not_subscribable"

    async def test_subscribe_positive_path_acks(
        self,
        fake_httpx_client: httpx.Client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Subscribe to ``corpus://status`` against a stub policy installed
        via ``monkeypatch.setitem`` (additive — won't break once Plan 03
        populates SUBSCRIPTION_POLICIES for real). The handler must ack
        with ``EmptyResult`` and the manager must hold an active task
        for the session.

        Tests that leave a subscription active at the end MUST call
        ``manager.cleanup_all()`` before exiting the in-memory harness.
        Plan 04 will wire this into ``run_stdio``'s ``finally`` block;
        until then, leaving tasks pinned past the event-loop teardown
        emits ``Task was destroyed but it is pending`` warnings.
        """
        stub: SubscriptionPolicy = _StubPolicy("corpus://status")
        monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", stub)

        server = build_server(fake_httpx_client)
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as client:
            # No exception → SDK returned EmptyResult — that's the ack.
            await client.subscribe_resource(AnyUrl("corpus://status"))
            # Exactly one active task. Assert WITHIN the session scope
            # because the in-memory harness cancels the server task on
            # context exit (which drops outstanding subscriptions).
            assert server._subscription_manager.active_count() == 1

            # Plan 04 wires this into run_stdio's finally; for Plan 02
            # tests we call it explicitly so the polling task is
            # cancelled before the event loop tears down.
            server._subscription_manager.cleanup_all()

    async def test_subscribe_then_unsubscribe_cleans_up(
        self,
        fake_httpx_client: httpx.Client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Subscribe + unsubscribe round-trip drives ``active_count`` back
        to zero (the polling task is cancelled). The unsubscribe ack
        always returns ``EmptyResult`` regardless of whether a task
        was actually cancelled (MCP spec semantic)."""
        stub: SubscriptionPolicy = _StubPolicy("corpus://status")
        monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", stub)

        server = build_server(fake_httpx_client)
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as client:
            manager = server._subscription_manager
            await client.subscribe_resource(AnyUrl("corpus://status"))
            assert manager.active_count() == 1

            await client.unsubscribe_resource(AnyUrl("corpus://status"))
            assert manager.active_count() == 0

    async def test_subscribe_twice_same_uri_same_session_rejected(
        self,
        fake_httpx_client: httpx.Client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Strict duplicate-subscribe rejection (Phase 52 CONTEXT decision A).
        The first call subscribes; the second must surface as
        ``duplicate_subscribe`` instead of the bare RuntimeError from
        ``manager.start_polling``."""
        stub: SubscriptionPolicy = _StubPolicy("corpus://status")
        monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", stub)

        server = build_server(fake_httpx_client)
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as client:
            await client.subscribe_resource(AnyUrl("corpus://status"))

            with pytest.raises(McpError) as exc:
                await client.subscribe_resource(AnyUrl("corpus://status"))
            assert exc.value.error.code == INVALID_PARAMS
            assert isinstance(exc.value.error.data, dict)
            assert exc.value.error.data["reason"] == "duplicate_subscribe"

            # Manager state is unchanged — first subscription still active.
            assert server._subscription_manager.active_count() == 1
            server._subscription_manager.cleanup_all()

    async def test_subscribe_with_trailing_slash_normalized(
        self,
        fake_httpx_client: httpx.Client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``corpus://status/`` (trailing slash) is normalized to
        ``corpus://status`` and successfully resolves the same policy.
        Mirrors the ``read_resource`` normalization rule."""
        stub: SubscriptionPolicy = _StubPolicy("corpus://status")
        monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", stub)

        server = build_server(fake_httpx_client)
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as client:
            await client.subscribe_resource(AnyUrl("corpus://status/"))
            assert server._subscription_manager.active_count() == 1
            server._subscription_manager.cleanup_all()

    async def test_unsubscribe_unknown_uri_acks_silently(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """``resources/unsubscribe`` for a URI we never subscribed to
        is a no-op ack per MCP spec. The handler must NOT reject —
        even if the URI is genuinely unknown, the spec lets clients
        send unsubscribe defensively after a disconnect."""
        server = build_server(fake_httpx_client)
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as client:
            # No exception → ack. The URI is bogus but the unsubscribe
            # handler intentionally doesn't validate (Plan 02 acceptance).
            await client.unsubscribe_resource(AnyUrl("bogus://never-subscribed"))


class TestSubscribePolicyScheme:
    """Scheme-prefix resolution: a ``job://`` policy entry must match
    ANY ``job://<id>`` URI, not just the prefix string itself."""

    async def test_job_scheme_policy_matches_any_job_id(
        self,
        fake_httpx_client: httpx.Client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Register the policy under ``"job://"`` (scheme key) so
        # ``resolve_policy`` falls through from exact to scheme match.
        stub: SubscriptionPolicy = _StubPolicy("job://")
        monkeypatch.setitem(SUBSCRIPTION_POLICIES, "job://", stub)

        server = build_server(fake_httpx_client)
        async with create_connected_server_and_client_session(
            server, raise_exceptions=True
        ) as client:
            await client.subscribe_resource(AnyUrl("job://abc123"))
            assert server._subscription_manager.active_count() == 1
            server._subscription_manager.cleanup_all()

    def test_exact_uri_policy_wins_over_scheme(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If BOTH an exact-URI policy and a scheme policy exist for the
        same URI, ``resolve_policy`` must pick the exact match. Critical
        invariant for Plan 03 where ``corpus://status`` (exact) and any
        future per-scheme ``corpus://`` entry must not collide."""
        from agent_brain_mcp.subscriptions import resolve_policy

        exact: SubscriptionPolicy = _StubPolicy("corpus://status", interval_s=1.0)
        scheme: SubscriptionPolicy = _StubPolicy("corpus://", interval_s=99.0)
        monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", exact)
        monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://", scheme)

        # ``resolve_policy`` is the public lookup helper Plan 02 uses;
        # this is the pure-function regression pin. The wire path is
        # exercised by the integration tests above.
        resolved = resolve_policy("corpus://status")
        assert resolved is exact
        # Sanity: an unrelated corpus URI falls through to the scheme
        # policy (in this test fixture).
        unrelated = resolve_policy("corpus://anything-else")
        assert unrelated is scheme


class TestSubscribeWithMockedSession:
    """Direct-handler invocation tests that don't pay the MCP SDK round-trip
    cost. Use a manually-injected ``request_ctx`` so the handler closure
    can be called like any async function.

    Why both styles: the in-memory SDK harness above proves the FULL
    wire round-trip (Subscribe Request → EmptyResult ack). These direct
    tests catch dispatch-logic regressions faster (~10x speedup) and let
    us cover edge cases (e.g., MagicMock session injection) without
    spinning up an anyio task group per test.
    """

    async def test_subscribe_handler_uses_session_from_request_context(
        self,
        fake_httpx_client: httpx.Client,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The handler must read ``server.request_context.session`` and
        pass that exact object to ``manager.start_polling``."""
        import mcp.types as types
        from mcp.server.lowlevel.server import request_ctx
        from mcp.shared.context import RequestContext

        stub: SubscriptionPolicy = _StubPolicy("corpus://status")
        monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", stub)

        server = build_server(fake_httpx_client)
        # The handler reads ``session`` from the request context AND calls
        # ``session.send_resource_updated(...)`` from the polling loop's
        # on_change closure. AsyncMock satisfies both — its
        # ``send_resource_updated`` returns an awaitable, so the polling
        # task doesn't crash when the first poll fires immediately
        # (interval=3600 keeps subsequent polls suppressed).
        fake_session = MagicMock(name="ServerSession")
        fake_session.send_resource_updated = AsyncMock(return_value=None)

        # Build a RequestContext shell. The MCP SDK stuffs it into the
        # contextvar before invoking the handler; we mirror that.
        ctx: RequestContext[Any, Any, Any] = RequestContext(
            request_id="test-req-1",
            meta=None,
            session=fake_session,
            lifespan_context=None,
            request=None,
        )
        token = request_ctx.set(ctx)
        try:
            subscribe_handler = server.request_handlers[types.SubscribeRequest]
            await subscribe_handler(
                types.SubscribeRequest(
                    method="resources/subscribe",
                    params=types.SubscribeRequestParams(uri=AnyUrl("corpus://status")),
                )
            )
        finally:
            request_ctx.reset(token)

        manager = server._subscription_manager
        # The manager keys by ``id(session)`` — the only way ``is_subscribed``
        # returns True is if start_polling received our fake_session.
        assert manager.is_subscribed(fake_session, "corpus://status")

        # Explicit teardown — the polling task lives until cleanup_all is
        # called. Without this, the task lingers past the test boundary
        # and asyncio emits "Task was destroyed but it is pending" warnings.
        manager.cleanup_all()
