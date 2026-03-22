---
phase: 34-config-command-spec
plan: 01
subsystem: docs
tags: [config-wizard, plugin, markdown, agent-brain-config, spec-reconciliation]

# Dependency graph
requires:
  - phase: 39-wizard-and-platform
    provides: "GraphRAG 4-option wizard, port auto-discovery, Ollama batch tuning decisions"
provides:
  - "SPEC.md title corrected: 9-step -> 12-step wizard"
  - "SPEC.md Step 2 output keys table expanded to match ab-setup-check.sh actual output"
  - "SPEC.md Step 7 GraphRAG updated to 4-option combined approach matching command"
  - "SPEC.md Step 7 config keys updated: use_llm_extraction replaced by doc_extractor"
  - "SPEC.md Step 12 option 1 updated to mention port auto-discovery in 8000-8300 range"
  - "SPEC.md version section: Current spec version: v9.3.0 (Phase 34)"
  - "Command Purpose section expanded from 2 to 9 wizard areas"
  - "Command Step 4 Gemini option now has config.yaml snippet"
  - "Command Step 4 Ollama option documents EMBEDDING_BATCH_SIZE and OLLAMA_REQUEST_DELAY_MS"
affects: [phase-35, future-config-wizard-phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Spec-first contract: SPEC.md is source of truth, command file is implementation"
    - "GraphRAG extractor choice integrated into main question (not split sub-question)"
    - "Port auto-discovery for API port range 8000-8300"
    - "Ollama performance tuning documented at Step 4 (provider-specific)"

key-files:
  created:
    - ".planning/phases/34-config-command-spec/34-01-SUMMARY.md"
  modified:
    - ".planning/phases/34-config-command-spec/SPEC.md"
    - "agent-brain-plugin/commands/agent-brain-config.md"

key-decisions:
  - "12-step wizard is the correct count (SPEC title had stale 9-step reference)"
  - "GraphRAG extraction mode is integrated into the 4-option main question — no separate sub-question"
  - "doc_extractor key replaces use_llm_extraction in config YAML for GraphRAG options 2-4"
  - "Ollama EMBEDDING_BATCH_SIZE and OLLAMA_REQUEST_DELAY_MS documented at Step 4 only (not exposed for cloud providers)"
  - "SPEC.md Step 2 output keys must match ab-setup-check.sh actual JSON output exactly"

patterns-established:
  - "SPEC.md must be updated whenever agent-brain-config.md changes (drift = bug)"
  - "ab-setup-check.sh output keys are the canonical Step 2 state bag for all wizard steps"

requirements-completed: [SPEC-AUDIT-01, SPEC-FIX-01, SPEC-FIX-02]

# Metrics
duration: 20min
completed: 2026-03-20
---

# Phase 34 Plan 01: Config Command Spec Summary

**SPEC.md reconciled with 12-step wizard command — title fixed, Step 2 keys aligned to ab-setup-check.sh, GraphRAG updated to 4-option combined approach with doc_extractor config key**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-20T00:00:00Z
- **Completed:** 2026-03-20T00:20:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Fixed SPEC.md title from "9-step" to "12-step wizard behavior" — aligned with the body which already described 12 steps
- Expanded SPEC.md Step 2 output keys table to include all 12 fields actually emitted by ab-setup-check.sh (was only 5 keys)
- Updated SPEC.md Step 7 GraphRAG from 3-option + sub-question to 4-option combined structure matching the command implementation
- Fixed SPEC.md Step 7 config keys: replaced `use_llm_extraction` with `doc_extractor` to match actual YAML output
- Updated SPEC.md Step 12 option 1 to document port auto-discovery in 8000-8300 range
- Added "Current spec version: v9.3.0 (Phase 34)" to SPEC.md version section
- Expanded command Purpose section from 2 bullet points to 9 wizard areas covering all 12 steps
- Added Gemini config.yaml snippet to command Step 4 Option 3 (was env vars only)
- Added Ollama performance tuning (EMBEDDING_BATCH_SIZE, OLLAMA_REQUEST_DELAY_MS) to command Step 4 Option 1

## Task Commits

Each task was committed atomically:

1. **Task 1: Audit SPEC vs Command and fix SPEC.md title/discrepancies** - `1b095aa` (docs)
2. **Task 2: Fix command file drift to match updated SPEC** - `5975697` (docs)

## Files Created/Modified

- `.planning/phases/34-config-command-spec/SPEC.md` - Title fix, Step 2 keys expanded, Step 7 GraphRAG 4-option structure, Step 12 port discovery, version added
- `agent-brain-plugin/commands/agent-brain-config.md` - Purpose expanded, Gemini config.yaml added, Ollama batch tuning documented

## Decisions Made

- SPEC.md GraphRAG Step 7: Combined the 3-option enable question and separate extraction mode sub-question into a single 4-option question matching the command implementation. This is cleaner UX and avoids duplicate decision points.
- doc_extractor is the correct YAML key for GraphRAG document extraction mode (not use_llm_extraction which was the legacy key name)

## Deviations from Plan

None - plan executed exactly as written. All 8 SPEC.md fix points from the plan were evaluated; 6 had actual drift that was fixed, 2 were already aligned (error states table was complete, frontmatter already said "12-step").

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SPEC.md and agent-brain-config.md are fully reconciled with zero known drift
- Plan 02 in this phase can proceed (if exists)
- The config wizard spec is now at v9.3.0 and ready for use as a reference by any phase that modifies the wizard

---
*Phase: 34-config-command-spec*
*Completed: 2026-03-20*
