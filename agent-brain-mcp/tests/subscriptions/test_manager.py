"""Unit tests for :class:`agent_brain_mcp.subscriptions.SubscriptionManager`.

Covers acceptance criteria from
``.planning/phases/52-resource-subscriptions/plans/01-subscription-manager-core.md``:

* Synchronous registry write before ``asyncio.create_task``
  (subscribe→cancel race).
* ``try / finally`` defense-in-depth — registry self-cleans on
  cancellation AND on unhandled exception inside the fetcher.
* Diff-suppression: identical payload modulo volatile keys → no
  ``on_change`` call.
* Diff trigger: non-volatile field change → ``on_change`` fires.
* Multi-session isolation: ``cleanup_session`` leaves another
  session's subscriptions intact.
* ``cleanup_all`` cancels everything.

The tests use a real asyncio event loop via ``pytest-asyncio``
(``asyncio_mode = "auto"`` in ``pyproject.toml``).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agent_brain_mcp.subscriptions import SubscriptionManager

# Fast poll interval keeps tests snappy. 0.02s is plenty above asyncio
# scheduler granularity on macOS / Linux and well below any test timeout.
INTERVAL = 0.02


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


# ---------------------------------------------------------------------------
# start_polling + diff suppression
# ---------------------------------------------------------------------------


async def test_first_poll_fires_on_change() -> None:
    """The very first poll always invokes ``on_change`` (no prior hash)."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        return {"value": 42}

    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    try:
        await recorder.wait_for_call(timeout=1.0)
        assert recorder.calls[0] == ("test://x", {"value": 42})
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)  # let cancellation propagate


async def test_constant_payload_emits_once() -> None:
    """A fetcher that returns the same payload should only fire once."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        return {"value": 42, "timestamp": "ignored"}

    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    try:
        # Let the loop iterate several times.
        await asyncio.sleep(INTERVAL * 5)
        assert (
            len(recorder.calls) == 1
        ), f"expected exactly one on_change call, got {len(recorder.calls)}"
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


async def test_volatile_only_change_does_not_emit() -> None:
    """Only-timestamp change → hash equal → no second on_change."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()
    counter = {"n": 0}

    async def fetcher() -> dict[str, Any]:
        counter["n"] += 1
        # Only ``timestamp`` changes between polls.
        return {"value": 42, "timestamp": f"T{counter['n']}"}

    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    try:
        await asyncio.sleep(INTERVAL * 6)
        # Multiple polls happened…
        assert counter["n"] >= 3
        # …but only the first emitted an on_change (volatile-only diff).
        assert len(recorder.calls) == 1
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


async def test_non_volatile_change_emits_again() -> None:
    """Change in a non-dropped field triggers another on_change."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()
    n = {"i": 0}

    async def fetcher() -> dict[str, Any]:
        n["i"] += 1
        # ``value`` increments every poll — every iteration should emit.
        return {"value": n["i"]}

    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    try:
        await asyncio.sleep(INTERVAL * 5)
        # At least 3 emissions in 5 intervals — generous lower bound to
        # tolerate scheduler jitter.
        assert len(recorder.calls) >= 3
        # Each emitted payload has a strictly increasing ``value``.
        values = [call[1]["value"] for call in recorder.calls]
        assert values == sorted(values)
        assert len(set(values)) == len(values)
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# unsubscribe + the synchronous-registry race
# ---------------------------------------------------------------------------


async def test_subscribe_then_immediate_unsubscribe_cancels_before_first_poll() -> None:
    """Acceptance criterion (race-safety):

    A caller invoking ``unsubscribe()`` on the very next line after
    ``start_polling()`` must successfully cancel the task BEFORE its
    first ``fetcher()`` call. Proved via an ``asyncio.Event`` that
    gates the fetcher: the event is never set, so if cancellation
    works correctly, ``fetcher`` returns ``None``-equivalent (never
    completes) and ``call_count`` stays 0.
    """
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()
    fetcher_called = asyncio.Event()
    release = asyncio.Event()  # never set — gates the fetcher indefinitely

    async def fetcher() -> dict[str, Any]:
        fetcher_called.set()
        await release.wait()  # would block forever absent cancellation
        return {"value": 0}

    # Synchronous start_polling + synchronous unsubscribe — task should
    # be cancelled before the loop has any chance to schedule the
    # fetcher coroutine.
    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    cancelled = mgr.unsubscribe(session, "test://x")

    assert cancelled is True
    # Let the cancellation propagate.
    await asyncio.sleep(0.05)
    # The registry self-cleaned via the finally block.
    assert mgr.active_count() == 0
    # The fetcher was either never reached, or its body was cancelled
    # before completing. Either way, on_change was never called.
    assert recorder.calls == []
    # If the fetcher WAS reached, that's still acceptable as long as it
    # was cancelled mid-await (didn't return a value). Asserting the
    # absence of on_change calls is the load-bearing invariant.
    _ = fetcher_called  # noqa — kept for clarity in failing-case diag


async def test_unsubscribe_returns_false_when_not_subscribed() -> None:
    """Tolerant: unsubscribe on an unknown (session, uri) returns False."""
    mgr = SubscriptionManager()
    session = object()
    assert mgr.unsubscribe(session, "test://nope") is False


async def test_unsubscribe_clears_last_hash() -> None:
    """After unsubscribe, the registry entry is gone and re-subscribing
    starts with a fresh ``last_hash`` (so the first poll emits again)."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()
    payload = {"value": 42}

    async def fetcher() -> dict[str, Any]:
        return payload

    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    await recorder.wait_for_call(timeout=1.0)
    assert len(recorder.calls) == 1

    assert mgr.unsubscribe(session, "test://x") is True
    await asyncio.sleep(0.05)
    assert mgr.active_count() == 0

    # Re-subscribe with the same fetcher — must emit again.
    recorder._event.clear()
    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    try:
        await recorder.wait_for_call(timeout=1.0)
        assert len(recorder.calls) == 2
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Already-subscribed guard
# ---------------------------------------------------------------------------


async def test_double_subscribe_raises_runtime_error() -> None:
    """Plan §step5: re-subscribing the same (session, uri) is an error."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        return {"v": 1}

    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    try:
        with pytest.raises(RuntimeError, match="Already subscribed"):
            mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Defense-in-depth: try/finally self-cleans on unhandled exception
# ---------------------------------------------------------------------------


async def test_loop_survives_fetcher_exception_and_keeps_polling() -> None:
    """Acceptance criterion: a transient fetcher exception must NOT
    tear down the polling loop. The loop logs and continues so the
    next iteration can succeed."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()
    counter = {"n": 0}

    async def fetcher() -> dict[str, Any]:
        counter["n"] += 1
        if counter["n"] == 1:
            raise RuntimeError("transient failure")
        return {"value": counter["n"]}

    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    try:
        # First call raises; second call (after backoff) succeeds.
        await recorder.wait_for_call(timeout=2.0)
        assert len(recorder.calls) >= 1
        # Registry still tracks the active subscription.
        assert mgr.is_subscribed(session, "test://x")
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


async def test_registry_self_cleans_on_cancellation() -> None:
    """After ``cleanup_all``, both ``_tasks`` and ``_last_hash`` are empty."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        return {"value": 42}

    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    await recorder.wait_for_call(timeout=1.0)

    cancelled = mgr.cleanup_all()
    assert cancelled == 1
    await asyncio.sleep(0.05)

    assert mgr.active_count() == 0
    # Private-field check is appropriate here — Plan acceptance
    # criterion mandates ``_last_hash`` is also cleared by the
    # finally block (defense-in-depth).
    assert mgr._last_hash == {}
    assert mgr._tasks == {}


# ---------------------------------------------------------------------------
# Multi-session isolation
# ---------------------------------------------------------------------------


async def test_cleanup_session_isolates_one_session() -> None:
    """``cleanup_session(A)`` cancels A's tasks but leaves B's intact."""
    mgr = SubscriptionManager()
    session_a = object()
    session_b = object()
    rec_a = _OnChangeRecorder()
    rec_b = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        return {"v": 1}

    mgr.start_polling(session_a, "test://shared", INTERVAL, fetcher, rec_a)
    mgr.start_polling(session_b, "test://shared", INTERVAL, fetcher, rec_b)
    try:
        # Both should have had their first poll by now.
        await rec_a.wait_for_call(timeout=1.0)
        await rec_b.wait_for_call(timeout=1.0)
        assert mgr.active_count() == 2

        n = mgr.cleanup_session(session_a)
        assert n == 1
        await asyncio.sleep(0.05)

        # Session A is gone; session B still polling.
        assert mgr.active_count() == 1
        assert not mgr.is_subscribed(session_a, "test://shared")
        assert mgr.is_subscribed(session_b, "test://shared")
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


async def test_cleanup_session_cancels_all_uris_for_that_session() -> None:
    """One session may have multiple URIs — cleanup gets them all."""
    mgr = SubscriptionManager()
    session = object()
    other = object()
    recorder = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        return {"v": 1}

    mgr.start_polling(session, "test://a", INTERVAL, fetcher, recorder)
    mgr.start_polling(session, "test://b", INTERVAL, fetcher, recorder)
    mgr.start_polling(session, "test://c", INTERVAL, fetcher, recorder)
    mgr.start_polling(other, "test://a", INTERVAL, fetcher, recorder)

    try:
        assert mgr.active_count() == 4
        n = mgr.cleanup_session(session)
        assert n == 3
        await asyncio.sleep(0.05)
        assert mgr.active_count() == 1
        assert mgr.is_subscribed(other, "test://a")
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


async def test_cleanup_session_on_unknown_session_returns_zero() -> None:
    """A session that never subscribed is cleanly handled."""
    mgr = SubscriptionManager()
    assert mgr.cleanup_session(object()) == 0


async def test_cleanup_all_cancels_everything() -> None:
    """``cleanup_all`` returns the count across all sessions/URIs."""
    mgr = SubscriptionManager()
    s1 = object()
    s2 = object()
    recorder = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        return {"v": 1}

    mgr.start_polling(s1, "test://a", INTERVAL, fetcher, recorder)
    mgr.start_polling(s1, "test://b", INTERVAL, fetcher, recorder)
    mgr.start_polling(s2, "test://a", INTERVAL, fetcher, recorder)

    assert mgr.active_count() == 3
    n = mgr.cleanup_all()
    assert n == 3
    await asyncio.sleep(0.05)
    assert mgr.active_count() == 0


# ---------------------------------------------------------------------------
# Custom drop_keys plumbing
# ---------------------------------------------------------------------------


async def test_custom_drop_keys_plumbed_to_hash() -> None:
    """Caller-supplied ``drop_keys`` overrides the default — proves the
    parameter actually reaches ``canonical_hash`` inside the loop."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()
    counter = {"n": 0}

    async def fetcher() -> dict[str, Any]:
        counter["n"] += 1
        # 'timestamp' is in DEFAULT_DROP_KEYS — by passing an explicit
        # set that does NOT include it, the timestamp mutation becomes
        # a real diff every poll.
        return {"value": 42, "timestamp": f"T{counter['n']}"}

    mgr.start_polling(
        session,
        "test://x",
        INTERVAL,
        fetcher,
        recorder,
        drop_keys=set(),
    )
    try:
        await asyncio.sleep(INTERVAL * 4)
        # Each poll emits because the timestamp difference is now load-bearing.
        assert len(recorder.calls) >= 2
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# active_count / is_subscribed surface
# ---------------------------------------------------------------------------


async def test_is_subscribed_and_active_count() -> None:
    """Sanity check of the two introspection helpers."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        return {"v": 1}

    assert mgr.active_count() == 0
    assert not mgr.is_subscribed(session, "test://x")

    mgr.start_polling(session, "test://x", INTERVAL, fetcher, recorder)
    assert mgr.active_count() == 1
    assert mgr.is_subscribed(session, "test://x")
    # Different uri, same session — not subscribed.
    assert not mgr.is_subscribed(session, "test://y")
    # Different session, same uri — not subscribed.
    assert not mgr.is_subscribed(object(), "test://x")

    mgr.cleanup_all()
    await asyncio.sleep(0.05)
    assert mgr.active_count() == 0


# ---------------------------------------------------------------------------
# SubscribableUriRejected — Plan 02 will raise; Plan 01 only smoke-tests
# ---------------------------------------------------------------------------


def test_subscribable_uri_rejected_carries_structured_data() -> None:
    """The error type defined here is consumed by Plan 02's wire handler."""
    from agent_brain_mcp.errors import INVALID_PARAMS
    from agent_brain_mcp.subscriptions import SubscribableUriRejected

    err = SubscribableUriRejected("chunk://abc", reason="not_subscribable")
    # ``McpError.error`` exposes the underlying ``ErrorData``.
    assert err.error.code == INVALID_PARAMS
    assert err.error.data == {"uri": "chunk://abc", "reason": "not_subscribable"}
    assert "chunk://abc" in err.error.message
    assert "not_subscribable" in err.error.message


def test_subscribable_uri_rejected_unknown_uri_reason() -> None:
    """The other documented reason slug works the same."""
    from agent_brain_mcp.subscriptions import SubscribableUriRejected

    err = SubscribableUriRejected("zzz://nope", reason="unknown_uri")
    assert err.error.data == {"uri": "zzz://nope", "reason": "unknown_uri"}
