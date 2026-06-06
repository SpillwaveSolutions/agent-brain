---
phase: 56-design-doc-cli-backend-skeleton
plan: 03
subsystem: cli-backend-skeleton

tags: [mcp, v3, backend-client, mcp-stdio, mcp-http, skeleton, not-implemented-error, phase-57-prereq]

# Dependency graph
requires:
  - phase: 56-01
    provides: v3 design doc (locks backend class location §3.1, sync facade §3.2, MCP-tool mapping §2.3, NotImplementedError sentinel for reset() §4 risks)
  - phase: 56-02
    provides: BackendClient @runtime_checkable Protocol (15-method shape, structural conformance via isinstance)
provides:
  - "agent_brain_mcp.client.McpStdioBackend — BackendClient-conformant stdio backend skeleton; ctx-mgr + close() real; 12 endpoint methods raise NotImplementedError('Wired in Phase 57+')"
  - "agent_brain_mcp.client.McpHttpBackend — BackendClient-conformant HTTP backend skeleton; same shape; same sentinel"
  - "agent_brain_mcp.client.__all__ extended with McpStdioBackend, McpHttpBackend (alongside existing ApiClient)"
  - "Skeleton conformance test suite: 6 tests pinning isinstance + NotImplementedError sentinel + DocServeClient regression + ctx-mgr lifecycle"
  - "agent-brain-cli wired as dev-only path dep on agent-brain-mcp's pyproject (develop=false to avoid tests/ shadowing)"
affects: [Phase 57 (transport selector returns McpStdioBackend / McpHttpBackend instead of NotImplementedError-raising stubs; grep for "Wired in Phase 57+" identifies skeleton call sites), Phase 60 (subprocess hygiene replaces None defaults for cwd/env), Phase 63 (MIN_BACKEND_VERSION bump from 10.2.0 to 10.3.0 in lockstep with release pyproject pin), v10.4 (#188 OAuth wraps McpHttpBackend's streamablehttp_client call site)]

# Tech tracking
tech-stack:
  added: []  # skeleton-only — no new runtime libraries (Phase 57+ adds the MCP SDK client wiring)
  patterns:
    - "BackendClient Protocol structural conformance via @runtime_checkable (Plan 56-02 contract honored by both new backends + existing DocServeClient)"
    - "Sync facade with async-internal deferred to Phase 57 (skeleton method bodies raise NotImplementedError; the facade choice between Pattern A=asyncio.run-per-call and Pattern B=persistent _loop is a Phase 57 measurement decision per design doc §3.2)"
    - "TYPE_CHECKING-only forward imports of api_client dataclasses to avoid runtime cycle (HealthStatus, IndexingStatus, QueryResponse, FolderInfo, IndexResponse referenced but never imported at runtime)"
    - "Load-bearing NotImplementedError sentinel string ('Wired in Phase 57+') — Phase 57 transport selector tests grep for this constant to distinguish skeleton from real implementation"
    - "Dev-only path dep with develop=false — avoids develop=true's .pth-injection of the sibling package's tests/ directory shadowing the host package's own tests/ namespace"

key-files:
  created:
    - "agent-brain-mcp/tests/test_cli_backends_skeleton.py (75 lines, 6 conformance tests)"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/client.py (added McpStdioBackend, McpHttpBackend, _PHASE_57_NOT_WIRED constant, TYPE_CHECKING import block, __all__ export list — ApiClient unchanged)"
    - "agent-brain-mcp/pyproject.toml (added agent-brain-cli path dep to [tool.poetry.group.dev.dependencies] with develop=false)"
    - "agent-brain-mcp/poetry.lock (regenerated to include agent-brain-cli + transitive rich downgrade to ^13.9.0 to match CLI's pin)"

key-decisions:
  - "develop=false (NOT develop=true) on the agent-brain-cli path dep — develop=true drops a .pth file that puts ../agent-brain-cli on sys.path, which makes the CLI's tests/ directory shadow agent-brain-mcp's own tests/ package and breaks pytest collection (tests.conftest and tests.contract._tool_matrix both become unimportable). develop=false also matches the precedent in agent-brain-mcp/Taskfile.yml's install task which writes path deps for agent-brain-rag / agent-brain-uds with develop=false. This was the only deviation from the literal plan text and is documented inline in the pyproject comment."
  - "Single grouped commit for Plans 1+2+3 (not per-task) — mirrors Plan 56-01's commit-grouping pattern. The plan's Task 3 explicitly stages all four files (client.py + test + pyproject + poetry.lock) in one git add + git commit. Each task's verification step ran independently as it landed; the commit boundary is the plan boundary, which is the integration boundary for Phase 57 reviewers."
  - "Sentinel string `_PHASE_57_NOT_WIRED = \"Wired in Phase 57+\"` declared as module-level constant — referenced by both backend classes' 12 endpoint methods (24 raises total). Phase 57 transport selector tests grep for this literal string to confirm the skeleton-vs-implementation boundary."
  - "Forward type hints unquoted (e.g. `def health(self) -> HealthStatus:`) — the existing module-header `from __future__ import annotations` defers all annotations to strings at module level, so quoting is unnecessary and Black/Ruff prefer the unquoted form. Plan's sample used quoted strings (legacy compatibility); unquoted matches the existing client.py ApiClient style and passes mypy strict identically."
  - "__exit__ traceback parameter typed as TracebackType | None (matching existing ApiClient pattern at line 39), not the plan's suggested `object` — TracebackType is already imported at module top from `from types import TracebackType` and matches the ApiClient signature byte-for-byte."

requirements-completed: [CLI-MCP-01, CLI-MCP-02]

# Metrics
duration: ~15 min
completed: 2026-06-06
---

# Phase 56 Plan 03: McpStdioBackend + McpHttpBackend Skeletons Summary

**McpStdioBackend and McpHttpBackend land in `agent-brain-mcp/agent_brain_mcp/client.py` alongside the existing ApiClient — both structurally satisfy the BackendClient Protocol (`isinstance` returns True at runtime), all 12 endpoint methods on each new class raise `NotImplementedError("Wired in Phase 57+")`, ctx-mgr + `close()` are real (non-stub), ApiClient is unchanged, exactly ONE `from __future__ import annotations` line in the file, 6 conformance tests pass (including a DocServeClient regression pin proving Plan 02's contract is preserved), 474 total MCP tests pass (468 baseline + 6 new), `task before-push` exits 0 from monorepo root, single atomic commit `7f45466` delivered. CLI-MCP-01 + CLI-MCP-02 satisfied at the skeleton level per ROADMAP Phase 56 success criteria #5.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-06T21:51:28Z
- **Completed:** 2026-06-06T22:07:18Z
- **Tasks:** 3 (Task 1 dev-dep + lock, Task 2 backend skeletons, Task 3 tests + before-push)
- **Files modified:** 4 (1 created, 3 edited)
- **Tests added:** 6 (all pass on first GREEN)

## Accomplishments

- Filed `agent-brain-mcp/agent_brain_mcp/client.py` extensions: two new classes `McpStdioBackend` and `McpHttpBackend` plus the `_PHASE_57_NOT_WIRED` sentinel constant and an `__all__ = ["ApiClient", "McpStdioBackend", "McpHttpBackend"]` export list. `ApiClient` source unchanged (line-for-line identical to HEAD before the plan started).
- Each new class exposes the full 15-attribute BackendClient surface: `__enter__` / `__exit__` / `close` (REAL — close marks `_closed = True`) plus 12 endpoint methods (`health`, `status`, `query`, `index`, `list_folders`, `delete_folder`, `reset`, `list_jobs`, `get_job`, `cancel_job`, `cache_status`, `clear_cache`) all of which raise `NotImplementedError("Wired in Phase 57+")`.
- Runtime conformance verified: `isinstance(McpStdioBackend(command="dummy"), BackendClient) == True`, `isinstance(McpHttpBackend(url="http://127.0.0.1:9999/mcp"), BackendClient) == True`, `isinstance(DocServeClient(base_url="http://x"), BackendClient) == True` (regression-pin proves Plan 02's contract is preserved).
- Filed `agent-brain-mcp/tests/test_cli_backends_skeleton.py` (75 lines, 6 tests): two `isinstance` assertions (stdio + http), two `pytest.raises(NotImplementedError, match="Wired in Phase 57+")` pinning tests (stdio.query + http.query), one DocServeClient regression-pin, one ctx-mgr lifecycle smoke test.
- Updated `agent-brain-mcp/pyproject.toml`: added `agent-brain-cli = { path = "../agent-brain-cli", develop = false }` to `[tool.poetry.group.dev.dependencies]` with inline justification comment explaining why develop=false is mandatory (avoid CLI's `tests/` dir shadowing MCP's `tests/` via `.pth`).
- Regenerated `agent-brain-mcp/poetry.lock` to include `agent-brain-cli 10.2.1` + transitive `rich 13.9.4` downgrade (from 15.0.0 — matches CLI's `rich = "^13.9.0"` pin). Lock-drift guard (#174) auto-handled the bootstrap drift on `agent-brain-cli/poetry.lock` during `task before-push` (auto-reverted, no impact on commits).
- Quality gates green for both edited files at file level: `poetry run black --check agent_brain_mcp/client.py tests/test_cli_backends_skeleton.py`, `poetry run ruff check ...`, `poetry run mypy --strict ...` all exit 0.
- `task before-push` from monorepo root: exit 0 in 13.71s for MCP suite (474 tests passed, 91% coverage on agent-brain-mcp), full monorepo before-push includes server + cli + uds suites and final lock-drift check.
- Single atomic conventional commit `7f45466` delivered on main, touching exactly the four files Plan 03 scopes (`client.py`, `test_cli_backends_skeleton.py`, `pyproject.toml`, `poetry.lock`). Commit subject prefixed `feat(56-03)` per plan spec. NO push happened (orchestrator decides push timing).

## Task Commits

Single atomic plan-level commit per the plan's commit-grouping decision (mirrors Plan 56-01's pattern):

- **Plan 03 (combined Tasks 1+2+3):** `7f45466` — `feat(56-03): McpStdioBackend + McpHttpBackend skeletons (CLI-MCP-01, CLI-MCP-02)` — touches `agent-brain-mcp/agent_brain_mcp/client.py`, `agent-brain-mcp/tests/test_cli_backends_skeleton.py`, `agent-brain-mcp/pyproject.toml`, `agent-brain-mcp/poetry.lock`.

Task-level verification ran independently as each task landed (Task 1 verified via `poetry run python -c "from agent_brain_cli.client.protocol import BackendClient; print(BackendClient)"`; Task 2 verified via isinstance assertions + Black/Ruff/mypy on the updated client.py; Task 3 verified via the 6-test pytest run + Black/Ruff/mypy on the test file + `task before-push` exit 0). The commit boundary is the plan boundary, which is the Phase 57 integration boundary.

## Files Created/Modified

- **`agent-brain-mcp/agent_brain_mcp/client.py`** (modified) — Two new classes appended after the existing ApiClient (which is byte-for-byte unchanged):
  - `McpStdioBackend(command: str | list[str], *, cwd: str | None = None, env: dict[str, str] | None = None)` — stdio MCP subprocess backend. Constructor records configuration; `__enter__` returns self; `__exit__` calls `close()`; `close()` marks `_closed = True` (idempotent). All 12 endpoint methods raise `NotImplementedError(_PHASE_57_NOT_WIRED)`. Docstring cites design doc §3.2 (sync facade pattern deferred to Phase 57 measurement), §4.5 / Phase 60 (subprocess hygiene), and §2.3 (method ↔ MCP tool mapping).
  - `McpHttpBackend(url: str, *, timeout: float = 30.0)` — Streamable HTTP MCP backend. Same shape. Docstring cites design doc §1.3 (loopback only — public-bind auth deferred to v10.4 #188), §3.2 (sync facade), §2.3 (mapping).
  - `_PHASE_57_NOT_WIRED = "Wired in Phase 57+"` — module-level constant referenced by all 24 method bodies (12 methods × 2 classes).
  - `if TYPE_CHECKING:` block importing `FolderInfo`, `HealthStatus`, `IndexingStatus`, `IndexResponse`, `QueryResponse` from `agent_brain_cli.client.api_client` — these are used as return type hints; runtime never imports them, avoiding the runtime cycle.
  - `from typing import TYPE_CHECKING, Any` — single edit at the existing import site (`from typing import Any` extended; no separate import line added at the bottom).
  - `__all__: list[str] = ["ApiClient", "McpStdioBackend", "McpHttpBackend"]` — new export list at end of module.
  - The file contains EXACTLY ONE `from __future__ import annotations` line (verified: `grep -c "from __future__" agent_brain_mcp/client.py` returns 1).

- **`agent-brain-mcp/tests/test_cli_backends_skeleton.py`** (created, 75 lines) — 6 conformance tests:
  1. `test_mcp_stdio_backend_satisfies_backend_client_protocol` — `isinstance(McpStdioBackend(command="agent-brain-mcp"), BackendClient) is True`.
  2. `test_mcp_http_backend_satisfies_backend_client_protocol` — `isinstance(McpHttpBackend(url="http://127.0.0.1:9999/mcp"), BackendClient) is True`.
  3. `test_mcp_stdio_query_raises_phase_57_sentinel` — `pytest.raises(NotImplementedError, match="Wired in Phase 57+")` on `.query("anything")`.
  4. `test_mcp_http_query_raises_phase_57_sentinel` — same on the HTTP backend.
  5. `test_doc_serve_client_still_satisfies_backend_client_protocol` — regression-pin: `isinstance(DocServeClient(base_url="http://127.0.0.1:8000"), BackendClient) is True` after Plan 03 lands. Module docstring calls out the regression-pin's purpose.
  6. `test_context_manager_lifecycle_does_not_raise` — `with McpStdioBackend(...) as stdio: ...` and `with McpHttpBackend(...) as http: ...` both run cleanly (ctx-mgr methods are NOT stubs).

- **`agent-brain-mcp/pyproject.toml`** (modified) — added to `[tool.poetry.group.dev.dependencies]`:
  ```toml
  agent-brain-cli = { path = "../agent-brain-cli", develop = false }
  ```
  Inline comment block (10 lines) explains the develop=false choice + cites the Taskfile.yml precedent for path deps. NOT added to the main `[tool.poetry.dependencies]` block (verified: `awk` extraction of the main-deps block contains zero matches for `agent-brain-cli`).

- **`agent-brain-mcp/poetry.lock`** (modified, +258 / -239 lines) — added `agent-brain-cli 10.2.1` (path-source, NOT develop), updated `agent-brain-rag` and `agent-brain-uds` from `10.1.2 → 10.2.1` (pre-existing #174 monorepo-bootstrap drift; lockstep with the PyPI version of agent-brain-server and agent-brain-uds — both already on `^10.2.1` in pyproject), downgraded `rich 15.0.0 → 13.9.4` (agent-brain-cli pins `rich = "^13.9.0"`; the dep resolver chose 13.9.4 as the highest compatible version across the path-installed CLI + the MCP package's own transitives).

## Decisions Made

- **`develop=false` on the agent-brain-cli path dep** (CRITICAL — this is the only deviation from the plan's literal text). The plan instructed `agent-brain-cli = { path = "../agent-brain-cli", develop = true }`. With `develop=true`, Poetry drops a `.pth` file in the MCP venv's `site-packages/` that adds `../agent-brain-cli` to sys.path. That `.pth` file makes the CLI's `tests/` directory (which contains a `__init__.py`) importable as a top-level `tests` package — which SHADOWS the MCP's own `tests/` directory. The MCP test suite uses `from tests.conftest import ...` and `from tests.contract._tool_matrix import ...` patterns; with the shadow active, both imports fail and `task test` collapses with 3 collection errors. `develop=false` installs the CLI as a built sdist/wheel from the path, including only `packages = [{include = "agent_brain_cli"}]` per the CLI's pyproject — no .pth file, no tests/ shadowing, MCP's 468 baseline tests pass again. The precedent for this pattern is already in `agent-brain-mcp/Taskfile.yml`'s `install` task which writes path deps for agent-brain-rag / agent-brain-uds with `develop = false`. The change is documented inline in the pyproject comment block.

- **Single grouped commit (Plans 1+2+3 in one commit)** — mirrors Plan 56-01's pattern. The plan's Task 3 explicitly stages all four files (`client.py + test + pyproject + poetry.lock`) in one `git add` + `git commit` invocation. Task-level verification ran independently as each task landed; the commit boundary is the plan boundary, which is the integration boundary for Phase 57 reviewers.

- **`_PHASE_57_NOT_WIRED = "Wired in Phase 57+"` declared as module-level constant** — referenced by both backend classes' 24 endpoint method bodies. Phase 57 transport selector tests grep for this literal string to confirm the skeleton-vs-implementation boundary. Single source of truth for the sentinel.

- **Forward type hints unquoted** — e.g., `def health(self) -> HealthStatus:` (not `-> "HealthStatus":`). The module-header `from __future__ import annotations` defers all annotations to strings at module level, so quoting is unnecessary and Black/Ruff prefer the unquoted form. Plan's sample used quoted strings (legacy compatibility); unquoted matches the existing ApiClient style in the same file and passes mypy strict identically.

- **`__exit__` traceback parameter typed as `TracebackType | None`** (not `object` as the plan's sample suggested) — matches the existing `ApiClient.__exit__` signature byte-for-byte. `TracebackType` is already imported at module top via `from types import TracebackType`; no new import needed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] develop=true broke the MCP test suite collection**

- **Found during:** Task 1 verification step — after `poetry install --with dev` finished, running `task test` collapsed with 3 `ModuleNotFoundError` collection errors (`tests.contract`, `tests.conftest`, `tests.contract._tool_matrix`).
- **Issue:** `develop = true` on the CLI path dep drops a `.pth` file into the MCP venv's `site-packages/` that adds `../agent-brain-cli` (the CLI repo root) to `sys.path`. The CLI's `tests/` directory ships an `__init__.py`, so it becomes importable as a top-level `tests` package — which SHADOWS the MCP package's own `tests/` directory (which is a namespace package without `__init__.py`). The MCP test suite's `from tests.conftest import ...` and `from tests.contract._tool_matrix import ...` then resolve to the CLI's `tests/` package, which doesn't contain those modules.
- **Fix:** Changed `develop = true` to `develop = false` in the pyproject dev-deps line and added a 10-line inline comment explaining the choice + citing the Taskfile.yml precedent. Re-ran `poetry lock && poetry install --with dev` — agent-brain-cli now installs as a built package (only the `agent_brain_cli/` source per its `packages` declaration), no `.pth` file, no shadowing. `task test` reports 474 passed.
- **Files modified:** `agent-brain-mcp/pyproject.toml` (line 62 changed from `develop = true` to `develop = false` + added comment block).
- **Commit:** `7f45466` (folded into the plan-level commit per the plan's commit-grouping spec).

**2. [Rule 1 - Bug] `grep -c "from __future__"` counted a comment line**

- **Found during:** Task 2 verification step — the plan's acceptance criterion `grep -c "from __future__" agent-brain-mcp/agent_brain_mcp/client.py` returned 2 instead of the required exactly 1.
- **Issue:** The plan's suggested skeleton-block header comment block contained the literal string `from __future__` in a NEGATIVE assertion ("this block deliberately does NOT contain `from __future__ import annotations`"). `grep -c` is line-substring-based and counted the comment as a hit.
- **Fix:** Rewrote the comment to avoid the literal substring `from __future__` while preserving the load-bearing meaning ("this block deliberately does NOT re-import the deferred-annotations future. ... Python forbids those imports anywhere except the file header — re-importing here (even with an alias) is a SyntaxError."). The comment continues to warn future readers about the SyntaxError risk; only the substring grep targets changes.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py` (one comment block rewritten).
- **Commit:** `7f45466`.

**3. [Rule 1 - Bug] Ruff I001 import-order on the test file**

- **Found during:** Task 3 quality-gate step (`poetry run ruff check tests/test_cli_backends_skeleton.py`).
- **Issue:** Ruff's `I001` import-sorting rule flagged the test file's import block as not grouped per the project's `isort` profile (the `from __future__ import annotations` line was not separated from the subsequent imports by the canonical blank-line grouping).
- **Fix:** `poetry run ruff check --fix tests/test_cli_backends_skeleton.py` — autofixed in place. Black + mypy + pytest all re-verified after the fix.
- **Files modified:** `agent-brain-mcp/tests/test_cli_backends_skeleton.py` (import-block reformatted).
- **Commit:** `7f45466`.

### Other

- **Rich 15.0.0 → 13.9.4 downgrade in the lock file** (informational, not a deviation): when agent-brain-cli was added as a dev dep, Poetry's resolver chose Rich 13.9.4 as the highest version satisfying both the MCP package's previous transitives and the CLI's `rich = "^13.9.0"` pin. This is the expected behavior of adding a sibling-package path dep with a tighter Rich pin. No impact on MCP runtime (MCP uses Rich only indirectly via `mcp` SDK + nothing else).
- **`task before-push` lock-drift warning on `agent-brain-cli/poetry.lock`** (informational, not a failure): same as Plan 56-01 / 56-02 — the post-run `before_push_lock_guard.sh check` reported the CLI's lock drifted during the gate run (known #174 monorepo-bootstrap drift). The guard auto-reverted; the Plan 03 commits were not affected. Exit code 0.

## Auth Gates Encountered

None. This is a skeleton plan — no external services or APIs touched.

## Issues Encountered

None blocking. The `task before-push` run surfaced the same pre-existing warnings carried forward from Plans 56-01 and 56-02:

- `websockets.legacy` deprecation in MCP `test_http_listener.py` (Phase 53 carry-forward; tracked separately).
- Lock-drift on `agent-brain-cli/poetry.lock` (known #174 monorepo bootstrap; auto-reverted by guard).

Neither affects this plan's commits or test outcomes.

## User Setup Required

None — this is a skeleton plan, no external service configuration required.

## Phase 57 Note (next milestone phase)

Phase 57 will REPLACE the `NotImplementedError` bodies with real MCP SDK calls. The sentinel string to grep for is:

```
_PHASE_57_NOT_WIRED = "Wired in Phase 57+"
```

declared at module level in `agent-brain-mcp/agent_brain_mcp/client.py`. Phase 57's transport-selector tests should grep for this literal string to confirm "I got the skeleton, not a stale stub left behind by a botched refactor."

Phase 57 will also resolve the sync-facade pattern choice from design doc §3.2:

- **Pattern A:** `asyncio.run(self._async_xxx(...))` per call — creates and tears down a new event loop per method call. Simple. Fine for short CLI invocations.
- **Pattern B:** persistent `self._loop = asyncio.new_event_loop()` on the backend instance, called via `self._loop.run_until_complete(...)`. Single bootstrap cost, freed on `close()`. Trickier lifecycle.

Plan 56-03 does NOT measure either pattern — both are equally valid skeleton shapes. Phase 57 measures + picks.

The MCP method ↔ tool mapping table in design doc §2.3 is the wire-up reference: `query` ↔ `search_documents` tool, `health` ↔ `server_health`, `status` ↔ `corpus://status` resource read, `index` ↔ `index_folder` (or `inject_documents` if `injector_script` is set), `list_folders` ↔ `corpus://folders` resource read, `delete_folder` ↔ `remove_folder` tool, `reset` ↔ NO MCP TOOL EQUIVALENT IN V2 (Phase 57 decides whether to add `reset_index` tool or hold for v4 — the skeleton's `NotImplementedError` for `reset()` carries forward verbatim), `list_jobs` ↔ `list_jobs` tool, `get_job` ↔ `job://<id>` resource read, `cancel_job` ↔ `cancel_job` tool, `cache_status` ↔ `cache_status` tool, `clear_cache` ↔ `clear_cache` tool (requires `confirm: True`).

## Next Phase Readiness

- **Phase 57 ready to execute:** Both backend skeletons import cleanly from `agent_brain_mcp.client`, both pass `isinstance(backend, BackendClient)`, both raise the documented sentinel on every endpoint method. The transport-selector at `agent-brain-cli/agent_brain_cli/client/transport.py` can now route `--transport mcp` to either backend; Phase 57 wires the actual MCP SDK calls.
- **Phase 56 plan progress:** 3/3 plans complete (56-01 ✓, 56-02 ✓, 56-03 ✓).
- **No blockers.**

---
*Phase: 56-design-doc-cli-backend-skeleton*
*Completed: 2026-06-06*

## Self-Check: PASSED

- FOUND: `agent-brain-mcp/agent_brain_mcp/client.py` (modified — McpStdioBackend + McpHttpBackend added alongside ApiClient, exactly 1 `from __future__` line, 0 `_ab_annotations` aliases)
- FOUND: `agent-brain-mcp/tests/test_cli_backends_skeleton.py` (created, 75 lines, 6 tests pass)
- FOUND: `agent-brain-mcp/pyproject.toml` (modified — agent-brain-cli in dev group with `develop = false`, NOT in main deps)
- FOUND: `agent-brain-mcp/poetry.lock` (modified — agent-brain-cli 10.2.1 added; rich downgrade 15.0.0 → 13.9.4 to satisfy CLI's pin)
- FOUND: `.planning/phases/56-design-doc-cli-backend-skeleton/56-03-SUMMARY.md` (this file)
- FOUND: commit `7f45466` — `feat(56-03): McpStdioBackend + McpHttpBackend skeletons (CLI-MCP-01, CLI-MCP-02)` (touches client.py + test + pyproject + poetry.lock, nothing else)
- VERIFIED: `task before-push` exit 0 — 474 MCP tests passed (468 baseline + 6 new), 91% coverage, Black/Ruff/mypy strict all clean
- VERIFIED: `isinstance(McpStdioBackend(command='dummy'), BackendClient)` returns True
- VERIFIED: `isinstance(McpHttpBackend(url='http://127.0.0.1:9999/mcp'), BackendClient)` returns True
- VERIFIED: `isinstance(DocServeClient(base_url='http://x'), BackendClient)` returns True (Plan 02 regression-pin preserved)
