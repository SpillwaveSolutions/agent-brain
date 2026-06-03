"""Subscription bookkeeping and polling primitive for MCP resources.

Phase 52 (Plan 01) greenfield package. Owns per-session subscription
state, polling tasks, canonical payload hashing for diff-suppression,
and the ``SubscribableUriRejected`` error type.

Plan 02 adds the per-URI policy registry — :class:`SubscriptionPolicy`
+ :data:`SUBSCRIPTION_POLICIES` (empty until Plan 03 populates) +
:func:`resolve_policy` (exact-then-scheme lookup helper used by the
``@server.subscribe_resource()`` wire handler).

Public API (Plans 02/03/04 + Phase 54 TOOL-04 ``wait_for_job`` reuse):

* :class:`SubscriptionManager` — per-server-process subscription
  registry + polling-task lifecycle.
* :func:`canonical_hash` — SHA-256 of normalized JSON payload, with
  volatile keys dropped at every depth.
* :data:`DEFAULT_DROP_KEYS` — the frozenset of volatile keys that
  ``canonical_hash`` strips by default.
* :class:`SubscribableUriRejected` — MCP error raised by Plan 02's
  ``@server.subscribe_resource()`` handler when a URI is unknown
  or outside the subscribable allowlist.
* :class:`SubscriptionTerminated` — control-flow sentinel a Plan 03
  policy fetcher raises to signal the polling loop should exit
  cleanly (e.g., ``job://<id>`` reached a terminal status).
* :class:`SubscriptionPolicy` — Protocol for per-URI cadence + fetcher
  factory (Plan 03 lands concrete implementations).
* :data:`SUBSCRIPTION_POLICIES` — registry of per-URI policies.
  Plan 02 lands the empty registry; Plan 03 populates with
  :class:`JobPolicy`, :class:`CorpusStatusPolicy`,
  :class:`CorpusFoldersPolicy` at module import time.
* :func:`resolve_policy` — exact-then-scheme lookup helper.

The MCP wire integration in :mod:`agent_brain_mcp.server` consumes these
symbols; this package owns the data structures and dispatch helpers but
does NOT import the MCP SDK directly outside of :mod:`.errors`.
"""

from .errors import SubscribableUriRejected, SubscriptionTerminated
from .manager import Fetcher, OnChange, SubscriptionManager
from .payloads import DEFAULT_DROP_KEYS, canonical_hash
from .policies import (
    SUBSCRIPTION_POLICIES,
    CorpusFoldersPolicy,
    CorpusStatusPolicy,
    JobPolicy,
    PolicyFetcherFactory,
    SubscriptionPolicy,
    resolve_policy,
)

__all__ = [
    "DEFAULT_DROP_KEYS",
    "CorpusFoldersPolicy",
    "CorpusStatusPolicy",
    "Fetcher",
    "JobPolicy",
    "OnChange",
    "PolicyFetcherFactory",
    "SUBSCRIPTION_POLICIES",
    "SubscribableUriRejected",
    "SubscriptionManager",
    "SubscriptionPolicy",
    "SubscriptionTerminated",
    "canonical_hash",
    "resolve_policy",
]
