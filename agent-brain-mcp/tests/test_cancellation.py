"""Phase 5 test: tool handlers are cancellation-responsive (plan §6.4, §12.3 #12).

Each tool handler issues a sync ``httpx`` call. If invoked directly in
an ``async def`` it would block the event loop — meaning
``asyncio.wait_for`` cannot fire its timeout and MCP
``notifications/cancelled`` cannot propagate to the in-flight request.

Phase 5 wraps the handler invocation in ``asyncio.to_thread`` so:

1. The event loop stays responsive while the HTTP call is in flight.
2. Cancelling the outer task raises ``CancelledError`` at the ``await``,
   even though the underlying thread continues running (that's a Python
   limitation — there's no portable way to kill a thread).

This is the minimum behaviour plan §6.4 promises ("cancellation is
fast-path only"): the MCP-side handler unblocks; the OS-level request
may still complete in the background, but the client gets a prompt
response.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import mcp.types as types
import pytest

from agent_brain_mcp.server import build_server


def _slow_transport(sleep_seconds: float) -> httpx.MockTransport:
    """Return a MockTransport whose handler sleeps before responding."""

    def _handler(request: httpx.Request) -> httpx.Response:
        time.sleep(sleep_seconds)
        return httpx.Response(200, json={"total_documents": 1, "total_chunks": 1})

    return httpx.MockTransport(_handler)


def _query_count_request() -> types.CallToolRequest:
    return types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name="query_count", arguments={}),
    )


@pytest.mark.asyncio
async def test_slow_handler_does_not_block_event_loop() -> None:
    """A 5s-blocking handler must be cancellable in ~1s via ``wait_for``.

    Pre-fix: sync ``httpx`` inside ``async def call_tool`` blocks the
    loop; ``asyncio.wait_for(..., timeout=1.0)`` cannot interrupt and the
    test takes ~5s.
    Post-fix (Phase 5): handler runs in ``asyncio.to_thread``; cancelling
    the awaiting coroutine returns within the timeout window.
    """
    client = httpx.Client(transport=_slow_transport(5.0), base_url="http://e2e")
    try:
        server, _ = build_server(client)
        handler = server.request_handlers[types.CallToolRequest]

        start = asyncio.get_event_loop().time()
        with pytest.raises((asyncio.TimeoutError, asyncio.CancelledError)):
            await asyncio.wait_for(handler(_query_count_request()), timeout=1.0)
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed < 2.5, (
            f"event loop appears blocked: elapsed={elapsed:.2f}s "
            "(should be ~1s once handler runs in asyncio.to_thread)"
        )
    finally:
        client.close()


@pytest.mark.asyncio
async def test_concurrent_tool_calls_overlap_not_serialize() -> None:
    """Two concurrent ``call_tool`` invocations must overlap on the loop.

    With sync httpx inline in an async handler the calls serialize:
    total ~1s for two 0.5s tasks. With ``asyncio.to_thread`` they
    overlap in the default executor: total ~0.6s.
    """
    client = httpx.Client(transport=_slow_transport(0.5), base_url="http://e2e")
    try:
        server, _ = build_server(client)
        handler = server.request_handlers[types.CallToolRequest]

        start = asyncio.get_event_loop().time()
        await asyncio.gather(
            handler(_query_count_request()),
            handler(_query_count_request()),
        )
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed < 0.9, (
            f"concurrent calls serialized: elapsed={elapsed:.2f}s "
            "(should be ~0.6s when running in asyncio.to_thread)"
        )
    finally:
        client.close()
