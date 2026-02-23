# Architecture Patterns

**Domain:** Index folder management, file type filtering, chunk eviction, content injection
**Researched:** 2026-02-23

## Recommended Architecture

The v7.0 features follow existing Agent Brain patterns, extending rather than replacing current architecture. All features layer onto existing indexing pipeline and storage abstraction.

### High-Level Components

```
┌────────────────────────────────────────────────────────────────┐
│                        CLI Layer                                │
│  agent-brain folders list | remove | add                        │
│  agent-brain index --include-type python,docs                   │
│  agent-brain inject --script enrich.py /path                    │
└─────────────────────┬──────────────────────────────────────────┘
                      │
┌─────────────────────┴──────────────────────────────────────────┐
│                    API / Services Layer                          │
│  ┌──────────────────────┐    ┌────────────────────┐            │
│  │  IndexingService     │    │  FolderManager     │            │
│  │  (existing)          │    │  (NEW)             │            │
│  │  - Index folders     │    │  - Persist folders │            │
│  │  - Generate embeddings│   │  - Remove chunks   │            │
│  └──────────┬───────────┘    └──────────┬─────────┘            │
└─────────────┴──────────────────────────┴────────────────────────┘
              │                           │
┌─────────────┴───────────────────────────┴───────────────────────┐
│                   Storage Layer (Existing)                       │
│  ┌────────────────────┐    ┌──────────────────────┐             │
│  │  StorageBackend    │    │  ManifestStore       │             │
│  │  (Protocol)        │    │  (JSONL files)       │             │
│  │  - ChromaDB        │    │  (Phase 2)           │             │
│  │  - PostgreSQL      │    └──────────────────────┘             │
│  └────────────────────┘                                          │
└──────────────────────────────────────────────────────────────────┘
```

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **FolderManager** | Track indexed folders, persist to disk, bulk chunk removal by folder | IndexingService, StorageBackend |
| **FileTypePresetResolver** | Map preset names → glob patterns | DocumentLoader |
| **ManifestTracker** (Phase 2) | Track file→chunk mapping, detect changes | IndexingService, FolderManager |
| **ContentInjector** | Apply custom metadata to chunks before embedding | IndexingService (in pipeline) |

## Data Flow

### Folder Management Flow

```
CLI: agent-brain folders remove /abs/path
  ↓
FolderManager.remove_folder(folder_path)
  ↓
┌─────────────────────────────────────────┐
│ 1. Load indexed_folders.json            │
│ 2. Find all chunk IDs for folder        │
│    (query ChromaDB where source starts) │
│ 3. Bulk delete chunks by IDs            │
│ 4. Remove folder from list               │
│ 5. Persist updated list                  │
└─────────────────────────────────────────┘
  ↓
Return: {chunks_removed: 142}
```

### File Type Preset Flow

```
CLI: agent-brain index /path --include-type python,docs
  ↓
FileTypePresetResolver.resolve(["python", "docs"])
  ↓
┌─────────────────────────────────────────┐
│ PRESETS = {                              │
│   "python": ["*.py", "*.pyi", "*.pyx"]   │
│   "docs": ["*.md", "*.rst", "*.txt"]     │
│ }                                        │
│ → Returns: ["*.py", "*.pyi", "*.pyx",    │
│              "*.md", "*.rst", "*.txt"]   │
└─────────────────────────────────────────┘
  ↓
DocumentLoader.load_files(
  folder_path,
  include_patterns=resolved_patterns
)
```

### Content Injection Flow (Phase 2)

```
CLI: agent-brain inject --script enrich.py /path
  ↓
IndexingService.start_indexing(
  request,
  injector=load_injector_script("enrich.py")
)
  ↓
DocumentLoader → Chunker → Chunks created
  ↓
For each chunk:
  injector.process_chunk(chunk) → Enriched chunk
  ↓
EmbeddingGenerator → embeddings
  ↓
StorageBackend.upsert_documents(enriched_chunks)
```

## Patterns to Follow

### Pattern 1: Folder Persistence (JSONL)

**What:** Indexed folders list stored as newline-delimited JSON
**When:** Every time folder successfully indexed
**Why:** Crash-safe, append-only, easy to debug

```python
# .agent-brain/indexed_folders.jsonl
{"folder_path": "/abs/path/src", "indexed_at": "2026-02-23T12:00:00Z", "chunk_count": 142}
{"folder_path": "/abs/path/docs", "indexed_at": "2026-02-23T12:05:00Z", "chunk_count": 57}

class FolderManager:
    def __init__(self, state_dir: Path):
        self.manifest_path = state_dir / "indexed_folders.jsonl"

    def add_folder(self, folder_path: str, chunk_count: int) -> None:
        """Append folder to manifest."""
        record = {
            "folder_path": str(Path(folder_path).absolute()),
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "chunk_count": chunk_count
        }
        with self.manifest_path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    def list_folders(self) -> list[dict]:
        """Load all indexed folders."""
        if not self.manifest_path.exists():
            return []
        with self.manifest_path.open("r") as f:
            return [json.loads(line) for line in f if line.strip()]
```

**Why JSONL not JSON:** Append-safe (no need to read entire file to add entry), line-by-line processing for large lists, crash recovery (partial writes don't corrupt file).

### Pattern 2: Bulk Chunk Deletion by Folder

**What:** Remove all chunks where `source` field starts with folder path
**When:** User removes indexed folder
**Why:** ChromaDB metadata filters support exact match, need to query first then bulk delete

```python
async def remove_folder_chunks(
    self,
    folder_path: str,
    backend: StorageBackendProtocol
) -> int:
    """Remove all chunks from a folder."""
    abs_path = str(Path(folder_path).absolute())

    # ChromaDB: Query by metadata, then bulk delete
    if backend.backend_type == "chroma":
        collection = backend.vector_store.get_collection()
        # Get all chunks for this folder
        results = collection.get(
            where={"$or": [
                {"file_path": {"$starts_with": abs_path}},
                {"source": {"$starts_with": abs_path}}
            ]}
        )
        if results["ids"]:
            collection.delete(ids=results["ids"])
            return len(results["ids"])

    # PostgreSQL: Direct delete by metadata
    elif backend.backend_type == "postgres":
        async with backend.conn_manager.get_session() as session:
            result = await session.execute(
                text("""
                    DELETE FROM documents
                    WHERE metadata->>'file_path' LIKE :pattern
                       OR metadata->>'source' LIKE :pattern
                """),
                {"pattern": f"{abs_path}%"}
            )
            return result.rowcount

    return 0
```

**Limitation:** ChromaDB doesn't support `$starts_with` operator. Workaround: Query all chunks, filter in Python by path prefix, bulk delete by IDs.

### Pattern 3: File Type Preset Resolution

**What:** Predefined extension sets for common use cases
**When:** User specifies `--include-type` instead of `--include`
**Why:** User-friendly, reduces CLI verbosity, reuses existing DocumentLoader patterns

```python
# config/file_type_presets.py
from agent_brain_server.indexing.document_loader import DocumentLoader

FILE_TYPE_PRESETS = {
    "python": ["*.py", "*.pyi", "*.pyx", "*.pyw"],
    "javascript": ["*.js", "*.jsx", "*.mjs", "*.cjs"],
    "typescript": ["*.ts", "*.tsx", "*.d.ts"],
    "web": ["*.html", "*.css", "*.js", "*.jsx", "*.vue"],
    "docs": ["*.md", "*.mdx", "*.rst", "*.txt"],
    "code": DocumentLoader.CODE_EXTENSIONS,  # All code types
    "all": DocumentLoader.SUPPORTED_EXTENSIONS,  # Everything
}

class FileTypePresetResolver:
    @staticmethod
    def resolve(presets: list[str]) -> list[str]:
        """Convert preset names to glob patterns."""
        patterns = []
        for preset in presets:
            if preset in FILE_TYPE_PRESETS:
                patterns.extend(FILE_TYPE_PRESETS[preset])
            else:
                # Treat as literal glob pattern
                patterns.append(preset)
        return patterns
```

**Integration:** Resolve presets in CLI layer before passing to API. API receives expanded glob patterns (existing IndexRequest schema unchanged).

### Pattern 4: Content Injector Protocol (Phase 2)

**What:** Optional callable that transforms chunks before embedding
**When:** User wants custom metadata (team, project, sensitivity)
**Why:** Flexible, testable, doesn't require indexing service changes

```python
# User-provided enrich.py
def process_chunk(chunk: dict) -> dict:
    """Enrich chunk with custom metadata."""
    # Example: Tag by folder
    if "/internal/" in chunk["source"]:
        chunk["metadata"]["sensitivity"] = "internal"
    if "/api/" in chunk["source"]:
        chunk["metadata"]["team"] = "backend"
    return chunk

# IndexingService integration
class IndexingService:
    async def _run_indexing_pipeline(
        self,
        request: IndexRequest,
        job_id: str,
        injector: Callable[[dict], dict] | None = None
    ) -> None:
        # ... existing chunking code ...

        # Apply injector before embedding
        if injector:
            for chunk in chunks:
                enriched = injector(chunk.to_dict())
                # Merge metadata back
                chunk.metadata.extra.update(enriched.get("metadata", {}))

        # ... existing embedding code ...
```

**Alternative:** Folder-level metadata JSON file (simpler for static metadata):

```python
# /path/.agent-brain.json
{
  "folder_metadata": {
    "team": "backend",
    "project": "api-service",
    "sensitivity": "internal"
  }
}

# IndexingService reads this and merges into all chunks
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Regex for Folder Path Matching

**What:** Use regex to match folder paths in metadata queries
**Why bad:** ChromaDB doesn't support regex in `where` filters, PostgreSQL JSONB regex slow
**Instead:** Normalize to absolute paths, use exact prefix matching or `$in` with path list

### Anti-Pattern 2: In-Memory Folder List

**What:** Track indexed folders only in `_indexed_folders` set
**Why bad:** Lost on restart, no history, can't audit
**Instead:** JSONL file persisted to disk, load on startup

### Anti-Pattern 3: Per-Chunk Deletion

**What:** Delete chunks one-by-one in a loop
**Why bad:** 1000 chunks = 1000 delete calls, slow, connection pool exhaustion
**Instead:** Bulk delete by IDs list (ChromaDB `delete(ids=[...])`, PostgreSQL `DELETE WHERE id = ANY(:ids)`)

### Anti-Pattern 4: Custom Metadata Extraction from Scratch

**What:** Write LLM prompts manually for chunk enrichment
**Why bad:** LlamaIndex extractors already optimized, battle-tested
**Instead:** Use LlamaIndex `SummaryExtractor`, `TitleExtractor`, `QuestionsAnsweredExtractor`

## Scalability Considerations

| Concern | At 10 folders | At 100 folders | At 1,000 folders |
|---------|---------------|----------------|------------------|
| **Folder list storage** | JSONL fine | JSONL fine | JSONL starts to slow (100KB+), consider SQLite |
| **Bulk chunk deletion** | Fast (<1s) | Medium (1-5s) | Slow (5-30s), needs batching |
| **Manifest file count** | Negligible | Manageable | 1,000 files in dir, consider subdirectories |
| **Path normalization** | No issue | No issue | Symlink resolution slow, cache normalized paths |

## Sources

**Folder Management:**
- [RLAMA RAG Pipeline with Directory Watching](https://rlama.dev/blog/directory-watching) — Folder exclusion patterns
- [Building a Production-Ready RAG System with Incremental Indexing](https://dev.to/guptaaayush8/building-a-production-ready-rag-system-with-incremental-indexing-4bme) — Manifest-based change detection
- [LangChain: Delete vectors by source](https://github.com/langchain-ai/langchain/discussions/19903) — Bulk deletion patterns

**File Type Filtering:**
- [ripgrep User Guide](https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md) — File type preset patterns
- [VS Code Document Selectors](https://code.visualstudio.com/api/references/document-selector) — Language-based filtering

**ChromaDB Metadata Queries:**
- [ChromaDB: Delete Data](https://docs.trychroma.com/docs/collections/delete-data) — `where` filter syntax, bulk delete
- [LlamaIndex: Document Management](https://docs.llamaindex.ai/en/stable/module_guides/indexing/document_management/) — Metadata filtering patterns
