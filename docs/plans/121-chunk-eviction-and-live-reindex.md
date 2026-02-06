# Plan: Chunk Eviction & Live Reindexing

## Objective
Eliminate ghost chunks when files shrink, move, or delete, and keep the index in sync with file changes via targeted reindex events—without requiring `agent-brain reset --yes`.

## Problems
- Stable chunk IDs (`hash(path + idx)`) mean upserts update existing IDs but never delete superseded ones, so shorter files leave stale chunks. (See `ContextAwareChunker` ID seeds)
- Reindex currently only upserts; no delete pass in `IndexingService._run_indexing_pipeline` or `VectorStoreManager`.
- Path-based IDs make renames produce duplicates (old path IDs remain).
- Deletions are not detected; removed files leave their chunks behind.
- Empty `collection.delete(ids=[])` can delete the entire collection in some Chroma versions—must guard inputs. citeturn0search0
- Chroma supports deleting by `ids` or metadata `where` filters, which we can leverage for pruning. citeturn0search14turn0search3

## Strategy Overview
1) **Per-file prune-then-upsert**: For every file we reindex, compute the new stable chunk IDs, delete obsolete IDs for that file, then upsert the new chunks.
2) **Manifest-driven deletions**: Persist a manifest of previously indexed file paths and their chunk counts; on a run, detect removed or renamed files and delete their chunks.
3) **Change-triggered reindex**: Add a change detector (watcher or git-diff mode) to enqueue reindex jobs for touched files/dirs; reuse the job queue design so operations are non-blocking.
4) **Safety rails**: Never call `delete` with an empty `ids`; prefer `where` filters (`source == path`) when available; gate deletes behind explicit `allow_delete` flag to avoid accidental collection wipes.

## Design Details

### Data Model & Tracking
- **Chunk ID schema**: Keep existing `chunk_<md5(path + idx)>` for determinism.
- **File manifest**: New JSON file under Chroma persist dir (e.g., `manifest.jsonl`) keyed by absolute path → {chunk_count, last_hash, last_indexed_at}.
- **Hashing**: Store a fast hash (xxhash/blake3) of file contents to detect changes; optional size+mtime fallback.

### Vector Store API Additions
- Add `VectorStoreManager.delete_by_ids(ids: list[str])` wrapping `collection.delete(ids=ids)`; no-op if list empty (early return). Guard empty list to avoid catastrophic delete (bug noted above). citeturn0search0
- Add `delete_by_source(path: str)` using `where={"source": path}` for bulk removal when chunk IDs are unknown; relies on metadata stored today. citeturn0search14
- Optional `delete_by_prefix(prefix: str)` for directory-level pruning using `$contains` on `source` if paths are hierarchical.

### IndexingService Flow Changes
For each file in the batch:
1. Chunk & embed → produce `new_ids`.
2. Determine `stale_ids`:
   - If manifest has prior `chunk_count = n_old`, compute stable IDs `chunk_<hash(path+idx)>` for idx ≥ len(new_ids) to n_old-1.
   - Or query Chroma `get(where={"source": path}, include=["ids"])` to list existing IDs (bounded by a limit + pagination if needed). citeturn0search9
3. Delete stale IDs: prefer `delete(ids=stale_ids)`; if list large, use `delete(where={"source": path})` after verifying `new_ids` set is known. citeturn0search1turn0search14
4. Upsert current chunks.
5. Update manifest entry for the path (chunk_count, file hash, timestamp).

### Handling Renames and Deletions
- After scanning files, compute `manifest_paths - current_paths`; for each missing path, call `delete_by_source(path)` and drop manifest entry.
- For renames, if hash matches an existing manifest entry under a different path, delete old path’s chunks then reindex under new path.

### Change Detection / Eventing
- **Option A: Watchdog** (dev mode): start a file watcher; enqueue per-path reindex jobs on change/create/delete events (debounced).
- **Option B: Git diff** (CI): `agent-brain index --changed-since <ref>`; resolve file list via `git diff --name-status`, then run the prune-upsert cycle on those paths.
- **Option C: API hook**: expose `/index/refresh` accepting a list of paths; each path triggers the per-file prune-upsert.

### Safety & Performance
- Hard-cap delete pagination (e.g., 10k IDs per call) to avoid memory spikes; stream IDs.
- Early return when `new_ids` is empty AND file is empty: delete existing IDs by source, mark manifest chunk_count=0.
- All delete operations require explicit `allow_delete=True` in server settings to reduce blast radius in prod.
- Log deletions with counts for observability; emit metrics: `chunks_deleted`, `chunks_upserted`, `files_pruned`.

### Testing Plan
- **Unit**: VectorStoreManager delete wrappers (empty list guard, where filter). Mock Chroma.
- **Integration**: index a file with 5 chunks → shrink to 2 → expect 3 deletes, 2 upserts, search returns only new text.
- **Rename**: index `a.py`, rename to `b.py`, reindex → old path chunks gone, new path present.
- **Delete**: remove file, run refresh → no results for that path.
- **Watcher**: modify file; ensure change event triggers prune-upsert.
- **Concurrency**: run two reindex jobs on same path; lock to avoid interleaved deletes.

### Rollout / Migration
- Ship behind a feature flag `AGENT_BRAIN_PRUNE_CHUNKS=true`.
- On first run with flag enabled, build manifest by querying collection IDs grouped by `source` (paged) to avoid full reset.
- Provide CLI command `agent-brain vacuum` to force a full manifest rebuild + prune for all known paths.

## Success Criteria
- Reindexing a shortened file leaves zero ghost chunks (verified via get/delete counts and search results).
- Deleting or renaming files removes old chunks within one refresh cycle.
- No accidental full-collection deletes when `ids=[]` (guarded and tested).
- Change-triggered reindex keeps vector store consistent without `reset`.
