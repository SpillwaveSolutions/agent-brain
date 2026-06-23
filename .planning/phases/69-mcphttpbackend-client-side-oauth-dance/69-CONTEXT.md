# Phase 69: McpHttpBackend Client-Side OAuth Dance - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning
**Mode:** `--auto` (decisions are recommended defaults; review before planning if any look wrong)

<domain>
## Phase Boundary

`McpHttpBackend` (CLI-side) transparently completes the client half of the OAuth 2.1
dance when connecting to an OAuth-protected `agent-brain-mcp` server, and persists the
resulting tokens so that **Pattern A** invocations (a fresh subprocess/client per CLI tool
call) reuse the cached token instead of re-triggering the browser login on every call.

In scope (OAUTH-07):
- Handle `401 + WWW-Authenticate` → run the SDK `OAuthClientProvider` dance
  (PRM discovery → OASM discovery → PKCE S256 → loopback callback → token) → retry.
- `FileTokenStorage` at `state_dir/mcp-oauth-tokens.json` (chmod `0o600`) implementing the
  SDK `TokenStorage` 4-method protocol.
- Silent refresh when access token expired but refresh token valid (SC#3).
- Preserve the confused-deputy boundary: MCP→REST leg keeps `AGENT_BRAIN_API_KEY`; the
  OAuth token is NEVER forwarded upstream (SC#4 / OAUTH-08).

Out of scope (later phases / deferred):
- Split AS/RS, Keycloak-in-CI, JWKS verification, introspection/revocation → **Phase 70**.
- A dedicated `agent-brain mcp login` pre-warm command → **deferred** (see below).

</domain>

<decisions>
## Implementation Decisions

### A. Auth provider activation
- **Opt-in, default OFF.** The backend attaches an `OAuthClientProvider` only when OAuth is
  explicitly enabled (config/env, e.g. an `AGENT_BRAIN_MCP_AUTH=oauth`-style signal — exact
  name is the planner's call, mirror the server's `AGENT_BRAIN_AUTH` naming). Rationale: a
  `basic`/`none` deployment must pay nothing and must never get a surprise browser launch.
- **Client registration: DCR (Dynamic Client Registration)** — the SDK default; the
  co-located AS (Phase 67) supports it; a local CLI cannot host a CIMD HTTPS metadata doc.
  *Alternative noted:* CIMD via `OAuthClientProvider(client_metadata_url=...)` when the
  server advertises `client_id_metadata_document_supported=true` — not chosen for v1.
- **Scopes requested: the full union the CLI needs** (`read` + `index` + `admin`, per the
  Phase 68 `TOOL_SCOPE_REQUIREMENTS` map) so any command works after a single login. SC#4
  still holds — broad client scope does not weaken the upstream-token boundary.
- **Dance timeout: SDK default 300s** (`OAuthClientProvider(timeout=300.0)`).

### B. Connection-helper centralization
- **Refactor the 17 `streamablehttp_client(self.url)` call sites into ONE helper** — an
  async context manager (e.g. `_http_session()`) that builds the optional `auth=` provider
  and yields an initialized `ClientSession`. Single auth-injection point; DRY; one place to
  thread `timeout` (the SDK `streamablehttp_client` now exposes `timeout` + `auth`).
- **Provider lifetime: lazy, once per `McpHttpBackend` instance**, reused across any sessions
  opened within that invocation. (File-backed storage survives across Pattern A regardless.)
- **`McpStdioBackend` does NOT share the OAuth path** — OAuth applies to HTTP transport only.

### C. Browser / loopback UX (Pattern A)
- **`redirect_handler`:** `webbrowser.open(url)` AND print the URL to **stderr** as a headless
  fallback ("Open this URL to authorize: …").
- **`callback_handler`:** spin up an **ephemeral localhost HTTP server on an OS-assigned port**,
  capture `code` + `state`, return a friendly "authentication complete — you may close this
  tab" page, then shut down. The `redirect_uri` (`http://127.0.0.1:<port>/callback`) is chosen
  before registration so DCR registers the correct URI.
- **Headless/CI:** print the URL and run the listener anyway; if no browser is available the
  dance blocks until timeout. A non-interactive pre-auth flow is deferred (below).

### D. Token storage & refresh-failure behavior
- **Location & perms:** `state_dir/mcp-oauth-tokens.json`, `os.chmod(path, 0o600)` immediately
  after every write (mandatory — design doc Probe 6 + security gate). A test MUST assert the
  file is not world-readable.
- **Persisted content:** BOTH the `OAuthToken` and the `OAuthClientInformationFull` (the DCR
  registration result) — so per-call invocations don't re-register the client each time. This
  satisfies all 4 `TokenStorage` methods (`get/set_tokens`, `get/set_client_info`).
- **Corrupt/unreadable file:** log a warning and treat as no-token (re-trigger the dance) —
  graceful, never a hard crash.
- **Refresh-token rejected (SC#3 failure path):** fall back to the full browser dance and
  clear the dead token from storage. (The SDK provider drives most of this; ensure storage is
  reset so the next call re-registers/re-auths cleanly.)

### Locked (carried forward — NOT revisited)
- **SC#4 / OAUTH-08 confused-deputy:** the MCP→REST leg uses `X-API-Key: <AGENT_BRAIN_API_KEY>`
  (static Bearer); the client's OAuth access token is NEVER sent upstream to `agent-brain-server`.
  An automated integration test asserts the outgoing REST call carries `X-API-Key` and does
  NOT carry the OAuth token.
- **RFC 8707 Resource Indicators:** the client sends `resource` in authorization + token
  requests; the SDK `OAuthClientProvider` derives this from PRM discovery. No bespoke work.
- **PKCE S256-only:** enforced server-side (Phase 67); the SDK client uses S256 by default.

### Claude's Discretion
- Exact env/config var name for the client opt-in (mirror `AGENT_BRAIN_AUTH` conventions).
- The ephemeral-callback-server framework (stdlib `http.server` vs a tiny Starlette app).
- Whether `_http_session()` also subsumes `McpStdioBackend`'s connect (likely not).
- Error message wording and the callback success page HTML.
- Whether to wire the now-available `streamablehttp_client(timeout=...)` knob in this phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### OAuth design contract (binding)
- `docs/plans/2026-06-14-mcp-v4-oauth-design.md` — the binding design doc for Phases 66–70.
  - §"Client side — `mcp.client.auth`" (~lines 89–95) — `OAuthClientProvider` responsibilities.
  - §"Client-Side Token Storage: FileTokenStorage chmod 0o600 Required (Pattern A)" (~lines 676–690) — the mandatory `0o600` requirement + test assertion.
  - §"Risk 1: Confused-Deputy / Token Passthrough (OAUTH-08)" (~lines 120+) — the upstream-token boundary this phase must preserve.
  - §"Additional Probe: FileTokenStorage chmod 0o600" (~lines 892–905) — adversarial-review gap-fix accepted as binding.
- `.planning/research/SUMMARY.md` — PRIMARY research input (spec levels, library picks, CIMD-vs-DCR, the four threat risks). Read first.
- `docs/roadmaps/mcp/v4-oauth-for-remote.md` — v4 design sketch (standards stack, deployment shapes).

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — **OAUTH-07** (this phase) + **OAUTH-08** (confused-deputy invariant this phase preserves).
- `.planning/ROADMAP.md` — Phase 69 goal + the 4 success criteria (the DoD anchor).

### Prior-phase context (consistency)
- `.planning/phases/67-co-located-as-rs-middleware/67-CONTEXT.md` — the AS the client dances against (DCR + CIMD, PKCE S256, JWKS).
- `.planning/phases/68-per-tool-scope-enforcement/68-CONTEXT.md` — scope map that dictates which scopes the CLI requests.

### SDK source (installed `mcp 1.27.2` — verify symbols at planning time)
- `agent-brain-mcp/.venv/.../mcp/client/auth/oauth2.py` — `OAuthClientProvider.__init__(server_url, client_metadata, storage, redirect_handler, callback_handler, timeout=300, client_metadata_url=None)` and the `TokenStorage` Protocol (4 async methods).
- `agent-brain-mcp/.venv/.../mcp/client/streamable_http.py` — `streamablehttp_client(url, …, timeout=, auth: httpx.Auth | None)` — confirmed `auth=` seam.
- `agent-brain-mcp/.venv/.../mcp/shared/auth.py` — `OAuthClientMetadata`, `OAuthClientInformationFull`, `OAuthToken` models.

### Live spec (re-verify at authoring time)
- MCP Authorization spec **2025-11-25** (baseline); check the **2026-07-28 RC** status via context7/WebFetch against the live modelcontextprotocol spec.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `McpHttpBackend` — `agent-brain-mcp/agent_brain_mcp/client.py:1146`. Already takes
  `state_dir` in `__init__` (used for `mcp.runtime.json` discovery) — the same `state_dir`
  keys `FileTokenStorage`. 17 `streamablehttp_client(self.url)` call sites to centralize.
- `McpStdioBackend` — sibling backend in the same file; the connection-helper refactor must
  not disturb it (no OAuth on stdio).
- `agent_brain_cli/client/transport.py:189` — constructs `McpHttpBackend(url=…, timeout=…)`;
  must be threaded with `state_dir` (and the auth opt-in signal) for the http branch.
- `agent_brain_cli/mcp_runtime.py` — `read_mcp_runtime`/`write_mcp_runtime` resolve files
  under `state_dir`; mirror this idiom for the token file path + permission handling.

### Established Patterns
- **Pattern A** (Phase 57 CONTEXT): every backend method is `asyncio.run(self._async_*())`
  per call. This is exactly why file-backed token persistence is load-bearing.
- The SDK is **lazy-imported inside async methods** (`from mcp import ClientSession`) to keep
  HTTP/UDS-only invocations free of the MCP SDK import cost — preserve this in the helper.
- Phase 67 server-side already did DCR/CIMD + SSRF-hardened registration — the client side
  is the symmetric counterpart against the same AS.

### Integration Points
- The single new seam: `streamablehttp_client(self.url, auth=<OAuthClientProvider | None>)`.
- `FileTokenStorage` implements the SDK `TokenStorage` Protocol (4 async methods) and writes
  one JSON file (`tokens` + `client_info`) at `state_dir/mcp-oauth-tokens.json`, `0o600`.
- `OAuthClientProvider` is constructed from: `server_url` (= `self.url` base), an
  `OAuthClientMetadata` (redirect_uris incl. the ephemeral callback, requested scopes),
  the `FileTokenStorage`, and the `redirect_handler`/`callback_handler` callables.

</code_context>

<specifics>
## Specific Ideas

- "First invocation opens a browser for login; subsequent invocations proceed without
  interaction" — the SC#1 UX bar. Pattern-A persistence is what makes this true.
- Keep the SDK doing the OAuth heavy lifting; Phase 69's bespoke code is only:
  `FileTokenStorage`, the two browser/loopback callables, the `auth=` wiring, the opt-in
  switch, and the confused-deputy integration test.

</specifics>

<deferred>
## Deferred Ideas

- **`agent-brain mcp login` command** — an explicit, non-interactive-friendly pre-warm that
  runs the dance once and populates the token cache (useful for CI / headless setup, and for
  decoupling "log in" from "run a tool"). Out of scope for OAUTH-07; candidate for a future
  CLI-UX phase.
- **CIMD client registration** (`client_metadata_url`) as an alternative to DCR — viable once
  there's a hosted client-metadata document; revisit if/when the CLI gains a stable HTTPS home.
- Split AS/RS, Keycloak JWKS, introspection/revocation, full E2E suite → **Phase 70** (already
  roadmapped, not deferred-loose).

</deferred>

---

*Phase: 69-mcphttpbackend-client-side-oauth-dance*
*Context gathered: 2026-06-16*
