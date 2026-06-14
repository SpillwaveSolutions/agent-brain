---
phase: 61-python-framework-adapter-matrix
plan: 01
subsystem: testing
tags: [pytest, mcp, framework-matrix, psutil, agent-brain-mcp, subprocess, harness]

# Dependency graph
requires:
  - phase: 60-subprocess-hygiene-1000-invocation-orphan-test
    provides: "SIGTERM->SIGKILL close() escalation + psutil children-delta orphan pattern"
  - phase: 59-mcp-cli-resources-prompts
    provides: "agent-brain-mcp --transport http binary + /healthz readiness + /mcp mount path"
provides:
  - "framework-matrix/ top-level directory with full harness skeleton"
  - "seeded_mcp_server session fixture (ONE real agent-brain-serve + indexed FRAMEWORK_CORPUS)"
  - "http_mcp_listener function fixture (real agent-brain-mcp --transport http, SIGTERM teardown)"
  - "FRAMEWORK_CORPUS tiny 4-file corpus guaranteeing authenticate token search hits"
  - "SMOKE_QUERY/TOOL/ARGS canonical connect->call->assert inputs"
  - "stdio_server_params(state_dir) tuple builder for per-framework stdio launch"
  - "assert_non_empty_search normalizing 5 framework result shapes"
  - "assert_no_orphans psutil children-delta assertion"
  - "framework pytest marker opt-in (not in before-push)"
  - "bootstrap_venv.sh per-framework venv creator with pin-freshness check"
affects:
  - 61-02 (openai-agents framework test)
  - 61-03 (langchain + llama-index + pydantic-ai tests)
  - 61-04 (autogen test)
  - 62-xx (TypeScript framework matrix, similar harness pattern)

# Tech tracking
tech-stack:
  added:
    - "framework-matrix/ directory (new top-level, not a Python package)"
    - "pytest.ini with asyncio_mode=auto + framework marker"
    - "bootstrap_venv.sh POSIX sh venv creator"
  patterns:
    - "Per-framework isolated venv with exact pins (no shared requirements.txt)"
    - "Opt-in pytest marker (mirrors stress marker precedent from Phase 60)"
    - "Inlined seeding logic (no cross-package import; framework-matrix has no package root)"
    - "SIGTERM->wait(grace)->SIGKILL teardown for all subprocess fixtures (Phase 60 contract)"
    - "psutil children-delta orphan guard at session scope (autouse)"

key-files:
  created:
    - "framework-matrix/README.md"
    - "framework-matrix/bootstrap_venv.sh"
    - "framework-matrix/pytest.ini"
    - "framework-matrix/_harness.py"
    - "framework-matrix/conftest.py"
  modified: []

key-decisions:
  - "Seeding logic inlined in conftest.py (not imported from agent-brain-cli/tests/integration/_corpus.py) because framework-matrix has no package root and must not create cross-package imports"
  - "http_mcp_listener uses SIGTERM->wait->SIGKILL (NOT SIGINT) per Phase 60 contract"
  - "framework pytest marker addopts=-m framework makes bare pytest framework-matrix/ only run framework-marked tests (NOT collected by task before-push)"
  - "assert_non_empty_search tolerates extraction failures on non-None envelopes (counts as >=1) to avoid raising wrong errors when shape detection fails"
  - "psutil orphan guard degrades gracefully when psutil is unavailable (framework venvs may not have it pre-installed)"

patterns-established:
  - "Opt-in heavy test suite: pytest marker + no testpaths reference in any package pyproject (mirrors Phase 60 stress marker)"
  - "5-shape result normalization: MCP SDK CallToolResult -> LangChain ToolMessage -> LlamaIndex ToolOutput -> Pydantic AI list -> Autogen ToolResult"
  - "Short AF_UNIX-safe temp dir via tempfile.mkdtemp(prefix='abfwm-') for seeded server state"

requirements-completed: [FRAME-01]

# Metrics
duration: 35min
completed: 2026-06-11
---

# Phase 61 Plan 01: Framework Matrix Foundation Summary

**Session-scoped real-server harness with 5-shape search helper, SIGTERM teardown HTTP fixture, opt-in framework marker, and pin-enforcing venv bootstrap for the Phase 61 adapter matrix**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-06-11T21:35:00Z
- **Completed:** 2026-06-11T22:10:00Z
- **Tasks:** 3 (Task 3 was TDD)
- **Files modified:** 5 created, 0 modified

## Accomplishments

- Created `framework-matrix/` top-level directory with all 5 planned files
- `_harness.py`: tiny FRAMEWORK_CORPUS (4 files, `authenticate` token), `SMOKE_QUERY/TOOL/ARGS` canonical inputs, `stdio_server_params` tuple builder, `assert_non_empty_search` (normalizes all 5 framework result shapes), `assert_no_orphans` with psutil children-delta pattern from Phase 60
- `conftest.py`: session-scoped `seeded_mcp_server` (mirrors `_corpus.py:start_seeded_server` exactly, inlined), function-scoped `http_mcp_listener` factory (real `agent-brain-mcp --transport http` binary, `/healthz` readiness, SIGTERM teardown), `pytest_collection_modifyitems` auto-marker, session-scoped autouse `_orphan_guard`
- `pytest.ini`: `framework:` marker registered with `before-push` documentation, `addopts = -m framework`; verified absent from all 4 package pyprojects and root Taskfile
- `bootstrap_venv.sh`: POSIX sh, `cd` to repo root via `git rev-parse --show-toplevel`, creates `.venv`, installs pinned requirements + local agent-brain packages, enforces exact pins via re-install no-op check (exits 3 on drift)
- `task before-push` passes unchanged: 544 passed, 111 deselected, 7 warnings — framework tests not collected

## Task Commits

1. **Task 1: Layout + README + bootstrap script** - `0328792` (feat)
2. **Task 2: pytest marker + pytest.ini** - `313089c` (chore)
3. **Task 3 RED: _harness.py helper contract** - `776ae66` (test)
4. **Task 3 GREEN: conftest.py harness fixtures** - `4d15d7e` (feat)

## Files Created/Modified

- `framework-matrix/README.md` - Phase 61/62 matrix overview, opt-in contract, 5 framework subdir table, bootstrap usage
- `framework-matrix/bootstrap_venv.sh` - Per-framework venv creator with pin-freshness check (exit 3 on drift)
- `framework-matrix/pytest.ini` - framework marker + asyncio_mode=auto + addopts=-m framework
- `framework-matrix/_harness.py` - FRAMEWORK_CORPUS, SMOKE_QUERY/TOOL/ARGS, stdio_server_params, assert_non_empty_search (5-shape), assert_no_orphans
- `framework-matrix/conftest.py` - seeded_mcp_server, http_mcp_listener, pytest_collection_modifyitems, _orphan_guard

## Decisions Made

- **Seeding logic inlined:** `conftest.py` inlines `prerequisites_available`, `_find_free_port`, `_poll_health`, `start_seeded_server` from `_corpus.py` rather than importing. `framework-matrix/` has no package root so cross-package imports would break in any venv that doesn't have `agent-brain-cli` installed. The docstring references the canonical source for auditing but does not import it.
- **SIGTERM-only teardown:** `http_mcp_listener` uses `SIGTERM -> wait(_HTTP_LISTENER_GRACE_S=5s) -> SIGKILL`. `SIGINT` is documented as intentionally NOT used (Phase 60 contract). The word `SIGINT` appears only in warning comments.
- **Tolerant shape normalization:** `assert_non_empty_search` catches extraction exceptions on non-None envelopes and treats them as count>=1 to avoid masking real 0-result failures with shape-sniffing errors.
- **psutil graceful degradation:** `_children_pids` returns an empty set when psutil is unavailable; `assert_no_orphans` skips the check. Per-framework venvs may not have psutil pre-installed.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. `task before-push` passed on first attempt (544 passed, framework tests not collected).

## User Setup Required

None — no external service configuration required. The harness skips gracefully when `OPENAI_API_KEY` or required binaries are missing.

## Next Phase Readiness

- All 5 per-framework plans (61-02 through 61-04) can now `from _harness import ...` and use `seeded_mcp_server` / `http_mcp_listener` / `stdio_server_params` / `assert_non_empty_search` without re-deriving any server-spawn logic
- Running `pytest framework-matrix/` with no per-framework tests yet collects 0 tests without error (skeleton is import-clean)
- `task before-push` exits 0 with framework tests uncollected — zero regression risk from this plan

---
*Phase: 61-python-framework-adapter-matrix*
*Completed: 2026-06-11*
