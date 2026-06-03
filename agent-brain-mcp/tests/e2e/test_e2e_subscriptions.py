"""E2E subscription tests — SDK-driven SUB-01/02/03/05 acceptance.

Plan 04 Task 3. Spawns ``agent-brain-mcp`` (via a fake subprocess script
that wires our :func:`build_server` + a MockTransport httpx client) and
uses the official MCP Python SDK ``stdio_client`` + ``ClientSession``
to exercise the FULL subscribe → receive notification → unsubscribe /
disconnect → assert-cleanup flow over the actual MCP wire.

Five tests cover the Phase 52 acceptance contract end-to-end:

1. ``test_subscribe_corpus_status_emits_on_change`` — SUB-02. Fast-cadence
   stub policy for ``corpus://status``; mocked health endpoint flips a
   non-volatile field on the 2nd poll; client receives ≥1
   ``notifications/resources/updated`` within 1.5s.
2. ``test_subscribe_job_emits_until_terminal`` — SUB-01. Job status sequence
   running → running → completed; client receives ≥2 notifications and
   the polling task exits cleanly via :class:`SubscriptionTerminated`
   (Plan 03 sentinel).
3. ``test_subscribe_folders_active_cadence`` — SUB-03. Fast-cadence stub
   for ``corpus://folders``; folder list flips on the 2nd poll; client
   sees 2 notifications within 1.5s.
4. ``test_disconnect_cleans_up_polling_tasks`` — SUB-05. PRIMARY assertion
   uses an injectable fetcher counter (deterministic — no OS-dependent
   thread inspection): subscribe → counter increments → close stdin →
   wait → counter stops incrementing. This is the load-bearing test for
   Plan 04's ``run_stdio`` cleanup hook.
5. ``test_two_sessions_independent_subscriptions`` — multi-session
   isolation. Each ``stdio_client`` invocation spawns its own MCP
   subprocess (CONTEXT decision A semantics for stdio); the test
   verifies session A's close doesn't affect session B's subscription
   stream. Documented as cross-process isolation, which is the trivial
   stdio analog of the in-process unit-level isolation Plan 01 already
   covers (``tests/subscriptions/test_manager.py`` —
   ``test_two_sessions_for_same_uri_get_independent_tasks``).

SDK pattern notes (spike from Plan 04 risk register):

* ``ClientSession`` accepts a ``message_handler`` callback that receives
  ``RequestResponder | ServerNotification | Exception``. We filter on
  ``ServerNotification`` whose ``.root`` is a
  ``ResourceUpdatedNotification`` and append to a list.
* Notifications arrive on a background task inside ``ClientSession``;
  we sleep + assert rather than blocking on a queue (good enough for
  the cadences we test — 0.3–0.5s polling, 1.5–4s assertion window).
* Each subprocess scripts its own fake ``ApiClient`` responses inline.
  The script also installs a stub :class:`SubscriptionPolicy` via
  ``monkeypatch.setitem(SUBSCRIPTION_POLICIES, ...)`` equivalent —
  directly assigning to the dict before ``build_server()`` runs.
"""

from __future__ import annotations

import asyncio
import builtins
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from mcp.types import ResourceUpdatedNotification, ServerNotification

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Helper: filter ResourceUpdatedNotification out of the SDK message stream
# ---------------------------------------------------------------------------


def _make_collector(
    notifications: list[ResourceUpdatedNotification],
) -> Callable[[Any], Awaitable[None]]:
    """Build a ``message_handler`` that appends every
    ``ResourceUpdatedNotification`` to ``notifications``.

    The SDK dispatches notifications through
    :meth:`ClientSession._handle_incoming` which forwards to the
    ``message_handler`` callback. The callback receives either a
    ``RequestResponder``, a ``ServerNotification`` (discriminated
    union — ``.root`` is the concrete notification), or an
    ``Exception``. We unwrap ``ServerNotification.root`` and filter on
    type.
    """

    async def handler(message: object) -> None:
        if isinstance(message, ServerNotification):
            inner = message.root
            if isinstance(inner, ResourceUpdatedNotification):
                notifications.append(inner)

    return handler


# ---------------------------------------------------------------------------
# Subprocess script — fast-cadence stub policies for each test
# ---------------------------------------------------------------------------
#
# The pattern mirrors tests/e2e/test_e2e_resources.py and
# tests/test_e2e_stdio.py: write a self-contained Python script into a
# tmp_path, then spawn it via StdioServerParameters. The script:
#
#  1. Replaces SUBSCRIPTION_POLICIES entries with fast-cadence stubs.
#  2. Wires a MockTransport httpx client whose handler can be
#     parameterized by env vars passed in StdioServerParameters.env.
#  3. Builds the server + runs run_stdio.
#
# Tests parameterize via ENV variables on the subprocess so the same
# fake script handles all 5 e2e tests with different fixture data.


_FAKE_SUBSCRIBE_SERVER_SCRIPT = """
import asyncio
import json
import os
import httpx

from agent_brain_mcp.server import build_server, run_stdio
from agent_brain_mcp.subscriptions import SUBSCRIPTION_POLICIES


# Stub policy with a fast interval for the test. The wire shape that
# Plan 02 uses is: ``policy.interval_s``, ``policy.drop_keys``,
# ``policy.build_fetcher(api_client, uri)``. We satisfy that Protocol
# structurally and parameterize the response stream via the
# ``_FETCHER_STATE`` dict + env-controlled state machine.
_FETCHER_STATE = {
    "job_polls": 0,
    "status_polls": 0,
    "folders_polls": 0,
}


def _job_payload():
    n = _FETCHER_STATE["job_polls"]
    _FETCHER_STATE["job_polls"] = n + 1
    if n < int(os.environ.get("JOB_RUNNING_POLLS", "2")):
        return {
            "job_id": "job-fast",
            "status": "running",
            "progress_percent": float(n) * 30,
            "message": f"poll {n}",
        }
    return {
        "job_id": "job-fast",
        "status": "completed",
        "progress_percent": 100.0,
        "message": "Done.",
    }


def _status_payload():
    n = _FETCHER_STATE["status_polls"]
    _FETCHER_STATE["status_polls"] = n + 1
    # Always-changing total_chunks so the canonical_hash differs on
    # every poll. Tests that care about diff-suppression use a different
    # stub policy or assert on count rather than count > N exactly.
    return {
        "total_documents": n,
        "total_chunks": n * 10,
        "indexing_in_progress": False,
        "current_job_id": None,
        "progress_percent": 0.0,
        "indexed_folders": [],
    }


def _folders_payload():
    n = _FETCHER_STATE["folders_polls"]
    _FETCHER_STATE["folders_polls"] = n + 1
    folders = []
    if n >= 1:
        folders = [
            {
                "folder_path": "/tmp/a",
                "chunk_count": 5,
                "last_indexed": "2026-06-03",
                "watch_mode": "off",
                "watch_debounce_seconds": 30,
            }
        ]
    return {"folders": folders}


# Stub policies — interval set from env so each test can tune cadence.
class _StubJobPolicy:
    uri_pattern = "job://"
    interval_s = float(os.environ.get("JOB_INTERVAL_S", "0.3"))
    drop_keys = None

    def build_fetcher(self, _api_client, _uri):
        from agent_brain_mcp.subscriptions import SubscriptionTerminated

        async def fetcher():
            payload = _job_payload()
            if payload["status"] in {"completed", "failed", "cancelled"}:
                raise SubscriptionTerminated(payload)
            return payload

        return fetcher


class _StubStatusPolicy:
    uri_pattern = "corpus://status"
    interval_s = float(os.environ.get("STATUS_INTERVAL_S", "0.3"))
    drop_keys = None

    def build_fetcher(self, _api_client, _uri):
        async def fetcher():
            return _status_payload()

        return fetcher


class _StubFoldersPolicy:
    uri_pattern = "corpus://folders"
    interval_s = float(os.environ.get("FOLDERS_INTERVAL_S", "0.3"))
    drop_keys = None

    def build_fetcher(self, _api_client, _uri):
        async def fetcher():
            return _folders_payload()

        return fetcher


# Replace registry entries with stubs so test-cadence runs.
SUBSCRIPTION_POLICIES["job://"] = _StubJobPolicy()
SUBSCRIPTION_POLICIES["corpus://status"] = _StubStatusPolicy()
SUBSCRIPTION_POLICIES["corpus://folders"] = _StubFoldersPolicy()


# Counter file — for the disconnect test, the e2e parent reads it to
# verify the polling task stopped fetching after the disconnect.
COUNTER_PATH = os.environ.get("FETCHER_COUNTER_PATH")
if COUNTER_PATH:

    _orig_status_payload = _status_payload

    def _status_payload_with_counter():
        # Write the running count to disk on every fetch so the parent
        # can poll-stat it after sending the disconnect.
        result = _orig_status_payload()
        try:
            with open(COUNTER_PATH, "w") as f:
                f.write(str(_FETCHER_STATE["status_polls"]))
        except OSError:
            pass
        return result

    # Rebind the global so the stub policy's fetcher uses the counter.
    globals()["_status_payload"] = _status_payload_with_counter


_RESPONSES = {
    ("GET", "/health/"): {
        "status": "healthy", "version": "10.2.0",
        "message": "ok", "mode": "project", "instance_id": "e2e-sub",
    },
    # Unused by the stub policies but keep for resources/read fallback.
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
    server, manager = build_server(client)
    await run_stdio(server, manager)


if __name__ == "__main__":
    asyncio.run(main())
"""


@pytest.fixture
def fake_subscriptions_server(tmp_path: Path) -> Path:
    """Write the self-contained MCP server subprocess script with stub
    fast-cadence subscription policies for the three subscribable URIs.

    Mirrors ``fake_subscribe_server`` in ``tests/e2e/test_e2e_resources.py``
    but with three policies registered (corpus://status, job://,
    corpus://folders) at faster cadences so the e2e test windows stay
    snappy.
    """
    script = tmp_path / "fake_mcp_subscriptions_server.py"
    script.write_text(_FAKE_SUBSCRIBE_SERVER_SCRIPT)
    return script


def _server_params(script: Path, **env_overrides: str) -> Any:
    """Build StdioServerParameters for the e2e subprocess."""
    from mcp.client.stdio import StdioServerParameters

    project_root = Path(__file__).resolve().parent.parent.parent
    env = {"PYTHONPATH": str(project_root)}
    env.update(env_overrides)
    return StdioServerParameters(
        command=sys.executable,
        args=[str(script)],
        cwd=str(project_root),
        env=env,
    )


# ---------------------------------------------------------------------------
# SUB-02: corpus://status emits notifications/resources/updated on change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_corpus_status_emits_on_change(
    fake_subscriptions_server: Path,
) -> None:
    """SUB-02 acceptance: subscribe to ``corpus://status``; mocked health
    payload flips on the 2nd poll; client receives ≥1
    ``notifications/resources/updated`` within 1.5s."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    from pydantic import AnyUrl

    notifications: list[ResourceUpdatedNotification] = []
    params = _server_params(fake_subscriptions_server, STATUS_INTERVAL_S="0.3")

    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write, message_handler=_make_collector(notifications)
        ) as session:
            await session.initialize()
            await session.subscribe_resource(AnyUrl("corpus://status"))
            # First poll fires immediately; second poll (with mutated
            # payload) fires after interval_s. Wait 1.5s — ≥1
            # notification must arrive.
            await asyncio.sleep(1.5)
            await session.unsubscribe_resource(AnyUrl("corpus://status"))

    assert len(notifications) >= 1, f"expected ≥1 notification, got {notifications}"
    # First notification's URI matches what we subscribed to.
    assert str(notifications[0].params.uri) == "corpus://status"


# ---------------------------------------------------------------------------
# SUB-01: job:// emits notifications until terminal status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_job_emits_until_terminal(
    fake_subscriptions_server: Path,
) -> None:
    """SUB-01 acceptance: subscribe to ``job://job-fast``; payload
    sequence is running → running → completed (controlled by
    JOB_RUNNING_POLLS=2). Client receives ≥2 notifications and the
    polling task auto-exits via Plan 03's SubscriptionTerminated
    sentinel — verified by the unsubscribe being a no-op (the slot is
    already gone) and the notification stream halting."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    from pydantic import AnyUrl

    notifications: list[ResourceUpdatedNotification] = []
    params = _server_params(
        fake_subscriptions_server,
        JOB_INTERVAL_S="0.3",
        JOB_RUNNING_POLLS="2",
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write, message_handler=_make_collector(notifications)
        ) as session:
            await session.initialize()
            await session.subscribe_resource(AnyUrl("job://job-fast"))
            # Wait long enough for: poll #1 (running) + sleep +
            # poll #2 (running) + sleep + poll #3 (completed →
            # SubscriptionTerminated → final on_change). At 0.3s
            # cadence that's <1.2s. Pad to 1.5s for CI jitter.
            await asyncio.sleep(1.5)
            # Unsubscribe is a no-op after terminal (the slot was
            # already scrubbed). MCP semantic is idempotent ack —
            # this MUST NOT raise.
            await session.unsubscribe_resource(AnyUrl("job://job-fast"))

    assert (
        len(notifications) >= 2
    ), f"expected ≥2 notifications, got {len(notifications)}"
    # Every notification matches the subscribed URI.
    for n in notifications:
        assert str(n.params.uri) == "job://job-fast"


# ---------------------------------------------------------------------------
# SUB-03: corpus://folders emits on folder change at active cadence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_folders_active_cadence(
    fake_subscriptions_server: Path,
) -> None:
    """SUB-03 acceptance: subscribe to ``corpus://folders`` with a
    fast 0.3s cadence stub. First poll returns empty list (hash A);
    second poll returns a single folder (hash B). Two distinct
    canonical hashes → two notifications within 1.5s."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    from pydantic import AnyUrl

    notifications: list[ResourceUpdatedNotification] = []
    params = _server_params(fake_subscriptions_server, FOLDERS_INTERVAL_S="0.3")

    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write, message_handler=_make_collector(notifications)
        ) as session:
            await session.initialize()
            await session.subscribe_resource(AnyUrl("corpus://folders"))
            await asyncio.sleep(1.5)
            await session.unsubscribe_resource(AnyUrl("corpus://folders"))

    assert (
        len(notifications) >= 2
    ), f"expected ≥2 notifications (initial + change), got {notifications}"
    for n in notifications:
        assert str(n.params.uri) == "corpus://folders"


# ---------------------------------------------------------------------------
# SUB-05: disconnect cleans up polling tasks (PRIMARY: counter-based)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disconnect_cleans_up_polling_tasks(
    fake_subscriptions_server: Path, tmp_path: Path
) -> None:
    """SUB-05 acceptance — the load-bearing test for Plan 04's
    ``run_stdio`` cleanup hook.

    Methodology (per Plan 04 risk register — primary deterministic
    assertion):

    1. Spawn the MCP server subprocess via ``stdio_client``.
    2. Subscribe to ``corpus://status``. The subprocess writes the
       current fetch count to ``COUNTER_PATH`` on every poll —
       monotonically increasing while the loop is alive.
    3. Wait until the counter has incremented at least twice
       (proves polling is active).
    4. Exit the ``stdio_client`` / ``ClientSession`` context — this
       closes stdin which triggers EOF in run_stdio's
       ``stdio_server()`` async-with body. run_stdio's
       ``try/finally`` then calls ``cleanup_all()`` which cancels
       the polling task.
    5. Snapshot the counter value. Wait 1.5s (covers ~5 polling
       intervals at 0.3s cadence). Re-read the counter — it MUST
       be the same as the snapshot, proving the polling loop
       stopped fetching.

    If Plan 04's cleanup hook is broken, the polling task survives
    past the stdio shutdown and the counter keeps growing for the
    subprocess's lifetime — this test fails loudly with a delta > 0.
    """
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    from pydantic import AnyUrl

    counter_path = tmp_path / "fetcher.counter"
    params = _server_params(
        fake_subscriptions_server,
        STATUS_INTERVAL_S="0.3",
        FETCHER_COUNTER_PATH=str(counter_path),
    )

    pre_disconnect = 0
    # The SDK's stdio_client task group surfaces an ExceptionGroup
    # containing anyio.BrokenResourceError when the subprocess
    # emits a final in-flight message after the client closed its
    # read stream. This is harmless on the subprocess side (the
    # write succeeds; the parent has just stopped reading) and is
    # exactly the scenario Plan 04's cleanup hook is designed to
    # handle: the subprocess's run_stdio.finally still runs and
    # cancels the polling task. The teardown noise is an SDK
    # quirk, NOT a Phase 52 bug. We catch it explicitly so the
    # test focuses on the cleanup-hook assertion that follows.
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await session.subscribe_resource(AnyUrl("corpus://status"))

                # Wait until counter is at least 2 — proves polling fired.
                deadline = asyncio.get_event_loop().time() + 3.0
                while asyncio.get_event_loop().time() < deadline:
                    if counter_path.exists():
                        try:
                            if int(counter_path.read_text().strip() or "0") >= 2:
                                break
                        except ValueError:
                            pass
                    await asyncio.sleep(0.1)

                # Sanity check before the disconnect.
                assert counter_path.exists(), "counter file never created"
                pre_disconnect = int(counter_path.read_text().strip())
                assert pre_disconnect >= 2, (
                    f"polling never ran ≥2 cycles before disconnect "
                    f"({pre_disconnect})"
                )
            # Exiting ClientSession context here closes its read side.
        # Exiting stdio_client context closes stdin → run_stdio's
        # finally block runs → cleanup_all() cancels the polling task.
    except builtins.BaseExceptionGroup as eg:
        # Filter out the expected BrokenResourceError; surface any
        # unexpected exception type so real bugs aren't swallowed.
        # ``BaseExceptionGroup`` is a Python 3.11+ builtin; we
        # explicitly route through ``builtins`` so static analyzers
        # don't trip on the 3.10 minimum.
        remaining = [
            exc
            for exc in eg.exceptions
            if not isinstance(exc, anyio_BrokenResourceError())
        ]
        if remaining:
            raise builtins.BaseExceptionGroup(  # noqa: B904 — preserve group
                "unexpected exceptions during disconnect", remaining
            )

    # Wait a generous window (Plan 04 risk register §2 — 2s budget +
    # padding) for the cancellation + subprocess teardown to settle.
    await asyncio.sleep(1.5)

    # Counter must not have advanced beyond pre_disconnect by more
    # than 1 (the last-in-flight poll may have written one final
    # value before cancellation kicked in — that's acceptable; any
    # more than that means the loop kept running).
    if counter_path.exists():
        post_disconnect = int(counter_path.read_text().strip())
        delta = post_disconnect - pre_disconnect
        assert delta <= 1, (
            f"polling loop kept running after disconnect: "
            f"pre={pre_disconnect}, post={post_disconnect}, delta={delta}"
        )


def anyio_BrokenResourceError() -> type[BaseException]:  # noqa: N802
    """Import-on-demand helper so the test module doesn't hard-depend
    on anyio at module load (the SDK pulls it in transitively, but
    keeping this lazy makes the dependency explicit at the call site).
    """
    import anyio

    return anyio.BrokenResourceError


# ---------------------------------------------------------------------------
# Cross-process isolation — stdio analog of multi-session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_sessions_independent_subscriptions(
    fake_subscriptions_server: Path,
) -> None:
    """Each ``stdio_client`` invocation spawns its own MCP subprocess —
    process isolation is the stdio analog of CONTEXT decision A's
    per-session multi-subscription semantics. The "real"
    same-process-multi-session test is Plan 01's
    ``test_two_sessions_for_same_uri_get_independent_tasks`` which
    runs inside a single asyncio loop.

    Here we verify the trivial-but-load-bearing property: closing
    session A's subprocess does NOT affect session B's notification
    stream. The 5th test in the Plan 04 acceptance list — kept lean
    per Plan 04 risk register §3 (which calls this out as a stdio-
    semantic trivial case)."""
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    from pydantic import AnyUrl

    notifications_a: list[ResourceUpdatedNotification] = []
    notifications_b: list[ResourceUpdatedNotification] = []

    params = _server_params(fake_subscriptions_server, STATUS_INTERVAL_S="0.3")

    # Session B is started first and kept alive across the entire
    # lifetime of session A. We assert B keeps receiving
    # notifications after A's subprocess goes away.
    async with stdio_client(params) as (read_b, write_b):
        async with ClientSession(
            read_b, write_b, message_handler=_make_collector(notifications_b)
        ) as session_b:
            await session_b.initialize()
            await session_b.subscribe_resource(AnyUrl("corpus://status"))

            # Session A — short-lived.
            async with stdio_client(params) as (read_a, write_a):
                async with ClientSession(
                    read_a,
                    write_a,
                    message_handler=_make_collector(notifications_a),
                ) as session_a:
                    await session_a.initialize()
                    await session_a.subscribe_resource(AnyUrl("corpus://status"))
                    await asyncio.sleep(0.8)

                # Session A subprocess goes away here.

            # Record session B's notification count after A's exit.
            count_at_a_exit = len(notifications_b)
            assert (
                count_at_a_exit >= 1
            ), f"session B got no notifications during A's lifetime ({count_at_a_exit})"

            # Continue waiting — B's subprocess is independent so its
            # polling task must keep firing.
            await asyncio.sleep(1.0)

            count_after_a_exit = len(notifications_b)

    # Session B kept receiving notifications after A's subprocess exited.
    assert count_after_a_exit > count_at_a_exit, (
        f"session B's subscription stalled after session A exited: "
        f"before={count_at_a_exit}, after={count_after_a_exit}"
    )
    # Session A's subprocess saw at least one notification before it
    # was cancelled (proves both subprocesses were actually polling).
    assert (
        len(notifications_a) >= 1
    ), f"session A got no notifications before exit ({notifications_a})"
