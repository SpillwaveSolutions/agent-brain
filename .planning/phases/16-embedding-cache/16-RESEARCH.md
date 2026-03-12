# Phase 16: Embedding Cache - Research

**Researched:** 2026-03-10
**Domain:** aiosqlite persistence, LRU caching, SHA-256 content hashing, embedding API interception
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Cache Metrics & Status Display**
- Metrics configurable: cumulative per session or persistent across restarts (Claude decides default, makes it configurable)
- Summary line in `agent-brain status` by default: entry count, hit rate, hits, misses
- Detailed section via `agent-brain status --verbose` or `--json`: adds DB size on disk, provider:model fingerprint, cache age
- `/health/status` API includes `embedding_cache` section only when cache has entries (omit for fresh installs)

**Cache Clear Behavior**
- `agent-brain cache` is a command group with subcommands: `cache clear`, `cache status`
- `agent-brain cache clear` requires `--yes` flag (matches `agent-brain reset --yes` pattern)
- Without `--yes`, prompt: "This will flush N cached embeddings. Continue? [y/N]"
- Cache clearing allowed while indexing jobs are running — running jobs will regenerate embeddings (costs API calls, no corruption)
- Feedback after clear: "Cleared 1,234 cached embeddings (45.2 MB freed)" — show count + size

**Provider/Model Change Handling**
- Silent auto-wipe on server startup when provider:model:dimensions mismatch detected
- Server logs info message about wipe but no user-facing warning
- Cache key includes provider + model + dimensions_override — catches edge case of same model with different dimension configs

**Cache Size & Eviction Policy**
- Configurable max disk size, default 500 MB (~40K entries at 3072-dim)
- LRU eviction when size limit reached — track last_accessed timestamp per entry
- Two-layer cache: in-memory LRU (hot entries) + aiosqlite disk (cold entries, still faster than API)
- In-memory layer sized by entry count (Claude decides appropriate default)
- Max disk size configurable via env var / YAML config

### Claude's Discretion
- Provider fingerprint storage strategy (metadata row vs per-entry key) — pick what best meets ECACHE-04
- Multi-provider cache behavior — pick based on how multi-instance architecture works (one server = one provider)
- Whether cache stats appear in job completion output — pick what fits existing job output pattern
- In-memory LRU layer size default
- aiosqlite WAL mode configuration
- Startup recovery / corruption handling
- Batch cache lookup optimization for embed_texts() calls

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 16 adds a two-layer embedding cache (in-memory LRU + aiosqlite disk) that intercepts `EmbeddingGenerator.embed_text()` / `embed_texts()` / `embed_query()` before delegating to the provider. Cache keys are `SHA-256(content) + ":" + provider + ":" + model + ":" + str(dimensions)`. This three-part fingerprint prevents dimension mismatches when provider or model changes.

The cache is a singleton service (`EmbeddingCacheService`) following the same `get_*()` / `reset_*()` / module-level pattern used by `EmbeddingGenerator`. It initializes in the FastAPI lifespan alongside other services, reads a metadata row on startup to detect provider changes and auto-wipe if needed, and exposes hit/miss counters both in-process and (optionally) persisted to the SQLite metadata table.

The CLI gets a new `cache` command group (parallel to `folders`, `jobs`) with `cache status` and `cache clear` subcommands. The `/health/status` response gains an `embedding_cache` dict field, populated only when the cache has entries.

**Primary recommendation:** Implement `EmbeddingCacheService` with aiosqlite (already a transitive dep at 0.22.0), WAL mode, float32 BLOB storage (`struct.pack`), and a fixed-size `OrderedDict` in-memory LRU layer. Wire into `EmbeddingGenerator` as the sole integration point for all three embed methods.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiosqlite | 0.22.0 (transitive, already installed) | Async SQLite persistence | Already a transitive dep via `asyncpg`/SQLAlchemy chain; no new install needed |
| Python stdlib `struct` | stdlib | BLOB encode/decode of float vectors | float32 (`struct.pack('Xf', *vec)`) halves storage vs float64; cosine-similarity precision is unaffected (verified: cos_sim = 1.0000000000) |
| Python stdlib `hashlib` | stdlib | SHA-256 content hash | Already used in ManifestTracker — reuse `compute_file_checksum` or inline `hashlib.sha256(text.encode()).hexdigest()` for text |
| Python stdlib `collections.OrderedDict` | stdlib | In-memory LRU layer | Sufficient for fixed-capacity LRU; no extra dep needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio.Lock` | stdlib | Serialise writes to SQLite | Required — aiosqlite is not thread/coroutine safe for concurrent writes |
| `pydantic_settings.BaseSettings` | 2.6.0 (existing) | `EMBEDDING_CACHE_*` env vars | Add `EMBEDDING_CACHE_MAX_DISK_MB`, `EMBEDDING_CACHE_MAX_MEM_ENTRIES`, `EMBEDDING_CACHE_PERSIST_STATS` to existing `Settings` class |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `struct.pack` float32 BLOB | `struct.pack` float64 | float64 is 24KB/entry (3072-dim) vs 12KB for float32; 500 MB holds ~21K vs ~42K entries; float32 precision is sufficient for cosine similarity |
| `struct.pack` BLOB | JSON array | JSON text is ~5× larger and slower to parse; BLOB is the right choice for vector data |
| `OrderedDict` LRU | `functools.lru_cache` | `lru_cache` is per-function and hard to size/clear dynamically; `OrderedDict` gives full control |
| `OrderedDict` LRU | `cachetools.LRUCache` | Would add a dep; `OrderedDict` is zero-dep and sufficient |

**Installation:** No new packages required. `aiosqlite` is already installed as a transitive dependency at version 0.22.0.

---

## Architecture Patterns

### Recommended Project Structure

New files for this phase:

```
agent-brain-server/
└── agent_brain_server/
    └── services/
        └── embedding_cache.py        # EmbeddingCacheService + get/reset functions

agent-brain-cli/
└── agent_brain_cli/
    └── commands/
        └── cache.py                  # cache_group (cache status + cache clear)
```

Modified files:

```
agent-brain-server/
└── agent_brain_server/
    ├── config/settings.py            # EMBEDDING_CACHE_* env vars
    ├── indexing/embedding.py         # Inject EmbeddingCacheService into embed_*() methods
    ├── models/health.py              # embedding_cache field on IndexingStatus
    ├── api/routers/health.py         # Populate embedding_cache from app.state
    ├── api/main.py                   # Initialize EmbeddingCacheService in lifespan
    └── storage_paths.py             # Add "embedding_cache" to SUBDIRECTORIES + resolve_storage_paths

agent-brain-cli/
└── agent_brain_cli/
    ├── client/api_client.py          # clear_cache() + cache_status() methods + CacheStatus dataclass
    ├── commands/__init__.py          # Export cache_group
    └── cli.py                        # cli.add_command(cache_group, name="cache")
```

### Pattern 1: EmbeddingCacheService — Two-Layer Architecture

**What:** An `asyncio`-native service with an in-memory `OrderedDict` LRU (hot path, sub-ms) backed by an aiosqlite database (persistent, single-digit ms). Single `asyncio.Lock` serialises all DB writes.

**When to use:** Every embed call in `EmbeddingGenerator` goes through this service before hitting the provider API.

**Example:**
```python
# agent_brain_server/services/embedding_cache.py
# Source: established project patterns (ManifestTracker, FolderManager)

import asyncio
import hashlib
import logging
import struct
import time
from collections import OrderedDict
from pathlib import Path

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

_MEM_LRU_DEFAULT = 1_000   # entries
_MAX_DISK_MB_DEFAULT = 500


class EmbeddingCacheService:
    """Two-layer embedding cache: in-memory LRU + aiosqlite disk.

    Cache key: SHA-256(content_text) + ":" + provider + ":" + model + ":" + str(dims)
    Embeddings stored as float32 BLOB (12 KB per 3072-dim vector).
    Provider fingerprint stored in metadata table for startup auto-wipe.
    """

    def __init__(
        self,
        db_path: Path,
        max_mem_entries: int = _MEM_LRU_DEFAULT,
        max_disk_mb: int = _MAX_DISK_MB_DEFAULT,
        persist_stats: bool = False,  # persist hit/miss counters across restarts
    ) -> None:
        self.db_path = db_path
        self.max_mem_entries = max_mem_entries
        self.max_disk_mb = max_disk_mb
        self.persist_stats = persist_stats

        self._lock = asyncio.Lock()
        self._mem: OrderedDict[str, list[float]] = OrderedDict()

        # Runtime counters (always in-process; optionally also persisted)
        self._hits = 0
        self._misses = 0

    async def initialize(self, provider_fingerprint: str) -> None:
        """Open DB, create schema, auto-wipe on fingerprint mismatch."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(_SCHEMA)
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA busy_timeout=5000")
            await db.commit()

            # Provider fingerprint check
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
                    f"Embedding provider changed "
                    f"(was {row[0]!r}, now {provider_fingerprint!r}). "
                    "Clearing embedding cache."
                )
                await db.execute("DELETE FROM embeddings")
                await db.execute(
                    "UPDATE metadata SET value = ? "
                    "WHERE key = 'provider_fingerprint'",
                    (provider_fingerprint,),
                )
                await db.commit()
                self._mem.clear()

        logger.info(
            f"EmbeddingCacheService initialized: {self.db_path}, "
            f"mem={self.max_mem_entries} entries, disk={self.max_disk_mb} MB"
        )

    @staticmethod
    def make_cache_key(text: str, provider: str, model: str, dimensions: int) -> str:
        """Compute deterministic cache key."""
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{content_hash}:{provider}:{model}:{dimensions}"

    async def get(self, cache_key: str) -> list[float] | None:
        """Look up embedding. Returns None on miss."""
        # Check in-memory LRU first (no lock needed for read — single asyncio thread)
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

        # Update last_accessed asynchronously (fire-and-forget under lock)
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute(
                    "UPDATE embeddings SET last_accessed = ? WHERE cache_key = ?",
                    (time.time(), cache_key),
                )
                await db.commit()

        self._hits += 1
        return embedding

    async def put(self, cache_key: str, embedding: list[float]) -> None:
        """Store embedding. Evicts LRU entries if disk limit exceeded."""
        dims = len(embedding)
        blob = struct.pack(f"{dims}f", *embedding)
        now = time.time()

        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA synchronous=NORMAL")
                await db.execute(
                    "INSERT OR REPLACE INTO embeddings "
                    "(cache_key, embedding, provider, model, dimensions, last_accessed) "
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
        """LRU eviction when DB size exceeds max_disk_mb (called under lock)."""
        cur = await db.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
        row = await cur.fetchone()
        if row is None:
            return
        size_bytes = row[0]
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
        """Clear all cached embeddings. Returns (count, size_bytes)."""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                cur = await db.execute("SELECT COUNT(*) FROM embeddings")
                row = await cur.fetchone()
                count = row[0] if row else 0
                # Get size before delete
                cur2 = await db.execute(
                    "SELECT page_count * page_size "
                    "FROM pragma_page_count(), pragma_page_size()"
                )
                size_row = await cur2.fetchone()
                size_bytes = size_row[0] if size_row else 0
                await db.execute("DELETE FROM embeddings")
                await db.commit()
        self._mem.clear()
        self._hits = 0
        self._misses = 0
        return count, size_bytes

    def get_stats(self) -> dict[str, object]:
        """Return current hit/miss counters and entry count."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "mem_entries": len(self._mem),
        }

    async def get_disk_stats(self) -> dict[str, object]:
        """Return disk-level stats (entry count, DB size)."""
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute("SELECT COUNT(*) FROM embeddings")
            row = await cur.fetchone()
            count = row[0] if row else 0
            cur2 = await db.execute(
                "SELECT page_count * page_size "
                "FROM pragma_page_count(), pragma_page_size()"
            )
            size_row = await cur2.fetchone()
            size_bytes = size_row[0] if size_row else 0
        return {"entry_count": count, "size_bytes": size_bytes}


# Module-level singleton
_embedding_cache: EmbeddingCacheService | None = None


def get_embedding_cache() -> EmbeddingCacheService | None:
    """Get global cache instance (None if not initialized)."""
    return _embedding_cache


def set_embedding_cache(cache: EmbeddingCacheService) -> None:
    """Set global cache instance (called from lifespan)."""
    global _embedding_cache
    _embedding_cache = cache


def reset_embedding_cache() -> None:
    """Reset global cache instance (for testing)."""
    global _embedding_cache
    _embedding_cache = None
```

### Pattern 2: EmbeddingGenerator Cache Interception

**What:** Wrap `embed_text()` and `embed_texts()` in `EmbeddingGenerator` with cache check-then-store logic. The cache is injected optionally, so the generator still works without a cache (backward compat for tests).

**When to use:** All embed paths go through EmbeddingGenerator, making it the correct single intercept point.

**Example:**
```python
# agent_brain_server/indexing/embedding.py — modified embed_text + embed_texts
# Source: existing codebase pattern

from agent_brain_server.services.embedding_cache import get_embedding_cache

async def embed_text(self, text: str) -> list[float]:
    """Generate embedding for a single text (cache-intercepted)."""
    cache = get_embedding_cache()
    if cache is not None:
        key = EmbeddingCacheService.make_cache_key(
            text,
            self._embedding_provider.provider_name,
            self._embedding_provider.model_name,
            self._embedding_provider.get_dimensions(),
        )
        cached = await cache.get(key)
        if cached is not None:
            return cached
        result = await self._embedding_provider.embed_text(text)
        await cache.put(key, result)
        return result
    return await self._embedding_provider.embed_text(text)

async def embed_texts(
    self,
    texts: list[str],
    progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
) -> list[list[float]]:
    """Batch embed with cache: check all, call API only for misses, store results."""
    cache = get_embedding_cache()
    if cache is None:
        return await self._embedding_provider.embed_texts(texts, progress_callback)

    dims = self._embedding_provider.get_dimensions()
    provider = self._embedding_provider.provider_name
    model = self._embedding_provider.model_name

    # Batch lookup
    keys = [EmbeddingCacheService.make_cache_key(t, provider, model, dims) for t in texts]
    results: list[list[float] | None] = [await cache.get(k) for k in keys]

    # Find misses
    miss_indices = [i for i, r in enumerate(results) if r is None]
    if miss_indices:
        miss_texts = [texts[i] for i in miss_indices]
        miss_embeddings = await self._embedding_provider.embed_texts(
            miss_texts, progress_callback
        )
        for idx, embedding in zip(miss_indices, miss_embeddings):
            results[idx] = embedding
            await cache.put(keys[idx], embedding)

    return [r for r in results if r is not None]  # type: ignore[misc]
```

### Pattern 3: Provider Fingerprint Construction

**What:** Build a stable fingerprint string from provider config for auto-wipe detection.

**Example:**
```python
# In api/main.py lifespan — build fingerprint before initializing cache
from agent_brain_server.config.provider_config import load_provider_settings
from agent_brain_server.providers.factory import ProviderRegistry

def _build_provider_fingerprint() -> str:
    """Build provider:model:dimensions fingerprint for cache invalidation."""
    ps = load_provider_settings()
    provider = ProviderRegistry.get_embedding_provider(ps.embedding)
    dims = provider.get_dimensions()
    return f"{ps.embedding.provider}:{ps.embedding.model}:{dims}"
```

### Pattern 4: CLI `cache` Command Group

**What:** Click command group following the `folders_group` / `jobs_command` pattern. Adds `cache status` and `cache clear` subcommands.

**Example:**
```python
# agent_brain_cli/commands/cache.py
import click
from rich.console import Console
from rich.prompt import Confirm
from ..client import ConnectionError, DocServeClient, ServerError
from ..config import get_server_url

console = Console()

@click.group("cache")
def cache_group() -> None:
    """Manage the embedding cache."""
    pass

@cache_group.command("status")
@click.option("--url", envvar="AGENT_BRAIN_URL", default=None)
@click.option("--json", "json_output", is_flag=True)
def cache_status_command(url: str | None, json_output: bool) -> None:
    """Show embedding cache statistics."""
    resolved_url = url or get_server_url()
    with DocServeClient(base_url=resolved_url) as client:
        stats = client.cache_status()
        # ... render with Rich table

@cache_group.command("clear")
@click.option("--url", envvar="AGENT_BRAIN_URL", default=None)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def cache_clear_command(url: str | None, yes: bool) -> None:
    """Flush all cached embeddings."""
    resolved_url = url or get_server_url()
    with DocServeClient(base_url=resolved_url) as client:
        # Get count first for prompt
        stats = client.cache_status()
        count = stats.entry_count
        if not yes:
            if not Confirm.ask(
                f"This will flush {count:,} cached embeddings. Continue?"
            ):
                console.print("[dim]Aborted.[/]")
                return
        result = client.clear_cache()
        console.print(
            f"[green]Cleared {result['count']:,} cached embeddings "
            f"({result['size_mb']:.1f} MB freed)[/]"
        )
```

### Pattern 5: API Endpoints for Cache

**What:** Two new HTTP endpoints for the cache, added to an existing or new router:

- `GET /index/cache/status` — returns cache stats (hits, misses, entry_count, size_bytes)
- `DELETE /index/cache` — clears all cache entries

These follow the existing `/index/jobs` pattern (jobs_router). The cache router can be a minimal addition to the index router file or its own `cache_router`.

### Pattern 6: Storage Path Addition

**What:** Add `embedding_cache` subdirectory to `SUBDIRECTORIES` list in `storage_paths.py` and to `resolve_storage_paths()`.

**Example:**
```python
# storage_paths.py
SUBDIRECTORIES = [
    "data",
    "data/chroma_db",
    "data/bm25_index",
    "data/llamaindex",
    "data/graph_index",
    "logs",
    "manifests",
    "embedding_cache",   # NEW — Phase 16
]

# resolve_storage_paths also gets:
"embedding_cache": state_dir / "embedding_cache",
```

The SQLite DB file path: `storage_paths["embedding_cache"] / "embeddings.db"`

### Anti-Patterns to Avoid

- **Opening a new `aiosqlite.connect()` per call without WAL mode:** Without `PRAGMA journal_mode=WAL`, concurrent readers block on the writer. Always set WAL on every connection open (it persists in the DB file, but setting it is idempotent and cheap).
- **Using `json.dumps(embedding)` for BLOB storage:** JSON is 5× larger and slower. Use `struct.pack(f"{N}f", *embedding)` for float32 (verified: cosine similarity is unaffected, max error ~3.57e-9).
- **Single asyncio.Lock for read operations:** Reads do NOT need the write lock in WAL mode. Only writes need the lock to prevent write-write conflicts. Holding the lock during reads degrades concurrency.
- **Calling `embed_texts()` with all texts sequentially to check cache:** The correct pattern is batch-lookup all keys, identify misses, then issue a single `embed_texts()` call for the miss batch — preserving the provider's batch efficiency.
- **Storing raw Python `list[float]` in memory LRU with `copy.deepcopy`:** Not needed. Embeddings are immutable after creation. Store the list directly.
- **Circular import via `get_embedding_cache()` in embedding.py:** Use the module-level singleton pattern (`from agent_brain_server.services.embedding_cache import get_embedding_cache`) with a `TYPE_CHECKING` guard if needed. No circular import risk here since `embedding_cache.py` does not import from `embedding.py`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async SQLite access | Custom thread-pool SQLite wrapper | `aiosqlite` 0.22.0 (already installed) | aiosqlite runs SQLite in a background thread with async interface; WAL mode handles concurrent read/write |
| LRU eviction in memory | Custom doubly-linked list | `collections.OrderedDict` | `move_to_end()` + `popitem(last=False)` implements O(1) LRU; zero deps |
| Float vector serialization | Custom text format | `struct.pack(f"{N}f", *vec)` | float32 BLOB is 12 KB for 3072-dim; verified precision adequate for cosine similarity |
| Provider change detection | Compare each cached entry's provider | Single metadata row in SQLite | One row lookup on startup, O(1); per-entry check would be O(N) |

**Key insight:** SQLite with WAL mode handles the concurrent read-while-writing pattern perfectly, which is exactly what happens during indexing (writes) while queries are served (reads). No custom locking beyond write serialization is required.

---

## Common Pitfalls

### Pitfall 1: aiosqlite Page Size vs Entry Count for Disk Limit
**What goes wrong:** `SELECT COUNT(*) * avg_entry_size` underestimates actual DB size because SQLite page fragmentation can waste space. Using page_count × page_size is accurate.
**Why it happens:** SQLite allocates pages, and deleted entries leave free pages until `VACUUM` is run.
**How to avoid:** Use `SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()` for accurate size checks. Run `VACUUM` in the `clear()` method to reclaim space after bulk delete.
**Warning signs:** Disk limit eviction not triggering as expected; DB file larger than expected after clear.

### Pitfall 2: WAL Mode Must Be Set Per Connection
**What goes wrong:** Opening a new connection without setting `PRAGMA journal_mode=WAL` causes the connection to use rollback journal mode, degrading concurrent performance.
**Why it happens:** WAL mode is stored in the DB file, but each new connection still needs to activate it with a PRAGMA call (it's idempotent).
**How to avoid:** Set `PRAGMA journal_mode=WAL` immediately after `aiosqlite.connect()` in every connection open. Also set `PRAGMA busy_timeout=5000` to avoid immediate `OperationalError: database is locked` on contention.
**Warning signs:** `OperationalError: database is locked` in tests with concurrent connections.

### Pitfall 3: In-Memory LRU Not Synchronized with Disk Eviction
**What goes wrong:** Disk LRU eviction deletes entries from SQLite, but the in-memory dict still has them. A subsequent cache.get() returns the in-memory copy even though the disk entry is gone — not harmful in normal operation but confusing in tests.
**Why it happens:** The in-memory LRU and disk LRU are independently managed.
**How to avoid:** For the `clear()` path, clear both. For disk-only eviction (size limit), the in-memory entries for evicted keys will naturally expire from the `OrderedDict` as new entries push them out — this is acceptable behavior.
**Warning signs:** Test assertions checking that cache is empty after `clear()` fail because `_mem` still has entries.

### Pitfall 4: Cache Key Collision Between Text Chunks and Queries
**What goes wrong:** `embed_query()` and `embed_text()` use the same cache key format. This is intentional and correct — if a query text happens to match an indexed chunk exactly, it should reuse the cached embedding. However, tests that mock `embed_query` separately may not realize cache is shared.
**Why it happens:** The cache key is purely content-based; it does not distinguish "chunk" from "query" use.
**How to avoid:** This is the intended behavior — document it. Tests that mock embedding calls must account for cache hits returning before the mock is called.
**Warning signs:** Tests that assert mock was called fail because cache hit occurred first.

### Pitfall 5: Float32 Precision Misunderstanding
**What goes wrong:** Developer switches storage to float64 "for correctness," doubling disk usage and halving capacity.
**Why it happens:** float64 is Python's default float type; it feels more correct.
**How to avoid:** Verified: float32 cosine similarity vs float64 is 1.0000000000 (max error 3.57e-9). Document this in the service class. float32 doubles capacity (42K entries vs 21K at 500MB).
**Warning signs:** `struct.pack('Xd', ...)` in code instead of `struct.pack('Xf', ...)`.

### Pitfall 6: `embed_texts()` Batch Lookup Sequential Await
**What goes wrong:** `[await cache.get(k) for k in keys]` runs N sequential DB lookups when most are cache misses, adding latency.
**Why it happens:** Naive translation of "check cache for each text."
**How to avoid:** For large miss ratios (e.g., first indexing run), the sequential lookups add overhead. Optimization: batch the DB query with `SELECT cache_key, embedding, dimensions FROM embeddings WHERE cache_key IN (?, ?, ...)`. Implement this in a `get_batch()` method. For the MVP, sequential is acceptable; flag for optimization if profiling shows it matters.
**Warning signs:** First indexing run is slower with cache enabled than without.

### Pitfall 7: lifespan Initialization Order
**What goes wrong:** `EmbeddingCacheService` initialized after `IndexingService`, meaning the first embed call (if any happens during startup) misses the cache.
**Why it happens:** lifespan initializes services sequentially; cache must be in-place before any embed call.
**How to avoid:** Initialize `EmbeddingCacheService` and call `set_embedding_cache()` BEFORE initializing `IndexingService` and `QueryService` in the lifespan. The singleton pattern ensures `get_embedding_cache()` in `EmbeddingGenerator` finds the instance.
**Warning signs:** First indexing job after startup shows 100% miss rate even on second run.

---

## Code Examples

Verified patterns from project codebase and verified aiosqlite experiments.

### aiosqlite WAL Mode (VERIFIED working)
```python
# Verified: WAL mode confirmed via PRAGMA journal_mode query
async with aiosqlite.connect(db_path) as db:
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA synchronous=NORMAL")   # Faster than FULL, safe with WAL
    await db.execute("PRAGMA busy_timeout=5000")    # Wait up to 5s on lock contention
    await db.commit()
# Result: ('wal',) — confirmed working
```

### float32 BLOB Round-Trip (VERIFIED working)
```python
import struct

# Encode
dims = len(embedding)
blob = struct.pack(f"{dims}f", *embedding)   # ~12 KB for 3072-dim

# Decode
embedding = list(struct.unpack(f"{dims}f", blob))
# Precision: cosine_similarity(original, recovered) = 1.0000000000
# Max error per element: ~3.57e-9 — negligible for similarity search
```

### SHA-256 Cache Key Construction
```python
import hashlib

def make_cache_key(text: str, provider: str, model: str, dimensions: int) -> str:
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{content_hash}:{provider}:{model}:{dimensions}"

# Example: "a3f9...7b2e:openai:text-embedding-3-large:3072"
# SHA-256 hex is 64 chars; total key ~80 chars — well within SQLite TEXT limits
```

### OrderedDict LRU Pattern (stdlib, zero deps)
```python
from collections import OrderedDict

mem: OrderedDict[str, list[float]] = OrderedDict()
MAX_MEM = 1_000

# Get (O(1))
if key in mem:
    mem.move_to_end(key)
    return mem[key]

# Put (O(1))
mem[key] = value
mem.move_to_end(key)
if len(mem) > MAX_MEM:
    mem.popitem(last=False)  # Remove least-recently-used
```

### Concurrent WAL Read/Write (VERIFIED working)
```python
# Tested: concurrent writer + reader tasks with WAL mode
# Result: [None, [2, 4, 6, 8, 10]] — reads succeed while writes are in progress
# No OperationalError: database is locked with WAL + busy_timeout=5000
```

### Batch Lookup (Optimization — use for embed_texts)
```python
async def get_batch(
    self, cache_keys: list[str]
) -> dict[str, list[float]]:
    """Batch lookup. Returns only cache hits."""
    if not cache_keys:
        return {}
    placeholders = ",".join("?" * len(cache_keys))
    async with aiosqlite.connect(self.db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        cur = await db.execute(
            f"SELECT cache_key, embedding, dimensions "
            f"FROM embeddings WHERE cache_key IN ({placeholders})",
            cache_keys,
        )
        rows = await cur.fetchall()
    result = {}
    for cache_key, blob, dims in rows:
        result[cache_key] = list(struct.unpack(f"{dims}f", blob))
    return result
```

### settings.py Additions
```python
# In agent_brain_server/config/settings.py — add to Settings class

# Embedding Cache Configuration (Phase 16)
EMBEDDING_CACHE_MAX_DISK_MB: int = 500    # Max disk size in MB
EMBEDDING_CACHE_MAX_MEM_ENTRIES: int = 1_000  # In-memory LRU size
EMBEDDING_CACHE_PERSIST_STATS: bool = False  # Persist hit/miss across restarts
```

### IndexingStatus Model Addition
```python
# In agent_brain_server/models/health.py — add field to IndexingStatus

# Embedding cache status (Phase 16)
embedding_cache: dict[str, Any] | None = Field(
    default=None,
    description=(
        "Embedding cache status with hits, misses, hit_rate, entry_count, "
        "size_bytes. Omitted for fresh installs with empty cache."
    ),
)
```

### lifespan Initialization Snippet
```python
# In api/main.py lifespan — after storage initialization, BEFORE IndexingService

from agent_brain_server.services.embedding_cache import (
    EmbeddingCacheService,
    set_embedding_cache,
)

# Initialize embedding cache service (Phase 16)
if storage_paths:
    cache_db_path = storage_paths["embedding_cache"] / "embeddings.db"
else:
    import tempfile
    cache_db_path = Path(tempfile.mkdtemp(prefix="agent-brain-cache-")) / "embeddings.db"

provider_fingerprint = _build_provider_fingerprint()
embedding_cache = EmbeddingCacheService(
    db_path=cache_db_path,
    max_mem_entries=settings.EMBEDDING_CACHE_MAX_MEM_ENTRIES,
    max_disk_mb=settings.EMBEDDING_CACHE_MAX_DISK_MB,
    persist_stats=settings.EMBEDDING_CACHE_PERSIST_STATS,
)
await embedding_cache.initialize(provider_fingerprint)
set_embedding_cache(embedding_cache)
app.state.embedding_cache = embedding_cache
logger.info("Embedding cache service initialized")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No caching — every embed call hits OpenAI API | Two-layer cache (mem LRU + aiosqlite disk) | Phase 16 | Zero API cost for unchanged content on re-index |
| ManifestTracker only prevents re-chunking/indexing | Cache also prevents re-embedding already-seen text chunks | Phase 16 | Complements ManifestTracker: manifest skips unchanged files entirely, cache handles cases where file metadata changed but content didn't |

**Note:** ManifestTracker (Phase 14) and EmbeddingCacheService are complementary, not redundant. ManifestTracker skips entire files when mtime + SHA-256 match. EmbeddingCacheService handles the case where chunks are re-extracted but their text content hasn't changed — a case that can occur when chunk boundaries shift due to file structure changes. The cache also benefits `embed_query()` for repeated queries.

---

## Open Questions

1. **Batch `get_batch()` vs sequential `get()` in `embed_texts()`**
   - What we know: Sequential is simpler to implement; batch SQL is more efficient for large miss ratios.
   - What's unclear: Whether first-run overhead of sequential lookups is measurable in practice (each is a local SQLite read, not a network call).
   - Recommendation: Implement `get_batch()` from the start since it's not significantly more complex and avoids the N-sequential-await pattern.

2. **Persistent hit/miss stats default: session vs persistent**
   - What we know: `persist_stats: bool = False` is Claude's discretion.
   - Recommendation: Default `False` (session-only). Persistent stats require an extra metadata row update on every cache hit, adding write contention. Session stats are sufficient for monitoring; the value resets on restart, which is acceptable since the cache itself persists.

3. **In-memory LRU size default: 1,000 entries**
   - What we know: 1,000 float32 3072-dim vectors = ~12 MB in-process; this is reasonable for a server process.
   - Recommendation: 1,000 entries is the right default. Configurable via `EMBEDDING_CACHE_MAX_MEM_ENTRIES`.

4. **`clear()` + `VACUUM` behavior**
   - What we know: After `DELETE FROM embeddings`, SQLite does not immediately reclaim disk space — pages are marked free. `VACUUM` rewrites the DB file to reclaim space.
   - Recommendation: Run `await db.execute("VACUUM")` inside `clear()` after the delete. Report the pre-vacuum size as "freed."

---

## Sources

### Primary (HIGH confidence)
- Codebase direct read: `agent_brain_server/indexing/embedding.py` — EmbeddingGenerator methods and singleton pattern
- Codebase direct read: `agent_brain_server/services/manifest_tracker.py` — SHA-256 hashing, atomic write, asyncio.Lock pattern
- Codebase direct read: `agent_brain_server/services/folder_manager.py` — in-memory dict + async persistence two-layer pattern
- Codebase direct read: `agent_brain_server/providers/factory.py` — `f"embed:{provider_type}:{config.model}"` cache key format
- Codebase direct read: `agent_brain_server/api/main.py` — lifespan initialization order, app.state pattern
- Codebase direct read: `agent_brain_server/config/settings.py` — BaseSettings pattern for new env vars
- Codebase direct read: `agent_brain_server/models/health.py` — IndexingStatus extension pattern (file_watcher added in Phase 15)
- Codebase direct read: `agent_brain_server/api/routers/health.py` — how Phase 15 file_watcher section was added
- Codebase direct read: `agent_brain_cli/commands/reset.py` — `--yes` flag pattern for destructive operations
- Codebase direct read: `agent_brain_server/storage_paths.py` — SUBDIRECTORIES and resolve_storage_paths pattern
- Verified experiment: aiosqlite WAL mode — `PRAGMA journal_mode=WAL` returns `('wal',)`, concurrent read/write works
- Verified experiment: float32 BLOB round-trip — cosine_similarity = 1.0000000000, max error 3.57e-9
- Verified experiment: float32 = 12 KB/entry (3072-dim), float64 = 24 KB/entry; 500MB holds ~42K float32 entries
- `aiosqlite` version: 0.22.0 installed as transitive dep (confirmed via `.venv/lib/python3.10/site-packages/`)

### Secondary (MEDIUM confidence)
- Python docs `collections.OrderedDict.move_to_end()` — O(1) LRU eviction via `last=False` popitem
- SQLite docs: WAL mode allows concurrent readers while writer holds write lock; `PRAGMA busy_timeout` avoids immediate lock errors

### Tertiary (LOW confidence — not needed for this phase)
- None applicable

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — aiosqlite already installed and verified working; stdlib only; no new deps
- Architecture: HIGH — directly mirrored from existing ManifestTracker + FolderManager patterns in codebase
- Pitfalls: HIGH — verified via direct code experiments (WAL mode, float32 precision, concurrent access)

**Research date:** 2026-03-10
**Valid until:** 2026-06-10 (stable SQLite + Python stdlib domain; aiosqlite API is stable)
