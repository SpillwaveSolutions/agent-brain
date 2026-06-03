"""Per-URI subscription policy registry — Plan 02 stub, Plan 03 populates.

This module defines the *shape* of a subscription policy and ships an
empty registry. Plan 02 wires the ``@server.subscribe_resource()`` handler
to consult :data:`SUBSCRIPTION_POLICIES` and :func:`resolve_policy`;
Plan 03 fills the registry with the concrete ``JobPolicy``,
``CorpusStatusPolicy``, and ``CorpusFoldersPolicy`` implementations.

Phase 52 CONTEXT decision A (subscribable URI allowlist):

* ``job://<id>`` — 1s polling, any id matches the ``"job://"`` scheme key
* ``corpus://status`` — 30s polling, exact-string key
* ``corpus://folders`` — 5s/60s polling, exact-string key

The registry key shape is **either** an exact URI string (``corpus://status``)
**or** a scheme-prefix ending in ``://`` (``job://``). :func:`resolve_policy`
tries exact match first, then scheme-prefix match. This keeps the lookup
deterministic — exact entries always win over scheme entries — without
forcing Plan 03 to list every conceivable job id at registration time.

Public surface — Plan 02 imports these symbols verbatim:

* :class:`SubscriptionPolicy` — Protocol defining the policy shape.
* :data:`SUBSCRIPTION_POLICIES` — registry dict, empty at Plan 02 land time.
* :func:`resolve_policy` — exact-then-scheme lookup helper.

Why a Protocol and not an ABC: tests need to register stub policies via
``monkeypatch.setitem(SUBSCRIPTION_POLICIES, "corpus://status", stub)``,
and structural typing keeps that lightweight (no inheritance required).
Plan 03's concrete policies will be plain dataclasses that happen to
satisfy the Protocol — no explicit ``SubscriptionPolicy`` registration.

Phase 54 cross-phase note: TOOL-04 (``wait_for_job`` progress
notifications) does NOT live in this registry. It reuses
:func:`SubscriptionManager.start_polling` directly with a one-shot
fetcher; subscription policies are only for ``resources/subscribe``-style
long-lived subscriptions.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

# Fetcher signature is intentionally identical to the
# :data:`agent_brain_mcp.subscriptions.manager.Fetcher` type alias —
# Plan 03's policies build the fetcher closure from ``ApiClient`` + URI
# and pass it through to ``SubscriptionManager.start_polling``.
PolicyFetcherFactory = Callable[[Any, str], Callable[[], Awaitable[dict[str, Any]]]]
"""Factory that takes ``(api_client, uri)`` and returns the async fetcher.

The factory pattern (instead of a bound method) lets Plan 03's policies
close over scheme-specific URL construction (e.g., ``job://abc`` →
``GET /index/jobs/abc``) without leaking the URI parsing into
:mod:`agent_brain_mcp.server`.
"""


@runtime_checkable
class SubscriptionPolicy(Protocol):
    """Per-URI cadence + drop-keys + fetcher factory for a subscribable URI.

    Plan 03 will land concrete dataclasses for the three v2 subscribable
    URIs. For Plan 02 we only need the Protocol so the handler can be
    type-checked against a structural shape.

    Attributes:
        uri_pattern: The registry key — either an exact URI
            (``"corpus://status"``) or a scheme prefix
            (``"job://"``). :func:`resolve_policy` matches by exact
            first, then by scheme prefix.
        interval_s: Seconds between successive ``fetcher()`` calls.
            Plan 03 defaults: 1.0 for ``job://``, 30.0 for
            ``corpus://status``, 5.0 for ``corpus://folders`` (active-
            subscriber cadence — the 60s safety poll is internal).
        drop_keys: Volatile keys stripped before SHA-256 diff-suppression.
            ``None`` means "use :data:`DEFAULT_DROP_KEYS`" — the
            5-key allowlist Plan 01 mandates.
        build_fetcher: Factory that constructs the async fetcher from
            ``(api_client, uri)``. Plan 02 calls
            ``policy.build_fetcher(api_client, uri)`` and forwards the
            result to :meth:`SubscriptionManager.start_polling`.
    """

    uri_pattern: str
    interval_s: float
    drop_keys: frozenset[str] | None
    build_fetcher: PolicyFetcherFactory


# Plan 02 lands this empty. Plan 03 populates with JobPolicy /
# CorpusStatusPolicy / CorpusFoldersPolicy. Tests should use
# ``monkeypatch.setitem(SUBSCRIPTION_POLICIES, ...)`` (additive, not
# replacement) so they keep working once Plan 03 fills the registry.
SUBSCRIPTION_POLICIES: dict[str, SubscriptionPolicy] = {}


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
    "PolicyFetcherFactory",
    "SUBSCRIPTION_POLICIES",
    "SubscriptionPolicy",
    "resolve_policy",
]
