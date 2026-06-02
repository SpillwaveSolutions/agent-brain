# Phase 53: Streamable HTTP transport — Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

`agent-brain-mcp` learns a second listen transport — Streamable HTTP per the current MCP spec — without losing the stdio behavior shipped in v1 (10.1.0):

1. New CLI flag `--transport {stdio,http}` on `agent-brain-mcp` (HTTP-01). Default stays `stdio` so existing Claude Desktop / Code installs keep working unchanged.
2. HTTP mode binds **loopback only** (`127.0.0.1`), no authentication (HTTP-02). Loopback is enforced; binding to `0.0.0.0` or a public interface is rejected at startup.
3. Transport selection is **explicit and load-bearing** — an invalid `--transport` value, an unavailable transport dependency, or a port-in-use produces a clear startup error. No silent fallback from `http` to `stdio` or vice versa (HTTP-03).
4. Auth is **explicitly reserved for MCP v4** (#188). v2 ships zero auth on the HTTP transport; the v2 design doc must say so out loud and warn operators not to expose the port.

Phase 53 stops at the transport boundary. The 9 deferred tools (Phase 54), `wait_for_job` progress notifications (Phase 54), resource subscriptions (Phase 52), and the new URI schemes (Phase 51) are out of scope — they ride either transport once Phase 53 lands. Phase 53 is independent of Phase 52 and can execute in parallel with it.

</domain>

<decisions>
## Implementation Decisions

### A. Transport selection wiring
- **D-01:** Replace today's `--backend {auto,uds,http}` mental model (which controls the **backend** httpx client transport between the MCP server and the Agent Brain HTTP server) with a separate, orthogonal `--transport {stdio,http}` flag that controls the **listen** transport between the MCP client (Claude Desktop, SDK) and the MCP server. The two are unrelated axes — `--backend` is preserved untouched, `--transport` is new. Naming is deliberately **listen-side**, not "frontend/backend", to avoid confusion in docs and error messages.
- **D-02:** Default `--transport` is `stdio`. No env-var override in v2 (`AGENT_BRAIN_MCP_TRANSPORT` is reserved but not honored yet). Reason: env-driven transport selection invites silent surprises in Claude Desktop where the env is inherited; explicit flag forces operators to opt in.
- **D-03:** `--transport http` requires `--host` (default `127.0.0.1`) and `--port` (default `8765`). Both are exposed as Click options so operators can change the port if 8765 is taken. Host is **validated** at startup — see D-06 for the loopback enforcement rule.
- **D-04:** Stdio mode ignores `--host` / `--port` (logged as INFO at DEBUG level, not WARN — they're harmless defaults). HTTP mode ignores nothing; all flags participate.

### B. HTTP server implementation
- **D-05:** Use the **MCP SDK's built-in Streamable HTTP support** (`mcp.server.streamable_http_manager.StreamableHTTPSessionManager` + `mcp.server.fastmcp.server.StreamableHTTPASGIApp`) rather than hand-rolling HTTP/SSE on top of `httpx` or Starlette. Verified present in `mcp 1.12.0` (see Phase 50 lockstep pin in `pyproject.toml`). The SDK pattern: build a low-level `Server` (we already do this in `agent_brain_mcp/server.py:build_server`), wrap it with `StreamableHTTPSessionManager(app=server, event_store=None, json_response=False, stateless=False)`, mount the ASGI app at `/mcp`, and serve via uvicorn.
- **D-06:** Run uvicorn **in-process**, not as a child process. The MCP server is single-purpose — no other ASGI app shares the loop — so launching uvicorn via `uvicorn.Server(uvicorn.Config(app, host, port, lifespan="on")).serve()` inside `main_async()` is simpler than orchestrating a subprocess. Mirrors how `agent-brain-server/api/uds_bind.py` runs uvicorn for the existing FastAPI server. **No FastAPI** in this path — the MCP SDK's StreamableHTTPASGIApp is a Starlette app, not FastAPI; do not add FastAPI as a dep.
- **D-07:** Mount path is `/mcp` (matches FastMCP default at `mcp/server/fastmcp/server.py:166 streamable_http_path: str = "/mcp"`). Health probe lives at `/healthz` returning `{"status": "ok", "transport": "http"}` so operators can curl-check the listener without driving the full MCP handshake. Note: `/healthz` is distinct from the agent-brain-server's `/health/` endpoint (which is the backend the MCP server talks to via httpx).

### C. Loopback enforcement (HTTP-02)
- **D-08:** Hard whitelist: `--host` accepts only `127.0.0.1`, `localhost`, and `::1`. Any other value produces a startup error: `agent-brain-mcp: error: --host must be one of {127.0.0.1, localhost, ::1} (auth is deferred to v4; binding to public interfaces is unsafe in v2)`. **No `--allow-public-bind` escape hatch** — auth is the only acceptable gate for a non-loopback bind, and auth is v4. The error message names v4 / OAuth explicitly so operators know when to expect the option.
- **D-09:** Lean on the **MCP SDK's auto-enabled DNS rebinding protection** for localhost binds (verified at `mcp/server/fastmcp/server.py:177-183` — when `host in ("127.0.0.1", "localhost", "::1")`, the SDK configures `TransportSecuritySettings(enable_dns_rebinding_protection=True, allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"], allowed_origins=["http://127.0.0.1:*", ...])`). We do not pass a custom `transport_security` — defaults are correct for loopback-only v2.
- **D-10:** Document in startup banner: `MCP server listening on http://127.0.0.1:<port>/mcp (loopback only, no auth — do NOT expose this port)`. Operators see the warning in their logs and Claude Desktop output without having to read the design doc.

### D. No-silent-fallback policy (HTTP-03)
- **D-11:** Invalid `--transport` value → Click's built-in `click.Choice(["stdio", "http"], case_sensitive=False)` rejection. Error path is the standard Click usage error — no custom handling needed.
- **D-12:** Port-in-use (`OSError: [Errno 48] Address already in use`) → catch in `main_async()`, raise `click.ClickException` with message `Port {port} already in use. Pass --port <free-port> or stop the conflicting process.` Do NOT fall back to a random port (silent surprise) or to stdio (transport mismatch). Exit code 2.
- **D-13:** Stdio mode failure (e.g., stdio closed unexpectedly) does NOT fall back to HTTP. Stdio errors propagate as today.
- **D-14:** Backend reachability is **independent of listen transport**. If the HTTP listener binds successfully but `agent-brain-serve` (the backend) is unreachable, that surfaces per-request as `BackendUnavailable` (existing error mapping in `agent_brain_mcp/errors.py:117 raise_backend_unavailable`) — not as a startup error. The MCP server can listen on HTTP even with the backend down so MCP clients see a clear per-call error instead of a connection refused at handshake time.

### E. Stdio behavior preservation
- **D-15:** When `--transport stdio` is selected (the default), the entire current code path runs unchanged — `mcp.server.stdio.stdio_server()` context manager + `server.run(read_stream, write_stream, ...)`. No refactor of `server.py:run_stdio()`. The HTTP path is a sibling function `run_http(server, *, host, port)` that the dispatcher in `main_async` calls instead. This keeps the diff small and stdio risk-free.
- **D-16:** The same `build_server(httpx_client, transport=...)` from `agent_brain_mcp/server.py:82` produces the `Server` instance for both transports. The `transport` parameter (currently set to `"http"` or `"uds"` for the **backend** httpx transport — see D-01) becomes ambiguous if reused; rename the existing parameter to `backend_transport` and add a new `listen_transport` parameter so both labels appear in the server's `_meta` block (per existing line 209). Both are surfaced in MCP initialize `serverInfo._meta` for client debugging — backwards-compatible additive change, not a rename of an over-the-wire field.

### F. Testing scope (Phase 53 owns these; Phase 55 owns the SDK contract sweep)
- **D-17:** Phase 53 adds: (a) `test_transport_selection.py` — verifies stdio still works, HTTP starts and serves an initialize handshake via official MCP SDK HTTP client (`mcp.client.streamable_http.streamablehttp_client`), `--transport bogus` rejects, `--host 0.0.0.0` rejects, port-in-use raises ClickException; (b) `test_http_loopback.py` — binds and confirms TCP listen socket is bound to `127.0.0.1`, attempts to connect from a non-loopback peer in CI (use `socket.SO_BINDTODEVICE` or simply assert `server.servers[0].sockets[0].getsockname()[0] == "127.0.0.1"`); (c) `test_http_smoke.py` — drives `tools/list`, `resources/list`, `prompts/list` over HTTP and asserts the 7-tool / 5-resource / 6-prompt v1 surface is identical to stdio. Phase 55 (VAL-03) folds these into the parameterized SDK contract suite.
- **D-18:** No subscription tests in Phase 53 — Phase 52 owns SUB-01..05 and runs in parallel. The Phase 53 HTTP smoke test must not assume subscriptions exist; it asserts only the v1-equivalent surface advertised over HTTP.

### Claude's Discretion
- Exact name of the new `run_http()` function in `server.py` (vs splitting it into a new module `agent_brain_mcp/http.py` — planner decides based on diff size).
- Whether to log the loopback warning at WARN or INFO (recommend INFO at startup, WARN if a non-default host is passed and rejected — surfaces the rejection more loudly).
- Whether to add a `--log-level` flag now or defer (recommend defer — uvicorn's default is fine for v2).
- Diagram tool for the v2 design doc's HTTP transport section (mermaid sequence diagram recommended showing initialize → tools/list → tools/call over HTTP).
- Whether the `/healthz` health probe path is configurable (recommend hardcode for v2; reconsider if framework adapters in v3 need it).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope contracts
- `.planning/REQUIREMENTS.md` §Streamable HTTP Transport (HTTP) — defines HTTP-01/02/03 in their authoritative form
- `.planning/ROADMAP.md` Phase 53 — phase boundaries and the 3 success criteria
- `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` §Streamable HTTP MCP transport — v2 scope contract; affirms loopback-only and "no auth in v2 — auth is v4"

### Phase 50 carry-forward
- `.planning/phases/50-server-endpoint-prep-v2-design-doc/50-CONTEXT.md` §Decision D (design-doc depth) — v2 design doc MUST cover Phase 53 in its "Architecture deltas vs v1" section. Phase 53 cannot start coding until VAL-05's design doc has landed and called out HTTP transport decisions. Phase 50's risk register entry on #179 auth interaction is load-bearing for Phase 53 (see Specifics below).

### v1 design lineage
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` §1 ("What v1 does not ship" — flagged Streamable HTTP as deferred) and §11 (v2 row, lists HTTP transport as a v2 deliverable). v1 plan is the structural reference for v2's design doc style.
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` §5 (server-side UDS bind / dual-uvicorn pattern) — reference for the in-process uvicorn pattern Phase 53 re-uses for the MCP HTTP listener. NB: the **server** uses dual-bind (HTTP + UDS for the backend FastAPI); the **MCP package** runs a single uvicorn instance for the MCP HTTP listener — do not confuse the two.

### MCP package (existing v1 code Phase 53 extends)
- `agent-brain-mcp/agent_brain_mcp/server.py` — `build_server(httpx_client, transport=...)` is the existing factory; `run_stdio(server)` is the existing stdio entry. Phase 53 adds a sibling `run_http(server, host, port)` and a dispatcher in `main_async`.
- `agent-brain-mcp/agent_brain_mcp/cli.py` — Click command; new `--transport / --host / --port` flags go here. Existing `--backend / --backend-url / --state-dir` stay untouched (orthogonal axis, see D-01).
- `agent-brain-mcp/agent_brain_mcp/config.py` — `open_backend_client()` controls the **backend** httpx transport (HTTP vs UDS). Phase 53 does NOT touch this; it operates on the **listen** transport axis.
- `agent-brain-mcp/agent_brain_mcp/errors.py` — `raise_backend_unavailable()` already handles backend reachability errors; Phase 53 reuses it for the "HTTP listener up, backend down" case (D-14).
- `agent-brain-mcp/pyproject.toml` — already pins `mcp = "^1.12.0"`, which includes `StreamableHTTPSessionManager` + `StreamableHTTPASGIApp`. No new dependency needed; uvicorn is transitively present via the SDK (verify before planning — if not, add `uvicorn = "^0.32"`).

### MCP SDK reference (vendored in `.venv` for verification)
- `agent-brain-mcp/.venv/lib/python3.12/site-packages/mcp/server/streamable_http.py:123 class StreamableHTTPServerTransport` — the low-level transport
- `agent-brain-mcp/.venv/lib/python3.12/site-packages/mcp/server/streamable_http_manager.py:30 class StreamableHTTPSessionManager` — session manager that wraps a `Server` and emits an ASGI app
- `agent-brain-mcp/.venv/lib/python3.12/site-packages/mcp/server/fastmcp/server.py:777 run_streamable_http_async` and `:950 streamable_http_app` — reference implementation pattern (we mirror this but stay on the low-level `Server`, not FastMCP)
- `agent-brain-mcp/.venv/lib/python3.12/site-packages/mcp/server/fastmcp/server.py:177-183 transport_security auto-enable` — DNS rebinding protection on loopback (see D-09)

### MCP protocol (external, cited in design doc)
- MCP spec — Streamable HTTP transport definition, `Mcp-Session-Id` header, `text/event-stream` MIME for SSE, `application/json` for batched responses. Phase 53 design-doc subsection must cite the spec revision the SDK is built against (1.12.0 → 2026-03-26 revision).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`agent_brain_mcp/server.py:build_server()`** — already separates server construction from transport. Same factory drives both stdio and HTTP listeners. No refactor needed; just add a second `run_*` function alongside `run_stdio()`.
- **`agent_brain_mcp/server.py:main_async()`** — already takes `backend / backend_url / state_dir` and resolves the **backend** httpx client. Phase 53 adds `transport / host / port` parameters and a dispatch on `transport` after the backend client is opened. Version-compat check (lines 296-303) runs for both transports.
- **`agent_brain_mcp/cli.py`** — Click command already has the boilerplate. Phase 53 adds three Click options. No structural change.
- **`agent-brain-server/agent_brain_server/api/uds_bind.py`** (server, not MCP) — reference for the in-process uvicorn pattern (`uvicorn.Server(uvicorn.Config(app, host, port)).serve()`). MCP HTTP listener mirrors this shape but with a single bind, not dual.
- **`agent_brain_mcp/errors.py:raise_backend_unavailable()`** — already handles "backend not reachable" cleanly. Reuse for D-14 (HTTP listener up, backend down).
- **MCP SDK `StreamableHTTPSessionManager`** — does the protocol-level work. We provide the `Server` and the ASGI mount; the SDK handles session IDs, SSE streaming, and request routing.

### Established Patterns
- **No silent fallback** (Phase 50 D-11 / v9.0 decision precedent): Phase 53 inherits this — `--transport` is explicit, port-in-use errors loudly, invalid host errors loudly.
- **Click for CLI ergonomics** (existing in `cli.py`): `click.Choice` for `--transport`, `click.IntRange(1, 65535)` for `--port`. Standard idiom.
- **In-process uvicorn** (Phase 0/2 server precedent): one less process to orchestrate; lifespan="on" so MCP server startup banner works.
- **Asyncio event loop** (existing `main_async`): no change in concurrency model — uvicorn integrates cleanly with the existing asyncio code.
- **Lockstep version pin** (v1 §6.1): `serverInfo` reports `_meta.agentBrainTransport`. Phase 53 expands this to report **both** `_meta.agentBrainBackendTransport` (current) and `_meta.agentBrainListenTransport` (new). Additive; v1 stdio clients see both fields but only need to read what they care about.

### Integration Points
- **`runtime.json`** (`<state_dir>/runtime.json`) — `agent-brain` (server) writes `socket_path` and `base_url`. Phase 53's MCP HTTP listener does NOT write to runtime.json. If a future CLI-via-MCP feature needs to discover the MCP HTTP port (v3), introduce `mcp.runtime.json` then — not now. Avoid coupling Phase 53 to v3 scope.
- **`Taskfile.yml`** (root + `agent-brain-mcp/Taskfile.yml`) — Phase 53 adds `task mcp:smoke:http` task (analog to the existing stdio smoke) so quick-start scripts and CI can drive an HTTP roundtrip. Phase 55 folds this into root `task before-push` per VAL-04.
- **Claude Desktop config** (operator-facing) — stdio remains the recommended Claude Desktop config (no change). HTTP transport is documented as **for SDK/IDE clients and v3 framework adapters**, not Claude Desktop's default. Documented in USER_GUIDE.md update.

### Greenfield (no existing pattern)
- **No prior HTTP listener in `agent-brain-mcp`.** Phase 53 introduces it. Decision F bundles the smoke tests; planner picks file layout (new module `agent_brain_mcp/http.py` vs extend `server.py`).
- **No prior `/healthz` endpoint in `agent-brain-mcp`.** D-07 adds a tiny Starlette route alongside the StreamableHTTPASGIApp mount; ~10 LOC, no test surface beyond a 200-OK assertion.

</code_context>

<specifics>
## Specific Ideas

- The v2 design doc's HTTP transport section must call out **#179 API authentication** explicitly: when #179's Bearer-token middleware lands on `agent-brain-server`, the MCP server's backend httpx client (per `config.py:open_backend_client`) will need to pass through that token — but that's a per-request concern on the **backend** axis, not the **listen** axis. The MCP HTTP listener itself remains unauthenticated in v2 per HTTP-02 / OAUTH-01 (v4). The doc should diagram this two-axis model so reviewers don't conflate "auth on the backend" with "auth on the MCP HTTP transport."
- The v2 design doc must also call out the **trust model**: `127.0.0.1` binding alone does not protect against malicious local processes — any process running as the same user can reach the MCP port and drive tools (including `cancel_job` which is annotated `destructiveHint: true`). Document this in the "Threat Model / Security" subsection alongside Phase 50's `roots/list` sandbox discussion. The deferred ideas list below adds local-process attestation as a v3+ idea.
- **Phase 53 deliberately ships before Phase 54** because the new 9 tools (Phase 54) need to be reachable via both transports. If Phase 53 slipped after Phase 54, Phase 54's tools would only be testable over stdio until Phase 53 lands — that's the dependency inversion the milestone ordering avoids. Surface this in the design doc's phase-ordering rationale.
- **Phase 53 is independent of Phase 52** (subscriptions): the HTTP transport must work for `resources/list`, `resources/read`, `tools/*`, and `prompts/*` regardless of whether subscriptions are wired. The Phase 53 HTTP smoke test must NOT assume subscription support — that lets Phase 52 and Phase 53 ship in either order without rework.
- **MCP SDK version pin is load-bearing.** `mcp = "^1.12.0"` already exposes Streamable HTTP. If a planner proposes upgrading to `^1.13` or `^2.x`, that's a separate ADR — Phase 53 does not require it. Confirm via `poetry show mcp` before planning that 1.12.x is the resolved version in the lockfile.

</specifics>

<deferred>
## Deferred Ideas

- **`--transport both` (run stdio AND http simultaneously)** — possible since they share a `Server` instance, but not in scope for v2. Defer to v3 if framework adapters want a single-process listener that's reachable both ways. Adds asyncio concurrency complexity (two `server.run()` calls on one loop) — small but not free.
- **`AGENT_BRAIN_MCP_TRANSPORT` env var** — reserved name (per D-02) but not honored in v2. Add in v3 if operators ask for env-driven selection in framework-adapter CI environments.
- **Custom `/healthz` body** — v2 ships a hardcoded `{"status": "ok"}`. Operators wanting embedding-cache stats or backend reachability info can call `server_health` over MCP. Defer richer `/healthz` to v3 alongside framework adapter ergonomics.
- **`/metrics` Prometheus endpoint** — out of scope for v2. v3 framework matrix may want it for production deployment; revisit then.
- **Non-loopback bind with auth** — explicitly deferred to v4 (OAUTH-01..04). Phase 53 must NOT add any `--allow-public-bind` / `--skip-auth-check` escape hatch; v4 is the right time, with the auth context to do it safely.
- **Local-process attestation** (proof that the connecting process belongs to the same user / specific binary) — deeper trust model than v2's "loopback is enough." Track as a v3+ security follow-up alongside OAuth.
- **Streamable HTTP resumability** — the MCP SDK's `EventStore` allows clients to resume disconnected sessions. v2 passes `event_store=None` (stateless sessions). Persistent event store is a v3+ concern, not v2.
- **MCP HTTP port discovery via `mcp.runtime.json`** — needed for v3 CLI-via-MCP so the CLI can auto-find the MCP HTTP listener. Not needed in v2; Phase 53 explicitly does not write a runtime file.
- **HTTP-over-UDS for MCP** — would unify the v1 UDS transport (currently backend-only) with MCP listen. Not in scope; UDS is for the backend axis, HTTP/stdio is for the listen axis.

</deferred>

---

*Phase: 53-streamable-http-transport*
*Context gathered: 2026-06-02*
