---
phase: 02-pluggable-providers
plan: 01
subsystem: provider-validation
tags: [PROV-07, validation, metadata, compatibility]
dependency-graph:
  requires: [provider-infrastructure, vector-store]
  provides: [dimension-validation, provider-mismatch-detection]
  affects: [indexing-service, api-server, cli]
tech-stack:
  added: []
  patterns: [metadata-storage, validation-layer, force-flag]
key-files:
  created:
    - tests/unit/storage/test_vector_store_metadata.py
  modified:
    - agent-brain-server/agent_brain_server/storage/vector_store.py
    - agent-brain-server/agent_brain_server/services/indexing_service.py
    - agent-brain-server/agent_brain_server/api/main.py
    - agent-brain-server/agent_brain_server/models/index.py
    - agent-brain-server/agent_brain_server/api/routers/index.py
    - agent-brain-cli/agent_brain_cli/client/api_client.py
    - agent-brain-cli/agent_brain_cli/commands/index.py
decisions:
  - Metadata stored in ChromaDB collection metadata (not separate table)
  - Validation happens at two points: startup (warning) and indexing (error)
  - Force flag bypasses validation to allow intentional provider changes
  - Validation checks both dimensions AND provider/model (not just dimensions)
metrics:
  duration: 411 seconds (6 minutes)
  completed: 2026-02-09T21:27:15Z
  tasks-completed: 5
  commits: 6
  tests-added: 7
---

# Phase 02 Plan 01: Dimension Mismatch Prevention (PROV-07) Summary

**One-liner:** Embedding metadata storage with dimension/provider validation to prevent silent search degradation when switching providers

## Objective

Implement dimension mismatch prevention to ensure embedding providers match indexed data, preventing silent search quality degradation when users switch embedding providers without re-indexing.

## Tasks Completed

### Task 1: Add embedding metadata model and storage methods to VectorStoreManager

**Status:** ✅ Complete
**Commit:** 8f2b861

Added `EmbeddingMetadata` dataclass with serialization methods and three new methods to `VectorStoreManager`:
- `get_embedding_metadata()`: Retrieves stored metadata from ChromaDB collection
- `set_embedding_metadata()`: Stores provider/model/dimensions in collection metadata
- `validate_embedding_compatibility()`: Raises ProviderMismatchError on mismatch

**Files modified:**
- `agent-brain-server/agent_brain_server/storage/vector_store.py`

### Task 2: Add validation to IndexingService before indexing

**Status:** ✅ Complete
**Commit:** 98cde54

Added embedding compatibility validation to indexing pipeline:
- Modified `start_indexing()` to accept `force` parameter
- Added `_validate_embedding_compatibility()` method
- Store embedding metadata after successful indexing
- Added validation check in `_run_indexing_pipeline()` when force=False

**Files modified:**
- `agent-brain-server/agent_brain_server/services/indexing_service.py`

### Task 3: Add startup validation to FastAPI lifespan

**Status:** ✅ Complete
**Commit:** d92f4d2

Added `check_embedding_compatibility()` function that:
- Checks stored metadata against current config at startup
- Logs warning if mismatch detected
- Stores warning on `app.state.embedding_warning` for health endpoint

**Files modified:**
- `agent-brain-server/agent_brain_server/api/main.py`

### Task 4: Add --force flag to CLI index command

**Status:** ✅ Complete
**Commit:** 9fe2805

Added `force` field to IndexRequest model and updated:
- API router to pass force from request body
- CLI client to include force in JSON body and query params
- CLI help text to describe provider mismatch bypass
- Added validation check in `_run_indexing_pipeline` respecting force flag

**Files modified:**
- `agent-brain-server/agent_brain_server/models/index.py`
- `agent-brain-server/agent_brain_server/api/routers/index.py`
- `agent-brain-cli/agent_brain_cli/client/api_client.py`
- `agent-brain-cli/agent_brain_cli/commands/index.py`

### Task 5: Add unit tests for embedding metadata validation

**Status:** ✅ Complete
**Commit:** c7f6ed9

Created comprehensive test suite with 7 tests:
- EmbeddingMetadata to_dict/from_dict conversion
- Validation passes when metadata matches
- Validation fails on dimension mismatch
- Validation fails on provider mismatch (even with same dimensions)
- Validation passes when no metadata exists (new index)

**Files created:**
- `agent-brain-server/tests/unit/storage/test_vector_store_metadata.py`

**Test Results:** 7 passed, all green

## Deviations from Plan

None - plan executed exactly as written.

## Technical Implementation

### Metadata Storage Strategy

Embedding metadata (provider, model, dimensions) is stored directly in ChromaDB collection metadata rather than in a separate table. This approach:
- Keeps metadata co-located with the data it describes
- Automatically cleared when collection is reset
- Accessible via `collection.metadata` without additional queries

```python
@dataclass
class EmbeddingMetadata:
    provider: str
    model: str
    dimensions: int
```

### Validation Flow

**Startup validation (warning only):**
1. Server starts → vector store initialized
2. `check_embedding_compatibility()` runs
3. If mismatch detected → log warning + store on app.state
4. Server continues (doesn't block startup)

**Indexing validation (error unless force=True):**
1. Indexing job starts
2. If `force=False`: validate compatibility
3. If mismatch → raise ProviderMismatchError
4. If `force=True` or no metadata: continue
5. After successful indexing → store current metadata

### Force Flag Behavior

The `--force` flag now serves dual purposes:
1. **Job queue deduplication bypass** (existing behavior)
2. **Provider validation bypass** (new behavior)

When `--force` is used:
- Validation is skipped during indexing
- New embeddings overwrite existing ones
- Metadata is updated to reflect current provider

## Verification Results

### Quality Checks

✅ **Formatting:** Black applied successfully
✅ **Linting:** Ruff checks passed
✅ **Type Checking:** mypy passed (56 files)
✅ **Unit Tests:** 376 passed, 2 pre-existing failures unrelated to changes

### New Test Coverage

Created 7 new tests specifically for embedding metadata validation:
- `test_to_dict`: EmbeddingMetadata serialization
- `test_from_dict`: EmbeddingMetadata deserialization
- `test_from_dict_missing_keys`: Handles missing metadata gracefully
- `test_validate_compatible`: Passes when everything matches
- `test_validate_dimension_mismatch`: Catches dimension changes
- `test_validate_provider_mismatch_same_dimensions`: Catches provider changes even with same dimensions
- `test_validate_no_stored_metadata`: Allows first-time indexing

All tests passing with proper error messages in ProviderMismatchError.

## Integration Points

### API Surface

**IndexRequest model:**
```python
force: bool = Field(
    default=False,
    description="Force re-indexing even if embedding provider has changed"
)
```

**API endpoint:**
```
POST /index/?force=true
```

**CLI command:**
```bash
agent-brain index /path --force
```

### Error Handling

**ProviderMismatchError message:**
```
Provider mismatch: index was created with openai/text-embedding-3-large,
but current config uses ollama/nomic-embed-text. Re-index with --force to update.
```

## Success Criteria

- [x] EmbeddingMetadata dataclass exists with to_dict/from_dict methods
- [x] VectorStoreManager stores embedding metadata in ChromaDB collection
- [x] VectorStoreManager.validate_embedding_compatibility raises ProviderMismatchError on mismatch
- [x] IndexingService validates before indexing (unless force=True)
- [x] IndexingService stores metadata after successful indexing
- [x] FastAPI startup logs warning if embedding mismatch detected
- [x] CLI index command has --force flag
- [x] Unit tests pass with >80% coverage for new code
- [x] Quality checks pass (format, lint, typecheck)

## Self-Check: PASSED

**Created files verified:**
```bash
[ -f "agent-brain-server/tests/unit/storage/test_vector_store_metadata.py" ] # ✅ FOUND
```

**Commits verified:**
```bash
git log --oneline | grep -E "8f2b861|98cde54|d92f4d2|9fe2805|c7f6ed9" # ✅ ALL FOUND
```

**Test execution:**
```bash
pytest tests/unit/storage/test_vector_store_metadata.py # ✅ 7 passed
```

## Next Steps

This plan addresses PROV-07 (dimension mismatch prevention). The next plan in Phase 2 should address:
- **02-02-PLAN.md:** Strict startup validation (PROV-06)
- **02-03-PLAN.md:** Provider switching E2E test (PROV-03)
- **02-04-PLAN.md:** Ollama offline E2E test (PROV-04)

## Notes

- Metadata storage uses ChromaDB's built-in collection metadata feature
- Validation is intentionally non-blocking at startup (warning only)
- Force flag provides escape hatch for intentional provider changes
- Both dimensions AND provider/model are validated (not just dimensions)
- Tests cover edge cases like same-dimension-different-provider scenarios
