# Requirements: v7.0 Index Management & Content Pipeline

**Defined:** 2026-02-23
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships

## Goal

Give users full control over what gets indexed, how folders are managed, and how content is enriched — eliminating ghost chunks, enabling smart file type selection, and adding optional LLM-powered chunk enrichment.

## Folder Management

- [ ] **FOLD-01**: List all indexed folders via CLI (`agent-brain folders list`) showing path, chunk count, and last indexed time
- [ ] **FOLD-02**: List all indexed folders via API (`GET /index/folders`) returning JSON object with folders array and total count
- [ ] **FOLD-03**: Remove a specific folder's chunks via CLI (`agent-brain folders remove /path`) with confirmation
- [ ] **FOLD-04**: Remove a specific folder's chunks via API (`DELETE /index/folders` with folder_path body)
- [ ] **FOLD-05**: Persist indexed folder list to disk (`indexed_folders.jsonl`) — survives server restarts
- [ ] **FOLD-06**: Normalize all folder paths to absolute canonical form before storing (resolve symlinks, `.`, `..`)
- [ ] **FOLD-07**: Reject folder removal if an active indexing job exists for that folder
- [ ] **FOLD-08**: Bulk delete chunks by folder using ChromaDB metadata filter or PostgreSQL WHERE clause
- [ ] **FOLD-09**: Add folder command (`agent-brain folders add /path`) as alias for idempotent index operation
- [ ] **FOLD-10**: Plugin slash commands for folder management (`/agent-brain-folders list`, `/agent-brain-folders remove`)

## File Type Presets

- [ ] **FTYPE-01**: Predefined file type presets map names to glob patterns (python, javascript, typescript, go, rust, java, web, docs, code, text, pdf)
- [ ] **FTYPE-02**: CLI `--include-type` flag accepts comma-separated preset names (`agent-brain index /path --include-type python,docs`)
- [ ] **FTYPE-03**: API `include_types` field in IndexRequest expands presets to glob patterns before DocumentLoader
- [ ] **FTYPE-04**: `agent-brain types list` CLI command shows all available presets with their extensions
- [ ] **FTYPE-05**: Unknown preset names raise clear error with list of valid presets
- [ ] **FTYPE-06**: `--include-type` and `--include` can be combined (union of both pattern sets)
- [ ] **FTYPE-07**: Plugin support for file type presets in `/agent-brain-index` command

## Chunk Eviction & Live Reindex

- [ ] **EVICT-01**: Manifest file per indexed folder tracks file_path → checksum + mtime + chunk_ids
- [ ] **EVICT-02**: On reindex, compare current files against manifest to detect added/changed/deleted files
- [ ] **EVICT-03**: Deleted files trigger bulk chunk eviction (delete chunk IDs from storage backend)
- [ ] **EVICT-04**: Changed files trigger chunk eviction then re-indexing (delete old chunks, create new)
- [ ] **EVICT-05**: New files indexed normally without evicting anything
- [ ] **EVICT-06**: Manifest persisted to `.agent-brain/manifests/<hash>.json` per folder
- [ ] **EVICT-07**: Incremental reindex only processes changed/new files (skip unchanged by checksum)
- [ ] **EVICT-08**: `--force` flag bypasses manifest comparison (full reindex, rebuilds manifest)
- [ ] **EVICT-09**: CLI shows eviction summary (files added/changed/deleted, chunks evicted/created)
- [ ] **EVICT-10**: StorageBackendProtocol extended with `delete_by_ids(ids: list[str])` method

## Content Injector

- [ ] **INJECT-01**: CLI command `agent-brain inject --script enrich.py /path` applies custom metadata during indexing
- [ ] **INJECT-02**: Injector script exports `process_chunk(chunk: dict) -> dict` callable protocol
- [ ] **INJECT-03**: Injector called for each chunk before embedding generation
- [ ] **INJECT-04**: Folder-level metadata alternative via `--folder-metadata metadata.json` merges into all chunks
- [ ] **INJECT-05**: Injector exceptions caught per-chunk (log warning, skip enrichment, continue indexing)
- [ ] **INJECT-06**: `--dry-run` flag tests injector script against sample chunks without indexing
- [ ] **INJECT-07**: Injector metadata merged into `ChunkMetadata.extra` dict
- [ ] **INJECT-08**: Document injector protocol and provide example scripts

## Cross-Cutting

- [ ] **XCUT-01**: All new features work with both ChromaDB and PostgreSQL backends
- [ ] **XCUT-02**: File locking or atomic writes prevent JSONL corruption from concurrent operations
- [ ] **XCUT-03**: All new CLI commands include `--help` with usage examples
- [ ] **XCUT-04**: All new API endpoints documented in OpenAPI schema
- [ ] **XCUT-05**: Unit tests for all new modules (>70% coverage)
- [ ] **XCUT-06**: `task before-push` passes with all changes

## Phase Mapping

| Phase | Requirements | Description |
|-------|-------------|-------------|
| Phase 12 | FOLD-01..10, FTYPE-01..07 | Core folder management + file type presets |
| Phase 13 | INJECT-01..08 | Content injection pipeline |
| Phase 14 | EVICT-01..10 | Manifest tracking + chunk eviction |
| All | XCUT-01..06 | Cross-cutting quality gates |

## Requirement Count

| Category | Count |
|----------|-------|
| Folder Management | 10 |
| File Type Presets | 7 |
| Chunk Eviction | 10 |
| Content Injector | 8 |
| Cross-Cutting | 6 |
| **Total** | **41** |

---
*Requirements defined: 2026-02-23*
