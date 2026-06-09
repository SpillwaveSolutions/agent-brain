---
phase: 60-subprocess-hygiene-1000-invocation-orphan-test
verified: 2026-06-08T00:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: null
---

# Phase 60: Subprocess hygiene + 1000-invocation orphan test — Verification Report

**Phase Goal:** Lock MCP stdio subprocess hygiene as a contract BEFORE the framework matrix lands — pinned cwd (no `cwd=None` inheritance), env sanitized to an explicit allowlist (drop API keys unless explicitly forwarded), SIGTERM → SIGKILL escalation with configurable grace, and an opt-in 1000-invocation pgrep test proving no orphans survive a tight tear-down loop.
**Verified:** 2026-06-08
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
| - | ----- | ------ | -------- |
| 1 | `McpStdioBackend.__init__` pins `cwd` (no `cwd=None` inheritance), filters `env` through documented allowlist, `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` not propagated unless opted in | VERIFIED | `DEFAULT_ENV_ALLOWLIST = frozenset({"PATH","HOME","USER","LANG","LC_ALL","TERM"})` at `client.py:38`; cwd snapshot at `client.py:613-614`; explicit cwd ValueError validation at `client.py:617-620`; `_effective_env()` filtering at `client.py:744-766` with `AGENT_BRAIN_API_KEY` SECURITY-01 auto-forward |
| 2 | `close()` sends SIGTERM → waits `grace_period_s` (default ≤5s) → SIGKILL; grace period honored by unit test using SIGTERM-ignoring stub | VERIFIED | `close()` escalation at `client.py:700-740` with `process.terminate()` → `_wait_for_subprocess_exit(process, self.grace_period_s)` → `process.kill()`; default `grace_period_s: float = 5.0` at `client.py:607`; stub at `tests/_stubs/ignore_sigterm.py:32` (`signal.signal(signal.SIGTERM, signal.SIG_IGN)`); `test_sigkill_escalation_kills_ignorant_child` at `tests/test_subprocess_hygiene_close.py:156` |
| 3 | `task mcp:stress:orphan-test` drives 1000 query→close cycles; per-iteration psutil children-delta assert; pgrep DIAGNOSTIC only; opt-in (NOT in `task before-push`); surfaces leak counts in failure message | VERIFIED | Per-package target `stress:orphan-test:` at `agent-brain-mcp/Taskfile.yml:110`; root-level discoverable via `includes: mcp:` alias; `@pytest.mark.stress` at `tests/stress/test_orphan_subprocess.py:98`; `children(recursive=True)` PRIMARY assert at line 81; pgrep DIAGNOSTIC at line 145 (only inside failure surface); `addopts` excludes via `and not stress` at `pyproject.toml:108`; root `before-push` block grep returns 0; orchestrator confirms 111 deselected (110 baseline + 1 new stress) |
| 4 | Phase 61 + 62 framework tests inherit hygiene by going through `McpStdioBackend` | VERIFIED | Architectural: McpStdioBackend is the only public Pattern-A surface for stdio MCP backends. All 16 `_async_*` helpers route through `self._hygienic_stdio_client(self._stdio_params())` (call sites lines 799, 812, 887, 942, 955, 971, 997, 1013, 1029, 1043, 1059, 1087, 1099, 1111, 1123, 1139). McpHttpBackend (line 1146) is a separate class with different process model (out of scope per CONTEXT.md). Documented in `60-CONTEXT.md` and ROADMAP §"Phase 60 hygiene-before-frameworks ordering" |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `agent-brain-mcp/agent_brain_mcp/client.py` | DEFAULT_ENV_ALLOWLIST + extended `__init__` + cwd validation + env filtering + weakref tracker + hygienic wrapper + SIGTERM/SIGKILL escalation | VERIFIED | All present; 18 references to `_hygienic_stdio_client` (1 def + 16 call sites + 1 docstring); 5 references to `_inflight_ref`; 3 references to `self.grace_period_s` |
| `agent-brain-mcp/tests/test_subprocess_hygiene_init.py` | 14+ unit tests for env allowlist + cwd snapshot + cwd validation + SECURITY-01 carryover | VERIFIED | 19 tests, 159 lines (exceeds 100-line min) |
| `agent-brain-mcp/tests/test_subprocess_hygiene_close.py` | 10+ unit tests for SIGTERM happy path + SIGKILL escalation + idempotency + E2E extraction guard | VERIFIED | 11 tests, 254 lines (exceeds 80-line min). Includes `test_sigterm_alone_kills_well_behaved_child`, `test_sigkill_escalation_kills_ignorant_child`, `test_hygienic_wrapper_registers_inflight_on_real_sdk_shape` (§3.5 no-silent-fallback E2E guard) |
| `agent-brain-mcp/tests/_stubs/ignore_sigterm.py` | Portable Python SIGTERM-ignoring stub | VERIFIED | 42 lines (exceeds 15-line min); `signal.signal(signal.SIGTERM, signal.SIG_IGN)` present; READY marker for synchronization |
| `agent-brain-mcp/tests/_stubs/__init__.py` | Package marker | VERIFIED | Exists |
| `agent-brain-mcp/tests/stress/__init__.py` | Package marker | VERIFIED | Exists |
| `agent-brain-mcp/tests/stress/test_orphan_subprocess.py` | 1000-invocation stress test, pytest.mark.stress, psutil PRIMARY, pgrep DIAGNOSTIC | VERIFIED | 155 lines (exceeds 60-line min); all required patterns present (`@pytest.mark.stress`, `children(recursive=True)`, `AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS`, `DEFAULT_MAX_ITERATIONS = 1000`, `backend.health()`, surviving PIDs + time-since-close in failure surface) |
| `agent-brain-mcp/pyproject.toml` | psutil dep + `stress` marker registered + addopts excludes stress | VERIFIED | `stress: 1000-invocation no-orphan test (MCPHYG-02 …)` registered line 105; `addopts = "-m 'not e2e and not e2e_http and not contract and not stress'"` line 108 |
| `agent-brain-mcp/Taskfile.yml` | `stress:orphan-test:` per-package target | VERIFIED | Bare task name at line 110 (per established `before-push` convention) |
| `Taskfile.yml` | Root-level exposure of `mcp:stress:orphan-test` + NOT in before-push | VERIFIED | Discoverable via `includes: mcp:` alias (Rule 1 fix from Plan 60-03; documented in comment block at lines 224-232); root before-push block grep returns 0 |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `McpStdioBackend.__init__` | `DEFAULT_ENV_ALLOWLIST` | `env_allowlist if env_allowlist is not None else DEFAULT_ENV_ALLOWLIST` | WIRED | `client.py:626-628` |
| `_stdio_params()` | `self._effective_env()` | `StdioServerParameters(..., env=self._effective_env())` | WIRED | `client.py:788` |
| `McpStdioBackend.close()` | `self._inflight_ref` | weakref dereference + SIGTERM/SIGKILL escalation | WIRED | `client.py:712-740` |
| 16 `_async_*` helpers | `_hygienic_stdio_client` | `self._hygienic_stdio_client(self._stdio_params())` | WIRED | All 16 call sites confirmed; raw `stdio_client(self._stdio_params())` count = 0 in `McpStdioBackend` |
| `task mcp:stress:orphan-test` (root) | per-package `stress:orphan-test` | `includes: mcp:` alias resolution | WIRED | Orchestrator-verified: `AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS=5 task mcp:stress:orphan-test` passes in ~7s wall-clock |
| `test_orphan_subprocess.py` | `McpStdioBackend` | per-iteration instantiation + `backend.health()` + `backend.close()` | WIRED | line 122 (`backend = McpStdioBackend(_agent_brain_mcp_on_path)`) |
| `test_orphan_subprocess.py` | `psutil.Process(os.getpid()).children(recursive=True)` | per-iteration delta assertion | WIRED | `_children_pids` helper at line 81; delta computed at iteration body |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| MCPHYG-01 | 60-01, 60-02 | MCP stdio subprocess hygiene — pinned cwd, env allowlist, SIGTERM→SIGKILL escalation with configurable grace period | SATISFIED | REQUIREMENTS.md line 37 marked `[x]`; mapping table line 108 shows Complete. Truths 1 & 2 verified; cwd/env at 60-01, close() escalation at 60-02 |
| MCPHYG-02 | 60-03 | 1000-invocation no-orphan stress test gated behind `task mcp:stress:orphan-test` | SATISFIED | REQUIREMENTS.md line 38 marked `[x]`; mapping table line 109 shows Complete. Truth 3 verified; stress test ships at `tests/stress/test_orphan_subprocess.py` with `@pytest.mark.stress` |

No orphaned requirements — REQUIREMENTS.md and PLAN frontmatter requirement IDs match exactly.

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments in modified source files. The `_extract_subprocess_from_streams` soft-fail-to-None inside the extractor is the §3.5 no-silent-fallback escape valve documented in CONTEXT.md and explicitly guarded by `test_hygienic_wrapper_registers_inflight_on_real_sdk_shape` (E2E extraction test at `test_subprocess_hygiene_close.py:216`) so an MCP SDK shape drift would fail loudly rather than silently disabling hygiene.

### Architectural Decisions Preserved

- **Pattern A locked** — fresh subprocess per call via `asyncio.run` + `stdio_client`; `_hygienic_stdio_client` is per-call (lines 673-698), NOT persistent. Verified at all 16 `_async_*` helpers.
- **McpBackend Protocol shape unchanged** — no `__enter__`/`__exit__` added to the Protocol; `McpStdioBackend` has them but they're class-level conveniences for `with backend:` ergonomics, not part of the Protocol contract.
- **All 16 `_async_*` helpers wrapped** — grep count: 16 call sites + 1 method def + 1 docstring = 18 total references to `_hygienic_stdio_client`. Zero raw `stdio_client(self._stdio_params())` remaining inside `McpStdioBackend` (the 17 such references in the file are all inside `McpHttpBackend` starting at line 1146, which has a different process model and is out of scope per CONTEXT.md).
- **AGENT_BRAIN_API_KEY auto-forwards** — `client.py:764-765` (v10.2.1 SECURITY-01 preserved); documented in `DEFAULT_ENV_ALLOWLIST` docstring at lines 32-36 and `_effective_env` docstring.
- **§3.5 no-silent-fallback** — `_extract_subprocess_from_streams` soft-fails to None inside extractor (acceptable per CONTEXT.md decision); the wrapper-level E2E guard `test_hygienic_wrapper_registers_inflight_on_real_sdk_shape` drives a faked SDK-shaped fixture through the full wrapper path so any silent disablement of hygiene would fail loudly.

### Quality Gates (orchestrator-confirmed)

- `task before-push` exits 0
- agent-brain-mcp: 544 tests pass (111 deselected — stress correctly excluded; +1 vs Plan 60-02 baseline of 110 is the new stress test)
- agent-brain-cli: 545 tests pass (no regressions)
- Smoke run `AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS=5 task mcp:stress:orphan-test` passes in ~7s wall-clock

### Commit Trail

- `be77138` docs(60-01): complete subprocess hygiene foundation plan
- `29d961a` feat(60-01): DEFAULT_ENV_ALLOWLIST + McpStdioBackend hygiene
- `5b9552b` test(60-01): subprocess hygiene init tests
- `712eef1` docs(60-01): backfill metadata commit hash in SUMMARY
- `cdcf089` test(60-02): SIGTERM-ignoring Python stub child
- `7967764` feat(60-02): hygienic stdio wrapper + close() SIGTERM/SIGKILL escalation
- `1aa6f1e` test(60-02): close() escalation tests + sync-context returncode fix
- `fd37e59` docs(60-02): complete subprocess hygiene close() escalation plan
- `6857324` chore(60-03): register stress pytest marker + tests/stress package
- `371def1` test(60-03): 1000-invocation orphan stress test
- `8cd6d79` chore(60-03): wire mcp:stress:orphan-test Taskfile target
- `a0acbf4` docs(60-03): complete 1000-invocation orphan stress test plan

### Gaps Summary

None. All 4 ROADMAP Success Criteria verified against the codebase. All required artifacts exist, are substantive, and are correctly wired. Both requirement IDs (MCPHYG-01, MCPHYG-02) marked Complete in REQUIREMENTS.md with verified implementation evidence. Architectural locks from Phases 56-59 preserved. Phase 61-62 framework tests will inherit the hygiene contract automatically by going through `McpStdioBackend`.

---

_Verified: 2026-06-08_
_Verifier: Claude (gsd-verifier)_
