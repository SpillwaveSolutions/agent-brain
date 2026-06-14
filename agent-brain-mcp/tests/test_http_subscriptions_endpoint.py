"""Tests for GET /mcp/subscriptions debug endpoint (HOUSE-01, Plan 64-04).

Exercises the route wired in ``agent_brain_mcp.http.build_asgi_app`` using
Starlette's synchronous TestClient so no real uvicorn or asyncio machinery
is needed.

Tested invariants (Plan 64-04 Task 2 acceptance criteria):

* Test 1: GET /mcp/subscriptions returns 200 + JSON body with keys
  transport, server_uptime_s, active_count, subscriptions.
* Test 2: No Authorization header required — 200 with no auth
  (same trust model as /healthz).
* Test 3: When the manager has an active subscription, subscriptions[]
  contains an entry with truncated session_id, uri, cadence_s,
  started_at, last_notified_at.
* Test 4: transport == "http" and server_uptime_s is a non-negative float.
* Test 5: /healthz still returns 200 with {"status":"ok","transport":"http"}
  (the new route does not break the existing one).
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from starlette.testclient import TestClient

from agent_brain_mcp.http import HEALTHZ_PATH, SUBSCRIPTIONS_PATH, build_asgi_app
from agent_brain_mcp.server import build_server
from agent_brain_mcp.subscriptions import SubscriptionManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_server() -> tuple[Any, SubscriptionManager]:
    """Build a low-level MCP server + manager backed by a mock HTTP client.

    Returns (server, manager) — the SubscriptionManager is the same
    one build_server uses internally.
    """
    backend_client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"detail": "test-stub"})
        ),
        base_url="http://test-agent-brain",
    )
    server, manager = build_server(backend_client)
    return server, manager


# ---------------------------------------------------------------------------
# Test 1: GET /mcp/subscriptions returns 200 + expected JSON keys
# ---------------------------------------------------------------------------


def test_subscriptions_endpoint_returns_200_with_expected_keys() -> None:
    """GET /mcp/subscriptions returns HTTP 200 and a JSON body containing
    transport, server_uptime_s, active_count, subscriptions keys."""
    server, manager = _make_fake_server()
    app = build_asgi_app(server, manager)

    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(SUBSCRIPTIONS_PATH)

    assert response.status_code == 200
    body = response.json()
    assert "transport" in body, f"missing 'transport' in {body}"
    assert "server_uptime_s" in body, f"missing 'server_uptime_s' in {body}"
    assert "active_count" in body, f"missing 'active_count' in {body}"
    assert "subscriptions" in body, f"missing 'subscriptions' in {body}"


# ---------------------------------------------------------------------------
# Test 2: No auth required — 200 with no Authorization header
# ---------------------------------------------------------------------------


def test_subscriptions_endpoint_requires_no_auth() -> None:
    """GET /mcp/subscriptions returns 200 without an Authorization header
    (same trust model as /healthz — loopback-only, no-token)."""
    server, manager = _make_fake_server()
    app = build_asgi_app(server, manager)

    with TestClient(app, raise_server_exceptions=True) as client:
        # Explicitly send NO Authorization header.
        response = client.get(SUBSCRIPTIONS_PATH)

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Test 3: Active subscription appears in subscriptions[] with expected fields
# ---------------------------------------------------------------------------


def test_subscriptions_endpoint_reports_active_subscription() -> None:
    """When the manager has an active subscription, the subscriptions[]
    array contains an entry with truncated session_id, uri, cadence_s,
    started_at, last_notified_at fields."""
    server, manager = _make_fake_server()
    session = object()

    # Start a subscription in the manager without running an event loop
    # inside the TestClient sync context. We use asyncio.run to drive
    # start_polling once (it's synchronous — no await needed).
    async def blocking_fetcher() -> dict[str, Any]:
        await asyncio.sleep(9999)
        return {"value": 1}  # pragma: no cover

    async def noop_on_change(uri: str, payload: dict[str, Any]) -> None:
        pass

    async def _start() -> None:
        manager.start_polling(
            session,
            "job://test_abc",
            2.5,
            blocking_fetcher,
            noop_on_change,
        )
        await asyncio.sleep(0.01)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_start())

        app = build_asgi_app(server, manager)
        with TestClient(app, raise_server_exceptions=True) as client:
            response = client.get(SUBSCRIPTIONS_PATH)

        assert response.status_code == 200
        body = response.json()
        assert body["active_count"] >= 1
        assert len(body["subscriptions"]) >= 1

        entry = body["subscriptions"][0]
        assert "session_id" in entry
        assert len(entry["session_id"]) <= 8  # truncated
        assert entry["uri"] == "job://test_abc"
        assert entry["cadence_s"] == 2.5
        assert entry["started_at"] is not None
        assert "last_notified_at" in entry  # may be None if no poll fired
    finally:
        loop.run_until_complete(asyncio.sleep(0))
        # Cancel pending tasks before closing.
        for task in asyncio.all_tasks(loop):
            task.cancel()
        loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
        loop.close()
        manager.cleanup_all()


# ---------------------------------------------------------------------------
# Test 4: transport == "http" and server_uptime_s is a non-negative float
# ---------------------------------------------------------------------------


def test_subscriptions_endpoint_transport_and_uptime() -> None:
    """transport field is 'http' and server_uptime_s is a non-negative float."""
    server, manager = _make_fake_server()
    app = build_asgi_app(server, manager)

    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(SUBSCRIPTIONS_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["transport"] == "http"
    assert isinstance(body["server_uptime_s"], float)
    assert body["server_uptime_s"] >= 0.0


# ---------------------------------------------------------------------------
# Test 5: /healthz still returns 200 with correct body (no regression)
# ---------------------------------------------------------------------------


def test_healthz_still_works_after_new_route() -> None:
    """/healthz returns 200 with {"status":"ok","transport":"http"} —
    the new /mcp/subscriptions route does not break the existing one."""
    server, manager = _make_fake_server()
    app = build_asgi_app(server, manager)

    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(HEALTHZ_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "transport": "http"}


# ---------------------------------------------------------------------------
# Bonus: build_asgi_app with manager=None still returns 200 (backward compat)
# ---------------------------------------------------------------------------


def test_subscriptions_endpoint_no_manager_returns_empty() -> None:
    """build_asgi_app(server) with no manager arg (default None) still
    returns 200 with active_count==0 and empty subscriptions (backward
    compatibility for callers that don't pass a manager)."""
    server, _ = _make_fake_server()
    # Default manager=None path.
    app = build_asgi_app(server)

    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get(SUBSCRIPTIONS_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["active_count"] == 0
    assert body["subscriptions"] == []
