"""Unit tests for the three concrete subscription policies.

Covers acceptance criteria from
``.planning/phases/52-resource-subscriptions/plans/03-per-uri-policies.md``:

* :class:`JobPolicy` URI matching + terminal-status exit.
* :class:`CorpusStatusPolicy` 30s cadence + ``request_id`` drop.
* :class:`CorpusFoldersPolicy` configurable cadence + ``last_polled`` drop
  (``last_indexed`` PRESERVED — it's a real change signal).
* :func:`resolve_policy` exact-then-scheme dispatch across the three
  populated registry entries.

These tests use a fake :class:`ApiClient` (``Any``-typed in mypy) so
the fetcher factories can be exercised without standing up the real
HTTP stack. Cross-policy integration tests live in
``test_policy_integration.py`` — they exercise the full polling loop
through :class:`SubscriptionManager.start_polling`.
"""

from __future__ import annotations

from typing import Any

import pytest

from agent_brain_mcp.subscriptions import (
    DEFAULT_DROP_KEYS,
    SUBSCRIPTION_POLICIES,
    CorpusFoldersPolicy,
    CorpusStatusPolicy,
    JobPolicy,
    SubscriptionPolicy,
    SubscriptionTerminated,
    canonical_hash,
    resolve_policy,
)
from agent_brain_mcp.subscriptions.policies import TERMINAL_JOB_STATUSES


class _FakeApiClient:
    """Hand-rolled stand-in for :class:`ApiClient`.

    Tests assign canned responses to the three methods Plan 03 polls.
    Keeping this hand-rolled (rather than ``unittest.mock.MagicMock``)
    keeps the call-shape explicit and forces every test to declare what
    the fake returns.
    """

    def __init__(self) -> None:
        self.get_job_payload: dict[str, Any] = {"id": "abc", "status": "running"}
        self.server_status_payload: dict[str, Any] = {
            "total_chunks": 0,
            "indexing_in_progress": False,
            "timestamp": "2026-06-03T00:00:00Z",
        }
        self.list_folders_payload: dict[str, Any] = {
            "folders": [],
            "total": 0,
        }
        self.get_job_calls: list[str] = []
        self.server_status_calls: int = 0
        self.list_folders_calls: int = 0

    def get_job(self, job_id: str) -> dict[str, Any]:
        self.get_job_calls.append(job_id)
        return self.get_job_payload

    def server_status(self) -> dict[str, Any]:
        self.server_status_calls += 1
        return self.server_status_payload

    def list_folders(self) -> dict[str, Any]:
        self.list_folders_calls += 1
        return self.list_folders_payload


# ---------------------------------------------------------------------------
# JobPolicy
# ---------------------------------------------------------------------------


def test_job_policy_attributes() -> None:
    """JobPolicy ships the CONTEXT-pinned defaults: scheme-key + 1s + default drops."""
    p = JobPolicy()
    assert p.uri_pattern == "job://"
    assert p.interval_s == 1.0
    assert p.drop_keys is None  # → falls back to DEFAULT_DROP_KEYS


def test_job_policy_satisfies_protocol() -> None:
    """JobPolicy must structurally match :class:`SubscriptionPolicy`."""
    assert isinstance(JobPolicy(), SubscriptionPolicy)


async def test_job_policy_fetcher_returns_running_payload() -> None:
    """When job status is non-terminal, fetcher returns the payload verbatim."""
    api = _FakeApiClient()
    api.get_job_payload = {"id": "abc-123", "status": "running", "progress": 0.5}
    fetcher = JobPolicy().build_fetcher(api, "job://abc-123")  # type: ignore[arg-type]
    payload = await fetcher()
    assert payload == {"id": "abc-123", "status": "running", "progress": 0.5}
    assert api.get_job_calls == ["abc-123"]


@pytest.mark.parametrize("terminal_status", ["completed", "failed", "cancelled"])
async def test_job_policy_fetcher_terminates_on_terminal_status(
    terminal_status: str,
) -> None:
    """Every terminal status raises SubscriptionTerminated carrying the payload.

    Covers all three TERMINAL_JOB_STATUSES — pinned by parametrize so a
    future addition to the frozenset is caught by a missing case.
    """
    api = _FakeApiClient()
    api.get_job_payload = {"id": "abc", "status": terminal_status, "result": "done"}
    fetcher = JobPolicy().build_fetcher(api, "job://abc")  # type: ignore[arg-type]
    with pytest.raises(SubscriptionTerminated) as exc_info:
        await fetcher()
    assert exc_info.value.final_payload == {
        "id": "abc",
        "status": terminal_status,
        "result": "done",
    }


def test_job_policy_terminal_statuses_pinned() -> None:
    """TERMINAL_JOB_STATUSES is the CONTEXT-mandated triple — pin it."""
    assert TERMINAL_JOB_STATUSES == frozenset({"completed", "failed", "cancelled"})


async def test_job_policy_empty_id_terminates_immediately() -> None:
    """``job://`` with no id raises SubscriptionTerminated on first call.

    Plan 02's ``_is_known_uri`` accepts ``job://`` (scheme is known) so
    we surface the empty-id condition in the fetcher.
    """
    api = _FakeApiClient()
    fetcher = JobPolicy().build_fetcher(api, "job://")  # type: ignore[arg-type]
    with pytest.raises(SubscriptionTerminated) as exc_info:
        await fetcher()
    assert exc_info.value.final_payload == {
        "status": "invalid",
        "uri": "job://",
        "reason": "missing_job_id",
    }
    # ApiClient must NOT have been called for a missing-id URI.
    assert api.get_job_calls == []


async def test_job_policy_strips_trailing_slash_defensively() -> None:
    """``job://abc/`` should be treated identically to ``job://abc``.

    Plan 02 normalizes URIs before dispatch, but the fetcher strips
    trailing slashes too so a future caller path that bypasses
    normalization still produces correct behavior.
    """
    api = _FakeApiClient()
    api.get_job_payload = {"id": "abc", "status": "running"}
    fetcher = JobPolicy().build_fetcher(api, "job://abc/")  # type: ignore[arg-type]
    await fetcher()
    assert api.get_job_calls == ["abc"]


async def test_job_policy_handles_uuid_style_ids() -> None:
    """UUID-with-dashes job ids round-trip through the fetcher."""
    api = _FakeApiClient()
    uuid = "12345678-1234-1234-1234-1234567890ab"
    api.get_job_payload = {"id": uuid, "status": "queued"}
    fetcher = JobPolicy().build_fetcher(api, f"job://{uuid}")  # type: ignore[arg-type]
    payload = await fetcher()
    assert payload["status"] == "queued"
    assert api.get_job_calls == [uuid]


# ---------------------------------------------------------------------------
# CorpusStatusPolicy
# ---------------------------------------------------------------------------


def test_corpus_status_policy_attributes() -> None:
    """CorpusStatusPolicy ships the 30s cadence + request_id drop."""
    p = CorpusStatusPolicy()
    assert p.uri_pattern == "corpus://status"
    assert p.interval_s == 30.0
    assert p.drop_keys is not None
    assert "request_id" in p.drop_keys
    # Plus the base DEFAULT_DROP_KEYS — all 5 keys must be present.
    assert DEFAULT_DROP_KEYS.issubset(p.drop_keys)


def test_corpus_status_policy_satisfies_protocol() -> None:
    assert isinstance(CorpusStatusPolicy(), SubscriptionPolicy)


async def test_corpus_status_fetcher_calls_server_status() -> None:
    """Fetcher must dispatch to :meth:`ApiClient.server_status`."""
    api = _FakeApiClient()
    api.server_status_payload = {
        "total_chunks": 42,
        "indexing_in_progress": True,
        "timestamp": "2026-06-03T01:23:45Z",
    }
    fetcher = CorpusStatusPolicy().build_fetcher(api, "corpus://status")  # type: ignore[arg-type]
    payload = await fetcher()
    assert payload["total_chunks"] == 42
    assert payload["indexing_in_progress"] is True
    assert api.server_status_calls == 1


def test_corpus_status_drop_keys_suppress_request_id_churn() -> None:
    """Two payloads differing ONLY in ``request_id`` and ``timestamp``
    hash to the same SHA-256 under the policy's drop set."""
    policy = CorpusStatusPolicy()
    assert policy.drop_keys is not None
    payload_a: dict[str, Any] = {
        "total_chunks": 0,
        "timestamp": "2026-06-03T00:00:00Z",
        "request_id": "req-aaa",
    }
    payload_b: dict[str, Any] = {
        "total_chunks": 0,
        "timestamp": "2026-06-03T00:00:30Z",
        "request_id": "req-bbb",
    }
    assert canonical_hash(payload_a, policy.drop_keys) == canonical_hash(
        payload_b, policy.drop_keys
    )


def test_corpus_status_drop_keys_preserve_real_change() -> None:
    """A real field change must still produce a different hash."""
    policy = CorpusStatusPolicy()
    assert policy.drop_keys is not None
    base: dict[str, Any] = {
        "total_chunks": 0,
        "timestamp": "2026-06-03T00:00:00Z",
        "request_id": "req-aaa",
    }
    changed: dict[str, Any] = dict(base)
    changed["total_chunks"] = 99  # real change
    assert canonical_hash(base, policy.drop_keys) != canonical_hash(
        changed, policy.drop_keys
    )


# ---------------------------------------------------------------------------
# CorpusFoldersPolicy
# ---------------------------------------------------------------------------


def test_corpus_folders_policy_attributes() -> None:
    """Default cadence is the settings-supplied 5.0s; drop_keys drop
    ``last_polled`` but PRESERVE ``last_indexed``."""
    p = CorpusFoldersPolicy()
    assert p.uri_pattern == "corpus://folders"
    assert p.interval_s == 5.0  # matches default in MCPSubscriptionSettings
    assert p.drop_keys is not None
    assert "last_polled" in p.drop_keys
    assert "last_indexed" not in p.drop_keys  # real change signal — MUST stay
    # Base DEFAULT_DROP_KEYS still applies.
    assert DEFAULT_DROP_KEYS.issubset(p.drop_keys)


def test_corpus_folders_policy_satisfies_protocol() -> None:
    assert isinstance(CorpusFoldersPolicy(), SubscriptionPolicy)


def test_corpus_folders_policy_accepts_injected_interval() -> None:
    """The ``__init__`` must accept ``interval_s`` so the module-level
    registry can inject the settings cadence at import time.

    Tests also inject fast values to keep integration tests snappy.
    """
    p = CorpusFoldersPolicy(interval_s=0.05)
    assert p.interval_s == 0.05


async def test_corpus_folders_fetcher_calls_list_folders() -> None:
    api = _FakeApiClient()
    api.list_folders_payload = {
        "folders": [{"path": "/tmp/abc", "chunk_count": 12}],
        "total": 1,
    }
    fetcher = CorpusFoldersPolicy().build_fetcher(api, "corpus://folders")  # type: ignore[arg-type]
    payload = await fetcher()
    assert payload["total"] == 1
    assert api.list_folders_calls == 1


def test_corpus_folders_last_indexed_change_is_not_suppressed() -> None:
    """Two folder payloads differing in ``last_indexed`` must hash
    DIFFERENTLY — ``last_indexed`` is a real signal that something
    actually got reindexed."""
    policy = CorpusFoldersPolicy()
    assert policy.drop_keys is not None
    base: dict[str, Any] = {
        "folders": [
            {"path": "/tmp/x", "last_indexed": "2026-06-01T00:00:00Z"},
        ],
        "total": 1,
    }
    changed: dict[str, Any] = {
        "folders": [
            {"path": "/tmp/x", "last_indexed": "2026-06-03T15:00:00Z"},
        ],
        "total": 1,
    }
    assert canonical_hash(base, policy.drop_keys) != canonical_hash(
        changed, policy.drop_keys
    )


def test_corpus_folders_last_polled_change_is_suppressed() -> None:
    """``last_polled`` (the internal poll timestamp) is in drop_keys, so
    it must not produce a hash diff."""
    policy = CorpusFoldersPolicy()
    assert policy.drop_keys is not None
    base: dict[str, Any] = {
        "folders": [{"path": "/tmp/x"}],
        "total": 1,
        "last_polled": "2026-06-03T00:00:00Z",
    }
    poll_later: dict[str, Any] = {
        "folders": [{"path": "/tmp/x"}],
        "total": 1,
        "last_polled": "2026-06-03T00:00:05Z",
    }
    assert canonical_hash(base, policy.drop_keys) == canonical_hash(
        poll_later, policy.drop_keys
    )


# ---------------------------------------------------------------------------
# Registry + resolve_policy dispatch
# ---------------------------------------------------------------------------


def test_registry_contains_all_three_policies() -> None:
    """All three v2 subscribable URIs are registered at module load."""
    assert "job://" in SUBSCRIPTION_POLICIES
    assert "corpus://status" in SUBSCRIPTION_POLICIES
    assert "corpus://folders" in SUBSCRIPTION_POLICIES
    assert isinstance(SUBSCRIPTION_POLICIES["job://"], JobPolicy)
    assert isinstance(SUBSCRIPTION_POLICIES["corpus://status"], CorpusStatusPolicy)
    assert isinstance(SUBSCRIPTION_POLICIES["corpus://folders"], CorpusFoldersPolicy)


def test_resolve_policy_job_scheme_prefix_matches_any_id() -> None:
    """``resolve_policy("job://abc")`` must dispatch to JobPolicy via scheme prefix."""
    policy = resolve_policy("job://abc-123")
    assert isinstance(policy, JobPolicy)


def test_resolve_policy_corpus_status_exact_match() -> None:
    policy = resolve_policy("corpus://status")
    assert isinstance(policy, CorpusStatusPolicy)


def test_resolve_policy_corpus_folders_exact_match() -> None:
    policy = resolve_policy("corpus://folders")
    assert isinstance(policy, CorpusFoldersPolicy)


def test_resolve_policy_unknown_corpus_uri_returns_none() -> None:
    """``corpus://config`` is a known resource but not subscribable."""
    assert resolve_policy("corpus://config") is None


def test_resolve_policy_non_job_scheme_returns_none() -> None:
    """``jobs://abc`` (note the trailing s) must NOT match ``job://`` — the
    prefix lookup requires the full ``"://"`` boundary."""
    assert resolve_policy("jobs://abc") is None


def test_resolve_policy_chunk_scheme_returns_none() -> None:
    """``chunk://`` is content-addressed (CONTEXT decision G) — never subscribable."""
    assert resolve_policy("chunk://abc") is None
