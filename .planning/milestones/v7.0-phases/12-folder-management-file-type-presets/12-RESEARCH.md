# Phase 12: Folder Management & File Type Presets - Research

**Researched:** 2026-02-23
**Domain:** Python RAG system folder tracking, file filtering, JSONL persistence
**Confidence:** HIGH

## Summary

Phase 12 adds folder management and file type preset features to Agent Brain. The system currently tracks indexed folders in-memory (`IndexingService._indexed_folders: set[str]`) but loses this data on restart. This phase adds persistent folder tracking via JSONL storage, adds CLI/API endpoints to list and remove folders, and introduces file type presets to simplify indexing operations.

The codebase already has strong foundations: absolute path normalization (`Path.resolve()` in IndexingService line 254), metadata filtering via ChromaDB/PostgreSQL `where` clauses, and Click CLI structure. The main gaps are: persistent folder storage, delete-by-folder operations, and file type preset resolution.

**Primary recommendation:** Use `pathlib.Path.resolve()` for canonicalization (resolves symlinks, makes absolute, normalizes), implement FolderManager with asyncio Locks for JSONL writes, extend StorageBackendProtocol with `delete_by_metadata()` method, and create FileTypePresetResolver as a pure function module.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pathlib | stdlib (3.10+) | Path normalization, canonical resolution | Built-in, cross-platform, resolve() handles symlinks |
| asyncio | stdlib (3.10+) | Async Locks for JSONL writes | Already used throughout codebase |
| Click | ^8.0 | CLI command groups, flags | Already used for agent-brain-cli commands |
| Pydantic | ^2.0 | Data validation for folder/preset models | Already used for IndexRequest/QueryRequest |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aiofiles | ^24.0 | Async file I/O for JSONL | If many concurrent folder operations |
| fcntl | stdlib (Unix) | Advisory file locks | Only if Windows support not needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSONL | SQLite | JSONL: simpler, human-readable. SQLite: better concurrency, transactions |
| pathlib | os.path | pathlib: cleaner API. os.path: more explicit control |
| asyncio.Lock | threading.Lock | asyncio: matches FastAPI. threading: simpler but blocks event loop |

**Installation:**
```bash
# Core dependencies already installed
# Optional async file I/O
poetry add aiofiles  # only if needed for performance
```

## Architecture Patterns

### Recommended Project Structure
```
agent-brain-server/
├── agent_brain_server/
│   ├── services/
│   │   ├── folder_manager.py       # FolderManager service
│   │   └── file_type_presets.py    # Preset resolution
│   ├── storage/
│   │   ├── protocol.py             # Add delete_by_metadata()
│   │   ├── chroma/backend.py       # Implement delete
│   │   └── postgres/backend.py     # Implement delete
│   ├── api/routers/
│   │   └── folders.py              # New router
│   └── models/
│       └── folders.py              # FolderRecord, FolderListResponse

agent-brain-cli/
├── agent_brain_cli/commands/
│   ├── folders.py                  # CLI command group
│   └── types.py                    # List file type presets

agent-brain-plugin/
└── commands/
    ├── agent-brain-folders.md      # Plugin command
    └── agent-brain-types.md        # Plugin command
```

### Pattern 1: FolderManager Service
**What:** Service that persists indexed folder metadata to JSONL and tracks folder→chunk relationships.
**When to use:** When IndexingService completes a job successfully.

**Example:**
```python
# Source: Codebase analysis + best practices
from pathlib import Path
import asyncio
import json
from datetime import datetime, timezone
from dataclasses import dataclass

@dataclass
class FolderRecord:
    folder_path: str  # Canonical absolute path
    chunk_count: int
    last_indexed: datetime
    chunk_ids: list[str] = field(default_factory=list)

class FolderManager:
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.jsonl_path = state_dir / "indexed_folders.jsonl"
        self._lock = asyncio.Lock()
        self._cache: dict[str, FolderRecord] = {}

    async def initialize(self) -> None:
        """Load existing folder records from JSONL."""
        async with self._lock:
            if self.jsonl_path.exists():
                with open(self.jsonl_path) as f:
                    for line in f:
                        record = FolderRecord(**json.loads(line))
                        self._cache[record.folder_path] = record

    async def add_folder(self, folder_path: str, chunk_ids: list[str]) -> None:
        """Add or update folder record."""
        canonical = str(Path(folder_path).resolve())
        record = FolderRecord(
            folder_path=canonical,
            chunk_count=len(chunk_ids),
            last_indexed=datetime.now(timezone.utc),
            chunk_ids=chunk_ids
        )

        async with self._lock:
            self._cache[canonical] = record
            await self._append_to_jsonl(record)

    async def _append_to_jsonl(self, record: FolderRecord) -> None:
        """Atomically append to JSONL (write-temp-rename pattern)."""
        temp_path = self.jsonl_path.with_suffix(".tmp")

        # Rewrite entire file (JSONL doesn't support in-place updates)
        with open(temp_path, "w") as f:
            for r in self._cache.values():
                f.write(json.dumps(r.__dict__) + "\n")

        # Atomic rename
        temp_path.replace(self.jsonl_path)
```

**Source:** [Safe atomic file writes for JSON](https://gist.github.com/therightstuff/cbdcbef4010c20acc70d2175a91a321f), Python asyncio patterns

### Pattern 2: Delete by Metadata Filter
**What:** Extend StorageBackendProtocol with `delete_by_metadata()` to bulk-delete chunks by folder path.
**When to use:** When user removes a folder via `agent-brain folders remove`.

**Example:**
```python
# Source: StorageBackendProtocol + ChromaDB docs
@runtime_checkable
class StorageBackendProtocol(Protocol):
    # Existing methods...

    async def delete_by_metadata(
        self,
        where: dict[str, Any],
    ) -> int:
        """Delete documents matching metadata filter.

        Args:
            where: Metadata filter (backend-specific syntax)

        Returns:
            Number of documents deleted

        Raises:
            StorageError: If delete operation fails
        """
        ...

# ChromaBackend implementation
async def delete_by_metadata(self, where: dict[str, Any]) -> int:
    """Delete chunks by metadata filter (e.g., folder path)."""
    # ChromaDB delete supports where filters
    return await self.vector_store.delete_by_metadata(where)
```

**Source:** [ChromaDB metadata filtering docs](https://docs.trychroma.com/docs/querying-collections/metadata-filtering), existing protocol pattern

### Pattern 3: File Type Preset Resolver
**What:** Pure function module that maps preset names to glob patterns.
**When to use:** Before passing patterns to DocumentLoader.

**Example:**
```python
# Source: Codebase DocumentLoader + best practices
FILE_TYPE_PRESETS: dict[str, list[str]] = {
    "python": ["*.py", "*.pyi", "*.pyw"],
    "javascript": ["*.js", "*.jsx", "*.mjs", "*.cjs"],
    "typescript": ["*.ts", "*.tsx"],
    "go": ["*.go"],
    "rust": ["*.rs"],
    "java": ["*.java"],
    "web": ["*.html", "*.css", "*.scss", "*.jsx", "*.tsx"],
    "docs": ["*.md", "*.txt", "*.rst", "*.pdf"],
    "code": ["*.py", "*.js", "*.ts", "*.go", "*.rs", "*.java", "*.c", "*.cpp", "*.h", "*.cs"],
    "text": ["*.md", "*.txt", "*.rst"],
    "pdf": ["*.pdf"],
}

def resolve_file_types(preset_names: list[str]) -> list[str]:
    """Resolve file type presets to glob patterns.

    Args:
        preset_names: List of preset names (e.g., ["python", "docs"])

    Returns:
        Deduplicated list of glob patterns

    Raises:
        ValueError: If unknown preset name
    """
    patterns = []
    for name in preset_names:
        if name not in FILE_TYPE_PRESETS:
            valid = ", ".join(FILE_TYPE_PRESETS.keys())
            raise ValueError(f"Unknown preset '{name}'. Valid: {valid}")
        patterns.extend(FILE_TYPE_PRESETS[name])
    return list(set(patterns))  # Deduplicate
```

**Source:** DocumentLoader.CODE_EXTENSIONS + Python glob best practices

### Anti-Patterns to Avoid
- **Storing full chunk text in JSONL:** Only store folder_path, chunk_count, chunk_ids — query storage backend for actual data
- **Blocking file I/O in async context:** Use `asyncio.to_thread()` or `aiofiles` for all disk operations
- **Deleting chunks one-by-one:** Use bulk `where` filter on ChromaDB — 10-100x faster for large collections
- **Forgetting path normalization:** Always `Path(user_input).resolve()` before storing or comparing paths

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Path canonicalization | String manipulation for `../`, `./`, symlinks | `pathlib.Path.resolve()` | Handles symlinks, cross-platform, OS-aware |
| Atomic file writes | Manual temp file + rename | `atomicio` (optional) or pattern | Edge cases: permissions, cross-filesystem moves |
| File locking | Custom fcntl wrappers | `asyncio.Lock` (single process) | Simpler, matches FastAPI async model |
| Glob pattern matching | Regex for `*.py`, `**/*.ts` | `pathlib.Path.glob()` or DocumentLoader | Already implemented, handles `**` recursion |
| JSONL parsing | Line-by-line string parsing | `json.loads()` per line | Robust, handles escaped chars |

**Key insight:** pathlib + asyncio.Lock covers 90% of needs. Only add `aiofiles` or `fcntl` if profiling shows bottleneck.

## Common Pitfalls

### Pitfall 1: Not Normalizing Paths Before Comparison
**What goes wrong:** User indexes `/home/user/docs` then `/home/user/../user/docs` — stored as separate folders, duplicates chunks.
**Why it happens:** `IndexingService._indexed_folders` uses raw strings, doesn't canonicalize.
**How to avoid:** Always `str(Path(folder_path).resolve())` before storing or comparing.
**Warning signs:** Same folder appears twice in `folders list`, duplicate chunks in search results.

**Example:**
```python
# BAD
def add_folder(self, folder_path: str):
    self._folders.add(folder_path)  # "/home/user/docs" != "../docs"

# GOOD
def add_folder(self, folder_path: str):
    canonical = str(Path(folder_path).resolve())
    self._folders.add(canonical)  # Always "/home/user/docs"
```

### Pitfall 2: ChromaDB where Filter Performance Degradation
**What goes wrong:** Filtering by `source` metadata on large collections (>100k chunks) adds 3-8x query overhead.
**Why it happens:** ChromaDB HNSW index is for vectors, not metadata — metadata filter is post-processing.
**How to avoid:** Document performance characteristics in CLI help text. For very large indices, suggest using separate collections per project.
**Warning signs:** Query latency increases from 5ms to 30ms+ with metadata filters.

**Research findings:** Per [ChromaDB cookbook](https://cookbook.chromadb.dev/core/filters/), category filtering costs 3.3x overhead (14.82ms vs 4.45ms baseline). Numeric range queries are most expensive (8x overhead, 35.67ms). Metadata filtering is usable but measurably slower.

### Pitfall 3: JSONL Corruption from Concurrent Writes
**What goes wrong:** Two index jobs finish simultaneously, both write to `indexed_folders.jsonl` → file corruption.
**Why it happens:** No write coordination, append operations aren't atomic in Python.
**How to avoid:** Use `asyncio.Lock` around all JSONL writes. Rewrite entire file on each update (JSONL doesn't support in-place edits).
**Warning signs:** JSONL file has invalid JSON lines, server crashes on startup when loading folder state.

**Example:**
```python
# BAD
async def add_folder(self, record):
    with open(self.jsonl_path, "a") as f:  # No lock!
        f.write(json.dumps(record) + "\n")

# GOOD
async def add_folder(self, record):
    async with self._lock:  # Serialize writes
        self._cache[record.folder_path] = record
        # Rewrite entire file atomically
        temp = self.jsonl_path.with_suffix(".tmp")
        with open(temp, "w") as f:
            for r in self._cache.values():
                f.write(json.dumps(r.__dict__) + "\n")
        temp.replace(self.jsonl_path)  # Atomic on POSIX
```

### Pitfall 4: Deleting Folder While Job In Progress
**What goes wrong:** User runs `folders remove /docs` while indexing job for `/docs` is running → partial chunks deleted, job fails.
**Why it happens:** No coordination between JobService and FolderManager.
**How to avoid:** Check `JobService.get_active_jobs()` before allowing folder deletion. Reject with clear error if active job exists for that folder.
**Warning signs:** Indexing jobs fail midway with "chunk not found" errors, folder list shows inconsistent state.

## Code Examples

Verified patterns from codebase and official sources:

### Existing Path Normalization
```python
# Source: agent_brain_server/services/indexing_service.py:254
# Normalize folder path to absolute path to avoid duplicates
abs_folder_path = os.path.abspath(request.folder_path)
logger.info(
    f"Normalizing indexing path: {request.folder_path} -> {abs_folder_path}"
)
```

**Improvement for Phase 12:** Use `Path.resolve()` instead of `os.path.abspath()` to also resolve symlinks.

### Existing In-Memory Folder Tracking
```python
# Source: agent_brain_server/services/indexing_service.py:503
self._indexed_folders.add(abs_folder_path)
```

**Phase 12 change:** Call `FolderManager.add_folder()` instead, which persists to JSONL.

### Existing CLI Command Structure
```python
# Source: agent_brain_cli/commands/index.py
@click.command()
@click.argument("path")
@click.option("--include-code", is_flag=True)
def index_command(path: str, include_code: bool):
    """Index documents from PATH."""
    # Implementation
```

**Phase 12 pattern:** Create similar `folders_group` with `list`, `add`, `remove` subcommands.

### Existing Metadata Schema
```python
# Source: agent_brain_server/indexing/chunking.py:28-30
@dataclass
class ChunkMetadata:
    chunk_id: str
    source: str  # Full file path
    file_name: str
    # ...
```

**Phase 12 usage:** Filter chunks by `source` metadata prefix to find all chunks from a folder.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| os.path.abspath() | pathlib.Path.resolve() | Python 3.4+ | resolve() also canonicalizes symlinks, safer for path comparison |
| Threading locks | asyncio.Lock | FastAPI async era | Matches async/await model, doesn't block event loop |
| Manual temp files | atomicio library | 2024+ | Handles edge cases (permissions, cross-fs) but adds dependency |
| Single JSONL append | Rewrite entire file | Always | JSONL doesn't support in-place updates, rewrite ensures consistency |

**Deprecated/outdated:**
- `os.path.abspath()` for canonical paths: Use `Path.resolve()` to handle symlinks correctly
- Blocking `open()` in async functions: Use `asyncio.to_thread()` or `aiofiles`

## Open Questions

1. **Should JSONL include full chunk_ids list or just count?**
   - What we know: Chunk IDs needed for deletion, but large folders = large lists
   - What's unclear: Memory/disk tradeoff. 10k chunks = ~800KB per folder record
   - Recommendation: Store chunk_ids initially, add `--compact` flag later if needed

2. **How to handle folder moves/renames?**
   - What we know: `resolve()` makes paths absolute, moves look like new folders
   - What's unclear: User expectation — should system auto-detect renames?
   - Recommendation: Treat as separate folders initially, document in user guide

3. **Should file type presets be user-configurable?**
   - What we know: Requirements say predefined presets (FTYPE-01)
   - What's unclear: Future feature request likely
   - Recommendation: Hard-code in Phase 12, design for extension (load from config file in future)

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `agent_brain_server/services/indexing_service.py`, `storage/protocol.py`, `indexing/chunking.py`, `api/routers/index.py`, `agent_brain_cli/commands/`
- Python stdlib docs: [pathlib](https://docs.python.org/3/library/pathlib.html), [asyncio](https://docs.python.org/3/library/asyncio-sync.html)

### Secondary (MEDIUM confidence)
- [ChromaDB Filters - Chroma Cookbook](https://cookbook.chromadb.dev/core/filters/)
- [ChromaDB Metadata Filtering Docs](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)
- [Metadata Filtering Performance Analysis - Dataquest](https://www.dataquest.io/blog/metadata-filtering-and-hybrid-search-for-vector-databases/)
- [Python glob patterns - Python Packaging Guide](https://packaging.python.org/en/latest/specifications/glob-patterns/)
- [Python pathlib Complete Guide 2026 - DevToolbox](https://devtoolbox.dedyn.io/blog/python-pathlib-complete-guide)
- [Safe atomic file writes for JSON - GitHub Gist](https://gist.github.com/therightstuff/cbdcbef4010c20acc70d2175a91a321f)
- [atomicio PyPI package](https://pypi.org/project/atomicio/)
- [aio-libs/aiorwlock - Read/Write Lock for asyncio](https://github.com/aio-libs/aiorwlock)

### Tertiary (LOW confidence)
- N/A

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pathlib, asyncio, Click already used throughout codebase
- Architecture: HIGH - FolderManager pattern matches existing services (IndexingService, QueryService), StorageBackendProtocol well-defined
- Pitfalls: MEDIUM-HIGH - Path normalization documented, ChromaDB filter performance verified, JSONL corruption is common async pattern

**Research date:** 2026-02-23
**Valid until:** 30 days (stable Python stdlib, ChromaDB API stable)
