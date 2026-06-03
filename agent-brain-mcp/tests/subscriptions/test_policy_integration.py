"""Integration tests — policies driving SubscriptionManager.start_polling.

Each test wires a Plan 03 policy into a real :class:`SubscriptionManager`
(Plan 01) and asserts the end-to-end contract:

* :class:`JobPolicy` — polls until job reports a terminal status; emits
  one final ``on_change`` with the terminal payload; manager registry
  self-cleans (``active_count()`` drops to zero, ``is_subscribed``
  flips to False).
* :class:`CorpusStatusPolicy` — diff-suppression suppresses constant
  payloads after the first poll; a real change re-fires.
* :class:`CorpusFoldersPolicy` — settings-driven cadence + drop_keys
  honor ``last_indexed`` as a real signal.

These tests prove the contract between Plan 03's policies and Plan 01's
polling loop holds without going through Plan 02's MCP wire — a faster
inner-loop check than the full e2e suite.

Time hygiene: the manager's polling loop calls ``asyncio.sleep`` after
each iteration. We pass an artificially small ``interval_s`` (0.02s for
job / status, 0.05s for folders) so tests finish in well under a
second. ``asyncio.wait_for`` guards every wait so a misbehaving loop
can't hang CI.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from agent_brain_mcp.subscriptions import (
    CorpusFoldersPolicy,
    CorpusStatusPolicy,
    JobPolicy,
    SubscriptionManager,
    SubscriptionTerminated,
)


class _OnChangeRecorder:
    """Async collector mirroring the helper in ``test_manager.py``."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._event = asyncio.Event()

    async def __call__(self, uri: str, payload: dict[str, Any]) -> None:
        self.calls.append((uri, payload))
        self._event.set()

    async def wait_for_call(self, timeout: float = 1.5) -> None:
        await asyncio.wait_for(self._event.wait(), timeout)
        self._event.clear()


class _FakeApiClient:
    """Minimal fake of :class:`ApiClient` whose responses tests mutate."""

    def __init__(self) -> None:
        self.get_job_payload: dict[str, Any] = {"id": "j1", "status": "running"}
        self.server_status_payload: dict[str, Any] = {
            "total_chunks": 0,
            "indexing_in_progress": False,
        }
        self.list_folders_payload: dict[str, Any] = {"folders": [], "total": 0}
        self.get_job_calls = 0
        self.server_status_calls = 0
        self.list_folders_calls = 0

    def get_job(self, job_id: str) -> dict[str, Any]:
        self.get_job_calls += 1
        # Return a fresh copy so test mutations to ``get_job_payload`` are
        # picked up on the NEXT call, not retroactively.
        return dict(self.get_job_payload)

    def server_status(self) -> dict[str, Any]:
        self.server_status_calls += 1
        return dict(self.server_status_payload)

    def list_folders(self) -> dict[str, Any]:
        self.list_folders_calls += 1
        return dict(self.list_folders_payload)


# ---------------------------------------------------------------------------
# Manager-level SubscriptionTerminated handling
# (these don't strictly belong to "policy integration" but they pin the
#  Plan 01 ↔ Plan 03 contract: the manager handles the sentinel exactly
#  as Plan 03 expects.)
# ---------------------------------------------------------------------------


async def test_manager_catches_subscription_terminated_and_emits_final() -> None:
    """Sentinel with final_payload → manager fires one last on_change."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        raise SubscriptionTerminated({"final": True, "status": "completed"})

    mgr.start_polling(session, "test://terminal", 0.02, fetcher, recorder)
    # Wait until the loop runs the terminal branch and exits.
    await recorder.wait_for_call(timeout=1.0)
    await asyncio.sleep(0.05)  # let the loop fully exit + finally fire
    assert recorder.calls == [
        ("test://terminal", {"final": True, "status": "completed"})
    ]
    assert mgr.active_count() == 0
    assert not mgr.is_subscribed(session, "test://terminal")


async def test_manager_handles_subscription_terminated_without_payload() -> None:
    """Sentinel with no final_payload → no terminal emission, clean exit."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    async def fetcher() -> dict[str, Any]:
        raise SubscriptionTerminated()  # no payload

    mgr.start_polling(session, "test://terminal", 0.02, fetcher, recorder)
    await asyncio.sleep(0.1)  # give the loop time to run + exit
    assert recorder.calls == []  # no terminal emission
    assert mgr.active_count() == 0


async def test_manager_terminates_after_running_polls() -> None:
    """Sentinel raised AFTER N successful polls → those N polls emit,
    plus one final terminal emission, then exit."""
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    calls = {"n": 0}

    async def fetcher() -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] >= 3:
            raise SubscriptionTerminated(
                {"id": "j1", "status": "completed", "iter": calls["n"]}
            )
        return {"id": "j1", "status": "running", "iter": calls["n"]}

    mgr.start_polling(session, "test://job", 0.02, fetcher, recorder)
    # Wait for the loop to reach the terminal branch.
    for _ in range(50):
        await asyncio.sleep(0.02)
        if not mgr.is_subscribed(session, "test://job"):
            break
    assert not mgr.is_subscribed(session, "test://job")
    # We expect: 1 emission for the first running payload (iter=1), then
    # the diff-suppressor saw iter=2 was a different payload (iter
    # changed) → 2nd emission, then terminal → 3rd emission. Total ≥ 3.
    assert len(recorder.calls) >= 2  # at minimum: 1 running + 1 terminal
    last_uri, last_payload = recorder.calls[-1]
    assert last_uri == "test://job"
    assert last_payload["status"] == "completed"


# ---------------------------------------------------------------------------
# JobPolicy end-to-end
# ---------------------------------------------------------------------------


async def test_job_policy_running_to_completed_lifecycle() -> None:
    """Job starts running, flips to completed; manager fires running +
    final, then registry self-cleans."""
    api = _FakeApiClient()
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    api.get_job_payload = {"id": "j1", "status": "running", "progress": 0.1}
    policy = JobPolicy()
    fetcher = policy.build_fetcher(api, "job://j1")  # type: ignore[arg-type]

    # Override the policy's 1.0s cadence for test speed.
    mgr.start_polling(
        session=session,
        uri="job://j1",
        interval_s=0.02,
        fetcher=fetcher,
        on_change=recorder,
        drop_keys=policy.drop_keys,
    )

    # First poll fires on_change with running payload.
    await recorder.wait_for_call(timeout=1.0)
    assert recorder.calls[-1][1]["status"] == "running"
    initial_call_count = len(recorder.calls)

    # Flip the backend to terminal.
    api.get_job_payload = {"id": "j1", "status": "completed", "result": "ok"}

    # Wait for the loop to pick up the new payload and terminate.
    for _ in range(50):
        await asyncio.sleep(0.02)
        if not mgr.is_subscribed(session, "job://j1"):
            break
    assert not mgr.is_subscribed(
        session, "job://j1"
    ), "expected polling task to self-terminate after job completion"

    # The recorder should have at least one additional call (the
    # terminal emission), with status=completed.
    assert len(recorder.calls) > initial_call_count
    last_payload = recorder.calls[-1][1]
    assert last_payload["status"] == "completed"
    assert mgr.active_count() == 0


async def test_job_policy_invalid_job_uri_terminates_fast() -> None:
    """``job://`` (no id) emits one ``invalid`` notification then exits."""
    api = _FakeApiClient()
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    fetcher = JobPolicy().build_fetcher(api, "job://")  # type: ignore[arg-type]
    mgr.start_polling(session, "job://", 0.02, fetcher, recorder)

    # Wait for the terminal emission.
    for _ in range(50):
        await asyncio.sleep(0.02)
        if not mgr.is_subscribed(session, "job://"):
            break
    assert not mgr.is_subscribed(session, "job://")
    assert len(recorder.calls) == 1
    assert recorder.calls[0][1] == {
        "status": "invalid",
        "uri": "job://",
        "reason": "missing_job_id",
    }
    # The API client must NOT have been touched.
    assert api.get_job_calls == 0


# ---------------------------------------------------------------------------
# CorpusStatusPolicy end-to-end
# ---------------------------------------------------------------------------


async def test_corpus_status_policy_constant_payload_emits_once() -> None:
    """Two polls of an unchanged payload → exactly one on_change call.

    The CorpusStatusPolicy drop_keys strip the timestamp/request_id
    churn so the SHA-256 stays constant across polls.
    """
    api = _FakeApiClient()
    api.server_status_payload = {
        "total_chunks": 42,
        "indexing_in_progress": False,
        "timestamp": "2026-06-03T00:00:00Z",
        "request_id": "req-1",
    }
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    policy = CorpusStatusPolicy()
    fetcher = policy.build_fetcher(api, "corpus://status")  # type: ignore[arg-type]
    mgr.start_polling(
        session=session,
        uri="corpus://status",
        interval_s=0.02,
        fetcher=fetcher,
        on_change=recorder,
        drop_keys=policy.drop_keys,
    )
    try:
        await recorder.wait_for_call(timeout=1.0)
        # Let the loop poll several more times — should NOT emit again
        # (only timestamp+request_id churn between polls).
        await asyncio.sleep(0.15)

        # Mutate ONLY the volatile fields (timestamp + request_id) — the
        # canonical hash must stay the same so no new on_change fires.
        api.server_status_payload = {
            "total_chunks": 42,
            "indexing_in_progress": False,
            "timestamp": "2026-06-03T00:00:30Z",  # changed
            "request_id": "req-2",  # changed
        }
        await asyncio.sleep(0.15)

        assert (
            len(recorder.calls) == 1
        ), f"expected exactly 1 emission, got {len(recorder.calls)}"
        assert api.server_status_calls > 2, (
            "manager should have polled multiple times even though only "
            "the first one fired on_change"
        )
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


async def test_corpus_status_policy_real_change_re_emits() -> None:
    """A change to ``total_chunks`` re-fires on_change."""
    api = _FakeApiClient()
    api.server_status_payload = {
        "total_chunks": 0,
        "indexing_in_progress": False,
        "timestamp": "t0",
    }
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    policy = CorpusStatusPolicy()
    fetcher = policy.build_fetcher(api, "corpus://status")  # type: ignore[arg-type]
    mgr.start_polling(
        session=session,
        uri="corpus://status",
        interval_s=0.02,
        fetcher=fetcher,
        on_change=recorder,
        drop_keys=policy.drop_keys,
    )
    try:
        await recorder.wait_for_call(timeout=1.0)
        assert len(recorder.calls) == 1
        assert recorder.calls[-1][1]["total_chunks"] == 0

        # Real change.
        api.server_status_payload = {
            "total_chunks": 99,
            "indexing_in_progress": True,
            "timestamp": "t1",
        }
        await recorder.wait_for_call(timeout=1.0)
        assert len(recorder.calls) >= 2
        assert recorder.calls[-1][1]["total_chunks"] == 99
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# CorpusFoldersPolicy end-to-end
# ---------------------------------------------------------------------------


async def test_corpus_folders_policy_constant_payload_emits_once() -> None:
    """Constant folders payload across multiple polls → one on_change."""
    api = _FakeApiClient()
    api.list_folders_payload = {
        "folders": [
            {"path": "/tmp/x", "chunk_count": 5, "last_indexed": "2026-06-01"},
        ],
        "total": 1,
    }
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    # Inject a fast cadence via constructor — Plan 03's policy supports this.
    policy = CorpusFoldersPolicy(interval_s=0.05)
    fetcher = policy.build_fetcher(api, "corpus://folders")  # type: ignore[arg-type]
    mgr.start_polling(
        session=session,
        uri="corpus://folders",
        interval_s=policy.interval_s,
        fetcher=fetcher,
        on_change=recorder,
        drop_keys=policy.drop_keys,
    )
    try:
        await recorder.wait_for_call(timeout=1.0)
        await asyncio.sleep(0.2)  # 4× the interval — plenty of polls
        assert len(recorder.calls) == 1
        assert api.list_folders_calls >= 3
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


async def test_corpus_folders_policy_last_indexed_change_re_emits() -> None:
    """A ``last_indexed`` change is a REAL signal and must fire on_change."""
    api = _FakeApiClient()
    api.list_folders_payload = {
        "folders": [
            {"path": "/tmp/x", "chunk_count": 5, "last_indexed": "2026-06-01"},
        ],
        "total": 1,
    }
    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()

    policy = CorpusFoldersPolicy(interval_s=0.05)
    fetcher = policy.build_fetcher(api, "corpus://folders")  # type: ignore[arg-type]
    mgr.start_polling(
        session=session,
        uri="corpus://folders",
        interval_s=policy.interval_s,
        fetcher=fetcher,
        on_change=recorder,
        drop_keys=policy.drop_keys,
    )
    try:
        await recorder.wait_for_call(timeout=1.0)
        assert len(recorder.calls) == 1

        # Update last_indexed → the canonical hash must change.
        api.list_folders_payload = {
            "folders": [
                {"path": "/tmp/x", "chunk_count": 5, "last_indexed": "2026-06-03"},
            ],
            "total": 1,
        }
        await recorder.wait_for_call(timeout=1.0)
        assert len(recorder.calls) >= 2
        assert recorder.calls[-1][1]["folders"][0]["last_indexed"] == "2026-06-03"
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)


async def test_corpus_folders_policy_respects_custom_interval() -> None:
    """``interval_s`` injection actually slows/speeds the polling cadence.

    With a 0.05s cadence and a 0.2s observation window we expect ≥3
    polls; with a 0.5s cadence we expect ≤1 poll in the same window.
    """
    # Fast: many polls in 0.2s
    api_fast = _FakeApiClient()
    mgr_fast = SubscriptionManager()
    session_fast = object()
    recorder_fast = _OnChangeRecorder()
    policy_fast = CorpusFoldersPolicy(interval_s=0.05)
    fetcher_fast = policy_fast.build_fetcher(api_fast, "corpus://folders")  # type: ignore[arg-type]
    mgr_fast.start_polling(
        session=session_fast,
        uri="corpus://folders",
        interval_s=policy_fast.interval_s,
        fetcher=fetcher_fast,
        on_change=recorder_fast,
        drop_keys=policy_fast.drop_keys,
    )

    # Slow: 1 poll in 0.2s window
    api_slow = _FakeApiClient()
    mgr_slow = SubscriptionManager()
    session_slow = object()
    recorder_slow = _OnChangeRecorder()
    policy_slow = CorpusFoldersPolicy(interval_s=0.5)
    fetcher_slow = policy_slow.build_fetcher(api_slow, "corpus://folders")  # type: ignore[arg-type]
    mgr_slow.start_polling(
        session=session_slow,
        uri="corpus://folders",
        interval_s=policy_slow.interval_s,
        fetcher=fetcher_slow,
        on_change=recorder_slow,
        drop_keys=policy_slow.drop_keys,
    )

    try:
        await asyncio.sleep(0.25)
        assert api_fast.list_folders_calls >= 3
        assert api_slow.list_folders_calls <= 2
    finally:
        mgr_fast.cleanup_all()
        mgr_slow.cleanup_all()
        await asyncio.sleep(0.05)


# ---------------------------------------------------------------------------
# Cross-policy: resolve_policy + manager wired end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri,expected_status_field",
    [
        ("corpus://status", "total_chunks"),
        ("corpus://folders", "total"),
    ],
)
async def test_singleton_policies_drive_manager(
    uri: str, expected_status_field: str
) -> None:
    """Both singleton policies (``corpus://status`` / ``corpus://folders``)
    drive the manager to a first-poll on_change emission."""
    from agent_brain_mcp.subscriptions import resolve_policy

    api = _FakeApiClient()
    api.server_status_payload = {"total_chunks": 7, "timestamp": "t0"}
    api.list_folders_payload = {"folders": [], "total": 0}

    policy = resolve_policy(uri)
    assert policy is not None
    fetcher = policy.build_fetcher(api, uri)  # type: ignore[arg-type]

    mgr = SubscriptionManager()
    session = object()
    recorder = _OnChangeRecorder()
    mgr.start_polling(
        session=session,
        uri=uri,
        interval_s=0.02,  # override real cadence for speed
        fetcher=fetcher,
        on_change=recorder,
        drop_keys=policy.drop_keys,
    )
    try:
        await recorder.wait_for_call(timeout=1.0)
        assert len(recorder.calls) == 1
        # Payload was something — the expected field exists.
        assert expected_status_field in recorder.calls[0][1]
    finally:
        mgr.cleanup_all()
        await asyncio.sleep(0.05)
