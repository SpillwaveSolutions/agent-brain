# Feature Landscape

**Domain:** RAG system for local code and documentation indexing
**Researched:** 2026-02-23

## Table Stakes

Features users expect in index management systems. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| List indexed folders | Users need visibility into what's indexed | Low | Already exists in health status, needs CLI command |
| Remove specific folder's chunks | Only way to clean up without full reset | Medium | ChromaDB `delete()` with `where` filter on `source` field |
| Persist indexed folder list | Survives restarts | Low | Already tracked in-memory in `_indexed_folders`, needs file persistence |
| File type presets (common languages) | Users expect shortcuts like "python" not "*.py,*.pyi" | Low | Map presets to glob patterns (ripgrep model: `-tpy`, `-tjs`, `-tgo`) |
| Incremental folder reindex | Re-scan folder without duplicating unchanged files | Medium | Requires manifest tracking (checksums/mtimes) |
| Content type detection | Distinguish doc vs code automatically | Low | Already implemented via `source_type` metadata |

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Chunk eviction by staleness | Remove chunks from deleted/moved files automatically | Medium | Track file→chunk IDs in manifest, detect missing files, bulk delete orphans |
| Content injection during indexing | Enrich chunks with custom metadata (tags, annotations) | Medium | Plugin/hook system: process chunks before embedding |
| Smart file type presets | Presets for ecosystems: `web` (html/css/js), `python-project` (py/toml/md) | Low | Predefined preset definitions, user-customizable |
| Manifest-based change detection | Only reindex changed files (checksum/mtime comparison) | Medium-High | Manifest file per indexed folder, track file_path→checksum→chunk_ids |
| Folder-level metadata injection | Apply metadata to all chunks from a folder (e.g., "internal-docs", "third-party") | Low | Folder config file or CLI flag, merge into chunk metadata |
| Live reindex on folder remove/add | Automatically update index when folder list changes | Medium | Depends on chunk eviction + incremental reindex |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Automatic file watching | Adds complexity (inotify/FSEvents), resource usage, permission issues | Manual reindex via CLI or API (users control timing) |
| Git-aware indexing | Tight coupling to git, breaks for non-git projects | Simple file-based approach, let users exclude `.git/` via patterns |
| Regex-based content injection | Fragile, hard to debug, users write brittle patterns | Provide structured metadata fields + optional CLI script hook |
| Auto-delete old versions | Risk of data loss, unclear "old" definition | Manual chunk eviction with manifest diff, user-controlled |
| Multi-level folder hierarchy tracking | Over-engineering, adds state management complexity | Flat list of indexed folders (normalized to absolute paths) |

## Feature Dependencies

```
Content injection (Phase 1)
  → Requires: Chunk metadata schema (already exists: ChunkMetadata)

File type presets (Phase 1)
  → Requires: Include/exclude pattern system (already exists: IndexRequest)

List/Add/Remove folders (Phase 1)
  → Requires: Persistent indexed folder tracking (needs persistence layer)
  → Requires: ChromaDB `where` filter deletion (already available)

Manifest tracking (Phase 2)
  → Requires: Folder metadata persistence
  → Requires: File checksum/mtime calculation

Chunk eviction (Phase 2)
  → Requires: Manifest tracking (file→chunk mapping)
  → Requires: Bulk delete by chunk IDs (ChromaDB supports this)

Incremental reindex (Phase 2)
  → Requires: Manifest tracking (change detection)
  → Requires: Chunk eviction (remove old chunks before adding new)

Live reindex (Phase 3 — optional)
  → Requires: Chunk eviction (remove old folder chunks)
  → Requires: Incremental reindex (re-add updated chunks)
```

## MVP Recommendation

Prioritize:
1. **List indexed folders** — Visibility into current state (table stakes)
2. **Remove specific folder** — Unblock cleanup without full reset (table stakes)
3. **File type presets** — Dramatically improves UX over manual glob patterns (differentiator)
4. **Content injection CLI** — Enables metadata enrichment use cases (differentiator)

Defer:
- **Manifest tracking + chunk eviction**: Complex, requires persistent manifest store per folder
- **Incremental reindex**: Depends on manifest tracking
- **Live reindex**: Nice-to-have, users can manually reindex after folder changes

## Implementation Patterns from Research

### Indexed Folder Management

**Pattern (RLAMA)**: Exclude directories with `--exclude-dir=node_modules,tmp`, track watched folders.

**Pattern (LangChain RecordManager)**: Track indexed documents, enable cleanup of deleted files, process only changed documents.

**Agent Brain approach**:
- Persist `indexed_folders` list to `.agent-brain/indexed_folders.json`
- Normalize all paths to absolute before storing (avoid duplicates)
- CLI commands: `agent-brain folders list`, `agent-brain folders remove /path`
- API: `DELETE /index/folder` with `{"folder_path": "/abs/path"}`

### File Type Presets

**Pattern (ripgrep)**: Pre-defined types via `--type-list`, e.g., `-tpy` for Python, `-tjs` for JavaScript. Custom types via `--type-add 'web:*.{html,css,js}'`.

**Pattern (VS Code)**: Document selectors by language, file patterns like `**/*.py`.

**Agent Brain approach**:
- Define presets in `config/file_type_presets.py`:
  ```python
  PRESETS = {
      "python": ["*.py", "*.pyi", "*.pyx"],
      "javascript": ["*.js", "*.jsx", "*.mjs"],
      "typescript": ["*.ts", "*.tsx"],
      "web": ["*.html", "*.css", "*.js", "*.jsx"],
      "docs": ["*.md", "*.mdx", "*.rst", "*.txt"],
      # ...
  }
  ```
- CLI: `agent-brain index /path --include-type python,docs`
- API: `POST /index` with `include_types: ["python", "docs"]`
- Expand to glob patterns before passing to DocumentLoader

### Chunk Eviction & Manifest Tracking

**Pattern (CocoIndex)**: Near-real-time incremental indexing, track file changes, reprocess only modified files.

**Pattern (mcp-rag-server)**: Manifest file (`.manifest.json`) with metadata (version, chunk params, model) + list of data files. On startup, load from manifest if metadata matches.

**Pattern (Azure AI Search)**: Delta indexing processes only new/modified data, track changes via checksums or timestamps.

**Agent Brain approach**:
- Manifest per indexed folder: `.agent-brain/manifests/<hash_of_folder_path>.json`
- Manifest schema:
  ```json
  {
    "folder_path": "/abs/path",
    "indexed_at": "2026-02-23T12:00:00Z",
    "file_manifest": {
      "/abs/path/file.py": {
        "checksum": "abc123...",
        "mtime": "2026-02-20T10:00:00Z",
        "chunk_ids": ["chunk_abc123", "chunk_def456"]
      }
    }
  }
  ```
- On reindex: Compare current files to manifest
  - Deleted files → bulk delete chunk IDs via ChromaDB `delete(ids=[...])`
  - Changed files → delete old chunks + reindex file
  - New files → index normally
- Store manifests to disk, load on startup

### Content Injection

**Pattern (Amazon Kendra CDE)**: Create, modify, or delete document attributes during ingestion. Automate via basic operations (inline lambda, S3 script).

**Pattern (LlamaIndex)**: Custom metadata extractors, supplement built-in parsers with domain-specific metadata.

**Pattern (Haystack)**: Automated structured metadata enrichment during preprocessing.

**Agent Brain approach**:
- CLI injector script: `agent-brain inject --script enrich.py /path`
- Script receives chunks before embedding:
  ```python
  # enrich.py
  def process_chunk(chunk: dict) -> dict:
      # Add custom metadata
      chunk["metadata"]["team"] = "backend"
      chunk["metadata"]["sensitivity"] = "internal"
      return chunk
  ```
- Injector protocol:
  - Script exports `process_chunk(chunk: dict) -> dict` function
  - Called for each chunk before embedding generation
  - Metadata merged into `ChunkMetadata.extra`
- Alternative: JSON metadata file per folder
  ```json
  {
    "folder_metadata": {
      "team": "backend",
      "project": "api-service"
    }
  }
  ```

## Complexity Assessment

| Feature | Complexity | Reason |
|---------|-----------|--------|
| List indexed folders | **Low** | Read from persisted list, format output |
| Persist indexed folders | **Low** | JSON file write on index complete |
| Remove folder's chunks | **Medium** | ChromaDB `where` filter on `source` field (supports prefix matching), needs careful filter construction |
| File type presets | **Low** | Static map, pattern expansion logic |
| Content injection via script | **Medium** | Dynamic import, function call protocol, error handling |
| Content injection via folder metadata | **Low** | JSON file read, metadata merge |
| Manifest tracking | **Medium-High** | Checksum calculation, diff logic, persistent storage per folder |
| Chunk eviction | **Medium** | Depends on manifest, bulk delete by IDs |
| Incremental reindex | **High** | Orchestrates manifest diff + chunk eviction + selective reindexing |

## Known Limitations from Research

1. **ChromaDB batch limits**: Max 41,666 items per operation (Agent Brain already handles via batching)
2. **Metadata filtering performance**: `where` filters on large collections can be slow; ChromaDB doesn't index metadata by default
3. **Manifest storage**: File-per-folder approach scales to ~1,000 folders before needing database
4. **Checksum overhead**: Hashing large codebases (100K+ files) takes time; mtime comparison faster but less reliable
5. **Delete by source prefix**: ChromaDB `where` doesn't support regex; need exact match or `$in` for multiple sources

## Sources

**Indexed Folder Management:**
- [RLAMA RAG Pipeline with Directory Watching](https://rlama.dev/blog/directory-watching)
- [Building a Production-Ready RAG System with Incremental Indexing](https://dev.to/guptaaayush8/building-a-production-ready-rag-system-with-incremental-indexing-4bme)
- [LangChain: Delete all vectors by source document (Qdrant)](https://github.com/langchain-ai/langchain/discussions/19903)

**File Type Filtering:**
- [ripgrep User Guide](https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md)
- [VS Code: Support Search profiles for predetermined file extensions](https://github.com/microsoft/vscode/issues/101481)
- [Sourcegraph Search Query Syntax](https://docs.sourcegraph.com/code_search/reference/queries)

**Chunk Eviction & Manifest Tracking:**
- [CocoIndex: Realtime Codebase Indexing](https://github.com/cocoindex-io/realtime-codebase-indexing)
- [mcp-rag-server: Manifest-based RAG](https://github.com/Daniel-Barta/mcp-rag-server)
- [Incremental Updates in RAG Systems (2026)](https://dasroot.net/posts/2026/01/incremental-updates-rag-dynamic-documents/)
- [Azure AI Search: Incrementally Indexing Documents](https://medium.com/microsoftazure/incrementally-indexing-documents-with-azureai-search-integrated-vectorization-6f7150556f62)

**Content Injection:**
- [Amazon Kendra: Custom Document Enrichment](https://docs.aws.amazon.com/kendra/latest/dg/custom-document-enrichment.html)
- [Haystack: Automated Structured Metadata Enrichment](https://haystack.deepset.ai/cookbook/metadata_enrichment)
- [deepset: Leveraging Metadata in RAG Customization](https://www.deepset.ai/blog/leveraging-metadata-in-rag-customization)
- [deepset: The Role of Data Preprocessing in RAG](https://www.deepset.ai/blog/preprocessing-rag)

**Vector Database Management:**
- [ChromaDB Tutorial: Delete Data](https://docs.trychroma.com/docs/collections/delete-data)
- [LlamaIndex: Document Management](https://docs.llamaindex.ai/en/stable/module_guides/indexing/document_management/)
- [Efficient Document Embedding Management with ChromaDB](https://blog.gopenai.com/efficient-document-embedding-management-with-chromadb-deleting-resetting-and-more-dac0e70e713b)
