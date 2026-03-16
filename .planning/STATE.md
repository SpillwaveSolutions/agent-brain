---
gsd_state_version: 1.0
milestone: v8.0
milestone_name: Performance & Developer Experience
current_phase: 25
current_plan: 02
status: completed
stopped_at: Completed 25-02-PLAN.md
last_updated: "2026-03-15T00:00:00Z"
last_activity: "2026-03-15 — Phase 25 Plans 1+2 complete: Setup wizard BM25/PostgreSQL awareness, GraphRAG gate, cache awareness note + skill docs query cache + PostgreSQL BM25 note"
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 9
  completed_plans: 9
---

# Agent Brain — Project State
**Last Updated:** 2026-03-12
**Current Milestone:** v8.0 Performance & Developer Experience
**Status:** Phase 22 complete
**Current Phase:** 22
**Total Phases:** Phase 22 complete
**Current Plan:** 02 of 02
**Total Plans in Phase:** 2

## Current Position
Phase: 25 (Setup Wizard Coverage Gaps)
Plan: 2 of 2
Status: Phase 25 complete
Last activity: 2026-03-15 — Phase 25 Plans 1+2 complete: Setup wizard now gates GraphRAG on ChromaDB backend, explains tsvector BM25 replacement for PostgreSQL, informs users about auto-enabled caches; SKILL.md and configuration-guide.md document query cache (QUERY_CACHE_TTL/MAX_SIZE) and PostgreSQL BM25 note; 15 regression tests pass

**Progress (v8.0):** [██████████] 100%

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
| Phase 22: Restore Setup Wizard with Full Config Prompts | 2 | ~15 min | Complete |
| Phase 24: Setup Permissions & Helper Script | 2 | ~12 min | Complete |
| Phase 25: Setup Wizard Coverage Gaps | 2 | ~14 min | Complete |

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

### Key Phase 24 Decisions (Setup Permissions & Helper Script)
- Write-tool-first bootstrap: .claude/settings.json written with Write tool (always pre-authorized), not Bash — no permission gate
- 24 Bash entries in allowlist: agent-brain, lsof, ollama, docker, mkdir, cat, jq, mv, du, ps, pgrep, pip, pipx, uv, python, python3, rg, wc, curl, ls, find, chmod, grep, bash
- ab-setup-check.sh uses set -uo pipefail (not -e) to avoid aborting on missing optional tools
- SETUP_STATE variable stored in memory for reuse across all wizard steps — single detection call
- MERGE semantics on existing .claude/settings.json — avoids destroying custom user permissions
- Full JSON permission block inlined in agent-brain-setup.md — command is self-contained

### Key Phase 25 Decisions (Setup Wizard Coverage Gaps)
- GraphRAG gate in Step 5: two-branch conditional — PostgreSQL gets informational block, ChromaDB gets existing 3-option prompt
- BM25/tsvector note placed inside "If PostgreSQL is selected" section in Step 4 as a blockquote
- Cache awareness note uses blockquote format in Step 6 after the --mode override note
- tests/ directory created in agent-brain-plugin (did not exist before Phase 25)
- 15 regression tests written (12 structural + 3 new); plan expected 14 = 11 existing + 3 new
- SKILL.md "Embedding Cache Tuning" renamed to "Caching" with two subsections (Embedding Cache + Query Cache)
- Query Mode table column renamed from "Requires GraphRAG" to "Requirements"
- Query Cache Configuration section added to configuration-guide.md after GraphRAG via Environment Variables

### Key Phase 22 Decisions (Restore Setup Wizard)
- query.default_mode written as YAML comment only — server has no global default_mode config key; mode is per-request via --mode flag
- Python yaml.dump used for safe config.yaml serialization in wizard write step — avoids manual YAML string quoting errors
- chmod 600 applied automatically after config.yaml write — security enforcement without extra user steps
- Wizard detects existing config and offers update/fresh/skip — preserves user's existing configuration
- autouse pytest fixture skips wizard regression tests if plugin dir not found — graceful CI degradation
- 11 regression tests instead of planned 10 — added test_setup_wizard_writes_config_yaml for config.yaml write step coverage

### Research Flags for Planning
- Phase 15: watchfiles confirmed as transitive dep via Uvicorn (resolved)
- Phase 16: aiosqlite WAL mode verified working under concurrent access (resolved)
- Phase 18: Validate asyncio.gather(tcp_server.serve(), uds_server.serve()) against pinned Uvicorn version

### Blockers/Concerns
- Phase 18 UDS dual-server pattern is MEDIUM confidence (community-verified, not official Uvicorn docs)

### Pending Todos
0 pending todos.

## Session Continuity

**Last Session:** 2026-03-15T00:00:00Z
**Stopped At:** Completed 25-02-PLAN.md
**Resume File:** None
**Next Action:** Phase 24 — Setup Permissions & Helper Script (parallel, independent of Phase 25)

---
*State updated: 2026-03-10*
