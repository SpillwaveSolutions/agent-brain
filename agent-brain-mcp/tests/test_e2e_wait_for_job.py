"""End-to-end test: ``wait_for_job`` over the official MCP SDK.

Plan 04 acceptance criterion: a real MCP SDK client invokes
``wait_for_job`` against an ``agent-brain-mcp`` stdio subprocess that
backs a stub-job server. The client receives ≥2 progress notifications
and the final result is the terminal job record.

This is the closing-out test for TOOL-04 — it proves the entire
async-handler + progress-notifier wire path works through the MCP
Python SDK, not just through internal handler invocation.

The harness mirrors the pattern from ``tests/test_e2e_stdio.py``:
spawn a subprocess that wires ``build_server`` + a stub
``MockTransport`` httpx backend. The stub progresses the job through
two ``running`` polls then a ``succeeded`` terminal — the client side
should see at least 3 notifications (2 per-poll + 1 final) and a
terminal job record in the tool result.

Run with ``poetry run pytest -m e2e tests/test_e2e_wait_for_job.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


_FAKE_SERVER_SCRIPT = """
import asyncio
import os

import httpx

from agent_brain_mcp.server import build_server, run_stdio


# Track how many times the client has polled /index/jobs/<id>.
# The first two polls return running; the third onward returns
# succeeded. This gives the SDK at least 3 progress emissions
# (2 per-running-poll + 1 final after the terminal poll).
_POLL_COUNT = [0]


_STATIC = {
    ("GET", "/health/"): {
        "status": "healthy", "version": "10.2.0",
        "message": "ok", "mode": "project", "instance_id": "e2e-wait",
    },
    ("GET", "/health/status"): {
        "total_documents": 0, "total_chunks": 0,
        "indexing_in_progress": True, "current_job_id": "e2e-wait-job",
        "progress_percent": 0.0, "indexed_folders": [],
    },
    ("GET", "/health/config"): {
        "storage_backend": "chroma",
        "stores": {"vector": True, "bm25": True, "graph": False},
        "reranker_enabled": False,
        "embedding_model": "text-embedding-3-large",
        "rerank_model": None, "graph_extractor": None,
        "watcher_running": False,
    },
    ("GET", "/health/providers"): {
        "config_source": None, "strict_mode": False,
        "validation_errors": [], "providers": [],
        "timestamp": "2026-06-03T00:00:00Z",
    },
}


def _job_record_for_poll(n):
    if n < 2:
        return {
            "job_id": "e2e-wait-job",
            "status": "running",
            "progress_percent": float(33 * (n + 1)),  # 33%, 66%
            "message": f"e2e poll #{n + 1}",
        }
    return {
        "job_id": "e2e-wait-job",
        "status": "succeeded",
        "progress_percent": 100.0,
        "message": "e2e job complete",
    }


def _handler(request):
    key = (request.method, request.url.path)
    if key == ("GET", "/index/jobs/e2e-wait-job"):
        body = _job_record_for_poll(_POLL_COUNT[0])
        _POLL_COUNT[0] += 1
        return httpx.Response(200, json=body)
    body = _STATIC.get(key, {"detail": f"not configured: {key}"})
    return httpx.Response(200, json=body)


async def main():
    client = httpx.Client(
        transport=httpx.MockTransport(_handler),
        base_url="http://e2e-wait",
    )
    server, manager = build_server(client)
    await run_stdio(server, manager)


if __name__ == "__main__":
    asyncio.run(main())
"""


@pytest.fixture
def fake_wait_server_module(tmp_path: Path) -> Path:
    """Write the self-contained subprocess script for this e2e."""
    script = tmp_path / "fake_wait_server.py"
    script.write_text(_FAKE_SERVER_SCRIPT)
    return script


@pytest.mark.asyncio
async def test_wait_for_job_emits_progress_via_sdk(
    fake_wait_server_module: Path,
) -> None:
    """Real MCP SDK client receives progress notifications + terminal result.

    Wire:

    1. Spawn ``agent-brain-mcp`` stdio subprocess wired to the
       stub-job server.
    2. ``initialize`` (MCP handshake).
    3. Call ``wait_for_job`` with the stub job id; attach a
       ``progress_callback`` that records every progress notification
       received from the server.
    4. Assert: ≥2 progress notifications received (at the cadence of
       the handler's per-poll emissions) AND the tool result's
       structured content carries the terminal record.
    """
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    project_root = Path(__file__).resolve().parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(fake_wait_server_module)],
        cwd=str(project_root),
        env={"PYTHONPATH": str(project_root)},
    )

    # Capture every progress notification the SDK delivers to us.
    captured: list[tuple[float, float | None, str | None]] = []

    async def _on_progress(
        progress: float, total: float | None, message: str | None
    ) -> None:
        captured.append((progress, total, message))

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "wait_for_job",
                {
                    # Drive the poll cadence below the default 1.0s so the
                    # whole e2e completes in ~1s wall-clock instead of ~3s.
                    "job_id": "e2e-wait-job",
                    "poll_interval_seconds": 0.5,
                    "timeout_seconds": 30,
                },
                progress_callback=_on_progress,
            )

            # Tool result carries structuredContent with the terminal record.
            assert result.structuredContent is not None
            structured = result.structuredContent
            assert structured["job_id"] == "e2e-wait-job"
            assert structured["status"] == "succeeded"
            assert structured["final"] is True
            assert structured["elapsed_seconds"] >= 0.0

    # The SDK delivered ≥2 progress notifications to our callback (one
    # per running poll + the final terminal emission). The stub
    # server's poll counter started at 0 and returned running on the
    # first 2 polls + succeeded on the 3rd; handler emits 3 per-poll +
    # 1 final = 4 total emissions. The SDK may deliver fewer if some
    # arrive after the result (rare but possible in stdio); we assert
    # ≥2 as the Plan 04 acceptance criterion floor.
    assert len(captured) >= 2, (
        f"Expected >= 2 progress notifications via SDK callback, "
        f"got {len(captured)}: {captured}"
    )
    # Every payload conforms to MCP spec: progress in [0, 1], total
    # either 1.0 or None (SDK passes through), message str|None.
    for progress, total, message in captured:
        assert 0.0 <= progress <= 1.0
        assert total is None or total == 1.0
        assert message is None or isinstance(message, str)
