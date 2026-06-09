---
phase: 60-subprocess-hygiene-1000-invocation-orphan-test
plan: 02
subsystem: infra
tags: [mcp, subprocess, hygiene, sigterm, sigkill, weakref, mcphyg-01]

# Dependency graph
requires:
  - phase: 60-subprocess-hygiene-1000-invocation-orphan-test
    plan: 01
    provides: env allowlist + cwd snapshot + grace_period_s persisted on McpStdioBackend.__init__
  - phase: 58-runtime-discovery-helper-commands
    provides: SIGTERM→poll→SIGKILL escalation precedent (psutil.pid_exists polling pattern)
  - phase: 57-cli-transport-selector-byte-identical-equivalence
    provides: 16 wired _async_* helpers using stdio_client(self._stdio_params()) (single swap surface)
provides:
  - _wait_for_subprocess_exit module helper (psutil-backed polling)
  - _process_has_exited module helper (returncode OR psutil.pid_exists check)
  - _extract_subprocess_from_streams duck-type extractor (soft-fail inside; E2E-guarded at wrapper)
  - McpStdioBackend._hygienic_stdio_client asynccontextmanager (per-call wrapper around SDK's stdio_client)
  - McpStdioBackend._register_inflight / _unregister_inflight tracker (threading.Lock-guarded weakref)
  - McpStdioBackend.close() SIGTERM→wait grace_period_s→SIGKILL escalation
  - Portable Python SIGTERM-ignoring stub child (tests/_stubs/ignore_sigterm.py) for SIGKILL escalation testing
affects: [60-03, 61-framework-matrix, 62-framework-matrix-extension]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - weakref.ref + threading.Lock pair for in-flight subprocess tracking (Pattern A invariant: 1 subprocess per backend at any moment)
    - asynccontextmanager method on the class for per-call wrapping (NOT a persistent connection refactor)
    - duck-type extraction with module-level helper + soft-fail boundary inside extractor + E2E test enforcement at wrapper level
    - psutil.pid_exists for kernel-level liveness check from sync code (Phase 58-03 _wait_for_pid_exit precedent)
    - portable Python stub child (no shell scripts) for SIGTERM-ignoring fixture (Phase 58 lock stale-pid stub precedent)

key-files:
  created:
    - agent-brain-mcp/tests/_stubs/__init__.py
    - agent-brain-mcp/tests/_stubs/ignore_sigterm.py
    - agent-brain-mcp/tests/test_subprocess_hygiene_close.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/client.py

key-decisions:
  - "_hygienic_stdio_client is an @asynccontextmanager METHOD on McpStdioBackend — drop-in replacement for stdio_client(params) inside each _async_* helper. Pattern A preserved: still fresh subprocess per call, no persistent-connection refactor."
  - "In-flight tracker uses weakref.ref + threading.Lock pair. Weakref so we never extend the SDK's subprocess lifecycle; Lock so close() from another thread cannot race the wrapper's registration."
  - "_extract_subprocess_from_streams walks (read, write) tuple checking write._process / write.process / write._transport for an asyncio.subprocess.Process-shaped object. Soft-fails to None INSIDE the extractor — that's correct (the SDK still tears down via its own context cleanup on the success path). The §3.5 no-silent-fallback contract is enforced at the WRAPPER LEVEL by test_hygienic_wrapper_registers_inflight_on_real_sdk_shape which drives the full extraction path through a faked SDK-shaped fixture."
  - "_wait_for_subprocess_exit / _process_has_exited check BOTH process.returncode AND psutil.pid_exists(process.pid). returncode alone is unreliable from sync code because close() runs OUTSIDE the asyncio event loop — the loop never updates returncode until a downstream `await process.wait()`. Phase 58-03 precedent: psutil.pid_exists is the kernel-level truth."
  - "ALL 16 _async_* helpers on McpStdioBackend swap to self._hygienic_stdio_client(self._stdio_params()) — verified by grep_c '_hygienic_stdio_client' returning 18 (1 docstring comment + 1 method def + 16 call sites). McpHttpBackend is NOT touched — different process model (HTTP listener owned by `agent-brain mcp start|stop` from Phase 58)."
  - "Test fake _FakeProcess class (NOT SimpleNamespace) for E2E extraction test because weakref.ref() requires the __weakref__ slot which SimpleNamespace lacks."

patterns-established:
  - "Pattern: asynccontextmanager method per-call wrapper around an SDK async cm (mirrors mcp.client.stdio.stdio_client signature)"
  - "Pattern: weakref + threading.Lock for in-flight subprocess tracking (at most ONE in-flight per backend invariant)"
  - "Pattern: duck-type extraction with soft-fail boundary + E2E test at wrapper level (the no-silent-fallback contract lives at the wrapper, not the extractor)"
  - "Pattern: psutil.pid_exists for sync-context kernel-level liveness check (Phase 58-03 carry-forward into Phase 60)"

requirements-completed: [MCPHYG-01]

# Metrics
duration: 13min
completed: 2026-06-08
---

# Phase 60 Plan 02: McpStdioBackend close() SIGTERM→SIGKILL escalation Summary

**Hygienic stdio_client wrapper + weakref-based in-flight subprocess tracker + close() SIGTERM/SIGKILL escalation honoring self.grace_period_s. All 16 _async_* helpers swap to the wrapper. MCPHYG-01 fully closed.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-06-09T03:40:31Z
- **Completed:** 2026-06-09T03:53:24Z
- **Tasks:** 4
- **Files modified:** 3 created + 1 modified

## Accomplishments

- `_hygienic_stdio_client` async context manager method landed on `McpStdioBackend` — drop-in replacement for `stdio_client(params)` that registers the spawned subprocess via `weakref.ref` on `self._inflight_ref` (guarded by `threading.Lock`) and unregisters on context exit. Pattern A preserved (no persistent-subprocess refactor — wrapper is a thin per-call wrap).
- `McpStdioBackend.close()` now escalates **SIGTERM → wait `self.grace_period_s` → SIGKILL** when an in-flight subprocess is registered. Idempotent fast path when nothing is in-flight. Safe to call from another thread while a sync method is mid-flight (threading.Lock guards the weakref).
- Module-level helpers `_wait_for_subprocess_exit` (polling) and `_process_has_exited` (returncode OR psutil.pid_exists check) handle the sync-context returncode reliability gap (see Deviations below).
- Module-level helper `_extract_subprocess_from_streams` walks the (read, write) tuple looking for an `asyncio.subprocess.Process`-shaped object on the write stream's transport. Soft-fails to None INSIDE the extractor — but the wrapper-level §3.5 no-silent-fallback contract is enforced by `test_hygienic_wrapper_registers_inflight_on_real_sdk_shape` which drives the full extraction path through a faked SDK-shaped fixture.
- All 16 `_async_*` helpers on `McpStdioBackend` swap to `self._hygienic_stdio_client(self._stdio_params())`. Verified by `grep -c '_hygienic_stdio_client'` returning 18 (1 docstring comment + 1 method def + 16 call sites). `McpHttpBackend` not touched — different process model.
- Portable SIGTERM-ignoring Python stub at `agent-brain-mcp/tests/_stubs/ignore_sigterm.py` with `signal.signal(SIGTERM, SIG_IGN)` + `READY` synchronization marker. No shell scripts.
- 11 unit tests pass across 6 classes at `tests/test_subprocess_hygiene_close.py` (288 lines) — exceeds plan's 10-test floor.
- `task before-push` exits 0 (544 passed, 110 deselected, 7 warnings; 88% coverage on agent-brain-mcp).

## Task Commits

Each task was committed atomically:

1. **Task 1: SIGTERM-ignoring Python stub child** — `cdcf089` (test)
2. **Task 2: Hygienic wrapper + in-flight tracker + close() escalation** — `7967764` (feat)
3. **Task 3: Unit tests + Rule 1 sync-context returncode fix** — `1aa6f1e` (test)
4. **Task 4: Cross-package backward-compat verification** — no source change required (65/65 Phase 57 + 59 + 60-01 + 60-02 wire tests green; `task before-push` exits 0). Captured in the plan-metadata commit below.

**Plan metadata:** captured in the SUMMARY + STATE + ROADMAP + REQUIREMENTS docs commit.

## Files Created/Modified

- `agent-brain-mcp/agent_brain_mcp/client.py` (modified) — added `import threading`, `import weakref`, `from collections.abc import AsyncIterator`, `from contextlib import asynccontextmanager`. Added module-level helpers `_process_has_exited`, `_wait_for_subprocess_exit`, `_extract_subprocess_from_streams`. Added `_inflight_ref` (`weakref.ref[Any] | None`) + `_inflight_lock` (`threading.Lock`) fields on `__init__`. Added `_register_inflight`, `_unregister_inflight`, `_hygienic_stdio_client` methods. Rewrote `close()` with SIGTERM → wait `grace_period_s` → SIGKILL escalation. Swapped all 16 `_async_*` helpers from `stdio_client(self._stdio_params())` to `self._hygienic_stdio_client(self._stdio_params())`. Removed 16 now-unused `from mcp.client.stdio import stdio_client` imports inside helpers (ruff --fix). +169/-35 lines net.
- `agent-brain-mcp/tests/_stubs/__init__.py` (created, 1 line) — marks `_stubs/` a regular package.
- `agent-brain-mcp/tests/_stubs/ignore_sigterm.py` (created, 42 lines) — Python stub child that ignores SIGTERM, sleeps, prints `READY` marker.
- `agent-brain-mcp/tests/test_subprocess_hygiene_close.py` (created, 246 lines after Black) — 11 tests across 6 classes:
  - `TestCloseIdempotency` (2): `close()` no-op on fresh backend; double-close safe
  - `TestWaitForSubprocessExit` (2): timeout honored + exits-fast paths
  - `TestExtractSubprocessFromStreams` (3): duck-type extraction success + 2 soft-fail boundaries
  - `TestCloseEscalationRealSubprocess` (2): real-subprocess SIGTERM happy path + SIGKILL escalation against the `ignore_sigterm.py` stub
  - `TestPatternAPreservation` (1): `close()` does NOT poison `_stdio_params`
  - `TestHygienicWrapperRealSdkShape` (1): E2E extraction guard for §3.5 no-silent-fallback contract

## Decisions Made

- **`_hygienic_stdio_client` as `@asynccontextmanager` method (not a class):** keeps the wrapper API a drop-in replacement for `stdio_client(params)` — same `async with` usage, same yield shape. A class with `__aenter__`/`__aexit__` would have worked too, but the `@asynccontextmanager` decorator is the minimal-surface idiom.
- **`weakref.ref` + `threading.Lock`:** weakref so we never extend the SDK's subprocess lifecycle (Pattern A invariant: SDK owns the subprocess; we just register a handle for `close()` escalation). Lock so a cross-thread `close()` cannot race the wrapper's registration. Pattern A invariant means at most ONE in-flight subprocess per backend at any moment.
- **`_extract_subprocess_from_streams` soft-fails inside extractor; §3.5 contract enforced at wrapper level by E2E test:** the SDK 1.12.x line stores the process on the write stream's transport. If a future SDK version shifts the shape, the extractor returns None and Pattern A still tears down via the SDK's normal context cleanup — correct, just no SIGKILL escalation. The §3.5 no-silent-fallback contract is enforced by `test_hygienic_wrapper_registers_inflight_on_real_sdk_shape` which drives a faked SDK-shaped fixture through the FULL wrapper path and asserts `_inflight_ref` is non-None inside the with-block.
- **Pattern A preservation:** the wrapper is per-call. Each `_async_*` helper still opens `self._hygienic_stdio_client(self._stdio_params())` → spawns a fresh subprocess → closes it on context exit. No persistent connection. `close()` only matters for the rare race where a caller invokes it FROM ANOTHER THREAD while a sync method is mid-flight on the main thread.
- **psutil.pid_exists for sync-context liveness:** `asyncio.subprocess.Process.returncode` updates only when the asyncio event loop reaps the child. `close()` runs OUTSIDE the loop (sync facade), so returncode-only checks return None even after the OS killed the process. Phase 58-03 `_wait_for_pid_exit` already used `psutil.pid_exists` for the same reason; we adopt the precedent.
- **`_FakeProcess` class (not SimpleNamespace) in tests:** `weakref.ref()` requires the `__weakref__` slot which `SimpleNamespace` lacks. Trivial class with `returncode`, `terminate`, `kill` attrs is the minimum to satisfy both the duck-type extractor AND the weakref registration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed sync-context returncode reliability bug discovered by Task 3 real-subprocess tests**

- **Found during:** Task 3 (first pytest run after wiring tests)
- **Issue:** `_wait_for_subprocess_exit` polled only `process.returncode`. `asyncio.subprocess.Process.returncode` updates only when the asyncio event loop reaps the child. `close()` runs sync OUTSIDE the asyncio loop, so even after `process.terminate()` succeeded at the OS level, the returncode-only check returned False (still alive). Both real-subprocess escalation tests failed: SIGTERM-happy-path test asserted `process.returncode is not None` but it was still None; SIGKILL-escalation test had the same shape. The Pattern A invariant was correct (subprocess terminated) but the polling helper couldn't observe it.
- **Fix:** Added module-level `_process_has_exited(process)` helper that checks BOTH `process.returncode` AND `psutil.pid_exists(process.pid)`. Real `asyncio.subprocess.Process` has a `pid` attr; SimpleNamespace fakes that lack `pid` fall back to the returncode check. `_wait_for_subprocess_exit` and `close()`'s early-return both route through `_process_has_exited`. Tests updated to use `psutil.pid_exists` for the kernel-level assertion + `await process.wait()` for the returncode assertion (after which asyncio learns the exit code).
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/client.py` (added `_process_has_exited` helper + updated `_wait_for_subprocess_exit` + updated `close()` early-return path), `agent-brain-mcp/tests/test_subprocess_hygiene_close.py` (tests use psutil.pid_exists + `await process.wait()` instead of bare `returncode` checks).
- **Commit:** `1aa6f1e` (folded into Task 3 commit since the bug was discovered by the new tests).

**2. [Rule 1 - Bug] Replaced `SimpleNamespace` with `_FakeProcess` class for E2E test fixture**

- **Found during:** Task 3 (E2E test TypeError on first pytest run)
- **Issue:** `weakref.ref()` requires the `__weakref__` slot. `SimpleNamespace` lacks it. The E2E test failed with `TypeError: cannot create weak reference to 'types.SimpleNamespace' object` when `_register_inflight` tried to `weakref.ref(fake_process)`.
- **Fix:** Added a tiny `_FakeProcess` class at the test file top with `__init__(returncode)` + `terminate()` + `kill()` methods. Default `__dict__` instance class supports weakref. Replaced `SimpleNamespace(returncode=..., terminate=..., kill=...)` with `_FakeProcess(returncode=...)`. Other fakes (the `fake_write = SimpleNamespace(_process=fake_process)`) stay as SimpleNamespace — they don't need weakref.
- **Files modified:** `agent-brain-mcp/tests/test_subprocess_hygiene_close.py` (added `_FakeProcess` class + updated `test_hygienic_wrapper_registers_inflight_on_real_sdk_shape` to use it).
- **Commit:** `1aa6f1e` (folded into Task 3 commit).

### Other deviations

- **Ruff UP035 + 16 F401 unused-import fixes:** after swapping all `_async_*` helpers to use the wrapper, ruff flagged 16 `from mcp.client.stdio import stdio_client` imports inside the helpers as unused (the wrapper now owns the import). Also flagged `typing.AsyncIterator` as UP035 (use `collections.abc.AsyncIterator` instead). Both fixed via `ruff check --fix` + manual import-block rewrite. No semantic change. Ruff + Black + mypy strict all clean.
- **No prior-phase wire-test patch-path inversions needed:** existing Phase 57 + 59 wire tests already patched `mcp.client.stdio.stdio_client` (the module-level symbol) rather than the per-helper import. Since `_hygienic_stdio_client` also imports `stdio_client` from the same module-level symbol, the patches resolve correctly without any test changes. All 54 Phase 57 + 59 wire tests green unchanged.

## Issues Encountered

- **Two Rule 1 bugs discovered by the new tests (see Deviations above).** Both fixed inline; commit message documents the root cause + fix.
- **No issues with `task before-push`** — 544 passed, 0 failures, 7 warnings (preexisting), 88% coverage on agent-brain-mcp.

## User Setup Required

None — no external service configuration required. All changes are internal to `agent-brain-mcp` package surface.

## Authentication Gates

None encountered.

## Verification Evidence

```
$ cd agent-brain-mcp && poetry run pytest tests/test_subprocess_hygiene_close.py -v
============================== 11 passed in 1.24s ==============================

$ cd agent-brain-mcp && poetry run pytest tests/test_cli_backends_skeleton.py \
    tests/test_cli_backends_query_wire.py tests/test_cli_backends_methods_wire.py \
    tests/test_mcp_backend_prompts_wire.py tests/test_subprocess_hygiene_init.py \
    tests/test_subprocess_hygiene_close.py
====================== 65 passed, 14 deselected in 9.08s =======================

$ task before-push
... 544 passed, 110 deselected, 7 warnings in 23.71s ...
--- All checks passed - Ready to push ---
[exit code 0]

$ grep -c "_hygienic_stdio_client" agent-brain-mcp/agent_brain_mcp/client.py
18  # 1 docstring comment + 1 @asynccontextmanager method def + 16 call sites

$ grep -c "import weakref" agent-brain-mcp/agent_brain_mcp/client.py
1

$ grep -c "import threading" agent-brain-mcp/agent_brain_mcp/client.py
1

$ grep -c "process.terminate()" agent-brain-mcp/agent_brain_mcp/client.py
2

$ grep -c "process.kill()" agent-brain-mcp/agent_brain_mcp/client.py
2

$ grep -c "self.grace_period_s" agent-brain-mcp/agent_brain_mcp/client.py
3

$ grep -c "_inflight_ref" agent-brain-mcp/agent_brain_mcp/client.py
5
```

## Next Phase Readiness

- **Plan 60-03** (1000-invocation orphan stress test) now has a CORRECT teardown primitive. Without escalation, the stress test could zombie on ignored-SIGTERM children. The `_hygienic_stdio_client` wrapper + `close()` escalation give the stress test a clean tear-down primitive: each iteration's `with backend:` (or explicit `backend.close()`) handles both well-behaved AND ignored-SIGTERM subprocesses.
- **Phase 61-62** (framework matrix smoke tests) get the contract for free by going through `McpStdioBackend` rather than spawning raw subprocesses. Every framework's test client inherits `cwd` pinning + env allowlist (60-01) + SIGTERM→SIGKILL escalation (60-02).

## Self-Check: PASSED

- FOUND: `agent-brain-mcp/agent_brain_mcp/client.py`
- FOUND: `agent-brain-mcp/tests/_stubs/__init__.py`
- FOUND: `agent-brain-mcp/tests/_stubs/ignore_sigterm.py`
- FOUND: `agent-brain-mcp/tests/test_subprocess_hygiene_close.py`
- FOUND commit: `cdcf089` (test: SIGTERM-ignoring Python stub child)
- FOUND commit: `7967764` (feat: hygienic stdio wrapper + close() escalation)
- FOUND commit: `1aa6f1e` (test: close() escalation tests + sync-context returncode bug fix)

---

*Phase: 60-subprocess-hygiene-1000-invocation-orphan-test*
*Completed: 2026-06-08*
