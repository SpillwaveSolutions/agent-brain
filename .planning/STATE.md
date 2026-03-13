---
gsd_state_version: 1.0
milestone: v8.0
milestone_name: Performance & Developer Experience
current_phase: 19
current_plan: Not started
status: completed
stopped_at: Phase 23 context gathered
last_updated: "2026-03-13T01:56:06.574Z"
last_activity: "2026-03-10 — Phase 16 Plan 2 complete: `agent-brain cache` command group + embedding cache metrics in `agent-brain status` + 12 tests"
progress:
  total_phases: 11
  completed_phases: 3
  total_plans: 11
  completed_plans: 5
---

# Agent Brain — Project State
**Last Updated:** 2026-03-10
**Current Milestone:** v8.0 Performance & Developer Experience
**Status:** Milestone complete
**Current Phase:** 19
**Total Phases:** 4 (Phases 15-18)
**Current Plan:** Not started
**Total Plans in Phase:** 2

## Current Position
Phase: 16 of 18 (Embedding Cache)
Plan: 2 of 2
Status: Phase 16 complete
Last activity: 2026-03-10 — Phase 16 Plan 2 complete: `agent-brain cache` command group + embedding cache metrics in `agent-brain status` + 12 tests

**Progress (v8.0):** [█████░░░░░] 50%

## Project Reference
See: .planning/PROJECT.md (updated 2026-03-06)
**Core value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Current focus:** v8.0 Performance & Developer Experience — Phase 16 complete, ready for Phase 17: Query Cache

## Milestone Summary
```
v3.0 Advanced RAG:          [██████████] 100% (shipped 2026-02-10)
v6.0 PostgreSQL Backend:    [██████████] 100% (shipped 2026-02-13)
v6.0.4 Plugin & Install:   [██████████] 100% (shipped 2026-02-22)
v7.0 Index Mgmt & Pipeline: [██████████] 100% (shipped 2026-03-05)
v8.0 Performance & DX:      [█████░░░░░]  50% (Phase 15+16 complete)
```

## Performance Metrics
**Velocity (v7.0 milestone):**
- Total plans completed: 7 (Phases 12-14)
- Phases 12-14: 3+2+2 = 7 plans
- Average duration: ~18 min/plan

**By Phase (v7.0):**
| Phase | Plans | Duration | Status |
|-------|-------|----------|--------|
| Phase 12: Folder Mgmt & Presets | 3 | ~100 min | Complete |
| Phase 13: Content Injection | 2 | ~13 min | Complete |
| Phase 14: Manifest & Eviction | 2 | ~14 min | Complete |

**By Phase (v8.0 in progress):**
| Phase | Plans | Duration | Status |
|-------|-------|----------|--------|
| Phase 15: File Watcher & BGINC | 2 | 13 min total (7+6) | Complete |
| Phase 16: Embedding Cache | 2 | 14 min total (10+4) | Complete |
| Phase 19-plugin-and-skill-updates-for-embedding-cache-management P01 | 2 | 2 tasks | 6 files |

## Accumulated Context

### Key v7.0 Decisions (relevant to v8.0)
- ManifestTracker uses SHA-256 + mtime fast-path — embedding cache must complement this (hash already available)
- Atomic temp+Path.replace() for JSONL writes — same pattern required for aiosqlite cache writes
- JobRecord.eviction_summary as dict[str, Any] — extend same model for source indicator (BGINC-04)
- Two-step ChromaDB delete guards against empty ids=[] bug — embedding cache IDs must never be empty list

### Key v8.0 Decisions (Phase 15)
- watchfiles 1.1.1 is already a transitive dep via uvicorn — confirmed, no new install needed
- anyio.Event (not asyncio.Event) used for stop_event — watchfiles.awatch requires anyio-compatible event, must be created inside async context
- One asyncio.Task per folder — independent lifecycles, named tasks (watcher:{path})
- source="auto" field on JobRecord default='manual' — full backward compatibility
- force=False for watcher-triggered jobs — rely on ManifestTracker for incremental efficiency (BGINC-03)
- allow_external=True for watcher-enqueued jobs — auto-mode folders may be outside project root
- TYPE_CHECKING guard prevents circular: services/file_watcher_service.py -> job_queue/job_service.py -> models
- FileWatcherService stops BEFORE JobWorker (dependency order in shutdown)
- watch_mode/watch_debounce_seconds on JobRecord (not just IndexRequest) — JobWorker needs them post-completion
- Setter injection for FileWatcherService/FolderManager on JobWorker — lifespan creates them sequentially
- _apply_watch_config catches all exceptions — watch config failure does not fail an otherwise successful job
- include_code now passed from IndexingService to folder_manager.add_folder() (was missing)

### Key v8.0 Decisions (Phase 16)
- Lazy import in embed_text/embed_texts (not module-level) breaks circular import: indexing -> services -> indexing
- persist_stats=False default — session-only counters avoid write contention on every cache hit
- In-memory LRU default 1000 entries (~12 MB at 3072 dims) — configurable via EMBEDDING_CACHE_MAX_MEM_ENTRIES
- get_batch() implemented from start for embed_texts() efficiency (batch SQL vs N sequential awaits)
- embedding_cache section in /health/status omitted when entry_count == 0 (clean for fresh installs)
- float32 BLOB via struct.pack — ~12 KB/entry at 3072 dims; cosine similarity unaffected (max error ~3.57e-9)
- Provider fingerprint in metadata row — O(1) startup wipe check vs O(N) per-entry scan (ECACHE-04)
- embedding_cache: dict | None on IndexingStatus dataclass — None default preserves all existing code
- No pre-fetch in --yes path: cache clear --yes skips count lookup (avoids extra API call)
- Connection-safe count fetch in cache clear confirmation: try/except shows 0 if fetch fails

### v8.0 Phase Order Rationale (revised 2026-03-06)
- Phase 15 (File Watcher + BGINC): DX first — user's top priority; builds on Phase 14 ManifestTracker
- Phase 16 (Embedding Cache): Cost optimization for the now-running watcher — prevents API bill from automatic reindexing
- Phase 17 (Query Cache): Freshness guarantees after auto-reindex; index_generation counter established by Phase 16
- Phase 18 (UDS + Quality Gate): Ship last — touches api/main.py server startup (widest blast radius)

### v8.0 Phase Dependencies
- Phase 15 (File Watcher + BGINC): Builds on Phase 14 ManifestTracker + IndexingService + job queue
- Phase 16 (Embedding Cache): Watcher must be running first — cache makes repeated auto-reindexing cheap
- Phase 17 (Query Cache): Requires Phase 15 (watcher generates reindex events needing cache invalidation) + Phase 16 (index_generation counter)
- Phase 18 (UDS + Quality Gate): Ship last — touches api/main.py server startup (widest blast radius)

### Roadmap Evolution
- Phase 20 added: Plugin skill next-step hints should suggest slash commands (not just CLI commands)
- Phase 21 added: Fix duplicate chunk ID crash during indexing (ChromaDB DuplicateIDError when duplicate files exist)
- Phase 22 added: Restore setup wizard with full configuration prompts (storage backend, embedding provider, query mode, index types)
- Phase 23 added: Migrate global config from ~/.agent-brain to ~/.config/agent-brain + uninstall cleanup (XDG compliance + clean uninstall)
- Phase 24 added: Setup agent permissions + helper script — eliminate permission prompts during setup wizard (config detection, Ollama checks, dir creation, large-dir scanning)
- Phase 25 added: Setup wizard coverage gaps — GraphRAG opt-in prompt, BM25 unavailable with PostgreSQL (uses built-in keyword search), search mode education, cache mention, GraphRAG+PostgreSQL compatibility research

### Research Flags for Planning
- Phase 15: watchfiles confirmed as transitive dep via Uvicorn (resolved)
- Phase 16: aiosqlite WAL mode verified working under concurrent access (resolved)
- Phase 18: Validate asyncio.gather(tcp_server.serve(), uds_server.serve()) against pinned Uvicorn version

### Blockers/Concerns
- Phase 18 UDS dual-server pattern is MEDIUM confidence (community-verified, not official Uvicorn docs)

### Pending Todos
0 pending todos.

## Session Continuity

**Last Session:** 2026-03-13T01:56:06.570Z
**Stopped At:** Phase 23 context gathered
**Resume File:** .planning/phases/23-migrate-global-config-from-agent-brain-to-config-agent-brain-uninstall-cleanup/23-CONTEXT.md
**Next Action:** Phase 17 — Query Cache (freshness guarantees after auto-reindex)

---
*State updated: 2026-03-10*
