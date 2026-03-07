# Agent Brain — Project State
**Last Updated:** 2026-03-07
**Current Milestone:** v8.0 Performance & Developer Experience
**Status:** In Progress
**Current Phase:** 15 — File Watcher & Background Incremental Updates
**Total Phases:** 4 (Phases 15-18)
**Current Plan:** 2 of 2
**Total Plans in Phase:** 2

## Current Position
Phase: 15 of 18 (File Watcher & Background Incremental Updates)
Plan: 2 of 2
Status: In Progress (Plan 01 complete, Plan 02 ready)
Last activity: 2026-03-07 — Phase 15 Plan 01 complete: FileWatcherService, model extensions, backward-compatible JSONL

**Progress (v8.0):** [█░░░░░░░░░] 10%

## Project Reference
See: .planning/PROJECT.md (updated 2026-03-06)
**Core value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Current focus:** v8.0 Performance & Developer Experience — Phase 15: File Watcher & Background Incremental Updates

## Milestone Summary
```
v3.0 Advanced RAG:          [██████████] 100% (shipped 2026-02-10)
v6.0 PostgreSQL Backend:    [██████████] 100% (shipped 2026-02-13)
v6.0.4 Plugin & Install:   [██████████] 100% (shipped 2026-02-22)
v7.0 Index Mgmt & Pipeline: [██████████] 100% (shipped 2026-03-05)
v8.0 Performance & DX:      [█░░░░░░░░░]  10% (Phase 15 Plan 01 complete)
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
| Phase 15: File Watcher & BGINC | 2 | Plan 01: 7 min | Plan 01 Complete |

## Accumulated Context

### Key v7.0 Decisions (relevant to v8.0)
- ManifestTracker uses SHA-256 + mtime fast-path — embedding cache must complement this (hash already available)
- Atomic temp+Path.replace() for JSONL writes — same pattern required for aiosqlite cache writes
- JobRecord.eviction_summary as dict[str, Any] — extend same model for source indicator (BGINC-04)
- Two-step ChromaDB delete guards against empty ids=[] bug — embedding cache IDs must never be empty list

### Key v8.0 Decisions (Phase 15 Plan 01)
- watchfiles 1.1.1 is already a transitive dep via uvicorn — confirmed, no new install needed
- anyio.Event (not asyncio.Event) used for stop_event — watchfiles.awatch requires anyio-compatible event, must be created inside async context
- One asyncio.Task per folder — independent lifecycles, named tasks (watcher:{path})
- source="auto" field on JobRecord default='manual' — full backward compatibility
- force=False for watcher-triggered jobs — rely on ManifestTracker for incremental efficiency (BGINC-03)
- allow_external=True for watcher-enqueued jobs — auto-mode folders may be outside project root
- TYPE_CHECKING guard prevents circular: services/file_watcher_service.py -> job_queue/job_service.py -> models
- FileWatcherService stops BEFORE JobWorker (dependency order in shutdown)

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

### Research Flags for Planning
- Phase 15: watchfiles confirmed as transitive dep via Uvicorn (resolved)
- Phase 16: Test aiosqlite WAL mode under concurrent indexing reads/writes
- Phase 18: Validate asyncio.gather(tcp_server.serve(), uds_server.serve()) against pinned Uvicorn version

### Blockers/Concerns
- Phase 18 UDS dual-server pattern is MEDIUM confidence (community-verified, not official Uvicorn docs)

### Pending Todos
0 pending todos.

## Session Continuity

**Last Session:** 2026-03-07
**Stopped At:** Phase 15 Plan 01 complete — FileWatcherService, model extensions, 31 new tests, task before-push exits 0
**Resume File:** None
**Next Action:** Execute Phase 15 Plan 02 — CLI and plugin integration for --watch auto flag

---
*State updated: 2026-03-07*
