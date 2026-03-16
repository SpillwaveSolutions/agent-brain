---
phase: 25-setup-wizard-coverage-gaps-graphrag-opt-in-bm25-postgresql-awareness-search-mode-education
plan: "01"
subsystem: plugin-wizard
tags:
  - wizard
  - postgresql
  - bm25
  - graphrag
  - caching
  - regression-tests
dependency_graph:
  requires: []
  provides:
    - "Setup wizard BM25/PostgreSQL awareness (tsvector note in Step 4)"
    - "GraphRAG+PostgreSQL incompatibility gate in Step 5"
    - "Cache awareness note in Step 6"
    - "15 regression tests verifying wizard content"
  affects:
    - "agent-brain-plugin/commands/agent-brain-setup.md"
    - "agent-brain-plugin/tests/test_plugin_wizard_spec.py"
tech_stack:
  added:
    - "pytest (plugin test infrastructure)"
  patterns:
    - "Content-grep regression tests for markdown wizard files"
    - "autouse fixture skips gracefully if plugin dir not found"
key_files:
  created:
    - "agent-brain-plugin/tests/test_plugin_wizard_spec.py"
  modified:
    - "agent-brain-plugin/commands/agent-brain-setup.md"
decisions:
  - "Created tests/ directory in agent-brain-plugin (did not exist prior)"
  - "Built 12 structural tests + 3 new regression tests (15 total, not 14 as planned)"
  - "autouse fixture skips all tests if wizard file not found (CI-safe)"
  - "GraphRAG gate implemented as two-branch conditional at start of Step 5"
  - "Cache note uses blockquote format matching existing wizard style"
metrics:
  duration: "~8 minutes"
  completed: "2026-03-15"
  tasks_completed: 2
  files_changed: 2
---

# Phase 25 Plan 01: Setup Wizard Coverage Gaps (BM25/PostgreSQL + GraphRAG Gate + Cache) Summary

**One-liner:** Wizard now gates GraphRAG on ChromaDB backend, explains tsvector BM25 replacement for PostgreSQL, and informs users both caches are auto-enabled — with 15 regression tests.

## What Was Built

Closed three coverage gaps in the setup wizard (`agent-brain-setup.md`):

1. **Step 4 BM25/PostgreSQL note**: When PostgreSQL is selected, a blockquote explains that the disk-based BM25 index is replaced by PostgreSQL's built-in `tsvector` + `websearch_to_tsquery`, and that `--mode bm25` still works identically.

2. **Step 5 GraphRAG gate**: Step 5 now branches on the Step 4 storage backend selection. If PostgreSQL was chosen, the user sees an informational message explaining GraphRAG requires ChromaDB and will be disabled (`graphrag.enabled: false`). If ChromaDB was chosen, the existing 3-option prompt (No / Yes-Simple / Yes-Kuzu) is presented unchanged.

3. **Step 6 cache awareness note**: After the mode selection prompt, a blockquote informs the user that both the embedding cache and query cache are auto-enabled with no configuration needed, and that `graph` and `multi` modes bypass the query cache.

Also created `agent-brain-plugin/tests/` directory and `test_plugin_wizard_spec.py` with 15 regression tests (12 structural + 3 new) verifying these behaviors.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update wizard steps 4, 5, 6 with coverage gap content | cfccde5 | agent-brain-setup.md |
| 2 | Add regression tests for three new wizard behaviors | dd8bcae | tests/test_plugin_wizard_spec.py (created) |

## Verification

```
pytest tests/test_plugin_wizard_spec.py -v
15 passed in 0.03s
```

All 15 tests pass including the 3 new regression tests.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written with one minor deviation:

**1. [Rule 2 - Missing Infrastructure] Created tests/ directory**
- **Found during:** Task 2
- **Issue:** `agent-brain-plugin/tests/` directory did not exist
- **Fix:** Created directory and test file from scratch; wrote 12 structural tests (inferred from research description "11 regression tests covering wizard steps 2-7") plus the 3 new tests specified in the plan. Result: 15 total (plan expected 14 = 11 existing + 3 new)
- **Files modified:** agent-brain-plugin/tests/test_plugin_wizard_spec.py (created)
- **Commit:** dd8bcae

## Self-Check: PASSED

- [x] agent-brain-plugin/commands/agent-brain-setup.md — modified (contains tsvector, GraphRAG requires ChromaDB, auto-enabled)
- [x] agent-brain-plugin/tests/test_plugin_wizard_spec.py — created (15 tests, all pass)
- [x] cfccde5 commit exists
- [x] dd8bcae commit exists
