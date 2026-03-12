"""Embedding cache service with two-layer architecture.

Provides an in-memory LRU layer backed by aiosqlite for persistence.
Cache keys are SHA-256(content) + provider:model:dimensions to prevent
stale embeddings when the provider or model changes.

Usage::

    from agent_brain_server.services.embedding_cache import (
        EmbeddingCacheService,
        get_embedding_cache,
        set_embedding_cache,
    )

    # In lifespan
    cache = EmbeddingCacheService(db_path=path / "embeddings.db")
    await cache.initialize("openai:text-embedding-3-large:3072")
    set_embedding_cache(cache)

    # In embedding code
    cache = get_embedding_cache()
    if cache is not None:
        key = EmbeddingCacheService.make_cache_key(text, provider, model, dims)
        embedding = await cache.get(key)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import struct
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS embeddings (
    cache_key TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    last_accessed REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_last_accessed ON embeddings (last_accessed);
"""

_MEM_LRU_DEFAULT = 1_000  # entries
_MAX_DISK_MB_DEFAULT = 500


class EmbeddingCacheService:
    """Two-layer embedding cache: in-memory LRU + aiosqlite disk.

    Layer 1 (hot path): Fixed-size ``collections.OrderedDict`` LRU.
    Sub-millisecond lookup with zero I/O.

    Layer 2 (cold path): aiosqlite SQLite database in WAL mode.
    Single-digit millisecond lookup; persists across server restarts.

    Cache key format: ``SHA-256(content_text):provider:model:dimensions``.
    This three-part fingerprint prevents stale embeddings when the provider
    or model changes.

    Provider fingerprint: stored in a ``metadata`` table row. On startup,
    a mismatch triggers an automatic wipe of all cached embeddings
    (ECACHE-04).

    Embeddings stored as float32 BLOBs (``struct.pack("Xf", *vec)``).
    At 3072 dimensions, each entry occupies ~12 KB on disk. 500 MB
    accommodates ~42,000 entries.

    Notes:
        - Reads do NOT acquire the asyncio lock; WAL mode allows concurrent
          readers while a writer holds the lock.
        - Writes serialise through ``self._lock`` to prevent write conflicts.
        - float32 precision: cosine_similarity = 1.0000000000 vs float64
          (max element error ~3.57e-9); negligible for similarity search.
    """

    def __init__(
        self,
        db_path: Path,
        max_mem_entries: int = _MEM_LRU_DEFAULT,
        max_disk_mb: int = _MAX_DISK_MB_DEFAULT,
        persist_stats: bool = False,
    ) -> None:
        """Initialise the cache service (does NOT open DB; call ``initialize``).

        Args:
            db_path: Path to the SQLite database file. Parent directory
                must exist before calling ``initialize``.
            max_mem_entries: Maximum number of entries in the in-memory
                LRU layer. Default 1,000 (~12 MB at 3072 dims).
            max_disk_mb: Maximum disk size in MB before LRU eviction runs.
                Default 500 MB (~42,000 entries at 3072 dims).
            persist_stats: If True, persist hit/miss counters across
                restarts in the metadata table. Default False (session-only
                stats avoid extra write contention on every cache hit).
        """
        self.db_path = db_path
        self.max_mem_entries = max_mem_entries
        self.max_disk_mb = max_disk_mb
        self.persist_stats = persist_stats

        self._lock: asyncio.Lock = asyncio.Lock()
        self._mem: OrderedDict[str, list[float]] = OrderedDict()

        # Runtime counters (always in-process; optionally persisted)
        self._hits: int = 0
        self._misses: int = 0

    async def initialize(self, provider_fingerprint: str) -> None:
        """Open DB, create schema, and auto-wipe on fingerprint mismatch.

        Must be called once before any ``get`` / ``put`` operations.
        Creates the database file and all required tables/indexes.
        Sets WAL journal mode, NORMAL synchronous writes, and a
        5-second busy timeout for contention resilience.

        If ``provider_fingerprint`` differs from the stored fingerprint,
        all cached embeddings are deleted and the new fingerprint is saved.
        This handles provider or model changes transparently (ECACHE-04).

        Args:
            provider_fingerprint: Stable string of the form
                ``"provider:model:dimensions"`` (e.g.
                ``"openai:text-embedding-3-large:3072"``).
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_SCHEMA)
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.commit()

            # Provider fingerprint check (ECACHE-04)
            cur = await db.execute(
                "SELECT value FROM metadata WHERE key = 'provider_fingerprint'"
            )
            row = await cur.fetchone()
            if row is None:
                await db.execute(
                    "INSERT INTO metadata VALUES ('provider_fingerprint', ?)",
                    (provider_fingerprint,),
                )
                await db.commit()
            elif row[0] != provider_fingerprint:
                logger.info(
                    "Embedding provider changed "
                    "(was %r, now %r). Clearing embedding cache.",
                    row[0],
                    provider_fingerprint,
                )
                await db.execute("DELETE FROM embeddings")
                await db.execute(
                    "UPDATE metadata SET value = ? WHERE key = 'provider_fingerprint'",
                    (provider_fingerprint,),
                )
                await db.commit()
                self._mem.clear()

        logger.info(
            "EmbeddingCacheService initialized: %s, mem=%d entries, disk=%d MB",
            self.db_path,
            self.max_mem_entries,
            self.max_disk_mb,
        )

    @staticmethod
    def make_cache_key(text: str, provider: str, model: str, dimensions: int) -> str:
        """Compute a deterministic cache key for an embedding request.

        Key format: ``SHA-256(text):provider:model:dimensions``.
        The SHA-256 hex digest is 64 characters; total key length is ~80
        characters — well within SQLite TEXT limits.

        Args:
            text: The text content to embed.
            provider: Provider name (e.g. ``"openai"``).
            model: Model identifier (e.g. ``"text-embedding-3-large"``).
            dimensions: Number of embedding dimensions (e.g. ``3072``).

        Returns:
            Deterministic cache key string.
        """
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{content_hash}:{provider}:{model}:{dimensions}"

    async def get(self, cache_key: str) -> list[float] | None:
        """Look up an embedding by cache key.

        Checks the in-memory LRU first (no lock — single asyncio thread).
        On a memory miss, queries SQLite and promotes the result into
        memory (evicting the oldest entry if the LRU is full).

        Args:
            cache_key: Key produced by :meth:`make_cache_key`.

        Returns:
            Embedding vector on hit, ``None`` on miss.
        """
        # Check in-memory LRU first (no lock needed; single asyncio thread)
        if cache_key in self._mem:
            self._mem.move_to_end(cache_key)
            self._hits += 1
            return self._mem[cache_key]

        # Check disk
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            cur = await db.execute(
                "SELECT embedding, dimensions FROM embeddings WHERE cache_key = ?",
                (cache_key,),
            )
            row = await cur.fetchone()

        if row is None:
            self._misses += 1
            return None

        blob, dims = row[0], row[1]
        embedding = list(struct.unpack(f"{dims}f", blob))

        # Promote to in-memory LRU
        self._mem[cache_key] = embedding
        self._mem.move_to_end(cache_key)
        if len(self._mem) > self.max_mem_entries:
            self._mem.popitem(last=False)

        # Update last_accessed under write lock (fire-and-forget style)
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db2:
                await db2.execute("PRAGMA journal_mode=WAL")
                await db2.execute(
                    "UPDATE embeddings SET last_accessed = ? WHERE cache_key = ?",
                    (time.time(), cache_key),
                )
                await db2.commit()

        self._hits += 1
        return embedding

    async def get_batch(self, cache_keys: list[str]) -> dict[str, list[float]]:
        """Batch lookup for multiple cache keys.

        Uses a single ``IN (?, ?, ...)`` query for efficiency. Only
        returns hits; missing keys are absent from the result dict.

        Promotes all hits to the in-memory LRU. Does not update
        ``last_accessed`` for batch hits (acceptable trade-off for
        batch efficiency).

        Args:
            cache_keys: List of keys produced by :meth:`make_cache_key`.

        Returns:
            Dict mapping cache key to embedding for all hits.
        """
        if not cache_keys:
            return {}

        # Check memory first, collect disk misses
        result: dict[str, list[float]] = {}
        disk_miss_keys: list[str] = []

        for key in cache_keys:
            if key in self._mem:
                self._mem.move_to_end(key)
                result[key] = self._mem[key]
                self._hits += 1
            else:
                disk_miss_keys.append(key)

        if not disk_miss_keys:
            return result

        # Batch SQL query for disk misses
        placeholders = ",".join("?" * len(disk_miss_keys))
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            cur = await db.execute(
                f"SELECT cache_key, embedding, dimensions "
                f"FROM embeddings WHERE cache_key IN ({placeholders})",
                disk_miss_keys,
            )
            rows = list(await cur.fetchall())

        for row_key, blob, dims in rows:
            embedding = list(struct.unpack(f"{dims}f", blob))
            result[row_key] = embedding
            self._hits += 1
            # Promote to in-memory LRU
            self._mem[row_key] = embedding
            self._mem.move_to_end(row_key)
            if len(self._mem) > self.max_mem_entries:
                self._mem.popitem(last=False)

        # Count disk misses that were not found
        disk_hits = len(rows)
        self._misses += len(disk_miss_keys) - disk_hits

        return result

    async def put(self, cache_key: str, embedding: list[float]) -> None:
        """Store an embedding in both disk and memory layers.

        Acquires the write lock, encodes the embedding as a float32 BLOB,
        inserts or replaces the row, runs eviction if the disk limit is
        exceeded, then writes to the in-memory LRU.

        Args:
            cache_key: Key produced by :meth:`make_cache_key`.
            embedding: Embedding vector to store.
        """
        dims = len(embedding)
        blob = struct.pack(f"{dims}f", *embedding)
        now = time.time()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA synchronous=NORMAL")
                await db.execute(
                    "INSERT OR REPLACE INTO embeddings "
                    "(cache_key, embedding, provider, model, "
                    "dimensions, last_accessed) "
                    "VALUES (?, ?, '', '', ?, ?)",
                    (cache_key, blob, dims, now),
                )
                await db.commit()

                # Evict if over disk limit
                await self._evict_if_needed(db)

        # Write to in-memory LRU
        self._mem[cache_key] = embedding
        self._mem.move_to_end(cache_key)
        if len(self._mem) > self.max_mem_entries:
            self._mem.popitem(last=False)

    async def _evict_if_needed(self, db: aiosqlite.Connection) -> None:
        """LRU evict oldest entries when DB exceeds ``max_disk_mb``.

        Uses ``page_count * page_size`` for accurate size measurement
        (accounts for SQLite page fragmentation). Deletes the oldest 10%
        of entries by ``last_accessed`` timestamp.

        Must be called under ``self._lock`` with an open DB connection.

        Args:
            db: Open aiosqlite connection (already under write lock).
        """
        cur = await db.execute(
            "SELECT page_count * page_size "
            "FROM pragma_page_count(), pragma_page_size()"
        )
        row = await cur.fetchone()
        if row is None:
            return
        size_bytes: int = row[0]
        max_bytes = self.max_disk_mb * 1024 * 1024
        if size_bytes <= max_bytes:
            return

        # Delete oldest 10% by last_accessed
        cur2 = await db.execute("SELECT COUNT(*) FROM embeddings")
        count_row = await cur2.fetchone()
        if count_row is None:
            return
        evict_count = max(1, count_row[0] // 10)
        await db.execute(
            "DELETE FROM embeddings WHERE cache_key IN "
            "(SELECT cache_key FROM embeddings ORDER BY last_accessed ASC LIMIT ?)",
            (evict_count,),
        )
        await db.commit()

    async def clear(self) -> tuple[int, int]:
        """Clear all cached embeddings and reclaim disk space.

        Uses its own DB connection with a short busy timeout instead of
        acquiring ``self._lock``, so it never blocks behind a long
        embedding write stream.  SQLite WAL mode handles concurrent
        writers at the database level — the DELETE waits only for the
        current page-level write to finish, not the entire batch.

        VACUUM is scheduled as a background task so the HTTP response
        returns immediately after the DELETE.

        Returns:
            Tuple of ``(entry_count, size_bytes_freed)`` measured before
            the clear.
        """
        async with aiosqlite.connect(self.db_path) as db:
            # WAL + short busy timeout so we don't block if put() holds
            # the DB write lock momentarily.
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")

            cur = await db.execute("SELECT COUNT(*) FROM embeddings")
            row = await cur.fetchone()
            count: int = row[0] if row else 0

            # Get size before delete
            cur2 = await db.execute(
                "SELECT page_count * page_size "
                "FROM pragma_page_count(), pragma_page_size()"
            )
            size_row = await cur2.fetchone()
            size_bytes: int = size_row[0] if size_row else 0

            await db.execute("DELETE FROM embeddings")
            await db.commit()

        self._mem.clear()
        self._hits = 0
        self._misses = 0

        # VACUUM in background — reclaims disk space without blocking
        # the HTTP response.  Fire-and-forget; errors are logged.
        asyncio.create_task(self._vacuum_background())

        return count, size_bytes

    async def _vacuum_background(self) -> None:
        """Run VACUUM in a background task to reclaim disk space."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA busy_timeout=30000")
                await db.execute("VACUUM")
        except Exception:
            logger.warning("Background VACUUM failed (non-critical)", exc_info=True)

    def get_stats(self) -> dict[str, Any]:
        """Return current session hit/miss counters and memory layer size.

        Returns:
            Dict with keys: ``hits``, ``misses``, ``hit_rate``,
            ``mem_entries``.
        """
        total = self._hits + self._misses
        hit_rate: float = (self._hits / total) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "mem_entries": len(self._mem),
        }

    async def get_disk_stats(self) -> dict[str, Any]:
        """Return disk-level statistics from SQLite.

        Returns:
            Dict with keys: ``entry_count``, ``size_bytes``.
        """
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM embeddings")
            row = await cur.fetchone()
            count: int = row[0] if row else 0
            cur2 = await db.execute(
                "SELECT page_count * page_size "
                "FROM pragma_page_count(), pragma_page_size()"
            )
            size_row = await cur2.fetchone()
            size_bytes: int = size_row[0] if size_row else 0
        return {"entry_count": count, "size_bytes": size_bytes}


# ---------------------------------------------------------------------------
# Module-level singleton (follows established pattern from embedding.py)
# ---------------------------------------------------------------------------

_embedding_cache: EmbeddingCacheService | None = None


def get_embedding_cache() -> EmbeddingCacheService | None:
    """Return the global cache instance, or ``None`` if not initialised.

    Returns:
        The singleton :class:`EmbeddingCacheService`, or ``None`` when the
        server has not yet initialised the cache (e.g. in tests that do not
        call :func:`set_embedding_cache`).
    """
    return _embedding_cache


def set_embedding_cache(cache: EmbeddingCacheService) -> None:
    """Set the global cache instance (called from the FastAPI lifespan).

    Args:
        cache: Fully initialised :class:`EmbeddingCacheService`.
    """
    global _embedding_cache
    _embedding_cache = cache


def reset_embedding_cache() -> None:
    """Reset the global cache instance to ``None`` (for testing).

    Allows test cases to start from a clean state without residual
    singleton state from previous test runs.
    """
    global _embedding_cache
    _embedding_cache = None
