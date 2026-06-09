---
phase: 59-cli-prompts-resources-commands
plan: 02
subsystem: api
tags: [mcp, click, prompts, asyncio-run, pattern-a, cli-mcp-05]

# Dependency graph
requires:
  - phase: 56-cli-mcp-skeleton
    provides: BackendClient Protocol + McpStdioBackend / McpHttpBackend skeleton-first pattern (Plan 56-03)
  - phase: 57-cli-mcp-wire
    provides: Pattern A asyncio.run sync facade + verbatim §3.5 wording (Plan 57-02..03)
  - phase: 59-cli-prompts-resources-commands
    provides: McpBackend Protocol + 10 skeleton method bodies + open_mcp_backend factory + isinstance pinning (Plan 59-01)
provides:
  - "10 wire bodies on the 2 backends (McpStdioBackend + McpHttpBackend × 5 methods) via asyncio.run Pattern A"
  - "10 _async_* helper coroutines (mirrors Plan 57-02/03 shape)"
  - "agent-brain prompt <name> Click command — positional NAME + --arg KEY=VALUE multi + --json flag"
  - "model_dump(mode='json', exclude_none=False) translator for all 5 SDK result shapes (GetPromptResult, ListPromptsResult, ListResourcesResult, ListResourceTemplatesResult, ReadResourceResult)"
  - "Unknown-name fallback: McpError catch → list_prompts() → UsageError('Unknown prompt {name!r}; available: ...') with alphabetical sort"
affects:
  - 59-03 (Plan 03 uses the same wired list_resources / list_resource_templates / read_resource methods to ship `agent-brain resources` sub-group)
  - 60+ (any new MCP-only CLI command — same Pattern A shape + open_mcp_backend factory + model_dump translator)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pattern A confirmed for the 10 new method wires — same shape as Plan 57-02 _async_query (stdio leg client.py:580) and 57-03 _async_query (http leg client.py:943); each public method is asyncio.run(self._async_*()), each helper opens stdio_client / streamablehttp_client → ClientSession → SDK method → model_dump translation"
    - "Sync facade NOT a persistent loop — every CLI invocation spawns a fresh stdio_client subprocess or streamablehttp_client connection per call (Pattern A — Plan 57-02 CONTEXT decision); Phase 60 owns the persistent-subprocess hygiene refinement target unchanged"
    - "Single-point --transport mcp enforcement: open_mcp_backend(ctx) is the factory the new prompt command calls (NOT open_backend); the Plan 59-01 contract carries forward verbatim — Plan 59-03's `agent-brain resources *` will call the same factory"
    - "model_dump(mode='json', exclude_none=False) for all 5 SDK results — mode='json' ensures AnyUrl + datetime serialize as strings; exclude_none=False preserves the full shape so the command layer can rely on messages/contents/etc being always present (possibly as [])"
    - "Partition-on-first-= for --arg KEY=VALUE parsing — VALUE may contain additional '=' verbatim (matches the existing --metadata KEY=VALUE idiom in commands/index.py)"
    - "Defensive fallback in unknown-name error path: if backend.list_prompts() ALSO fails, surface the original McpError alongside the secondary failure so the operator isn't told a second error masked the first"

key-files:
  created:
    - agent-brain-mcp/tests/test_mcp_backend_prompts_wire.py (13 Layer 1 wire-mock tests — 7 stdio + 5 http + 1 sentinel-removal pin)
    - agent-brain-cli/agent_brain_cli/commands/prompt.py (191 LOC after Black — _parse_arg helper + prompt_command Click command + render-vs-json dispatch)
    - agent-brain-cli/tests/test_prompt_command.py (13 CliRunner tests covering all 9 must-haves + 3-case parametrize matrix)
  modified:
    - agent-brain-mcp/agent_brain_mcp/client.py (+138 net LOC: 10 wire bodies replace 10 skeletons; 10 _async_* helpers added; sentinel removed)
    - agent-brain-cli/agent_brain_cli/commands/__init__.py (+2 LOC: prompt_command export + __all__)
    - agent-brain-cli/agent_brain_cli/cli.py (+2 LOC: import + cli.add_command(prompt_command, name='prompt'))
    - agent-brain-cli/tests/test_mcp_backend_factory.py (Rule 1: inverted sentinel-pinning test → returns-real-wired-backend test)
    - agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py (Rule 1: inverted sentinel-pinning test → no-longer-raises-sentinel test)

key-decisions:
  - "Pattern A confirmed for the 10 new method wires — mirrors Plan 57-02 _async_query at agent-brain-mcp/agent_brain_mcp/client.py:580 (stdio) and the http counterpart at client.py:969. Each public method is 1-line asyncio.run(self._async_*()); each helper opens stdio_client / streamablehttp_client, opens ClientSession, calls the SDK method, then translates via model_dump."
  - "Prompt rendering shape: messages joined with the literal separator `\"\\n---\\n\"` (Plan 59-01 CONTEXT decision; mirrors v2 design doc §6.6 client-side convention). --json mode prints via json.dumps(result, indent=2). The two modes are mutually exclusive — --json overrides default."
  - "Unknown-prompt error wording: `Unknown prompt {name!r}; available: {sorted-csv}` (alphabetical sort by name from prompts/list); if list_prompts() ALSO fails: `Prompt call failed: {exc}; additionally, prompts/list failed: {list_exc}`. Both exit 2 via click.UsageError."
  - "--arg KEY=VALUE partition-on-first-`=` semantics — `expr=a=b` → `{expr: 'a=b'}`. Uses str.partition('=') (mirrors the established --metadata idiom in commands/index.py). Malformed (no '=' or empty KEY) raises click.UsageError with the offending value rendered via repr."
  - "Pass arguments=None (NOT {}) to backend.get_prompt when --arg is unset — the MCP server treats `None` vs `{}` as semantically different per the spec, and the CLI preserves that. Confirmed in test_get_prompt_stdio_passes_none_arguments_when_unspecified."
  - "Hyphenated prompt names — the 6 v1 prompts use hyphens (find-callers, NOT find_callers; see agent-brain-mcp/agent_brain_mcp/prompts/__init__.py PROMPT_REGISTRY at line 21). The CLI does NOT hard-code names — `<name>` is forwarded verbatim to prompts/get; the source of truth at runtime is prompts/list."
  - "McpBackend Protocol intentionally does NOT declare __enter__/__exit__ — Pattern A spawns a fresh client per call inside the async helper, so there is no persistent connection to bracket CLI-side. The plan's prescribed `with backend:` wrapper was removed (the Protocol doesn't satisfy that surface). Phase 60 may revisit if a persistent-loop refactor lands."
  - "Rule 1 deviation: Plan 59-01 shipped two sentinel-pinning tests (test_mcp_backend_skeleton_methods_raise_with_sentinel + test_open_mcp_backend_unimplemented_methods_still_raise) that asserted the Plan 02 sentinel still raised. Plan 02 wires the bodies — sentinel is gone by design. Both tests were inverted (renamed + assertion flipped) to pin the post-Plan-02 contract: sentinel is gone, real SDK calls bubble up real failures. Same Rule 1 pattern Plan 59-01 itself applied to the Phase 57 routing tests in f6eddd3."

patterns-established:
  - "Pattern X — wire-mock test fixture: AsyncMock-backed async context managers for stdio_client / streamablehttp_client + ClientSession. Patch at the LATE-import path (mcp.client.stdio.stdio_client, mcp.client.streamable_http.streamablehttp_client, mcp.ClientSession) — these are the symbols the helper bodies resolve at call time. Plan 59-03 can clone this fixture shape verbatim."
  - "Pattern Y — Click command for MCP-only surface: @click.pass_context + open_mcp_backend(ctx) at the top of the body. UsageError parses --arg up-front (before backend construction). Exception order: McpError catch wraps with UsageError + list_prompts fallback; outer except surfaces any other Exception as exit 1 with stderr message; click.UsageError re-raises so Click handles exit code 2 + stderr."
  - "Pattern Z — sentinel-invert deviation: when Plan N+1 wires a body that Plan N pinned-as-skeleton, the Plan N pinning test must be renamed + inverted to pin the post-Plan-N+1 contract (e.g., NO longer raises the sentinel). Keeps test surface coverage stable while reflecting the post-wire reality."

requirements-completed: [CLI-MCP-05]

# Metrics
duration: 16min
completed: 2026-06-08
---

# Phase 59 Plan 02: McpBackend wire + agent-brain prompt command Summary

**10 wire bodies replace the Plan 59-01 sentinels (5 methods × 2 backends, Pattern A asyncio.run sync facade); new `agent-brain prompt <name> [--arg K=V]... [--json]` command surfaces the MCP `prompts/get` endpoint with full no-silent-fallback + unknown-name-fallback contract carriage. Closes CLI-MCP-05.**

## Performance

- **Duration:** ~16 min (incl. 1 Rule 1 deviation + 2 Black/Ruff cycles)
- **Started:** 2026-06-08T21:34:11Z
- **Completed:** 2026-06-08T21:49:43Z
- **Tasks:** 3 (2 TDD + 1 QA gate)
- **Files modified:** 8 (3 created, 5 modified)
- **Net LOC added:** ~1,250 (source + tests; net of deletions)

## Accomplishments

- **10 wire bodies landed** on `McpStdioBackend` (lines 819-899 — 5 public methods + 5 `_async_*` helpers) and `McpHttpBackend` (lines 1287-1367 — same shape). The Plan 59-01 sentinel `"Wired in Phase 59 Plan 02"` returns 0 occurrences in `client.py`. Each public method is a 1-line `asyncio.run(self._async_*())` facade; each helper opens `stdio_client(self._stdio_params())` or `streamablehttp_client(self.url)`, opens `ClientSession`, calls one SDK method (`session.get_prompt` / `list_prompts` / `list_resources` / `list_resource_templates` / `read_resource(AnyUrl(uri))`), then translates the Pydantic result via `model_dump(mode="json", exclude_none=False)`.

- **`agent-brain prompt <name>`** Click command at `agent-brain-cli/agent_brain_cli/commands/prompt.py` (191 LOC after Black). Surface: positional `NAME` + `--arg KEY=VALUE` repeatable (Click `multiple=True`) + `--json` flag. Default render: `messages[].content.text` joined with literal `"\n---\n"` separator. `--json` mode: pretty-printed `json.dumps(result, indent=2)`. Registered in `commands/__init__.py` + `cli.py` (`cli.add_command(prompt_command, name="prompt")` after the existing `cli.add_command(mcp_group, name="mcp")`).

- **`--transport mcp` enforcement** carried through verbatim via `open_mcp_backend(ctx)` from Plan 59-01. Without the flag: `agent-brain prompt foo` → exit 2 + `Error: This command requires --transport mcp; example: agent-brain --transport mcp --mcp-transport stdio <command>`. The factory is the single point of contract — no duplication in the command body.

- **Unknown-prompt name UX**: CLI catches `mcp.McpError` from `backend.get_prompt()`, calls `backend.list_prompts()`, builds an alphabetically-sorted comma-separated string of names, raises `click.UsageError(f"Unknown prompt {name!r}; available: {csv}")` → exit 2. Defensive fallback: if `list_prompts()` ALSO fails, surface the original `McpError` alongside the secondary failure (`f"Prompt call failed: {exc}; additionally, prompts/list failed: {list_exc}"`).

- **--arg KEY=VALUE parsing**: `_parse_arg(arg)` helper splits on the FIRST `=` via `str.partition`. VALUE may contain additional `=` verbatim (`--arg expr=a=b` → `{"expr": "a=b"}`). Malformed values (no `=` or empty KEY) raise `click.UsageError` with the offending value rendered via `repr()`. Pass `arguments=None` (NOT `{}`) when no `--arg` is provided — the MCP server treats them as semantically different per the spec.

- **26 new unit tests pass** (13 wire-mock + 13 prompt-command). Plus 2 inverted Plan 59-01 sentinel-pinning tests (`test_mcp_backend_methods_no_longer_raise_plan_59_01_sentinel` + `test_open_mcp_backend_returns_real_wired_backend_not_stub`) — same coverage intent, post-Plan-02 contract.

- **`task before-push` exits 0** across the full monorepo: 527 cli + 514 mcp + 32 uds + server tests all pass; Black/Ruff/mypy strict all clean. Coverage 80% (cli) + 88% (mcp).

## Task Commits

| # | Type      | Hash      | Message                                                            |
| - | --------- | --------- | ------------------------------------------------------------------ |
| 1 | RED       | `01057da` | test(59-02): add failing wire tests for 5 McpBackend methods       |
| 2 | GREEN     | `92d0fe6` | feat(59-02): wire 5 McpBackend methods on both backends via Pattern A |
| 3 | Rule-1    | `67796b7` | fix(59-02): invert Plan 59-01 sentinel tests after wire bodies     |
| 4 | RED       | `e23d118` | test(59-02): add failing tests for agent-brain prompt command      |
| 5 | GREEN     | `957bf3d` | feat(59-02): add agent-brain prompt command (CLI-MCP-05)           |
| 6 | QA chore  | `e90ebb4` | chore(59-02): apply Black + Ruff formatting for QA gate            |

## Files Created/Modified

### Created
- `agent-brain-mcp/tests/test_mcp_backend_prompts_wire.py` — 13 Layer 1 wire-mock tests. `AsyncMock`-backed async context managers patched at the late-import sites (`mcp.client.stdio.stdio_client`, `mcp.client.streamable_http.streamablehttp_client`, `mcp.ClientSession`). Canned SDK return shapes use real Pydantic models from `mcp.types` (`GetPromptResult`, `ListPromptsResult`, `ListResourcesResult`, `ListResourceTemplatesResult`, `ReadResourceResult`). Plus a sentinel-removal regression pin (asserts the literal `"Wired in Phase 59 Plan 02"` is gone within ±5 lines of every Phase 59 method def).
- `agent-brain-cli/agent_brain_cli/commands/prompt.py` — 191 LOC after Black. `_parse_arg(arg) -> tuple[str, str]` partition-on-first-`=` helper. `@click.command("prompt")` with `<name>` positional + `--arg KEY=VALUE` multi + `--json` flag. Exception order: `McpError` → `UsageError` + `list_prompts` fallback; outer `Exception` → exit 1 with stderr message; `click.UsageError` re-raises so Click handles exit 2.
- `agent-brain-cli/tests/test_prompt_command.py` — 13 CliRunner tests covering all 9 must-haves from the plan + a 3-case parametrize matrix (zero / one / multi `--arg` including duplicate-key last-wins). `open_mcp_backend` patched at the command module's import site.

### Modified
- `agent-brain-mcp/agent_brain_mcp/client.py` — 10 skeleton bodies replaced with Pattern A wires. 10 `_async_*` helpers added (5 per backend) — all use the lazy-import-inside-helper convention established in the file. Sentinel removed (grep returns 0).
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` — Added `from .prompt import prompt_command` + `"prompt_command"` in `__all__`.
- `agent-brain-cli/agent_brain_cli/cli.py` — Added `prompt_command` to the top-level command imports + `cli.add_command(prompt_command, name="prompt")` after the existing `cli.add_command(mcp_group, name="mcp")`.
- `agent-brain-cli/tests/test_mcp_backend_factory.py` — Rule 1 deviation: `test_open_mcp_backend_unimplemented_methods_still_raise` → `test_open_mcp_backend_returns_real_wired_backend_not_stub`. Same intent (factory returns real backend, not stub); post-Plan-02 contract (sentinel gone, real SDK failure bubbles up).
- `agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py` — Rule 1 deviation: `test_mcp_backend_skeleton_methods_raise_with_sentinel` → `test_mcp_backend_methods_no_longer_raise_plan_59_01_sentinel`. 3 isinstance architectural pins (Stdio ✓, Http ✓, DocServeClient ⊄ McpBackend) survive untouched.

## Decisions Made

1. **Pattern A confirmed for all 10 new method wires.** Same shape as Plan 57-02 `_async_query` (stdio leg at `client.py:580`, http leg at `client.py:969`). Each public method is a 1-line `asyncio.run(self._async_*())`; each `_async_*` helper opens `stdio_client(self._stdio_params())` or `streamablehttp_client(self.url)`, opens `ClientSession`, calls one SDK method, then translates via `model_dump`. No persistent loop, no shared subprocess — each CLI call spawns fresh (Plan 57-02 CONTEXT decision, confirmed across the full 10-method × 2-backend surface by Plan 57-03). Phase 60 owns the persistent-subprocess hygiene refinement target unchanged.

2. **Prompt rendering shape: `"\n---\n".join(messages[].content.text)` for default; `json.dumps(result, indent=2)` for `--json`.** Mirrors the v2 design doc §6.6 client-side convention. The two modes are mutually exclusive — `--json` overrides default render. Both go to stdout (clean pipe target).

3. **Unknown-prompt error wording: `Unknown prompt {name!r}; available: {sorted-csv-of-list_prompts}`.** Alphabetical sort by `p.get("name", "")` extracted from `list_prompts()` results. Defensive: if `list_prompts()` ALSO fails, surface `Prompt call failed: {original_exc}; additionally, prompts/list failed: {secondary_exc}` so the operator isn't told a second error masked the first. Both exit 2 via `click.UsageError`.

4. **`--arg KEY=VALUE` partition-on-first-`=` semantics.** VALUE may contain additional `=` verbatim — `--arg expr=a=b` → `{"expr": "a=b"}`. Uses `str.partition("=")` (mirrors the established `--metadata KEY=VALUE` idiom in `commands/index.py`). Malformed values (no `=` OR empty KEY) raise `click.UsageError` with the offending value rendered via `repr()`. Click translates UsageError → exit 2 with the message on stderr.

5. **Pass `arguments=None` (NOT `{}`) when `--arg` is unset.** The MCP server treats `None` (no arguments at all) vs `{}` (explicit empty) as semantically different per the spec; the CLI preserves that distinction. Confirmed in `test_get_prompt_stdio_passes_none_arguments_when_unspecified` and `test_prompt_command_arg_forwarding_matrix[argv0-None]`.

6. **Hyphenated prompt names are the source of truth at runtime.** The 6 v1 prompts use hyphens (`find-callers`, NOT `find_callers`) per `agent-brain-mcp/agent_brain_mcp/prompts/__init__.py` `PROMPT_REGISTRY` at line 21. The CLI does NOT hard-code names — `<name>` is forwarded verbatim to `prompts/get`; the runtime `list_prompts()` call is the source of truth for the available-names list shown in the unknown-name UsageError.

7. **McpBackend Protocol intentionally does NOT declare `__enter__`/`__exit__`.** Pattern A spawns a fresh client per call inside the async helper, so there is no persistent connection to bracket CLI-side. The plan's prescribed `with backend:` wrapper was REMOVED from `commands/prompt.py` (the Protocol doesn't satisfy that surface; mypy strict catches it). Phase 60 may revisit if a persistent-loop refactor lands. The current shape: `backend = open_mcp_backend(ctx); try: result = backend.get_prompt(...); except McpError: ...`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan 59-01 sentinel-pinning tests obsolete after Plan 02 wires the bodies**

- **Found during:** Task 1 acceptance check (`pytest tests/test_mcp_backend_protocol_skeleton.py`).
- **Issue:** Plan 59-01 shipped two tests that asserted the Plan 02 sentinel `"Wired in Phase 59 Plan 02"` still raised verbatim:
  - `agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py::test_mcp_backend_skeleton_methods_raise_with_sentinel[McpStdioBackend|McpHttpBackend]`
  - `agent-brain-cli/tests/test_mcp_backend_factory.py::test_open_mcp_backend_unimplemented_methods_still_raise`

  Both tests were Plan 59-01's RED pinning intent — load-bearing because the sentinel literal was what Plan 02 would grep before replacing each body. Plan 02 wires the bodies → sentinel is gone by design → both tests fail. This is the same shape Plan 59-01 itself encountered with the pre-Phase-57 routing tests in commit `f6eddd3`.

- **Fix:** Inverted both tests to pin the post-Plan-02 contract:
  - `test_mcp_backend_skeleton_methods_raise_with_sentinel` → `test_mcp_backend_methods_no_longer_raise_plan_59_01_sentinel` (same 5 methods × 2 backends coverage; assertion flipped from `str(exc) == SENTINEL` to `SENTINEL not in str(exc)`; expected runtime error is now a real SDK connection failure bubbling up against a dummy backend — `BaseException` catch absorbs `BaseExceptionGroup` from anyio).
  - `test_open_mcp_backend_unimplemented_methods_still_raise` → `test_open_mcp_backend_returns_real_wired_backend_not_stub` (same intent: factory returns real `McpStdioBackend`, not a stub; calling `get_prompt` against a dummy raises a real failure — the sentinel literal MUST NOT appear in `str(exc)`).

  Renamed the `SKELETON_SENTINEL` constant to `PLAN_59_01_SENTINEL` to clarify its post-Plan-02 role as the negative-case anchor for regression detection.

- **Files modified:**
  - `agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py`
  - `agent-brain-cli/tests/test_mcp_backend_factory.py`
- **Verification:** Both renamed tests pass (`test_mcp_backend_methods_no_longer_raise_plan_59_01_sentinel[McpStdioBackend|McpHttpBackend]` 2/2 + `test_open_mcp_backend_returns_real_wired_backend_not_stub` 1/1); the 3 isinstance architectural pins continue to pass untouched.
- **Committed in:** `67796b7`.

**2. [Rule 1 - Bug] Plan-prescribed `with backend:` wrapper incompatible with the McpBackend Protocol**

- **Found during:** Task 2 mypy strict run.
- **Issue:** The plan's `<interfaces>` block for `commands/prompt.py` prescribed `with backend:` to wrap the `get_prompt` call. But the `McpBackend` Protocol (declared by Plan 59-01 at `agent-brain-cli/agent_brain_cli/client/protocol.py:131-170`) intentionally does NOT declare `__enter__`/`__exit__` — only `get_prompt`, `list_prompts`, `list_resources`, `list_resource_templates`, `read_resource`. mypy strict rejected the `with backend:` wrapper with two errors at line 131:
  ```
  agent_brain_cli/commands/prompt.py:131: error: "McpBackend" has no attribute "__enter__"
  agent_brain_cli/commands/prompt.py:131: error: "McpBackend" has no attribute "__exit__"
  ```
- **Fix:** Removed the `with backend:` wrapper from `commands/prompt.py`. The shape is now: `backend = open_mcp_backend(ctx); try: result = backend.get_prompt(...); except McpError: ...`. Pattern A spawns a fresh client per call inside the async helper, so there is no persistent connection to bracket CLI-side — the wrapper served no purpose against the Protocol surface anyway. Added a docstring comment explaining the omission (Pattern A reasoning + Phase 60 deferral).
- **Files modified:** `agent-brain-cli/agent_brain_cli/commands/prompt.py`.
- **Verification:** `mypy agent_brain_cli/commands/prompt.py` exits 0; 13/13 CliRunner tests pass.
- **Committed in:** `957bf3d` (rolled into the Task 2 GREEN commit since the wrapper never landed).

---

**Total deviations:** 2 auto-fixed (both Rule 1 bugs).

**Impact on plan:** Deviation #1 was strictly necessary for the Plan 59-01 regression check (Task 1 acceptance criterion). Deviation #2 was a plan-shape correction: the prescribed `with backend:` wrapper conflicted with the Plan 59-01 Protocol shape. Both deviations are documented for the Plan 59-03 planner — `agent-brain resources list/read` will face the same Protocol shape (no context-manager surface) and should NOT include `with backend:` wrappers in its prescribed code shapes.

## Issues Encountered

- **Path-dep stale install carries forward from Plan 59-01.** Same pattern documented in Plan 59-01's "Issues Encountered" section: after modifying `agent_brain_mcp/client.py` (added wire bodies), the `agent-brain-cli/.venv` still had the pre-Plan-59-02 snapshot of `agent_brain_mcp`. Fix: `pip install --force-reinstall --no-deps ../agent-brain-mcp` into the CLI venv. The Plan 59-01 Decisions documented this for downstream plans; Plan 59-02 hit it on the Task 1 GREEN → Task 2 RED transition. Plan 59-03 will hit it AGAIN every time it touches `client.py` (out of scope but expected).

- **Black + Ruff cycles around the GREEN commits.** Each TDD GREEN cycle's first `task before-push` run reformatted the new files (Black collapsed `prompt.py` body lines + sorted test-file imports). Resolved by `task before-push` (which calls `format` before `format:check`) on the next run. No semantic changes — folded into a single chore commit `e90ebb4`.

## User Setup Required

None — Plan 59-02 is purely additive wires + new Click command. No new env vars, secrets, services, or runtime configuration.

## Next Phase Readiness

- **Plan 59-03 can begin immediately.** The 5 method wires (`list_resources`, `list_resource_templates`, `read_resource`) it needs to ship `agent-brain resources list` + `agent-brain resources read <uri>` are wired and unit-tested on both backends. The `open_mcp_backend(ctx)` factory is the dispatcher Plan 59-03's `resources` Click sub-group will call. Plan 59-03 should NOT include `with backend:` wrappers in its command code (the Protocol shape doesn't satisfy that surface — Plan 02 deviation #2).
- **CLI-MCP-05 closed end-to-end.** Operators can invoke any of the 6 v1 MCP prompts via `agent-brain --transport mcp --mcp-transport {stdio|http} prompt <name> [--arg K=V]... [--json]` with the full no-silent-fallback + unknown-name-fallback contract.
- **No blockers.** `task before-push` exits 0 at HEAD `e90ebb4`. Plan 59-01's isinstance architectural pinning + Phase 56-03's BackendClient pinning continue to hold.

## Self-Check: PASSED

- `agent-brain-mcp/agent_brain_mcp/client.py` — FOUND (modified, sentinel `"Wired in Phase 59 Plan 02"` grep returns 0; `session.get_prompt(` grep returns 2; `_async_get_prompt`/`_async_list_prompts`/`_async_list_resources`/`_async_list_resource_templates`/`_async_read_resource` each appear 2× — once per backend)
- `agent-brain-cli/agent_brain_cli/commands/prompt.py` — FOUND (created, `@click.command("prompt")` grep returns 1, `open_mcp_backend(ctx)` grep returns 1)
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` — FOUND (modified, `from .prompt import prompt_command` grep returns 1, `"prompt_command"` in `__all__` returns 1)
- `agent-brain-cli/agent_brain_cli/cli.py` — FOUND (modified, `cli.add_command(prompt_command` grep returns 1)
- `agent-brain-mcp/tests/test_mcp_backend_prompts_wire.py` — FOUND (created, 13 tests pass)
- `agent-brain-cli/tests/test_prompt_command.py` — FOUND (created, 13 tests pass)
- `agent-brain-cli/tests/test_mcp_backend_factory.py` — FOUND (modified Rule 1)
- `agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py` — FOUND (modified Rule 1, 3 isinstance pins survive)
- Commits FOUND: `01057da` `92d0fe6` `67796b7` `e23d118` `957bf3d` `e90ebb4` (all 6 present in `git log`)
- `agent-brain prompt --help` exits 0 and lists `<NAME>`, `--arg`, `--json`
- `agent-brain prompt foo` (no --transport) exits 2 with verbatim `--transport mcp` UsageError
- `task before-push` exits 0 across the monorepo

---
*Phase: 59-cli-prompts-resources-commands*
*Completed: 2026-06-08*
