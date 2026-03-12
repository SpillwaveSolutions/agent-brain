# Pitfalls Research: v7.0 Index Management & Content Pipeline

**Domain:** RAG Index Management, Chunk Eviction, Content Injection, Folder Tracking
**Researched:** 2026-02-23
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: ChromaDB Empty IDs Delete Bug (Collection Wipe)

**What goes wrong:**
Calling `collection.delete(ids=[])` with an empty list deletes ALL documents in the ChromaDB collection. This is a documented bug that persists in ChromaDB 0.3.23+ where empty `ids` parameter is treated as "delete everything that matches the where clause" rather than "delete nothing".

**Why it happens:**
When implementing folder removal or selective chunk eviction, developers often build a list of IDs to delete based on metadata filters. If the filter returns no matches (e.g., folder path typo, already deleted), passing the empty list to `delete()` triggers catastrophic data loss. This is especially dangerous during:
- Folder removal when folder path doesn't exist
- Chunk eviction when file hash doesn't match
- Concurrent deletion operations where another process removed the target first

**How to avoid:**
```python
# DANGEROUS — DO NOT DO THIS
ids_to_delete = get_ids_for_folder(folder_path)  # might be []
collection.delete(ids=ids_to_delete)  # WIPES COLLECTION IF EMPTY

# SAFE — Always check before delete
ids_to_delete = get_ids_for_folder(folder_path)
if ids_to_delete:
    collection.delete(ids=ids_to_delete)
else:
    logger.warning(f"No chunks found for folder {folder_path}")
```

**Warning signs:**
- Index count suddenly drops to zero after folder management operation
- "Document not found" errors after delete operations that should have been no-ops
- Delete operations that complete instantly (0ms) — suggests no work done but might indicate bug trigger

**Phase to address:**
Phase 12 (Folder Management CLI) — Add explicit guard checks before all delete operations. Phase 13 (Chunk Eviction) — Validate that eviction logic never passes empty lists to delete().

---

### Pitfall 2: Stale Chunk Accumulation (Zombie Embeddings)

**What goes wrong:**
When source files are updated, old chunks remain in the vector store alongside new chunks, causing search results to return outdated content. Users query for current code/docs but retrieve stale embeddings representing deleted or modified content. Over time, vector store fills with duplicate and obsolete chunks, degrading search quality and wasting storage.

**Why it happens:**
Naive indexing implementations append new chunks without removing old ones. File updates trigger re-chunking and new embeddings, but the system lacks:
- File-to-chunk mapping to identify old chunks
- Content hashing to detect changes
- Metadata versioning to track chunk generations
- Eviction strategy to remove superseded chunks

This is especially problematic with code files that change frequently (hot paths, configuration files).

**How to avoid:**
**Strategy 1: Delete-then-insert (Transactional)**
```python
# On file update:
# 1. Query existing chunks by source_file metadata
old_chunk_ids = storage_backend.query_by_metadata({"source_file": file_path})
# 2. Delete old chunks (with empty check!)
if old_chunk_ids:
    storage_backend.delete_chunks(old_chunk_ids)
# 3. Insert new chunks
storage_backend.upsert_chunks(new_chunks)
```

**Strategy 2: Content Hash Versioning**
```python
# Chunk metadata includes content hash
chunk.metadata = {
    "source_file": file_path,
    "content_hash": hashlib.sha256(file_content).hexdigest(),
    "indexed_at": datetime.now(timezone.utc).isoformat()
}

# On re-index, skip if hash unchanged
existing_hash = storage_backend.get_file_hash(file_path)
new_hash = hashlib.sha256(file_content).hexdigest()
if existing_hash == new_hash:
    logger.info(f"Skipping {file_path} — content unchanged")
    return
```

**Strategy 3: Versioned Embeddings**
Use version metadata and periodic garbage collection:
```python
chunk.metadata = {"source_file": file_path, "version": 2}
# Later: delete all chunks where version < current_version
```

**Warning signs:**
- Search results include code that was deleted weeks ago
- Vector store size grows monotonically despite stable source directory size
- Duplicate results with different timestamps for same source file
- "I just updated this but search still shows old version"

**Phase to address:**
Phase 13 (Chunk Eviction & Live Reindex) — Implement delete-before-insert strategy with content hash change detection. Phase 12 (Folder Management) — Track file-to-chunk mapping for eviction.

---

### Pitfall 3: File Manifest Persistence Failure (State Loss on Restart)

**What goes wrong:**
Folder tracking state (which folders are indexed, file count, last index time) is stored only in-memory. Server restarts lose all folder management state. Users add folders via CLI, restart server, and `/folders/list` returns empty. Re-adding folders causes duplicate indexing. No way to reconstruct "what was indexed" without re-scanning filesystem.

**Why it happens:**
Developer stores folder manifest in Python dict/list without persistence layer:
```python
class IndexingService:
    def __init__(self):
        self.indexed_folders = []  # ⚠️ LOST ON RESTART
```

RAG systems often focus on vector storage and ignore operational metadata persistence. IndexingService currently tracks nothing about folder origins — chunks have `source_file` metadata but no `folder_root` or `index_session_id`.

**How to avoid:**
**Strategy 1: Persistent Manifest File (Simple)**
```python
# .claude/agent-brain/index_manifest.json
{
  "folders": [
    {
      "path": "/path/to/project",
      "added_at": "2026-02-23T10:30:00Z",
      "file_count": 142,
      "last_indexed_at": "2026-02-23T11:00:00Z",
      "include_patterns": ["*.py", "*.md"]
    }
  ]
}
```

Load on startup, persist after modifications. Use file locking for concurrent access.

**Strategy 2: Store in Vector DB Metadata (Backend Agnostic)**
Create special "manifest" documents:
```python
manifest_chunk = {
    "id": "manifest:folder:/path/to/project",
    "content": "Indexed folder manifest",
    "metadata": {
        "type": "folder_manifest",
        "folder_path": "/path/to/project",
        "added_at": "...",
        "file_count": 142
    }
}
```

Query by `type: folder_manifest` to reconstruct state.

**Strategy 3: Use Storage Backend for All State (PostgreSQL Path)**
If using PostgreSQL backend, add `indexed_folders` table with schema:
```sql
CREATE TABLE indexed_folders (
    id SERIAL PRIMARY KEY,
    folder_path TEXT UNIQUE NOT NULL,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    file_count INT,
    include_patterns JSONB
);
```

ChromaDB backend falls back to JSON manifest file.

**Warning signs:**
- `/folders/list` returns empty after server restart despite previous indexing
- Users report "I added this yesterday but it's gone"
- Duplicate indexing of same folder after restart
- No audit trail of what was indexed when

**Phase to address:**
Phase 12 (Folder Management CLI) — Implement persistent manifest with JSON file. Phase 15 (PostgreSQL Folder State) — Migrate to database table for PostgreSQL backend.

---

### Pitfall 4: Content Injection Subprocess Zombies (CLI Tool Orphans)

**What goes wrong:**
Content injector spawns subprocess (`claude`, `opencode`, custom CLI tools) but fails to properly wait for completion. Process exits, leaving zombie processes. Over multiple injection operations, zombies accumulate, consuming PIDs and potentially leaking file descriptors. On production systems, PID exhaustion blocks new process creation.

**Why it happens:**
Naive subprocess usage without proper cleanup:
```python
# DANGEROUS — Creates zombies
import subprocess
proc = subprocess.Popen(["claude", "--version"])
# ⚠️ Parent exits without wait() — zombie created
```

Python's `subprocess.run()` with timeout doesn't handle signals properly. CLI tool might hang indefinitely (network timeout, deadlock, user input prompt). If parent kills child with SIGTERM but doesn't reap exit status, zombie persists.

**How to avoid:**
**Strategy 1: Use subprocess.run() with Proper Cleanup**
```python
import subprocess

try:
    result = subprocess.run(
        ["claude", "query", "--input", content],
        timeout=30,
        capture_output=True,
        text=True,
        check=True  # Raises on non-zero exit
    )
    return result.stdout
except subprocess.TimeoutExpired:
    # Process killed, status reaped automatically
    raise ContentInjectionTimeout(f"CLI tool exceeded 30s timeout")
except subprocess.CalledProcessError as e:
    # Non-zero exit, status reaped
    raise ContentInjectionError(f"CLI tool failed: {e.stderr}")
```

**Strategy 2: Process Group Management**
Kill entire process tree on timeout:
```python
import os
import signal
import psutil

proc = subprocess.Popen(
    ["complex-cli-tool"],
    preexec_fn=os.setsid  # Create new session
)

try:
    proc.wait(timeout=30)
except subprocess.TimeoutExpired:
    # Kill entire process group
    pgid = os.getpgid(proc.pid)
    os.killpg(pgid, signal.SIGTERM)
    proc.wait()  # Reap zombie
```

**Strategy 3: Ignore SIGCHLD for Auto-Reaping**
For fire-and-forget background tasks:
```python
import signal
signal.signal(signal.SIGCHLD, signal.SIG_IGN)  # Auto-reap children
```

**Warning signs:**
- `ps aux | grep -i defunct` shows processes in `<defunct>` state
- `/proc/sys/kernel/pid_max` approaching limit (check `/proc/sys/kernel/pid_current`)
- "Cannot fork: Resource temporarily unavailable" errors
- File descriptor leaks (`lsof | wc -l` growing over time)

**Phase to address:**
Phase 14 (Content Injection CLI) — Use `subprocess.run()` with timeout and proper exception handling. Add health check that counts zombie processes and alerts.

---

### Pitfall 5: ChromaDB Concurrent Operation Race Conditions (Single-Threaded Blocking)

**What goes wrong:**
ChromaDB is fundamentally single-threaded — only one thread can read/write to a given HNSW index at a time. Under concurrent load (multiple folder indexing jobs, live reindex while querying), operations block sequentially. Average latency increases dramatically. User triggers folder indexing, then immediately queries, but query blocks until indexing completes (potentially minutes).

**Why it happens:**
ChromaDB v0.4+ fixed many thread-safety bugs but remains single-threaded internally. HNSW algorithm has parallelism, but only one operation at a time per index. Developer assumes concurrent safety:
```python
# Job 1: Index 10k documents (takes 5 minutes)
await storage_backend.upsert_chunks(large_batch)

# Job 2: Query during indexing (blocks until Job 1 finishes)
results = await storage_backend.query("search term")  # ⚠️ 5 min latency
```

Agent Brain job queue processes one job at a time (sequential), which mitigates but doesn't eliminate issue. User could issue query via API while job runs.

**How to avoid:**
**Strategy 1: Job Queue Concurrency Control (Current Approach)**
Maintain single-threaded job execution, block queries during indexing:
```python
# In query endpoint
if job_queue.has_running_job():
    raise HTTPException(503, "Indexing in progress, retry in 30s")
```

**Strategy 2: Read-Write Separation**
Allow queries during indexing with eventual consistency trade-off:
```python
# Use asyncio.Lock for write operations only
write_lock = asyncio.Lock()

async def upsert_chunks(chunks):
    async with write_lock:
        await storage_backend.upsert_chunks(chunks)

async def query(text):
    # No lock — allow concurrent reads
    # May return incomplete results during indexing
    return await storage_backend.query(text)
```

**Strategy 3: PostgreSQL Backend for Concurrency**
PostgreSQL handles concurrent reads/writes natively via MVCC. Phase 6 already implemented PostgreSQL backend — use it for high-concurrency deployments.

**Warning signs:**
- Query latency spikes from <100ms to >30s during indexing
- `/health/status` shows long queue times
- Users report "search is frozen" during indexing operations
- Timeout errors on queries that normally succeed

**Phase to address:**
Phase 12 (Folder Management) — Document concurrency limits in CLI help text. Phase 13 (Live Reindex) — Add `/health/indexing-status` endpoint that clients poll before querying. Phase 15+ — Recommend PostgreSQL backend for concurrent usage.

---

### Pitfall 6: Glob Pattern Edge Cases (Unexpected File Inclusion)

**What goes wrong:**
Smart filtering with glob patterns (e.g., `*.py`, `**/*.md`, `[!_]*.ts`) fails to match expected files or includes unintended files due to:
- Spaces in filenames (glob breaks on unquoted paths)
- Newlines in filenames (rare but possible on Unix)
- Case sensitivity differences (macOS case-insensitive, Linux case-sensitive)
- Recursive glob (`**`) not working without `recursive=True` flag
- Negation patterns (`[!_]`) matching more than intended

Users configure "index all Python files except tests" with `*.py, !test_*.py` but test files still get indexed.

**Why it happens:**
Python's `glob.glob()` has subtle behavior:
```python
# WRONG — Doesn't recurse by default
glob.glob("**/*.py")  # Only matches ./foo.py, not ./subdir/bar.py

# CORRECT
glob.glob("**/*.py", recursive=True)

# WRONG — Negation doesn't work as expected
glob.glob("!test_*.py")  # Returns literal string "!test_*.py"

# CORRECT — Use separate filter
files = [f for f in glob.glob("*.py") if not f.startswith("test_")]
```

**How to avoid:**
**Strategy 1: Use pathlib (Modern Approach)**
```python
from pathlib import Path

# Recursive glob with proper negation
py_files = Path(folder).rglob("*.py")
py_files = [f for f in py_files if not f.name.startswith("test_")]
```

**Strategy 2: Explicit Include/Exclude Lists**
```python
# CLI accepts both include and exclude patterns
agent-brain index /project --include "*.py,*.md" --exclude "test_*,*_test.py,__pycache__"
```

Validation logic ensures patterns are parsed consistently.

**Strategy 3: Preset Patterns**
Define presets for common use cases:
```python
PRESETS = {
    "python": {"include": ["*.py"], "exclude": ["test_*.py", "*_test.py", "conftest.py"]},
    "docs": {"include": ["*.md", "*.rst"], "exclude": ["LICENSE*", "README*"]},
    "code": {"include": ["*.py", "*.ts", "*.js"], "exclude": ["*.min.js", "dist/*"]}
}

# CLI usage
agent-brain index /project --preset python
```

**Warning signs:**
- Test files appearing in search results despite exclusion pattern
- Empty search results when files definitely exist
- Different file counts on macOS vs Linux for same folder
- "Pattern matched 0 files" when files exist

**Phase to address:**
Phase 12 (Folder Management) — Implement include/exclude pattern validation with test suite covering edge cases. Phase 13 (Smart Filtering) — Add preset patterns and clear documentation of glob behavior.

---

### Pitfall 7: Metadata Filter Type Inconsistency (ChromaDB Query Failure)

**What goes wrong:**
ChromaDB metadata filtering fails or returns unexpected results when metadata field types are inconsistent across documents. Example: `file_size` stored as integer `12345` for one document, string `"12345"` for another. Filter `where={"file_size": {"$gt": 10000}}` only matches integer type, silently skipping string type.

**Why it happens:**
ChromaDB doesn't enforce schema on metadata — any JSON-serializable value is accepted. Developer indexing code inconsistently types metadata:
```python
# File 1: size as int
chunk.metadata = {"source_file": "a.py", "file_size": 12345}

# File 2: size as string (from CLI arg parsing)
chunk.metadata = {"source_file": "b.py", "file_size": "67890"}

# Query fails to match File 2
results = collection.query(where={"file_size": {"$gt": 10000}})
```

Also problematic: date strings with inconsistent formats (`2026-02-23` vs `February 23, 2026`), boolean values as strings (`"true"` vs `True`).

**How to avoid:**
**Strategy 1: Enforce Schema at Chunk Creation**
```python
from pydantic import BaseModel, Field

class ChunkMetadata(BaseModel):
    source_file: str
    file_size: int  # Type enforced
    indexed_at: str  # ISO 8601 datetime
    chunk_index: int

# Validate before storage
metadata = ChunkMetadata(
    source_file=file_path,
    file_size=os.path.getsize(file_path),  # Always int
    indexed_at=datetime.now(timezone.utc).isoformat(),
    chunk_index=i
)
chunk.metadata = metadata.dict()
```

**Strategy 2: Migration Script for Existing Data**
```python
# Fix inconsistent types
for chunk in collection.get()["metadatas"]:
    if isinstance(chunk["file_size"], str):
        chunk["file_size"] = int(chunk["file_size"])
    collection.update(ids=[chunk["id"]], metadatas=[chunk])
```

**Strategy 3: Document Metadata Schema**
Create `docs/metadata_schema.md`:
```markdown
## Chunk Metadata Schema

| Field | Type | Example | Required |
|-------|------|---------|----------|
| source_file | str | "/path/to/file.py" | Yes |
| file_size | int | 12345 | Yes |
| indexed_at | str (ISO 8601) | "2026-02-23T10:30:00Z" | Yes |
| folder_root | str | "/path/to/project" | No |
```

**Warning signs:**
- Metadata filters return fewer results than expected
- Query by numeric range misses documents
- "Cannot compare str and int" errors in logs
- Filters work for recent documents but not old ones

**Phase to address:**
Phase 12 (Folder Management) — Define and enforce metadata schema with Pydantic. Phase 13 (Chunk Eviction) — Add metadata validation to health check endpoint.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store folder list in-memory dict | Simple, no DB dependency | State lost on restart, no audit trail | Never — JSON manifest has minimal overhead |
| Skip content hash check on re-index | Faster indexing | Duplicate stale chunks accumulate | Only for append-only document sets (never updated) |
| Use `subprocess.Popen()` without timeout | Flexible control | Zombie processes, hangs on CLI tool failure | Never — `subprocess.run()` with timeout is standard |
| Allow empty IDs in delete() calls | Simpler code, fewer conditionals | Risk of wiping entire collection | Never — guard check is one line |
| Store metadata as strings (no schema) | Easy prototyping | Filter failures, inconsistent queries | Only in POC phase — enforce schema before production |
| Single-threaded job queue | Simple, no race conditions | Poor UX during long indexing jobs | Acceptable for MVP — migrate to PostgreSQL for concurrency |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| ChromaDB delete() | Passing empty `ids=[]` list | Always check `if ids_to_delete:` before calling |
| CLI subprocess timeout | Using `subprocess.Popen()` without wait | Use `subprocess.run(timeout=30)` with exception handling |
| Content injector tools | Assuming CLI tools always succeed | Wrap in try/except, log stderr, return error codes |
| File glob patterns | Using `**/*.py` without `recursive=True` | Use `pathlib.Path.rglob()` or `glob.glob(..., recursive=True)` |
| Metadata filtering | Storing mixed types (int/str) | Define Pydantic schema, validate at chunk creation |
| PostgreSQL pgvector | Not creating HNSW index | Schema initialization must `CREATE INDEX USING hnsw` |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No chunk eviction strategy | Vector store grows unbounded, stale results | Implement delete-before-insert with content hashing | >10k files with frequent updates |
| Sequential folder indexing | Long blocking operations, poor UX | Job queue with progress tracking, allow concurrent queries (PostgreSQL) | >5 folders, >1k files each |
| No file manifest persistence | Re-index entire project on restart | Persist folder manifest to JSON/database | Any multi-folder project |
| Regex metadata filters | Slow queries on large indexes | Use indexed metadata fields, avoid `$regex` | >100k chunks |
| Embedding every chunk on update | Re-embed unchanged content | Content hash check, skip unchanged files | >1k files with frequent commits |
| ChromaDB under concurrent load | Query latency spikes from 100ms to 30s | Use PostgreSQL backend or serialize operations | >10 concurrent users |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Allow arbitrary CLI tool execution in content injector | Command injection, privilege escalation | Allowlist CLI tools, validate tool paths, run in sandboxed subprocess |
| Index sensitive files (`.env`, credentials) | Secrets leak in search results | Default exclude patterns for sensitive extensions, warn on detection |
| Expose folder paths in API responses | Information disclosure (filesystem structure) | Return folder ID aliases, sanitize paths in error messages |
| No input validation on folder paths | Directory traversal (`../../../etc/passwd`) | Validate paths resolve within allowed roots, reject `..` |
| Store PostgreSQL credentials in YAML | Credential theft from config file | Require env vars for sensitive config, document in setup guide |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress feedback during indexing | "Is it frozen?" uncertainty | WebSocket or SSE for real-time progress, estimated time remaining |
| Silent failures on CLI tool errors | User assumes success, later confusion | Log stderr, return error codes, show user-friendly error messages |
| No indication of indexing vs query blocking | User retries queries, creating more load | Return 503 with "Indexing in progress, retry after 30s" header |
| Folder removal requires exact path match | "I added `/home/user/project` but removal needs `/home/user/project/`" | Normalize paths (strip trailing slash, resolve symlinks) |
| No dry-run mode for glob patterns | User deletes wrong files/folders | Add `--dry-run` flag to show what would be indexed/deleted |
| Unclear folder list output | "Which folders are currently indexed?" | Show folder path, file count, last indexed time, status |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Folder Management:** Often missing persistent manifest — verify state survives restart
- [ ] **Chunk Eviction:** Often missing empty IDs check — verify guard clause before delete()
- [ ] **Content Injection:** Often missing timeout handling — verify subprocess.run() has timeout parameter
- [ ] **Glob Filtering:** Often missing recursive flag — verify `recursive=True` or using pathlib
- [ ] **Metadata Schema:** Often missing type validation — verify Pydantic model enforces types
- [ ] **Concurrent Operations:** Often missing read-write separation — verify queries don't block during indexing
- [ ] **Error Handling:** Often missing subprocess stderr logging — verify errors propagate to user
- [ ] **Path Normalization:** Often missing trailing slash handling — verify paths compared consistently

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| ChromaDB collection wiped by empty delete | HIGH | Restore from backup or re-index all folders (hours to days) |
| Zombie processes accumulate | LOW | `pkill -9 -f defunct` to kill zombies, restart server |
| Stale chunks accumulate | MEDIUM | Run cleanup script: query all source files, compare with disk, delete orphaned chunks |
| Folder manifest lost | MEDIUM | Re-add folders via CLI, deduplicate chunks based on content hash |
| Metadata type inconsistency | MEDIUM | Run migration script to cast all metadata fields to correct types |
| Concurrent operation deadlock | LOW | Restart server, configure PostgreSQL backend for future |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| ChromaDB empty IDs delete bug | Phase 12 (Folder Management) | Unit test: delete(ids=[]) raises ValueError |
| Stale chunk accumulation | Phase 13 (Chunk Eviction) | Integration test: update file, verify old chunks removed |
| File manifest persistence failure | Phase 12 (Folder Management) | E2E test: add folder, restart server, verify folder still listed |
| Subprocess zombies | Phase 14 (Content Injection) | Health check: verify no defunct processes after 100 injections |
| Concurrent operation race conditions | Phase 13 (Live Reindex) | Load test: concurrent queries during indexing, verify latency <500ms (PostgreSQL) or 503 errors (ChromaDB) |
| Glob pattern edge cases | Phase 12 (Folder Management) | Unit test suite: recursive, negation, spaces, case sensitivity |
| Metadata type inconsistency | Phase 12 (Folder Management) | Unit test: metadata validation with Pydantic, test type coercion failures |

---

## Sources

### Critical Bug Documentation
- [ChromaDB Issue #583: collection.delete() deletes all data with empty ids list](https://github.com/chroma-core/chroma/issues/583)
- [ChromaDB Delete Data Documentation](https://docs.trychroma.com/docs/collections/delete-data)
- [ChromaDB Issue #666: Multi-process concurrent access](https://github.com/chroma-core/chroma/issues/666)

### RAG System Patterns & Best Practices
- [Best Chunking Strategies for RAG in 2025](https://www.firecrawl.dev/blog/best-chunking-strategies-rag-2025)
- [RAG Isn't a Modeling Problem. It's a Data Engineering Problem](https://datalakehousehub.com/blog/2026-01-rag-isnt-the-problem/)
- [Building an Enterprise RAG System in 2026](https://medium.com/@Deep-concept/building-an-enterprise-rag-system-in-2026-the-tools-i-wish-i-had-from-day-one-2ad3c2299275)

### Vector Database Management
- [Versioning vector databases - DataRobot](https://docs.datarobot.com/en/docs/gen-ai/vector-database/vector-versions.html)
- [ChromaDB Single-Node Performance and Limitations](https://docs.trychroma.com/deployment/performance)
- [ChromaDB Metadata Filtering Documentation](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
- [Metadata-Based Filtering in RAG Systems](https://codesignal.com/learn/courses/scaling-up-rag-with-vector-databases/lessons/metadata-based-filtering-in-rag-systems)

### Python Subprocess Management
- [Python Subprocess Documentation](https://docs.python.org/3/library/subprocess.html)
- [Kill Python subprocess and children on timeout](https://alexandra-zaharia.github.io/posts/kill-subprocess-and-its-children-on-timeout-python/)
- [How to Safely Kill Python Subprocesses Without Zombies](https://dev.to/generatecodedev/how-to-safely-kill-python-subprocesses-without-zombies-3h9g)

### File Pattern Matching
- [Python glob documentation](https://docs.python.org/3/library/glob.html)
- [File Searching in Python: Avoiding glob Gotchas](https://runebook.dev/en/docs/python/library/glob)
- [Glob Patterns Guide](https://www.devzery.com/post/your-comprehensive-guide-to-glob-patterns)

---

*Pitfalls research for: v7.0 Index Management & Content Pipeline*
*Researched: 2026-02-23*
*Confidence: HIGH — All critical pitfalls verified with official documentation or known issues*
