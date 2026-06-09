# Phase 60: Subprocess hygiene + 1000-invocation orphan test - Context

**Gathered:** 2026-06-08
**Status:** Ready for planning
**Mode:** Auto (--auto, recommended defaults selected per gray area)

<domain>
## Phase Boundary

Lock MCP stdio subprocess hygiene as a contract on `McpStdioBackend` BEFORE the framework matrix lands (Phases 61-62). Specifically: (a) pinned `cwd` (no `cwd=None` inheritance), (b) env sanitized to a documented allowlist (drop `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` unless explicitly forwarded — but preserve `AGENT_BRAIN_API_KEY` for v10.2.1 SECURITY-01), (c) SIGTERM → SIGKILL escalation with configurable grace, (d) an opt-in 1000-invocation orphan test using `psutil` (primary) + `pgrep -f` (diagnostic) proving no `agent-brain-mcp` PIDs survive tight tear-down.

Phase 61+ framework smoke tests inherit the hygiene contract automatically by going through `McpStdioBackend` rather than spawning raw subprocesses.

**Out of scope (NOT in this phase):**
- Persistent-subprocess refactor (Pattern A — fresh subprocess per call — stays locked from Phase 57-02)
- `McpHttpBackend` lifecycle (HTTP subprocess is owned by `agent-brain mcp start|stop` from Phase 58)
- Framework matrix scoping (deferred to Phase 61 lighter scoping doc per Phase 56 CONTEXT.md design-doc-scope lock)
- Phase 58's latent `AGENT_BRAIN_URL` CLI-side env-routing quirk (orthogonal to subprocess hygiene; would be its own fix point — flagged in Phase 58 SUMMARY)
- `AGENT_BRAIN_OPENAI_API_KEY` / `AGENT_BRAIN_ANTHROPIC_API_KEY` propagation (explicit non-goal per v3 design doc §1.3)

</domain>

<decisions>
## Implementation Decisions

### Env allowlist composition

- **Default allowlist:** Module-level constant `DEFAULT_ENV_ALLOWLIST: frozenset[str]` containing the minimum needed to run a Python subprocess: `{"PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM"}`. Rationale: smallest surface that keeps Python startup + locale working on macOS/Linux/Windows.
- **AGENT_BRAIN_API_KEY:** Auto-forwarded when set in the parent env. This is the v10.2.1 SECURITY-01 server-auth key — treating it as a leak would break loopback API-key auth. Documented explicitly in the allowlist constant.
- **AGENT_BRAIN_*** other vars: NOT auto-forwarded. Caller must opt-in via constructor.
- **OPENAI_API_KEY / ANTHROPIC_API_KEY / etc.:** NEVER auto-forwarded. Caller must explicitly opt-in via `forward_env: list[str]` constructor kwarg.
- **Override mechanism:** `McpStdioBackend(..., env_allowlist=None, forward_env=None)` constructor kwargs. `env_allowlist=None` means "use DEFAULT_ENV_ALLOWLIST"; pass a `frozenset[str]` to replace entirely. `forward_env` is additive on top of the active allowlist.
- **Pattern reference:** mirrors v10.2 HTTP-02 loopback-only allowlist pattern (module constant + constructor override).

### cwd default policy

- **`cwd=None` behavior:** Snapshot `os.getcwd()` at `__init__` time. Predictable; no "moving target" if caller `os.chdir()`s later. The existing comment at `client.py:464-466` already flagged this is Phase 60 work.
- **Explicit cwd validation:** Path must exist and be a directory. Raise `ValueError` at construction otherwise. Fail-fast at the boundary.
- **Symlink resolution:** No — store cwd as given (relative or absolute, no `Path.resolve()`). Symlink policy is its own §3.5-style decision; punt to per-subprocess `execve` time which already happens through `StdioServerParameters`.
- **No deprecation warning:** Silent behavior change is fine. The existing source comment is documentation that this was always planned.

### close() semantics under Pattern A

- **In-flight subprocess tracking:** Track the active `stdio_client` subprocess via a `weakref.ref` + `threading.Lock` pair maintained on the backend instance. If a caller invokes `close()` while a sync method (e.g. `query()`) is mid-flight on another thread, the in-flight subprocess gets the SIGTERM→SIGKILL escalation. This is the only real leak vector under Pattern A.
- **SIGTERM→SIGKILL escalation site:** Wrap the SDK's `stdio_client` async context manager with our own wrapper that owns the `asyncio.subprocess.Process` reference and applies escalation. `process.terminate()` → wait `grace_period_s` → `process.kill()` if still alive.
- **Default grace_period_s:** `5.0` seconds, configurable via constructor `grace_period_s: float = 5.0`. Mirrors Phase 58-03 `mcp stop --grace` default + v10.2 HTTP-02 pattern.
- **Test stub child:** Python stub script that does `signal.signal(SIGTERM, lambda *_: None)` then `time.sleep(...)` — portable, no shell scripts, mirrors Phase 58 lock stale-pid stub.
- **No-op when no in-flight subprocess:** `close()` is idempotent — if nothing's running, return immediately (current behavior preserved).

### 1000-invocation orphan detection mechanism

- **Primary assert:** `psutil.pid_exists(spawned_pid)` per-iteration check. Already a CLI dep from Phase 58-01 so no new dependencies. Cross-platform.
- **PID capture style:** Record spawned PIDs via `psutil.Process(os.getpid()).children(recursive=True)` snapshot before+after each iteration; the **delta** must shrink back to zero. More precise than `pgrep` and doesn't conflict with other concurrent `agent-brain-mcp` test processes in the suite.
- **Diagnostic-only `pgrep`:** Used in the task target's failure-message surface (e.g. on first leak, print `pgrep -f "agent-brain-mcp"` output for human triage). NOT the per-iteration assert — only fires when psutil already detected leak.
- **Task target:** New top-level `task mcp:stress:orphan-test` Taskfile entry. Opt-in, NOT in `task before-push` per SC3 (slow — 1000 subprocess spawns × ~0.5-2s each = 500-2000s wall-clock).
- **Failure surface:** On first iteration leak, print {iteration #, spawned PID, surviving PIDs from `pgrep`, time-since-close} for triage. Stop tight-loop early (NOT after 1000).
- **Test location:** `agent-brain-mcp/tests/stress/test_orphan_subprocess.py` with `pytest.mark.stress` marker; Taskfile target runs `pytest -m stress`.

### Claude's Discretion

- Exact wrapper class name for the stdio_client wrapper (e.g. `_HygienicStdioClient` vs `_StdioSubprocessGuard`)
- Whether the env allowlist is a `frozenset` or a tuple (immutability matters; either works)
- Exact format of the orphan-test failure message (must include iteration + spawned PID + surviving PIDs)
- Whether `task before-push` should print a one-line reminder that `task mcp:stress:orphan-test` exists (probably yes, no harm)
- Whether to add a `--max-iterations` knob to the orphan test (probably yes, default 1000)
- How to thread the in-flight subprocess weakref through the async wrapper (asyncio detail)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v3 design (source of truth for hygiene contract)
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §4.5 — Phase 60 scope: pinned cwd, env allowlist, SIGTERM→SIGKILL escalation, 1000-invocation orphan test
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §1.3 — explicit non-goal: `AGENT_BRAIN_OPENAI_API_KEY` / `AGENT_BRAIN_ANTHROPIC_API_KEY` propagation default-on
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §3.5 — no-silent-fallback contract (carry forward — applies to env handling)

### Phase 56-59 architectural locks (do not re-decide)
- `.planning/phases/56-design-doc-cli-backend-skeleton/56-CONTEXT.md` — backend location (agent-brain-mcp), Protocol style (`@runtime_checkable`), sync facade pattern
- `.planning/phases/57-cli-transport-selector-byte-identical-equivalence/57-CONTEXT.md` — Pattern A locked (sync facade via `asyncio.run`); fresh subprocess per call
- `.planning/phases/58-runtime-discovery-helper-commands/58-CONTEXT.md` — psutil dep precedent; grace_period=5s default; lock acquisition pattern
- `.planning/phases/59-cli-prompts-resources-commands/59-CONTEXT.md` — McpBackend Protocol does NOT declare `__enter__`/`__exit__` (Pattern A: fresh client per call)

### Roadmap + Requirements
- `.planning/ROADMAP.md` §"Phase 60" — 4 success criteria
- `.planning/REQUIREMENTS.md` — MCPHYG-01 (hygiene), MCPHYG-02 (orphan test)

### Existing call sites (extend, don't replace)
- `agent-brain-mcp/agent_brain_mcp/client.py:471-523` — `McpStdioBackend.__init__` + `_stdio_params()` — these are the targets for cwd/env hardening
- `agent-brain-mcp/agent_brain_mcp/client.py:494-500` — `close()` — currently a no-op marker; this is where SIGTERM/SIGKILL goes
- `agent-brain-mcp/agent_brain_mcp/client.py:464-468` — pre-existing comments flagging Phase 60 as the owner

### Related cross-package precedents
- `agent-brain-cli/agent_brain_cli/commands/mcp.py` (Phase 58-02/03) — `os.killpg` + grace + SIGKILL pattern for the HTTP launcher (different process model but same escalation shape)
- `agent_brain_server/security/file_sandbox.py` (v10.2 Phase 50) — frozenset-based hard whitelist pattern (mirror for env allowlist)
- `agent-brain-cli/agent_brain_cli/mcp_runtime.py` (Phase 58-01) — psutil.pid_exists usage pattern

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **psutil**: Already a hard dep in `agent-brain-cli/pyproject.toml` from Phase 58-01. New code in `agent-brain-mcp` adds it as a dep there too (or imports through cli-helper if such a path exists — researcher should confirm packaging boundary).
- **Phase 58 `is_listening` helper at `mcp_runtime.py`**: Uses `psutil.pid_exists` — direct precedent for the orphan-test detection mechanism.
- **Phase 58-03 grace-period polling at `commands/mcp.py`**: Polls every 100ms during the grace period before SIGKILL — exact pattern to mirror for `close()` escalation.
- **Phase 50 `file_sandbox.py` frozenset allowlist**: Exact pattern for `DEFAULT_ENV_ALLOWLIST` constant.

### Established Patterns
- **Pattern A (fresh subprocess per call)**: Phase 57-02 locked this. The hygiene contract MUST work within Pattern A — no architectural pivot to persistent subprocess.
- **Module-level constants + constructor override**: HTTP-02 loopback pattern, file_sandbox 4-deny-reasons pattern — env allowlist follows the same shape.
- **5-second default grace period**: Phase 58-03 `mcp stop --grace`, v10.2 HTTP-02 grace — keep consistent.
- **Stress tests live separately**: `tests/stress/` directory with `pytest.mark.stress`, gated behind a Taskfile target (NOT `task before-push`).

### Integration Points
- `McpStdioBackend.__init__` signature: `(command, *, cwd=None, env=None)` — extend to `(command, *, cwd=None, env=None, env_allowlist=None, forward_env=None, grace_period_s=5.0)`. Backward-compatible — all new args have defaults.
- `_stdio_params()` method: insert the env-filtering call here before constructing `StdioServerParameters`. Single chokepoint for all 12 wired methods (verified via grep of `_stdio_params()` callers in Phase 57 SUMMARY).
- `close()`: Currently sets `self._closed = True`. Extend to (a) check weakref for in-flight subprocess, (b) if present, escalate per grace period.
- Inside each `_async_xxx` helper: wrap `stdio_client(...)` with the new hygienic wrapper so the wrapper holds the subprocess reference + registers with `self._inflight_ref` for the close() path.
- Phase 61's framework smoke tests will instantiate `McpStdioBackend(...)` directly — they inherit hygiene automatically by virtue of going through the backend instead of spawning their own subprocess.

</code_context>

<specifics>
## Specific Ideas

- "5 seconds grace, then SIGKILL" — explicit Phase 58 precedent, do NOT deviate
- "psutil over pgrep for the assert" — pgrep is macOS/Linux-only; ship cross-platform
- "Stress test must be `task mcp:stress:orphan-test`" — exact target name from ROADMAP SC3
- "AGENT_BRAIN_API_KEY is the one auto-forwarded var" — v10.2.1 SECURITY-01 carryover, must be documented in `DEFAULT_ENV_ALLOWLIST` docstring
- "Fail fast" — explicit cwd validation at __init__, not at first subprocess spawn

</specifics>

<deferred>
## Deferred Ideas

- **`AGENT_BRAIN_URL` CLI envvar routing quirk** (surfaced in Phase 58-03 SUMMARY) — different fix point. Phase 58 noted it as "Phase 60 territory" but really it's a CLI-side Click-option redesign, orthogonal to McpStdioBackend subprocess hygiene. File a follow-up issue if not addressed in a separate slice.
- **Async-first `AsyncBackendClient` Protocol variant** — explicit v3 non-goal per design doc §1.3 (sync-only ships in v3, async re-evaluated when v4 OAuth lands).
- **Watchdog daemon for orphan PIDs across multiple runs** — overkill; the per-iteration psutil assert catches everything we need.
- **Cross-platform Windows shipping** — `os.getsid`/`killpg` don't exist on Windows but the orphan test uses psutil (cross-platform). Document the Windows status when (if) it comes up; not blocking Phase 60.

</deferred>

---

*Phase: 60-subprocess-hygiene-1000-invocation-orphan-test*
*Context gathered: 2026-06-08*
