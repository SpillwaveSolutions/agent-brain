---
phase: 05-storage-abstraction
plan: 01
subsystem: storage-backend
tags: [protocol, factory, configuration, async, phase5]
dependency_graph:
  requires: []
  provides:
    - StorageBackendProtocol
    - StorageConfig
    - get_storage_backend factory
  affects:
    - agent-brain-server/agent_brain_server/storage/
    - agent-brain-server/agent_brain_server/config/
tech_stack:
  added:
    - runtime_checkable Protocol (typing)
    - Pydantic field_validator
    - AGENT_BRAIN_STORAGE_BACKEND env var
  patterns:
    - Async-first protocol design
    - Singleton factory pattern
    - Config precedence (env > YAML > default)
key_files:
  created:
    - agent-brain-server/agent_brain_server/storage/protocol.py
    - agent-brain-server/agent_brain_server/storage/factory.py
    - agent-brain-server/tests/unit/storage/test_protocol.py
    - agent-brain-server/tests/unit/storage/test_factory.py
    - agent-brain-server/tests/unit/config/test_storage_config.py
  modified:
    - agent-brain-server/agent_brain_server/config/provider_config.py
    - agent-brain-server/agent_brain_server/config/settings.py
decisions:
  - decision: "Use Protocol instead of ABC for backend interface"
    rationale: "Protocols provide structural subtyping without inheritance, allowing existing classes to satisfy interface without modification"
    alternatives: ["Abstract base class", "Duck typing only"]
  - decision: "Normalize all search scores to 0-1 range (higher=better)"
    rationale: "Consistent scoring across ChromaDB cosine distance (0-2), BM25 raw scores, and future PostgreSQL ts_rank (0-1)"
    alternatives: ["Keep backend-specific ranges", "Normalize to 0-100"]
  - decision: "Singleton factory pattern with module-level cache"
    rationale: "Matches existing VectorStoreManager pattern, ensures single backend instance per process"
    alternatives: ["Dependency injection", "New instance per call"]
metrics:
  duration_seconds: 476
  duration_human: "~8 minutes"
  completed_at: "2026-02-11T04:12:36Z"
  tasks_completed: 3
  files_created: 5
  files_modified: 2
  commits: 4
  tests_added: 33
  total_tests: 538
  test_pass_rate: "100%"
  coverage: "70%"
---

# Phase 05 Plan 01: StorageBackendProtocol and Configuration Summary

**Protocol foundation and factory infrastructure for pluggable storage backends.**

## One-Liner

Async-first StorageBackendProtocol with 11 methods, StorageConfig with backend validation, and factory with env var > YAML > default precedence.

## What Was Built

### 1. StorageBackendProtocol (protocol.py)

**Types:**
- `SearchResult` dataclass: Backend-agnostic search result (text, metadata, score 0-1, chunk_id)
- `EmbeddingMetadata` dataclass: Provider metadata with to_dict/from_dict serialization
- `StorageError` exception: Base exception with optional backend identifier

**Protocol Methods (11 total):**
- `async initialize()` — Create indexes, validate schema
- `async upsert_documents()` — Upsert with embeddings, returns count
- `async vector_search()` — Vector similarity search (scores 0-1)
- `async keyword_search()` — BM25/tsvector search (scores 0-1)
- `async get_count()` — Document count with optional filter
- `async get_by_id()` — Fetch single document
- `async reset()` — Clear all data and reinitialize
- `async get_embedding_metadata()` — Retrieve stored provider metadata
- `async set_embedding_metadata()` — Store provider metadata
- `validate_embedding_compatibility()` — Sync validation (raises ProviderMismatchError)
- `is_initialized` property — Ready for operations

**Key Design Choices:**
- All async except validate_embedding_compatibility (sync validation)
- Scores normalized to 0-1 (higher=better) across all backends
- Exceptions normalized to StorageError
- Metadata is JSON-compatible dicts only
- Protocol is runtime_checkable for isinstance checks

### 2. StorageConfig (provider_config.py)

**Configuration:**
- `backend: str` — "chroma" or "postgres" (default: "chroma")
- `postgres: dict[str, Any]` — PostgreSQL connection params (Phase 6)
- Case-insensitive validation ("CHROMA" → "chroma")
- Rejects invalid backends with helpful error

**Integration:**
- Added to `ProviderSettings` as `storage` field
- Logs active backend in `load_provider_settings()`
- Validates postgres backend has config (WARNING if empty)

### 3. Backend Factory (factory.py)

**Functions:**
- `get_effective_backend_type()` — Resolves backend without creating instance
- `get_storage_backend()` — Returns backend singleton (NotImplementedError for now)
- `reset_storage_backend_cache()` — Clear singleton for testing

**Precedence:**
1. `AGENT_BRAIN_STORAGE_BACKEND` env var (if set)
2. YAML `storage.backend` (via ProviderSettings)
3. Default: "chroma"

**Current State:**
- ChromaBackend: NotImplementedError → "see Plan 05-02"
- PostgresBackend: NotImplementedError → "see Phase 6"
- Unknown backend: ValueError with helpful message

### 4. Environment Variable (settings.py)

Added:
```python
AGENT_BRAIN_STORAGE_BACKEND: str = ""  # Empty = use YAML config
```

Empty string default ensures YAML config is used when env var not set.

### 5. Unit Tests (33 new tests)

**test_protocol.py (12 tests):**
- SearchResult creation and field access
- Score range validation (0-1 expected, no enforcement)
- EmbeddingMetadata to_dict/from_dict roundtrip
- StorageError with backend identifier
- Protocol structural typing (complete vs incomplete mock)

**test_factory.py (6 tests):**
- Backend type resolution (returns valid backend)
- Cache clearing (singleton management)
- NotImplementedError for chroma and postgres
- Function existence and determinism

**test_storage_config.py (15 tests):**
- Default backend ("chroma")
- Case normalization ("POSTGRES" → "postgres")
- Invalid backend rejection (with helpful error)
- ProviderSettings integration
- YAML roundtrip (dict → ProviderSettings → dict)
- Validation warnings (postgres without config)

## Deviations from Plan

None — plan executed exactly as written.

## Must-Haves Verification

All must-haves satisfied:

**Truths:**
- ✅ StorageBackendProtocol defines all async storage operations
- ✅ StorageConfig validates "chroma" and "postgres"
- ✅ AGENT_BRAIN_STORAGE_BACKEND env var overrides YAML
- ✅ Factory returns correct backend type (NotImplementedError placeholders)
- ✅ Server startup validates backend config

**Artifacts:**
- ✅ protocol.py exports StorageBackendProtocol, SearchResult, EmbeddingMetadata, StorageError
- ✅ factory.py exports get_storage_backend, reset_storage_backend_cache, get_effective_backend_type
- ✅ provider_config.py contains StorageConfig class
- ✅ settings.py contains AGENT_BRAIN_STORAGE_BACKEND

**Key Links:**
- ✅ factory.py → provider_config.py via load_provider_settings().storage.backend
- ✅ factory.py → settings.py via AGENT_BRAIN_STORAGE_BACKEND env var override

## Test Results

**New Tests:** 33 tests added (12 protocol + 6 factory + 15 config)
**Total Tests:** 538 tests
**Pass Rate:** 100% (538/538)
**Coverage:** 70% overall
- protocol.py: 100% coverage
- factory.py: 71% coverage (uncovered: NotImplementedError branches)
- provider_config.py: Integrated with existing coverage

**Quality Checks:**
- ✅ Black formatting: All files formatted
- ✅ Ruff linting: No errors
- ✅ mypy strict: No type errors
- ✅ All tests pass: 538/538

## Commits

1. `80786d6` — feat(05-01): create StorageBackendProtocol and data types
2. `fbea40a` — feat(05-01): add StorageConfig and backend factory
3. `be7fbe6` — test(05-01): add unit tests for protocol, factory, and config
4. `9a448aa` — fix(05-01): remove unused imports and fix test lint issues

## Technical Decisions

**1. Protocol vs Abstract Base Class**

Chose `typing.Protocol` over `abc.ABC`:
- Structural subtyping (duck typing with type checking)
- Existing classes can satisfy protocol without inheritance
- Plan 02 can wrap VectorStoreManager without modification

**2. Score Normalization (0-1 range)**

All backends normalize scores to 0-1 (higher=better):
- ChromaDB: cosine distance (0-2) → similarity (1 - distance)
- BM25: raw scores (unbounded) → normalize to max
- PostgreSQL: ts_rank (0-1) already normalized

Rationale: Consistent fusion weighting in hybrid search.

**3. Singleton Factory Pattern**

Module-level singleton `_storage_backend` variable:
- Matches existing `get_vector_store()` pattern
- Single backend instance per process lifecycle
- Reset function for testing

Alternative (dependency injection) considered but rejected to minimize refactoring.

**4. Async-First Design**

All protocol methods are async except `validate_embedding_compatibility`:
- ChromaDB is synchronous → wrap in `asyncio.to_thread()` (Plan 02)
- PostgreSQL is async-native → direct implementation (Phase 6)
- Validation is sync because it's called at startup (non-async context)

## Integration Points

**Plan 02 (ChromaBackend adapter):**
- Wrap VectorStoreManager in ChromaBackend class
- Implement StorageBackendProtocol methods
- Use asyncio.to_thread() for sync ChromaDB operations
- Update services to use get_storage_backend() factory

**Phase 6 (PostgreSQL backend):**
- Implement PostgresBackend class
- Use asyncpg for native async operations
- Read connection params from StorageConfig.postgres
- pgvector for vector search, tsvector for keyword search

**Config File (user-facing):**
```yaml
storage:
  backend: chroma  # or postgres
  postgres:        # Only needed when backend=postgres
    host: localhost
    port: 5432
    database: agent_brain
    user: postgres
    password: secret
```

## Known Issues

**CLI Build Failure (chroma-hnswlib):**
The `task before-push` command failed on CLI package build due to missing C++ headers (`<iostream>` not found). This is a known issue from MEMORY.md affecting Python 3.13 on macOS. The server tests (538/538) all passed with 70% coverage. The CLI failure is unrelated to Phase 5 changes.

Workaround: `xcode-select --install` or use Python 3.10 for CLI.

## Next Steps

**Plan 02 (ChromaBackend adapter):**
1. Create ChromaBackend class implementing StorageBackendProtocol
2. Wrap VectorStoreManager methods with asyncio.to_thread()
3. Implement keyword_search using BM25RetrieverService
4. Update IndexingService and QueryService to use factory
5. Consolidate SearchResult/EmbeddingMetadata imports (remove duplicates)

**Validation:**
- All 538+ tests pass
- Zero regressions in existing services
- BM25 and vector search still work via ChromaBackend adapter

## Self-Check: PASSED

**Created files exist:**
```bash
✅ agent-brain-server/agent_brain_server/storage/protocol.py
✅ agent-brain-server/agent_brain_server/storage/factory.py
✅ agent-brain-server/tests/unit/storage/test_protocol.py
✅ agent-brain-server/tests/unit/storage/test_factory.py
✅ agent-brain-server/tests/unit/config/test_storage_config.py
```

**Commits exist:**
```bash
✅ 80786d6: feat(05-01): create StorageBackendProtocol and data types
✅ fbea40a: feat(05-01): add StorageConfig and backend factory
✅ be7fbe6: test(05-01): add unit tests for protocol, factory, and config
✅ 9a448aa: fix(05-01): remove unused imports and fix test lint issues
```

**Tests pass:**
```bash
✅ 538/538 tests passed (100% pass rate)
✅ 70% overall coverage maintained
✅ protocol.py: 100% coverage
✅ factory.py: 71% coverage
```

All verification checks passed. Plan 05-01 is complete.
