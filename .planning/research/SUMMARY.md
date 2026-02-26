# Research Summary: v7.0 Index Management & Content Pipeline

**Domain:** RAG index management and content enrichment
**Researched:** 2026-02-23
**Overall confidence:** HIGH

## Executive Summary

Agent Brain v7.0 should add index folder management (list/add/remove), smart file type presets, chunk eviction tracking, and content injection capabilities to address the critical pain point of "no way to clean up specific folders without full reset." Research shows modern RAG systems use manifest-based change detection for incremental updates, file-type presets (ripgrep-style) for UX simplification, and metadata enrichment hooks for domain customization. The recommended approach prioritizes simple folder management and file type presets (low complexity, high user value) in Phase 1, defers complex manifest tracking and chunk eviction (medium-high complexity, dependent features) to Phase 2+.

The critical path follows: (1) persist indexed folder list and implement removal via ChromaDB `where` filters, (2) add file type preset system expanding to glob patterns, (3) implement content injection via Python script hooks or JSON folder metadata, (4) defer manifest tracking until folder management patterns validated in production. The main risk is over-engineering manifest tracking before validating simpler folder operations, mitigated by phasing complex dependency tracking after core features proven.

Key architectural decision: Use ChromaDB's `where` metadata filter with `$or` conditions for bulk delete by folder path (source field), expand file type presets to include_patterns before DocumentLoader, inject content metadata via chunk processing hooks before embedding generation. Persist indexed folders to `.agent-brain/indexed_folders.json` for restart survival. Defer manifest-based incremental reindex (file checksum tracking, chunk eviction) until Phase 2 when folder management patterns established.

## Key Findings

**Stack:** Existing Agent Brain stack sufficient (ChromaDB, LlamaIndex, Python 3.10+). No new dependencies for Phase 1. Manifest tracking (Phase 2+) needs hashlib (built-in), mtime comparison (pathlib), JSON persistence.

**Architecture:** Indexed folder manager persists list to disk, ChromaDB delete uses metadata filtering on `source` field, file type presets in config/file_type_presets.py map names → glob patterns, content injector uses Python callable protocol or JSON merge.

**Critical pitfall:** ChromaDB metadata filters don't support regex or prefix matching — need to list all file paths or use `$or` with multiple exact matches for folder removal. Workaround: Track file→folder mapping in manifest (Phase 2) or query ChromaDB for all sources with folder prefix.

## Implications for Roadmap

Based on research, suggested phase structure prioritizes quick wins (folder visibility, removal, file presets) before complex features (manifest tracking, chunk eviction, incremental reindex).

### Phase 1: Core Folder Management + File Type Presets

**Delivers:**
- List indexed folders (CLI + API)
- Remove specific folder's chunks (CLI + API)
- Persist indexed folders to disk (survives restarts)
- File type presets (python, javascript, typescript, web, docs)
- Add folder command (idempotent indexing)

**Rationale:** These are table stakes features users expect. Low complexity (metadata filtering already exists, pattern expansion is simple). High user value (unblocks cleanup without full reset, dramatically improves UX over manual globs).

**Phase ordering rationale:**
- List folders before remove (users need visibility)
- Persist folders alongside list (restart survival expected)
- File type presets parallel to folder management (independent features)
- Content injection deferred to Phase 2 (more complex, fewer users need it immediately)

### Phase 2: Content Injection & Folder Metadata

**Delivers:**
- Content injection via Python script (`--inject-script enrich.py`)
- Folder-level metadata injection (`--folder-metadata metadata.json`)
- Metadata merge into ChunkMetadata.extra
- Injection protocol documentation

**Rationale:** Differentiators that enable power-user workflows (tagging, sensitivity labeling, team metadata). Medium complexity (dynamic import, callable protocol, error handling). Deferred after folder management proven (fewer users need this immediately).

**Phase ordering rationale:**
- After folder management validated (users understand what folders are indexed)
- Before manifest tracking (injected metadata doesn't require change detection)
- Script injection more flexible than JSON (JSON fallback for simple cases)

### Phase 3: Manifest Tracking + Chunk Eviction

**Delivers:**
- Manifest file per indexed folder (`.agent-brain/manifests/<hash>.json`)
- File checksum/mtime tracking
- Chunk eviction for deleted files
- Incremental reindex (only changed files)

**Rationale:** Complex features requiring persistent storage, checksum calculation, diff logic. High value for users with frequently changing codebases. Deferred until core folder management patterns established.

**Phase ordering rationale:**
- After Phase 1 and 2 proven (complex dependencies)
- Manifest structure depends on folder management patterns (need production data)
- Chunk eviction requires file→chunk mapping (build manifest first)
- Incremental reindex orchestrates manifest + eviction (highest complexity last)

**Research flags for phases:**
- Phase 1: Likely needs deeper research — ChromaDB `where` filter performance on large collections, optimal folder path normalization strategy
- Phase 2: Standard patterns, unlikely to need research — Python callable protocol well-documented, JSON merge straightforward
- Phase 3: Likely needs deeper research — Manifest storage scalability (file-per-folder vs single DB), checksum vs mtime tradeoffs, chunk ID retrieval from ChromaDB by source field

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Folder management | HIGH | ChromaDB `where` filters documented, deletion patterns verified in official docs |
| File type presets | HIGH | Ripgrep model well-established, glob pattern expansion straightforward |
| Content injection | MEDIUM-HIGH | AWS Kendra CDE and LlamaIndex patterns documented, Python callable protocol standard |
| Manifest tracking | MEDIUM | CocoIndex and mcp-rag-server patterns documented, but no Agent Brain-specific testing yet |
| Chunk eviction | MEDIUM | ChromaDB bulk delete by IDs supported, but performance on 100K+ chunks unknown |
| Incremental reindex | MEDIUM | Azure AI pattern documented, but integration with existing indexing service needs design |

## Gaps to Address

**ChromaDB deletion performance:** `where` filters on metadata not indexed by default. Large collections (100K+ chunks) may have slow delete operations. Need to test performance and potentially implement batch deletion strategy.

**Folder path normalization:** Research shows absolute path normalization prevents duplicates, but Windows vs Unix path handling needs verification. Pathlib handles this, but need to test edge cases (symlinks, case sensitivity on macOS).

**Manifest file scaling:** File-per-folder approach scales to ~1,000 folders before filesystem overhead becomes significant. Agent Brain targets single-codebase use case (typically 1-10 indexed folders), so this is acceptable for MVP.

**Checksum vs mtime tradeoffs:** Checksums accurate but slow (100K+ files takes minutes), mtime fast but unreliable (doesn't detect content-only changes). Research suggests hybrid: mtime for first-pass filter, checksum for changed files. Need to validate in Phase 3.

**ChromaDB metadata filter syntax:** Documentation shows `$or`, `$and`, `$in` operators, but complex queries (prefix matching) not supported. Need to query all chunks, filter in Python, then bulk delete by IDs. Performance impact unknown.

