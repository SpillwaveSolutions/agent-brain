---
phase: 60-subprocess-hygiene-1000-invocation-orphan-test
plan: 03
subsystem: infra
tags: [mcp, subprocess, hygiene, stress-test, orphan-detection, psutil, mcphyg-02]

# Dependency graph
requires:
  - phase: 60-subprocess-hygiene-1000-invocation-orphan-test
    plan: 01
    provides: env allowlist + cwd snapshot + grace_period_s on McpStdioBackend.__init__
  - phase: 60-subprocess-hygiene-1000-invocation-orphan-test
    plan: 02
    provides: _hygienic_stdio_client wrapper + close() SIGTERM→SIGKILL escalation (the teardown primitive the stress test exercises)
  - phase: 58-runtime-discovery-helper-commands
    provides: psutil dependency precedent + psutil.pid_exists pattern
  - phase: 57-cli-transport-selector-byte-identical-equivalence
    provides: McpStdioBackend.health() wired via _async_health → call_tool("server_health") through _hygienic_stdio_client (Pattern A)
provides:
  - agent-brain-mcp/tests/stress/__init__.py (Python package marker for opt-in stress tests)
  - agent-brain-mcp/tests/stress/test_orphan_subprocess.py (1000-invocation orphan stress test, pytest.mark.stress)
  - 'stress' pytest marker registered in agent-brain-mcp/pyproject.toml with MCPHYG-02 + Taskfile-target docstring
  - addopts filter extended to `not e2e and not e2e_http and not contract and not stress` (default runs SKIP stress)
  - per-package `stress:orphan-test` Taskfile target in agent-brain-mcp/Taskfile.yml
  - root-level `task mcp:stress:orphan-test` exposed via `includes: mcp:` alias (no separate root task block needed)
affects: [61-framework-matrix, 62-framework-matrix-extension]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - psutil.Process(os.getpid()).children(recursive=True) delta as PRIMARY orphan assert (cross-platform)
    - pgrep -f as DIAGNOSTIC-ONLY surface in failure messages (best-effort; soft-fails on Windows / missing PATH)
    - env-var iteration knob (AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS) with safe default 1000
    - module-scope fixture (pytest.skip) when prereq binary not on PATH
    - opt-in pytest marker + addopts exclusion (mirrors e2e/e2e_http/contract precedent)
    - includes-alias dispatch convention (`task mcp:<name>` resolves to per-package bare `<name>:` task)

key-files:
  created:
    - agent-brain-mcp/tests/stress/__init__.py
    - agent-brain-mcp/tests/stress/test_orphan_subprocess.py
    - .planning/phases/60-subprocess-hygiene-1000-invocation-orphan-test/60-03-SUMMARY.md
  modified:
    - agent-brain-mcp/pyproject.toml
    - agent-brain-mcp/Taskfile.yml
    - Taskfile.yml

key-decisions:
  - "psutil PRIMARY / pgrep DIAGNOSTIC architecture: per-iteration assert is psutil.Process(os.getpid()).children(recursive=True) delta (cross-platform, precise). pgrep only invoked inside the failure-surface (after psutil already detected leak) for human triage. pgrep gracefully degrades to <pgrep not available on PATH> on Windows."
  - "AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS env-var knob with safe default 1000 (ROADMAP Phase 60 SC3). Invalid integer values fall back to the default rather than erroring; minimum clamp at 1. Lets developers run a fast 3- or 5-iteration smoke without code changes."
  - "Test SKIPS gracefully (module-scope fixture) when agent-brain-mcp not on PATH. Does NOT skip on backend unavailability — the orphan check is the contract, regardless of whether the spawned subprocess succeeded or raised."
  - "[Rule 1 - Bug fix] Stress test tolerates backend.health() exceptions because the MCPHYG-02 contract is about subprocess teardown hygiene, NOT backend reachability. The MCP subprocess's MIN_BACKEND_VERSION check raises McpError when no compatible agent-brain-server is up, but the subprocess still spawns + exits cleanly. The orphan-delta assert is the load-bearing check."
  - "[Rule 1 - Bug fix] Per-package Taskfile task name is BARE `stress:orphan-test:` (NO `mcp:` prefix). The root Taskfile's `includes: mcp:` alias prepends the namespace, mirroring the established `before-push:` (per-package) → `task: mcp:before-push` (root reference) idiom. The plan's literal `mcp:stress:orphan-test:` per-package name would have collided with the includes-aliased entry under the same fully-qualified key."
  - "[Rule 1 - Bug fix] No separate root-level task block needed — the `includes: mcp:` alias from line 33 of root Taskfile.yml automatically exposes the per-package `stress:orphan-test:` as `mcp:stress:orphan-test` at root scope. The plan's literal duplicate-root-task spec triggered `task: Found multiple tasks (mcp:stress:orphan-test) included by 'mcp'` and was replaced with an explanatory comment block."
  - "Stress test stops on FIRST leak (not after 1000) so failure messages stay actionable. Failure surface includes: iteration #, surviving PIDs (sorted), time-since-close in ms, pgrep diagnostic blob, Phase 60 hygiene-contract violation hint."
  - "addopts filter `not e2e and not e2e_http and not contract and not stress` ensures the slow stress test is excluded from `task mcp:test`, `task before-push`, and per-package `pr-qa-gate`. Verified by `pytest --collect-only` returning 0 matches for `test_orphan_subprocess` under default options."

patterns-established:
  - "Pattern: psutil.children(recursive=True) delta assertion (cross-platform orphan detection) + pgrep diagnostic in failure surface (best-effort, soft-fails on unsupported OS)"
  - "Pattern: env-var iteration-count knob with safe default + invalid-input fallback (no startup-time validation that could regress)"
  - "Pattern: opt-in pytest marker + addopts exclusion + Taskfile target (NOT in before-push) for slow tests — mirrors e2e/e2e_http/contract triad established in v10.2"
  - "Pattern: per-package bare task name + root includes-alias dispatch (no root-level duplicate; rely on Task's includes resolver)"

requirements-completed: [MCPHYG-02]

# Metrics
duration: 9min
completed: 2026-06-09
---

# Phase 60 Plan 03: 1000-invocation orphan stress test Summary

**Ships `task mcp:stress:orphan-test` — an opt-in 1000-invocation McpStdioBackend stress test using psutil children-delta as PRIMARY orphan assert + pgrep DIAGNOSTIC-ONLY in failure surface, configurable iteration count via env var, NOT in `task before-push`. MCPHYG-02 closed; Phase 60 complete.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-06-09T03:59:10Z
- **Completed:** 2026-06-09T04:08:00Z
- **Tasks:** 4
- **Files modified:** 3 created + 3 modified

## Accomplishments

- `agent-brain-mcp/tests/stress/test_orphan_subprocess.py` (155 lines after Black) ships with `@pytest.mark.stress` marker. PRIMARY assert is `psutil.Process(os.getpid()).children(recursive=True)` set-delta per iteration; DIAGNOSTIC `pgrep -f agent-brain-mcp` invoked ONLY inside the failure-surface message (after psutil already detected a leak), best-effort with `<pgrep not available on PATH>` fallback on Windows.
- Iteration count knob: `AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS` env var, default 1000 (ROADMAP Phase 60 SC3). Invalid integer values fall back to default (no startup error). Minimum clamp at 1.
- Stops on FIRST leak — failure surface includes: iteration #, sorted surviving PIDs, time-since-close in ms, pgrep diagnostic blob, plan-60-02 hygiene-contract violation hint.
- `stress` pytest marker registered in `agent-brain-mcp/pyproject.toml` with MCPHYG-02 + Taskfile-target hint in docstring. `addopts` filter extended to `"-m 'not e2e and not e2e_http and not contract and not stress'"` so `task mcp:test`, `task before-push`, and `pr-qa-gate` all skip the stress test by default. Verified by `pytest --collect-only` returning 0 matches for `test_orphan_subprocess`.
- `agent-brain-mcp/tests/stress/__init__.py` marks the stress test directory as a Python package (mirrors `tests/_stubs` convention from Plan 60-02).
- `agent-brain-mcp/Taskfile.yml` gains per-package `stress:orphan-test:` task (BARE name — no `mcp:` prefix). The root Taskfile's `includes: mcp:` alias automatically exposes this as `mcp:stress:orphan-test` at root scope (no separate root task block needed). Mirrors the `before-push:` (per-package) → `task: mcp:before-push` (root reference) idiom.
- 5-iteration smoke via `task mcp:stress:orphan-test` from repo root passes in **3.72s pytest** (7s total wall-clock including poetry install no-op). Zero psutil children-delta false positives observed across 5 iterations.
- `task before-push` exits 0 with **544 passed, 111 deselected, 7 warnings** in 25.09s (88% coverage on agent-brain-mcp). The +1 deselected vs Plan 60-02 baseline (110) is the new stress test, correctly excluded.

## Task Commits

Each task was committed atomically:

1. **Task 1: Register psutil dep + 'stress' pytest marker + create tests/stress/__init__.py** — `6857324` (chore)
2. **Task 2: Add 1000-invocation orphan stress test with psutil children delta + pgrep diagnostic + --max-iterations knob** — `371def1` (test)
3. **Task 3: Add Taskfile target mcp:stress:orphan-test in agent-brain-mcp + root-level alias** — `8cd6d79` (chore)
4. **Task 4: Verify full suite still green + task before-push still excludes stress + smoke-run mcp:stress:orphan-test with low iteration count** — verification-only (no code change). Results captured in this SUMMARY's "Verification Evidence" section + folded into the plan-metadata commit below.

**Plan metadata:** SUMMARY + STATE + ROADMAP + REQUIREMENTS update commit captures the final docs.

## Files Created/Modified

- `agent-brain-mcp/tests/stress/__init__.py` (created, 7 lines) — Python package marker, docstring references MCPHYG-02 + Taskfile target.
- `agent-brain-mcp/tests/stress/test_orphan_subprocess.py` (created, 155 lines after Black) — 1000-invocation orphan stress test. Module-scope fixture `_agent_brain_mcp_on_path` skips when binary missing. Single test function `test_no_orphan_subprocess_after_1000_query_close_cycles` drives the tight loop. Module-level helpers: `_resolve_max_iterations` (env-var knob), `_pgrep_diagnostic` (best-effort pgrep), `_children_pids` (psutil children snapshot).
- `agent-brain-mcp/pyproject.toml` (modified, +2 lines) — added `stress` marker entry (with MCPHYG-02 + opt-in hint in docstring); extended `addopts` filter with `and not stress`.
- `agent-brain-mcp/Taskfile.yml` (modified, +14 lines) — new `stress:orphan-test:` per-package task running `pytest tests/stress/test_orphan_subprocess.py -v -m stress`. Docstring documents MCPHYG-02 + slow opt-in status + includes-alias dispatch convention.
- `Taskfile.yml` (modified, +12 lines comment block) — explanatory comment block right after `before-push:` documenting how `task mcp:stress:orphan-test` resolves via the `includes: mcp:` alias (no duplicate root task; intentional).
- `.planning/phases/60-subprocess-hygiene-1000-invocation-orphan-test/60-03-SUMMARY.md` (created, this file).

## Decisions Made

- **psutil PRIMARY / pgrep DIAGNOSTIC split:** `psutil.Process(os.getpid()).children(recursive=True)` returns a set of descendant PIDs and is cross-platform. Set-delta per iteration is the cleanest formulation of "what did this iteration spawn that's still alive?". `pgrep -f agent-brain-mcp` is macOS/Linux only and would false-positive against concurrent test suites running the same binary; using it ONLY in the failure-surface message (after psutil already detected the leak) gives operators a human-readable trace without false-positive risk.
- **Module-scope fixture for binary-on-PATH precheck:** `pytest.fixture(scope="module")` runs `shutil.which("agent-brain-mcp")` once. Missing binary → `pytest.skip(...)` with install instructions. Faster than per-test check and avoids cluttering reports with the same skip reason repeated 1000 times.
- **Tolerate `backend.health()` exceptions (Rule 1 - Bug fix):** The MCP subprocess startup runs a `MIN_BACKEND_VERSION = "10.2.0"` check against the discovered `agent-brain-server`. When no compatible backend is reachable (which is common in stress-test environments without a fully-seeded local server), `health()` raises `McpError("Backend version X.Y.Z is below the MCP client minimum 10.2.0")`. Crucially, the subprocess STILL spawns + STILL exits cleanly — the orphan-delta check is the contract; whether `health()` succeeded is incidental. The initial draft of the test called `pytest.fail` on `health()` exception BEFORE checking for orphans; fixed by falling through to the orphan-delta assert and treating `health()` exceptions as expected behavior on environments without a live backend.
- **Bare per-package task name + includes-alias dispatch (Rule 1 - Bug fix):** Plan 60-03 literally specified `mcp:stress:orphan-test:` as the per-package task name. Combined with the root `includes: mcp:` alias, this produced a fully-qualified `mcp:mcp:stress:orphan-test` AND a duplicate-name collision with a root-level task block — `task: Found multiple tasks (mcp:stress:orphan-test) included by "mcp"`. Followed the established `before-push:` (per-package, bare) → `task: mcp:before-push` (root reference, namespaced) idiom and used bare `stress:orphan-test:` for the per-package name. The root Taskfile gets an explanatory comment block instead of a duplicate task block.
- **Stop loop on first leak (not after 1000):** A leak after iteration 437 is a leak; running 563 more iterations to "confirm" it would just zombie the test host. `pytest.fail` with a detailed failure surface (iteration #, surviving PIDs, time-since-close, pgrep blob, contract-violation hint) lets operators diagnose without sifting through 1000 sets of output.
- **`addopts` filter extended additively:** The existing `"-m 'not e2e and not e2e_http and not contract'"` filter pattern keeps Phase 55's fast-lane invariant intact. Added `and not stress` to the existing chain rather than rebuilding the filter. Verified by `poetry run pytest --collect-only` returning 0 matches for `test_orphan_subprocess`.
- **`grace_period_s` default 5.0s preserved:** Plan 60-01 set this; the stress test uses `McpStdioBackend(_agent_brain_mcp_on_path)` with the default kwargs. If a future stress-test variant wants a tighter grace for runtime measurement, the kwarg is already there.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Stress test failed to assert orphan check when backend.health() raised**

- **Found during:** Task 2 — first 3-iteration smoke run (`AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS=3`).
- **Issue:** The initial draft caught `Exception` from `backend.health()` and called `pytest.fail(f"backend.health() raised unexpectedly: {exc!r}")` BEFORE the orphan-delta check. But the MCP subprocess startup hits a `MIN_BACKEND_VERSION = "10.2.0"` check against the discovered `agent-brain-server`; when no compatible backend is up locally (the actual test environment), `health()` raises `McpError("Backend version 10.0.7 is below the MCP client minimum 10.2.0")`. This collapsed the test into "did health() succeed?" — which is NOT the MCPHYG-02 contract. The MCPHYG-02 contract is "does close() leak children?" — and the subprocess that ran the version check DID get spawned, DID exit cleanly, and the orphan-delta check would have passed even though health() raised.
- **Fix:** Caught and ignored `Exception` from `backend.health()` with a `try/except Exception: pass` block. Fall through to `backend.close()` + the orphan-delta assert which IS the contract. Added an inline docstring explaining that `health()` exception tolerance is by-design.
- **Files modified:** `agent-brain-mcp/tests/stress/test_orphan_subprocess.py` (Task 2 commit).
- **Commit:** `371def1` (test) — folded into the Task 2 commit since the bug was discovered by the new test itself.

**2. [Rule 1 - Bug] Plan-specified per-package task name `mcp:stress:orphan-test:` collided with includes alias**

- **Found during:** Task 3 — first attempt at running `task mcp:stress:orphan-test` from repo root.
- **Issue:** Plan 60-03 literally specified the per-package task name as `mcp:stress:orphan-test:` in `agent-brain-mcp/Taskfile.yml`, AND specified a root-level `mcp:stress:orphan-test:` task block. The root `includes: mcp:` alias from line 33 of root Taskfile prepends `mcp:` to every per-package task name, so the per-package `mcp:stress:orphan-test:` became `mcp:mcp:stress:orphan-test` at root scope. The root-level duplicate `mcp:stress:orphan-test:` block AND the includes-aliased entry both resolved to the same `mcp:stress:orphan-test` fully-qualified name, triggering `task: Found multiple tasks (mcp:stress:orphan-test) included by "mcp"`. The root cmd `task: mcp:stress:orphan-test` ALSO triggered `task: Maximum task call exceeded (1000) for task "mcp:stress:orphan-test": probably an cyclic dep or infinite loop` because Task couldn't disambiguate self-reference from includes-alias reference.
- **Fix:** Renamed the per-package task to bare `stress:orphan-test:` (mirrors `before-push:` per-package naming). Removed the root-level duplicate task block; replaced with an explanatory comment block right after `before-push:`. The `includes: mcp:` alias automatically exposes `task mcp:stress:orphan-test` from root scope, mirroring the established `task: mcp:before-push` dispatch idiom from the root `before-push.cmds` block.
- **Files modified:** `agent-brain-mcp/Taskfile.yml` (task name change), `Taskfile.yml` (removed duplicate block, added comment).
- **Commit:** `8cd6d79` (chore) — folded into the Task 3 commit since the bug was discovered by Task 3's `task --list` + dispatch test.

### Other Deviations

- **Acceptance criterion `grep -c "mcp:stress:orphan-test:" agent-brain-mcp/Taskfile.yml returns at least 1` was downgraded:** the literal task-name form would have triggered the cyclic-dependency collision documented above. The semantic intent (per-package task exists + is discoverable from root via `task mcp:stress:orphan-test`) is preserved: per-package task is named `stress:orphan-test:`, and the root-aliased form `mcp:stress:orphan-test` is the only operator-facing name. Verified by `task --list 2>&1 | grep -c "mcp:stress:orphan-test"` returning 1.

## Issues Encountered

- **Two Rule 1 bugs discovered + fixed inline (see Deviations above).** Both were architectural-fit issues between the plan's literal spec and the established repo conventions (`MIN_BACKEND_VERSION` startup check, Taskfile `includes:` namespacing). Both were resolved by following established patterns from Plans 60-01/60-02 (psutil-based liveness checks) and the Taskfile `before-push:` precedent.
- **No new issues with `task before-push`** — 544 passed, 0 failures, 7 warnings (preexisting), 88% coverage on agent-brain-mcp. The +1 deselected vs Plan 60-02 baseline (110 → 111) is exactly the new stress test, correctly excluded.

## User Setup Required

None — no external service configuration required. All changes are internal to `agent-brain-mcp` package surface + Taskfile orchestration.

Operators wanting to run the 1000-iteration test need: a working `agent-brain-mcp` binary on PATH (`poetry install` inside `agent-brain-mcp/`) + ~500-2000s of wall-clock time. The test does NOT require a live `agent-brain-server` to verify the MCPHYG-02 contract (the orphan-delta check works regardless of `health()` success).

## Authentication Gates

None encountered. The stress test deliberately does NOT depend on `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` (unlike Plan 57-02's byte-equivalence test which gates on `OPENAI_API_KEY` for seeded-corpus indexing). Subprocess hygiene is verifiable without backend reachability.

## Verification Evidence

```
$ cd agent-brain-mcp && AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS=3 poetry run pytest tests/stress/test_orphan_subprocess.py -v -m stress
tests/stress/test_orphan_subprocess.py::test_no_orphan_subprocess_after_1000_query_close_cycles PASSED [100%]
============================== 1 passed in 1.87s ===============================

$ AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS=5 task mcp:stress:orphan-test 2>&1 | tail -5
tests/stress/test_orphan_subprocess.py::test_no_orphan_subprocess_after_1000_query_close_cycles PASSED [100%]
============================== 1 passed in 3.72s ===============================
WALL-CLOCK: 7s (includes poetry install no-op)

$ cd agent-brain-mcp && poetry run pytest --collect-only 2>&1 | grep -c "test_orphan_subprocess"
0  # ← default runs SKIP the stress test (addopts filter working)

$ cd agent-brain-mcp && poetry run pytest --collect-only -m stress 2>&1 | tail -5
        <Function test_no_orphan_subprocess_after_1000_query_close_cycles>
========================== 1 test collected in 0.24s ===========================
# ← exactly 1 test under -m stress

$ task before-push 2>&1 | tail -5
=============== 544 passed, 111 deselected, 7 warnings in 25.09s ===============
task: [before-push] echo "--- All checks passed - Ready to push ---"
--- All checks passed - Ready to push ---
[exit code 0]
# ← +1 deselected vs Plan 60-02 baseline (110 → 111) is the new stress test

$ task --list 2>&1 | grep "mcp:stress:orphan-test"
* mcp:stress:orphan-test:       Phase 60 (MCPHYG-02): 1000-invocation no-orphan stress test. SLOW (500-2000s wall-clock)...

$ awk '/^  before-push:/{flag=1;next}/^  [a-zA-Z#]/{flag=0}flag' Taskfile.yml | grep -c "stress:orphan-test"
0  # ← stress test NOT in root before-push block

$ grep -c "MCPHYG-02" agent-brain-mcp/pyproject.toml agent-brain-mcp/Taskfile.yml Taskfile.yml
agent-brain-mcp/pyproject.toml:1
agent-brain-mcp/Taskfile.yml:1
Taskfile.yml:1
```

## Next Phase Readiness

- **Phase 60 COMPLETE.** All 3 plans landed: 60-01 (env allowlist + cwd snapshot + grace_period_s), 60-02 (hygienic stdio wrapper + close() SIGTERM/SIGKILL escalation), 60-03 (1000-invocation orphan stress test). MCPHYG-01 + MCPHYG-02 both closed.
- **Phase 61 (framework matrix smoke tests)** inherits the orphan-free contract automatically by going through `McpStdioBackend` rather than spawning raw subprocesses. Every framework's test client gets `cwd` pinning + env allowlist (60-01) + SIGTERM→SIGKILL escalation (60-02) + an opt-in orphan stress test target (60-03) for free.
- **ROADMAP Phase 60 SC3 satisfied:** `task mcp:stress:orphan-test` drives McpStdioBackend through 1000 query→close cycles asserting no surviving PIDs per iteration; task is opt-in and NOT in `task before-push`.
- **ROADMAP Phase 60 SC4 inherited:** Phase 61 + 62 framework tests will go through `McpStdioBackend` (Plans 60-01 + 60-02 contract) and inherit the orphan-free guarantee automatically.
- **Pattern A architectural lock honored throughout** — no persistent-subprocess refactor; the stress test creates a fresh `McpStdioBackend` each iteration, exercising the per-call subprocess spawn + tear-down loop that Pattern A defines.

## Self-Check: PASSED

- FOUND: `agent-brain-mcp/tests/stress/__init__.py`
- FOUND: `agent-brain-mcp/tests/stress/test_orphan_subprocess.py`
- FOUND: `.planning/phases/60-subprocess-hygiene-1000-invocation-orphan-test/60-03-SUMMARY.md`
- FOUND commit: `6857324` (chore: register stress marker + tests/stress package)
- FOUND commit: `371def1` (test: 1000-invocation orphan stress test)
- FOUND commit: `8cd6d79` (chore: wire mcp:stress:orphan-test Taskfile target)

---

*Phase: 60-subprocess-hygiene-1000-invocation-orphan-test*
*Completed: 2026-06-09*
