# Phase 21: Fix Duplicate Chunk ID Crash During Indexing - Research

**Researched:** 2026-03-12
**Domain:** ChromaDB upsert deduplication, chunk ID generation, indexing pipeline
**Confidence:** HIGH

---

## Summary

Phase 21 is a targeted bug fix. The indexing pipeline crashes with a `DuplicateIDError` from ChromaDB when a batch upsert contains two or more entries with the same chunk ID. The real-world trigger is Confluence exports that contain the same file at multiple subdirectory paths (e.g., `usdm_v3.json` in 3 locations). Even though the chunk IDs are based on `f"{document.source}_{idx}"` (file path + chunk index), duplicate IDs arise when LlamaIndex's `SimpleDirectoryReader` resolves multiple input files to the same `doc_id` or `file_path` string — producing identical `document.source` values and therefore colliding IDs in the assembled batch.

The fix is a single-function change to `VectorStoreManager.upsert_documents()` in `agent-brain-server/agent_brain_server/storage/vector_store.py`. Before calling `collection.upsert()`, deduplicate the input lists by ID, keeping the last occurrence (last-writer-wins is consistent with upsert semantics). No changes are needed in the chunking layer — users may legitimately have the same content in multiple files (deduplication at that layer would silently lose data).

The PostgreSQL backend's `upsert_documents` should receive the same deduplication treatment for consistency, though the primary crash path is ChromaDB.

**Primary recommendation:** Deduplicate the four parallel lists (`ids`, `embeddings`, `documents`, `metadatas`) by ID in `VectorStoreManager.upsert_documents()` before calling `collection.upsert()`, using a dict-based O(N) deduplication that preserves last-occurrence order. Log a warning with the count of duplicates removed.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DUPID-01 | `upsert_documents` silently deduplicates chunk IDs within a batch before calling ChromaDB, keeping last occurrence | Identified fix location: `VectorStoreManager.upsert_documents()` in `storage/vector_store.py` |
| DUPID-02 | Warning logged when duplicates are found, including count and sample IDs | Standard Python logging pattern; no new deps needed |
| DUPID-03 | PostgreSQL backend `upsert_documents` receives same deduplication guard | `storage/postgres/backend.py` `upsert_documents()` |
| DUPID-04 | Regression test: batch with duplicate IDs succeeds without error and stores last-occurrence value | Unit test in `tests/unit/storage/` using existing mock patterns |
| DUPID-05 | Regression test: batch without duplicates is unchanged (no silent data loss) | Companion test asserting identity when input has no duplicates |
</phase_requirements>

---

## Standard Stack

### Core (all already present — no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| chromadb | ^0.x (pinned in pyproject.toml) | Vector store; raises `DuplicateIDError` on duplicate IDs in a batch | Project standard vector backend |
| Python stdlib `dict` | N/A | O(N) deduplication by key, preserves insertion order (Python 3.7+) | Built-in, zero overhead |
| Python stdlib `logging` | N/A | Warning on duplicate detection | Project-wide logging pattern |
| pytest + pytest-asyncio | existing | Unit tests for async upsert path | Project standard test framework |
| unittest.mock `AsyncMock` | existing | Mock ChromaDB collection in unit tests | Used throughout existing test suite |

### No New Dependencies Required
This fix requires zero new packages. All components (ChromaDB, logging, dict deduplication) are already present.

---

## Architecture Patterns

### Recommended Project Structure
No new files or directories required. Changes are confined to:

```
agent-brain-server/
├── agent_brain_server/
│   └── storage/
│       ├── vector_store.py           # PRIMARY FIX: upsert_documents() deduplication
│       └── postgres/
│           └── backend.py            # SECONDARY FIX: same guard for consistency
└── tests/
    └── unit/
        └── storage/
            └── test_vector_store.py  # NEW: regression tests for DUPID-04, DUPID-05
```

The existing `tests/unit/storage/test_vector_store_metadata.py` demonstrates the test setup pattern. The new test file follows the same structure.

### Pattern 1: Dict-Based O(N) Deduplication with Last-Occurrence Semantics

**What:** Zip the four parallel lists into a dict keyed by ID. Later entries overwrite earlier entries (last-wins). Reconstruct the four lists from dict values.

**When to use:** Any time a caller assembles a batch from multiple document sources that may produce the same chunk ID. This is defensive programming in the storage layer.

**Why last-occurrence (not first)?** Upsert semantics update the stored value to the latest write. If the same chunk ID appears twice in a batch, the "correct" stored value is the last one the caller assembled — consistent with what would happen if the caller called upsert twice sequentially.

**Example:**
```python
# Source: project pattern — dict-based deduplication
def _deduplicate_by_id(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> tuple[list[str], list[list[float]], list[str], list[dict[str, Any]]]:
    """Deduplicate parallel lists by ID, keeping last occurrence."""
    seen: dict[str, tuple[list[float], str, dict[str, Any]]] = {}
    for id_, emb, doc, meta in zip(ids, embeddings, documents, metadatas):
        seen[id_] = (emb, doc, meta)  # last-writer-wins

    if len(seen) == len(ids):
        return ids, embeddings, documents, metadatas  # fast path: no duplicates

    dedup_ids = list(seen.keys())
    dedup_embs = [v[0] for v in seen.values()]
    dedup_docs = [v[1] for v in seen.values()]
    dedup_metas = [v[2] for v in seen.values()]
    return dedup_ids, dedup_embs, dedup_docs, dedup_metas
```

The fast path (no duplicates) avoids any allocation when the common case is a clean batch.

### Pattern 2: Warning Log with Sample IDs

**What:** When duplicates are found, log at WARNING level with the count and up to 5 sample IDs for debuggability.

**Example:**
```python
# In upsert_documents(), before calling collection.upsert():
dup_count = len(ids) - len(seen)
if dup_count > 0:
    sample = list(ids_before - set(seen.keys()))[:5]
    logger.warning(
        f"Deduplicated {dup_count} duplicate chunk IDs in upsert batch "
        f"(sample: {sample}). Keeping last occurrence."
    )
```

### Anti-Patterns to Avoid

- **Deduplicating in chunking.py:** Chunking should be source-faithful. If two files have identical content, both should produce chunks — they are indexed with their own source paths. The duplication problem only matters at the storage layer.
- **Raising an exception on duplicates:** The caller (IndexingService) should not need to know about or handle this edge case. Silent deduplication at the storage layer is the correct contract.
- **Sorting or reordering IDs:** Sorting destroys the semantic relationship between `ids[i]`, `embeddings[i]`, `documents[i]`, `metadatas[i]`. Always use a zipped dict approach to keep the four lists aligned.
- **Using `dict.fromkeys(ids)`:** This only deduplicates the IDs list but does not carry along the associated embeddings/documents/metadatas. Always zip first.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| O(N) deduplication by key | Custom hash table or sorted scan | Python `dict` | Python 3.7+ dict preserves insertion order; O(1) lookup per entry; built-in |
| Deduplication with last-win | Custom scan-backward loop | dict iteration (later `seen[k] = v` overwrites earlier) | Idiomatic, readable, zero-allocation until needed |

**Key insight:** Dict-based deduplication is idiomatic Python with no external dependencies. A custom solution would add complexity with no benefit.

---

## Common Pitfalls

### Pitfall 1: Off-by-One in Parallel List Reconstruction
**What goes wrong:** After filtering `seen.values()`, the four lists fall out of sync if the dev iterates them separately instead of from the zipped dict.
**Why it happens:** Forgetting that `ids`, `embeddings`, `documents`, `metadatas` must remain index-aligned.
**How to avoid:** Always zip all four lists into a single dict of `id -> (emb, doc, meta)`, then unzip. Never filter any one list independently.
**Warning signs:** `ValueError: ids, embeddings, and documents must have the same length` raised by the existing length-check guard in `upsert_documents`.

### Pitfall 2: Deduplication Before the Existing Length Guard
**What goes wrong:** The existing code checks `len(ids) == len(embeddings) == len(documents)` before deduplication. If deduplication is added after that check but before upsert, it's fine. If it's added before the check, the check still catches pre-dedup inconsistencies. Either placement works; post-check placement is preferable to keep existing validation intact.
**How to avoid:** Insert the deduplication logic AFTER the existing `if not (len(ids) == len(embeddings) == len(documents)):` guard.

### Pitfall 3: ChromaDB Batch Size Guard Not Applied to Deduped Count
**What goes wrong:** `IndexingService` batches chunks at `chroma_batch_size = 40000`. After deduplication in `upsert_documents`, the batch size is already smaller — this is fine. No secondary guard needed. But the BM25 `TextNode` list built from the original (pre-dedup) `chunks` list still has duplicates, which can cause incorrect BM25 scoring.
**How to avoid:** The deduplication fix is in the storage layer only. For BM25 correctness, the `IndexingService._run_indexing_pipeline()` can optionally also deduplicate the `chunks` list by `chunk_id` before building `nodes`, but this is a secondary concern — BM25 tolerates duplicate node IDs (it does not crash).

### Pitfall 4: Test Isolation — ChromaDB Collection Singleton
**What goes wrong:** Tests that instantiate `VectorStoreManager` with a real ChromaDB client will fight over the singleton `_vector_store`. Existing tests (see `tests/unit/storage/test_vector_store_metadata.py`) mock the ChromaDB client at the `chromadb.PersistentClient` level.
**How to avoid:** Mock `chromadb.PersistentClient` and `chromadb.Collection.upsert` using `unittest.mock.patch`. The deduplication logic is pure Python and can be tested without any real ChromaDB dependency.

---

## Code Examples

### Location of Primary Fix
```
agent-brain-server/agent_brain_server/storage/vector_store.py
class VectorStoreManager
  method: upsert_documents()   (line 250)
```

Current code (simplified):
```python
async def upsert_documents(
    self,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]] | None = None,
) -> int:
    if not (len(ids) == len(embeddings) == len(documents)):
        raise ValueError("ids, embeddings, and documents must have the same length")

    async with self._lock:
        assert self._collection is not None
        collection = self._collection
        safe_metadatas = metadatas or [{}] * len(ids)

        def _upsert() -> None:
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=safe_metadatas,
            )
        await asyncio.to_thread(_upsert)

    return len(ids)
```

After fix, insert deduplication between the length-check and the lock acquisition:
```python
# After the length check, before acquiring the lock:
safe_metadatas = metadatas or [{}] * len(ids)

# Deduplicate by ID (last-occurrence wins, consistent with upsert semantics)
seen: dict[str, tuple[list[float], str, dict[str, Any]]] = {}
for id_, emb, doc, meta in zip(ids, embeddings, documents, safe_metadatas):
    seen[id_] = (emb, doc, meta)

if len(seen) < len(ids):
    dup_count = len(ids) - len(seen)
    logger.warning(
        f"upsert_documents: removed {dup_count} duplicate chunk ID(s) "
        f"from batch of {len(ids)}. Keeping last occurrence. "
        f"Sample duplicate IDs: {list(ids)[:5]}"
    )
    ids = list(seen.keys())
    embeddings = [v[0] for v in seen.values()]
    documents = [v[1] for v in seen.values()]
    safe_metadatas = [v[2] for v in seen.values()]
```

### Test Pattern (from existing `test_vector_store_metadata.py` style)
```python
# tests/unit/storage/test_vector_store_deduplication.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_collection():
    col = MagicMock()
    col.upsert = MagicMock()
    col.metadata = {}
    return col

@pytest.fixture
def initialized_store(mock_collection):
    with patch("chromadb.PersistentClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_client_cls.return_value = mock_client

        from agent_brain_server.storage.vector_store import VectorStoreManager
        store = VectorStoreManager(persist_dir="/tmp/test", collection_name="test")
        store._collection = mock_collection
        store._initialized = True
        yield store

@pytest.mark.asyncio
async def test_upsert_deduplicates_batch(initialized_store, mock_collection):
    """DUPID-04: Batch with duplicate IDs succeeds; last occurrence stored."""
    ids = ["chunk_aaa", "chunk_bbb", "chunk_aaa"]  # 'chunk_aaa' duplicated
    embeddings = [[0.1], [0.2], [0.9]]             # last embedding for 'chunk_aaa' is [0.9]
    documents = ["first", "second", "third"]
    metadatas = [{"v": 1}, {"v": 2}, {"v": 99}]

    count = await initialized_store.upsert_documents(ids, embeddings, documents, metadatas)

    assert count == 2  # 3 in - 1 dup = 2 unique
    call_kwargs = mock_collection.upsert.call_args.kwargs
    assert call_kwargs["ids"] == ["chunk_bbb", "chunk_aaa"]  # last-win order
    assert [0.9] in call_kwargs["embeddings"]                # last embedding kept
    assert {"v": 99} in call_kwargs["metadatas"]             # last metadata kept

@pytest.mark.asyncio
async def test_upsert_no_duplicates_unchanged(initialized_store, mock_collection):
    """DUPID-05: Batch without duplicates passes through unchanged."""
    ids = ["chunk_x", "chunk_y"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    documents = ["doc_x", "doc_y"]
    metadatas = [{"a": 1}, {"b": 2}]

    count = await initialized_store.upsert_documents(ids, embeddings, documents, metadatas)

    assert count == 2
    call_kwargs = mock_collection.upsert.call_args.kwargs
    assert call_kwargs["ids"] == ["chunk_x", "chunk_y"]
```

---

## Root Cause Analysis

### Why IDs Collide Despite Source-Based Hashing

The `id_seed = f"{document.source}_{idx}"` scheme should produce unique IDs when `document.source` values are distinct. Two collision scenarios exist:

**Scenario A (most likely for Confluence exports):** `SimpleDirectoryReader` with `filename_as_id=True` uses the **filename** (not the full path) as the document ID. When two files in different subdirectories have the same filename (e.g., `dir1/usdm_v3.json` and `dir2/usdm_v3.json`), `doc.doc_id` is `usdm_v3.json` for both. The `file_path` in metadata may differ, but if LlamaIndex uses the filename as `doc_id` to deduplicate, it may assign the same `doc_id` or the chunker may receive the same `source` string for both.

**Scenario B:** Path normalization. The `IndexingService` calls `os.path.abspath(request.folder_path)` to normalize the folder path, but `document.source` comes from `doc.metadata.get("file_path", "")` which LlamaIndex sets. If LlamaIndex resolves symlinks or normalizes differently, two nominally different file paths could resolve to the same string.

**Conclusion:** The exact cause is secondary. The fix is correct regardless — defensive deduplication at the storage layer handles any upstream source of colliding IDs without requiring changes to document loading or chunking behavior.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No deduplication guard — crash on duplicate IDs | Deduplicate in `upsert_documents()` | Phase 21 | Indexing succeeds for Confluence exports and any other duplicate-file corpus |

**Deprecated/outdated:**
- None. This is a net-new defensive guard.

---

## Open Questions

1. **Should BM25 TextNode list also be deduplicated?**
   - What we know: BM25 (`rank-bm25`) does not raise on duplicate node IDs — it treats duplicates as separate documents (double-weights their terms).
   - What's unclear: Whether this causes meaningfully wrong BM25 scores in practice.
   - Recommendation: Fix BM25 deduplication in a follow-on task in the same plan (low risk, small change). Primary fix is the ChromaDB crash path.

2. **Should the PostgreSQL backend get the same fix?**
   - What we know: The PostgreSQL `upsert_documents` uses `INSERT ... ON CONFLICT DO UPDATE` which natively handles duplicate IDs within a batch only if the DB engine sees them sequentially. Some PostgreSQL versions raise an error on duplicate keys within a single batch.
   - Recommendation: Add the same deduplication guard to `storage/postgres/backend.py` for consistency, even if the PostgreSQL path is not the current crash site.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (existing) |
| Config file | `agent-brain-server/pyproject.toml` (pytest settings) |
| Quick run command | `cd agent-brain-server && poetry run pytest tests/unit/storage/ -x -q` |
| Full suite command | `cd agent-brain-server && poetry run pytest -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DUPID-01 | Duplicate IDs removed before ChromaDB upsert | unit | `poetry run pytest tests/unit/storage/test_vector_store_deduplication.py::test_upsert_deduplicates_batch -x` | Wave 0 |
| DUPID-02 | Warning logged with count and sample IDs | unit | `poetry run pytest tests/unit/storage/test_vector_store_deduplication.py::test_upsert_logs_warning_on_duplicates -x` | Wave 0 |
| DUPID-03 | PostgreSQL backend deduplication | unit | `poetry run pytest tests/unit/storage/test_vector_store_deduplication.py::test_postgres_upsert_deduplicates -x` | Wave 0 |
| DUPID-04 | Duplicate batch → last-occurrence value stored | unit | `poetry run pytest tests/unit/storage/test_vector_store_deduplication.py::test_upsert_deduplicates_batch -x` | Wave 0 |
| DUPID-05 | Clean batch → no data loss | unit | `poetry run pytest tests/unit/storage/test_vector_store_deduplication.py::test_upsert_no_duplicates_unchanged -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd agent-brain-server && poetry run pytest tests/unit/storage/ -x -q`
- **Per wave merge:** `cd agent-brain-server && poetry run pytest -x -q`
- **Phase gate:** `task before-push` exits 0 before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/storage/test_vector_store_deduplication.py` — covers DUPID-01, DUPID-02, DUPID-04, DUPID-05
- [ ] Add PostgreSQL mock test to same file — covers DUPID-03

*(Existing test infrastructure: `tests/unit/storage/test_vector_store_metadata.py` and `conftest.py` provide the fixture and mock patterns — no new test infrastructure setup needed)*

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `agent_brain_server/storage/vector_store.py` — `upsert_documents()` method (line 250-297) — confirmed exact fix location
- Direct code inspection: `agent_brain_server/indexing/chunking.py` — `id_seed = f"{document.source}_{idx}"` (lines 304, 724) — confirmed ID generation scheme
- Direct code inspection: `agent_brain_server/services/indexing_service.py` — `_run_indexing_pipeline()` (lines 607-626) — confirmed batch upsert call site
- Direct code inspection: `agent_brain_server/indexing/document_loader.py` — `SimpleDirectoryReader(filename_as_id=True)` (line 372) — confirmed LlamaIndex document loading with filename-as-id

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — `Two-step ChromaDB delete guards against empty ids=[] bug` (Phase 14 decision) — confirms project pattern of defensive guards in the ChromaDB layer
- Error description in phase brief — "7 chunk IDs duplicated within the batch" — consistent with source-path-collision hypothesis from `filename_as_id=True`

### Tertiary (LOW confidence — requires validation at implementation time)
- LlamaIndex `SimpleDirectoryReader` behavior with `filename_as_id=True`: when two files share the same filename across subdirectories, the `file_path` metadata field in the loaded document may use the filename only (not the full path), causing `document.source` to collide. This is the most likely root cause but was not verified against the LlamaIndex source code in this research pass.

---

## Metadata

**Confidence breakdown:**
- Fix location: HIGH — confirmed by direct code inspection; `upsert_documents()` in `vector_store.py` is exactly the right place
- Fix implementation: HIGH — dict-based deduplication is idiomatic Python with no edge cases for the parallel-lists problem
- Root cause: MEDIUM — two plausible explanations; the fix is correct regardless of which applies
- Test patterns: HIGH — existing test in `test_vector_store_metadata.py` demonstrates exact mock setup needed

**Research date:** 2026-03-12
**Valid until:** 2026-06-12 (stable: ChromaDB API, Python stdlib dict behavior)
