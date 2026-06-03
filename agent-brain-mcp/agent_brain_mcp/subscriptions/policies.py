"""Per-URI subscription policy registry — Plan 03 populates.

This module defines the *shape* of a subscription policy
(:class:`SubscriptionPolicy` Protocol), three concrete policies that
fulfill the Phase 52 subscribable URI allowlist, and the registry
:data:`SUBSCRIPTION_POLICIES` that Plan 02's
``@server.subscribe_resource()`` handler dispatches against.

Phase 52 CONTEXT decision A (subscribable URI allowlist):

* ``job://<id>`` — 1.0s polling, scheme-key entry (``"job://"``).
  :class:`JobPolicy` raises :class:`SubscriptionTerminated` when the
  polled job reaches a terminal status so the polling loop exits
  cleanly.
* ``corpus://status`` — 30.0s polling, exact-string key.
  :class:`CorpusStatusPolicy` drops the ``request_id`` envelope field
  on top of :data:`DEFAULT_DROP_KEYS` (uvicorn's
  ``GET /health/status`` payload embeds a per-request UUID that would
  otherwise produce a different SHA-256 every 30s).
* ``corpus://folders`` — 5.0s polling by default (configurable via
  :class:`MCPSubscriptionSettings`), exact-string key.
  :class:`CorpusFoldersPolicy` preserves ``last_indexed`` (a real
  change signal — folder reindex updates it) while dropping
  ``last_polled``-style internal counters.

The registry key shape is **either** an exact URI string (``corpus://status``)
**or** a scheme-prefix ending in ``://`` (``job://``). :func:`resolve_policy`
tries exact match first, then scheme-prefix match. This keeps the lookup
deterministic — exact entries always win over scheme entries — without
forcing the registry to list every conceivable job id.

Public surface — Plan 02's wire handler imports these symbols verbatim:

* :class:`SubscriptionPolicy` — Protocol defining the policy shape.
* :data:`SUBSCRIPTION_POLICIES` — registry dict, populated below.
* :func:`resolve_policy` — exact-then-scheme lookup helper.
* :class:`JobPolicy`, :class:`CorpusStatusPolicy`,
  :class:`CorpusFoldersPolicy` — concrete policies (re-exported from
  :mod:`agent_brain_mcp.subscriptions`).

Why a Protocol and not an ABC: tests register stub policies via
``monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", stub)``;
structural typing keeps the test stubs lightweight (no inheritance
required). The three concrete policies are plain dataclasses that
happen to satisfy the Protocol.

Phase 54 cross-phase note: TOOL-04 (``wait_for_job`` progress
notifications) does NOT live in this registry. It reuses
:func:`SubscriptionManager.start_polling` directly with a one-shot
fetcher; subscription policies are only for ``resources/subscribe``-style
long-lived subscriptions.

Settings reload timing (CONTEXT specifics §3): the ``interval_s`` for
:class:`CorpusFoldersPolicy` is read from ``mcp_subscription_settings``
at module import. If settings change after the MCP server starts, the
new value is NOT picked up — restart the server. v2 explicitly accepts
this (no hot reload). The safety-poll cadence ``folders_safety_interval_s``
is documented in :mod:`agent_brain_mcp.config` but Plan 03 does NOT
wire it through the polling loop — it is reserved for a v3 micro-plan
if the 5s active cadence proves insufficient.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..client import ApiClient
from ..config import mcp_subscription_settings
from .errors import SubscriptionTerminated
from .payloads import DEFAULT_DROP_KEYS

# Fetcher signature is intentionally identical to the
# :data:`agent_brain_mcp.subscriptions.manager.Fetcher` type alias —
# the concrete policies build the fetcher closure from ``ApiClient`` +
# URI and pass it through to ``SubscriptionManager.start_polling``.
PolicyFetcherFactory = Callable[[Any, str], Callable[[], Awaitable[dict[str, Any]]]]
"""Factory that takes ``(api_client, uri)`` and returns the async fetcher.

The factory pattern (instead of a bound method) lets the concrete
policies close over scheme-specific URL construction (e.g., ``job://abc``
→ ``GET /index/jobs/abc``) without leaking the URI parsing into
:mod:`agent_brain_mcp.server`.
"""

# Terminal job statuses — when ``ApiClient.get_job(job_id)["status"]``
# matches one of these, :class:`JobPolicy` raises
# :class:`SubscriptionTerminated` so the polling loop exits cleanly.
# Pinned by ``tests/subscriptions/test_policies.py``.
TERMINAL_JOB_STATUSES: frozenset[str] = frozenset({"completed", "failed", "cancelled"})


@runtime_checkable
class SubscriptionPolicy(Protocol):
    """Per-URI cadence + drop-keys + fetcher factory for a subscribable URI.

    The three concrete policies (:class:`JobPolicy`,
    :class:`CorpusStatusPolicy`, :class:`CorpusFoldersPolicy`) are plain
    dataclasses that satisfy this Protocol structurally — they do NOT
    inherit. Test stubs likewise satisfy the Protocol by structural
    typing alone.

    Attributes are declared via ``@property`` because they are
    effectively read-only at the policy level (instantiated once per
    process at module load and never mutated). Pydantic/mypy is strict
    about mutable-vs-read-only attribute compatibility when checking
    Protocol conformance against dataclass instances; declaring as
    properties makes the read-only intent explicit and lets the
    dataclass field expose the same value via attribute access.

    Attributes:
        uri_pattern: The registry key — either an exact URI
            (``"corpus://status"``) or a scheme prefix
            (``"job://"``). :func:`resolve_policy` matches by exact
            first, then by scheme prefix.
        interval_s: Seconds between successive ``fetcher()`` calls.
            Plan 03 defaults: 1.0 for ``job://``, 30.0 for
            ``corpus://status``, configurable (default 5.0) for
            ``corpus://folders``.
        drop_keys: Volatile keys stripped before SHA-256 diff-suppression.
            ``None`` means "use :data:`DEFAULT_DROP_KEYS`" — the
            5-key allowlist Plan 01 mandates.
        build_fetcher: Factory that constructs the async fetcher from
            ``(api_client, uri)``. The wire handler calls
            ``policy.build_fetcher(api_client, uri)`` and forwards the
            result to :meth:`SubscriptionManager.start_polling`.
    """

    @property
    def uri_pattern(self) -> str: ...
    @property
    def interval_s(self) -> float: ...
    @property
    def drop_keys(self) -> frozenset[str] | None: ...
    @property
    def build_fetcher(self) -> PolicyFetcherFactory: ...


# ---------------------------------------------------------------------------
# Concrete policy implementations (Phase 52 Plan 03)
# ---------------------------------------------------------------------------
#
# Why module-level fetcher-factories instead of @staticmethod inside the
# dataclasses: mypy + the runtime_checkable Protocol see a @staticmethod
# as a method descriptor, not a plain ``Callable``, and refuse to admit
# the dataclass satisfies :class:`SubscriptionPolicy`. Exposing the
# factory as a module-level function and assigning it to the dataclass
# field at class-default time produces an instance attribute whose value
# IS a plain Callable, which matches the Protocol verbatim.


def _build_job_fetcher(
    api_client: ApiClient, uri: str
) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Return an async fetcher that polls ``GET /index/jobs/<id>``.

    The job id is parsed from ``uri`` by stripping the ``job://``
    prefix (and any trailing slash, defensively — Plan 02 normalizes
    but the fetcher does the same to stay robust). Empty id →
    terminal "invalid" exit on first poll. Terminal job status →
    :class:`SubscriptionTerminated` so the polling loop exits cleanly
    (no more ``GET /index/jobs/<id>`` calls after a job completes).
    """
    job_id = uri.removeprefix("job://").rstrip("/")

    async def fetcher() -> dict[str, Any]:
        if not job_id:
            # No id → nothing to poll. Exit fast with a minimal
            # payload so the subscriber sees one ``on_change`` and
            # the loop returns. Plan 02's wire handler accepts the
            # subscribe attempt because the URI passes
            # ``_is_known_uri`` (scheme is known); we surface the
            # missing-id condition here so URI parsing stays in the
            # policy layer.
            raise SubscriptionTerminated(
                {"status": "invalid", "uri": uri, "reason": "missing_job_id"}
            )
        payload = await asyncio.to_thread(api_client.get_job, job_id)
        if payload.get("status") in TERMINAL_JOB_STATUSES:
            raise SubscriptionTerminated(payload)
        return payload

    return fetcher


def _build_corpus_status_fetcher(
    api_client: ApiClient, uri: str
) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Return an async fetcher that polls ``GET /health/status``.

    ``uri`` is accepted for Protocol-signature consistency but is
    unused — ``corpus://status`` is a singleton URI with no
    parameterized id.
    """
    del uri  # unused — singleton URI has no parameters

    async def fetcher() -> dict[str, Any]:
        return await asyncio.to_thread(api_client.server_status)

    return fetcher


def _build_corpus_folders_fetcher(
    api_client: ApiClient, uri: str
) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Return an async fetcher that polls ``GET /index/folders/``.

    ``uri`` is accepted for Protocol-signature consistency but is
    unused — ``corpus://folders`` is a singleton URI with no
    parameterized id.
    """
    del uri  # unused — singleton URI has no parameters

    async def fetcher() -> dict[str, Any]:
        return await asyncio.to_thread(api_client.list_folders)

    return fetcher


@dataclass
class JobPolicy:
    """Polling policy for ``job://<id>`` URIs (SUB-01).

    Cadence: 1.0s per CONTEXT decision B — jobs mutate continuously
    while running. Diff-suppression via :data:`DEFAULT_DROP_KEYS`
    handles timestamp churn in the job payload.

    Terminal exit: when the polled payload reports
    ``status in TERMINAL_JOB_STATUSES``, the fetcher raises
    :class:`SubscriptionTerminated(payload)`. Plan 01's polling loop
    catches the sentinel, emits one final ``on_change`` with the
    terminal payload, and exits cleanly.

    Invalid job id (URI is literally ``job://`` with no id after the
    scheme): the fetcher raises ``SubscriptionTerminated`` with a
    minimal "invalid" payload so the subscriber sees one notification
    and the loop exits. Plan 02's wire handler could pre-validate but
    that would couple URI parsing into the handler — leaving it in
    the fetcher keeps validation localized.
    """

    uri_pattern: str = "job://"
    interval_s: float = 1.0
    drop_keys: frozenset[str] | None = None  # → DEFAULT_DROP_KEYS
    build_fetcher: PolicyFetcherFactory = field(default=_build_job_fetcher)


@dataclass
class CorpusStatusPolicy:
    """Polling policy for ``corpus://status`` (SUB-02).

    Cadence: 30.0s per CONTEXT decision B — status mutates rarely.
    Diff-suppression adds ``request_id`` to :data:`DEFAULT_DROP_KEYS`:
    uvicorn's ``GET /health/status`` payload embeds a per-request
    correlation UUID that would otherwise produce a different
    SHA-256 every 30s regardless of whether the status actually
    changed.
    """

    uri_pattern: str = "corpus://status"
    interval_s: float = 30.0
    drop_keys: frozenset[str] | None = field(
        default_factory=lambda: DEFAULT_DROP_KEYS | {"request_id"}
    )
    build_fetcher: PolicyFetcherFactory = field(default=_build_corpus_status_fetcher)


@dataclass
class CorpusFoldersPolicy:
    """Polling policy for ``corpus://folders`` (SUB-03).

    Cadence: configurable via :class:`MCPSubscriptionSettings`. Plan 03
    uses the active-subscriber cadence ``folders_active_interval_s``
    (default 5.0s — CONTEXT decision B). The corresponding
    ``folders_safety_interval_s`` (default 60.0s) is documented in
    :mod:`agent_brain_mcp.config` but NOT wired through this policy in
    Plan 03 — the active 5s cadence runs the whole time a subscriber
    is active, and the v2 design has no separate "no-subscriber"
    branch (CONTEXT decision E + specifics §3). Reserved for a future
    v3 micro-plan if the 5s cadence proves insufficient.

    Drop keys: :data:`DEFAULT_DROP_KEYS` plus the internal
    ``last_polled`` key. The payload's ``last_indexed`` field is a
    **real** change signal (file watcher / index job completion
    updates it) and MUST NOT be dropped — CONTEXT decision B + risk
    note.

    Cadence injection: the dataclass field ``interval_s`` is exposed
    so the module-level registry instantiation can construct
    ``CorpusFoldersPolicy(interval_s=settings.folders_active_interval_s)``
    at import time. Tests can also pass a fast value (e.g., 0.05s) to
    keep integration tests snappy.
    """

    uri_pattern: str = "corpus://folders"
    interval_s: float = 5.0
    drop_keys: frozenset[str] | None = field(
        default_factory=lambda: DEFAULT_DROP_KEYS | {"last_polled"}
    )
    build_fetcher: PolicyFetcherFactory = field(default=_build_corpus_folders_fetcher)


# ---------------------------------------------------------------------------
# Registry — module-load instantiation
# ---------------------------------------------------------------------------

# Plan 03 populates with the three concrete policies. Tests should use
# ``monkeypatch.setitem(SUBSCRIPTION_POLICIES, ...)`` (additive
# replacement for one test scope) so they keep working without rebuilding
# the entire registry.
#
# Cadence injection: CorpusFoldersPolicy reads from settings at module
# import. Settings are themselves read from env vars at config-module
# import (no hot reload — restart the server).
SUBSCRIPTION_POLICIES: dict[str, SubscriptionPolicy] = {
    "job://": JobPolicy(),
    "corpus://status": CorpusStatusPolicy(),
    "corpus://folders": CorpusFoldersPolicy(
        interval_s=mcp_subscription_settings.folders_active_interval_s
    ),
}


def resolve_policy(uri: str) -> SubscriptionPolicy | None:
    """Look up the policy that owns ``uri``, or ``None`` if not subscribable.

    Resolution order:

    1. **Exact match** — ``corpus://status`` or ``corpus://folders``
       must be exact (the strings are pinned by Phase 52 CONTEXT
       decision A as the only subscribable corpus URIs).
    2. **Scheme-prefix match** — any URI starting with ``job://`` (or
       a future scheme like ``progress://``) falls through to its
       scheme entry. The prefix MUST end in ``"://"`` so partial-
       string matches like ``"jobsomething://"`` don't collide.

    Args:
        uri: The normalized resource URI (trailing slash already
            stripped by the wire handler).

    Returns:
        The matching :class:`SubscriptionPolicy` or ``None`` if no
        entry matches. Plan 02's handler converts ``None`` into a
        ``SubscribableUriRejected(reason="not_subscribable")`` MCP
        error before the SDK frames the response.
    """
    # (1) exact match first — exact wins over scheme.
    policy = SUBSCRIPTION_POLICIES.get(uri)
    if policy is not None:
        return policy

    # (2) scheme-prefix match: find ``scheme://`` and check the registry.
    # ``urlsplit`` is overkill here since we only need the scheme; do a
    # cheap left-anchored lookup so the helper stays import-light.
    sep = uri.find("://")
    if sep == -1:
        return None
    scheme_key = uri[: sep + 3]  # includes the trailing "://"
    return SUBSCRIPTION_POLICIES.get(scheme_key)


__all__ = [
    "CorpusFoldersPolicy",
    "CorpusStatusPolicy",
    "JobPolicy",
    "PolicyFetcherFactory",
    "SUBSCRIPTION_POLICIES",
    "SubscriptionPolicy",
    "TERMINAL_JOB_STATUSES",
    "resolve_policy",
]
