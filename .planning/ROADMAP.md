# Agent Brain Roadmap

**Created:** 2026-02-07
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API

## Milestones

- ✅ **v3.0 Advanced RAG** — Phases 1-4 (shipped 2026-02-10)
- ✅ **v6.0 PostgreSQL Backend** — Phases 5-10 (shipped 2026-02-13)
- ✅ **v6.0.4 Plugin & Install Fixes** — Phase 11 (shipped 2026-02-22)
- ✅ **v7.0 Index Management & Content Pipeline** — Phases 12-14 (shipped 2026-03-05)

## Phases

<details>
<summary>✅ v3.0 Advanced RAG (Phases 1-4) — SHIPPED 2026-02-10</summary>

- [x] Phase 1: Two-Stage Reranking (7/7 plans) — Feature 123
- [x] Phase 2: Pluggable Providers (4/4 plans) — Feature 103
- [x] Phase 3: Schema-Based GraphRAG (2/2 plans) — Feature 122
- [x] Phase 4: Provider Integration Testing (2/2 plans) — Feature 124

**Full details:** [v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md)

</details>

<details>
<summary>✅ v6.0 PostgreSQL Backend (Phases 5-10) — SHIPPED 2026-02-13</summary>

- [x] Phase 5: Storage Backend Abstraction Layer (2/2 plans) — 2026-02-10
- [x] Phase 6: PostgreSQL Backend Implementation (3/3 plans) — 2026-02-11
- [x] Phase 7: Testing & CI Integration (2/2 plans) — 2026-02-12
- [x] Phase 8: Plugin & Documentation (2/2 plans) — 2026-02-12
- [x] Phase 9: Runtime Backend Wiring (2/2 plans) — 2026-02-12
- [x] Phase 10: Live PostgreSQL E2E Validation (1/1 plans) — 2026-02-12

**Full details:** [v6.0.4-ROADMAP.md](milestones/v6.0.4-ROADMAP.md)

</details>

<details>
<summary>✅ v6.0.4 Plugin & Install Fixes (Phase 11) — SHIPPED 2026-02-22</summary>

- [x] Phase 11: Plugin Port Discovery & Install Fix (1/1 plans) — 2026-02-22

**Full details:** [v6.0.4-ROADMAP.md](milestones/v6.0.4-ROADMAP.md)

</details>

<details>
<summary>✅ v7.0 Index Management & Content Pipeline (Phases 12-14) — SHIPPED 2026-03-05</summary>

- [x] Phase 12: Folder Management & File Type Presets (3/3 plans) — 2026-02-25
- [x] Phase 13: Content Injection Pipeline (2/2 plans) — 2026-03-05
- [x] Phase 14: Manifest Tracking & Chunk Eviction (2/2 plans) — 2026-03-05

</details>

---

## Phase 12: Folder Management & File Type Presets

**Goal:** Users can list, add, and remove indexed folders via CLI/API/plugin, and use shorthand file type presets instead of manual glob patterns.

**Requirements:** FOLD-01..10, FTYPE-01..07 (17 requirements)

**Plans:** 3 plans

Plans:
- [ ] 12-01-PLAN.md — Server foundation: FolderManager, FileTypePresetResolver, models, protocol extension
- [ ] 12-02-PLAN.md — API endpoints + server integration: folders router, lifespan wiring, include_types
- [ ] 12-03-PLAN.md — CLI commands + plugin: folders, types, --include-type flag, plugin commands

**Success Criteria:**
1. `agent-brain folders list` shows all indexed folders with chunk counts
2. `agent-brain folders remove /path` deletes all chunks for that folder
3. `agent-brain index /path --include-type python,docs` indexes only matching file types
4. Indexed folders persist across server restarts
5. All commands work with both ChromaDB and PostgreSQL backends
6. Plugin slash commands mirror CLI folder management

**Key Components:**
- `FolderManager` service — persist/list/remove indexed folders (JSONL storage)
- `FileTypePresetResolver` — map preset names to glob patterns
- API endpoints: `GET /index/folders`, `DELETE /index/folders`
- CLI commands: `agent-brain folders list|add|remove`, `agent-brain types list`
- CLI flag: `--include-type` on `agent-brain index`

**Research Flags:** ChromaDB `where` filter performance on large collections, path normalization strategy

---

## Phase 13: Content Injection Pipeline

**Goal:** Users can enrich chunks with custom metadata during indexing via Python scripts or folder-level JSON metadata.

**Requirements:** INJECT-01..08 (8 requirements)

**Plans:** 2 plans

Plans:
- [ ] 13-01-PLAN.md — Server foundation: ContentInjector service, model extensions, pipeline integration, dry-run, tests
- [ ] 13-02-PLAN.md — CLI inject command, DocServeClient extension, protocol documentation

**Success Criteria:**
1. `agent-brain inject --script enrich.py /path` applies custom metadata to chunks
2. `--folder-metadata metadata.json` merges static metadata into all chunks from a folder
3. Injector exceptions don't crash the indexing job (per-chunk error handling)
4. `--dry-run` mode validates script without indexing
5. Injector protocol documented with example scripts

**Key Components:**
- Content injector callable protocol (`process_chunk(chunk: dict) -> dict`)
- Dynamic script loading with validation
- Folder-level JSON metadata merge
- Integration into IndexingService pipeline (post-chunk, pre-embed)

**Research Flags:** Standard patterns, unlikely to need deep research

---

## Phase 14: Manifest Tracking & Chunk Eviction

**Goal:** Automatically detect file changes, evict stale chunks, and only reindex modified files — enabling efficient incremental updates.

**Requirements:** EVICT-01..10 (10 requirements)

**Plans:** 2 plans

Plans:
- [ ] 14-01-PLAN.md — Foundation: ManifestTracker, ChunkEvictionService, storage_paths extension, JobRecord model changes, unit tests
- [ ] 14-02-PLAN.md — Pipeline integration: IndexingService wiring, JobWorker force threading, BM25 rebuild, CLI eviction summary, integration tests

**Success Criteria:**
1. Reindexing a folder only processes changed/new files (unchanged files skipped)
2. Deleted files' chunks automatically evicted from index
3. Changed files' old chunks replaced with new ones
4. `--force` bypasses manifest for full reindex
5. CLI shows eviction summary (added/changed/deleted counts)
6. StorageBackendProtocol extended with `delete_by_ids()` method

**Key Components:**
- `ManifestTracker` — per-folder manifest (file_path → checksum + mtime + chunk_ids)
- `ChunkEvictionService` — detect changes, bulk delete stale chunks
- Manifest storage in `.agent-brain/manifests/<hash>.json`
- Integration with IndexingService for incremental pipeline

**Research Flags:** Manifest storage scalability, checksum vs mtime tradeoffs, chunk ID retrieval from ChromaDB

---

## Progress

**Execution Order:**
Phases execute in numeric order: 12 → 13 → 14

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Two-Stage Reranking | v3.0 | 7/7 | Complete | 2026-02-08 |
| 2. Pluggable Providers | v3.0 | 4/4 | Complete | 2026-02-09 |
| 3. Schema-Based GraphRAG | v3.0 | 2/2 | Complete | 2026-02-10 |
| 4. Provider Integration Testing | v3.0 | 2/2 | Complete | 2026-02-10 |
| 5. Storage Abstraction | v6.0 | 2/2 | Complete | 2026-02-10 |
| 6. PostgreSQL Backend | v6.0 | 3/3 | Complete | 2026-02-11 |
| 7. Testing & CI | v6.0 | 2/2 | Complete | 2026-02-12 |
| 8. Plugin & Documentation | v6.0 | 2/2 | Complete | 2026-02-12 |
| 9. Runtime Backend Wiring | v6.0 | 2/2 | Complete | 2026-02-12 |
| 10. Live PostgreSQL E2E Validation | v6.0 | 1/1 | Complete | 2026-02-12 |
| 11. Plugin Port Discovery & Install Fix | v6.0.4 | 1/1 | Complete | 2026-02-22 |
| 12. Folder Management & File Type Presets | v7.0 | 3/3 | Complete | 2026-02-25 |
| 13. Content Injection Pipeline | v7.0 | 2/2 | Complete | 2026-03-05 |
| 14. Manifest Tracking & Chunk Eviction | v7.0 | 2/2 | Complete | 2026-03-05 |

## Future Phases

### Phase 15+: AWS Bedrock Provider (Feature 105)

- Bedrock embeddings (Titan, Cohere)
- Bedrock summarization (Claude, Llama, Mistral)

### Phase 16+: Vertex AI Provider (Feature 106)

- Vertex embeddings (textembedding-gecko)
- Vertex summarization (Gemini)

### Future Optimizations

- Embedding cache with content hashing
- File watcher for auto-indexing
- Background incremental updates
- Query caching with LRU
- UDS transport for sub-ms latency

---

## Completed Phases (Legacy Archive)

### Phase 1 (Legacy): Core Document RAG — COMPLETED
Features 001-005: Document ingestion, vector search, REST API, CLI

### Phase 2 (Legacy): BM25 & Hybrid Retrieval — COMPLETED
Feature 100: BM25 keyword search, hybrid retrieval with RRF

### Phase 3 (Legacy): Source Code Ingestion — COMPLETED
Feature 101: AST-aware code ingestion, code summaries

### Phase 3.1-3.6 (Legacy): Extensions — COMPLETED
- 109: Multi-instance architecture
- 110: C# code indexing
- 111: Skill instance discovery
- 112: Agent Brain naming
- 113: GraphRAG integration
- 114: Agent Brain plugin
- 115: Server-side job queue

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-03-05 — Phase 14 complete, v7.0 milestone shipped*
