---
phase: 61-python-framework-adapter-matrix
plan: 04
subsystem: testing
tags: [pytest, mcp, framework-matrix, pydantic-ai, autogen, mcpserverstdio, mcpworkbench, stdio]

# Dependency graph
requires:
  - phase: 61-01
    provides: "framework-matrix harness skeleton: seeded_mcp_server, _harness.py, bootstrap_venv.sh"
provides:
  - "framework-matrix/pydantic-ai/ — FRAME-04 Pydantic AI MCPServerStdio smoke test"
  - "framework-matrix/autogen/ — FRAME-05 Autogen McpWorkbench smoke test"
  - "Both tests keyless, <30s, orphan-free, exact-pinned (==)"
affects:
  - phase-62 (TypeScript framework matrix, similar per-framework isolation pattern)

# Tech tracking
tech-stack:
  added:
    - "pydantic-ai==1.107.0 (ships pydantic_ai.mcp.MCPServerStdio)"
    - "autogen-ext[mcp]==0.7.5 + autogen-core==0.7.5 (ships autogen_ext.tools.mcp.McpWorkbench + StdioServerParams)"
  patterns:
    - "Per-framework isolated venv with exact == pins (established in Plan 61-01)"
    - "TDD RED/GREEN per task: failing test committed first, then implementation artifacts"
    - "sys.path.insert to resolve _harness from sibling framework-matrix/ root (no cross-package import)"

key-files:
  created:
    - "framework-matrix/pydantic-ai/requirements.txt"
    - "framework-matrix/pydantic-ai/test_pydantic_ai_smoke.py"
    - "framework-matrix/pydantic-ai/README.md"
    - "framework-matrix/autogen/requirements.txt"
    - "framework-matrix/autogen/test_autogen_smoke.py"
    - "framework-matrix/autogen/README.md"
  modified: []

key-decisions:
  - "pydantic-ai MCPServerStdio is deprecated as of v1.x (migration path: MCPToolset with StdioTransport) but still exists and ships in pydantic-ai==1.107.0; the plan specifically required MCPServerStdio so we use it with the async-with context manager pattern"
  - "McpWorkbench ships in autogen-ext[mcp] (Microsoft fork) NOT in ag2-agentchat or pyautogen; autogen-core==0.7.5 is required as a transitive dep for Component/Workbench base classes"
  - "Both tests use sys.path.insert(0, parent_dir) to import _harness without a package root — consistent with Plan 61-01's no-cross-package-import decision"
  - "pytest-asyncio==0.26.0 pinned in both requirements files to support @pytest.mark.asyncio"
  - "mcp==1.9.4 pinned explicitly in both files as transitive dep to prevent drift"

requirements-completed: [FRAME-04, FRAME-05]

# Metrics
duration: 4min
completed: 2026-06-11
---

# Phase 61 Plan 04: Pydantic AI + Autogen/AG2 Framework Adapters Summary

**Pydantic AI MCPServerStdio (FRAME-04) and Autogen McpWorkbench (FRAME-05) exact-pinned stdio smoke tests against the seeded corpus harness**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-06-11T21:47:28Z
- **Completed:** 2026-06-11T21:51:28Z
- **Tasks:** 2 (both TDD RED + GREEN)
- **Files modified:** 6 created, 0 modified

## Accomplishments

- Created `framework-matrix/pydantic-ai/` with requirements.txt (pydantic-ai==1.107.0, mcp==1.9.4, exact pins), test_pydantic_ai_smoke.py (76 lines, framework-marked, MCPServerStdio async-with pattern), and README.md
- Created `framework-matrix/autogen/` with requirements.txt (autogen-ext[mcp]==0.7.5, autogen-core==0.7.5, exact pins with AG2 fork distribution note), test_autogen_smoke.py (85 lines, framework-marked, McpWorkbench async-with pattern), and README.md
- Both tests import `seeded_mcp_server`, `stdio_server_params`, `SMOKE_TOOL/ARGS`, and `assert_non_empty_search` from `_harness.py` via `sys.path.insert` (consistent with no-cross-package-import decision from Plan 61-01)
- `task before-push` passes unchanged: 544 passed, 111 deselected, 7 warnings — framework tests not collected

## Task Commits

1. **Task 1 RED: Pydantic AI MCPServerStdio test** - `b7fae2a` (test)
2. **Task 1 GREEN: Pydantic AI requirements.txt + README** - `4ca01f6` (feat)
3. **Task 2 RED: Autogen McpWorkbench test** - `192fa4f` (test)
4. **Task 2 GREEN: Autogen requirements.txt + README** - `7f754ed` (feat)

## Files Created/Modified

- `framework-matrix/pydantic-ai/requirements.txt` — pydantic-ai==1.107.0 + mcp==1.9.4 + anyio==4.9.0 + pytest-asyncio==0.26.0, all exact-pinned with source URL + pinned date comments
- `framework-matrix/pydantic-ai/test_pydantic_ai_smoke.py` — 76 lines, pytestmark=framework, MCPServerStdio async-with connect->list_tools->call_tool->assert_non_empty_search
- `framework-matrix/pydantic-ai/README.md` — FRAME-04, bootstrap + run commands
- `framework-matrix/autogen/requirements.txt` — autogen-ext[mcp]==0.7.5 + autogen-core==0.7.5 + mcp==1.9.4 + anyio==4.9.0 + pytest-asyncio==0.26.0, all exact-pinned with distribution fork note
- `framework-matrix/autogen/test_autogen_smoke.py` — 85 lines, pytestmark=framework, McpWorkbench/StdioServerParams async-with connect->list_tools->call_tool->assert_non_empty_search
- `framework-matrix/autogen/README.md` — FRAME-05, distribution note (Microsoft fork != AG2), bootstrap + run commands

## Decisions Made

- **MCPServerStdio deprecation acknowledged:** pydantic-ai v1.107.0 marks `MCPServerStdio` as deprecated (migration path is `MCPToolset` + `StdioTransport` in v2). Since the plan explicitly requires `MCPServerStdio`, we use the async-with context manager pattern which still ships in 1.107.0.
- **autogen-ext is Microsoft's fork:** The `McpWorkbench` class lives in `autogen-ext[mcp]` (Microsoft AutoGen) — NOT in `ag2-agentchat` or `pyautogen` (AG2 fork). The README documents this distinction explicitly.
- **autogen-core required:** `autogen-ext` 0.7.5 requires `autogen-core` for `Component` and `Workbench` base class resolution. Pinned at 0.7.5 to match.
- **sys.path.insert approach:** Both tests insert `parent_dir` (framework-matrix/) into sys.path at the top of the file to import `_harness` without a package root — mirrors the approach the plan specified and is consistent with Plan 61-01's no-cross-package-import decision.

## Deviations from Plan

None — plan executed exactly as written. `MCPServerStdio` deprecation is noted as an informational finding (not a deviation — the class still ships and works in pydantic-ai==1.107.0).

## Issues Encountered

None. Both test files parse cleanly, all automated verification checks pass, `task before-push` exits 0 with framework tests not collected.

## User Setup Required

None — no external service configuration required. Both tests skip gracefully when `OPENAI_API_KEY` or required binaries are missing (via `seeded_mcp_server` fixture from conftest.py).

## Next Phase Readiness

- All 5 framework adapters (FRAME-01 through FRAME-05) now have their test files and requirements defined
- Plan 61-02 (openai-agents) and Plan 61-03 (langchain/llama-index) still need their test files — those were not in scope for this plan (61-04 covers Pydantic AI + Autogen)
- Phase 62 (TypeScript framework matrix) can follow the same per-framework isolated venv + exact-pin pattern

---
*Phase: 61-python-framework-adapter-matrix*
*Completed: 2026-06-11*
