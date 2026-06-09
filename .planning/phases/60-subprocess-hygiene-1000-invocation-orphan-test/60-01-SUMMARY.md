---
phase: 60-subprocess-hygiene-1000-invocation-orphan-test
plan: 01
subsystem: infra
tags: [mcp, subprocess, hygiene, env-allowlist, cwd, security, mcphyg-01]

# Dependency graph
requires:
  - phase: 56-design-doc-cli-backend-skeleton
    provides: McpStdioBackend class location + sync facade pattern (Pattern A)
  - phase: 57-cli-transport-selector-byte-identical-equivalence
    provides: 10 wired methods through _stdio_params chokepoint (single point for env injection)
  - phase: 58-runtime-discovery-helper-commands
    provides: 5s grace_period precedent + psutil dependency
  - phase: 59-cli-prompts-resources-commands
    provides: McpBackend Protocol shape (no __enter__/__exit__ for stdio backend)
provides:
  - DEFAULT_ENV_ALLOWLIST module constant (6 POSIX keys + documented AGENT_BRAIN_API_KEY auto-forward)
  - Extended McpStdioBackend.__init__ with env_allowlist, forward_env, grace_period_s kwargs
  - cwd snapshot at __init__ (predictable subprocess working dir)
  - Explicit cwd validation (fail-fast ValueError on missing or non-directory)
  - _effective_env() helper — env filter chokepoint feeding _stdio_params
  - grace_period_s persisted at __init__ (consumed by Plan 60-02 close() escalation)
affects: [60-02, 60-03, 61-framework-matrix, 62-framework-matrix-extension]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - frozenset module constant + constructor override (mirrors agent_brain_server/security/file_sandbox.py:85)
    - explicit forward_env opt-in (vs. silent inheritance)
    - construction-time fail-fast validation (cwd existence/dir check, grace_period > 0)
    - single chokepoint env filtering at _stdio_params (10 wired methods inherit hygiene automatically)

key-files:
  created:
    - agent-brain-mcp/tests/test_subprocess_hygiene_init.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/client.py

key-decisions:
  - "DEFAULT_ENV_ALLOWLIST = frozenset({PATH, HOME, USER, LANG, LC_ALL, TERM}) — smallest surface that keeps Python startup + locale working cross-platform"
  - "AGENT_BRAIN_API_KEY auto-forwards in _effective_env (v10.2.1 SECURITY-01 carryover); OPENAI_API_KEY / ANTHROPIC_API_KEY require explicit forward_env opt-in"
  - "cwd=None snapshots os.getcwd() at __init__ — predictable; later os.chdir() does not move subprocess target"
  - "Explicit cwd validated at __init__ — ValueError on missing path or non-directory (fail-fast at construction boundary, not at first subprocess spawn)"
  - "grace_period_s default 5.0 mirrors Phase 58-03 mcp stop --grace and v10.2 HTTP-02 grace precedent"
  - "env= kwarg (non-None) bypasses _effective_env entirely — escape hatch for tests/advanced ops"

patterns-established:
  - "Pattern: frozenset module constant with constructor override (mirrors file_sandbox._DENY_REASONS)"
  - "Pattern: env hygiene at _stdio_params chokepoint — all 10 wired methods inherit automatically"
  - "Pattern: fail-fast validation at __init__ for cwd + grace_period_s"

requirements-completed: [MCPHYG-01]

# Metrics
duration: 7min
completed: 2026-06-09
---

# Phase 60 Plan 01: McpStdioBackend subprocess hygiene foundation Summary

**DEFAULT_ENV_ALLOWLIST + cwd snapshot/validation + grace_period_s persistence on McpStdioBackend — 10 wired methods inherit hygiene via the _stdio_params chokepoint with no body changes.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-06-09T03:29:05Z
- **Completed:** 2026-06-09T03:36:00Z
- **Tasks:** 3
- **Files modified:** 1 created + 1 modified

## Accomplishments

- `DEFAULT_ENV_ALLOWLIST: frozenset[str]` module constant landed at `agent-brain-mcp/agent_brain_mcp/client.py` with exactly 6 POSIX-ish keys (`PATH`, `HOME`, `USER`, `LANG`, `LC_ALL`, `TERM`); docstring explicitly calls out `AGENT_BRAIN_API_KEY` as the SECURITY-01 auto-forward exception.
- `McpStdioBackend.__init__` widened with 3 new backward-compat kwargs (`env_allowlist`, `forward_env`, `grace_period_s`). All existing Phase 57+ wire test suites stay green with default kwargs.
- `cwd=None` now snapshots `os.getcwd()` at construction — predictable. Explicit `cwd` validated as existing directory (`ValueError` on missing path; `ValueError` on file path).
- `_effective_env()` helper filters `os.environ` through the allowlist, additively merges `forward_env` keys, and auto-forwards `AGENT_BRAIN_API_KEY` when present. `_stdio_params()` routes through it so all 10 wired methods inherit hygiene at a single chokepoint.
- `grace_period_s` (default 5.0; `ValueError` on ≤ 0) persisted at `__init__` ready for Plan 60-02's `close()` SIGTERM→SIGKILL escalation.
- 19 unit tests pass across 5 test classes — exceeds plan's 14-test floor.
- `task before-push` exits 0 (533 passed, 110 deselected, 7 warnings; 88% coverage on agent-brain-mcp).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add DEFAULT_ENV_ALLOWLIST + extend McpStdioBackend.__init__** — `29d961a` (feat)
2. **Task 2: Add unit tests for env allowlist + cwd + grace_period_s** — `5b9552b` (test)
3. **Task 3: Cross-package backward-compat verification** — no source change required (54/54 Phase 57 + 59 wire tests green; `task before-push` exits 0). Captured in the plan-metadata commit below.

**Plan metadata:** `be77138` (docs: complete subprocess hygiene foundation plan — SUMMARY + STATE + ROADMAP + REQUIREMENTS)

## Files Created/Modified

- `agent-brain-mcp/agent_brain_mcp/client.py` (modified) — added `import os`, `DEFAULT_ENV_ALLOWLIST` constant, widened `__init__` signature with 3 new kwargs, cwd snapshot + validation logic, `_effective_env()` helper, `_stdio_params()` now routes env through helper. +96/-8 lines.
- `agent-brain-mcp/tests/test_subprocess_hygiene_init.py` (created, 159 lines) — 19 tests across `TestDefaultEnvAllowlist` (2), `TestCwdSnapshot` (4), `TestEnvAllowlist` (7), `TestGracePeriodPersistence` (4), `TestStdioParamsBackwardCompat` (2).

## Decisions Made

- **DEFAULT_ENV_ALLOWLIST shape:** `frozenset` (immutable; mirrors `file_sandbox._DENY_REASONS` precedent) with exactly the 6 documented keys. Smaller than POSIX standard `_PC_*`; larger than nothing — enough for Python startup + locale.
- **AGENT_BRAIN_API_KEY auto-forward inside `_effective_env`:** v10.2.1 SECURITY-01 carryover. Treating it as a leak would break loopback API-key auth between `agent-brain-mcp` and `agent-brain-server`. Documented in the constant's docstring AND the `_effective_env` helper docstring.
- **`env=` non-None kwargs bypass `_effective_env`:** explicit escape hatch for tests/advanced ops. Caller fully owns the dict. Asserted by `test_explicit_env_overrides_allowlist`.
- **Construction-time validation for both cwd and grace_period_s:** fail-fast at the boundary so downstream wire methods do not surface subprocess-spawn failures later. Mirrors v3 design doc §3.5 no-silent-fallback contract.
- **No prior-phase test inversions needed.** All 54 Phase 57 + Phase 59 wire tests pass unchanged — backward compat preserved by default kwargs. Compare to Plan 59-02's Rule 1 sentinel inversions (which were necessary because Phase 57 wired bodies that Plan 59-01's tests still expected to be sentinels). The default `env_allowlist=None` + `forward_env=None` + `grace_period_s=5.0` semantics keep the pre-Plan-60-01 behavior intact for all existing test constructions.

## Deviations from Plan

None — plan executed exactly as written. All 3 tasks completed in order, all acceptance criteria met, all verify commands green on first run.

The plan's explicit `import os` addition reminder (CRITICAL REMINDER #2 from the prompt) was honored — `import os` is now present in the imports block.

The plan budgeted for possible Rule 1 prior-phase test inversions (Task 3); none were needed because the backward-compat kwargs preserved Phase 57+ semantics. Documented above under Decisions Made.

## Issues Encountered

- **Black reformatted the new test file on its first pass** — 2 lines collapsed for line-length conformance. No semantic change; the system-reminder confirmed the reformat was intentional. Test file content is identical in behavior.
- **STATE.md and .planning/config.json had pre-existing uncommitted changes at plan start** (15-line diff to STATE.md, 2-line diff to config.json). These were noise from a prior session; STATE.md will be rewritten by the state update step below, so the prior delta is absorbed. No action needed for plan execution.

## User Setup Required

None — no external service configuration required. All changes are internal to `agent-brain-mcp` package surface.

## Authentication Gates

None encountered. The new `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` filtering behavior is by-design and was driven by the plan's locked CONTEXT decisions, not an unexpected auth-gate scenario.

## Verification Evidence

```
$ cd agent-brain-mcp && poetry run pytest tests/test_subprocess_hygiene_init.py -v
============================== 19 passed in 0.31s ==============================

$ cd agent-brain-mcp && poetry run pytest tests/test_cli_backends_skeleton.py \
    tests/test_cli_backends_query_wire.py tests/test_cli_backends_methods_wire.py \
    tests/test_mcp_backend_prompts_wire.py tests/test_subprocess_hygiene_init.py
====================== 54 passed, 14 deselected in 8.14s =======================

$ task before-push
... 533 passed, 110 deselected, 7 warnings in 22.43s ...
--- All checks passed - Ready to push ---
[exit code 0]
```

## Next Phase Readiness

- **Plan 60-02** inherits `self.grace_period_s` for the `close()` SIGTERM→SIGKILL escalation. Default 5.0s mirrors Phase 58-03 precedent.
- **Plan 60-03** (1000-invocation orphan stress test) inherits the hygiene contract automatically — every `McpStdioBackend(...)` constructed by the stress test gets the pinned cwd + filtered env without any per-test wiring.
- **Phase 61-62** (framework matrix smoke tests) get the contract for free by going through `McpStdioBackend` rather than spawning raw subprocesses.

## Self-Check: PASSED

- FOUND: `agent-brain-mcp/agent_brain_mcp/client.py`
- FOUND: `agent-brain-mcp/tests/test_subprocess_hygiene_init.py`
- FOUND commit: `29d961a` (feat: McpStdioBackend hygiene)
- FOUND commit: `5b9552b` (test: subprocess hygiene init tests)

---

*Phase: 60-subprocess-hygiene-1000-invocation-orphan-test*
*Completed: 2026-06-09*
