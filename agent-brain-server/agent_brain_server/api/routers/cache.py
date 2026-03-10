"""Cache management API endpoints.

Provides endpoints for querying and clearing the embedding cache.
Mounted at ``/index/cache`` in the main application.

Endpoints:
    GET  / — Return combined hit/miss + disk statistics.
    DELETE / — Clear all cached embeddings and return freed counts.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from agent_brain_server.services.embedding_cache import get_embedding_cache

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/",
    summary="Embedding Cache Status",
    description=(
        "Returns embedding cache hit/miss counters and disk statistics. "
        "Returns 503 if the cache service is not initialised."
    ),
)
async def cache_status(request: Request) -> dict[str, Any]:
    """Return embedding cache statistics.

    Combines in-process session counters (hits, misses, hit_rate,
    mem_entries) with disk-level stats (entry_count, size_bytes) from
    SQLite.

    Returns:
        Dict with keys: hits, misses, hit_rate, mem_entries,
        entry_count, size_bytes.

    Raises:
        HTTPException: 503 if cache service is not initialised.
    """
    cache = get_embedding_cache()
    if cache is None:
        raise HTTPException(
            status_code=503,
            detail="Embedding cache service not initialised",
        )

    stats = cache.get_stats()
    disk_stats = await cache.get_disk_stats()
    return {**stats, **disk_stats}


@router.delete(
    "/",
    summary="Clear Embedding Cache",
    description=(
        "Deletes all cached embeddings and reclaims disk space via VACUUM. "
        "Returns the number of entries cleared and bytes freed. "
        "Safe to call while indexing jobs are running (running jobs will "
        "regenerate embeddings at normal API cost). "
        "Returns 503 if the cache service is not initialised."
    ),
)
async def clear_cache(request: Request) -> dict[str, Any]:
    """Clear all cached embeddings.

    Counts entries and measures DB size before deletion, deletes all rows,
    runs VACUUM to reclaim disk space. In-memory LRU is also cleared.
    Session hit/miss counters are reset.

    Returns:
        Dict with keys: count (entries cleared), size_bytes,
        size_mb (size_bytes / 1 MB).

    Raises:
        HTTPException: 503 if cache service is not initialised.
    """
    cache = get_embedding_cache()
    if cache is None:
        raise HTTPException(
            status_code=503,
            detail="Embedding cache service not initialised",
        )

    count, size_bytes = await cache.clear()
    return {
        "count": count,
        "size_bytes": size_bytes,
        "size_mb": size_bytes / (1024 * 1024),
    }
