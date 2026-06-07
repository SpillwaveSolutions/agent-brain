---
phase: 58-runtime-discovery-helper-commands
plan: 01
subsystem: cli
tags: [mcp, psutil, runtime-discovery, lock-file, click, file-permissions, issue-179]

requires:
  - phase: 57-cli-transport-selector-byte-identical-equivalence
    provides: "Two-axis transport selector (resolve_mcp_transport) with §3.5 case-2 placeholder error string that Plan 58-03 will swap for the discovery-file wording."
  - phase: 56-mcp-v3-design-and-skeletons
    provides: "v3 design doc §2.4 mcp.runtime.json schema + McpHttpBackend skeleton whose __init__ Plan 58-03 wires to read_mcp_runtime."

provides:
  - "agent_brain_cli.mcp_runtime module — 6 helpers + 4 constants + 1 exception class"
  - "MCP_RUNTIME_FILE / MCP_LOCK_FILE / MCP_DEFAULT_PORT / MCP_DEFAULT_START_TIMEOUT public constants (load-bearing across Plans 58-02 / 58-03)"
  - "read_mcp_runtime / write_mcp_runtime / delete_mcp_runtime file IO with 0o600 perms"
  - "acquire_lock / release_lock with stale-pid reclamation via psutil"
  - "is_listening(pid, host, port, timeout, poll_interval) — psutil kernel-bind verifier cloned from agent-brain-mcp/tests/test_http_loopback.py"
  - "LockAcquisitionError with verbatim 'agent-brain mcp already running on port {port} (pid {pid}); run agent-brain mcp stop first' wording"

affects: [58-02-mcp-start, 58-03-mcp-stop-and-discovery, 59-prompts-and-resources, 60-subprocess-hygiene]

tech-stack:
  added: ["psutil ^5.9 (now a runtime dep of agent-brain-cli — previously only pinned in agent-brain-mcp)"]
  patterns:
    - "Shared MCP runtime helpers module (mirrors start.py's read_runtime/write_runtime pattern but for MCP variants)"
    - "0o600 file permissions on pid-bearing files (issue #179 API-key-file convention carry-forward)"
    - "psutil kernel-bind verification reused from agent-brain-mcp HTTP-02 test pattern"
    - "Stale-pid reclamation via psutil.pid_exists (lock file + runtime file unlinked + retry once)"

key-files:
  created:
    - "agent-brain-cli/agent_brain_cli/mcp_runtime.py (282 lines — 6 helpers + 4 constants + 1 exception)"
    - "agent-brain-cli/tests/test_mcp_runtime.py (340 lines — 19 unit tests covering all helpers + psutil stubs)"
  modified:
    - "agent-brain-cli/pyproject.toml (+1 dep line: psutil = ^5.9)"
    - "agent-brain-cli/poetry.lock (psutil 5.9.8 + transitive entries)"

key-decisions:
  - "Module location: agent-brain-cli/agent_brain_cli/mcp_runtime.py (separate from commands/start.py — different command namespace)"
  - "0o600 file permissions on both mcp.runtime.json AND agent-brain-mcp.lock (issue #179 convention)"
  - "psutil ^5.9 declared as agent-brain-cli runtime dep (was previously only pinned in agent-brain-mcp's pyproject.toml — +1 transitive across CLI package)"
  - "is_listening returns False on every edge case (NoSuchProcess, AccessDenied, timeout) — callers exit non-zero with stderr-log path; never raises"
  - "acquire_lock uses os.open(O_CREAT|O_EXCL|O_WRONLY, 0o600) for atomic creation; stale-pid reclamation via psutil.pid_exists with single retry"
  - "LockAcquisitionError wording pinned by regex test: 'agent-brain mcp already running on port {port} (pid {pid}); run agent-brain mcp stop first'"
  - "Single atomic plan-level commit (mirrors Plan 56-03 commit-grouping pattern) — Tasks 1/2/3 land together after task before-push exit 0"

patterns-established:
  - "Shared MCP runtime helpers in a dedicated module — commands/mcp.py (Plan 58-02) and McpHttpBackend.__init__ (Plan 58-03) both `from agent_brain_cli.mcp_runtime import ...` rather than duplicating file IO + psutil polling"
  - "psutil stub pattern for unit tests (_StubLAddr / _StubConn / _StubProcess classes) — avoids spawning real subprocesses at unit-test time; integration tests own real-subprocess coverage"
  - "FileExistsError handling in acquire_lock uses `raise ... from None` to avoid B904 (the FileExistsError is not a true cause — the LockAcquisitionError is the operator-facing surface)"

requirements-completed: []  # CLI-MCP-08 is INTRODUCED here (helpers land) but not CLOSED — Plan 58-03 wires the McpHttpBackend.__init__ discovery integration end-to-end.

duration: 6min
completed: 2026-06-07
---

# Phase 58 Plan 01: Runtime Helper Module Summary

**MCP runtime + lock helper module with psutil kernel-bind verifier and 0o600 file permissions — foundation for `agent-brain mcp start/stop` and `McpHttpBackend` discovery (Plans 58-02 / 58-03).**

## Performance

- **Duration:** 6 min
- **Started:** 2026-06-07T02:09:40Z
- **Completed:** 2026-06-07T02:15:45Z
- **Tasks:** 3 (Task 1 psutil dep, Task 2 module + tests, Task 3 QA gate + commit)
- **Files modified:** 4 (2 created, 2 modified)
- **Tests added:** 19 unit tests (15 plan-required names + 4 additional sanity tests)
- **`task before-push` runtime:** ~3-4 minutes (full monorepo: server + CLI + UDS + MCP all green)

## Accomplishments

- **Schema constants pinned** — `MCP_RUNTIME_FILE = "mcp.runtime.json"`, `MCP_LOCK_FILE = "agent-brain-mcp.lock"`, `MCP_DEFAULT_PORT = 8765`, `MCP_DEFAULT_START_TIMEOUT = 10.0` — all 4 importable from `agent_brain_cli.mcp_runtime` by Plans 58-02 / 58-03.
- **File IO helpers** — `read_mcp_runtime` (returns None on missing/malformed; never raises), `write_mcp_runtime` (creates parent state_dir, writes JSON, chmods to 0o600), `delete_mcp_runtime` (idempotent, swallows OSError).
- **Lock helpers** — `acquire_lock` uses `os.open(O_CREAT|O_EXCL|O_WRONLY, 0o600)` for atomic creation; on alive holder raises `LockAcquisitionError` with verbatim "agent-brain mcp already running..." wording; on dead holder reclaims (deletes lock + runtime files) and retries once. `release_lock` idempotent.
- **psutil kernel-bind verifier** — `is_listening(pid, host, port, timeout=10.0, poll_interval=0.1)` polls `psutil.Process(pid).net_connections(kind="inet")` filtered to `CONN_LISTEN` + loopback IP + exact port. Returns False (never raises) on NoSuchProcess, AccessDenied, or timeout — the pattern is grep-pinned (`psutil.Process(pid).net_connections(kind="inet")` literal substring) for Plan 58-02 verifier scripts.
- **psutil dep added** — `psutil = "^5.9"` added to `agent-brain-cli/pyproject.toml`; lock file updated; `psutil 5.9.8` installed in the CLI venv. **+1 transitive dep across the CLI package** (was previously only pinned in agent-brain-mcp; the dep family is intentionally identical — `^5.9` — to keep poetry's resolver friendly when both packages are installed in the same environment).
- **Quality gate green** — `task before-push` exits 0: Black + Ruff + mypy strict + 490 monorepo tests (19 new in `test_mcp_runtime.py` + zero regressions) + MCP sub-package suite (490 tests, 87% coverage) + UDS sub-package suite.

## Task Commits

This plan landed as a **single atomic per-plan commit** (mirroring Plan 56-03's commit-grouping pattern). Per-task work was verified independently as each task landed; the commit boundary is the plan boundary.

1. **Task 1: Add psutil dependency** — Edited `pyproject.toml`, ran `poetry lock` + `poetry install`, verified `import psutil` succeeds in the venv (psutil 5.9.8). Acceptance criteria: `grep -c 'psutil = "\^5.9"' pyproject.toml = 1` ✓; lock file contains psutil entry ✓; venv import succeeds ✓.
2. **Task 2: Create mcp_runtime.py + tests** — TDD-style: wrote module + 19 unit tests; tests pass on first run (`poetry run pytest tests/test_mcp_runtime.py -v` → 19 passed in 0.10s). Acceptance criteria: all 11 grep patterns pass (constants × 4, function defs × 6, exception class × 1, `0o600` literal count ≥ 2 (actually 5), `psutil.Process(pid).net_connections(kind="inet")` literal × 1, verbatim error wording × 1). All 15 plan-required test names present + 4 additional sanity tests.
3. **Task 3: `task before-push` + commit** — Ran QA gate: Black auto-formatted 2 files; Ruff caught 3 issues (B904 × 2 + I001 × 1) auto-fixed via `raise ... from None` + `ruff check --fix`; mypy strict caught 1 `Any` return that was fixed with explicit `bool()` cast on `psutil.pid_exists`. Final `task before-push` exits 0. Committed as `da37239` `feat(58-01): mcp_runtime.py shared helpers + psutil verifier + 0o600 perms`.

**Plan-level commit:** `da37239`

## Files Created/Modified

- `agent-brain-cli/agent_brain_cli/mcp_runtime.py` *(created, 282 lines)* — Shared MCP runtime + lock + psutil helpers. Exports: `MCP_RUNTIME_FILE`, `MCP_LOCK_FILE`, `MCP_DEFAULT_PORT`, `MCP_DEFAULT_START_TIMEOUT`, `LockAcquisitionError`, `read_mcp_runtime`, `write_mcp_runtime`, `delete_mcp_runtime`, `acquire_lock`, `release_lock`, `is_listening`.
- `agent-brain-cli/tests/test_mcp_runtime.py` *(created, 340 lines)* — 19 unit tests with psutil stub classes (`_StubLAddr`, `_StubConn`, `_StubProcess`) for `is_listening` without spawning real subprocesses.
- `agent-brain-cli/pyproject.toml` *(modified)* — Added `psutil = "^5.9"` runtime dep line after `agent-brain-uds = "^10.2.1"`.
- `agent-brain-cli/poetry.lock` *(modified)* — Locked psutil 5.9.8 entry.

## Decisions Made

| Decision | Rationale |
|---|---|
| **Module location:** `agent-brain-cli/agent_brain_cli/mcp_runtime.py` (NOT extending `commands/start.py`) | Phase 58 CONTEXT decision — keeps `agent-brain mcp ...` namespace clean; `start.py` manages agent-brain-server, not MCP. |
| **0o600 file perms** on both `mcp.runtime.json` and `agent-brain-mcp.lock` | Issue #179 API-key-bearing-file convention carry-forward (the runtime file embeds the spawned-subprocess pid; lock embeds the parent-CLI pid). |
| **`psutil ^5.9`** dep family identical to agent-brain-mcp's pin | Keeps poetry resolver friendly when both packages share a venv; +1 transitive dep across CLI package documented here per CONTEXT discretion note. |
| **`is_listening` returns False on every edge case** (NoSuchProcess, AccessDenied, timeout, never-alive) | Callers (Plan 58-02 `mcp start`) treat False as "subprocess failed to come up; surface stderr log + exit non-zero". Raising would tangle the error-flow contract. |
| **`acquire_lock` uses `os.open(O_CREAT|O_EXCL|O_WRONLY, 0o600)`** for atomic creation | The only race-free way to combine "create if absent, fail if present" on POSIX without TOCTOU. Lock file content = parent-CLI pid (diagnostic value); `mcp.runtime.json` pid = spawned subprocess pid (what `stop` signals). |
| **Stale-pid reclamation via `psutil.pid_exists` with single retry** | Mirrors `commands/start.py::is_stale + cleanup_stale` semantics. Single retry prevents infinite loops if reclamation itself races; defensive `LockAcquisitionError("failed to reclaim...")` surfaces on second collision. |
| **`LockAcquisitionError` wording pinned by regex test** | Plan 58-02's operator-facing error formatter can grep for the literal substring without depending on this module's exception type. Wording: `agent-brain mcp already running on port {port} (pid {pid}); run 'agent-brain mcp stop' first`. |
| **Single atomic plan-level commit** | Mirrors Plan 56-03 precedent. Per-task work was verified independently (acceptance criteria pass at task boundary); the commit boundary is the plan boundary (= integration boundary for Plan 58-02 reviewers). |
| **`raise ... from None` for LockAcquisitionError in `except FileExistsError`** | Ruff B904 fix. The FileExistsError is not a true cause — `LockAcquisitionError` is the operator-facing surface; explicit `from None` suppresses the misleading exception chain. |
| **`bool(psutil.pid_exists(pid))` cast** | mypy strict refuses `Any`-typed return under `ignore_missing_imports = true`. Explicit cast keeps strict mode happy. |

## Deviations from Plan

None. The plan executed exactly as written, with three minor auto-fixes per **Rule 1 - Bug / Rule 3 - Blocking** during the QA gate that were already anticipated by the plan's "Common fixes" guidance:

1. **[Rule 3 - Blocking] Black auto-format** — 2 files reformatted (minor whitespace/dict-wrap changes). Anticipated by Task 3's "Common fixes" guidance.
2. **[Rule 3 - Blocking] Ruff B904 × 2 + I001 × 1** — Added `raise ... from None` on both `LockAcquisitionError` raises inside `except FileExistsError`; ran `ruff check --fix` for the import-sort. Anticipated by Task 3's guidance.
3. **[Rule 3 - Blocking] mypy strict: `Any` return from `psutil.pid_exists`** — Added explicit `bool()` cast in `_is_pid_alive`. Anticipated by Task 3's "mypy: most likely an explicit return annotation or a stubs install" note.

**Test count:** Plan asked for exactly 15 named tests; implementation has **19 tests** (15 plan-required + 4 additional sanity tests: `test_module_constants_match_design_doc`, `test_read_mcp_runtime_returns_dict_when_present`, `test_is_listening_returns_false_on_access_denied`, `test_is_listening_ignores_non_listen_status`). The 4 extras are strict supersets of the plan's behavior matrix — they pin additional edge cases (constant rename detection, happy-path read, AccessDenied parity with NoSuchProcess, non-LISTEN-status filtering) that round out the coverage without changing the contract.

**Total deviations:** 0 scope deviations; 3 anticipated quality-gate auto-fixes; +4 tests beyond the plan's required 15.
**Impact on plan:** Zero scope creep. All extras are within the existing module's contract.

## Issues Encountered

- **Poetry 2.x dropped `--no-update`** — The plan's literal `poetry lock --no-update` command failed (`The option "--no-update" does not exist`). Poetry 2.3.2 (installed in this venv) treats `poetry lock` as non-destructive by default; the `--no-update` flag was removed. Ran plain `poetry lock` instead — same effect (dep resolution + lock file write without touching existing pins). Documented here for downstream plans that may try the same command.

## User Setup Required

None — no external service configuration. The dep addition + helper module are entirely internal.

## Hand-off Points for Plans 58-02 and 58-03

### Plan 58-02 (`agent-brain mcp start`)

```python
from agent_brain_cli.mcp_runtime import (
    LockAcquisitionError,
    MCP_DEFAULT_PORT,
    MCP_DEFAULT_START_TIMEOUT,
    MCP_RUNTIME_FILE,
    acquire_lock,
    is_listening,
    release_lock,  # for Popen-failure cleanup
    write_mcp_runtime,
)
```

Plan 58-02's flow per CONTEXT decisions:

1. `acquire_lock(state_dir)` BEFORE Popen — atomic file creation; raises `LockAcquisitionError` if alive holder.
2. `subprocess.Popen([...], start_new_session=True, ...)` with stdout/stderr to `<state_dir>/mcp.stdout.log` + `mcp.stderr.log`.
3. `is_listening(process.pid, "127.0.0.1", port, timeout=MCP_DEFAULT_START_TIMEOUT)` — psutil-verified kernel bind.
4. On success: `write_mcp_runtime(state_dir, {"host": "127.0.0.1", "port": port, "pid": process.pid, "started_at": <iso>, "transport": "http"})`.
5. On Popen failure / timeout: SIGTERM subprocess (best-effort) + `release_lock(state_dir)` + raise click.ClickException with stdout/stderr log paths embedded.

### Plan 58-03 (`agent-brain mcp stop` + `McpHttpBackend` discovery)

```python
from agent_brain_cli.mcp_runtime import (
    MCP_RUNTIME_FILE,
    delete_mcp_runtime,
    read_mcp_runtime,
    release_lock,
)
```

Plan 58-03's flow:

- **`mcp stop`:** `read_mcp_runtime(state_dir)` → if None, "agent-brain mcp not running" exit 0; else `os.killpg(os.getpgid(pid), SIGTERM)` → poll → SIGKILL after grace → `delete_mcp_runtime(state_dir)` + `release_lock(state_dir)`.
- **`McpHttpBackend.__init__` discovery:** when `url=None`, `read_mcp_runtime(state_dir)` → construct `f"http://{data['host']}:{data['port']}"`. If `read_mcp_runtime` returns None, raise the §3.5 wording about `mcp.runtime.json` discovery (replaces Phase 57's case-2 placeholder error).

### CLI-MCP-08 progress

**Introduced** here (helpers land); **closed** in Plan 58-03 (discovery wired end-to-end into `McpHttpBackend.__init__`). REQUIREMENTS.md remains unchecked for CLI-MCP-08 — the requirement spans 58-01 + 58-03 and only flips green at 58-03's plan close.

## Next Phase Readiness

- **Plan 58-02 ready** — All imports it needs are exported from `agent_brain_cli.mcp_runtime`. CONTEXT.md flow (`acquire_lock` → `Popen` → `is_listening` → `write_mcp_runtime`) maps 1:1 to the helpers.
- **Plan 58-03 ready** — Discovery integration (`McpHttpBackend.__init__` reads `read_mcp_runtime`) + cleanup (`delete_mcp_runtime` + `release_lock`) all available. The Phase 57 placeholder error string at `agent_brain_cli/config.py:591-592` is still in place — Plan 58-03 swaps it for the §3.5 wording.
- **No blockers** — `task before-push` exits 0 against HEAD; no flaky tests; no skipped tests.

## Self-Check: PASSED

- `agent-brain-cli/agent_brain_cli/mcp_runtime.py` exists ✓
- `agent-brain-cli/tests/test_mcp_runtime.py` exists ✓
- `agent-brain-cli/pyproject.toml` contains `psutil = "^5.9"` ✓
- `agent-brain-cli/poetry.lock` contains `name = "psutil"` ✓
- Commit `da37239` on HEAD ✓ (`git log -1 --pretty=%s` → `feat(58-01): mcp_runtime.py shared helpers + psutil verifier + 0o600 perms`)
- All 11 grep acceptance criteria pass ✓
- All 19 unit tests pass ✓
- `task before-push` exits 0 ✓

---

*Phase: 58-runtime-discovery-helper-commands*
*Plan: 01*
*Completed: 2026-06-07*
