"""Unit tests for :meth:`SubscriptionManager.snapshot` (HOUSE-01).

Covers acceptance criteria from
``.planning/phases/64-graphrag-stability-subscriptions-debug-endpoint/64-04-PLAN.md``:

* Test 1: snapshot() after start_polling returns active_count==1 and a
  subscriptions list with correct uri, cadence_s, non-null started_at,
  and last_notified_at None.
* Test 2: the entry's session_id equals _truncate_session_id(session)
  (8-char) — NOT the full id(session).
* Test 3: after on_change fires, last_notified_at is a non-null ISO-8601
  timestamp.
* Test 4: snapshot() is read-only — does not mutate _tasks/_last_hash,
  active_count unchanged before/after.
* Test 5: after unsubscribe/cleanup, snapshot() no longer contains that
  entry and active_count reflects the drop.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from agent_brain_mcp.subscriptions import SubscriptionManager

# Fast poll interval keeps tests snappy.
INTERVAL = 0.02

ISO_8601_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?\+00:00$")


class _OnChangeRecorder:
    """Async collector for ``on_change`` callback invocations."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._event = asyncio.Event()

    async def __call__(self, uri: str, payload: dict[str, Any]) -> None:
        self.calls.append((uri, payload))
        self._event.set()

    async def wait_for_call(self, timeout: float = 1.0) -> None:
        """Block until ``on_change`` is called at least once, or time out."""
        await asyncio.wait_for(self._event.wait(), timeout)
        self._event.clear()


async def _noop_fetcher() -> dict[str, Any]:
    """Fetcher that returns a constant payload (triggers first on_change)."""
    return {"value": 1}


# ---------------------------------------------------------------------------
# Test 1: snapshot() after start_polling has correct shape + metadata
# ---------------------------------------------------------------------------


async def test_snapshot_after_start_polling_shape() -> None:
    """After start_polling, snapshot() returns active_count==1 and a
    subscriptions list with the expected uri, cadence_s, non-null
    started_at, and last_notified_at None (no notification yet)."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def blocking_fetcher() -> dict[str, Any]:
        # Block forever so on_change never fires — lets us inspect the
        # initial snapshot state with last_notified_at still None.
        await asyncio.sleep(9999)
        return {"value": 1}  # pragma: no cover

    mgr.start_polling(session, "job://abc", INTERVAL, blocking_fetcher, recorder)
    try:
        # Give the task a chance to schedule but not complete any poll.
        await asyncio.sleep(0.01)

        snap = mgr.snapshot()

        assert snap["active_count"] == 1
        assert len(snap["subscriptions"]) == 1
        entry = snap["subscriptions"][0]

        assert entry["uri"] == "job://abc"
        assert entry["cadence_s"] == INTERVAL
        assert entry["started_at"] is not None
        # Verify ISO-8601 UTC format.
        assert ISO_8601_RE.match(
            entry["started_at"]
        ), f"started_at is not ISO-8601 UTC: {entry['started_at']!r}"
        # No notification has fired yet.
        assert entry["last_notified_at"] is None
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Test 2: session_id is truncated (8 chars)
# ---------------------------------------------------------------------------


async def test_snapshot_session_id_is_truncated() -> None:
    """The session_id in snapshot() equals _truncate_session_id(session) —
    8 hex chars, NOT the full id(session) integer."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def blocking_fetcher() -> dict[str, Any]:
        await asyncio.sleep(9999)
        return {"value": 1}  # pragma: no cover

    mgr.start_polling(session, "job://abc", INTERVAL, blocking_fetcher, recorder)
    try:
        await asyncio.sleep(0.01)
        snap = mgr.snapshot()
        entry = snap["subscriptions"][0]

        expected = SubscriptionManager._truncate_session_id(session)
        assert (
            entry["session_id"] == expected
        ), f"expected {expected!r}, got {entry['session_id']!r}"
        # Must be at most 8 characters (the truncation).
        assert len(entry["session_id"]) <= 8
        # Full id should NOT be exposed.
        full_id = f"{id(session):x}"
        if len(full_id) > 8:
            assert entry["session_id"] != full_id
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Test 3: last_notified_at is stamped after on_change fires
# ---------------------------------------------------------------------------


async def test_snapshot_last_notified_at_stamped_after_on_change() -> None:
    """After on_change fires for a subscription, last_notified_at is a
    non-null ISO-8601 UTC timestamp in the snapshot."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    mgr.start_polling(session, "job://abc", INTERVAL, _noop_fetcher, recorder)
    try:
        # Wait for at least one on_change call.
        await recorder.wait_for_call(timeout=1.0)

        snap = mgr.snapshot()
        assert snap["active_count"] == 1
        entry = snap["subscriptions"][0]

        assert (
            entry["last_notified_at"] is not None
        ), "last_notified_at should be set after on_change fired"
        assert ISO_8601_RE.match(
            entry["last_notified_at"]
        ), f"last_notified_at is not ISO-8601 UTC: {entry['last_notified_at']!r}"
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Test 4: snapshot() is read-only — does not mutate state
# ---------------------------------------------------------------------------


async def test_snapshot_is_read_only() -> None:
    """Calling snapshot() does not mutate _tasks or _last_hash, and
    active_count is unchanged before/after."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def blocking_fetcher() -> dict[str, Any]:
        await asyncio.sleep(9999)
        return {"value": 1}  # pragma: no cover

    mgr.start_polling(session, "job://abc", INTERVAL, blocking_fetcher, recorder)
    try:
        await asyncio.sleep(0.01)

        count_before = mgr.active_count()
        tasks_before = dict(mgr._tasks)
        hash_before = dict(mgr._last_hash)

        _ = mgr.snapshot()

        assert mgr.active_count() == count_before
        assert mgr._tasks == tasks_before
        assert mgr._last_hash == hash_before
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Test 5: snapshot() reflects teardown (unsubscribe / cleanup)
# ---------------------------------------------------------------------------


async def test_snapshot_after_unsubscribe_removes_entry() -> None:
    """After unsubscribe, snapshot()'s subscriptions list no longer
    contains that entry and active_count drops to 0."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def blocking_fetcher() -> dict[str, Any]:
        await asyncio.sleep(9999)
        return {"value": 1}  # pragma: no cover

    mgr.start_polling(session, "job://abc", INTERVAL, blocking_fetcher, recorder)
    await asyncio.sleep(0.01)
    assert mgr.snapshot()["active_count"] == 1

    mgr.unsubscribe(session, "job://abc")
    # Allow cancellation to propagate.
    await asyncio.sleep(0.05)

    snap = mgr.snapshot()
    assert snap["active_count"] == 0
    assert snap["subscriptions"] == []


async def test_snapshot_after_cleanup_all_removes_all_entries() -> None:
    """After cleanup_all, snapshot() shows empty subscriptions and
    active_count == 0."""
    mgr = SubscriptionManager()
    s1 = object()
    s2 = object()
    recorder = _OnChangeRecorder()

    async def blocking_fetcher() -> dict[str, Any]:
        await asyncio.sleep(9999)
        return {"value": 1}  # pragma: no cover

    mgr.start_polling(s1, "job://a", INTERVAL, blocking_fetcher, recorder)
    mgr.start_polling(s2, "job://b", INTERVAL, blocking_fetcher, recorder)
    await asyncio.sleep(0.01)
    assert mgr.snapshot()["active_count"] == 2

    mgr.cleanup_all()
    await asyncio.sleep(0.05)

    snap = mgr.snapshot()
    assert snap["active_count"] == 0
    assert snap["subscriptions"] == []
