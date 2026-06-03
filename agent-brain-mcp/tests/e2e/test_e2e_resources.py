"""E2E: resource read + Phase 52 subscription round-trip.

Phase 4 (v1) stubs covered ``resources/read`` for the 5 ``corpus://*``
URIs but were marked ``pytest.skip`` pending the Phase 4 fixture
harness (which never materialized — ``indexed_server`` / ``mcp_client``
are still skip-stubs in ``conftest.py``).

Phase 52 (Plan 02) ships real subscribe/unsubscribe e2e tests using the
same fake-server-script pattern as :mod:`tests.test_e2e_stdio` — the
authoritative non-skipped e2e harness in this package. The original
``test_resources_subscribe_returns_method_not_found`` stub is **deleted**
because the capability flipped from ``False`` to ``True`` in Plan 02;
subscribing now acks instead of erroring with ``MethodNotFound``.

The skip-marked read tests are preserved as Phase 4 leftovers (they're
in the same file; deleting them is out of scope for Plan 02). They
remain in their pre-Plan-02 form so test counts in CI don't drift.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def test_corpus_config_returns_documented_fields(mcp_client: object) -> None:
    """``resources/read corpus://config`` returns the ConfigStatus shape
    (Phase 2 endpoint, Phase 4 wire-up)."""
    pytest.skip("Phase 4 implementation pending.")


def test_corpus_status_returns_chunk_counts(mcp_client: object) -> None:
    """``resources/read corpus://status`` exposes total_chunks, total_documents,
    indexing state, graph index counters, cache hit rates."""
    pytest.skip("Phase 4 implementation pending.")


def test_corpus_health_returns_server_info(mcp_client: object) -> None:
    """``resources/read corpus://health`` returns HealthStatus."""
    pytest.skip("Phase 4 implementation pending.")


def test_corpus_providers_lists_active_providers(mcp_client: object) -> None:
    """``resources/read corpus://providers`` lists embedding/summarization/
    reranker providers with model + healthy/degraded/unavailable status."""
    pytest.skip("Phase 4 implementation pending.")


def test_corpus_folders_includes_watch_state(mcp_client: object) -> None:
    """``resources/read corpus://folders`` returns each folder's watch_mode
    and watch_debounce_seconds (so the user can answer 'what's auto-watched')."""
    pytest.skip("Phase 4 implementation pending.")


# --- Phase 52 Plan 02 subscribe e2e tests ---------------------------------
#
# These tests spawn the agent-brain-mcp server as a subprocess via the
# official MCP Python SDK stdio_client (same pattern as
# tests/test_e2e_stdio.py — the authoritative non-skipped e2e harness).
# A stub SubscriptionPolicy is registered via SUBSCRIPTION_POLICIES
# inside the subprocess script so the wire path can be exercised end
# to end without depending on Plan 03's per-URI policies.


_FAKE_SUBSCRIBE_SERVER_SCRIPT = """
import asyncio
import os
import httpx

from agent_brain_mcp.server import build_server, run_stdio
from agent_brain_mcp.subscriptions import (
    SUBSCRIPTION_POLICIES,
    SubscriptionPolicy,
)

# Minimal stub policy registered for corpus://status so the e2e test
# can exercise the positive-path subscribe ack without depending on
# Plan 03's real cadences.
class _StubPolicy:
    uri_pattern = "corpus://status"
    interval_s = 3600.0  # never poll during the ack-only test
    drop_keys = None

    def build_fetcher(self, _api_client, _uri):
        async def _fetch():
            return {"stub": True}
        return _fetch


SUBSCRIPTION_POLICIES["corpus://status"] = _StubPolicy()


_RESPONSES = {
    ("GET", "/health/"): {
        "status": "healthy", "version": "10.2.0",
        "message": "ok", "mode": "project", "instance_id": "e2e-sub",
    },
    ("GET", "/health/status"): {
        "total_documents": 0, "total_chunks": 0,
        "indexing_in_progress": False, "current_job_id": None,
        "progress_percent": 0.0, "indexed_folders": [],
    },
}


def _handler(request):
    key = (request.method, request.url.path)
    body = _RESPONSES.get(key, {"detail": f"not configured: {key}"})
    return httpx.Response(200, json=body)


async def main():
    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://e2e",
    )
    server = build_server(client)
    await run_stdio(server)


if __name__ == "__main__":
    asyncio.run(main())
"""


@pytest.fixture
def fake_subscribe_server(tmp_path: Path) -> Path:
    """Write a self-contained MCP server subprocess script with a stub
    subscription policy registered for ``corpus://status``.

    Mirrors the ``fake_server_module`` fixture in
    :mod:`tests.test_e2e_stdio` — same pattern, different policy setup.
    """
    script = tmp_path / "fake_mcp_subscribe_server.py"
    script.write_text(_FAKE_SUBSCRIBE_SERVER_SCRIPT)
    return script


@pytest.mark.asyncio
async def test_e2e_initialize_advertises_subscribe_capability(
    fake_subscribe_server: Path,
) -> None:
    """``initialize`` over real stdio reports ``resources.subscribe: True``.

    Proves the capability flip survives the full MCP wire round-trip,
    not just the in-process ``get_capabilities`` call (which is also
    pinned by ``tests/test_initialize.py``).
    """
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    project_root = Path(__file__).resolve().parent.parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_subscribe_server)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init_result = await session.initialize()
            assert init_result.serverInfo.name == "agent-brain"
            assert init_result.capabilities.resources is not None
            assert init_result.capabilities.resources.subscribe is True


@pytest.mark.asyncio
async def test_resources_subscribe_acks_known_uri(
    fake_subscribe_server: Path,
) -> None:
    """Positive path: subscribe to ``corpus://status`` → ``EmptyResult``,
    unsubscribe → ``EmptyResult``. Replaces the v1
    ``test_resources_subscribe_returns_method_not_found`` stub: since
    Plan 02 flipped the capability to True, the SDK no longer routes
    the call to MethodNotFound — it dispatches to our handler.
    """
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from pydantic import AnyUrl

    project_root = Path(__file__).resolve().parent.parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_subscribe_server)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Subscribe acks with EmptyResult (no body).
            sub_result = await session.subscribe_resource(AnyUrl("corpus://status"))
            # EmptyResult — pydantic serializes as an object with no extra
            # fields. The SDK returns the exact EmptyResult type.
            assert sub_result is not None

            # Unsubscribe acks with EmptyResult.
            unsub_result = await session.unsubscribe_resource(AnyUrl("corpus://status"))
            assert unsub_result is not None


@pytest.mark.asyncio
async def test_subscribe_unknown_uri_rejected_with_reason(
    fake_subscribe_server: Path,
) -> None:
    """Negative path: subscribe to ``bogus://x`` → MCP error with
    ``code=-32602`` and ``data.reason == "unknown_uri"``."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.shared.exceptions import McpError
    from pydantic import AnyUrl

    project_root = Path(__file__).resolve().parent.parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_subscribe_server)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            with pytest.raises(McpError) as exc:
                await session.subscribe_resource(AnyUrl("bogus://x"))
            assert exc.value.error.code == -32602
            assert isinstance(exc.value.error.data, dict)
            assert exc.value.error.data["reason"] == "unknown_uri"


@pytest.mark.asyncio
async def test_subscribe_not_subscribable_uri_rejected_with_reason(
    fake_subscribe_server: Path,
) -> None:
    """Negative path: subscribe to ``corpus://config`` (known but not
    in the subscribable allowlist) → ``data.reason == "not_subscribable"``."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.shared.exceptions import McpError
    from pydantic import AnyUrl

    project_root = Path(__file__).resolve().parent.parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_subscribe_server)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            with pytest.raises(McpError) as exc:
                await session.subscribe_resource(AnyUrl("corpus://config"))
            assert exc.value.error.code == -32602
            assert isinstance(exc.value.error.data, dict)
            assert exc.value.error.data["reason"] == "not_subscribable"


@pytest.mark.asyncio
async def test_subscribe_duplicate_same_session_rejected(
    fake_subscribe_server: Path,
) -> None:
    """Negative path: subscribing twice to the same URI on the same
    session rejects with ``data.reason == "duplicate_subscribe"``.
    Pinned per Phase 52 CONTEXT decision A (strict rejection so the
    polling-task lifecycle stays deterministic)."""
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.shared.exceptions import McpError
    from pydantic import AnyUrl

    project_root = Path(__file__).resolve().parent.parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_subscribe_server)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.subscribe_resource(AnyUrl("corpus://status"))
            with pytest.raises(McpError) as exc:
                await session.subscribe_resource(AnyUrl("corpus://status"))
            assert exc.value.error.code == -32602
            assert isinstance(exc.value.error.data, dict)
            assert exc.value.error.data["reason"] == "duplicate_subscribe"
