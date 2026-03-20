---
phase: 39-plugin-and-setup-wizard-ux
plan: "01"
subsystem: plugin
tags: [permissions, setup-wizard, policy-island, scripts, tdd]

requires:
  - phase: 38-server-reliability-provider-fixes
    provides: Stable setup wizard foundation and prior setup-check script flow
provides:
  - Scoped setup-assistant tool permissions for script execution and config writes
  - Policy-island command routing for setup/config/install/init/start/verify commands
  - Script-backed PyPI version and uv availability helper scripts used by install flow
affects: [agent-brain-plugin, setup-ux, install-flow]

tech-stack:
  added: [bash helper scripts]
  patterns: [agent-scoped permissions, script-first command wiring, TDD red-green]

key-files:
  created:
    - agent-brain-plugin/scripts/ab-pypi-version.sh
    - agent-brain-plugin/scripts/ab-uv-check.sh
    - agent-brain-plugin/tests/test_setup_permissions_spec.py
  modified:
    - agent-brain-plugin/agents/setup-assistant.md
    - agent-brain-plugin/commands/agent-brain-config.md
    - agent-brain-plugin/commands/agent-brain-install.md
    - agent-brain-plugin/commands/agent-brain-setup.md
    - agent-brain-plugin/commands/agent-brain-init.md
    - agent-brain-plugin/commands/agent-brain-start.md
    - agent-brain-plugin/commands/agent-brain-verify.md

key-decisions:
  - "Use context: fork + agent: setup-assistant on setup-flow commands to centralize permissions in a policy island."
  - "Replace high-churn inline install checks with executable helper scripts to reduce approval prompts and improve maintainability."

patterns-established:
  - "Path-scoped Bash permissions for plugin scripts instead of broad shell approvals"
  - "Setup/install command docs prefer script entry points over inline shell pipelines"

requirements-completed: []

duration: 4 min
completed: 2026-03-20
---

# Phase 39 Plan 01: Setup Assistant Policy-Island and Scripted Checks Summary

**Setup flows now run through a single setup-assistant policy island with scoped permissions, while install/config checks use script-backed helpers to avoid repeated runtime approval prompts.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-20T01:40:40Z
- **Completed:** 2026-03-20T01:44:59Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Added `allowed_tools` to `setup-assistant` with scoped `Bash(...)`, `Write(...)`, and `Edit(...)` rules for supported script/config paths.
- Bound all six setup-flow commands to `context: fork` + `agent: setup-assistant` so setup operations share one permission island.
- Replaced config/install inline shell fragments with direct script calls and added canonical helper scripts for PyPI version and uv checks.
- Added and extended regression tests to enforce policy-island bindings, script references, and executable helper scripts.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add setup-assistant policy-island permissions and bind setup commands to the agent** - `2670300` (feat)
2. **Task 2 (RED): Replace inline install/config shell fragments with script-backed calls** - `38c95cf` (test)
3. **Task 2 (GREEN): Replace inline install/config shell fragments with script-backed calls** - `c212ab2` (feat)

_Note: TDD task produced RED and GREEN commits._

## Files Created/Modified
- `agent-brain-plugin/agents/setup-assistant.md` - Added scoped `allowed_tools` policy block.
- `agent-brain-plugin/commands/agent-brain-config.md` - Switched setup-check invocation to direct script execution.
- `agent-brain-plugin/commands/agent-brain-install.md` - Routed version and uv checks through helper scripts.
- `agent-brain-plugin/commands/agent-brain-setup.md` - Bound command to setup-assistant policy island.
- `agent-brain-plugin/commands/agent-brain-init.md` - Bound command to setup-assistant policy island.
- `agent-brain-plugin/commands/agent-brain-start.md` - Bound command to setup-assistant policy island.
- `agent-brain-plugin/commands/agent-brain-verify.md` - Bound command to setup-assistant policy island.
- `agent-brain-plugin/scripts/ab-pypi-version.sh` - New PyPI latest-version resolver.
- `agent-brain-plugin/scripts/ab-uv-check.sh` - New uv availability checker with install hint.
- `agent-brain-plugin/tests/test_setup_permissions_spec.py` - Regression coverage for permissions and script-first wiring.

## Decisions Made
- Use path-scoped script execution permissions in the setup assistant instead of broad shell command allowances.
- Standardize setup-flow command routing through the setup assistant with frontmatter-level policy binding.
- Keep helper scripts single-responsibility so command docs stay readable and permission scopes remain predictable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created missing setup permissions regression spec file**
- **Found during:** Task 1
- **Issue:** `agent-brain-plugin/tests/test_setup_permissions_spec.py` did not exist, so task verification target could not run.
- **Fix:** Added baseline regression tests for setup-assistant permissions and command policy bindings.
- **Files modified:** `agent-brain-plugin/tests/test_setup_permissions_spec.py`
- **Verification:** `python3 -m pytest agent-brain-plugin/tests/test_setup_permissions_spec.py -q`
- **Committed in:** `2670300`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required to make planned verification executable; no scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 39-01 is complete with passing setup permission and script-wiring regressions.
- Ready for `39-02-PLAN.md` (GraphRAG extraction option + auto port discovery wizard updates).

## Self-Check: PASSED
- FOUND: `.planning/phases/39-plugin-and-setup-wizard-ux/39-01-SUMMARY.md`
- FOUND: `agent-brain-plugin/scripts/ab-pypi-version.sh`
- FOUND: `agent-brain-plugin/scripts/ab-uv-check.sh`
- FOUND: `agent-brain-plugin/tests/test_setup_permissions_spec.py`
- FOUND commit: `2670300`
- FOUND commit: `38c95cf`
- FOUND commit: `c212ab2`
