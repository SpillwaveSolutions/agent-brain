---
phase: 53-streamable-http-transport
verified: 2026-06-03T18:05:00Z
status: passed
score: 3/3 must-haves verified
must_haves:
  truths:
    - "Operator can run `agent-brain-mcp --transport http` to start an MCP server over Streamable HTTP (HTTP-01)"
    - "Streamable HTTP transport binds loopback only; v2 ships no MCP authentication (HTTP-02)"
    - "Stdio continues to work alongside HTTP; transport selection is explicit via --transport with no silent fallback (HTTP-03)"
  artifacts:
    - path: "agent-brain-mcp/agent_brain_mcp/cli.py"
      provides: "Click options --transport / --host / --port; CLI hoist of validate_loopback_host + probe_port_available before main_async"
    - path: "agent-brain-mcp/agent_brain_mcp/http.py"
      provides: "validate_loopback_host, PortInUseError(exit_code=2), build_asgi_app, run_http with pre-flight port probe + finally cleanup_all, loopback_transport_security"
    - path: "agent-brain-mcp/agent_brain_mcp/server.py"
      provides: "build_server returns (Server, SubscriptionManager); _MetaInjectingServerSession + _install_meta_injecting_session; main_async dispatcher; legacy transport= alias with DeprecationWarning"
    - path: "agent-brain-mcp/tests/test_transport_selection.py"
      provides: "SDK round-trip e2e against subprocess — initialize + 7 tools / 5 resources / 6 prompts + _meta both labels"
    - path: "agent-brain-mcp/tests/test_http_loopback.py"
      provides: "psutil kernel-level loopback bind assertion against live subprocess"
    - path: "agent-brain-mcp/tests/test_http_negative_paths.py"
      provides: "3 subprocess-driven negative paths (bogus, non-loopback, port-in-use exit 2)"
  key_links:
    - from: "cli.py"
      to: "http.validate_loopback_host + http.probe_port_available"
      via: "imported and called pre-main_async when transport==http"
    - from: "server.py build_server"
      to: "_install_meta_injecting_session"
      via: "called at end of build_server; wraps server.run to substitute _MetaInjectingServerSession"
    - from: "http.run_http finally"
      to: "subscription_manager.cleanup_all()"
      via: "called on every exit path including PortInUseError pre-probe branch"
    - from: "build_asgi_app"
      to: "StreamableHTTPSessionManager(..., security_settings=loopback_transport_security())"
      via: "explicit security_settings kwarg (manager does NOT auto-enable like FastMCP)"
---

# Phase 53: Streamable HTTP Transport Verification Report

**Phase Goal:** `agent-brain-mcp` learns a Streamable HTTP listen transport (loopback-only, no auth — auth deferred to v4) without losing stdio behavior. Transport selection is explicit via `--transport {stdio,http}` flag with no silent fallback. The v1-equivalent surface (7 tools, 5 resources, 6 prompts) is reachable over both transports.
**Verified:** 2026-06-03T18:05:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | **HTTP-01** — Operator can run `agent-brain-mcp --transport http`; SDK HTTP client speaks the v1 surface over the listener | VERIFIED | `cli.py:40-67` declares `--transport [stdio|http]`, `--host TEXT`, `--port IntRange(1,65535)`; `http.py:290-395` `run_http` mounts `StreamableHTTPSessionManager` via Starlette + uvicorn; `test_transport_selection.py:48-120` drives `streamablehttp_client` against a live subprocess and asserts the exact v1 set `{search_documents, query_count, index_folder, get_job, list_jobs, cancel_job, server_health}` plus `len(resources) == 5` and `len(prompts) == 6`. Test PASSED in 2.16s. |
| 2 | **HTTP-02** — Loopback-only bind, no auth; banner emits the contract warning; kernel socket actually bound to 127.0.0.1 | VERIFIED | `http.py:65-67` whitelist `{127.0.0.1, localhost, ::1}`; `http.py:77-80` exact contract message `--host must be one of {127.0.0.1, localhost, ::1} (auth is deferred to v4; binding to public interfaces is unsafe in v2)`; `http.py:365-371` banner literal `(loopback only, no auth — do NOT expose this port)`; `http.py:118-122` `loopback_transport_security()` returns `TransportSecuritySettings(enable_dns_rebinding_protection=True, ...)`; `http.py:184` passed explicitly to `StreamableHTTPSessionManager`; `test_http_loopback.py:37-78` uses `psutil.Process(pid).net_connections(kind="tcp")` filtered to `CONN_LISTEN` and asserts every `laddr.ip in {127.0.0.1, ::1}`. Test PASSED against live subprocess. |
| 3 | **HTTP-03** — Explicit transport selection, no silent fallback (bogus rejected, non-loopback rejected, port-in-use exits 2 with contract message) | VERIFIED | `cli.py:42` uses `click.Choice(["stdio", "http"], case_sensitive=False)` — `bogus` rejected by Click before dispatch; `cli.py:88-90` CLI hoist runs `validate_loopback_host(host)` + `probe_port_available(host, port)` BEFORE main_async (so non-loopback fails before backend probe masks it); `http.py:97-106` `PortInUseError(click.ClickException)` with `exit_code = 2`; `http.py:245-256` `_probe_port_available` raises `PortInUseError` on errno 48/98; `server.py:912-920` dispatcher has explicit `if/elif` with `ValueError` fallback for direct callers — no silent fallback path. `test_http_negative_paths.py` 3 tests all PASSED: bogus exits non-zero with "not one of", `--host 0.0.0.0` exits non-zero with "must be one of"/"loopback" message, `--port <occupied>` exits with code `2` and "already in use" wording. |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-mcp/agent_brain_mcp/cli.py` | Click options + hoist | VERIFIED | All 3 new Click options present with case-insensitive Choice for `--transport` (`cli.py:40-67`); `validate_loopback_host` + `probe_port_available` imported from `.http` (`cli.py:9`) and called pre-main_async when `transport == "http"` (`cli.py:88-90`) |
| `agent-brain-mcp/agent_brain_mcp/http.py` | run_http listener + loopback validator + PortInUseError + cleanup hook | VERIFIED | 318 LOC module exports `run_http`, `validate_loopback_host`, `probe_port_available`, `PortInUseError(exit_code=2)`, `build_asgi_app`, `build_uvicorn_server`, `loopback_transport_security`, `ALLOWED_LOOPBACK_HOSTS`, `MCP_MOUNT_PATH`, `HEALTHZ_PATH`, `LOOPBACK_REJECTION_MESSAGE`; finally block calls `subscription_manager.cleanup_all()` on every exit path (success, port-in-use pre-probe at line 356, OSError at line 388); explicit `security_settings=loopback_transport_security()` at `http.py:184` |
| `agent-brain-mcp/agent_brain_mcp/server.py` | build_server tuple return + _meta wire injection + dispatcher | VERIFIED | `build_server` signature at `server.py:175-181` returns `tuple[Server, SubscriptionManager]`; legacy `transport=` kwarg emits `DeprecationWarning` at `server.py:232-238`; both `_agent_brain_backend_transport` and `_agent_brain_listen_transport` private attrs set (`server.py:578-579`); `_agent_brain_meta` dict attached (`server.py:600-603`); `_MetaInjectingServerSession` SDK subclass + `_install_meta_injecting_session(server)` helper wired (`server.py:643-778`) — wraps `server.run` on instance, substitutes session subclass, override only `InitializeRequest` case via `Implementation(_meta=<dict>)` exploiting `model_config = ConfigDict(extra="allow")`; `main_async` dispatcher uses `if/elif/else ValueError` shape at `server.py:912-920` |
| `agent-brain-mcp/tests/test_transport_selection.py` | SDK round-trip e2e | VERIFIED | Drives `mcp.client.streamable_http.streamablehttp_client` against live `agent-brain-mcp` subprocess; asserts `tool_names == {7 v1 names}` set equality (not just count), `len(resources) == 5`, `len(prompts) == 6`; asserts `meta_raw.get("agentBrainListenTransport") == "http"` AND `"agentBrainBackendTransport" in meta_raw`; defensive `*_` unpack on yield tuple. PASSED |
| `agent-brain-mcp/tests/test_http_loopback.py` | psutil kernel socket inspection | VERIFIED | Uses `psutil.Process(proc.pid).net_connections(kind="tcp")` filtered to `psutil.CONN_LISTEN`; asserts every `conn.laddr.ip in {"127.0.0.1", "::1"}`; cross-checks `free_loopback_port` is in bound port set; skipif Windows. PASSED |
| `agent-brain-mcp/tests/test_http_negative_paths.py` | bogus + non-loopback + port-in-use exit 2 | VERIFIED | 3 subprocess-driven tests via `python -m agent_brain_mcp.cli`; port-in-use case marked `@pytest.mark.e2e_http` because it briefly attempts bind; all 3 PASSED with exit code 2 confirmed on port-in-use |
| `agent-brain-mcp/pyproject.toml` | e2e_http marker + addopts + psutil | VERIFIED | Lines 86-87 register both `e2e` and `e2e_http` markers; line 90 `addopts = "-m 'not e2e and not e2e_http'"` excludes both from fast path; line 54 `psutil = "^6.0"` in dev dep group |
| `agent-brain-mcp/Taskfile.yml` | mcp:smoke:http task | VERIFIED | Lines 96-100 define `mcp:smoke:http` running `pytest test_transport_selection.py test_http_loopback.py test_http_negative_paths.py -v -m e2e_http`; lines 102-107 define `mcp:smoke:all` umbrella |
| `agent-brain-mcp/README.md` | Transport selection section | VERIFIED | Section "Transport selection (v10.2+)" at line 39; copy-pasteable `agent-brain-mcp --transport http --host 127.0.0.1 --port 8765` invocation at line 57; loopback / no-auth banner reproduced verbatim; exit code table (1 = validation; 2 = port-in-use); `AGENT_BRAIN_MCP_TRANSPORT` reserved-but-not-honored note at line 101 |
| `docs/MCP_USER_GUIDE.md` | Two-axis transport diagram + #179 vs OAUTH-01 disambiguation | VERIFIED | Section "MCP transport axes (v10.2+)" at line 244; ASCII two-axis diagram at line 249; line 275 states `In short: #179 ≠ OAUTH-01. They protect different axes.`; OAUTH-01 / #188 named as listen-axis v4 concern; #179 named as backend-axis Bearer-token middleware |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `cli.py` (CLI hoist) | `http.validate_loopback_host` + `http.probe_port_available` | imported and called pre-main_async | WIRED | `cli.py:9` imports both; `cli.py:88-90` calls them BEFORE `asyncio.run(main_async(...))`; gated on `if transport == "http"` — closes the BackendUnavailable masking gap |
| `build_server` end | `_install_meta_injecting_session(server)` | direct call at `server.py:604` | WIRED | Helper wraps `server.run` on the instance (`server.py:726-778`); stashes original at `_agent_brain_original_run`; substitutes `_MetaInjectingServerSession` for `ServerSession` |
| `_MetaInjectingServerSession._received_request` | `Implementation(_meta=<dict>)` | extra="allow" Pydantic round-trip | WIRED | Override only matches `InitializeRequest` case (`server.py:674-704`); every other case defers to `super()._received_request()` at line 707; SDK-version-pinned with inline comments referencing `mcp/server/session.py:165-187` (mcp 1.12.x) |
| `run_http` finally | `subscription_manager.cleanup_all()` | called on every exit path | WIRED | `http.py:356` calls it on PortInUseError pre-probe branch; `http.py:389` calls it in finally after `uvi_server.serve()` returns/raises; logs cleanup count if non-zero — mirrors Phase 52's `run_stdio` pattern at `server.py:826-833` |
| `build_asgi_app` | `StreamableHTTPSessionManager(..., security_settings=loopback_transport_security())` | explicit kwarg | WIRED | `http.py:179-185` constructs manager with all four explicit kwargs including `security_settings=loopback_transport_security()`; addresses the documented gap that bare `StreamableHTTPSessionManager` does NOT auto-enable DNS rebinding protection (only `FastMCP` does at `mcp/server/fastmcp/server.py:177-183`) |
| `server.py` dispatch | `run_http(server, subscription_manager, host=host, port=port)` | imported re-export | WIRED | `server.py:51` `from .http import run_http` — identity re-export (NOT a wrapper); Plan 01's monkeypatch-on-server_module dispatch tests still work because `server.run_http IS http.run_http`; defended by `test_dispatch.py::TestRunHttpStub::test_run_http_is_re_exported_from_http_module` |
| `main_async` dispatcher | explicit if/elif with ValueError fallback | no silent crossover | WIRED | `server.py:912-920` — stdio path calls `run_stdio(server, manager)`; http path calls `run_http(server, manager, host=host, port=port)`; defensive `raise ValueError(...)` for direct callers bypassing Click; `try/finally` at line 921 closes httpx client on every exit |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| HTTP-01 | 53-01, 53-02, 53-03 | Operator can run `agent-brain-mcp --transport http` to start the MCP server over Streamable HTTP | SATISFIED | CLI flags wired (Plan 01); listener mounted via StreamableHTTPSessionManager + uvicorn (Plan 02); SDK round-trip e2e proven against live subprocess (Plan 03) with exact v1 surface set equality |
| HTTP-02 | 53-02, 53-03 | Streamable HTTP transport binds loopback only (127.0.0.1); v2 ships no MCP authentication (auth is reserved for v4) | SATISFIED | `validate_loopback_host` whitelist `{127.0.0.1, localhost, ::1}` with exact contract message (Plan 02); banner literal substring `(loopback only, no auth — do NOT expose this port)` (Plan 02); explicit `loopback_transport_security()` wired (Plan 02); kernel-level psutil bind inspection proves actual socket loopback (Plan 03) |
| HTTP-03 | 53-01, 53-03 | Stdio transport continues to work alongside HTTP; transport selection is controlled by the `--transport` flag with no silent fallback | SATISFIED | Click `Choice(["stdio","http"])` rejects bogus values (Plan 01); explicit if/elif dispatcher with ValueError fallback for direct callers (Plan 01); CLI hoist of loopback + port probe BEFORE backend probe so misconfigurations don't masquerade as BackendUnavailable (Plan 03); PortInUseError(exit_code=2) for port collisions distinct from validation exit_code=1 (Plan 02); 3 subprocess negative tests prove no silent fallback (Plan 03) |

**No orphaned requirements detected.** ROADMAP.md maps exactly HTTP-01 / HTTP-02 / HTTP-03 to Phase 53; all three are declared in plan frontmatters (Plan 01: HTTP-01 partial + HTTP-03 full; Plan 02: HTTP-01 full + HTTP-02 full; Plan 03: HTTP-01 + HTTP-02 + HTTP-03 cumulative e2e closure). Requirements traceability rows in ROADMAP.md all read `Complete`.

### Anti-Patterns Found

None. Spot-checked the three modified source files for TODO/FIXME/PLACEHOLDER/stub markers:
- `cli.py` — only Phase 53 Plan 03 explanatory comments, no anti-patterns.
- `http.py` — only design-rationale docstrings + decision references, no stubs.
- `server.py` — no anti-patterns; the Plan 01 `NotImplementedError` stub was properly replaced by the `from .http import run_http` re-export (`server.py:51`).

### Critical Contracts (Spot-Checked)

| Contract | Status | Evidence |
|----------|--------|----------|
| `build_server()` returns `tuple[Server, SubscriptionManager]` (Phase 52 contract preserved) | VERIFIED | Return annotation at `server.py:181`; `return server, subscription_manager` at line 605 |
| Both transport labels in `serverInfo._meta` over the wire | VERIFIED | `_MetaInjectingServerSession._received_request` overrides only InitializeRequest case; passes `_meta=dict(self._agent_brain_meta)` to `Implementation(...)` constructor (`server.py:688-689`); confirmed wire-format by `test_transport_selection.py` asserting both `agentBrainListenTransport == "http"` and `"agentBrainBackendTransport" in meta_raw` |
| Legacy `transport=` kwarg emits `DeprecationWarning` | VERIFIED | `server.py:232-238` calls `warnings.warn(..., DeprecationWarning, stacklevel=2)` and routes to `backend_transport` |
| CLI hoist: validate_loopback_host + probe_port_available run BEFORE main_async | VERIFIED | `cli.py:88-90` — gated on `transport == "http"`, runs before `asyncio.run(main_async(...))`; closes the BackendUnavailable masking gap so non-loopback hosts and port collisions surface cleanly even when no backend is running |
| `run_http` finally calls `cleanup_all()` on every exit path | VERIFIED | `http.py:356` on PortInUseError pre-probe; `http.py:388-395` finally block runs after success / SIGINT / OSError / unhandled exception; cleanup count logged if non-zero |
| Explicit `security_settings=loopback_transport_security()` (manager does NOT auto-enable) | VERIFIED | `http.py:184` passes the kwarg explicitly; docstring at `http.py:165-169` names the FastMCP-vs-bare-manager asymmetry; `loopback_transport_security()` at `http.py:118-122` returns `TransportSecuritySettings(enable_dns_rebinding_protection=True, ...)` |
| Pytest markers `e2e` and `e2e_http` both registered + excluded from fast path | VERIFIED | `pyproject.toml:86-87` registers both markers; line 90 `addopts = "-m 'not e2e and not e2e_http'"` |
| `task mcp:smoke:http` defined and runs the 3 e2e_http tests | VERIFIED | `Taskfile.yml:96-100`; ran live during verification — 3 passed, 2 deselected in 2.16s |

### Regression Verification

| Suite | Result |
|-------|--------|
| Phase 50 / 51 / 52 fast-lane regressions + Phase 53 fast-lane | 57 passed, 5 deselected, 0 failures (`pytest tests/test_smoke.py tests/test_e2e_stdio.py tests/test_cli_transport_flags.py tests/test_dispatch.py tests/test_loopback_enforcement.py tests/test_http_listener.py tests/test_dns_rebinding.py`) — covers stdio byte-equivalent behavior (test_smoke + test_e2e_stdio), Plan 01 CLI flags + dispatcher (test_cli_transport_flags + test_dispatch), Plan 02 loopback + listener + DNS-rebinding (test_loopback_enforcement + test_http_listener + test_dns_rebinding) |
| Phase 53 e2e_http opt-in suite | 3 passed, 2 deselected (`pytest -m e2e_http`) — SDK round-trip + psutil loopback bind + port-in-use exit 2 |
| Layering contracts | 3 kept, 0 broken (`task check:layering`): server has no upward deps; uds touches only server.models; mcp never calls server internals — confirms no new `agent_brain_mcp → agent_brain_cli` or `agent_brain_mcp → agent_brain_server.{api,services,indexing,storage}` imports |

### Human Verification Required

None. All criteria verified programmatically — Click flag surface via subprocess invocation, SDK wire contract via official `streamablehttp_client`, kernel bind via psutil, exit codes via subprocess return code inspection, banner via grep against actual source.

### Deviations Worth Flagging for the Design Doc

The Plan 02 and Plan 03 SUMMARYs already named these; they're worth preserving in the v2 design doc as upstream-quirk notes for future maintainers:

1. **uvicorn 0.32.x catches `OSError` on `loop.create_server` and calls `sys.exit(1)`** (`uvicorn/server.py:169-172`), which raises `SystemExit` (a `BaseException`) rather than propagating the underlying `OSError`. That swallows the errno AND short-circuits any caller-level `try/finally` (so `subscription_manager.cleanup_all()` would NOT fire if relied on the spec's "catch OSError at serve() call site" pattern). Mitigation: pre-flight `_probe_port_available()` at `http.py:219-256` binds-and-closes a one-shot socket BEFORE handing off to uvicorn — gives a clean `PortInUseError(exit_code=2)` + the cleanup hook actually runs. The `OSError` handler around `serve()` is preserved at `http.py:375-387` as defense-in-depth for future uvicorn behavior changes.
2. **`StreamableHTTPSessionManager` does NOT auto-enable `TransportSecuritySettings`** — only `FastMCP` does, at `mcp/server/fastmcp/server.py:177-183`. The bare manager is constructed with explicit `security_settings=loopback_transport_security()` at `http.py:184` to mirror FastMCP's defaults. Without this, DNS rebinding protection would be silently disabled despite the loopback bind.
3. **CLI-layer hoist of loopback + port probe** (Plan 03 deviation, Rule 2). `main_async` opens the backend httpx client and runs the MIN_BACKEND_VERSION check BEFORE the dispatcher reaches `run_http`. Against a missing backend, `--host 0.0.0.0` or `--port <occupied>` would surface as `BackendUnavailable` (errno 61 connection refused) instead of the loopback whitelist contract message or the port-in-use exit-2 contract. Hoisting `validate_loopback_host(host)` + `probe_port_available(host, port)` to `cli.py:88-90` (gated on `transport == "http"`) closes this gap. Plan 02's in-process checks stay as defense-in-depth for direct callers (tests, embeddings).
4. **`_meta` over-the-wire injection via SDK subclass + `Server.run` instance override** — the MCP SDK 1.12.x hardcodes the `Implementation` construction inside `mcp/server/session.py:_received_request` with no extension hook. Plan 03 exploits `Implementation.model_config = ConfigDict(extra="allow")` (`mcp/types.py:274`) to pass `_meta=<dict>` as a constructor kwarg that round-trips through `model_dump(by_alias=True)`. The duplicated ~50 LOC of SDK logic (`_MetaInjectingServerSession._received_request` mirrors `mcp/server/session.py:165-187`; `_install_meta_injecting_session` mirrors `mcp/server/lowlevel/server.py:640-690`) is SDK-version-pinned with inline comments. Phase 55 may revisit if upstream publishes a cleaner extension point.
5. **Taskfile `PYTHONPATH` env block dropped `./agent_brain_mcp`** — Plan 02's new `agent_brain_mcp/http.py`, when its parent dir is on PYTHONPATH, shadows the stdlib `http` package because Python's import system finds the local file first. urllib3 → requests → poetry's console scripts all break. The Plan 03 fix at `Taskfile.yml:env` reduced the block to `./tests` only. The poetry-installed venv resolves `agent_brain_mcp` via site-packages without needing PYTHONPATH gymnastics.

### Gaps Summary

None. All 3 observable truths verified; all artifacts present, substantive, and wired; all key links connected; all critical contracts spot-checked against actual source; both fast-lane regressions and the opt-in e2e_http suite pass; layering contracts unbroken. Phase 53 achieves its goal — the v1-equivalent MCP surface is now reachable over Streamable HTTP alongside stdio, loopback-only, no silent fallback, with both transport axis labels surfaced on `serverInfo._meta` over the wire.

---

*Verified: 2026-06-03T18:05:00Z*
*Verifier: Claude (gsd-verifier)*
