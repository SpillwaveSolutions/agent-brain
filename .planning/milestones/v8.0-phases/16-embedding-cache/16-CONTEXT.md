# Phase 16: Embedding Cache - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Users pay zero OpenAI API cost for unchanged content on any reindex run triggered by the watcher or manually. An aiosqlite-backed embedding cache with content-hash + provider:model:dimensions key prevents redundant API calls. Cache survives server restarts, auto-invalidates on provider/model change, and exposes hit/miss metrics.

</domain>

<decisions>
## Implementation Decisions

### Cache Metrics & Status Display
- Metrics configurable: cumulative per session or persistent across restarts (Claude decides default, makes it configurable)
- Summary line in `agent-brain status` by default: entry count, hit rate, hits, misses
- Detailed section via `agent-brain status --verbose` or `--json`: adds DB size on disk, provider:model fingerprint, cache age
- `/health/status` API includes `embedding_cache` section only when cache has entries (omit for fresh installs)

### Cache Clear Behavior
- `agent-brain cache` is a command group with subcommands: `cache clear`, `cache status`
- `agent-brain cache clear` requires `--yes` flag (matches `agent-brain reset --yes` pattern)
- Without `--yes`, prompt: "This will flush N cached embeddings. Continue? [y/N]"
- Cache clearing allowed while indexing jobs are running — running jobs will regenerate embeddings (costs API calls, no corruption)
- Feedback after clear: "Cleared 1,234 cached embeddings (45.2 MB freed)" — show count + size

### Provider/Model Change Handling
- Silent auto-wipe on server startup when provider:model:dimensions mismatch detected
- Server logs info message about wipe but no user-facing warning
- Cache key includes provider + model + dimensions_override — catches edge case of same model with different dimension configs

### Cache Size & Eviction Policy
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

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EmbeddingGenerator` (`indexing/embedding.py`): Singleton facade with `embed_text()`, `embed_texts()`, `embed_chunks()`, `embed_query()` — primary integration point for cache intercept
- `ManifestTracker` SHA-256 hashing: Content hash already computed during indexing — reusable as cache key component
- `FolderManager._cache` pattern: In-memory dict + async JSONL persistence with `asyncio.Lock` — similar two-layer approach
- `ProviderRegistry` cache keys: Already uses `f"embed:{provider_type}:{config.model}"` format — reuse for cache fingerprint

### Established Patterns
- `@lru_cache` + `clear_*_cache()` for singleton services — cache service follows same pattern
- Atomic temp + `Path.replace()` for disk writes — established safe write pattern
- Module-level singleton with `get_*()` / `reset_*()` functions — cache service follows same lifecycle
- `pydantic_settings.BaseSettings` for env var config — add `EMBEDDING_CACHE_*` vars here

### Integration Points
- `EmbeddingGenerator.embed_text()` / `embed_texts()` (embedding.py:88-115): Intercept before delegating to provider — check cache first, store result after
- `EmbeddingGenerator.embed_query()` (embedding.py:132): Query embeddings also cacheable
- `IndexingService._validate_embedding_compatibility()` (indexing_service.py:201): Already validates provider/model — cache can read same config
- `api/main.py` lifespan: Initialize/cleanup cache service alongside other services
- `/health/status` endpoint (health.py:109): Add `embedding_cache` section to `IndexingStatus` response
- `DocServeClient` (api_client.py): Add `clear_cache()` and `cache_status()` methods for CLI
- `cli.py` command registration: Add `cache` group alongside `folders`, `jobs`, etc.
- `provider_config.py`: `EmbeddingConfig` has `provider`, `model`, and dimension info for fingerprint

</code_context>

<specifics>
## Specific Ideas

- Cache key is `SHA-256(content) + provider:model:dimensions` — three-part fingerprint prevents any dimension mismatch
- 500 MB default disk limit is ~40K entries for text-embedding-3-large (3072-dim × 4 bytes × 40K ≈ 470MB)
- Two-layer architecture: memory LRU for hot path (sub-ms), aiosqlite disk for persistence (single-digit ms)
- `agent-brain cache status` provides quick view without needing full `agent-brain status`
- Provider change detection on startup uses metadata row comparison — simple and reliable

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-embedding-cache*
*Context gathered: 2026-03-09*
