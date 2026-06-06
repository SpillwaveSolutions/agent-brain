---
phase: 57-cli-transport-selector-byte-identical-equivalence
plan: 01
subsystem: cli-transport-selector

tags: [mcp, v3, cli, click, transport-dispatcher, backend-client, no-silent-fallback, exit-2, shutil-which, lazy-import, soft-dep]

# Dependency graph
requires:
  - phase: 56-01
    provides: v3 design doc (§2.1 three-axis transport model, §3.1 lazy import contract, §3.5 verbatim no-silent-fallback wording)
  - phase: 56-02
    provides: BackendClient @runtime_checkable Protocol — 15 methods, return type widened from DocServeClient on the open_backend factory
  - phase: 56-03
    provides: McpStdioBackend + McpHttpBackend skeleton classes — NotImplementedError("Wired in Phase 57+") sentinel bodies; ctx-mgr + close() real; dispatcher routes here from Phase 57-01
provides:
  - "agent_brain_cli.config.resolve_mcp_transport(*, mcp_transport_hint, mcp_url_override) -> tuple[Literal['stdio','http'], str | None] — MCP-axis per-axis resolver with click.UsageError on missing http URL"
  - "agent_brain_cli.cli — 4-choice --transport (auto/http/uds/mcp) + --mcp-transport (stdio/http) + --mcp-url group flags wired to ctx.obj keys mcp_transport_hint and mcp_url_override"
  - "agent_brain_cli.client.transport.open_backend(ctx) -> BackendClient — 4-branch dispatcher (mcp+stdio, mcp+http, http, uds) with shutil.which precheck on stdio branch; replaces open_client"
  - "8 command modules atomically swapped to import open_backend from the dispatcher (20 callsite changes across cache/folders/index/inject/jobs/query/reset/status)"
  - "agent-brain-cli adds agent-brain-ag-mcp as a dev path dep (develop=false) so the CLI test suite can exercise the MCP dispatcher branches without depending on a PyPI-published mcp package"
  - "8 new tests in tests/test_transport_selector_mcp.py covering all three §3.5 misuse cases (verbatim wording exit-2), skeleton routing on both MCP branches, HTTP regression, and open_client removal smoke test"
  - "7 new tests in tests/test_config_resolve_mcp_transport.py covering precedence (flag/env/default), the §3.5 case 2 error path, and at-call-time env reads"
affects:
  - "Phase 57-02 (query() wire-up on both MCP backends — replaces NotImplementedError in McpStdioBackend.query and McpHttpBackend.query; the dispatcher already routes here)"
  - "Phase 57-03 (remaining BackendClient methods wired on both MCP backends — closes CLI-MCP-03 fully; reset() stays NotImplementedError per design doc §5)"
  - "Phase 58 (--mcp-url becomes optional once mcp.runtime.json discovery lands — error message text in transport.py § case 2 will be swapped at that point)"
  - "Phase 60 (subprocess hygiene replaces command='agent-brain-mcp' with full subprocess.Popen lifecycle on the stdio branch; shutil.which precheck remains as the first gate)"

# Tech tracking
tech-stack:
  added: [agent-brain-ag-mcp (dev path dep on agent-brain-cli side, mirrors Phase 56-03 precedent)]
  patterns:
    - "Per-axis pure resolver: resolve_mcp_transport mirrors resolve_transport's tuple-returning shape — single-axis precedence chains compose cleaner than one dual-axis resolver (CONTEXT decision honored)"
    - "Lazy import inside the mcp branch — `from agent_brain_mcp.client import McpHttpBackend, McpStdioBackend` only runs when --transport mcp is active; protects HTTP/UDS-only invocations from paying the MCP SDK import cost and from breaking when agent-brain-mcp isn't installed"
    - "shutil.which PATH precheck guards the stdio dispatcher branch — runs BEFORE McpStdioBackend instantiation so missing-binary failures surface as click.UsageError(exit 2) with verbatim §3.5 wording, NOT as a downstream subprocess spawn error"
    - "cast(BackendClient, ...) on the MCP backend returns — agent_brain_mcp is under mypy's ignore_missing_imports, so the lazy-imported classes are typed as Any; the runtime @runtime_checkable Protocol contract is pinned by Phase 56-03's isinstance test in agent-brain-mcp/tests/test_cli_backends_skeleton.py"
    - "20-callsite atomic rename: all 8 command modules swap `from ..client.transport import open_client` → `open_backend` AND `with open_client(ctx) as client:` → `with open_backend(ctx) as client:` in a single commit; mypy strict catches any miss via the BackendClient return-type widening"
    - "Late `import click as _click` inside the resolve_mcp_transport error branch — keeps config.py's top-level imports free of a Click dependency (config.py today imports only yaml + pydantic); the error path is hit only on flag misuse, so the per-call import cost is irrelevant"

key-files:
  created:
    - "agent-brain-cli/tests/test_config_resolve_mcp_transport.py (155 lines, 7 tests on resolve_mcp_transport precedence + §3.5 case 2 error path)"
    - "agent-brain-cli/tests/test_transport_selector_mcp.py (269 lines, 8 tests covering all three §3.5 cases as exit-2 + skeleton routing + HTTP regression + open_client-gone smoke)"
  modified:
    - "agent-brain-cli/agent_brain_cli/config.py (added resolve_mcp_transport(...) helper at end of file, mirrors resolve_transport's shape)"
    - "agent-brain-cli/agent_brain_cli/cli.py (--transport choice extended to 4 values, two new group flags --mcp-transport + --mcp-url, ctx.obj writes two new keys)"
    - "agent-brain-cli/agent_brain_cli/client/transport.py (full rewrite — open_client → open_backend with 4-branch dispatcher + shutil.which precheck; was 61 lines, now 137 lines)"
    - "agent-brain-cli/agent_brain_cli/commands/{cache,folders,index,inject,jobs,query,reset,status}.py (20-callsite atomic swap of open_client → open_backend; jobs.py also retyped 4 helper signatures DocServeClient → BackendClient)"
    - "agent-brain-cli/agent_brain_cli/client/api_client.py (single docstring reference open_client → open_backend updated)"
    - "agent-brain-cli/pyproject.toml (added agent-brain-ag-mcp as dev path dep, develop=false)"
    - "agent-brain-cli/poetry.lock (regenerated to include agent-brain-ag-mcp 10.2.1 + transitive mcp SDK + jsonschema + sse-starlette etc.)"
    - "11 existing test files patched to mock open_backend instead of open_client (cache/cli/inject/folders/folders_watch/query/query_modes/query_explain/api_key/transport_selector/config_resolve_transport)"

key-decisions:
  - "shutil imported at module-top of transport.py (not inside the dispatcher branch). Rationale: (a) shutil is stdlib, no import cost concern; (b) testability — the test_transport_selector_mcp.py §3.5 case 3 test uses monkeypatch.setattr('shutil.which', lambda cmd: None) which targets the global module reference, matching what the dispatcher imports. CONTEXT marked this as Claude's discretion; module-top recommended for testability."
  - "resolve_mcp_transport return type stayed as tuple[Literal['stdio','http'], str | None] — matched the original plan spec verbatim. str | None target is None for stdio (subprocess, no URL) and the resolved URL string for http. This mirrors resolve_transport's (transport, target) shape per-axis."
  - "agent-brain-ag-mcp dev path dep added with develop=false (mirrors the Phase 56-03 precedent on the MCP side). Without this dev dep, the test suite's §3.5 case 3 and skeleton-routing tests have nothing to dispatch to — they would all fall through to the §3.5 case 1 ImportError path. With develop=true, the same .pth-injection issue Phase 56-03 hit would let agent-brain-mcp's tests/ directory collide with agent-brain-cli's tests/__init__.py. develop=false installs only the agent_brain_mcp/ package."
  - "Sync facade Pattern A vs Pattern B decision (per design doc §3.2) is DEFERRED to Plan 57-02 — Plan 57-01 only routes; no method body wiring happens here, so the per-call asyncio overhead question doesn't surface yet. Plan 57-02 measures + decides."
  - "cast(BackendClient, ...) wraps the McpStdioBackend and McpHttpBackend constructor returns inside the mcp branch. mypy strict + ignore_missing_imports=true means the lazy-imported classes are typed as Any; without the cast, mypy emits `Returning Any from function declared to return 'BackendClient' [no-any-return]`. The runtime @runtime_checkable Protocol conformance is pinned by Phase 56-03's tests/test_cli_backends_skeleton.py — the cast is purely a static-typing convenience."
  - "jobs.py command module retyped four helper signatures (_list_jobs, _show_job_detail, _cancel_job, _watch_jobs) from DocServeClient to BackendClient. The other 7 command modules all use the context manager block in-place without passing the client to typed helpers, so they needed no further changes. This was a mypy-strict-driven correctness fix surfaced by the open_backend return-type widening."
  - "agent_brain_cli.client import in jobs.py dropped DocServeClient — only ConnectionError and ServerError remain. BackendClient is imported separately from the new ..client.protocol path. Same effect; cleaner import hierarchy now that DocServeClient is no longer the concrete type the command handlers manipulate."

patterns-established:
  - "Three-cases exit-2 contract for --transport mcp misuse — verbatim §3.5 wording test-pinned. Future MCP-related CLI flags should follow the same pattern: explicit selection, no silent fallback, verbatim error wording, test asserts exit_code == 2 + substring match on result.output. Phase 58's mcp.runtime.json discovery error will swap the case-2 wording but keep the exit-2 contract."
  - "Two-tier transport axis model: resolve_transport for cli_listen_transport (HTTP/UDS), resolve_mcp_transport for cli_backend_transport (stdio/http). Each is a pure per-axis function returning (transport, target). The dispatcher in transport.py composes them — never the resolvers themselves. Sets the shape Phase 58/59 follow when adding mcp.runtime.json discovery."
  - "Test pattern: pytest.importorskip('agent_brain_mcp.client') at the top of tests that require the package to be importable. Falls through cleanly when the soft dep isn't installed (e.g. on a CI runner that runs only the agent-brain-cli unit tests in isolation). The §3.5 case 1 test (which exercises the no-package path) uses monkeypatch.setitem(sys.modules, 'agent_brain_mcp.client', None) — does NOT need the package present."
  - "Late `import click as _click` inside config.py functions — keeps config.py's top-level imports unchanged (only yaml + pydantic). The error path's import cost is irrelevant because the error path runs once per CLI invocation max."

requirements-completed: []  # CLI-MCP-03 partial — selector flags + dispatcher + 3 §3.5 misuse cases land; full method wiring closes in 57-03

# Metrics
duration: ~12 min
completed: 2026-06-06
---

# Phase 57 Plan 01: CLI Transport Selector + 3 §3.5 Misuse Cases Summary

**`agent-brain --transport mcp [--mcp-transport stdio|http] [--mcp-url …]` lands as a real, dispatching transport selector — `open_client(ctx)` is gone; `open_backend(ctx) -> BackendClient` routes across 4 branches (mcp+stdio, mcp+http, http, uds) with a `shutil.which("agent-brain-mcp")` PATH precheck and lazy `agent_brain_mcp.client` import; all three v3 design-doc §3.5 misuse cases surface as exit-code-2 `click.UsageError`s with verbatim wording — case 1 ("install agent-brain-mcp to use --transport mcp"), case 2 ("discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57"), case 3 ("agent-brain-mcp not found on PATH; install agent-brain-mcp into the same Python environment"); 20 call-sites atomically swapped across 8 command modules; 15 new tests + all 451 existing CLI tests green; `task before-push` exits 0 end-to-end (CLI 451 passed, MCP 474 passed, server suite passed, UDS suite passed).**

## Performance

- **Duration:** ~12 min (704 seconds)
- **Started:** 2026-06-06T22:55:41Z
- **Completed:** 2026-06-06T23:07:25Z
- **Tasks:** 4 (Task 1 resolve_mcp_transport + tests, Task 2 cli.py group flags, Task 3 dispatcher rename + 20-callsite swap + 8 tests, Task 4 task before-push gate)
- **Files modified:** 23 (3 source files + 12 test files + 1 pyproject + 1 poetry.lock + 8 command modules atomically — Task 3 commit was the largest)
- **Tests added:** 15 (7 in test_config_resolve_mcp_transport.py + 8 in test_transport_selector_mcp.py)

## Accomplishments

- Filed `agent_brain_cli/config.py::resolve_mcp_transport(*, mcp_transport_hint, mcp_url_override) -> tuple[Literal["stdio","http"], str | None]` — pure per-axis resolver with precedence chain (flag → env → "stdio" default), URL precedence (flag → env → exit-2 error), and a late `import click as _click` inside the error branch keeping the module's top-level Click-free.
- Extended `agent_brain_cli/cli.py` top-level Click group with `--transport mcp` (4th Choice value), `--mcp-transport stdio|http` (new group flag, defaults None → env → "stdio"), and `--mcp-url URL` (new group flag, defaults None → env → resolve_mcp_transport error). Both new keys land on `ctx.obj["mcp_transport_hint"]` and `ctx.obj["mcp_url_override"]`. Help text mentions all 4 transports and explains both new flags.
- Rewrote `agent_brain_cli/client/transport.py` end-to-end: `open_client(ctx) -> DocServeClient` is gone, replaced by `open_backend(ctx) -> BackendClient` with the 4-branch dispatcher. The mcp branch lazy-imports `agent_brain_mcp.client` (soft dep — gives the §3.5 case 1 error message on ImportError) and on the stdio sub-branch runs `shutil.which("agent-brain-mcp")` as a PATH precheck (gives the §3.5 case 3 error message on None). `cast(BackendClient, ...)` wraps the MCP-backend constructor returns to satisfy mypy strict (agent_brain_mcp is under ignore_missing_imports).
- Atomically swapped 20 call-sites across 8 command modules (cache, folders, index, inject, jobs, query, reset, status) — each file's `from ..client.transport import open_client` → `from ..client.transport import open_backend` AND every `with open_client(ctx) as client:` → `with open_backend(ctx) as client:`. mypy strict + the BackendClient return-type widening verified no callsite was missed.
- Retyped 4 helper signatures in jobs.py (`_list_jobs`, `_show_job_detail`, `_cancel_job`, `_watch_jobs`) from `DocServeClient` to `BackendClient`. The other 7 command modules used the context-manager block inline without passing the client into typed helpers, so no further command-side type changes were needed.
- Added `agent-brain-ag-mcp` as a dev path dep on agent-brain-cli's pyproject.toml with `develop = false` (mirrors Phase 56-03's precedent on the MCP side). Without this dev dep, the §3.5 case 3 and skeleton-routing tests would all fall through to the §3.5 case 1 ImportError path. `develop = false` avoids the .pth shadow-collision that develop=true would create with agent-brain-cli's tests/__init__.py.
- Filed `tests/test_config_resolve_mcp_transport.py` (155 lines, 7 tests): flag-wins-stdio, flag-wins-http-with-url, env-precedence, default-is-stdio, env-supplies-url-when-flag-missing, §3.5 case 2 error path, at-call-time env reads sanity.
- Filed `tests/test_transport_selector_mcp.py` (269 lines, 8 tests): §3.5 case 1 (no package via sys.modules None monkeypatch), §3.5 case 2 (http without url), §3.5 case 3 (stdio + shutil.which None — verbatim wording asserted), skeleton routing on stdio branch (NotImplementedError surfaces), skeleton routing on http branch (same), HTTP regression (rename didn't break --transport http), open_backend importable, open_client gone.
- Updated 11 existing test files that mocked `@patch("agent_brain_cli.commands.X.open_client")` to use `.open_backend` — full suite stays green (451 passed).
- Quality gates green: Black/Ruff/mypy strict all clean on the modified files. `task before-push` from monorepo root exits 0 — CLI suite (451 tests) + MCP suite (474 tests + 91% coverage) + server suite + UDS suite + lock-drift check all pass in 13.69s for the MCP arm + similar for the others.

## Task Commits

Each task was committed atomically:

1. **Task 1: resolve_mcp_transport helper + 7 tests** — `5448420` (feat)
2. **Task 2: --transport mcp / --mcp-transport / --mcp-url flags** — `075cea9` (feat)
3. **Task 3: open_backend dispatcher rename + 20-callsite swap + 8 tests + dev path dep** — `cd8e9cb` (feat)
4. **Task 4: task before-push exit 0** — no separate commit (verification only; nothing new to add); plan-metadata commit follows.

## Files Created/Modified

- `agent-brain-cli/agent_brain_cli/config.py` (modified) — Added `resolve_mcp_transport(*, mcp_transport_hint, mcp_url_override)` at end of file (mirrors the existing `resolve_transport`'s shape). Returns `("stdio", None)` by default, `("http", url)` when http is selected with a resolvable URL, raises `click.UsageError("discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57")` when http is selected without a URL.
- `agent-brain-cli/agent_brain_cli/cli.py` (modified) — `--transport` Choice extended to `["auto","http","uds","mcp"]`; added `--mcp-transport stdio|http` and `--mcp-url URL` group flags between `--base-url` and `--debug-transport`; `cli(...)` parameter list extended with `mcp_transport` + `mcp_url`; `ctx.obj` write block adds 2 new keys.
- `agent-brain-cli/agent_brain_cli/client/transport.py` (modified, full rewrite from 61 → 137 lines) — `open_client` gone. `open_backend(ctx) -> BackendClient` with 4-branch dispatcher. MCP backends lazy-imported. `shutil.which("agent-brain-mcp")` precheck on stdio branch. `cast(BackendClient, ...)` on both MCP constructor returns. Module docstring documents the rename + all 3 §3.5 cases verbatim.
- `agent-brain-cli/agent_brain_cli/commands/cache.py` (modified) — 2 callsite swaps (1 import + 2 `with open_backend(ctx)`).
- `agent-brain-cli/agent_brain_cli/commands/folders.py` (modified) — 4 callsite swaps (1 import + 3 `with open_backend(ctx)`).
- `agent-brain-cli/agent_brain_cli/commands/index.py` (modified) — 2 callsite swaps (1 import + 1 callsite).
- `agent-brain-cli/agent_brain_cli/commands/inject.py` (modified) — 2 callsite swaps.
- `agent-brain-cli/agent_brain_cli/commands/jobs.py` (modified) — 2 callsite swaps PLUS 4 helper-signature retypes (`_list_jobs`, `_show_job_detail`, `_cancel_job`, `_watch_jobs`: `DocServeClient` → `BackendClient`); dropped `DocServeClient` from the `..client` import; added new `..client.protocol.BackendClient` import.
- `agent-brain-cli/agent_brain_cli/commands/query.py` (modified) — 2 callsite swaps.
- `agent-brain-cli/agent_brain_cli/commands/reset.py` (modified) — 2 callsite swaps.
- `agent-brain-cli/agent_brain_cli/commands/status.py` (modified) — 3 callsite swaps (1 import + 1 callsite + 1 docstring reference).
- `agent-brain-cli/agent_brain_cli/client/api_client.py` (modified, 1 line) — single docstring sphinx ref updated `open_client` → `open_backend`.
- `agent-brain-cli/pyproject.toml` (modified) — added `agent-brain-ag-mcp = { path = "../agent-brain-mcp", develop = false }` to `[tool.poetry.group.dev.dependencies]` with a 6-line inline justification comment.
- `agent-brain-cli/poetry.lock` (modified) — regenerated to include `agent-brain-ag-mcp 10.2.1` (path source, NOT develop) + transitives: `mcp 1.27.2`, `jsonschema 4.26.0`, `jsonschema-specifications 2025.9.1`, `sse-starlette 3.0.3`, `httpx-sse 0.4.3`, `pyjwt 2.13.0`, `python-multipart 0.0.32`, `referencing 0.37.0`, `rpds-py 2026.5.1`.
- `agent-brain-cli/tests/test_config_resolve_mcp_transport.py` (created, 155 lines) — 7 tests covering precedence + the §3.5 case 2 error path + at-call-time env reads sanity.
- `agent-brain-cli/tests/test_transport_selector_mcp.py` (created, 269 lines) — 8 tests covering all three §3.5 misuse cases as exit-2 + skeleton routing on both branches + HTTP regression + open_client-gone smoke.
- 11 existing test files patched `@patch("agent_brain_cli.commands.X.open_client")` → `.open_backend` (test_cli.py, test_cli_query_modes.py, test_query_explain_render.py, test_cache_command.py, test_folders_cli.py, test_folders_watch_flags.py, test_inject_command.py, test_api_key_propagation.py, test_transport_selector.py, test_config_resolve_transport.py).

## Verbatim §3.5 Error Wording (test-pinned)

All three messages are pinned by string-match assertions in `tests/test_transport_selector_mcp.py`:

| Case | Trigger | Verbatim message |
|------|---------|------------------|
| 1 | `--transport mcp` + `agent_brain_mcp.client` not importable | `install agent-brain-mcp to use --transport mcp` |
| 2 | `--mcp-transport http` + no `--mcp-url` + no `AGENT_BRAIN_MCP_URL` env | `discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57` |
| 3 | `--mcp-transport stdio` + `shutil.which("agent-brain-mcp")` returns None | `agent-brain-mcp not found on PATH; install agent-brain-mcp into the same Python environment` |

All three exit with `click.UsageError` → exit code 2 (v10.2 HTTP-03 no-silent-fallback contract carry-forward).

## Final Dispatcher Branch Ordering

```python
def open_backend(ctx: click.Context, *, timeout: float = 30.0) -> BackendClient:
    obj = ctx.obj or {}
    transport_hint = obj.get("transport_hint")
    api_key = resolve_api_key()

    # 1. MCP branch (v3) — lazy import inside, raises §3.5 case 1 on ImportError
    if (transport_hint or "").lower() == "mcp":
        mcp_transport, mcp_target = resolve_mcp_transport(...)  # raises §3.5 case 2
        # ... debug-transport echo ...
        try:
            from agent_brain_mcp.client import McpHttpBackend, McpStdioBackend
        except ImportError:
            raise click.UsageError("install agent-brain-mcp to use --transport mcp")

        if mcp_transport == "stdio":
            # 1a. stdio sub-branch — PATH precheck (§3.5 case 3)
            if shutil.which("agent-brain-mcp") is None:
                raise click.UsageError("agent-brain-mcp not found on PATH; ...")
            return cast(BackendClient, McpStdioBackend(command="agent-brain-mcp"))
        # 1b. http sub-branch — mcp_target guaranteed non-None by resolve_mcp_transport
        assert mcp_target is not None
        return cast(BackendClient, McpHttpBackend(url=mcp_target, timeout=timeout))

    # 2. HTTP / UDS branch (existing v1/v2 path — unchanged behavior)
    transport, target = resolve_transport(...)
    # ... debug-transport echo ...
    if transport == "http":
        return DocServeClient(base_url=target, timeout=timeout, api_key=api_key)
    # UDS — lazy import agent_brain_uds; same as before
    from agent_brain_uds import make_client
    inner = make_client(socket_path=Path(target), timeout=timeout)
    return DocServeClient.from_httpx(inner, api_key=api_key)
```

Branch ordering matches the plan + CONTEXT spec exactly. No deviations.

## Decisions Made

- **`shutil` imported at module-top of transport.py** (CONTEXT marked as Claude's discretion). Rationale: (a) shutil is stdlib so there's no import cost concern; (b) the §3.5 case 3 test uses `monkeypatch.setattr("shutil.which", lambda cmd: None)` which targets the global shutil module reference — matches what the dispatcher imports. Module-top wins for testability.

- **`resolve_mcp_transport` return type stayed `tuple[Literal["stdio","http"], str | None]`** (also CONTEXT discretion). Matched the plan spec verbatim. The `str | None` target is `None` for stdio (subprocess, no URL) and the resolved URL for http. This mirrors `resolve_transport`'s `(transport, target)` shape per-axis. No richer 3-tuple needed.

- **`agent-brain-ag-mcp` added as dev path dep, `develop = false`**. Without it, the §3.5 case 3 and skeleton-routing tests have nothing to dispatch to — they all fall through to the §3.5 case 1 ImportError path, defeating their purpose. With `develop = true`, Poetry's .pth-injection would put `../agent-brain-mcp` on sys.path; since agent-brain-mcp's `tests/` is a namespace package without `__init__.py`, it would collide ambiguously with agent-brain-cli's `tests/__init__.py`. `develop = false` installs the package as a built sdist/wheel, only the `agent_brain_mcp/` source per its `packages` declaration — no shadow risk. Mirrors the precedent Phase 56-03 set on the MCP side.

- **`cast(BackendClient, ...)` on the MCP constructor returns** — mypy strict + `ignore_missing_imports = true` on agent_brain_mcp means the lazy-imported `McpStdioBackend` / `McpHttpBackend` are typed as `Any`. Without the cast, mypy emits `Returning Any from function declared to return "BackendClient"`. Runtime conformance is pinned by Phase 56-03's `tests/test_cli_backends_skeleton.py` `isinstance` assertions — the cast is purely a static-typing convenience.

- **jobs.py helper retyping (4 functions: `DocServeClient` → `BackendClient`)** — surfaced by mypy strict after the open_backend return-type widening. The other 7 command modules use the `with open_backend(ctx) as client:` context manager block inline (don't pass the client to typed helpers), so they needed no further type changes. Clean correctness fix.

- **Sync facade Pattern A vs Pattern B decision is DEFERRED to Plan 57-02** — Plan 57-01 only does routing; no method body wiring happens here, so the per-call asyncio overhead question doesn't surface yet. The plan's OUTPUT section explicitly noted this as STILL OPEN, decided in Plan 57-02.

- **NO drift from design doc §2.3 wire mapping** — Plan 57-01 doesn't touch the method↔tool mapping table (that's Plan 57-02/57-03's scope). The dispatcher routes; the skeletons still raise `NotImplementedError("Wired in Phase 57+")` for every method. Plans 57-02/57-03 will replace those bodies per the §2.3 table.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] mypy strict surfaced 6 errors after the rename**

- **Found during:** Task 3, after the 20-callsite swap completed.
- **Issue:** mypy strict reported (a) 2 × `[no-any-return]` on transport.py lines 111/115 because `agent_brain_mcp.client.McpStdioBackend` / `McpHttpBackend` are typed as `Any` under `ignore_missing_imports = true`; (b) 4 × `[arg-type]` in jobs.py because helper functions `_list_jobs`, `_show_job_detail`, `_cancel_job`, `_watch_jobs` were typed `DocServeClient` but now receive `BackendClient` from the widened `open_backend` return type.
- **Fix:** (a) Added `from typing import cast` to transport.py and wrapped both MCP constructor returns with `cast(BackendClient, ...)` — runtime conformance is pinned by Phase 56-03's `isinstance` test, so the cast is a static-typing convenience. (b) Retyped the 4 jobs.py helpers `DocServeClient` → `BackendClient`, dropped `DocServeClient` from the `..client` import, added `from ..client.protocol import BackendClient`. mypy strict re-runs clean.
- **Files modified:** `agent-brain-cli/agent_brain_cli/client/transport.py`, `agent-brain-cli/agent_brain_cli/commands/jobs.py`.
- **Verification:** `poetry run mypy agent_brain_cli` exits 0 with `Success: no issues found in 40 source files`.
- **Committed in:** `cd8e9cb` (folded into the Task 3 commit).

**2. [Rule 3 - Blocking] §3.5 case 3 + skeleton-routing tests had no MCP package to import**

- **Found during:** Task 3, first run of `tests/test_transport_selector_mcp.py`.
- **Issue:** `agent-brain-mcp` is NOT a runtime dep of `agent-brain-cli` (per the soft-dep design doc §3.1 contract). The CLI venv had no `agent_brain_mcp` module installed; tests 3, 4, 7 all fell through to the §3.5 case 1 ImportError path instead of exercising their target branches.
- **Fix:** Added `agent-brain-ag-mcp = { path = "../agent-brain-mcp", develop = false }` to `[tool.poetry.group.dev.dependencies]` in agent-brain-cli/pyproject.toml. Poetry resolved the dep, installed the path package + transitives. Tests now run against the real `McpStdioBackend` and `McpHttpBackend` skeletons. (The §3.5 case 1 test still works correctly because it monkeypatches `sys.modules["agent_brain_mcp.client"] = None`, simulating an uninstalled package even when one is present.) Added `pytest.importorskip("agent_brain_mcp.client")` at the top of tests 3, 4, 7 as a defensive fallback so they skip-not-fail on a CI runner that runs only agent-brain-cli unit tests in isolation.
- **Files modified:** `agent-brain-cli/pyproject.toml`, `agent-brain-cli/poetry.lock`, `agent-brain-cli/tests/test_transport_selector_mcp.py`.
- **Verification:** `poetry run pytest tests/test_transport_selector_mcp.py -v` exits 0 with 8/8 passing; `poetry run pytest` exits 0 with 451/451 passing across the whole CLI suite.
- **Committed in:** `cd8e9cb` (folded into the Task 3 commit).

**3. [Rule 1 - Bug] Initial MCP package-name guess was wrong**

- **Found during:** Task 3, first `poetry lock` after adding the dev dep.
- **Issue:** I guessed the package name was `agent-brain-mcp` (matching the directory name), but the actual `pyproject.toml` declares `name = "agent-brain-ag-mcp"`. Poetry's lock fast-fails: `The dependency name for agent-brain-mcp does not match the actual package's name: agent-brain-ag-mcp`.
- **Fix:** Renamed the dep line to `agent-brain-ag-mcp` (kept `path = "../agent-brain-mcp"` since the directory name is still `agent-brain-mcp`). Lock + install succeed.
- **Files modified:** `agent-brain-cli/pyproject.toml`.
- **Verification:** `poetry lock` succeeds; `poetry install --with dev` installs `agent-brain-ag-mcp 10.2.1`; `poetry run python -c "from agent_brain_mcp.client import McpStdioBackend"` prints `OK` (the Python package name `agent_brain_mcp` is unchanged — only the distribution name was off).
- **Committed in:** `cd8e9cb`.

---

**Total deviations:** 3 auto-fixed (1 Rule 1 bug, 2 Rule 3 blocking issues).
**Impact on plan:** All three were correctness/test-completeness fixes — no scope creep. The dev path dep addition is a permanent infrastructure addition that future Phase 57+ plans will benefit from (the test suite can exercise MCP routing without manual venv setup).

## Acceptance Criteria Notes

- The plan's acceptance criterion for case 3 verbatim wording (`grep -c "agent-brain-mcp not found on PATH; install agent-brain-mcp into the same Python environment" returns 1`) reads the literal string as a single-line substring. In transport.py the message is split across two physical lines via implicit string concatenation (Black's 88-char limit). The RUNTIME-joined string is byte-identical to the spec — verified by running `python -c "raise click.UsageError(...)"` and checking `e.message`. Same pattern applies to the case 2 wording in config.py. Tests assert on the runtime-joined value, which is correct.
- The plan's acceptance criterion `grep -c "import shutil" returns 1` passes (the dispatcher imports the bare `shutil` module).
- The plan's acceptance criterion `grep -c "shutil.which(\"agent-brain-mcp\")" returns 1` returned 2 — one is the actual function call in the if-statement, the other is in the docstring (`(precheck: ``shutil.which("agent-brain-mcp")`` must be non-None ...)`). Functionally correct; the precheck is invoked exactly once per dispatcher call.

## Issues Encountered

None blocking. The deviations above were caught and resolved within the same task that introduced them.

## User Setup Required

None — Plan 57-01 is a CLI surface + dispatcher refactor. The MCP backends still raise `NotImplementedError("Wired in Phase 57+")` for every method body, so there's nothing for an operator to verify end-to-end yet. Plans 57-02 (query) and 57-03 (remaining methods) will surface user-verifiable functional behavior.

## Next Phase Readiness

- **Plan 57-02 ready to execute:** the dispatcher routes `--transport mcp` correctly to both `McpStdioBackend` and `McpHttpBackend` skeletons. Plan 57-02's task is to replace `McpStdioBackend.query` and `McpHttpBackend.query` `NotImplementedError` bodies with real MCP SDK `search_documents` tool calls + commit the Pattern A vs Pattern B sync-facade decision.
- **Plan 57-03 follows:** wires the remaining 11 BackendClient methods (`health`, `status`, `index`, `list_folders`, `delete_folder`, `list_jobs`, `get_job`, `cancel_job`, `cache_status`, `clear_cache`) per the design doc §2.3 mapping table; `reset()` stays `NotImplementedError` with the §5 risk-register wording.
- **CLI-MCP-03 partially advanced:** selector + dispatcher + 3 §3.5 misuse cases land; the requirement closes in Plan 57-03 once all method bodies are wired. (REQUIREMENTS.md remains "Pending" for CLI-MCP-03 — flipping to "Complete" happens at 57-03 close.)
- **No blockers.**

---
*Phase: 57-cli-transport-selector-byte-identical-equivalence*
*Completed: 2026-06-06*

## Self-Check: PASSED

- FOUND: `agent-brain-cli/agent_brain_cli/config.py` (resolve_mcp_transport added; mypy strict + Black/Ruff clean)
- FOUND: `agent-brain-cli/agent_brain_cli/cli.py` (4-choice --transport + --mcp-transport + --mcp-url; ctx.obj writes 2 new keys)
- FOUND: `agent-brain-cli/agent_brain_cli/client/transport.py` (open_backend dispatcher with 4 branches + shutil.which precheck; open_client gone)
- FOUND: 8 command modules (cache/folders/index/inject/jobs/query/reset/status) all using `open_backend(ctx)`
- FOUND: `agent-brain-cli/tests/test_config_resolve_mcp_transport.py` (7 tests pass)
- FOUND: `agent-brain-cli/tests/test_transport_selector_mcp.py` (8 tests pass — all 3 §3.5 cases + skeleton routing + HTTP regression + open_client gone)
- FOUND: `agent-brain-cli/pyproject.toml` (agent-brain-ag-mcp dev path dep, develop=false)
- FOUND: `agent-brain-cli/poetry.lock` (regenerated, mcp 1.27.2 + transitives)
- FOUND: `.planning/phases/57-cli-transport-selector-byte-identical-equivalence/57-01-SUMMARY.md` (this file)
- FOUND: commit `5448420` (feat(57-01): add resolve_mcp_transport() helper for MCP-axis precedence)
- FOUND: commit `075cea9` (feat(57-01): wire --mcp-transport + --mcp-url flags + extend --transport choice)
- FOUND: commit `cd8e9cb` (feat(57-01): rename open_client → open_backend with 4-branch MCP dispatcher)
- VERIFIED: `task before-push` exit 0 — 451 CLI tests + 474 MCP tests + server suite + UDS suite + lock-drift check all green
- VERIFIED: `grep -rh "open_client" agent_brain_cli/commands/` returns 0 lines (atomic rename complete)
- VERIFIED: runtime-joined error messages match verbatim §3.5 wording for all 3 misuse cases (case 1: "install agent-brain-mcp to use --transport mcp"; case 2: "discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57"; case 3: "agent-brain-mcp not found on PATH; install agent-brain-mcp into the same Python environment")
- VERIFIED: `agent-brain --help` shows all four `--transport` choices + `--mcp-transport` + `--mcp-url`
