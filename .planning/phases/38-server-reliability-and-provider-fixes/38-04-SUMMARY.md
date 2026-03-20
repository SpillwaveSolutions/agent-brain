---
phase: 38-server-reliability-and-provider-fixes
plan: 04
subsystem: cli
tags: [cli, config, wizard, ollama, click, yaml]

requires:
  - phase: 38-server-reliability-and-provider-fixes
    provides: Ollama batch and delay configuration decisions from 38-CONTEXT.md
provides:
  - Interactive `agent-brain config wizard` command
  - Ollama-only prompts for `batch_size` and `request_delay_ms`
  - Integration coverage for prompt flow and validation behavior
affects: [phase-39-plugin-setup-wizard-ux, cli-configuration]

tech-stack:
  added: []
  patterns: [click prompt flow, provider-specific defaults, YAML config generation]

key-files:
  created:
    - agent-brain-cli/tests/commands/__init__.py
    - agent-brain-cli/tests/commands/test_config_wizard.py
  modified:
    - agent-brain-cli/agent_brain_cli/commands/config.py

key-decisions:
  - "Expose batch_size and request_delay_ms prompts only when embedding provider is ollama."
  - "Do not expose max_retries in wizard; leave advanced retry tuning to manual YAML edits."

patterns-established:
  - "Wizard writes to nearest .agent-brain/config.yaml discovered by walking up from CWD."
  - "Input validation uses Click Choice and IntRange for immediate re-prompt behavior."

requirements-completed: []

duration: 2 min
completed: 2026-03-20
---

# Phase 38 Plan 04: Config Wizard Summary

**Added an interactive `agent-brain config wizard` that captures provider settings and Ollama batch/delay tuning, then writes `.agent-brain/config.yaml` with validated values.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-19T19:58:41-05:00
- **Completed:** 2026-03-20T01:01:23Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `config wizard` sub-command to the existing `config` command group.
- Implemented provider-aware wizard prompts with Ollama-only `batch_size` and `request_delay_ms` inputs.
- Added four integration tests covering Ollama prompts, skip behavior for OpenAI/Cohere, and invalid input rejection.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement config wizard sub-command** - `1d22b04` (feat)
2. **Task 2 (RED): Write failing integration tests** - `719705a` (test)
3. **Task 2 (GREEN): Stabilize validation assertions** - `e51266b` (test)

**Plan metadata:** pending final docs commit

## Files Created/Modified
- `agent-brain-cli/agent_brain_cli/commands/config.py` - Added wizard command, prompt flow, YAML output path resolution, and config writing.
- `agent-brain-cli/tests/commands/test_config_wizard.py` - Added integration tests for wizard behavior and input validation.
- `agent-brain-cli/tests/commands/__init__.py` - Added commands test package marker.

## Decisions Made
- Used provider-specific default model maps in the wizard to keep prompts concise and predictable.
- Reused Click-native validation (`Choice`, `IntRange`) for invalid input handling instead of custom parsing logic.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Click emits provider validation errors as "is not one of" and IntRange errors as "x>=0"; test assertions were updated to match current Click output.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan deliverables are complete and verified for 38-04.
- Remaining Phase 38 plans can proceed independently.

---
*Phase: 38-server-reliability-and-provider-fixes*
*Completed: 2026-03-20*

## Self-Check: PASSED

- Verified `38-04-SUMMARY.md` exists on disk.
- Verified task commit hashes `1d22b04`, `719705a`, and `e51266b` exist in git history.
