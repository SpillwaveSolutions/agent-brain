"""Cache-related tools: ``cache_status`` (TOOL-07) + ``clear_cache`` (TOOL-08).

Plan 02 landed :func:`handle_cache_status`. Plan 03 EXTENDS this
module with :func:`handle_clear_cache` — the destructive counterpart
guarded by ``confirm: Literal[True]`` at the Pydantic layer.

``cache_status`` is a thin wrapper over :meth:`ApiClient.cache_status`
(Phase 54 Plan 01 ApiClient method). The server returns 503 when the
cache service is not initialised; that surfaces as an
:class:`McpError(SERVICE_INDEXING)` through the existing
:func:`agent_brain_mcp.errors.raise_for_status` pipeline (Phase 54
CONTEXT decision G) — no per-handler mapping needed.

``clear_cache`` wraps :meth:`ApiClient.clear_cache`
(``DELETE /index/cache/``). The same 503 mapping applies; the
:class:`ClearCacheInput` ``Literal[True]`` confirm ensures the
destructive call is only reachable after explicit acknowledgement
(extension of v1 ``cancel_job`` pattern).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import (
    CacheStatusInput,
    CacheStatusOutput,
    ClearCacheInput,
    ClearCacheOutput,
)

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


def handle_clear_cache(
    client: ApiClient,
    args: ClearCacheInput,  # noqa: ARG001 — confirm enforced by Pydantic
) -> ClearCacheOutput:
    """Clear the embedding cache via ``DELETE /index/cache/``.

    The ``confirm: Literal[True]`` guard on :class:`ClearCacheInput`
    is enforced by Pydantic at construction time — invocations without
    ``confirm=True`` are rejected before this handler runs. The handler
    therefore does not need to re-check ``args.confirm`` defensively
    (the value is either True or the schema rejected).

    Args:
        client: Authenticated :class:`ApiClient`.
        args: Validated :class:`ClearCacheInput` (only field is
            ``confirm: Literal[True]``; unused at runtime because
            Pydantic gates construction).

    Returns:
        :class:`ClearCacheOutput` mirroring the server's
        ``_clear_cache_impl`` return shape (``count`` / ``size_bytes`` /
        ``size_mb``).

    Raises:
        McpError: If the server returns 503 (cache service not
            initialised). Uniform mapping via
            :func:`errors.raise_for_status`.
    """
    raw = client.clear_cache()
    return ClearCacheOutput.model_validate(raw)
