"""Phase 55 Plan 03 — VAL-02 subscription lifecycle contract tests.

Exercises Phase 52's ``resources/subscribe`` → ``notifications/resources/updated``
→ ``resources/unsubscribe`` round-trip via the official MCP SDK over
stdio, for every subscribable URI Phase 52 ships:

* ``job://<id>`` (1.0s cadence in production; ``0.5s`` in this test
  via :mod:`tests.contract.conftest` cadence override). Polled stub
  ``GET /index/jobs/job_abc`` returns ``status="running",
  progress=50%`` — stable payload, so canonical_hash diff-suppression
  kicks in. Verifies the initial poke is delivered (per Phase 52
  decision C — first poll always fires).
* ``corpus://status`` (30.0s production cadence; ``0.5s`` override).
  Polled stub ``GET /health/status`` — verifies stub backend round-trip.
* ``corpus://folders`` (5.0s production cadence; ``0.5s`` override).
  Polled stub ``GET /index/folders/`` — verifies registry-driven dispatch.

Plus one disconnect-cleanup test that:

* spawns a SECOND raw ``subprocess.Popen`` (not via ``stdio_client``);
* drives initialize + subscribe via raw JSON-RPC framing on stdin;
* forcibly closes stdin to trigger Phase 52's ``run_stdio`` ``finally``
  block;
* scrapes the subprocess's stderr for the Phase 52 disconnect-cleanup
  log line — proves SUB-05's per-session cleanup fired.

The disconnect test uses the **stderr-log-scrape** verification path
per CONTEXT D-06 because Phase 52 did not ship a subscription-count
observability endpoint. Follow-up issue documented in the Plan 03
SUMMARY.md.

Subscription tests run **stdio only** per CONTEXT D-08 — Plan 04's
HTTP transport tests cover SSE notification framing separately.

Cadence tolerance: assertions use ``cadence × 1.5`` upper bound per
CONTEXT D-07. The 0.5s cadence override yields a 0.75s deadline which
gives Phase 52's polling task one full iteration plus ~250ms CI jitter
budget — empirically reliable on shared GitHub Actions runners.

Notification capture mechanism: the SDK exposes a ``message_handler``
callback on :class:`ClientSession`. Plan 01's ``mcp_stdio_session``
factory (extended by Plan 03's conftest) forwards the kwarg verbatim;
the callback receives ``ServerNotification`` whose ``.root`` is a
:class:`ResourceUpdatedNotification`. We append matching notifications
to a list the test asserts against. The pattern mirrors Phase 52
Plan 04's e2e tests (``tests/e2e/test_e2e_subscriptions.py``).
"""

from __future__ import annotations

import asyncio
import json
import select
import subprocess
import time
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from mcp.types import ResourceUpdatedNotification, ServerNotification
from pydantic import AnyUrl

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


# ---------------------------------------------------------------------------
# Helper — notification collector message_handler
# ---------------------------------------------------------------------------


def _make_collector(
    notifications: list[ResourceUpdatedNotification],
) -> Callable[[Any], Awaitable[None]]:
    """Return a ``message_handler`` callback that appends every
    ``ResourceUpdatedNotification`` to ``notifications``.

    The SDK dispatches incoming messages through
    ``ClientSession._handle_incoming`` which forwards to the configured
    ``message_handler``. The callback receives ``RequestResponder |
    ServerNotification | Exception``; we filter on
    ``ServerNotification`` and unwrap ``.root`` for the concrete
    notification type. Mirrors the pattern used in
    ``tests/e2e/test_e2e_subscriptions.py::_make_collector``.
    """

    async def handler(message: object) -> None:
        if isinstance(message, ServerNotification):
            inner = message.root
            if isinstance(inner, ResourceUpdatedNotification):
                notifications.append(inner)

    return handler


# ---------------------------------------------------------------------------
# Happy-path lifecycle matrix
# ---------------------------------------------------------------------------
#
# (uri, cadence_s, mode):
#
#   * ``cadence_s`` matches the env-var override the conftest's
#     fast-cadence script applies (0.5s). The assertion window uses
#     ``cadence_s * 1.5`` per Phase 55 CONTEXT D-07.
#   * ``mode`` is informational (CONTEXT D-05): "poll" for the three
#     URIs Phase 52 ships — none use the watcher-driven path Plan 03's
#     CONTEXT.md mentions because Phase 52 CONTEXT decision E reduced
#     ``corpus://folders`` to client-side polling.
LIFECYCLE_CASES: list[tuple[str, float, str]] = [
    ("job://job_abc", 0.5, "poll"),
    ("corpus://status", 0.5, "poll"),
    ("corpus://folders", 0.5, "poll"),
]


@pytest.mark.parametrize(
    "uri,cadence_s,mode",
    LIFECYCLE_CASES,
    ids=lambda v: str(v) if isinstance(v, str) else f"{v}s",
)
async def test_subscription_lifecycle(
    mcp_stdio_session: Callable[..., Any],
    fast_cadence_subscription_module: Any,
    uri: str,
    cadence_s: float,
    mode: str,
) -> None:
    """SUBSCRIBE → wait → ≥1 notification → UNSUBSCRIBE round-trip.

    For each of Phase 52's three subscribable URIs:

    1. Open an MCP session over stdio against the fast-cadence
       subprocess script (compresses ``corpus://status`` from 30s
       to 0.5s so the contract suite stays under 30s total).
    2. Subscribe via ``session.subscribe_resource(AnyUrl(uri))``.
    3. Wait ``cadence_s * 1.5`` seconds — long enough for the
       initial poll to fire (Phase 52 ``_poll_loop`` always emits
       the first observation) but short enough to keep the suite
       snappy.
    4. Assert at least one ``ResourceUpdatedNotification`` arrived
       carrying the subscribed URI.
    5. Unsubscribe (no-op tolerance — already-unsubscribed slots
       MUST NOT raise per MCP spec idempotency).

    Cadence override mechanism: the bundled fast-cadence script
    (``fake_subscription_server.py``, written by
    :fixture:`fast_cadence_subscription_module`) monkeypatches the
    three ``SubscriptionPolicy`` instances'  ``interval_s`` attributes
    BEFORE ``build_server()`` runs. The default 0.5s applies to all
    three URIs; no per-test env vars are needed for these happy-path
    assertions.

    Subscribe / unsubscribe payload assertions: Phase 52 emits the
    minimal MCP-spec shape ``{"uri": "<resource_uri>"}`` (CONTEXT
    decision C — payload-in-notification is non-standard). The test
    asserts ``params.uri`` matches the subscribed URI — Phase 52
    Plan 04 e2e regression-pins the same shape.
    """
    # Discard ``mode`` — informational only (kept in matrix for
    # readability per CONTEXT D-05's mode column).
    del mode
    notifications: list[ResourceUpdatedNotification] = []
    collector = _make_collector(notifications)

    async with mcp_stdio_session(
        custom_script=fast_cadence_subscription_module,
        message_handler=collector,
    ) as session:
        await session.initialize()
        await session.subscribe_resource(AnyUrl(uri))
        # Wait long enough for ≥1 poll to complete. The fast-cadence
        # script's ``interval_s = 0.5`` means the first poll fires
        # immediately on subscribe (Phase 52 ``_poll_loop``'s first
        # iteration runs before the sleep) and the second poll fires
        # at +0.5s. ``cadence_s * 1.5`` = 0.75s gives us the first
        # poll plus CI jitter headroom.
        await asyncio.sleep(cadence_s * 1.5)

        assert len(notifications) >= 1, (
            f"expected ≥1 notification for {uri} within "
            f"{cadence_s * 1.5}s, got {len(notifications)}"
        )
        # Every notification must carry the subscribed URI.
        for n in notifications:
            assert str(n.params.uri) == uri, (
                f"notification URI {n.params.uri!r} does not match "
                f"subscribed URI {uri!r}"
            )

        # Unsubscribe — must not raise. MCP spec says unsubscribe is
        # idempotent; Phase 52's wire handler tolerates the no-op case
        # for already-cleaned slots (e.g., terminal job that auto-
        # exited via SubscriptionTerminated).
        await session.unsubscribe_resource(AnyUrl(uri))


# ---------------------------------------------------------------------------
# Disconnect cleanup — SUB-05 stderr log scrape (CONTEXT D-06 fallback)
# ---------------------------------------------------------------------------


def _jsonrpc_frame(payload: dict[str, Any]) -> bytes:
    """Serialize a JSON-RPC message as a newline-delimited frame.

    MCP's stdio transport uses the JSON-RPC 2.0 spec's newline framing
    (each message is a single line of JSON terminated by ``\\n``). Used
    by the disconnect test to drive initialize + subscribe via raw
    stdin writes without spinning up a full ``ClientSession``.
    """
    return (json.dumps(payload) + "\n").encode("utf-8")


def _drain_stderr_until(
    proc: subprocess.Popen[bytes],
    *,
    pattern: str,
    timeout_s: float,
) -> str:
    """Read stderr until ``pattern`` appears or ``timeout_s`` elapses.

    Returns the accumulated stderr text. Used by the disconnect test
    to confirm the Phase 52 cleanup log line was emitted.

    Why ``select`` instead of ``proc.stderr.read()``: the latter blocks
    until EOF, which only fires after the subprocess fully exits.
    Cleanup tests need to read available output WHILE the subprocess
    is still running through its finally block.
    """
    assert proc.stderr is not None, "subprocess must have stderr=PIPE"
    deadline = time.monotonic() + timeout_s
    chunks: list[bytes] = []
    while time.monotonic() < deadline:
        # Use select to wait for stderr readiness without blocking.
        # Timeout is the smaller of 0.1s or remaining deadline so
        # ctrl-c stays responsive in interactive runs.
        remaining = max(0.0, deadline - time.monotonic())
        ready, _, _ = select.select([proc.stderr], [], [], min(0.1, remaining))
        if not ready:
            # No data ready — either subprocess is computing or stderr
            # is genuinely quiet. Loop until deadline.
            if proc.poll() is not None:
                # Subprocess exited; drain any remaining buffered data.
                tail = proc.stderr.read() or b""
                chunks.append(tail)
                break
            continue
        # Read a chunk; an empty result means EOF (subprocess exited).
        # Use os-level read to avoid Python's buffered-mode quirks
        # interacting with select.
        import os as _os

        try:
            chunk = _os.read(proc.stderr.fileno(), 4096)
        except OSError:
            break
        if not chunk:
            # EOF — subprocess exited. Stop reading.
            break
        chunks.append(chunk)
        accumulated = b"".join(chunks).decode("utf-8", errors="replace")
        if pattern in accumulated:
            return accumulated
    return b"".join(chunks).decode("utf-8", errors="replace")


async def test_disconnect_cleanup_emits_phase52_log_line(
    mcp_stdio_subprocess_handle: Callable[..., Any],
) -> None:
    """SUB-05: client disconnect cancels per-session polling tasks.

    Methodology (CONTEXT D-06 fallback path — Phase 52 ships no
    ``/mcp/subscriptions/__debug`` observability endpoint):

    1. Spawn a raw ``subprocess.Popen`` of the fast-cadence MCP
       subprocess (via ``mcp_stdio_subprocess_handle``). PIPE'd
       stdin/stdout/stderr lets us drive initialize + subscribe
       directly and scrape stderr afterwards.
    2. Hand-frame a JSON-RPC ``initialize`` request + the matching
       ``notifications/initialized`` ack + a ``resources/subscribe``
       request for ``job://job_abc`` (the production-running stub).
       Writing to stdin via the raw Popen bypasses the SDK's
       ``stdio_client`` cleanup so we can test ``run_stdio``'s
       ``finally`` block in isolation.
    3. Wait for one polling cadence (the fast-cadence script's
       0.5s default) so the polling task is alive and registered.
    4. Force-close stdin via ``proc.stdin.close()``. This triggers
       EOF in the subprocess's ``mcp.server.stdio.stdio_server()``
       which causes ``server.run`` to return, which runs
       ``run_stdio``'s ``finally`` block which calls
       ``subscription_manager.cleanup_all()``. The cleanup log
       line is emitted via ``logger.info`` if any tasks were
       cancelled.
    5. Wait for the subprocess to exit (deadline 5s), then scan
       stderr for the Phase 52 log line literal:
       ``"subscription cleanup: cancelled"`` (sub-string of
       ``"subscription cleanup: cancelled %d polling task(s) on
       session close"`` from ``server.py:984-987``).

    If Phase 52's ``run_stdio`` cleanup hook is broken, the log line
    never fires and this test fails with the accumulated stderr in
    the assertion message so the diagnosis is one ``pytest -v`` away.

    Follow-up: this test scrapes stderr because Phase 52 did not ship
    a subscription-count observability surface. Plan 03's SUMMARY.md
    files a follow-up to expose ``GET /mcp/subscriptions/__debug``
    behind ``AGENT_BRAIN_DEBUG=1`` in v10.3+ so future verifications
    can read the count directly.
    """
    # We use the raw subprocess handle, NOT mcp_stdio_session, because
    # the SDK's stdio_client wraps stdin in its own anyio task group
    # whose teardown sends SIGTERM rather than EOF. SUB-05's contract
    # is "stdio EOF triggers cleanup" — SIGTERM is a different signal
    # path that Phase 52 also handles (run_stdio's finally runs in
    # either case) but we want to verify the EOF code path specifically
    # because that's the spec-correct client-disconnect semantic.
    async with mcp_stdio_subprocess_handle() as proc:
        assert proc.stdin is not None, "stdin must be piped"
        # --- 1. Drive initialize ----------------------------------
        # Use protocolVersion matching the SDK pin's LATEST_PROTOCOL_VERSION.
        # The fake-cadence subprocess accepts any spec-conformant
        # initialize per the SDK; we hand-frame the minimum required
        # fields so the test stays decoupled from SDK version drift.
        initialize_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "plan-55-03-disconnect-test", "version": "0.0"},
            },
        }
        proc.stdin.write(_jsonrpc_frame(initialize_req))
        proc.stdin.flush()
        # Read the initialize response so we don't tear down before the
        # server has fully come up. ``_drain_stderr_until`` is a stderr
        # helper; for stdout we just await briefly. The contract suite
        # doesn't need an InitializeResult assertion — Plan 01's smoke
        # test already pins that.
        await asyncio.sleep(0.3)

        # MCP requires a notifications/initialized ack before any other
        # request will be accepted. The SDK's ClientSession.initialize
        # sends this automatically; for raw stdin we must send it
        # explicitly.
        initialized_notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        proc.stdin.write(_jsonrpc_frame(initialized_notif))
        proc.stdin.flush()

        # --- 2. Subscribe to job://job_abc ------------------------
        # job_abc is the v1 ``_DEFAULT_RESPONSES`` stub returning
        # ``status="running", progress=50%`` — perfect for the
        # disconnect test because the polling task stays alive (the
        # JobPolicy fetcher won't raise SubscriptionTerminated until
        # the status flips to a terminal value, which the stub never
        # does).
        subscribe_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/subscribe",
            "params": {"uri": "job://job_abc"},
        }
        proc.stdin.write(_jsonrpc_frame(subscribe_req))
        proc.stdin.flush()

        # Wait for one full polling cadence so the task is registered
        # and has emitted ≥1 ResourceUpdatedNotification. The fast-
        # cadence script's 0.5s default plus 250ms jitter budget.
        await asyncio.sleep(0.75)

        # --- 3. Force-close stdin ---------------------------------
        # This is the SUB-05 trigger: closing stdin without an explicit
        # unsubscribe MUST drive Phase 52's run_stdio finally block to
        # cancel the active polling task and log the cleanup line.
        proc.stdin.close()

        # --- 4. Scrape stderr for the cleanup log line ------------
        # Phase 52 emits via logger.info at server.py:984-987 — the
        # literal "subscription cleanup: cancelled" prefix is the
        # spec-mandated marker.
        stderr_text = _drain_stderr_until(
            proc,
            pattern="subscription cleanup: cancelled",
            timeout_s=5.0,
        )

        # Wait for clean subprocess exit so the test doesn't leave the
        # subprocess as an orphan (the autouse orphan-scan would
        # SIGKILL it but flag the test as failing).
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            # If the subprocess didn't exit cleanly after stdin EOF,
            # that's a Phase 52 bug — the test below will fail with
            # the log assertion which gives the diagnosis.
            pass

    # Assertion AFTER the context manager exits so any orphan is
    # already killed. The stderr scrape itself is the load-bearing
    # check: Phase 52's run_stdio finally MUST have logged the cleanup
    # line at info level, and Python's default root logger writes to
    # stderr.
    assert "subscription cleanup: cancelled" in stderr_text, (
        "Phase 52 disconnect-cleanup log line not found in subprocess "
        "stderr. Either run_stdio's finally block did not run, "
        "cleanup_all() found no tasks to cancel (the subscribe may "
        "have failed before the polling task registered), or logging "
        "is misconfigured.\n\n"
        f"Captured stderr:\n{stderr_text}"
    )
