# Phase 14: Manifest Tracking & Chunk Eviction - Research

**Researched:** 2026-03-05
**Domain:** Incremental indexing with manifest-based change detection, chunk lifecycle management
**Confidence:** HIGH (all findings based on direct codebase inspection)

---

## Summary

Phase 14 adds incremental indexing to Agent Brain. Currently the system re-indexes entire folders from scratch on every `index` command, which is expensive. The goal is a manifest file per indexed folder that records `file_path → checksum + mtime + chunk_ids`, so that on re-index only changed/new files are processed and deleted files' chunks are evicted from storage.

The implementation fits cleanly into the existing architecture: `FolderManager` already stores `chunk_ids` per folder; `StorageBackendProtocol` already has `delete_by_ids()`; `IndexingService` already accepts a `force` flag. Phase 14 adds a `ManifestTracker` (parallel to `FolderManager` in structure), a `ChunkEvictionService` (orchestrates diff + delete), and hooks these into the existing `_run_indexing_pipeline` method.

The key design decision is manifest-per-folder stored as a single JSON file at `.agent-brain/manifests/<sha256_of_folder_path>.json`. This mirrors the pattern established by `FolderManager` (JSONL in `.claude/agent-brain/`) but uses JSON (not JSONL) because the entire manifest is rewritten atomically after each run. The atomic write pattern (temp file + `Path.replace()`) from Phase 12 is the correct approach for crash safety.

**Primary recommendation:** Implement `ManifestTracker` as a new service class that mirrors `FolderManager`'s async/lock/atomic-write pattern. Wire it into `IndexingService._run_indexing_pipeline()` at the file-scan step, before chunks are generated, to compute the diff and evict stale chunks before any new indexing begins.

---

## Standard Stack

### Core (already in project, no new dependencies needed)
| Library | Version | Purpose | Why Used |
|---------|---------|---------|----------|
| `hashlib` (stdlib) | stdlib | SHA-256 file checksums | Zero-dep, deterministic, collision-resistant |
| `pathlib` (stdlib) | stdlib | Path manipulation, manifest key | Already used throughout codebase |
| `json` (stdlib) | stdlib | Manifest serialization | Consistent with FolderManager pattern |
| `asyncio` (stdlib) | stdlib | Lock, to_thread | Already used in FolderManager |
| `dataclasses` (stdlib) | stdlib | FileRecord, EvictionSummary | Already used in FolderManager |
| `os.stat` (stdlib) | stdlib | mtime retrieval | Faster than Path.stat() in loops |

### No New PyPI Dependencies
The entire implementation can be done with stdlib. Do not add hashlib alternatives, watchdog, or any file-system watcher — the manifest approach is pull-based (compare on demand), not push-based (watch for changes).

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
agent-brain-server/agent_brain_server/
├── services/
│   ├── manifest_tracker.py       # NEW: ManifestTracker + FileRecord + EvictionSummary
│   ├── chunk_eviction_service.py # NEW: ChunkEvictionService (diff + delete)
│   ├── folder_manager.py         # EXISTING: no changes needed
│   └── indexing_service.py       # EXISTING: wire in ManifestTracker + ChunkEvictionService
├── storage_paths.py              # EXISTING: add "manifests" subdirectory
├── models/
│   └── job.py                    # EXISTING: add force + eviction_summary fields to JobRecord
```

```
.agent-brain/
├── data/
│   ├── chroma_db/
│   ├── bm25_index/
│   └── ...
├── manifests/               # NEW subdirectory
│   ├── <sha256_of_path1>.json
│   └── <sha256_of_path2>.json
└── logs/
```

### Pattern 1: ManifestTracker

**What:** Per-folder JSON file tracking `file_path → {checksum, mtime, chunk_ids}`. Atomic writes via temp+replace. Single asyncio.Lock for all manifest operations within the service.

**When to use:** On every `index` call that does NOT pass `force=True`.

```python
# Source: direct codebase inspection (mirrors FolderManager pattern exactly)
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    """Per-file record in a folder manifest."""

    checksum: str        # SHA-256 hex digest of file content
    mtime: float         # os.stat().st_mtime as float seconds
    chunk_ids: list[str] # Chunk IDs produced from this file


@dataclass
class FolderManifest:
    """Full manifest for one indexed folder."""

    folder_path: str
    files: dict[str, FileRecord] = field(default_factory=dict)
    # key = absolute file path string


@dataclass
class EvictionSummary:
    """Result of a manifest diff + eviction pass."""

    files_added: list[str]     # New files not in prior manifest
    files_changed: list[str]   # Files whose checksum changed
    files_deleted: list[str]   # Files in manifest but not on disk
    files_unchanged: list[str] # Files with matching checksum (skipped)
    chunks_evicted: int        # Total chunk IDs deleted from storage
    chunks_to_create: int      # Files that need (re-)indexing


class ManifestTracker:
    """Tracks per-folder file manifests for incremental indexing.

    Manifest path: <manifests_dir>/<sha256(folder_path)>.json
    Uses atomic write (temp + Path.replace()) for crash safety.
    """

    def __init__(self, manifests_dir: Path) -> None:
        self.manifests_dir = manifests_dir
        self._lock = asyncio.Lock()

    def _manifest_path(self, folder_path: str) -> Path:
        key = hashlib.sha256(folder_path.encode()).hexdigest()
        return self.manifests_dir / f"{key}.json"

    async def load(self, folder_path: str) -> FolderManifest | None:
        """Load manifest for folder, returns None if not present."""
        path = self._manifest_path(folder_path)
        if not path.exists():
            return None
        return await asyncio.to_thread(self._read_manifest, path, folder_path)

    async def save(self, manifest: FolderManifest) -> None:
        """Atomically persist manifest to disk."""
        async with self._lock:
            await asyncio.to_thread(self._write_manifest, manifest)

    async def delete(self, folder_path: str) -> None:
        """Remove manifest file (e.g., on folder removal or force reindex)."""
        path = self._manifest_path(folder_path)
        async with self._lock:
            if path.exists():
                await asyncio.to_thread(path.unlink)

    def _read_manifest(self, path: Path, folder_path: str) -> FolderManifest:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        files = {
            fp: FileRecord(
                checksum=rec["checksum"],
                mtime=rec["mtime"],
                chunk_ids=rec["chunk_ids"],
            )
            for fp, rec in data.get("files", {}).items()
        }
        return FolderManifest(folder_path=folder_path, files=files)

    def _write_manifest(self, manifest: FolderManifest) -> None:
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        path = self._manifest_path(manifest.folder_path)
        temp_path = path.with_suffix(".json.tmp")
        data = {
            "folder_path": manifest.folder_path,
            "files": {
                fp: {
                    "checksum": rec.checksum,
                    "mtime": rec.mtime,
                    "chunk_ids": rec.chunk_ids,
                }
                for fp, rec in manifest.files.items()
            },
        }
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        temp_path.replace(path)  # POSIX atomic rename


def compute_file_checksum(file_path: str) -> str:
    """Compute SHA-256 hex digest of file contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
```

### Pattern 2: ChunkEvictionService

**What:** Computes diff between current filesystem state and prior manifest, deletes stale chunks from ChromaDB/Postgres, returns `EvictionSummary` and the list of files that need re-indexing.

**When to use:** Called in `IndexingService._run_indexing_pipeline()` after loading documents, when a manifest may exist.

```python
# Source: direct codebase inspection
class ChunkEvictionService:
    """Computes manifest diff and evicts stale chunks from storage."""

    def __init__(
        self,
        manifest_tracker: ManifestTracker,
        storage_backend: StorageBackendProtocol,
    ) -> None:
        self._manifest = manifest_tracker
        self._storage = storage_backend

    async def compute_diff_and_evict(
        self,
        folder_path: str,
        current_files: list[str],  # absolute paths of files found on disk
        force: bool = False,
    ) -> tuple[EvictionSummary, list[str]]:
        """Compute changes and evict stale chunks.

        Returns (EvictionSummary, files_to_index) where files_to_index
        is the subset of current_files that need (re-)indexing.
        """
        if force:
            # Force: delete ALL prior chunks, return all current files for indexing
            prior = await self._manifest.load(folder_path)
            chunks_evicted = 0
            if prior:
                all_prior_ids = [
                    cid
                    for rec in prior.files.values()
                    for cid in rec.chunk_ids
                ]
                if all_prior_ids:
                    chunks_evicted = await self._storage.delete_by_ids(all_prior_ids)
                await self._manifest.delete(folder_path)
            return (
                EvictionSummary(
                    files_added=current_files,
                    files_changed=[],
                    files_deleted=[],
                    files_unchanged=[],
                    chunks_evicted=chunks_evicted,
                    chunks_to_create=len(current_files),
                ),
                current_files,
            )

        prior = await self._manifest.load(folder_path)
        if prior is None:
            # No manifest: treat all files as new
            return (
                EvictionSummary(
                    files_added=current_files,
                    files_changed=[],
                    files_deleted=[],
                    files_unchanged=[],
                    chunks_evicted=0,
                    chunks_to_create=len(current_files),
                ),
                current_files,
            )

        current_set = set(current_files)
        prior_set = set(prior.files.keys())

        files_deleted = list(prior_set - current_set)
        files_to_evict: list[str] = list(files_deleted)  # deleted + changed
        files_unchanged: list[str] = []
        files_added: list[str] = []
        files_changed: list[str] = []
        files_to_index: list[str] = []

        # Detect new and changed files
        for fp in current_files:
            if fp not in prior_set:
                files_added.append(fp)
                files_to_index.append(fp)
            else:
                # Compare by checksum (definitive) with mtime as fast pre-check
                prior_rec = prior.files[fp]
                current_mtime = os.stat(fp).st_mtime
                if current_mtime == prior_rec.mtime:
                    # mtime unchanged → assume content unchanged (skip checksum)
                    files_unchanged.append(fp)
                else:
                    # mtime changed → verify by checksum
                    current_checksum = await asyncio.to_thread(
                        compute_file_checksum, fp
                    )
                    if current_checksum == prior_rec.checksum:
                        files_unchanged.append(fp)
                    else:
                        files_changed.append(fp)
                        files_to_evict.append(fp)  # evict old chunks
                        files_to_index.append(fp)

        # Bulk evict stale chunks
        ids_to_evict: list[str] = []
        for fp in files_to_evict:
            if fp in prior.files:
                ids_to_evict.extend(prior.files[fp].chunk_ids)

        chunks_evicted = 0
        if ids_to_evict:
            chunks_evicted = await self._storage.delete_by_ids(ids_to_evict)

        return (
            EvictionSummary(
                files_added=files_added,
                files_changed=files_changed,
                files_deleted=files_deleted,
                files_unchanged=files_unchanged,
                chunks_evicted=chunks_evicted,
                chunks_to_create=len(files_to_index),
            ),
            files_to_index,
        )
```

### Pattern 3: Manifest Update After Indexing

**What:** After a successful indexing run, the new manifest is built from the files that were (re-)indexed, merged with the unchanged entries from the prior manifest, and atomically saved.

**Key insight:** The manifest must store the new `chunk_ids` for each file, which means `IndexingService` must correlate chunks back to their source files after the pipeline runs. Chunks already have `metadata.source` (the file path) so this correlation is trivial.

```python
# Source: direct codebase inspection of chunk metadata
# After _run_indexing_pipeline produces chunks, build new manifest:

new_manifest = FolderManifest(folder_path=abs_folder_path)

# Carry over unchanged files from prior manifest
if prior_manifest is not None:
    for fp in eviction_summary.files_unchanged:
        new_manifest.files[fp] = prior_manifest.files[fp]

# Record newly indexed files
# Build file → chunk_ids map first
file_to_chunks: dict[str, list[str]] = {}
for chunk in chunks:
    fp = chunk.metadata.to_dict().get("source", "")
    if fp:
        file_to_chunks.setdefault(fp, []).append(chunk.chunk_id)

for fp, chunk_ids in file_to_chunks.items():
    checksum = await asyncio.to_thread(compute_file_checksum, fp)
    mtime = os.stat(fp).st_mtime
    new_manifest.files[fp] = FileRecord(
        checksum=checksum,
        mtime=mtime,
        chunk_ids=chunk_ids,
    )

await manifest_tracker.save(new_manifest)
```

### Pattern 4: storage_paths.py Extension

```python
# Source: direct codebase inspection of storage_paths.py
# agent_brain_server/storage_paths.py

SUBDIRECTORIES = [
    "data",
    "data/chroma_db",
    "data/bm25_index",
    "data/llamaindex",
    "data/graph_index",
    "logs",
    "manifests",  # ADD THIS — new in Phase 14
]

# In resolve_storage_paths(), add:
paths["manifests"] = state_dir / "manifests"
```

### Pattern 5: IndexingService Integration

The integration hook in `_run_indexing_pipeline()` is between Step 1 (load documents) and Step 2 (chunk). After `DocumentLoader.load_files()` returns the full document list, extract source paths, run the diff+evict, then filter documents to only the subset that needs indexing.

```python
# INTEGRATION POINT in _run_indexing_pipeline() — after Step 1 document load:
# Source: direct codebase inspection of indexing_service.py

eviction_summary: EvictionSummary | None = None
prior_manifest: FolderManifest | None = None

if self.manifest_tracker is not None:
    eviction_service = ChunkEvictionService(
        manifest_tracker=self.manifest_tracker,
        storage_backend=self.storage_backend,
    )
    current_file_paths = [
        str(Path(doc.metadata.get("source", "")).resolve())
        for doc in documents
        if doc.metadata.get("source")
    ]
    prior_manifest = await self.manifest_tracker.load(abs_folder_path)
    eviction_summary, files_to_index_list = (
        await eviction_service.compute_diff_and_evict(
            folder_path=abs_folder_path,
            current_files=current_file_paths,
            force=request.force,
        )
    )
    files_to_index_set = set(files_to_index_list)
    documents = [
        doc for doc in documents
        if str(Path(doc.metadata.get("source", "")).resolve()) in files_to_index_set
    ]
    logger.info(
        f"Manifest diff: +{len(eviction_summary.files_added)} added "
        f"~{len(eviction_summary.files_changed)} changed "
        f"-{len(eviction_summary.files_deleted)} deleted "
        f"={len(eviction_summary.files_unchanged)} unchanged, "
        f"{eviction_summary.chunks_evicted} chunks evicted"
    )
    if not documents:
        logger.info("No files need re-indexing — all files unchanged")
        # Mark completed, save manifest (unchanged), return early
        self._state.status = IndexingStatusEnum.COMPLETED
        self._state.is_indexing = False
        self._state.completed_at = datetime.now(timezone.utc)
        # Manifest already current, no need to re-save
        return
```

### Pattern 6: BM25 Rebuild for Incremental Runs

After incremental indexing, the BM25 index must be rebuilt from ALL chunks (unchanged + new), not just the newly indexed ones. The confirmed approach is to rebuild from the full manifest's chunk IDs after each run.

```python
# After storage upsert and before BM25 rebuild — for incremental runs:
# Source: confirmed via BM25IndexManager API inspection
# bm25_manager.build_index(nodes) does a full rebuild from provided nodes

# For incremental runs with unchanged files, we need ALL nodes:
# Option 1 (recommended): Use ManifestTracker to get all chunk_ids, then
# fetch from vector store to reconstruct nodes for BM25.
# This ensures BM25 is always consistent with vector store.

if eviction_summary is not None and eviction_summary.files_unchanged:
    # There are unchanged files — BM25 needs their chunks too
    all_chunk_ids = []
    if new_manifest is not None:
        for file_rec in new_manifest.files.values():
            all_chunk_ids.extend(file_rec.chunk_ids)
    # Fetch unchanged chunks from vector store and combine with new chunks
    # for the full BM25 rebuild
    # (Implementation: use storage_backend.get_by_id() for each unchanged ID,
    #  then build TextNode list combining unchanged + new)
```

### Anti-Patterns to Avoid

- **Storing manifests inside FolderManager JSONL:** Keep manifest data separate from folder records. FolderManager tracks folders (existence + total chunk IDs). ManifestTracker tracks per-file granularity. Mixing them creates huge JSONL entries for large codebases.
- **Using mtime only without checksum verification:** mtime is a fast pre-check but unreliable across network mounts, `git checkout`, `touch`, and some editors that preserve timestamps. Always verify with checksum when mtime changes.
- **Using checksum only without mtime pre-check:** For large folders (10k+ files), computing SHA-256 of every file on every reindex is expensive. The mtime fast path skips ~95% of files in practice.
- **Rebuilding BM25 from only the new chunks:** `BM25IndexManager.build_index()` does a full corpus rebuild and will forget all unchanged-file chunks if only new chunks are passed. Must pass ALL nodes.
- **Empty IDs passed to delete_by_ids:** Both backends guard `if not ids: return 0`. But callers must still be careful — never construct an eviction call assuming the guard exists.
- **Manifest stored in the indexed folder:** The manifest goes in `state_dir/manifests/`, NOT inside the user's project folder. Writing into the indexed folder would pollute user projects.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes | Custom file locking | `temp_path.replace(path)` (POSIX) | Already used in FolderManager; atomic on POSIX; established Phase 12 pattern |
| File change detection | inotify/watchdog | mtime + SHA-256 on demand | Pull-based is simpler, no background threads, consistent with batch index model |
| Chunk ID → file mapping | Separate lookup table | `chunk.metadata["source"]` in every chunk | Source path is already stored in chunk metadata at creation time |
| Concurrent manifest access | Per-file locks | Single `asyncio.Lock` per `ManifestTracker` | Manifests are per-folder, not shared across concurrent requests; single lock is correct |
| Manifest content hash | Custom rolling hash | Python `hashlib.sha256()` | Stdlib, fast, standard |

**Key insight:** All storage primitives needed already exist (`delete_by_ids`, chunk metadata with source paths, atomic writes). Phase 14 is pure orchestration on top of existing infrastructure.

---

## Common Pitfalls

### Pitfall 1: BM25 Must Receive ALL Nodes After Incremental Run
**What goes wrong:** After incremental indexing, `bm25_manager.build_index(nodes)` receives only the newly-indexed chunks, wiping the BM25 entries for all unchanged files.
**Why it happens:** `BM25IndexManager.build_index()` does a full rebuild from the provided nodes. API confirmed: `build_index(nodes: Sequence[BaseNode])` replaces the entire index.
**How to avoid:** After incremental indexing, fetch unchanged chunk data from vector store using chunk IDs from the manifest, build `TextNode` objects, then combine with new nodes before calling `build_index()`.
**Warning signs:** BM25 keyword search stops finding content from files that were not re-indexed.

### Pitfall 2: Chunk ID Accumulation Bug
**What goes wrong:** Manifests record `chunk_ids` per file. After a file is changed and re-indexed, the new chunk IDs are recorded. But if old chunk IDs are not evicted from storage before new ones are created, duplicates accumulate.
**Why it happens:** Missing the eviction step before re-indexing a changed file.
**How to avoid:** `ChunkEvictionService.compute_diff_and_evict()` must complete (and await) the `delete_by_ids()` call for changed files BEFORE `IndexingService` creates new chunks for those files. The pipeline order must be: diff → evict → filter → chunk → embed → store → manifest_save.
**Warning signs:** `get_count()` grows unboundedly on repeated re-indexes of the same folder.

### Pitfall 3: Manifest Out of Sync on Partial Failure
**What goes wrong:** Indexing fails after evicting old chunks but before creating new ones. The manifest still shows stale chunk IDs for the affected files.
**Why it happens:** Manifest is saved at the end of a successful pipeline run. If the pipeline crashes mid-run, the next invocation will see the old manifest and think no eviction is needed.
**How to avoid:** Manifest save happens only after a successful pipeline completion. Failed runs leave the manifest in its prior state. On retry, the changed files will be detected again, eviction will be re-attempted (`delete_by_ids()` with already-deleted IDs returns 0 safely), and new chunks will be created. This is correct behavior.
**Warning signs:** After a failed run, the affected files remain in the manifest with stale chunk IDs that no longer exist in storage.

### Pitfall 4: Manifest Path Collision Between Projects
**What goes wrong:** Two projects both index `/home/user/docs`. Their manifests collide on the SHA-256 key of the folder path.
**Why it happens:** SHA-256 of the folder path is unique per path string, but if two project instances share a `state_dir`, they share the same `manifests/` directory.
**How to avoid:** This is not a problem in project mode — each server instance has its own `state_dir` (established in Phase 9's multi-instance architecture). The manifests are under `state_dir/manifests/`. Only relevant if `DOC_SERVE_MODE=shared` and multiple projects share one daemon.
**Warning signs:** Manifests from different projects corrupting each other in shared mode.

### Pitfall 5: Large Manifests for Large Codebases
**What goes wrong:** A manifest for a 50k-file codebase is a single JSON file that could be 10-50 MB. Loading and parsing it on every reindex is slow.
**Why it happens:** The manifest format stores ALL file records in a single JSON blob.
**How to avoid:** For Phase 14, the full-manifest-per-folder approach is acceptable. Most real projects have fewer than 10k files, and JSON parse of a 5 MB file takes ~100ms, acceptable for a background job. Address sharding (per-subdirectory manifests) only if benchmarks show it is a problem.
**Warning signs:** Manifest JSON files exceeding ~5 MB; index command noticeably slow before document scanning.

### Pitfall 6: JobWorker Verification Delta Breaks for No-Op Incremental Runs
**What goes wrong:** `JobWorker._verify_collection_delta()` checks that `count_after - count_before > 0`. For an incremental run where NO files changed, zero chunks are added, and verification fails incorrectly.
**Why it happens:** The verification was written for full indexing where some chunks are always added.
**How to avoid:** When `eviction_summary.chunks_to_create == 0` (nothing changed), skip delta verification and mark the job as DONE immediately. This requires passing the `EvictionSummary` from `IndexingService` back to `JobWorker`, or adding a flag to `IndexingState`.
**Warning signs:** Incremental re-index of unchanged folder results in job status FAILED.

### Pitfall 7: JobRecord Missing force Field
**What goes wrong:** `JobRecord` does NOT currently have a `force` field. `JobWorker._process_job()` hardcodes `force=False` when constructing `IndexRequest`. The CLI `--force` flag never propagates through the job queue to manifest bypass.
**Why it happens:** `force` was not added to `JobRecord` in prior phases.
**How to avoid:** Add `force: bool = Field(default=False, description="Bypass manifest comparison")` to `JobRecord`. Update `JobWorker._process_job()` to pass `force=job.force`. Update the index API router to pass `force=force` when creating `JobRecord`. This is a REQUIRED change for EVICT-08.
**Warning signs:** `agent-brain index --force /path` still runs incremental instead of full reindex.

---

## Code Examples

Verified patterns from codebase inspection:

### Existing delete_by_ids (both backends, confirmed)
```python
# Source: agent_brain_server/storage/chroma/backend.py
async def delete_by_ids(self, ids: list[str]) -> int:
    if not ids:   # Guard: empty list returns 0, avoids collection wipe
        return 0
    try:
        return await self.vector_store.delete_by_ids(ids=ids)
    except Exception as e:
        raise StorageError(f"Delete by IDs failed: {e}", backend="chroma") from e

# Source: agent_brain_server/storage/postgres/backend.py
async def delete_by_ids(self, ids: list[str]) -> int:
    if not ids:
        return 0
    sql = text(
        "DELETE FROM documents WHERE chunk_id = ANY(CAST(:ids AS text[])) RETURNING chunk_id"
    )
    async with engine.begin() as conn:
        result = await conn.execute(sql, {"ids": ids})
        return len(result.fetchall())
```

### FolderManager atomic write pattern (established Phase 12, to replicate)
```python
# Source: agent_brain_server/services/folder_manager.py
def _write_jsonl(self) -> None:
    self.state_dir.mkdir(parents=True, exist_ok=True)
    temp_path = self.jsonl_path.with_suffix(".jsonl.tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        for record in self._cache.values():
            f.write(json.dumps(asdict(record)) + "\n")
    temp_path.replace(self.jsonl_path)  # POSIX atomic rename
```

### Chunk metadata source field (for file-to-chunk correlation)
```python
# Source: agent_brain_server/services/indexing_service.py lines 510-514
await self.storage_backend.upsert_documents(
    ids=[chunk.chunk_id for chunk in batch_chunks],
    embeddings=batch_embeddings,
    documents=[chunk.text for chunk in batch_chunks],
    metadatas=[chunk.metadata.to_dict() for chunk in batch_chunks],
)
# chunk.metadata.to_dict() includes "source" key = absolute file path
```

### StorageBackendProtocol (delete_by_ids already present — EVICT-10 is already met)
```python
# Source: agent_brain_server/storage/protocol.py
async def delete_by_ids(self, ids: list[str]) -> int:
    """Delete documents by their chunk IDs.
    Guards against empty ID lists to prevent accidental bulk deletion.
    Returns: Number of documents deleted.
    """
    ...
# CONCLUSION: EVICT-10 is already satisfied. No protocol changes needed in Phase 14.
```

### JobRecord confirmed missing force field (CONFIRMED — must add)
```python
# Source: agent_brain_server/models/job.py (direct inspection)
# JobRecord fields present: folder_path, include_code, operation, chunk_size,
# chunk_overlap, recursive, generate_summaries, supported_languages,
# include_patterns, include_types, exclude_patterns, injector_script,
# folder_metadata_file, status, cancel_requested, enqueued_at, started_at,
# finished_at, error, retry_count, progress, total_chunks, total_documents
#
# MISSING: force field — must add for EVICT-08
# ADD: force: bool = Field(default=False, description="Bypass manifest comparison")
#
# JobWorker currently creates IndexRequest with force=False hardcoded:
# index_request = IndexRequest(folder_path=job.folder_path, ..., force=False)
# MUST change to: force=job.force
```

### BM25 manager API (confirmed — full rebuild, no incremental update)
```python
# Source: agent_brain_server/indexing/bm25_index.py
def build_index(self, nodes: Sequence[BaseNode]) -> None:
    """Build a new BM25 index from nodes and persist it."""
    logger.info(f"Building BM25 index with {len(nodes)} nodes")
    self._retriever = BM25Retriever.from_defaults(nodes=nodes)
    # CONCLUSION: Full rebuild. Must pass ALL nodes for incremental runs.
    # Pattern: fetch unchanged chunk data from vector store by IDs in manifest,
    # build TextNode objects, combine with new nodes, then call build_index().
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Re-index entire folder every run | Manifest-based diff: only changed/new files | Reduces indexing from O(N) to O(delta) for repeat runs |
| FolderManager tracks total chunk_ids per folder | ManifestTracker tracks chunk_ids per file | Enables file-granular eviction without scanning vector store |
| `delete_by_ids` existed but unused for incremental | Use `delete_by_ids` for file-level eviction | Leverages existing ChromaDB + PostgreSQL capability |
| `--force` bypasses embedding compat check | `--force` now also bypasses manifest (full reindex) | Single flag controls both embedding compat and manifest bypass |

**No deprecated approaches:** The existing full-reindex path is preserved as the `--force` behavior.

---

## Open Questions

1. **JobRecord force field — CONFIRMED MISSING, must add**
   - Confirmed: `JobRecord` (inspected `models/job.py`) does NOT have a `force` field.
   - Action required: Add `force: bool = Field(default=False, ...)` to `JobRecord`. Update `JobWorker._process_job()` to pass `force=job.force` to `IndexRequest`. Update index API router to set `force=force` on `JobRecord` at enqueue time.
   - This is required for EVICT-08.

2. **BM25 rebuild for incremental runs — CONFIRMED: full rebuild from all nodes required**
   - Confirmed: `BM25IndexManager.build_index(nodes)` does a full corpus rebuild (no incremental add).
   - Strategy: After incremental indexing, collect chunk IDs for ALL files from the updated manifest. Fetch unchanged chunks from vector store via `get_by_id()` calls. Build `TextNode` objects from fetched data. Combine with `TextNode` objects from new chunks. Call `build_index(all_nodes)`.
   - This adds one `get_by_id()` call per unchanged chunk on each reindex. For large unchanged sets, this may be slow. Alternative: store full node data in manifest (large file). Recommend starting with `get_by_id()` approach and optimizing if needed.

3. **Manifest "source" field format in chunk metadata**
   - What we know: `chunk.metadata.to_dict()` includes a "source" key.
   - The `IndexingService` normalizes folder path to `abs_folder_path = os.path.abspath(request.folder_path)`. The DocumentLoader should produce absolute source paths from this base.
   - Recommendation: When building manifest, always normalize with `str(Path(fp).resolve())` before storing. This ensures consistent keys across OS restarts and symlink changes.

4. **CLI eviction summary display (EVICT-09)**
   - The job runs asynchronously. The summary must be stored in the `JobRecord` or `JobDetailResponse`.
   - Recommendation: Add `eviction_summary: dict[str, Any] | None = Field(default=None, ...)` to `JobRecord`. `JobWorker` populates it after `compute_diff_and_evict()`. `JobDetailResponse.from_record()` includes it. CLI `jobs <JOB_ID>` command displays it.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `agent_brain_server/services/folder_manager.py` — atomic write pattern, asyncio.Lock usage
- Direct codebase inspection: `agent_brain_server/storage/protocol.py` — StorageBackendProtocol with delete_by_ids (already present)
- Direct codebase inspection: `agent_brain_server/storage/chroma/backend.py` — delete_by_ids implementation with empty-list guard
- Direct codebase inspection: `agent_brain_server/storage/postgres/backend.py` — delete_by_ids SQL with RETURNING
- Direct codebase inspection: `agent_brain_server/services/indexing_service.py` — pipeline structure, force flag, folder_manager integration point
- Direct codebase inspection: `agent_brain_server/storage_paths.py` — SUBDIRECTORIES list, state_dir layout
- Direct codebase inspection: `agent_brain_server/job_queue/job_worker.py` — job processing, verification logic, hardcoded force=False
- Direct codebase inspection: `agent_brain_server/models/index.py` — IndexRequest.force field
- Direct codebase inspection: `agent_brain_server/models/job.py` — CONFIRMED: JobRecord has NO force field, must add
- Direct codebase inspection: `agent_brain_server/indexing/bm25_index.py` — CONFIRMED: build_index() is full rebuild, no incremental

### Secondary (MEDIUM confidence)
- Phase 12 prior decisions (from phase_context): atomic JSONL writes, two-step ChromaDB delete guard, delete_by_ids on StorageBackendProtocol
- Python stdlib documentation (hashlib, os.stat, pathlib) — well-known stable APIs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all confirmed by direct codebase inspection, no new dependencies
- Architecture: HIGH — ManifestTracker mirrors FolderManager exactly; all patterns are established in codebase
- Integration points: HIGH — IndexingService._run_indexing_pipeline() fully readable; insertion point clear
- BM25 rebuild strategy: HIGH — API confirmed, full-rebuild-with-all-nodes strategy confirmed correct
- JobRecord.force field: HIGH — CONFIRMED missing, confirmed action: add it
- Manifest scalability at >50k files: LOW — theoretical concern, not measured

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable domain, internal codebase — changes only on new phases)
