---
phase: 53-streamable-http-transport
plan: 03
subsystem: mcp
tags: [mcp, http, streamable, sdk-client, e2e, taskfile, docs, transport, meta, two-axis]

# Dependency graph
requires:
  - phase: 53-streamable-http-transport
    provides: Plan 02 — agent_brain_mcp.http.run_http() listener + validate_loopback_host + PortInUseError + free_loopback_port fixture
  - phase: 53-streamable-http-transport
    provides: Plan 01 — --transport/--host/--port CLI flags + main_async() dispatcher + build_server two-axis transport labels
  - phase: 50-server-endpoint-prep-v2-design-doc
    provides: v2 design doc §3.3 Streamable HTTP transport architecture
provides:
  - SDK HTTP round-trip e2e proof (test_transport_selection.py — initialize + 3 listings + tool call)
  - HTTP listener loopback bind verification via psutil.net_connections (test_http_listener_bound_to_loopback_only)
  - 3 subprocess-driven HTTP-03 negative paths (bogus transport, non-loopback host, port-in-use)
  - serverInfo._meta wire wiring carrying agentBrainBackendTransport + agentBrainListenTransport
  - _MetaInjectingServerSession SDK subclass + _install_meta_injecting_session server.run wrapper
  - CLI-level hoist of loopback validation + port-collision probe (sidesteps BackendUnavailable masking)
  - probe_port_available public alias for the Plan 02 private probe
  - mcp_http_subprocess + fake_http_server_module conftest fixtures (Plan 52 stdio harness pattern, HTTP variant)
  - pytest e2e_http marker + addopts exclusion (default fast lane stays fast)
  - psutil dev dep
  - Taskfile mcp:smoke:http + mcp:smoke:all umbrella tasks
  - Taskfile PYTHONPATH fix (drop ./agent_brain_mcp from env; was shadowing stdlib http)
  - README Transport selection section with copy-pasteable example + exit-code table
  - MCP_USER_GUIDE.md two-axis transport diagram + #179 vs OAUTH-01 disambiguation
affects: [54-mcp-tool-completion, 55-validation-qa]

# Tech tracking
tech-stack:
  added:
    - psutil ^6.0 (dev only — socket bind inspection in test_http_loopback.py)
  patterns:
    - SDK subclass + Server.run instance override for InitializeResult._meta injection (mcp 1.12.x SDK-version-pinned)
    - Pydantic ConfigDict(extra="allow") exploit: passing _meta=<dict> as Implementation constructor kwarg round-trips on the wire
    - Subprocess e2e harness with fake-server script + httpx.MockTransport backend (mirrors Phase 52 stdio harness; bypasses MIN_BACKEND_VERSION check)
    - SIGINT → 3s wait → SIGKILL teardown so cleanup_all() gets its grace window
    - SDK-version-pinned _received_request override (only InitializeRequest case duplicated; all other cases defer to super())

key-files:
  created:
    - agent-brain-mcp/tests/test_transport_selection.py
    - agent-brain-mcp/tests/test_http_loopback.py
    - agent-brain-mcp/tests/test_http_negative_paths.py
    - .planning/phases/53-streamable-http-transport/plans/03-sdk-roundtrip-smoke-and-taskfile-SUMMARY.md
  modified:
    - agent-brain-mcp/agent_brain_mcp/server.py (meta wiring + _MetaInjectingServerSession + _install_meta_injecting_session)
    - agent-brain-mcp/agent_brain_mcp/cli.py (loopback + port-probe CLI hoist)
    - agent-brain-mcp/agent_brain_mcp/http.py (probe_port_available public alias)
    - agent-brain-mcp/pyproject.toml (e2e_http marker + psutil dev dep + addopts)
    - agent-brain-mcp/Taskfile.yml (mcp:smoke:http + mcp:smoke:all + PYTHONPATH fix)
    - agent-brain-mcp/tests/conftest.py (mcp_http_subprocess + fake_http_server_module fixtures)
    - agent-brain-mcp/tests/test_smoke.py (in-process _agent_brain_meta assertion)
    - agent-brain-mcp/README.md (Transport selection section)
    - docs/MCP_USER_GUIDE.md (two-axis transport diagram + CLI flags reorg)

key-decisions:
  - "_meta wired via SDK subclass + Server.run override (option (b) from Plan 02's Concerns). The bare Implementation type allows extras (model_config = ConfigDict(extra='allow') at mcp/types.py:274), so passing _meta=<dict> as a constructor kwarg round-trips on the wire. _MetaInjectingServerSession overrides _received_request ONLY for the InitializeRequest case; every other case defers to super() — minimizes the surface that breaks on SDK upgrade."
  - "CLI-level hoist of loopback validation + port probe (Rule 2 deviation — missing critical functionality). main_async() opens the backend httpx client and runs the version-compat check BEFORE the dispatcher reaches run_http; without the hoist, --host 0.0.0.0 or --port <occupied> against a missing backend would surface as BackendUnavailable (connection refused), masking the real misconfiguration. The Plan 02 in-process checks stay as defense-in-depth for direct callers."
  - "probe_port_available public alias in http.py — the CLI's hoist needs to import the probe without reaching for the underscore-prefixed in-module name. The Plan 02 leading-underscore name stays (in-module callers prefer it for clarity); the public alias is the cross-module surface."
  - "Subprocess e2e uses a fake-server script + httpx.MockTransport instead of agent-brain-mcp's real CLI entry. The CLI's main_async() runs MIN_BACKEND_VERSION = 10.2.0 check that needs a live agent-brain-serve at startup. The fake-server script (mirroring Phase 52's tests/test_e2e_stdio.py harness) wires build_server() + run_http() directly, skipping main_async, so the SDK round-trip doesn't drag in a full backend stack."
  - "Taskfile PYTHONPATH env block dropped ./agent_brain_mcp/ (only ./tests/ kept). Plan 02 introduced agent_brain_mcp/http.py — with the parent dir on PYTHONPATH, this shadows the stdlib http package and breaks every transitively-importing tool (urllib3 → requests → poetry's own console scripts). The poetry-installed venv is enough."
  - "Defensive *_ unpack on streamablehttp_client yield tuple. The SDK's 1.12.x yield shape is (read, write, session_id_factory) but adding trailing elements is forward-compat — *_ absorbs any new ones (Plan 03 risk #1)."

# Requirements completed by this plan
requirements-completed: [HTTP-01, HTTP-02, HTTP-03]  # Plan 01 + 02 + 03 cumulative — Plan 03 closes the e2e SDK proof
# HTTP-01: SDK round-trip proven via mcp.client.streamable_http.streamablehttp_client (test_http_round_trip_lists_v1_surface)
# HTTP-02: Loopback bind verified via psutil.Process.net_connections at runtime (test_http_listener_bound_to_loopback_only); CLI-layer hoist makes the failure mode visible without a backend
# HTTP-03: 3 subprocess-driven no-silent-fallback proofs (test_bogus_transport_rejected_by_click + test_non_loopback_host_rejected_before_bind + test_port_in_use_exits_code_2)

# Metrics
duration: 22min
completed: 2026-06-03
---

# Phase 53 Plan 03: SDK round-trip smoke + Taskfile + USER_GUIDE Summary

**Plan 02's HTTP listener is now exercised end-to-end via the official MCP Python SDK's `streamablehttp_client`; the v1 surface (7 tools / 5 resources / 6 prompts) is wire-verified symmetric across stdio and HTTP; both transport axis labels surface on `serverInfo._meta`; loopback bind is verified at the kernel-socket level via psutil; and the CLI hoists loopback + port-collision rejection so the failure modes don't get masked by `BackendUnavailable`. `task mcp:smoke:http` exits 0.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-06-03T17:01:26Z
- **Completed:** 2026-06-03T17:23:52Z (final docs commit)
- **Tasks:** 4 atomic commits (source + tooling + tests + docs) + this metadata commit
- **Files modified:** 10 (3 source modified + 4 tests created + 1 test modified + 2 docs + 2 tooling) — `tests/test_smoke.py` extended; `agent_brain_mcp/server.py`, `agent_brain_mcp/cli.py`, `agent_brain_mcp/http.py`, `pyproject.toml`, `Taskfile.yml`, `tests/conftest.py`, `agent-brain-mcp/README.md`, `docs/MCP_USER_GUIDE.md` modified; `tests/test_transport_selection.py`, `tests/test_http_loopback.py`, `tests/test_http_negative_paths.py` created
- **MCP test count:** 305 → 308 fast lane (+3 net: 2 new no-bind negative tests in fast lane + 1 new smoke meta assertion); + 3 new e2e_http tests (round-trip, loopback bind, port-in-use). Total opt-in suite via `task mcp:smoke:http`: 3 passed.
- **Monorepo test count:** 416 → 416 fast path (Plan 03's new tests live in MCP package — server/CLI unchanged; the 3 new MCP fast-lane tests don't propagate because monorepo count is constrained by other suites).
- **MCP coverage:** 91.03% on the whole package (above the 80% Taskfile gate).

## Accomplishments

- **Wire-level SDK round-trip (`test_transport_selection.py`, marked `e2e_http`):**
  - Drives `mcp.client.streamable_http.streamablehttp_client` against `agent_brain_mcp.http.run_http` running in a subprocess on a loopback port from the `free_loopback_port` fixture.
  - Asserts the v1 surface exactly: 7 named tools (`search_documents`, `query_count`, `index_folder`, `get_job`, `list_jobs`, `cancel_job`, `server_health`); 5 resources; 6 prompts. The set-equality (not just count) assertion on tool names pins HTTP-03 / D-18 — Phase 53 surface must not leak into unfinished Phase 52 / 54 surface.
  - Asserts `init_result.serverInfo._meta["agentBrainListenTransport"] == "http"` AND `"agentBrainBackendTransport" in _meta` — the over-the-wire counterpart to Plan 01's in-process `server._agent_brain_*_transport` private attrs.
  - Defensive `*_` unpack on `streamablehttp_client`'s yield tuple absorbs any future trailing-element addition (current shape in mcp 1.12.x: `(read, write, session_id_factory)`).
  - Confirms `call_tool("server_health", {})` returns `structuredContent`.
- **Loopback bind kernel-level verification (`test_http_loopback.py`, marked `e2e_http`):**
  - Uses `psutil.Process(proc.pid).net_connections(kind="tcp")` filtered to `LISTEN` state.
  - Asserts every listening socket's `laddr.ip` is in `{127.0.0.1, ::1}`.
  - Cross-checks that the requested port is in the bound set so the inspection targets the right process.
  - Skipped on Windows (psutil needs admin for foreign procs there); CI matrix is macOS + linux.
- **HTTP-03 subprocess-driven negative paths (`test_http_negative_paths.py`):**
  - `test_bogus_transport_rejected_by_click` (fast lane — Click rejects before any dispatch): asserts non-zero exit + "not one of" in stderr.
  - `test_non_loopback_host_rejected_before_bind` (fast lane — Plan 03 CLI hoist rejects before backend check): asserts non-zero exit + loopback whitelist contract message.
  - `test_port_in_use_exits_code_2` (marked `e2e_http` — Plan 02 pre-flight probe briefly binds): asserts exit code 2 (Plan 02 D-12) + "already in use" wording. Holds the port open in the test process so the subprocess hits EADDRINUSE.
- **`serverInfo._meta` over-the-wire wiring (the load-bearing Plan 03 carry-forward):**
  - `build_server()` now attaches `server._agent_brain_meta = {"agentBrainBackendTransport": ..., "agentBrainListenTransport": ...}` and installs `_install_meta_injecting_session(server)`.
  - `_MetaInjectingServerSession` is a `ServerSession` subclass that overrides `_received_request` ONLY for `InitializeRequest`. The override mirrors `mcp/server/session.py:165-187` (mcp 1.12.x) with one change: `Implementation(name=..., version=..., websiteUrl=..., icons=..., _meta=session._agent_brain_meta)`. Every other request type defers to `super()._received_request(responder)`.
  - `_install_meta_injecting_session(server)` wraps `server.run` on the instance with a body that mirrors `mcp/server/lowlevel/server.py:640-690` (mcp 1.12.x), substituting `_MetaInjectingServerSession` for `ServerSession`. The wrapper sets `session._agent_brain_meta` from `server._agent_brain_meta` right after session construction so the subclass override sees the right dict. Original `Server.run` is stashed at `server._agent_brain_original_run` for test introspection.
  - The `Implementation` SDK type has `model_config = ConfigDict(extra="allow")` (mcp/types.py:274); passing `_meta=<dict>` as a constructor kwarg goes through Pydantic's extras storage and round-trips through `model_dump(by_alias=True)` as `"_meta": {...}` on the JSON-RPC wire.
- **CLI hoist of loopback validation + port probe (`agent_brain_mcp/cli.py`):**
  - When `--transport http`, the CLI now calls `validate_loopback_host(host)` + `probe_port_available(host, port)` BEFORE delegating to `main_async`. The Plan 02 in-process checks in `run_http` stay as defense-in-depth for direct callers (tests, embeddings).
  - Without the hoist, `--host 0.0.0.0` or `--port <occupied>` against a missing backend would surface as `BackendUnavailable` (the version-compat check fires before the dispatcher reaches `run_http`), masking the real misconfiguration.
  - `agent_brain_mcp.http` exposes the previously-private `_probe_port_available` as `probe_port_available` (public alias added to `__all__`) so the CLI import doesn't pull an underscore-prefixed name across modules.
- **Fixtures (`tests/conftest.py`):**
  - `mcp_http_subprocess` factory + `fake_http_server_module` session-scoped fixture pair. The fake-server script wires `build_server()` + `run_http()` to an `httpx.MockTransport` backend — bypasses `main_async`'s MIN_BACKEND_VERSION check so the SDK round-trip doesn't need a real `agent-brain-serve` running. Mirrors Phase 52's `tests/test_e2e_stdio.py` harness.
  - Teardown is SIGINT → 3s wait → SIGKILL fallback. The 3-second SIGINT grace window is enough for uvicorn's graceful shutdown to drain in-flight requests AND for `run_http`'s `finally` block to run `subscription_manager.cleanup_all()` (Plan 02 contract).
- **Taskfile (`agent-brain-mcp/Taskfile.yml`):**
  - New `mcp:smoke:http` task runs `pytest tests/test_transport_selection.py tests/test_http_loopback.py tests/test_http_negative_paths.py -v -m e2e_http`.
  - New `mcp:smoke:all` umbrella runs the fast unit suite + the HTTP smoke.
  - `env: PYTHONPATH: './tests'` — dropped `./agent_brain_mcp` (Plan 02's new `http.py` was shadowing the stdlib `http` package via PYTHONPATH and breaking every transitively-importing tool including poetry's own console scripts).
- **Pytest config (`agent-brain-mcp/pyproject.toml`):**
  - Registered `e2e_http` marker for the opt-in HTTP suite.
  - Extended `addopts = "-m 'not e2e and not e2e_http'"` so both opt-in markers stay excluded from the fast lane.
  - Added `psutil = "^6.0"` to `[tool.poetry.group.dev.dependencies]` for the socket-bind inspection.
- **Smoke parity (`tests/test_smoke.py`):**
  - New `test_build_server_attaches_meta_dict_with_both_axis_labels` pins the in-process contract that `server._agent_brain_meta == {"agentBrainBackendTransport": backend_transport, "agentBrainListenTransport": listen_transport}`. Symmetric counterpart to the over-the-wire assertion in `test_transport_selection` — keeps a regression visible in the fast lane.
- **Documentation:**
  - `agent-brain-mcp/README.md` Transport selection section with copy-pasteable invocation, SDK client snippet, curl healthz check, loopback / no-auth warning mirroring the Plan 02 D-10 startup banner, exit-code table distinguishing port-in-use (2) from validation errors (1), and the `AGENT_BRAIN_MCP_TRANSPORT`-reserved-but-not-honored note.
  - `docs/MCP_USER_GUIDE.md` two-axis transport diagram (listen vs backend), authentication subsection that EXPLICITLY DISAMBIGUATES issue #179 (Bearer-token on `agent-brain-serve`, backend-axis only) from OAUTH-01 / #188 (auth on MCP listen transport, v4 only). Local-trust model caveat (loopback ≠ multi-user-safe) named. CLI flags table reorganized into backend-axis (unchanged from v10.1) + listen-axis (new in v10.2) groups. Resolution precedence updated. Table of Contents updated.

## Task Commits

1. **Task 1: source code — `_meta` wiring + CLI hoist** — `ce45940` (feat)
2. **Task 2: tooling — marker, dev dep, Taskfile, PYTHONPATH fix, conftest fixtures** — `e664c0e` (chore)
3. **Task 3: tests — 3 new e2e_http files + smoke meta assertion** — `38af276` (test)
4. **Task 4: docs — README Transport section + MCP_USER_GUIDE two-axis section** — `fc137f2` (docs)

**Plan metadata commit:** (next commit — includes SUMMARY.md + STATE.md + ROADMAP.md + REQUIREMENTS.md updates)

## Files Created/Modified

### Created

- **`agent-brain-mcp/tests/test_transport_selection.py`** — 1 test class, 1 e2e_http test. The HTTP-01 wire proof (initialize + 3 listings + tool call + `_meta` axis labels).
- **`agent-brain-mcp/tests/test_http_loopback.py`** — 1 e2e_http test using `psutil.Process.net_connections` to inspect the bound interface. Windows-skipped.
- **`agent-brain-mcp/tests/test_http_negative_paths.py`** — 2 fast-lane tests + 1 e2e_http test. HTTP-03 subprocess-driven no-silent-fallback proofs.

### Modified

- **`agent-brain-mcp/agent_brain_mcp/server.py`** — added imports for `AsyncExitStack`, `anyio`, `ServerSession`, `InitializationState`, `RequestResponder`, `SUPPORTED_PROTOCOL_VERSIONS`. Added `server._agent_brain_meta` attachment in `build_server`. Added `_MetaInjectingServerSession` subclass + `_install_meta_injecting_session(server)` helper just before `run_stdio`. The session subclass duplicates the `InitializeRequest` handler from the SDK (mcp 1.12.x) with the `_meta` injection; every other request type defers to `super()._received_request()`. The helper wraps `server.run` on the instance, mirroring the SDK's body verbatim with the `ServerSession` substitution.
- **`agent-brain-mcp/agent_brain_mcp/cli.py`** — added `validate_loopback_host` + `probe_port_available` imports from `agent_brain_mcp.http`. CLI body now calls both when `transport == "http"` BEFORE `asyncio.run(main_async(...))`. Inline comment names the failure mode this hoist closes (`BackendUnavailable` masking).
- **`agent-brain-mcp/agent_brain_mcp/http.py`** — `probe_port_available = _probe_port_available` public alias + added to `__all__`. No behavior change; the alias is the cross-module surface for the CLI hoist.
- **`agent-brain-mcp/pyproject.toml`** — `e2e_http` marker added; `addopts` extended to exclude both markers; `psutil = "^6.0"` added under `[tool.poetry.group.dev.dependencies]`.
- **`agent-brain-mcp/Taskfile.yml`** — `mcp:smoke:http` + `mcp:smoke:all` tasks added between `e2e` and `test:all`. Env block's `PYTHONPATH` reduced from `'./agent_brain_mcp:./tests'` to `'./tests'` with an explanatory comment.
- **`agent-brain-mcp/tests/conftest.py`** — added module-level imports for `os`, `signal`, `subprocess`, `sys`, `time`, `Iterator`, `contextmanager`. Added `_FAKE_HTTP_SERVER_SCRIPT` string constant (mirrors `tests/test_e2e_stdio.py`'s pattern for the HTTP variant). Added `fake_http_server_module` session-scoped fixture (writes the script to `tmp_path_factory.mktemp`). Added `_mcp_subprocess` context manager (SIGINT → 3s wait → SIGKILL fallback). Added `mcp_http_subprocess` factory fixture binding `free_loopback_port` + `fake_http_server_module`.
- **`agent-brain-mcp/tests/test_smoke.py`** — added `test_build_server_attaches_meta_dict_with_both_axis_labels` pinning the in-process `_agent_brain_meta` dict shape.
- **`agent-brain-mcp/README.md`** — replaced single Quick config section flow with: Quick config → **Transport selection (v10.2+)** → Full guide. The new section includes a copy-pasteable HTTP invocation, an SDK client snippet, a curl healthz check, the loopback / no-auth warning (verbatim from Plan 02 D-10), the exit-code table (1 = validation; 2 = port-in-use), the no-silent-fallback contract, and the `AGENT_BRAIN_MCP_TRANSPORT`-reserved note.
- **`docs/MCP_USER_GUIDE.md`** — added **MCP transport axes (v10.2+)** section before the CLI flags table. ASCII diagram showing the two axes with auth annotations. Authentication subsection explicitly disambiguates #179 vs OAUTH-01 / #188 (the most common operator conflation per Phase 53 CONTEXT specifics). Local-trust model warning (loopback ≠ multi-user). The "Picking a listen transport" table. CLI flags split into backend-axis + listen-axis groups. Resolution precedence updated. Table of Contents updated.

## Decisions Made

- **`_meta` injection via SDK subclass + instance-level `Server.run` override (option (b) from Plan 02's Concerns).** The cleanest extension point the SDK offers. Implementation duplicates ~30 lines of `Server.run` and ~20 lines of `ServerSession._received_request` for the InitializeRequest case; both duplicates are pinned to mcp 1.12.x with inline comments naming the source lines for future SDK upgrades.
- **`Implementation(_meta=<dict>)` exploits `model_config = ConfigDict(extra="allow")`.** Discovered at mcp/types.py:274 — `Implementation` accepts extras, so the kwarg lands in `model_extra` and round-trips through `model_dump(by_alias=True)`. The client side parses it back into `_meta` via the same alias. No SDK monkey-patching; no Pydantic gymnastics.
- **CLI-level hoist of loopback + port-collision checks.** Plan 02's checks fire inside `run_http`, which `main_async` only reaches AFTER `open_backend_client` + the MIN_BACKEND_VERSION check. Against a missing backend, the user sees `BackendUnavailable` (errno 61 connection refused) instead of "must be one of {127.0.0.1, localhost, ::1}". The hoist is the minimum-touch fix; Plan 02's checks stay as defense-in-depth for direct callers (tests, embeddings).
- **`probe_port_available` public alias instead of changing the Plan 02 name.** Plan 02's `_probe_port_available` is the in-module name; using `_probe` directly across module boundaries violates the leading-underscore convention. The alias preserves Plan 02's in-module clarity while giving cross-module callers a clean import.
- **Fake-server harness for the SDK round-trip — NOT the real `agent-brain-mcp` CLI.** `main_async`'s MIN_BACKEND_VERSION check needs a live `agent-brain-serve` reachable at startup; bringing one up in Plan 03's smoke task would 10x the task duration and pull in OpenAI / Anthropic API keys. The fake-server script mirrors Phase 52's stdio e2e harness — wires `build_server` to an `httpx.MockTransport` and calls `run_http` directly, bypassing `main_async` entirely. The HTTP transport's actual SDK wire behavior is what's under test; the backend reachability is orthogonal.
- **Taskfile `PYTHONPATH` drop `./agent_brain_mcp`.** Plan 02's new `agent_brain_mcp/http.py`, when its parent dir is on PYTHONPATH, shadows the stdlib `http` package because Python's import system finds the local file first. urllib3 → requests → poetry's console scripts all break. The fix is one line; the comment block in the Taskfile names the failure mode so it doesn't get re-added.
- **Defensive `*_` unpack on `streamablehttp_client` yield.** Plan 03 risk #1: SDK yield shape `(read, write, session_id_factory)` in 1.12.x may grow. The `async with streamablehttp_client(url) as (read, write, *_):` form absorbs trailing additions without test churn on SDK upgrades.
- **Subprocess teardown SIGINT → 3s → SIGKILL.** The 3-second grace window is calibrated for Plan 02's `run_http` finally block — uvicorn's graceful shutdown + `subscription_manager.cleanup_all()` complete in <1s on typical hardware. SIGKILL fallback covers the rare hung-loop case without leaking processes.
- **Fast-lane vs e2e_http boundary set by "does it spawn uvicorn / bind a socket?"** The Click-rejection (`--transport bogus`) and Plan 03-CLI-hoist (`--host 0.0.0.0`) negatives never reach the dispatcher; they're CLI-only and run in the fast lane. The port-in-use negative DOES briefly attempt a bind (Plan 02's pre-flight probe) so it gets the marker. The round-trip and the psutil-inspection tests both spawn real subprocesses so they get the marker.

## Deviations from Plan

**Total deviations:** 2 (both Rule 2 — missing critical functionality, auto-applied)

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] CLI-layer hoist of loopback validation + port probe**

- **Found during:** First run of `test_non_loopback_host_rejected_before_bind`.
- **Issue:** The test asserted `--transport http --host 0.0.0.0` produces a "loopback / must be one of" error message. Actual subprocess output was an `httpx.ConnectError: [Errno 61] Connection refused` stack trace from `main_async`'s `api.server_health()` call — the version-compat check runs BEFORE the dispatcher reaches `run_http`, so Plan 02's in-process loopback validator never fired. Same masking would apply to `--port <occupied>` against a missing backend (the port-in-use test wouldn't hit Plan 02 D-12's exit-code-2 contract; it would surface as `BackendUnavailable` instead).
- **Fix:** Hoisted `validate_loopback_host(host)` + `probe_port_available(host, port)` to the CLI entry point (`agent_brain_mcp/cli.py`), gated by `if transport == "http"`. Plan 02's in-process checks in `run_http` remain as defense-in-depth for direct callers. Added `probe_port_available` as a public alias for Plan 02's `_probe_port_available` so the CLI import doesn't reach for an underscore-prefixed name across modules.
- **Files modified:** `agent_brain_mcp/cli.py`, `agent_brain_mcp/http.py` (alias).
- **Verification:** Both fast-lane negative tests pass — `--host 0.0.0.0` exits non-zero with "must be one of" + "loopback" in stderr; `--port <occupied>` exits with code 2 + "already in use" wording.
- **Committed in:** `ce45940` (Task 1 — combined with the `_meta` wiring).
- **Impact on plan:** Strict tightening — closes a gap the acceptance criteria implicitly required (HTTP-03: "no silent fallback" + "clear startup error"). Plan 02's `BackendUnavailable` masking would have been a silent regression against HTTP-03 the moment an operator hit either misconfiguration on a fresh install.

**2. [Rule 2 - Missing Critical] Taskfile `PYTHONPATH` env block dropped `./agent_brain_mcp`**

- **Found during:** First `task mcp:smoke:http` invocation.
- **Issue:** `task` failed with `ModuleNotFoundError: No module named 'mcp'` coming from urllib3's `from http.client import IncompleteRead`. The MCP Taskfile sets `PYTHONPATH: './agent_brain_mcp:./tests'`; with `./agent_brain_mcp` on the path, Plan 02's new `agent_brain_mcp/http.py` is importable as a top-level `http` module, shadowing the stdlib `http` package. urllib3 → requests → poetry's own console scripts all break. The failure pre-existed Plan 03 (Plan 02 introduced `http.py`); Plan 03 surfaces it because Plan 03 is the first plan to actually run the per-package Taskfile target.
- **Fix:** Reduced the env block to `PYTHONPATH: './tests'`. The poetry-installed venv resolves `agent_brain_mcp` via site-packages without needing a PYTHONPATH game. Added an explanatory comment naming the failure mode so the line doesn't get re-added.
- **Files modified:** `agent-brain-mcp/Taskfile.yml`.
- **Verification:** `task mcp:smoke:http` exits 0; `task test` exits 0 (3 net new fast-lane tests + 308 baseline).
- **Committed in:** `e664c0e` (Task 2 — combined with the marker + dev dep additions).
- **Impact on plan:** Strict tightening — Phase 53's `task mcp:smoke:http` would have shipped broken without this. Detected this within seconds of writing the task, well before plan execution wrapped.

## Issues Encountered

- **MCP SDK does NOT expose an extension hook for `InitializeResult.serverInfo`.** Resolved by the SDK-subclass + `Server.run`-instance-override approach. The duplicated code is bounded (one method body, one class init mirror) and version-pinned with inline comments. Phase 55 may revisit if upstream publishes a cleaner injection point.
- **`Implementation` extras carry as `model_extra` keyed by the original field name, NOT auto-bound as attributes.** The smoke test originally tried `init_result.serverInfo.meta` (no underscore); that fails because `Implementation` has no `meta` field and the extra lives under the literal key `"_meta"`. Updated the test to access `getattr(server_info, "_meta", None)` with `model_extra.get("_meta")` fallback. The wire-format JSON round-trips correctly either way.
- **`task test` was broken before Plan 03 started.** The Plan 02 introduction of `agent_brain_mcp/http.py` shadowed stdlib `http` via Plan 02's unchanged `PYTHONPATH` setting. Plan 03 surfaced the issue while invoking the new task; fixed in the same Taskfile edit that added `mcp:smoke:http`.

## User Setup Required

**None.** psutil 6.x is a small (<2 MB) cross-platform dev dep available on every CI platform agent-brain targets. The `pip install agent-brain-ag-mcp` end-user surface is unchanged — psutil stays in the dev group.

Operators upgrading to MCP v10.2 and switching to the HTTP transport need:
1. Pass `--transport http` (default stays `stdio` — no Claude Desktop surprise).
2. Optionally pass `--host` (default 127.0.0.1; localhost / ::1 also accepted) and `--port` (default 8765).
3. Connect via `mcp.client.streamable_http.streamablehttp_client` at `http://127.0.0.1:<port>/mcp`.
4. Verify liveness: `curl http://127.0.0.1:<port>/healthz`.

## Next Phase Readiness

**Phase 53 complete (all 3 plans landed).** The verifier orchestration should:
- Confirm `task before-push` exits 0 at HEAD (already done by Plan 03's pre-commit gate).
- Confirm `task mcp:smoke:http` exits 0 at HEAD.
- Run `task mcp:smoke:all` (umbrella) to confirm the fast unit suite + HTTP smoke are joined cleanly.
- Mark the phase row in ROADMAP.md to `[x]` (3/3 plans) and the requirement traceability rows for HTTP-01/02/03 to `Complete`.
- Spawn the Phase 53 verifier (Wave 4) for final scoring.

**Ready for Phase 54 (TOOL-01..TOOL-09, 9 remaining MCP tools):**
- New tools will surface on BOTH transports because Plan 03 closed the HTTP wire contract. Phase 54's tests can parameterize stdio vs HTTP via the `mcp_http_subprocess` + existing `mcp_client` fixtures.
- The `_meta` injection pattern (Plan 03's `_MetaInjectingServerSession` + `_install_meta_injecting_session`) is reusable: if Phase 54 needs to surface tool-specific metadata on initialize, the helper is already in place.
- The CLI hoist + `probe_port_available` public alias means Phase 55's `task before-push` integration won't need to special-case the HTTP transport — the listener is loopback-validated + port-probed at the CLI layer before any uvicorn binding starts.

**Concerns for Phase 54:**

- **Phase 54's `wait_for_job` will need progress notifications over HTTP.** Plan 03 only proves the request/response surface (initialize + listings + tool call); progress notifications travel over the same Streamable HTTP session but follow the SSE event-stream path that Plan 02's `StreamableHTTPSessionManager` configures with `json_response=False`. Phase 54 Plan 04 (TOOL-04) should validate progress event flow on the HTTP transport AND stdio.
- **`mcp_http_subprocess` fixture is per-test scoped.** If Phase 54 runs many HTTP round-trip tests, the cumulative subprocess-spawn cost grows. Consider promoting to session-scope if a measurable CI slowdown emerges; for now, the 1-2s cold start per test stays under the e2e_http opt-in lane so the fast path is untouched.
- **`agent_brain_mcp/server.py` is now mypy-strict-disabled for the SDK-untyped-decorator codes (`misc`, `no-untyped-call`, `untyped-decorator`).** The new `_MetaInjectingServerSession` subclass + `_install_meta_injecting_session` helper add ~70 LOC under that disable. Phase 55's coverage / mypy audit should consider whether to extend or scope the disable more tightly.
- **Plan 02's `task mcp:smoke:http` is NOT yet in root `task before-push`.** Phase 55 (VAL-04) folds it in. Until then, Plan 03's smoke runs as opt-in only.

---

## Self-Check: PASSED

- `agent-brain-mcp/tests/test_transport_selection.py` — FOUND (created, 1 e2e_http test pass)
- `agent-brain-mcp/tests/test_http_loopback.py` — FOUND (created, 1 e2e_http test pass)
- `agent-brain-mcp/tests/test_http_negative_paths.py` — FOUND (created, 3 tests pass: 2 fast lane + 1 e2e_http)
- `agent-brain-mcp/agent_brain_mcp/server.py` — FOUND (modified; `_MetaInjectingServerSession` + `_install_meta_injecting_session` added; build_server attaches `_agent_brain_meta`)
- `agent-brain-mcp/agent_brain_mcp/cli.py` — FOUND (modified; loopback + port probe hoisted)
- `agent-brain-mcp/agent_brain_mcp/http.py` — FOUND (modified; `probe_port_available` public alias added)
- `agent-brain-mcp/pyproject.toml` — FOUND (modified; `e2e_http` marker + addopts + psutil dev dep)
- `agent-brain-mcp/Taskfile.yml` — FOUND (modified; `mcp:smoke:http` + `mcp:smoke:all` + PYTHONPATH fix)
- `agent-brain-mcp/tests/conftest.py` — FOUND (modified; `mcp_http_subprocess` + `fake_http_server_module` fixtures)
- `agent-brain-mcp/tests/test_smoke.py` — FOUND (modified; meta dict assertion)
- `agent-brain-mcp/README.md` — FOUND (modified; Transport selection section)
- `docs/MCP_USER_GUIDE.md` — FOUND (modified; MCP transport axes section + CLI flags reorg)
- Commit `ce45940` — FOUND (feat(53-03): wire serverInfo._meta + CLI hoist for transport/port validation)
- Commit `e664c0e` — FOUND (chore(53-03): register e2e_http marker + psutil dev dep + smoke:http task)
- Commit `38af276` — FOUND (test(53-03): SDK HTTP round-trip + loopback bind + negative paths)
- Commit `fc137f2` — FOUND (docs(53-03): document HTTP transport selection + two-axis model)
- `poetry run black --check agent_brain_mcp tests` — exit code 0
- `poetry run ruff check agent_brain_mcp tests` — exit code 0
- `poetry run mypy agent_brain_mcp` — exit code 0
- `poetry run pytest` (fast path) — 308 passed, 46 deselected, coverage 91.03% (above 80% gate)
- `task mcp:smoke:http` — exit code 0 (3 e2e_http tests pass)
- `task check:layering` — exit code 0 (3 contracts kept)
- `task before-push` — exit code 0 (416 monorepo tests passed; coverage gates honored)

---
*Phase: 53-streamable-http-transport*
*Completed: 2026-06-03*
