---
phase: 58-runtime-discovery-helper-commands
plan: 02
subsystem: cli
tags: [mcp, click, subprocess, popen, port-allocation, lock-acquisition, psutil, runtime-discovery]

requires:
  - phase: 58-runtime-discovery-helper-commands
    provides: "Plan 58-01: mcp_runtime helpers (acquire_lock, release_lock, is_listening, write_mcp_runtime, MCP_RUNTIME_FILE, LockAcquisitionError with verbatim 'agent-brain mcp already running on port {port} (pid {pid}); run agent-brain mcp stop first' wording)."
  - phase: 56-mcp-v3-design-and-skeletons
    provides: "v3 design doc §2.4 5-field mcp.runtime.json schema {host, port, pid, started_at, transport}."

provides:
  - "agent-brain mcp Click sub-group with start subcommand"
  - "Port allocation: --port > AGENT_BRAIN_MCP_PORT env > 8765 default; OS-fallback on EADDRINUSE; --port 0 escape hatch"
  - "Detached Popen pattern with start_new_session=True (load-bearing for Plan 58-03's os.killpg)"
  - "Psutil-verified write of mcp.runtime.json AFTER kernel-bind verification (never before — §2.4 contract)"
  - "Lock semantics: acquire_lock BEFORE Popen; release_lock on timeout/spawn-failure; mcp.runtime.json never written if listener-ready times out"

affects: [58-03-mcp-stop-and-discovery, 59-prompts-and-resources, 60-subprocess-hygiene]

tech-stack:
  added: []
  patterns:
    - "Click sub-group + subcommand topology: commands/mcp.py exposes mcp_group; Plan 58-03 appends stop_subcommand to the same module"
    - "Popen subprocess with start_new_session=True for POSIX process-group detach (subprocess gets its own pgid)"
    - "Pre-bind probe → close → respawn pattern for port allocation (TOCTOU window microseconds — same as start.py)"
    - "MagicMock + module-level patch for unit-testing Popen + is_listening without spawning real subprocesses"

key-files:
  created:
    - "agent-brain-cli/agent_brain_cli/commands/mcp.py (302 lines after Black auto-format — Click mcp_group + start subcommand + 4 helpers + _tail_log)"
    - "agent-brain-cli/tests/test_mcp_start_command.py (380 lines — 12 unit tests covering port resolution, EADDRINUSE fallback, lock collision, runtime schema, Popen args, start_new_session, --state-dir override, JSON output)"
  modified:
    - "agent-brain-cli/agent_brain_cli/cli.py (+2 lines: import mcp_group + cli.add_command registration)"
    - "agent-brain-cli/agent_brain_cli/commands/__init__.py (+2 lines: re-export mcp_group)"

key-decisions:
  - "Click sub-group lives in commands/mcp.py — NOT extending commands/start.py (which manages agent-brain-server, not MCP)"
  - "Port precedence: --port flag > AGENT_BRAIN_MCP_PORT env > 8765 default; --port 0 always asks the OS"
  - "EADDRINUSE fallback (errno 48 macOS / 98 Linux) → OS-allocated free port via bind(127.0.0.1, 0)"
  - "Loopback host is hard-coded in the Popen args list (no --host flag exposed — CONTEXT decision; v3 loopback-only contract)"
  - "Detached subprocess via start_new_session=True (required for Plan 58-03's os.killpg(getpgid(pid), SIGTERM))"
  - "mcp.runtime.json written AFTER is_listening returns True — never on timeout/crash (§2.4 contract pinned by test_start_does_not_write_runtime_on_timeout)"
  - "Lock acquired BEFORE Popen + released on every error edge (port-alloc failure, Popen failure, listener timeout) → no orphan locks"
  - "subprocess.Popen[bytes] explicit annotation to satisfy mypy strict (subprocess.Popen is a Generic)"

patterns-established:
  - "Per-task Popen subprocess unit-testing without real spawns — patch agent_brain_cli.commands.mcp.subprocess.Popen at the module level + MagicMock with .pid attribute"
  - "Patching agent_brain_cli.commands.mcp.is_listening rather than mcp_runtime.is_listening keeps the unit tests deterministic + avoids the real psutil poll loop"
  - "_resolve_preferred_port + _allocate_port broken out as module-level helpers (testable in isolation without invoking Click)"

requirements-completed: [CLI-MCP-09]

duration: 4min
completed: 2026-06-07
---

# Phase 58 Plan 02: `agent-brain mcp start` subcommand Summary

**Click sub-group `commands/mcp.py` exposing `mcp start` — detached `agent-brain-mcp --transport http` Popen with `start_new_session=True`, port allocation with EADDRINUSE-fallback, psutil-verified write of `mcp.runtime.json` (5-field locked §2.4 schema) only after listener-ready.**

## Performance

- **Duration:** 4 min 13 s
- **Started:** 2026-06-07T02:20:56Z
- **Completed:** 2026-06-07T02:25:15Z
- **Tasks:** 2 (Task 1 implementation + tests, Task 2 QA gate + atomic commit)
- **Files modified:** 4 (2 created, 2 modified)
- **Tests added:** 12 unit tests (11 plan-required names + 1 additional `--json` output sanity test)
- **`task before-push` runtime:** ~4 minutes (full monorepo: server + CLI + UDS + MCP all green)

## Accomplishments

- **Click sub-group + start subcommand shipped** — `commands/mcp.py` exposes `@click.group("mcp")` + `@mcp_group.command("start")` decorated function with four user-facing flags: `--port`, `--start-timeout`, `--state-dir`, `--json`. Plan 58-03's `stop` subcommand will append to the same module.
- **Port allocation precedence enforced** — `_resolve_preferred_port(port_flag)` resolves `--port` > `AGENT_BRAIN_MCP_PORT` env > `MCP_DEFAULT_PORT = 8765`; invalid env raises `click.UsageError` (exit 2). `_allocate_port(preferred)` pre-binds, falls back to `bind(127.0.0.1, 0)` on EADDRINUSE, and treats `--port 0` as "always ask the OS".
- **Detached subprocess pattern wired** — `subprocess.Popen([sys.executable, "-m", "agent_brain_mcp", "--transport", "http", "--host", "127.0.0.1", "--port", str(resolved_port)], stdout=..., stderr=..., start_new_session=True)`. The `start_new_session=True` kwarg is load-bearing for Plan 58-03's `os.killpg`.
- **§2.4 schema contract enforced** — `is_listening(process.pid, "127.0.0.1", resolved_port, timeout=start_timeout)` polled via psutil BEFORE the runtime file write. On `True`, writes the 5-field locked schema `{host, port, pid, started_at, transport}` with `started_at` as ISO8601 UTC; on `False`, sends SIGTERM, releases the lock, surfaces last 20 stderr lines, raises `SystemExit(1)`. Pinned by `test_start_does_not_write_runtime_on_timeout`.
- **Lock semantics carry forward end-to-end** — `acquire_lock(state_dir)` invoked BEFORE Popen; collision with an alive holder surfaces the verbatim wording `"agent-brain mcp already running on port {port} (pid {pid}); run 'agent-brain mcp stop' first"` from Plan 58-01's `LockAcquisitionError` (pinned by `test_start_lock_collision_exits_one`). `release_lock` called on every error edge (port-alloc, Popen, listener timeout).
- **CLI registration** — `cli.py` imports `mcp_group` and calls `cli.add_command(mcp_group, name="mcp")`; `commands/__init__.py` re-exports `mcp_group`. `agent-brain mcp --help` and `agent-brain mcp start --help` both surface the expected flags.
- **Quality gate green** — `task before-push` exits 0: Black auto-formatted `mcp.py` (1 file), Ruff caught 1 I001 import-sort in the test (auto-fixed via `ruff check --fix`), mypy strict clean, all 502 monorepo tests pass (12 new in `test_mcp_start_command.py` + zero regressions) + MCP sub-package suite (490 tests, 87% coverage) + UDS sub-package suite.

## Task Commits

This plan landed as a **single atomic per-plan commit** (mirroring Plan 58-01's commit-grouping pattern). Per-task work was verified independently as each task landed; the commit boundary is the plan boundary.

1. **Task 1: Implement `agent-brain mcp start` subcommand** — TDD-style: wrote test file (`tests/test_mcp_start_command.py`) + implementation (`commands/mcp.py`); all 12 tests pass on first run (`poetry run pytest tests/test_mcp_start_command.py -v` → 12 passed in 0.18s). Acceptance criteria: all 11 grep patterns pass (`@click.group("mcp")` × 1, `@mcp_group.command("start")` × 1, `start_new_session=True` × 1, `AGENT_BRAIN_MCP_PORT` × 4, `AGENT_BRAIN_MCP_START_TIMEOUT` × 1, `MCP_DEFAULT_PORT = 8765` × 1, `"agent_brain_mcp"` × 1, `from .mcp import mcp_group` × 1, `mcp_group` in `__init__` × 2, `cli.add_command(mcp_group, name="mcp")` × 1, line counts ≥ 180 and ≥ 150). All 11 plan-required test names present + 1 additional sanity test (`test_start_json_output_on_success`).
2. **Task 2: `task before-push` + commit** — Ran QA gate: Black auto-formatted `commands/mcp.py` (anticipated by plan's Common-pitfalls note on Popen command list); Ruff I001 caught 1 import-sort issue in the test file (auto-fixed via `ruff check --fix`); mypy strict clean (explicit `subprocess.Popen[bytes]` annotation added per plan's Common-pitfalls note). Final `task before-push` exits 0. Committed as `152c305` `feat(58-02): agent-brain mcp start subcommand (CLI-MCP-09)`.

**Plan-level commit:** `152c305`

## Files Created/Modified

- `agent-brain-cli/agent_brain_cli/commands/mcp.py` *(created, 302 lines after Black)* — Click `mcp_group` + `start_command` subcommand. Module-level constants (`MCP_DEFAULT_PORT = 8765`, `MCP_DEFAULT_START_TIMEOUT = 10`, `MCP_LOOPBACK_HOST = "127.0.0.1"`, `MCP_STDOUT_LOG = "mcp.stdout.log"`, `MCP_STDERR_LOG = "mcp.stderr.log"`). Helpers: `_resolve_state_dir`, `_resolve_preferred_port`, `_allocate_port`, `_tail_log`. Imports from `agent_brain_cli.mcp_runtime`: `LockAcquisitionError`, `MCP_RUNTIME_FILE`, `acquire_lock`, `is_listening`, `release_lock`, `write_mcp_runtime`.
- `agent-brain-cli/tests/test_mcp_start_command.py` *(created, 380 lines)* — 12 unit tests with `CliRunner` + `MagicMock` + module-level `patch` for `subprocess.Popen` and `is_listening`. Tests: port resolution precedence, EADDRINUSE fallback, `--port 0` escape hatch, invalid env-port `UsageError`, lock collision exit-1 with verbatim wording, runtime schema (5 fields + 0o600 perms), runtime NOT written on timeout, Popen verbatim arg list, `start_new_session=True` kwarg, `--state-dir` override precedence, mcp_group registration, JSON output.
- `agent-brain-cli/agent_brain_cli/cli.py` *(modified, +2 lines)* — Added `mcp_group` to the alphabetized `from .commands import (...)` block and `cli.add_command(mcp_group, name="mcp")` after `list_command` registration.
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` *(modified, +2 lines)* — Re-exported `mcp_group`: `from .mcp import mcp_group` + `"mcp_group",` in `__all__`.

## Decisions Made

| Decision | Rationale |
|---|---|
| **Module location:** `agent-brain-cli/agent_brain_cli/commands/mcp.py` (NOT extending `commands/start.py`) | Phase 58 CONTEXT decision — `start.py` manages agent-brain-server, not MCP. Keeps the `agent-brain mcp ...` namespace clean and avoids the footgun of `start` meaning "server OR MCP" depending on args. |
| **Port precedence:** `--port` flag > `AGENT_BRAIN_MCP_PORT` env > `MCP_DEFAULT_PORT = 8765` | Matches CONTEXT decision; invalid env-port raises `click.UsageError` (exit 2). Module-level constant pinned by `MCP_DEFAULT_PORT = 8765` grep. |
| **`--port 0` = "always ask the OS"** | CONTEXT discretion note: gives operators a clean escape hatch (especially for tests). Skips the preferred-port try entirely. |
| **EADDRINUSE fallback to OS-allocated** | CONTEXT decision: no range-scan; fall back to `bind(127.0.0.1, 0)` once. errno 48 (macOS) / 98 (Linux) is the only branch that triggers fallback — other OSErrors re-raise. |
| **No `--host` flag** | Loopback-only contract is enforced at the Popen-args layer, not at user-facing CLI. The constant `MCP_LOOPBACK_HOST = "127.0.0.1"` is the single source of truth (both in `_allocate_port` and in the Popen command list). |
| **`subprocess.Popen` with `start_new_session=True`** | Required for Plan 58-03's `os.killpg(os.getpgid(pid), SIGTERM)` — the MCP subprocess + any children it spawns receive the signal as a group. Pinned by `test_start_subprocess_uses_start_new_session_true`. |
| **`subprocess.Popen[bytes]` explicit annotation** | mypy strict refuses the unparameterized `Popen` as `Any`. The default `bufsize=-1` + bytes IO mode matches the actual runtime behavior (binary stdout/stderr files are opened in append mode `"a"` not `"ab"` because we open them as text handles for the subprocess to write to). |
| **mcp.runtime.json written AFTER `is_listening=True` only** | §2.4 contract: the runtime file is the source-of-truth for "MCP is live and accepting connections". Writing it before kernel-bind verification would mislead `McpHttpBackend.__init__` (Plan 58-03 discovery integration). Pinned by `test_start_does_not_write_runtime_on_timeout`. |
| **Lock released on every error edge** | `release_lock` called on port-alloc exception, Popen failure, and listener timeout — guarantees no orphan locks block subsequent `mcp start` invocations. |
| **Test patching at `agent_brain_cli.commands.mcp.is_listening` (not `mcp_runtime.is_listening`)** | Patching at the consumer module's namespace overrides the imported symbol where it's actually referenced. Patching at the source module would NOT affect the already-bound name in `commands/mcp.py`. |
| **`--port 0` in tests to avoid colliding with real services** | `MCP_DEFAULT_PORT = 8765` could be live on a developer's machine; `--port 0` always asks the OS for a free port. Tests for runtime-schema + Popen args + start_new_session all use `--port 0`. |
| **Single atomic plan-level commit** | Mirrors Plan 58-01 + Plan 56-03 precedent. Per-task work was verified independently (acceptance criteria pass at task boundary); the commit boundary is the plan boundary (= integration boundary for Plan 58-03 reviewers). |

## Deviations from Plan

None scope-wise. The plan executed exactly as written, with two anticipated quality-gate auto-fixes during Task 2:

1. **[Rule 3 - Blocking] Black auto-format on `commands/mcp.py`** — Black reformatted 1 file (minor whitespace/dict-wrap changes on the JSON output line: `click.echo(json.dumps({"error": f"failed to spawn agent-brain-mcp: {exc}"}))` was split across lines). Anticipated by Task 2's "Common pitfalls" guidance.
2. **[Rule 3 - Blocking] Ruff I001 import sort on `tests/test_mcp_start_command.py`** — The test file had `from pathlib import Path` + `from typing import Any` + `from unittest.mock import MagicMock, patch` mixed with the local agent_brain_cli imports in a way Ruff's isort didn't approve. Auto-fixed via `ruff check --fix`. Anticipated by Task 2's guidance.

**Test count:** Plan asked for exactly 11 named tests; implementation has **12 tests** (11 plan-required + 1 additional `--json` output sanity test: `test_start_json_output_on_success`). The extra test is a strict superset of the plan's behavior matrix — it pins the JSON payload shape (`status`, `host`, `port`, `pid`, `runtime_file` ending with `MCP_RUNTIME_FILE`) without changing the contract.

**Total deviations:** 0 scope deviations; 2 anticipated quality-gate auto-fixes; +1 test beyond the plan's required 11.
**Impact on plan:** Zero scope creep. All extras are within the existing module's contract.

## Issues Encountered

None. All 12 tests passed on first run; Black + Ruff fixed the only two quality-gate issues automatically; mypy strict was happy on first invocation (the explicit `subprocess.Popen[bytes]` annotation was added as a precaution and accepted without complaint).

## User Setup Required

None — no external service configuration. The new subcommand is entirely internal to the CLI.

## Hand-off Points for Plan 58-03

### `mcp stop` subcommand (CLI-MCP-10)

Plan 58-03 appends `@mcp_group.command("stop")` to the same `agent-brain-cli/agent_brain_cli/commands/mcp.py` file. Imports it will need (already exported by `agent_brain_cli.mcp_runtime` from Plan 58-01):

```python
from agent_brain_cli.mcp_runtime import (
    MCP_RUNTIME_FILE,
    delete_mcp_runtime,
    read_mcp_runtime,
    release_lock,
)
```

CONTEXT flow:
1. `read_mcp_runtime(state_dir)` → if None, print "agent-brain mcp not running" exit 0 (idempotent).
2. Extract `pid` from the runtime dict.
3. `os.killpg(os.getpgid(pid), signal.SIGTERM)` → poll `psutil.pid_exists(pid)` for `--grace` seconds (default 5s).
4. If still alive: `os.killpg(..., signal.SIGKILL)`, wait 1s.
5. `delete_mcp_runtime(state_dir)` + `release_lock(state_dir)`.

### `McpHttpBackend.__init__` discovery integration

Plan 58-03 swaps the Phase 57 placeholder error string at `agent_brain_cli/config.py:591-592`:

- Current: `"discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57"`
- v3 §3.5 wording: `"discovery file not found at <state_dir>/mcp.runtime.json; run 'agent-brain mcp start' or pass --mcp-url"`

The `McpHttpBackend.__init__` constructor (in `agent-brain-mcp/agent_brain_mcp/client.py`) gets a `read_mcp_runtime(state_dir)` call when `url=None`; on success, builds `f"http://{data['host']}:{data['port']}"`. On `None`, raises with §3.5 wording.

### CLI-MCP-09 closed

`CLI-MCP-09` (= `agent-brain mcp start` Click command) is **fully shipped + tested by this plan**; the requirement is checked off in `REQUIREMENTS.md` at the end of this plan's execute step.

### Integration test (start → query → stop)

Plan 58-03's end-to-end test should:
1. `agent-brain mcp start --state-dir <tmp> --port 0` (real subprocess; no `--mcp-url` needed).
2. `agent-brain --transport mcp --mcp-transport http query "X" --state-dir <tmp>` (auto-discovers via `mcp.runtime.json`).
3. `agent-brain mcp stop --state-dir <tmp>`.

The runtime file IS guaranteed present after `mcp start` returns (Plan 58-02's `is_listening` contract).

## Next Phase Readiness

- **Plan 58-03 ready** — `mcp_group` is importable from `agent_brain_cli.commands.mcp`; appending `@mcp_group.command("stop")` to the same module is a 1-file change.
- **§3.5 wording swap ready** — `config.py:591-592` placeholder string is still in place. Plan 58-03 has the exact replacement.
- **No blockers** — `task before-push` exits 0 against HEAD; no flaky tests; no skipped tests.

## Self-Check: PASSED

- `agent-brain-cli/agent_brain_cli/commands/mcp.py` exists (302 lines, ≥180 required) ✓
- `agent-brain-cli/tests/test_mcp_start_command.py` exists (380 lines, ≥150 required) ✓
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` modified (re-exports mcp_group) ✓
- `agent-brain-cli/agent_brain_cli/cli.py` modified (registers mcp_group under "mcp") ✓
- Commit `152c305` on HEAD ✓ (`git log -1 --pretty=%s` → `feat(58-02): agent-brain mcp start subcommand (CLI-MCP-09)`)
- All 11 grep acceptance criteria pass ✓
- All 12 unit tests pass ✓ (`poetry run pytest tests/test_mcp_start_command.py -v` → 12 passed in 0.18s)
- `agent-brain mcp --help` exits 0 and shows `start` ✓
- `agent-brain mcp start --help` exits 0 and shows `--port`, `--start-timeout`, `--state-dir`, `--json` ✓
- `task before-push` exits 0 ✓

---

*Phase: 58-runtime-discovery-helper-commands*
*Plan: 02*
*Completed: 2026-06-07*
