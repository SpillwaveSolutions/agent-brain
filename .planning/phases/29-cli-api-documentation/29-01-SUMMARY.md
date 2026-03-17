---
phase: 29-cli-api-documentation
plan: 01
subsystem: documentation
tags: [cli, help-output, user-guide, claude-md]

requires:
  - phase: 28-documentation-testing-archival
    provides: "v9.1 CLI with install-agent, codex, skill-runtime commands"
provides:
  - "Accurate CLI command tables in CLAUDE.md, .claude/CLAUDE.md, and USER_GUIDE.md"
  - "All 16 CLI subcommands documented in all three doc files"
  - "Correct .agent-brain/ directory paths replacing stale .claude/agent-brain/ references"
affects: [30-configuration-documentation, 31-user-guides, 33-cross-references-metadata]

tech-stack:
  added: []
  patterns: ["docs-as-code validation against --help output"]

key-files:
  created: []
  modified:
    - ".claude/CLAUDE.md"
    - "docs/USER_GUIDE.md"

key-decisions:
  - "CLAUDE.md root was already fixed by prior plan 30-01; only .claude/CLAUDE.md and USER_GUIDE.md needed updates"
  - "Config discovery order updated to reflect XDG-first priority from source code"

patterns-established:
  - "CLI doc audit: run agent-brain --help and all subcommand --help, compare against docs"

requirements-completed: [CLIDOC-01, CLIDOC-02, CLIDOC-04]

duration: 5min
completed: 2026-03-17
---

# Phase 29 Plan 01: CLI Command Documentation Audit Summary

**All 16 CLI subcommands documented across CLAUDE.md, .claude/CLAUDE.md, and USER_GUIDE.md with correct syntax, descriptions, and directory paths matching actual --help output**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-17T02:04:11Z
- **Completed:** 2026-03-17T02:09:23Z
- **Tasks:** 2
- **Files modified:** 2 (CLAUDE.md root was already correct)

## Accomplishments
- Captured --help output for all 16 CLI subcommands as source of truth
- Added complete CLI Commands section to .claude/CLAUDE.md (was entirely missing)
- Fixed 6 stale .claude/agent-brain/ path references to .agent-brain/ in USER_GUIDE.md
- Added 9 missing commands (folders, cache, types, config, inject, install-agent, uninstall) to USER_GUIDE.md CLI Reference section
- Fixed config discovery order to match source code XDG-first priority

## Task Commits

Each task was committed atomically:

1. **Task 1: Capture CLI source of truth and identify discrepancies** - (analysis only, no file changes)
2. **Task 2: Fix CLI documentation in all affected files** - `908aaad` (docs)

## Files Created/Modified
- `.claude/CLAUDE.md` - Added CLI Commands section with Project, Server, and Management command tables
- `docs/USER_GUIDE.md` - Fixed stale directory paths, added missing commands to CLI Reference

## Decisions Made
- CLAUDE.md (root) was already corrected by a prior commit (4e2084e from plan 30-01), so no changes needed there
- Updated config discovery order to match actual source code: .agent-brain/ first, then XDG (~/.config/agent-brain/), then legacy (~/.agent-brain/)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- CLAUDE.md root file had already been updated by a prior plan (30-01) with the same CLI command table changes, so edits were no-ops for that file. Only .claude/CLAUDE.md and USER_GUIDE.md needed updates.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CLI documentation is now accurate and consistent across all three files
- Ready for plan 29-02 (API endpoint documentation audit)
- Ready for phase 31 (User Guides) which depends on accurate CLI docs

---
*Phase: 29-cli-api-documentation*
*Completed: 2026-03-17*
