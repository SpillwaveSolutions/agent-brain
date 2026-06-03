"""Canonical payload hashing for subscription diff-suppression.

This module exists so :class:`SubscriptionManager` can decide whether a
freshly polled payload represents *meaningful* change worth a
``notifications/resources/updated`` poke, or just volatile churn
(timestamps, elapsed counters) that should be suppressed.

Phase 52 CONTEXT decision B: "Always hash the *normalized* payload
(sorted keys, drop volatile fields like ``timestamp``, ``elapsed_ms``).
Don't send ``notifications/resources/updated`` if the hash matches the
last sent value for that ``(session_id, uri)``."

The same helper backs the optional ``_meta.revision`` field in
:class:`mcp.types.ResourceUpdatedNotificationParams` (CONTEXT decision C)
so clients can short-circuit ``resources/read`` when the revision they
already cached matches.

Phase 54 TOOL-04 (``wait_for_job``) reuse contract: the
``progress`` field in
:class:`mcp.types.ProgressNotificationParams` is debounced via the same
canonical-hash machinery — keep the public surface (``canonical_hash``
+ ``DEFAULT_DROP_KEYS``) stable across phases.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Keys that are dropped at EVERY nesting depth before hashing. These are
# fields whose value mutates on every poll but doesn't represent
# user-meaningful change — uvicorn's ``/health/status`` for example
# embeds a request timestamp deep in its body, and without this drop the
# ``corpus://status`` subscription would emit on every 30s poll
# regardless of actual content change (Phase 52 CONTEXT specifics #3).
#
# ``frozenset`` is intentional — immutable + hashable so a caller can
# pass it as ``drop_keys`` without risk of mutation across polls.
DEFAULT_DROP_KEYS: frozenset[str] = frozenset(
    {
        "timestamp",
        "updated_at",
        "elapsed_ms",
        "polled_at",
        "now",
    }
)


def _strip(obj: Any, drop: frozenset[str] | set[str]) -> Any:
    """Recursively drop ``drop`` keys from ``obj`` at every nesting depth.

    Dicts return a new dict with disallowed keys excised; lists/tuples
    return a list with each element recursively stripped; scalars pass
    through unchanged. Non-dict/non-list values inside dicts are
    preserved verbatim.

    The function does NOT sort keys here — that is JSON's job at
    serialization time via ``sort_keys=True``. Returning a regular
    dict (insertion order) is fine because ``json.dumps`` re-orders.
    """
    if isinstance(obj, dict):
        return {k: _strip(v, drop) for k, v in obj.items() if k not in drop}
    if isinstance(obj, list):
        return [_strip(item, drop) for item in obj]
    if isinstance(obj, tuple):
        # Treat tuples as lists for hashing — JSON has no tuple type.
        return [_strip(item, drop) for item in obj]
    return obj


def canonical_hash(
    payload: dict[str, Any], drop: frozenset[str] | set[str] | None = None
) -> str:
    """Return the SHA-256 hex digest of ``payload`` after dropping ``drop`` keys.

    Steps (CONTEXT decision B):
        1. Recursively remove every key in ``drop`` from ``payload``
           (at every nesting depth).
        2. Serialize via ``json.dumps(..., sort_keys=True,
           separators=(",", ":"))`` for byte-stable output.
        3. SHA-256 hex digest (64 chars).

    Args:
        payload: The polled resource payload to hash.
        drop: Volatile keys to strip at every depth. Defaults to
            :data:`DEFAULT_DROP_KEYS` when ``None``.

    Returns:
        64-char lowercase hexadecimal SHA-256 digest.

    Raises:
        TypeError: If ``payload`` contains values that are not
            JSON-serializable after the strip step. The caller's
            polling task wraps this in a logged warning and treats
            it as "payload changed" (defensive — better to over-emit
            than swallow a real change).
    """
    effective_drop: frozenset[str] | set[str] = (
        DEFAULT_DROP_KEYS if drop is None else drop
    )
    stripped = _strip(payload, effective_drop)
    serialized = json.dumps(stripped, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
