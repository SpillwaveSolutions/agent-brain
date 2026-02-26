# Architecture Integration: v7.0 Index Management & Content Pipeline

**Domain:** RAG System Index Management
**Researched:** 2026-02-23
**Confidence:** HIGH (based on existing codebase analysis)

## Executive Summary

v7.0 introduces four major features that integrate cleanly with the existing Agent Brain architecture:

1. **Folder Management** - Track indexed folders persistently (not in-memory)
2. **Smart Include Filtering** - File type presets for targeted indexing
3. **Chunk Eviction & Live Reindex** - Remove stale chunks when files shrink/delete/rename
4. **Content Injector CLI** - Optional LLM enrichment stage in indexing pipeline

The existing architecture provides all necessary integration points:
- **JobQueueService** handles job enqueueing with pattern filtering
- **IndexingService._run_indexing_pipeline** has clear stage insertion points
- **StorageBackendProtocol** supports metadata queries for chunk tracking
- **DocumentLoader** already accepts include/exclude patterns

**Key architectural insight:** These features are additive, not disruptive. They extend existing components rather than requiring rewrites.

## Recommended Architecture

### Overall Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                          │
│  POST /index/folders/{action}   GET /index/folders                  │
│  POST /index (with include_patterns)                                 │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        JobQueueService                               │
│  • Validate path                                                     │
│  • Enqueue job with patterns & folder tracking                       │
│  • Return 202 with job_id                                            │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        JobWorker (async loop)                        │
│  • Dequeue next PENDING job                                          │
│  • Pass to IndexingService                                           │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  IndexingService._run_indexing_pipeline (MODIFIED)                   │
│                                                                       │
│  1. Load documents (DocumentLoader + patterns from job)              │
│  2. Chunk documents → compute new chunk IDs                          │
│  3. [NEW] ContentInjector.process_chunks (if enabled)                │
│  4. [NEW] Eviction: delete stale chunks for each file                │
│  5. Generate embeddings                                              │
│  6. Upsert to StorageBackend                                         │
│  7. Build BM25 index                                                 │
│  8. [NEW] Update FolderManifest (persist indexed paths)              │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│              StorageBackendProtocol (Chroma/Postgres)                │
│  • get_chunks_by_source(path) → list[chunk_id]                       │
│  • delete_chunks(ids)                                                │
│  • upsert_documents(ids, embeddings, docs, metadata)                 │
└──────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│               FolderManifest (NEW persistent JSON)                   │
│  • Store: {folder_path: {indexed_at, file_count, chunk_count}}      │
│  • Persist: ~/.agent-brain/state/folder_manifest.json               │
│  • API: add_folder, remove_folder, list_folders, get_metadata       │
└──────────────────────────────────────────────────────────────────────┘
```

## Integration Points by Feature

### 1. Folder Management

#### New Components

**FolderManifest** (new file: `agent_brain_server/indexing/folder_manifest.py`)
- **Purpose:** Persistent tracking of indexed folders
- **Storage:** JSON file at `{state_dir}/folder_manifest.json`
- **Schema:**
  ```python
  {
    "folders": {
      "/absolute/path/to/folder": {
        "indexed_at": "2026-02-23T10:00:00Z",
        "file_count": 127,
        "chunk_count": 1543,
        "include_code": true,
        "include_patterns": ["*.py", "*.ts"],
        "exclude_patterns": ["**/node_modules/**"]
      }
    }
  }
  ```
- **API:**
  ```python
  class FolderManifest:
      async def add_folder(self, path: str, metadata: FolderMetadata) -> None
      async def remove_folder(self, path: str) -> None
      async def list_folders(self) -> list[FolderEntry]
      async def get_metadata(self, path: str) -> FolderMetadata | None
      async def save(self) -> None  # Persist to disk
      async def load(self) -> None  # Load from disk
  ```

#### Modified Components

**IndexingService** (`agent_brain_server/services/indexing_service.py`)
- **Current state:** `self._indexed_folders: set[str]` (in-memory, lost on restart)
- **Change:** Remove `_indexed_folders`, add `self.folder_manifest: FolderManifest`
- **Integration point:** After successful indexing (line ~503), call:
  ```python
  await self.folder_manifest.add_folder(
      abs_folder_path,
      FolderMetadata(
          indexed_at=datetime.now(timezone.utc),
          file_count=len(documents),
          chunk_count=len(chunks),
          include_code=request.include_code,
          include_patterns=request.include_patterns,
          exclude_patterns=request.exclude_patterns,
      )
  )
  ```
- **Startup:** Initialize manifest in `__init__`:
  ```python
  self.folder_manifest = FolderManifest(state_dir=settings.DOC_SERVE_STATE_DIR)
  await self.folder_manifest.load()
  ```

**API Router** (new file: `agent_brain_server/api/routers/folders.py`)
- **Endpoints:**
  - `GET /index/folders` → list all indexed folders
  - `POST /index/folders/add` → manually add folder to manifest
  - `DELETE /index/folders/remove?path=...` → remove folder from manifest (doesn't delete chunks)
  - `DELETE /index/folders/purge?path=...` → remove folder + delete all its chunks

#### Data Flow
1. User calls `POST /index` with folder path
2. JobQueueService enqueues job
3. JobWorker executes → IndexingService indexes docs
4. **After successful indexing:** IndexingService updates FolderManifest
5. User calls `GET /index/folders` → retrieves persisted folder list

### 2. Smart Include Filtering

#### New Components

**FileTypePresets** (new file: `agent_brain_server/indexing/file_type_presets.py`)
- **Purpose:** Predefined pattern sets for common use cases
- **Schema:**
  ```python
  PRESETS = {
      "docs": {
          "include": ["*.md", "*.txt", "*.rst", "*.pdf"],
          "exclude": []
      },
      "python": {
          "include": ["*.py", "*.pyi"],
          "exclude": ["**/__pycache__/**", "**/venv/**"]
      },
      "typescript": {
          "include": ["*.ts", "*.tsx"],
          "exclude": ["**/node_modules/**", "**/dist/**"]
      },
      "web": {
          "include": ["*.ts", "*.tsx", "*.js", "*.jsx", "*.html", "*.css"],
          "exclude": ["**/node_modules/**", "**/dist/**", "**/build/**"]
      },
      "all-code": {
          "include": DocumentLoader.CODE_EXTENSIONS,  # All supported code types
          "exclude": DocumentLoader.DEFAULT_EXCLUDE_PATTERNS
      }
  }

  def get_preset(name: str) -> tuple[list[str], list[str]]:
      """Returns (include_patterns, exclude_patterns)"""
  ```

#### Modified Components

**IndexRequest** (`agent_brain_server/models/__init__.py`)
- **Current fields:** `include_patterns`, `exclude_patterns` already exist
- **Add:** `file_type_preset: str | None = None` (optional)
- **Validation:** If `file_type_preset` provided, merge preset patterns with explicit patterns:
  ```python
  def get_effective_patterns(self) -> tuple[list[str], list[str]]:
      if self.file_type_preset:
          preset_include, preset_exclude = get_preset(self.file_type_preset)
          include = list(set(preset_include + (self.include_patterns or [])))
          exclude = list(set(preset_exclude + (self.exclude_patterns or [])))
          return include, exclude
      return self.include_patterns or [], self.exclude_patterns or []
  ```

**DocumentLoader** (`agent_brain_server/indexing/document_loader.py`)
- **Current:** Already accepts `exclude_patterns` (line ~309-327)
- **Add:** Accept `include_patterns` parameter to `load_files()`:
  ```python
  async def load_files(
      self,
      folder_path: str,
      recursive: bool = True,
      include_code: bool = False,
      include_patterns: list[str] | None = None,  # NEW
      exclude_patterns: list[str] | None = None,  # NEW
  ) -> list[LoadedDocument]:
  ```
- **Filter logic:** Pass patterns to `SimpleDirectoryReader`:
  ```python
  reader = SimpleDirectoryReader(
      input_dir=str(path),
      recursive=recursive,
      required_exts=effective_extensions,  # From include_code
      file_extractor={...},  # Pattern-based filtering
      exclude=exclude_patterns or self.DEFAULT_EXCLUDE_PATTERNS,
  )
  ```

**JobQueueService** (`agent_brain_server/job_queue/job_service.py`)
- **Current:** Stores `include_patterns` and `exclude_patterns` in JobRecord (line ~66-70)
- **Change:** Resolve `file_type_preset` to patterns before creating JobRecord:
  ```python
  async def enqueue_job(self, request: IndexRequest, ...) -> JobEnqueueResponse:
      # Resolve patterns from preset if provided
      include_patterns, exclude_patterns = request.get_effective_patterns()

      # Create JobRecord with resolved patterns
      job = JobRecord(
          include_patterns=include_patterns,
          exclude_patterns=exclude_patterns,
          ...
      )
  ```

#### Data Flow
1. User sends `POST /index {"folder_path": "/code", "file_type_preset": "python"}`
2. IndexRequest validates and merges preset patterns
3. JobQueueService stores resolved patterns in JobRecord
4. JobWorker passes patterns to DocumentLoader via IndexingService
5. SimpleDirectoryReader filters files by patterns before loading

### 3. Chunk Eviction & Live Reindex

#### New Components

**ChunkManifest** (new file: `agent_brain_server/indexing/chunk_manifest.py`)
- **Purpose:** Track file-to-chunk mappings for eviction
- **Storage:** JSON file at `{state_dir}/chunk_manifest.jsonl` (line-delimited for append-only writes)
- **Schema per line:**
  ```json
  {"file_path": "/abs/path.py", "chunk_ids": ["chunk_abc123", "chunk_def456"], "indexed_at": "2026-02-23T10:00:00Z"}
  ```
- **API:**
  ```python
  class ChunkManifest:
      async def record_file_chunks(self, file_path: str, chunk_ids: list[str]) -> None
      async def get_file_chunks(self, file_path: str) -> list[str] | None
      async def delete_file_record(self, file_path: str) -> None
      async def list_files(self) -> list[str]
  ```

**ChunkEvictionService** (new file: `agent_brain_server/indexing/chunk_eviction.py`)
- **Purpose:** Compute stale chunks and delete them
- **API:**
  ```python
  class ChunkEvictionService:
      def __init__(
          self,
          storage_backend: StorageBackendProtocol,
          chunk_manifest: ChunkManifest,
      ):
          ...

      async def evict_stale_chunks(
          self,
          file_path: str,
          new_chunk_ids: list[str],
      ) -> int:
          """Delete chunks that no longer exist for this file.

          Returns number of chunks deleted.
          """
          # Get old chunk IDs from manifest
          old_chunk_ids = await self.chunk_manifest.get_file_chunks(file_path)
          if not old_chunk_ids:
              return 0  # No previous chunks

          # Compute stale IDs (old - new)
          stale_ids = set(old_chunk_ids) - set(new_chunk_ids)

          if stale_ids:
              # Delete from storage backend
              await self.storage_backend.delete_chunks(list(stale_ids))
              logger.info(f"Evicted {len(stale_ids)} stale chunks from {file_path}")

          # Update manifest
          await self.chunk_manifest.record_file_chunks(file_path, new_chunk_ids)

          return len(stale_ids)
  ```

#### Modified Components

**StorageBackendProtocol** (`agent_brain_server/storage/protocol.py`)
- **Add new method:**
  ```python
  async def delete_chunks(self, chunk_ids: list[str]) -> int:
      """Delete chunks by IDs.

      Args:
          chunk_ids: List of chunk IDs to delete.

      Returns:
          Number of chunks deleted.

      Raises:
          ValueError: If chunk_ids is empty (safety guard).
          StorageError: If delete operation fails.
      """
  ```
- **Implementation in ChromaBackend:**
  ```python
  async def delete_chunks(self, chunk_ids: list[str]) -> int:
      if not chunk_ids:
          raise ValueError("Cannot delete empty chunk list (safety guard)")

      async with self.vector_store._lock:
          self.vector_store._collection.delete(ids=chunk_ids)

      logger.info(f"Deleted {len(chunk_ids)} chunks from ChromaDB")
      return len(chunk_ids)
  ```

**IndexingService._run_indexing_pipeline** (line ~214-519)
- **Add eviction stage after chunking (line ~420 after chunks created):**
  ```python
  # Step 2.5: Evict stale chunks (if feature enabled)
  if settings.ENABLE_CHUNK_EVICTION:
      eviction_service = ChunkEvictionService(
          storage_backend=self.storage_backend,
          chunk_manifest=self.chunk_manifest,
      )

      # Group chunks by source file
      chunks_by_file: dict[str, list[str]] = {}
      for chunk in chunks:
          source = chunk.metadata.get("source", "")
          if source not in chunks_by_file:
              chunks_by_file[source] = []
          chunks_by_file[source].append(chunk.chunk_id)

      # Evict stale chunks per file
      total_evicted = 0
      for file_path, new_chunk_ids in chunks_by_file.items():
          evicted = await eviction_service.evict_stale_chunks(file_path, new_chunk_ids)
          total_evicted += evicted

      logger.info(f"Evicted {total_evicted} stale chunks across {len(chunks_by_file)} files")
  ```

**Settings** (`agent_brain_server/config/settings.py`)
- **Add:**
  ```python
  ENABLE_CHUNK_EVICTION: bool = Field(
      default=False,
      description="Enable chunk eviction for live reindexing",
  )
  ```

#### Data Flow (Reindex Scenario)
1. File `app.py` previously indexed → 10 chunks (manifest records this)
2. User modifies `app.py` → now generates 7 chunks
3. User calls `POST /index` with `app.py`'s folder
4. IndexingService chunks → generates 7 new chunk IDs
5. **Eviction stage:** ChunkEvictionService queries manifest → finds 10 old IDs
6. Compute stale: 10 old - 7 new = 3 stale IDs
7. Delete stale IDs from ChromaDB via `storage_backend.delete_chunks()`
8. Upsert 7 new chunks (upsert updates if ID exists, inserts if new)
9. Update manifest with 7 new IDs

### 4. Content Injector CLI

#### New Components

**CLIProvider** (new file: `agent_brain_server/providers/cli/base.py`)
- **Purpose:** Safe subprocess wrapper for CLI tools
- **API:**
  ```python
  class CLIProvider:
      def __init__(
          self,
          command: list[str],
          timeout_seconds: int = 30,
          max_output_chars: int = 4096,
      ):
          ...

      async def invoke(self, prompt: str) -> str:
          """Run CLI command with prompt, return stdout.

          Raises:
              TimeoutError: If command exceeds timeout.
              ProviderUnavailable: If binary not found.
          """
  ```

**ConcreteProviders** (new files):
- `agent_brain_server/providers/cli/claude_cli.py` → wraps `claude --prompt`
- `agent_brain_server/providers/cli/opencode_cli.py` → wraps `opencode --prompt`
- `agent_brain_server/providers/cli/gemini_cli.py` → wraps `gemini --prompt`

**ContentInjector** (new file: `agent_brain_server/indexing/content_injector.py`)
- **Purpose:** Enrich chunks with LLM-generated metadata
- **API:**
  ```python
  class ContentInjector:
      def __init__(
          self,
          provider: CLIProvider,
          max_concurrency: int = 4,
          fail_open: bool = True,
      ):
          ...

      async def process_chunks(
          self,
          chunks: list[TextChunk | CodeChunk],
      ) -> list[TextChunk | CodeChunk]:
          """Process chunks with LLM enrichment.

          For each chunk:
          1. Generate prompt: "Summarize in 3 bullets: {chunk.text}"
          2. Call provider.invoke(prompt)
          3. Store result in chunk.metadata["bullet_summary"]
          4. On error: log warning, keep original chunk

          Returns enriched chunks (never raises if fail_open=True).
          """
  ```

#### Modified Components

**IndexingService._run_indexing_pipeline** (line ~420 after chunking)
- **Add injection stage:**
  ```python
  # Step 2.5: Content injection (if enabled)
  if settings.ENABLE_CONTENT_INJECTION or request.enable_content_injection:
      try:
          provider = get_cli_provider(settings.CLI_PROVIDER)
          injector = ContentInjector(
              provider=provider,
              max_concurrency=settings.MAX_CLI_CONCURRENCY,
              fail_open=True,
          )
          chunks = await injector.process_chunks(chunks)
          logger.info(f"Content injection processed {len(chunks)} chunks")
      except ProviderUnavailable as e:
          logger.warning(f"Content injection unavailable: {e}. Continuing without enrichment.")
  ```

**IndexRequest** (`agent_brain_server/models/__init__.py`)
- **Add field:**
  ```python
  enable_content_injection: bool = Field(
      default=False,
      description="Enable LLM-based content enrichment",
  )
  ```

**Settings** (`agent_brain_server/config/settings.py`)
- **Add:**
  ```python
  ENABLE_CONTENT_INJECTION: bool = Field(default=False)
  CLI_PROVIDER: str = Field(default="claude", description="claude|opencode|gemini")
  CLI_TIMEOUT_SECONDS: int = Field(default=30)
  MAX_CLI_CONCURRENCY: int = Field(default=4)
  CLI_MAX_OUTPUT_CHARS: int = Field(default=4096)
  ```

**JobRecord** (`agent_brain_server/models/job.py`)
- **Add fields for observability:**
  ```python
  # Content injection stats
  injector_attempted: int = Field(default=0, ge=0)
  injector_success: int = Field(default=0, ge=0)
  injector_failed: int = Field(default=0, ge=0)
  injector_skipped: int = Field(default=0, ge=0)
  ```

#### Data Flow
1. User sends `POST /index {"folder_path": "/docs", "enable_content_injection": true}`
2. JobQueueService enqueues job with flag
3. JobWorker executes → IndexingService chunks docs
4. **Injection stage:** ContentInjector processes each chunk:
   - Prompt: "Summarize this chunk in 3 bullets: {text}"
   - CLI call: `claude --prompt "..."`
   - Parse output → store in `chunk.metadata["bullet_summary"]`
5. Continue to embedding + storage (metadata preserved)
6. Query time: chunks return with enriched metadata

## Component Boundaries

| Component | Responsibility | Depends On | Used By |
|-----------|---------------|------------|---------|
| **FolderManifest** | Track indexed folders | File system | IndexingService, FoldersRouter |
| **FileTypePresets** | Provide pattern presets | None | IndexRequest, API docs |
| **ChunkManifest** | Track file→chunk mapping | File system | ChunkEvictionService |
| **ChunkEvictionService** | Delete stale chunks | StorageBackend, ChunkManifest | IndexingService |
| **CLIProvider** | Safe subprocess wrapper | subprocess, asyncio | ContentInjector |
| **ContentInjector** | Enrich chunks with LLM | CLIProvider | IndexingService |
| **StorageBackendProtocol** | Vector/keyword storage | ChromaDB/Postgres | IndexingService, ChunkEvictionService |
| **IndexingService** | Orchestrate pipeline | All above | JobWorker |
| **JobQueueService** | Enqueue jobs | JobStore | API routers |

## Data Flow Changes

### Before v7.0 (Current)
```
POST /index
  → JobQueue.enqueue(request)
  → JobWorker.process_job()
  → IndexingService.start_indexing()
     1. Load documents (DocumentLoader)
     2. Chunk documents (ContextAwareChunker, CodeChunker)
     3. Generate embeddings (EmbeddingGenerator)
     4. Upsert to storage (StorageBackend.upsert_documents)
     5. Build BM25 index (BM25IndexManager.build_index)
  → Update in-memory _indexed_folders set (lost on restart)
```

### After v7.0
```
POST /index {"file_type_preset": "python", "enable_content_injection": true}
  → IndexRequest.get_effective_patterns() [NEW: resolve preset]
  → JobQueue.enqueue(request with resolved patterns)
  → JobWorker.process_job()
  → IndexingService.start_indexing()
     1. Load documents (DocumentLoader + patterns) [MODIFIED: accept include_patterns]
     2. Chunk documents
     3. [NEW] ContentInjector.process_chunks() (if enabled)
     4. [NEW] ChunkEvictionService.evict_stale_chunks() (per file, if enabled)
     5. Generate embeddings
     6. Upsert to storage (StorageBackend.upsert_documents)
     7. Build BM25 index
     8. [NEW] FolderManifest.add_folder() (persist to disk)
  → [NEW] ChunkManifest updated per file
```

## Scalability Considerations

| Concern | At 100 files | At 10K files | At 1M files |
|---------|--------------|--------------|-------------|
| **FolderManifest size** | <1KB JSON | ~50KB JSON | ~5MB JSON (load at startup, in-memory cache) |
| **ChunkManifest size** | <10KB JSONL | ~1MB JSONL | ~100MB JSONL (stream reads, indexed by file path) |
| **Eviction performance** | <100ms per file | 1-2s per batch (100 files) | Use manifest rebuild + bulk delete (vacuum command) |
| **Content injection** | 10-30s for batch | 5-10 min (with concurrency=4) | Queue batching required (Phase 8+) |

**Mitigation strategies:**
- ChunkManifest: Use SQLite for >100K files (Phase 8)
- Eviction: Batch deletes by folder (delete where source LIKE 'folder/%')
- Content injection: Make optional, provide CLI flag to disable

## Patterns to Follow

### Pattern 1: Fail-Open for Optional Features
**What:** New features (eviction, injection) must not break indexing if unavailable.
**When:** Any feature behind a feature flag or external dependency.
**Example:**
```python
try:
    if settings.ENABLE_CONTENT_INJECTION:
        chunks = await content_injector.process_chunks(chunks)
except ProviderUnavailable as e:
    logger.warning(f"Content injection unavailable: {e}. Continuing.")
    # Continue without enrichment
```

### Pattern 2: Async Wrapping for Sync Components
**What:** Existing sync components (BM25IndexManager, file I/O) must not block event loop.
**When:** Calling sync code from async context.
**Example:**
```python
# Sync manifest save
await asyncio.to_thread(self.folder_manifest.save)

# Sync BM25 rebuild
await asyncio.to_thread(self.bm25_manager.build_index, nodes)
```

### Pattern 3: Job Queue as Single Entry Point
**What:** All indexing operations flow through JobQueueService → JobWorker → IndexingService.
**When:** Any new indexing-related endpoint.
**Example:**
```python
# DON'T: Call IndexingService directly from router
await indexing_service.start_indexing(request)

# DO: Enqueue job, return 202
response = await job_queue_service.enqueue_job(request)
return JSONResponse(status_code=202, content=response.dict())
```

### Pattern 4: Metadata-Only Enrichment
**What:** Content injection adds metadata, never mutates chunk.text.
**When:** Processing chunks with external tools.
**Example:**
```python
# Store summary in metadata, don't replace text
chunk.metadata["bullet_summary"] = summary
chunk.metadata["injector_used"] = "claude-cli"
# chunk.text remains unchanged
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: In-Memory State for Persistence
**What:** Using instance variables (`_indexed_folders`) for data that must survive restarts.
**Why bad:** Lost on server restart, not shared across instances.
**Instead:** Use FolderManifest with file-backed persistence.

### Anti-Pattern 2: Blocking I/O in Async Context
**What:** Calling `open()`, `json.dump()`, `subprocess.run()` directly in async functions.
**Why bad:** Blocks event loop, degrades concurrency.
**Instead:** Wrap in `asyncio.to_thread()`.

### Anti-Pattern 3: Empty List Deletes
**What:** Calling `collection.delete(ids=[])` without checking.
**Why bad:** Some ChromaDB versions delete entire collection.
**Instead:** Always guard:
```python
if not chunk_ids:
    raise ValueError("Cannot delete empty chunk list")
```

### Anti-Pattern 4: Tight Coupling to CLI Tools
**What:** Hardcoding CLI commands in IndexingService.
**Why bad:** Makes testing hard, reduces flexibility.
**Instead:** Use CLIProvider abstraction with dependency injection.

## Build Order (Dependency-Aware)

### Phase 1: Foundation (No Dependencies)
1. **FolderManifest** - Standalone file persistence
2. **FileTypePresets** - Pure data structure
3. **ChunkManifest** - Standalone file persistence

### Phase 2: Storage Extensions (Depends on Protocol)
4. **StorageBackendProtocol.delete_chunks()** - New method in protocol
5. **ChromaBackend.delete_chunks()** - Implementation

### Phase 3: Services (Depends on Phase 1 + 2)
6. **ChunkEvictionService** - Uses ChunkManifest + StorageBackend
7. **CLIProvider** - Standalone subprocess wrapper
8. **ContentInjector** - Uses CLIProvider

### Phase 4: Integration (Depends on Phase 3)
9. **IndexRequest.get_effective_patterns()** - Uses FileTypePresets
10. **DocumentLoader.load_files()** - Accept include_patterns param
11. **IndexingService pipeline modifications** - Integrate all services

### Phase 5: API Surface (Depends on Phase 4)
12. **FoldersRouter** - New endpoints for folder management
13. **IndexRequest fields** - Add `file_type_preset`, `enable_content_injection`
14. **JobRecord fields** - Add injection stats

## Testing Strategy

### Unit Tests
- **FolderManifest:** CRUD operations, file I/O
- **ChunkManifest:** CRUD operations, JSONL parsing
- **ChunkEvictionService:** Compute stale IDs, mock storage backend
- **CLIProvider:** Timeout handling, binary detection, output limits
- **ContentInjector:** Batch processing, fail-open behavior, metadata attachment
- **FileTypePresets:** Pattern resolution, preset merging

### Integration Tests
- **Eviction workflow:** Index file → modify → reindex → verify old chunks deleted
- **Content injection:** Index with injection enabled → verify metadata populated
- **Folder management:** Index → list folders → remove → verify manifest updated
- **Pattern filtering:** Index with preset → verify only matching files loaded

### End-to-End Tests
- **Full pipeline:** Load → chunk → inject → evict → embed → store → query
- **Feature flags:** Verify features work independently and together
- **Restart resilience:** Index → restart server → verify manifest persisted

## Migration Path

### Existing Deployments
1. **No breaking changes:** All features behind feature flags (default OFF)
2. **Manifest bootstrap:** On first run with `ENABLE_CHUNK_EVICTION=true`, build manifest by querying storage backend:
   ```python
   # Get all chunks
   results = await storage_backend.get_all_chunks()
   # Group by source file
   chunks_by_file = group_by(results, lambda r: r.metadata["source"])
   # Populate manifest
   for file_path, chunks in chunks_by_file.items():
       await chunk_manifest.record_file_chunks(file_path, [c.id for c in chunks])
   ```
3. **CLI command:** Provide `agent-brain vacuum` to rebuild manifests from existing index

### New Deployments
- Manifests created automatically during first indexing
- No special migration needed

## Open Questions

1. **ChunkManifest storage format:** JSONL (simple) vs SQLite (scalable)? → Start with JSONL, migrate to SQLite in Phase 8 if needed.
2. **Eviction granularity:** Per-file (proposed) vs per-folder? → Per-file for precision, batch deletes by folder for performance.
3. **Content injection retry:** Should failed chunks retry? → No, fail-open means skip and continue.
4. **Folder manifest conflicts:** What if same folder indexed with different patterns? → Store multiple entries with different dedupe keys, or merge metadata?

## Success Metrics

- **Folder management:** Folders persist across restarts (verify via `/index/folders` after restart)
- **Pattern filtering:** File count matches expected preset (e.g., `python` preset indexes only `.py` files)
- **Chunk eviction:** Reindexing a modified file removes stale chunks (verify via chunk count decrease)
- **Content injection:** Chunks have `bullet_summary` metadata (verify via query response)
- **Performance:** Indexing time increases <20% with eviction + injection enabled
- **Reliability:** No indexing failures due to new features (fail-open guarantees)

## References

- **Existing codebase:** All file paths verified as of 2026-02-23
- **ChromaDB docs:** https://docs.trychroma.com/usage-guide (delete operations)
- **LlamaIndex docs:** https://docs.llamaindex.ai (SimpleDirectoryReader patterns)
- **Plan documents:**
  - `/Users/richardhightower/clients/spillwave/src/agent-brain/docs/plans/121-chunk-eviction-and-live-reindex.md`
  - `/Users/richardhightower/clients/spillwave/src/agent-brain/docs/plans/120-content-injector-cli.md`

---
*Architecture research for: v7.0 Index Management & Content Pipeline*
*Researched: 2026-02-23*
*Confidence: HIGH (existing codebase analysis + plan documents)*
