---
phase: 39-plugin-and-setup-wizard-ux
plan: "02"
subsystem: cli
tags: [wizard, graphrag, langextract, ports, plugin, tests]

requires:
  - phase: 39-plugin-and-setup-wizard-ux
    provides: setup assistant policy-island and script-first setup flow from 39-01
provides:
  - Wizard Step 7 first-class AST+LangExtract GraphRAG mode
  - Wizard Step 12 available API port discovery in 8000-8300
  - Config persistence for graphrag extraction mode and discovered API port
  - Regression tests for CLI and plugin wizard contract alignment
affects: [agent-brain-cli, agent-brain-plugin, setup-wizard-ux]

tech-stack:
  added: []
  patterns: [click wizard staged prompts, socket-based port probing, markdown spec regression tests]

key-files:
  created: []
  modified:
    - agent-brain-cli/agent_brain_cli/commands/config.py
    - agent-brain-cli/tests/commands/test_config_wizard.py
    - agent-brain-plugin/commands/agent-brain-config.md
    - agent-brain-plugin/tests/test_plugin_wizard_spec.py

key-decisions:
  - "Expose AST for code + LangExtract for docs as a top-level GraphRAG wizard option instead of a buried extractor sub-question."
  - "Scan 8000-8300 and suggest the first free API port to reduce project-to-project port collisions."

patterns-established:
  - "Wizard tests monkeypatch port-discovery helpers for deterministic assertions."
  - "Plugin command markdown explicitly mirrors CLI prompt labels for contract consistency."

requirements-completed: []

duration: 5 min
completed: 2026-03-20
---

# Phase 39 Plan 02: Plugin and Setup Wizard UX Summary

**The config wizard now offers a first-class mixed GraphRAG mode (AST for code + LangExtract for docs) and auto-discovers a free API port in 8000-8300, with CLI behavior and plugin spec tests kept in sync.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-20T01:48:37Z
- **Completed:** 2026-03-20T01:53:52Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added RED tests for GraphRAG mixed extraction persistence and available API port suggestion behavior.
- Implemented wizard GraphRAG mode selection, 8000-8300 port discovery, deployment prompts, and persisted `graphrag` + `api` config blocks.
- Updated plugin `agent-brain-config` Step 7 and Step 12 contract text to match implemented CLI prompt semantics.
- Verified both CLI and plugin regression suites pass with new behavior.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add failing tests for mixed GraphRAG mode and automatic API port suggestion** - `ffb9808` (test)
2. **Task 2 (GREEN): Implement wizard extraction mode and auto-port discovery behavior** - `7be263b` (feat)
3. **Task 3: Update plugin wizard spec text for Step 7 and Step 12** - `c83cbbb` (docs)

**Plan metadata:** pending final docs commit

## Files Created/Modified
- `agent-brain-cli/agent_brain_cli/commands/config.py` - Added GraphRAG mode prompts, mixed-mode persistence, and socket-based API port discovery.
- `agent-brain-cli/tests/commands/test_config_wizard.py` - Added RED/GREEN coverage for mixed GraphRAG persistence and available-port defaults; updated existing flows for new prompts.
- `agent-brain-plugin/commands/agent-brain-config.md` - Rewrote Step 7/12 guidance to include first-class AST+LangExtract and 8000-8300 API port auto-discovery.
- `agent-brain-plugin/tests/test_plugin_wizard_spec.py` - Added assertions covering Step 7 mixed mode wording and Step 12 auto-port text.

## Decisions Made
- Keep mixed extraction (`use_code_metadata: true` + `doc_extractor: langextract`) as a primary Step 7 choice for discoverability in mixed code/doc repositories.
- Use deterministic first-available port scanning across 8000-8300 for wizard defaults to avoid collisions without adding random behavior.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 39 plan set is now functionally complete (39-01 and 39-02 implemented).
- Ready for phase wrap-up or next milestone planning.

## Self-Check: PASSED
- FOUND: `.planning/phases/39-plugin-and-setup-wizard-ux/39-02-SUMMARY.md`
- FOUND: `ffb9808`
- FOUND: `7be263b`
- FOUND: `c83cbbb`
