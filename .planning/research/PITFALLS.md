# Domain Pitfalls

**Domain:** Index folder management, file type filtering, chunk eviction, content injection
**Researched:** 2026-02-23

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: ChromaDB Metadata Filter Limitations

**What goes wrong:** ChromaDB's `where` filter doesn't support prefix matching or regex. Attempting to delete all chunks from folder `/abs/path/src` requires querying ALL chunks, filtering in Python, then bulk deleting. Slow on large collections (100K+ chunks).

**Why it happens:** Developers assume metadata filters support SQL-LIKE patterns (`source LIKE '/abs/path/%'`). ChromaDB only supports exact match, `$in`, `$or`, `$and` operators. No `$starts_with` or regex.

**Consequences:** Folder removal takes 30+ seconds on large indexes, blocks other operations, risks timeout. Users frustrated by slow cleanup.

**Prevention:**
1. Query all chunks (no filter), filter by path prefix in Python
2. Track file→chunk mapping in manifest (Phase 2) for direct bulk delete
3. Add index on `source` field (ChromaDB doesn't support custom indexes, so this doesn't help)
4. Batch deletes in chunks of 1000 IDs to avoid memory issues

**Detection:** Time folder removal operation. If > 5 seconds for 10K chunks, filter performance issue confirmed.

---

### Pitfall 2: Absolute Path Normalization Inconsistency

**What goes wrong:** User indexes `/path/to/src` and `/path/to/./src` (same folder, different representations). System creates two entries in indexed_folders list. Removing one doesn't remove the other's chunks. Duplicates accumulate.

**Why it happens:** Pathlib resolves `.` and `..` but doesn't deduplicate symlinks. macOS is case-insensitive but case-preserving — `/Path/To/Src` != `/path/to/src` in manifest but refers to same folder.

**Consequences:** Duplicate chunks, wasted storage, confusion about what's indexed. User removes folder but chunks remain.

**Prevention:**
1. Normalize ALL paths with `Path(folder_path).resolve()` before storing (resolves symlinks + relative paths)
2. Case-normalize on case-insensitive filesystems: `str(path).lower()` on macOS/Windows
3. Dedup check: Query indexed folders, reject if normalized path already exists
4. Document: "Indexed folder paths are resolved to absolute canonical form"

**Detection:** `agent-brain folders list` shows `/path/to/src` twice with different cases or symlink representations.

---

### Pitfall 3: JSONL Corruption from Concurrent Writes

**What goes wrong:** Two indexing jobs complete simultaneously, both append to `indexed_folders.jsonl`. File becomes corrupted with interleaved writes: `{"folder_path": "/path1"{"folder_path": "/path2"}}`.

**Why it happens:** JSONL append is NOT atomic on most filesystems. Multiple processes can write concurrently. Python's `open("a")` doesn't lock the file.

**Consequences:** JSONL parse error on startup. Manifest unreadable. All indexed folder tracking lost.

**Prevention:**
1. File locking: `import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_EX)` before write
2. Single writer pattern: Indexing service serializes manifest writes via asyncio lock
3. Atomic writes: Write to temp file, then atomic rename (os.replace)
4. Validation: Read-after-write check that last line is valid JSON

**Detection:** `JSONDecodeError` when loading manifest. Inspect file, see interleaved JSON objects.

---

### Pitfall 4: Chunk Eviction Without File→Chunk Mapping

**What goes wrong:** User removes folder `/abs/path/src`. System queries ChromaDB for chunks with `source` starting with folder path. Query returns 0 results because chunk metadata uses `file_path` field, not `source`.

**Why it happens:** Inconsistent metadata field naming. DocumentLoader sets `source`, chunker sets `file_path`, both present but different formats. Developer queries wrong field.

**Consequences:** Folder "removed" from list but chunks remain in index. User confused. Storage not freed. Queries still return deleted folder's results.

**Prevention:**
1. Standardize metadata schema: Use ONLY `source` field for file path (existing pattern)
2. Query ALL relevant fields: `where={"$or": [{"source": ...}, {"file_path": ...}]}`
3. Manifest tracking (Phase 2): Store chunk IDs explicitly, delete by ID list
4. Integration test: Remove folder, verify chunk count decreases

**Detection:** Remove folder → `agent-brain status` shows chunk count unchanged. Query for folder path returns results.

---

### Pitfall 5: File Type Preset Conflicts with Glob Patterns

**What goes wrong:** User specifies `--include-type python --include *.py*`. System expands `python` preset to `["*.py", "*.pyi", "*.pyx"]`, then adds `*.py*` from CLI. Result: `["*.py", "*.pyi", "*.pyx", "*.py*"]`. The `*.py*` glob matches `*.py**` (anything starting with `.py`), causing unexpected matches like `.py-cache/` files.

**Why it happens:** Mixing preset expansion with glob patterns. Users don't understand precedence. Glob wildcard `*` matches arbitrary characters including directory separators in some implementations.

**Consequences:** Unexpected files indexed (cache files, backup files, temp files). Index polluted. User frustrated.

**Prevention:**
1. Clear precedence: `--include-type` and `--include` are mutually exclusive, or `--include-type` resolved first, then `--include` as additional patterns
2. Validate glob patterns: Reject `*.py*` (ambiguous), suggest `*.py` or `*.py[io]`
3. Document: "`--include-type python` includes .py, .pyi, .pyx. For custom patterns, use `--include` only."
4. Warn on overlap: "Preset 'python' already includes *.py, --include *.py is redundant"

**Detection:** Index includes files with weird extensions like `.py-backups`, `.pycache`. User reports unexpected results.

---

## Moderate Pitfalls

### Pitfall 6: Folder Removal During Active Indexing

**What goes wrong:** Indexing job running for `/path/src`. User runs `agent-brain folders remove /path/src` simultaneously. Remove command deletes chunks while indexing job adds new chunks. Race condition results in partial folder indexed.

**Why it happens:** No job coordination. Remove command doesn't check active jobs. Indexing service doesn't lock folder during indexing.

**Prevention:**
1. Job queue check: Remove command rejects if active job for folder exists
2. Folder lock: Indexing service marks folder as "indexing", remove waits for completion
3. Atomic operation: Remove command cancels active job first, then removes chunks

**Detection:** Remove folder → some chunks deleted but new ones appear. Folder not fully removed.

---

### Pitfall 7: Content Injector Script Exceptions Break Indexing

**What goes wrong:** User provides `enrich.py` with `process_chunk()` function. Script raises `KeyError` accessing chunk["metadata"]["source"]`. Entire indexing job fails, already-generated embeddings wasted.

**Why it happens:** User script not validated before indexing starts. Exception in injector propagates to indexing service, crashes job.

**Prevention:**
1. Injector validation: Call `process_chunk()` with sample chunk before starting indexing
2. Exception handling: Catch injector exceptions, log warning, skip enrichment for failing chunk
3. Dry-run mode: `agent-brain inject --dry-run enrich.py` tests script without indexing
4. Schema validation: Provide `ChunkSchema` type hint, validate script returns correct structure

**Detection:** Indexing job fails mid-way with Python traceback from user script. Embeddings wasted.

---

### Pitfall 8: Manifest File Growth on Large Deployments

**What goes wrong:** User indexes 1,000 folders. `indexed_folders.jsonl` grows to 500KB. Loading manifest on startup takes 2 seconds. Every folder addition appends, slowing down over time.

**Why it happens:** JSONL append-only pattern doesn't compact. Deleted folders leave entries. File grows unbounded.

**Prevention:**
1. Periodic compaction: Rewrite JSONL removing deleted folders (cron job or on startup)
2. Database alternative (Phase 3): Store manifest in SQLite instead of JSONL
3. Lazy loading: Don't load entire manifest into memory, query on-demand
4. Pagination: `agent-brain folders list --limit 100 --offset 0`

**Detection:** Startup time increases linearly with folder count. `indexed_folders.jsonl` > 1MB.

---

### Pitfall 9: File Type Presets Missing Edge Cases

**What goes wrong:** User indexes codebase with `--include-type python`. System expands to `["*.py", "*.pyi", "*.pyx"]`. Misses `*.pyw` (Windows Python GUI scripts) and `*.pyc` (compiled bytecode, should exclude).

**Why it happens:** Preset definition incomplete. No testing with real-world codebases.

**Prevention:**
1. Comprehensive presets: Research common file extensions per language (ripgrep uses 40+ for Python)
2. Explicit exclusions: `python-source` (only source) vs `python-all` (source + bytecode)
3. User override: Allow custom presets in config file (`~/.agent-brain/presets.yaml`)
4. Preset validation: Test presets against real codebases, document covered extensions

**Detection:** User reports missing files. Check preset definition, find missing extensions.

---

### Pitfall 10: Chunk Metadata Merge Conflicts

**What goes wrong:** Chunk has `metadata={"team": "backend"}` from folder-level injection. User script also sets `chunk["metadata"]["team"] = "api"`. Last write wins, original metadata lost.

**Why it happens:** No merge strategy defined. Simple dict update overwrites keys.

**Prevention:**
1. Merge strategy: Folder metadata < file metadata < chunk metadata < injector metadata (explicit precedence)
2. Namespace metadata: `chunk["metadata"]["folder"]["team"]` vs `chunk["metadata"]["injector"]["team"]`
3. Validation: Warn if injector overwrites existing metadata key
4. Document: "Injector metadata takes precedence over folder-level metadata"

**Detection:** Unexpected metadata values. User reports team field wrong.

---

## Minor Pitfalls

### Pitfall 11: Folder List Display Truncation

**What goes wrong:** User has 100 indexed folders. `agent-brain folders list` prints all 100 to terminal. Overwhelming, hard to find specific folder.

**Prevention:** Paginate list output, add `--limit` and `--filter` flags. Default: show 20 most recent.

---

### Pitfall 12: No Feedback During Bulk Deletion

**What goes wrong:** Removing large folder takes 30 seconds. CLI shows no progress. User thinks command hung.

**Prevention:** Progress bar for bulk deletion (`Removing chunks: 1420/5000 [28%]`).

---

### Pitfall 13: Case-Sensitive Path Comparison

**What goes wrong:** User indexes `/path/TO/src` on macOS (case-insensitive FS). Later removes `/path/to/src`. Command fails: "Folder not found".

**Prevention:** Case-normalize paths on case-insensitive systems before comparison.

---

### Pitfall 14: Symlink Loop Detection

**What goes wrong:** User indexes folder with symlink loop (`src/link → ../../src`). DocumentLoader follows symlink infinitely, hangs.

**Prevention:** Track visited inodes, detect loops, skip symlinks by default or add `--follow-symlinks` flag.

---

### Pitfall 15: Folder Removal Without Confirmation

**What goes wrong:** User typos `agent-brain folders remove /path/to/porject` (missing 'j'). Command silently succeeds (folder not indexed), no error. User confused.

**Prevention:** Validate folder exists in indexed list before removal. Confirm with `--yes` flag for scripting.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Folder list persistence | JSONL corruption from concurrent writes | File locking or atomic writes |
| Folder removal | ChromaDB metadata filter performance | Track file→chunk mapping in manifest |
| File type presets | Incomplete extension lists | Test with real codebases, document coverage |
| Content injection | Script exceptions break indexing | Validate script before indexing, exception handling |
| Manifest tracking (Phase 2) | File growth on large deployments | Periodic compaction or SQLite alternative |
| Chunk eviction (Phase 2) | Metadata field inconsistency | Standardize on `source` field, query all variants |

## Sources

**Folder Management:**
- [RLAMA RAG Pipeline with Directory Watching](https://rlama.dev/blog/directory-watching) — Folder exclusion patterns
- [Building a Production-Ready RAG System with Incremental Indexing](https://dev.to/guptaaayush8/building-a-production-ready-rag-system-with-incremental-indexing-4bme) — Manifest-based change detection
- [LangChain: Delete vectors by source](https://github.com/langchain-ai/langchain/discussions/19903) — Bulk deletion patterns

**ChromaDB Limitations:**
- [ChromaDB: Delete Data](https://docs.trychroma.com/docs/collections/delete-data) — `where` filter operators (no regex/prefix matching)
- [Efficient Document Embedding Management with ChromaDB](https://blog.gopenai.com/efficient-document-embedding-management-with-chromadb-deleting-resetting-and-more-dac0e70e713b) — Bulk deletion patterns

**File Path Normalization:**
- [Python pathlib documentation](https://docs.python.org/3/library/pathlib.html) — `Path.resolve()` for canonical paths
- [How to Handle File Paths in Python](https://realpython.com/python-pathlib/) — Cross-platform path handling

**Concurrent File Writes:**
- [Python fcntl documentation](https://docs.python.org/3/library/fcntl.html) — File locking on Unix systems
- [JSONL Best Practices](https://jsonltools.com/jsonl-for-developers) — Append-safe writes for crash recovery
