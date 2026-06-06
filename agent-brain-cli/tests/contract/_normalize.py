"""Volatile-field stripper for cross-transport contract tests.

Phase 57 Plan 02 — v3 DoD anchor (CLI-MCP-04). Lives under
``tests/contract/`` so future phases (58, 59) can reuse the
stripper for their own equivalence pins.
"""

from __future__ import annotations

from typing import Any

# Top-level keys that vary across CLI invocations and MUST NOT
# be compared (timing + walltime fields).
_TOPLEVEL_VOLATILE: frozenset[str] = frozenset({"elapsed_seconds", "query_time_ms"})

# Per-result keys that vary across CLI invocations and MUST NOT
# be compared (timestamp fields in chunk metadata).
_RESULT_VOLATILE: frozenset[str] = frozenset({"indexed_at", "updated_at", "elapsed_ms"})


def strip_volatile_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of ``payload`` with volatile keys removed.

    Strips:
      - Top-level ``elapsed_seconds`` and ``query_time_ms`` if present
      - Per-result ``indexed_at`` / ``updated_at`` / ``elapsed_ms`` (looks
        in ``result["metadata"]`` AND on the result itself)

    Used by the v3 byte-identical-equivalence contract test
    (``test_transport_equivalence.py``) — pinned shape per CONTEXT
    decision in 57-CONTEXT.md §decisions.
    """
    normalized: dict[str, Any] = {
        k: v for k, v in payload.items() if k not in _TOPLEVEL_VOLATILE
    }
    results = normalized.get("results", [])
    cleaned_results: list[dict[str, Any]] = []
    for result in results:
        r = {k: v for k, v in result.items() if k not in _RESULT_VOLATILE}
        metadata = r.get("metadata")
        if isinstance(metadata, dict):
            r["metadata"] = {
                k: v for k, v in metadata.items() if k not in _RESULT_VOLATILE
            }
        cleaned_results.append(r)
    normalized["results"] = cleaned_results
    return normalized
