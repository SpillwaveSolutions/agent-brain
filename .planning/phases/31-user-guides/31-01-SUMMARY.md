---
phase: 31-user-guides
plan: 01
subsystem: documentation
tags: [user-guide, quick-start, folder-management, file-type-presets, content-injection, chunk-eviction, file-watcher, embedding-cache, multi-runtime]

# Dependency graph
requires:
  - phase: 30-configuration-documentation
    provides: "Validated configuration docs that user guides reference"
provides:
  - "Updated USER_GUIDE.md with all v7-v9 features documented"
  - "Updated QUICK_START.md with file type presets, folder management, and multi-runtime install"
affects: [32-plugin-documentation, 33-cross-references-metadata]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - docs/USER_GUIDE.md
    - docs/QUICK_START.md

key-decisions:
  - "Added Index Management Commands as a separate table section rather than merging into Server Commands"
  - "Placed new feature sections (folders, presets, injection, eviction, watcher, cache) between Indexing and Job Queue for logical flow"
  - "Added multi-runtime install section in QUICK_START before All-in-One Setup to increase visibility"

patterns-established:
  - "Documentation sections mirror source code service names for traceability"

requirements-completed: [GUIDE-01, GUIDE-02]

# Metrics
duration: 8min
completed: 2026-03-17
---

# Phase 31 Plan 01: User Guides Summary

**Updated USER_GUIDE.md with 6 new feature sections (folders, presets, injection, eviction, watcher, cache) and QUICK_START.md with file type presets, folder management, and multi-runtime install**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-17T02:04:25Z
- **Completed:** 2026-03-17T02:12:20Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Updated command count from 24 to 30 across both guides
- Added 6 dedicated sections to USER_GUIDE.md for v7-v9 features: Folder Management, File Type Presets, Content Injection, Chunk Eviction, File Watcher, Embedding Cache
- Added Index Management Commands table with folders, inject, types, cache commands
- Added install-agent to Setup Commands table
- Updated QUICK_START.md with file type preset and folder management examples in Step 6
- Added "Install for Other AI Runtimes" section to QUICK_START.md

## Task Commits

Each task was committed atomically:

1. **Task 1: Update USER_GUIDE.md with v7-v9 features** - `6e5dc6a` (docs)
2. **Task 2: Update QUICK_START.md with current installation and features** - `5ccc896` (docs)

## Files Created/Modified
- `docs/USER_GUIDE.md` - Added 6 new sections, updated command tables and counts, expanded CLI reference
- `docs/QUICK_START.md` - Added file type preset examples, folder management, multi-runtime install section

## Decisions Made
- Added Index Management Commands as a separate table section in Plugin Commands rather than merging into Server Commands, keeping the tables focused
- Placed new feature sections between Indexing and Job Queue for logical reading flow (index -> manage folders -> filter types -> inject metadata -> evict stale -> watch changes -> cache embeddings -> job queue)
- Added multi-runtime install section before All-in-One Setup in QUICK_START to increase visibility without disrupting the main flow

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- USER_GUIDE.md and QUICK_START.md are current with v7-v9 features
- Ready for plan 31-02 (PLUGIN_GUIDE.md, POSTGRESQL_SETUP.md, GRAPHRAG_GUIDE.md updates)
- All command references verified against the 30 plugin command files

## Self-Check: PASSED

- FOUND: docs/USER_GUIDE.md
- FOUND: docs/QUICK_START.md
- FOUND: .planning/phases/31-user-guides/31-01-SUMMARY.md
- FOUND: 6e5dc6a (Task 1 commit)
- FOUND: 5ccc896 (Task 2 commit)

---
*Phase: 31-user-guides*
*Completed: 2026-03-17*
