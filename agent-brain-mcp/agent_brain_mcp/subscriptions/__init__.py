"""Subscription bookkeeping and polling primitive for MCP resources.

Phase 52 (Plan 01) greenfield package. Owns per-session subscription
state, polling tasks, canonical payload hashing for diff-suppression,
and the ``SubscribableUriRejected`` error type.

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

No MCP wire integration lives here — Plan 02 wires the SDK
decorators and the ``ServerSession.send_resource_updated`` call.
"""

from .errors import SubscribableUriRejected
from .manager import Fetcher, OnChange, SubscriptionManager
from .payloads import DEFAULT_DROP_KEYS, canonical_hash

__all__ = [
    "DEFAULT_DROP_KEYS",
    "Fetcher",
    "OnChange",
    "SubscribableUriRejected",
    "SubscriptionManager",
    "canonical_hash",
]
