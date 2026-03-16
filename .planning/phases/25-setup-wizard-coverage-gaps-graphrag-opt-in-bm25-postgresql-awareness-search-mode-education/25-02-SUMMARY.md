---
phase: 25-setup-wizard-coverage-gaps-graphrag-opt-in-bm25-postgresql-awareness-search-mode-education
plan: "02"
subsystem: plugin-skill-docs
tags:
  - skill-docs
  - postgresql
  - bm25
  - graphrag
  - query-cache
  - configuration
dependency_graph:
  requires: []
  provides:
    - "SKILL.md Caching section covering both embedding and query caches"
    - "SKILL.md Query Mode table with ChromaDB backend requirement for graph/multi"
    - "SKILL.md PostgreSQL BM25/tsvector note"
    - "configuration-guide.md QUERY_CACHE_TTL and QUERY_CACHE_MAX_SIZE env vars"
    - "configuration-guide.md Query Cache Configuration section"
    - "configuration-guide.md PostgreSQL BM25/tsvector note in Storage section"
  affects:
    - "agent-brain-plugin/skills/configuring-agent-brain/SKILL.md"
    - "agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md"
tech_stack:
  added: []
  patterns:
    - "Additive documentation updates preserving all existing content"
key_files:
  created: []
  modified:
    - "agent-brain-plugin/skills/configuring-agent-brain/SKILL.md"
    - "agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md"
decisions:
  - "Renamed 'Embedding Cache Tuning' to 'Caching' with two subsections (Embedding Cache + Query Cache)"
  - "Query Mode table column renamed from 'Requires GraphRAG' to 'Requirements'"
  - "PostgreSQL BM25 note placed after wizard config table in SKILL.md (before Standalone Config Command)"
  - "Query Cache section added after GraphRAG via Environment Variables in configuration-guide.md"
metrics:
  duration: "~6 minutes"
  completed: "2026-03-15"
  tasks_completed: 2
  files_changed: 2
---

# Phase 25 Plan 02: Skill Documentation Coverage Gaps (Query Cache + PostgreSQL BM25) Summary

**One-liner:** SKILL.md and configuration-guide.md now document the query cache (QUERY_CACHE_TTL/MAX_SIZE), PostgreSQL tsvector BM25 replacement, and the ChromaDB requirement for graph/multi modes.

## What Was Built

Closed two documentation gaps in the `configuring-agent-brain` skill:

### SKILL.md Changes

1. **Caching section (renamed from "Embedding Cache Tuning")**: Now has two subsections — "Embedding Cache" (existing content) and "Query Cache" (new). The Query Cache subsection explains it is automatic, that `graph`/`multi` modes bypass it, that it is invalidated on reindex, and references `QUERY_CACHE_TTL` and `QUERY_CACHE_MAX_SIZE` environment variables.

2. **Query Mode Selection table**: Column renamed from `Requires GraphRAG` to `Requirements`. `graph` and `multi` rows now show `GraphRAG + ChromaDB backend`. A note below the table explains these modes are not available with PostgreSQL backend.

3. **PostgreSQL + BM25 note**: Added after the wizard config table. Explains that `storage.backend: "postgres"` replaces the disk-based BM25 index with PostgreSQL `tsvector` + `websearch_to_tsquery`, and that `--mode bm25` works identically from the user's perspective.

### configuration-guide.md Changes

1. **Environment Variables table**: Added `QUERY_CACHE_TTL` (default: 300) and `QUERY_CACHE_MAX_SIZE` (default: 256) rows after the existing debugging variable.

2. **BM25 and Full-Text Search with PostgreSQL**: Added note after the postgres config block in the Storage Backend Configuration section, explaining tsvector replaces BM25, `ts_rank` scoring, score normalization, and `storage.postgres.language` control.

3. **Query Cache Configuration section**: New `##` section after GraphRAG configuration. Covers behavior (TTL window, invalidation, graph/multi bypass, no persistence), environment variables table, example values, and how to disable the cache (`QUERY_CACHE_TTL=0`).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update SKILL.md — query cache, mode table, PostgreSQL BM25 note | 6831e3f | SKILL.md |
| 2 | Update configuration-guide.md — query cache env vars and PostgreSQL BM25 note | 4023a5b | configuration-guide.md |

## Verification

```bash
grep -c "Query cache\|QUERY_CACHE" SKILL.md
# 3

grep -c "tsvector" SKILL.md
# 1

grep -c "QUERY_CACHE_TTL" configuration-guide.md
# 3 (table, section table, example)

grep -c "tsvector" configuration-guide.md
# 2 (BM25 note line + language note)
```

## Deviations from Plan

None — plan executed exactly as written. All changes are additive; no existing content was removed.

## Self-Check: PASSED

- [x] SKILL.md contains "Query cache" documentation with QUERY_CACHE_TTL and QUERY_CACHE_MAX_SIZE references
- [x] SKILL.md Query Mode Selection table shows "GraphRAG + ChromaDB backend" for graph/multi
- [x] SKILL.md contains "tsvector" PostgreSQL BM25 note
- [x] configuration-guide.md contains QUERY_CACHE_TTL and QUERY_CACHE_MAX_SIZE in env vars table
- [x] configuration-guide.md has "Query Cache Configuration" section
- [x] configuration-guide.md Storage Backend section contains "tsvector" BM25 note
- [x] 6831e3f commit exists
- [x] 4023a5b commit exists
