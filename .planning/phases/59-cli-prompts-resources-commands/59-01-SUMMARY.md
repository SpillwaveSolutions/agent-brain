---
phase: 59-cli-prompts-resources-commands
plan: 01
subsystem: api
tags: [mcp, click, protocol, runtime_checkable, transport, skeleton-first]

# Dependency graph
requires:
  - phase: 56-cli-mcp-skeleton
    provides: BackendClient Protocol + McpStdioBackend / McpHttpBackend skeleton-first pattern (Plan 56-03)
  - phase: 57-cli-mcp-wire
    provides: open_backend(ctx) -> BackendClient dispatcher + Pattern A asyncio.run sync facade + verbatim §3.5 wording (Plan 57-01..03)
  - phase: 58-mcp-helper-commands
    provides: agent-brain mcp start/stop + mcp.runtime.json discovery + _resolve_state_dir_for_discovery() helper (Plan 58-01..03)
provides:
  - McpBackend @runtime_checkable Protocol — 5 method signatures (get_prompt, list_prompts, list_resources, list_resource_templates, read_resource)
  - 10 skeleton method bodies (5 × 2 backends) raising NotImplementedError("Wired in Phase 59 Plan 02") — sentinel Plan 02 will grep
  - open_mcp_backend(ctx, *, timeout=30.0) -> McpBackend factory enforcing --transport mcp at a single point
  - Architectural-boundary pin: isinstance(DocServeClient(...), McpBackend) == False (load-bearing negative case)
affects:
  - 59-02 (wires the 5 method bodies on both MCP backends + adds agent-brain prompt command)
  - 59-03 (adds agent-brain resources sub-group; reuses open_mcp_backend factory verbatim)
  - 60+ (any new MCP-only CLI command — must call open_mcp_backend, never open_backend, for the prompts/resources surface)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Protocol split: BackendClient (tools surface) vs McpBackend (prompts+resources surface) — DocServeClient deliberately does NOT satisfy McpBackend"
    - "Single-point factory enforcement: open_mcp_backend(ctx) is the only place the --transport mcp check lives; every MCP-only command inherits the contract for free"
    - "Skeleton-first per Plan 56-03 / 57-01 precedent: Plan 01 closes the architectural boundary so Plan 02 can wire bodies without simultaneously debugging the Protocol shape"

key-files:
  created:
    - agent-brain-cli/tests/test_mcp_backend_protocol.py (4 shape-introspection tests)
    - agent-brain-cli/tests/test_mcp_backend_factory.py (8 factory tests — 4 negative parametrized + 4 positive)
    - agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py (5 architectural pins — 3 isinstance + parametrized sentinel × 2 backends)
  modified:
    - agent-brain-cli/agent_brain_cli/client/protocol.py (+44 LOC: new McpBackend Protocol + __all__ update)
    - agent-brain-cli/agent_brain_cli/client/transport.py (+91 LOC: open_mcp_backend factory + McpBackend import)
    - agent-brain-mcp/agent_brain_mcp/client.py (+51 LOC: 10 skeleton method bodies across both backends)
    - agent-brain-cli/tests/test_transport_selector_mcp.py (deviation Rule 1: updated 2 post-Phase-57 routing assertions)

key-decisions:
  - "Protocol split is load-bearing — McpBackend is a SEPARATE Protocol, NOT extending BackendClient. DocServeClient (HTTP/UDS) cannot satisfy McpBackend by design; the negative isinstance pinning test makes this architectural fact explicit and lasting."
  - "open_mcp_backend(ctx) is the single point of --transport mcp enforcement — every Phase 59 MCP-only command calls this factory (not open_backend). Future MCP-only commands inherit the contract for free; the no-silent-fallback §3.5 wording stays DRY."
  - "Skeleton sentinel literal is verbatim 'Wired in Phase 59 Plan 02' (no period, no extra spaces). Plan 59-02 will grep for this exact string before replacing each body — a drift would silently de-couple the skeletons from the wire plan."
  - "Return shapes are dict[str, Any] / list[dict[str, Any]] (NOT typed dataclasses). Per-method coercion lives at the Plan 59-02 / 59-03 command layer — mirrors the existing _unwrap_payload / _unwrap_resource_body pattern; Phase 60+ may revisit."
  - "generic UsageError wording in open_mcp_backend ('This command requires --transport mcp; example: ... <command>') — each command may wrap with its own placeholder ('prompt', 'resources list', etc.) but the factory default surfaces a working example invocation."

patterns-established:
  - "Pattern A — protocol_attrs introspection in tests: hasattr(Proto, '__protocol_attrs__') then frozenset(Proto.__protocol_attrs__) — Python 3.12+ shape pinning."
  - "Pattern B — sibling protocol files: test_<protocol>_protocol.py in agent-brain-cli (shape) + test_<protocol>_protocol_skeleton.py in agent-brain-mcp (instance + sentinel) — mirrors the Plan 56-02 / 56-03 split."
  - "Pattern C — open_mcp_backend factory: lazy-import McpStdioBackend/McpHttpBackend, cast(McpBackend, ...) at the return site, mirrors open_backend's MCP branch verbatim except returns McpBackend instead of BackendClient."

requirements-completed: []  # CLI-MCP-05 foundation only; Plan 59-02 closes the requirement.

# Metrics
duration: 12min
completed: 2026-06-08
---

# Phase 59 Plan 01: McpBackend Protocol + open_mcp_backend factory + skeletons Summary

**New `McpBackend` `@runtime_checkable` Protocol pins the architectural boundary (DocServeClient ⊄ McpBackend); 10 skeleton methods on both MCP backends ready for Plan 02 wiring; `open_mcp_backend(ctx)` factory enforces `--transport mcp` at a single point.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-06-08T21:15:38Z
- **Completed:** 2026-06-08T21:28:04Z
- **Tasks:** 4
- **Files modified:** 7 (3 source + 3 test + 1 test-fix for pre-existing Phase 57 drift)

## Accomplishments

- **McpBackend Protocol** declared in `agent-brain-cli/agent_brain_cli/client/protocol.py` (lines 131-170) alongside `BackendClient`. Both `@runtime_checkable`, both exported via `__all__`. Five method signatures verbatim from the CONTEXT decision: `get_prompt(name, arguments=None)`, `list_prompts()`, `list_resources()`, `list_resource_templates()`, `read_resource(uri)`. Return types are `dict[str, Any]` / `list[dict[str, Any]]` (per-method coercion deferred to Plan 02/03 command layer).

- **10 skeleton method bodies** added to `McpStdioBackend` (after `clear_cache`, lines 820-835) and `McpHttpBackend` (after `clear_cache`, lines 1223-1238) in `agent-brain-mcp/agent_brain_mcp/client.py`. Every body raises `NotImplementedError("Wired in Phase 59 Plan 02")` — exact literal Plan 02 will grep. No `from __future__ import annotations` re-import (Plan 56-03 burned on that).

- **open_mcp_backend(ctx, *, timeout=30.0) -> McpBackend** factory added to `agent-brain-cli/agent_brain_cli/client/transport.py` (lines 168-258). Single-point enforcement of `--transport mcp`: raises `click.UsageError("This command requires --transport mcp; example: agent-brain --transport mcp --mcp-transport stdio <command>")` when `transport_hint != "mcp"`. Mirrors `open_backend`'s dispatch verbatim for the MCP sub-branches (stdio binary precheck, mcp.runtime.json discovery, `cast(McpBackend, ...)` at return sites).

- **Architectural-boundary pin** at `agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py::test_doc_serve_client_does_not_satisfy_mcp_backend` — the load-bearing negative case. UDS/HTTP transports cannot speak MCP prompts/resources by design; this isinstance assertion makes the boundary explicit and lasting.

- **17 new unit tests pass** across 3 new test files. Plus 8 pre-existing Phase 57 routing tests adapted to post-Phase-57 reality (Rule 1 deviation).

## Task Commits

Each task was committed atomically (TDD red-then-green for Tasks 1-3):

1. **Task 1 RED** — `7bb7b61` (test): add failing test for McpBackend Protocol shape
2. **Task 1 GREEN** — `a6de20e` (feat): add McpBackend Protocol alongside BackendClient
3. **Task 2 RED** — `0a5ab94` (test): add failing skeleton + isinstance pinning tests for McpBackend
4. **Task 2 GREEN** — `84ce49a` (feat): add 5 McpBackend skeleton methods to both MCP backends
5. **Task 3 RED** — `ecf4843` (test): add failing tests for open_mcp_backend factory
6. **Task 3 GREEN** — `93582a7` (feat): add open_mcp_backend(ctx) factory enforcing --transport mcp
7. **Task 4 (Rule 1 deviation)** — `f6eddd3` (fix): update Phase 57 routing tests after Plan 57-02/03 wired bodies

## Files Created/Modified

### Created
- `agent-brain-cli/tests/test_mcp_backend_protocol.py` — 4 shape-introspection tests (declared methods, distinctness from BackendClient, runtime_checkable decoration, negative stub case).
- `agent-brain-cli/tests/test_mcp_backend_factory.py` — 8 factory tests: 4 negative parametrized (`transport_hint` ∈ {None, "auto", "http", "uds"}) + 4 positive (stdio happy path, http happy path, missing-binary verbatim wording, skeleton sentinel reach-through).
- `agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py` — 5 architectural pins: 3 isinstance assertions (positive×2 + load-bearing negative DocServeClient ⊄ McpBackend) + parametrized sentinel across 5 methods × 2 backends.

### Modified
- `agent-brain-cli/agent_brain_cli/client/protocol.py` — Appended `McpBackend` Protocol after `BackendClient`; `__all__` now exports both.
- `agent-brain-cli/agent_brain_cli/client/transport.py` — Imported `McpBackend` alongside `BackendClient`; appended `open_mcp_backend` factory after `open_backend`.
- `agent-brain-mcp/agent_brain_mcp/client.py` — Added 5 skeleton method bodies to `McpStdioBackend` (after `clear_cache`) and 5 to `McpHttpBackend` (after `clear_cache`). Sentinel literal exactly `"Wired in Phase 59 Plan 02"` (grep returns 10).
- `agent-brain-cli/tests/test_transport_selector_mcp.py` — Rule 1 deviation: updated 2 pre-existing Phase 57 routing tests that asserted the obsolete `"Wired in Phase 57+"` sentinel (Phase 57 Plan 02 + 03 wired the bodies — only `reset()` still raises). Renamed tests + preserved routing-coverage intent.

## Decisions Made

1. **Protocol split as architectural boundary** — `McpBackend` is a separate Protocol class, NOT extending `BackendClient`. The negative isinstance pinning test (`DocServeClient ⊄ McpBackend`) is load-bearing — if a future plan accidentally adds MCP-only methods to `DocServeClient` (e.g., to "unify" the surface), that test catches it. The CONTEXT decision is preserved in code.

2. **Single-point `--transport mcp` enforcement** — `open_mcp_backend(ctx)` is the only place where the transport check lives. Plan 59-02's `agent-brain prompt` and Plan 59-03's `agent-brain resources *` will call this factory directly; future MCP-only commands inherit the contract for free without duplicating the `if transport_hint != "mcp"` block.

3. **Verbatim sentinel literal** — Every skeleton body raises `NotImplementedError("Wired in Phase 59 Plan 02")` with no period, no extra spaces, no paraphrase. Plan 59-02 will grep for this exact string before replacing each body. The skeleton tests pin this literal byte-for-byte across both backends × 5 methods.

4. **Generic UsageError wording in factory** — `"This command requires --transport mcp; example: agent-brain --transport mcp --mcp-transport stdio <command>"`. Each MCP-only command may wrap and substitute its own name (`prompt`, `resources list`, etc.) for the trailing placeholder, but the factory default is a complete, runnable example invocation if the wrapper is ever forgotten.

5. **Return shapes are `dict[str, Any]` / `list[dict[str, Any]]`** — NOT typed dataclasses. The MCP wire payloads for `prompts/get` and `resources/read` differ enough that per-method coercion at the command layer (Plan 02/03) is cleaner than forcing a typed shape here. Mirrors the existing `_unwrap_payload` / `_unwrap_resource_body` helpers. Phase 60+ may revisit if a typed-resource layer pays for itself.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing Phase 57 routing tests asserted obsolete sentinel**
- **Found during:** Task 4 (`task before-push`)
- **Issue:** `tests/test_transport_selector_mcp.py::TestSkeletonRoutingStdio::test_stdio_branch_reaches_skeleton` and `TestSkeletonRoutingHttp::test_http_branch_reaches_skeleton` asserted `"Wired in Phase 57+"` was present in the CLI output. But Phase 57 Plan 02 + 03 actually wired all 10 method bodies on both backends (only `reset()` still raises `NotImplementedError`). The tests should have been updated when those plans landed. As-is, they:
  - On stdio: spawned a real `agent-brain-mcp` subprocess, attempted MCP handshake, got `ExceptionGroup('unhandled errors in a TaskGroup', [ConnectError])` — sentinel never appeared.
  - On http: opened a real `streamablehttp_client` against `http://127.0.0.1:9999/mcp`, got the same `ConnectError`.
  
  This was a true regression in the existing test surface, surfaced by `task before-push` (Plan 59-01 success criterion #5).
- **Fix:** Preserved the routing-coverage intent — assert `open_backend` returns the correct `McpStdioBackend` / `McpHttpBackend` instance for each MCP sub-branch. Patched `open_backend` at the query command's call site so the wired body never actually spawns a subprocess; the test captures the real backend instance via a side-effect spy and asserts its type. Renamed tests to reflect the post-Phase-57 contract:
  - `test_stdio_branch_reaches_skeleton` → `test_stdio_branch_reaches_mcp_stdio_backend`
  - `test_http_branch_reaches_skeleton` → `test_http_branch_reaches_mcp_http_backend`
- **Files modified:** `agent-brain-cli/tests/test_transport_selector_mcp.py`
- **Verification:** Both renamed tests pass; `task before-push` exits 0; full suite reports `501 passed, 110 deselected, 2 warnings`.
- **Committed in:** `f6eddd3` (Task 4 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — Rule 1)
**Impact on plan:** The fix was strictly necessary for `task before-push` to pass (Plan 59-01 success criterion #5). Scope was contained to the same routing-coverage intent the original tests had — no new assertions beyond what was already there in concept, just adapted to the post-Phase-57 reality. No new functionality added.

## Issues Encountered

- **Path-dep stale install caches across both venvs.** Both `agent-brain-cli` and `agent-brain-mcp` declare each other as `develop=false` path deps. After updating `agent_brain_cli/client/protocol.py` (adding `McpBackend`), the `agent-brain-mcp/.venv` still had the pre-Plan-59 snapshot of `agent_brain_cli`. Same problem after updating `agent_brain_mcp/client.py` (adding skeletons) — the `agent-brain-cli/.venv` had the pre-Plan-59 snapshot of `agent_brain_mcp`. `poetry install` saw no diff because lockfile was unchanged. Fix: `pip install --force-reinstall --no-deps ../<other-package>` into each affected venv. Documented for downstream plans (the same pattern will hit Plan 59-02 every time we touch `client.py` skeletons before testing from the CLI side).

## User Setup Required

None — Plan 59-01 is purely additive Protocol + skeleton + factory work. No new env vars, secrets, or services.

## Next Phase Readiness

- **Plan 59-02 can begin immediately.** The skeleton sentinel `"Wired in Phase 59 Plan 02"` is pinned in 10 places across both backends; Plan 02 greps for this exact string to find each replacement site. The `McpBackend` Protocol is the contract Plan 02's wire bodies must satisfy. The `open_mcp_backend(ctx)` factory is the dispatcher Plan 02's `agent-brain prompt` command calls.
- **Plan 59-03 inherits the factory and Protocol unchanged.** The `agent-brain resources` sub-group will dispatch through the same `open_mcp_backend(ctx)` factory verbatim.
- **No blockers.** The full monorepo `task before-push` exits 0 at HEAD `f6eddd3`.

## Self-Check: PASSED

- `agent-brain-cli/agent_brain_cli/client/protocol.py` — FOUND (modified, `class McpBackend(Protocol)` present)
- `agent-brain-cli/agent_brain_cli/client/transport.py` — FOUND (modified, `def open_mcp_backend(` present)
- `agent-brain-mcp/agent_brain_mcp/client.py` — FOUND (modified, sentinel grep returns 10)
- `agent-brain-cli/tests/test_mcp_backend_protocol.py` — FOUND (created, 4 tests passing)
- `agent-brain-cli/tests/test_mcp_backend_factory.py` — FOUND (created, 8 tests passing)
- `agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py` — FOUND (created, 5 tests passing including DocServeClient ⊄ McpBackend negative pin)
- `agent-brain-cli/tests/test_transport_selector_mcp.py` — FOUND (modified, Rule 1 deviation)
- Commits FOUND: `7bb7b61`, `a6de20e`, `0a5ab94`, `84ce49a`, `ecf4843`, `93582a7`, `f6eddd3` (all 7 present in `git log`)

---
*Phase: 59-cli-prompts-resources-commands*
*Completed: 2026-06-08*
