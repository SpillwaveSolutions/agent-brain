"""Query result cache service using cachetools TTLCache.

Provides in-memory caching of query results keyed by a SHA-256 hash of the
query parameters and the current index generation counter.  The generation
counter is incremented on every successful reindex so that stale cache entries
are automatically bypassed without needing explicit per-entry eviction.

Non-deterministic query modes (``graph``, ``multi``) are never cached.

Phase 17 — QCACHE-01, QCACHE-02, QCACHE-03, QCACHE-06
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Modes that produce non-deterministic results and must never be cached.
_UNCACHEABLE_MODES: frozenset[str] = frozenset({"graph", "multi"})


class QueryCacheService:
    """In-memory TTL-based cache for query results.

    Keyed by ``SHA-256(canonical_json_of_params):index_generation`` so that:
    - Identical queries with the same parameters return the cached result.
    - Reindex events increment the generation and thus produce new keys,
      automatically bypassing stale entries.

    Reads are lock-free for performance; writes and invalidations acquire an
    ``asyncio.Lock`` to serialise mutations.

    Args:
        ttl: Time-to-live for each cache entry in seconds.
        max_size: Maximum number of entries in the cache.
    """

    def __init__(self, ttl: int = 300, max_size: int = 256) -> None:
        self._ttl = ttl
        self._max_size = max_size
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=max_size, ttl=ttl)
        self._lock = asyncio.Lock()
        self._index_generation: int = 0
        self._hits: int = 0
        self._misses: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def make_cache_key(self, request_params: dict[str, Any]) -> str:
        """Build a deterministic cache key for the given query parameters.

        Lists within the params dict are sorted before hashing so that order
        differences in list-typed fields (e.g. ``source_types``) do not
        produce distinct keys.

        Args:
            request_params: Dict of query parameters.  Any list values are
                sorted before serialisation.

        Returns:
            A string of the form ``"<hex_digest>:<generation>"``.
        """
        normalised: dict[str, Any] = {}
        for k, v in request_params.items():
            if isinstance(v, list):
                normalised[k] = sorted(v)
            else:
                normalised[k] = v

        canonical = json.dumps(normalised, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return f"{digest}:{self._index_generation}"

    def get(self, key: str) -> Any | None:
        """Retrieve a cached result (lock-free).

        Args:
            key: Cache key produced by :meth:`make_cache_key`.

        Returns:
            The cached value, or ``None`` on a miss (including TTL expiry).
        """
        value = self._cache.get(key)
        if value is None:
            self._misses += 1
            return None
        self._hits += 1
        return value

    async def put(self, key: str, value: Any) -> None:
        """Store a result in the cache (acquires lock).

        Args:
            key: Cache key produced by :meth:`make_cache_key`.
            value: Query response to store.
        """
        async with self._lock:
            self._cache[key] = value

    async def invalidate_all(self) -> None:
        """Invalidate the entire cache by incrementing the generation counter.

        All existing keys reference the old generation and will therefore
        never match future lookups.  The underlying ``TTLCache`` is also
        cleared eagerly to reclaim memory.
        """
        async with self._lock:
            self._index_generation += 1
            self._cache.clear()
        logger.debug(
            "Query cache invalidated (new generation=%d)", self._index_generation
        )

    def get_stats(self) -> dict[str, Any]:
        """Return current cache statistics.

        Returns:
            Dict with keys: ``hits``, ``misses``, ``hit_rate``,
            ``cached_entries``, ``index_generation``.
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
            "cached_entries": len(self._cache),
            "index_generation": self._index_generation,
        }

    @staticmethod
    def is_cacheable_mode(mode: str) -> bool:
        """Return ``True`` if the query mode is safe to cache.

        ``graph`` and ``multi`` modes are non-deterministic (LLM extraction
        involved) and are therefore never cached.

        Args:
            mode: Query mode string (e.g. ``"vector"``, ``"graph"``).

        Returns:
            ``True`` for ``vector``, ``bm25``, ``hybrid``; ``False`` otherwise.
        """
        return mode not in _UNCACHEABLE_MODES


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_query_cache: QueryCacheService | None = None


def get_query_cache() -> QueryCacheService | None:
    """Return the module-level singleton, or ``None`` if not initialised."""
    return _query_cache


def set_query_cache(cache: QueryCacheService) -> None:
    """Set the module-level singleton (called from lifespan)."""
    global _query_cache
    _query_cache = cache


def reset_query_cache() -> None:
    """Reset the module-level singleton to ``None`` (called on shutdown)."""
    global _query_cache
    _query_cache = None
