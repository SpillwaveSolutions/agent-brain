"""Cache-related tools: ``cache_status`` (TOOL-07).

Phase 54 Plan 02 lands ``handle_cache_status``. Plan 03 will EXTEND
this module with ``handle_clear_cache`` (TOOL-08) — do not pre-empt
that work here.

``cache_status`` is a thin wrapper over :meth:`ApiClient.cache_status`
(Phase 54 Plan 01 ApiClient method). The server returns 503 when the
cache service is not initialised; that surfaces as an
:class:`McpError(SERVICE_INDEXING)` through the existing
:func:`agent_brain_mcp.errors.raise_for_status` pipeline (Phase 54
CONTEXT decision G) — no per-handler mapping needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import CacheStatusInput, CacheStatusOutput

if TYPE_CHECKING:
    from ..client import ApiClient


def handle_cache_status(
    client: ApiClient,
    args: CacheStatusInput,  # noqa: ARG001 — uniform ToolSpec handler signature
) -> CacheStatusOutput:
    """Return embedding cache statistics via ``GET /index/cache/``.

    Args:
        client: Authenticated ``ApiClient``.
        args: Empty input model (kept for ToolSpec signature uniformity).

    Returns:
        :class:`CacheStatusOutput` carrying the six typed keys
        (``hits`` / ``misses`` / ``hit_rate`` / ``mem_entries`` /
        ``entry_count`` / ``size_bytes``) plus any forward-compatible
        extras the server may add — :class:`CacheStatusOutput` is
        configured with ``extra="allow"`` so additional keys round-trip
        cleanly.

    Raises:
        McpError: If the server returns 503 (cache service not
            initialised). The mapping is handled uniformly by
            :func:`errors.raise_for_status` per CONTEXT decision G.
    """
    raw = client.cache_status()
    return CacheStatusOutput.model_validate(raw)
