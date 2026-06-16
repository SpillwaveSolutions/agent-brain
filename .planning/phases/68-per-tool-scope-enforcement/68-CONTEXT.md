# Phase 68: Per-Tool Scope Enforcement - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning

> Captured in `--auto` mode. Phase 68's decisions are almost entirely pre-locked by the
> APPROVED OAuth design doc (`docs/plans/2026-06-14-mcp-v4-oauth-design.md` §"Scope-to-Tool
> Mapping", §"Threat Model → Risk 4", §"Insufficient Scope Response"), REQUIREMENTS.md
> (OAUTH-06), the ROADMAP Phase-68 success criteria, and the seam Phase 67 left
> (`RequireAuthMiddleware(..., required_scopes=[])` with a "Phase 68 fills this" comment, and
> claims reachable at `request.state.auth`). CONTEXT transcribes those locks, resolves the
> Phase-68-specific gray areas (where the scope SOT lives, where enforcement happens, how the
> drift guard fails, and the two registry tools the design table doesn't name), and lists the
> canonical refs. No genuinely open human-decision items remain — the design-doc security gate
> cleared in Phase 65.

<domain>
## Phase Boundary

Make **every MCP tool enforce exactly the OAuth scope it requires**. A valid token with an
insufficient scope returns **HTTP 403** (`insufficient_scope`) — distinct from the 401 a
missing/invalid token gets (Phase 67). The scope-to-tool mapping is a **single source of
truth** co-located with the tool registry, protected by an **import-time drift guard**.

Phase 68 delivers exactly one requirement (OAUTH-06).

**ROADMAP Phase-68 success criteria (the acceptance gate):**
1. An `agent-brain:read`-only token can call the read tools (`search_documents`,
   `explain_result`, `list_folders`, `cache_status`, `list_jobs`, `get_job`,
   `list_file_types`, `get_corpus_status`) and succeeds.
2. An `agent-brain:read`-only token calling an `agent-brain:index` tool (`index_folder`,
   `add_documents`, `inject_documents`, `wait_for_job`) → **HTTP 403** with
   `WWW-Authenticate: Bearer error="insufficient_scope"` (NOT 401).
3. An `agent-brain:read`-only token calling an `agent-brain:admin` tool (`cancel_job`,
   `remove_folder`, `clear_cache`) → **HTTP 403** `insufficient_scope`.
4. The scope-to-tool mapping is a single source of truth (`_tool_matrix.py`-style / the
   `TOOL_REGISTRY`); a **drift guard at import time** detects any registered tool without a
   scope assignment.

**Explicitly OUT of scope for Phase 68** (belongs to Phases 69-70 / done already):
- Token validation (sig/exp/iss/aud), `RequireAuthMiddleware`, 401 path — done in Phase 67.
- `McpHttpBackend` client-side OAuth dance / `FileTokenStorage` — Phase 69 (OAUTH-07).
- Split AS/RS, JWKS verifier swap, introspection/revocation, ≥90% coverage gate — Phase 70.
- Adding/removing tools or changing tool behavior — only scope assignment + enforcement here.

</domain>

<decisions>
## Implementation Decisions

### Scope SOT location + representation (OAUTH-06 SC#4)
- **Add a `TOOL_SCOPE_REQUIREMENTS: dict[str, str]` mapping co-located with `TOOL_REGISTRY`**
  in `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` — the runtime registry IS the SOT
  (the design doc says "co-located with `_tool_matrix.py`"; the live registry is
  `TOOL_REGISTRY`). Keyed by tool name → one of the 4 scopes. (Adding a `scope` field to
  `ToolSpec` is an acceptable alternative — Claude's discretion; whichever keeps the drift
  guard simplest. Note `ToolSpec` uses `__slots__`, so a new field means adding to `__slots__`
  + `__init__`.)
- **The 4 locked scopes** (Phase 65/66 lock, advertised in PRM/OASM already):
  `agent-brain:read`, `agent-brain:index`, `agent-brain:admin`, `agent-brain:subscribe`.

### Scope-to-tool assignment (from design doc Scope Table — LOCKED)
- **`agent-brain:read`** → `search_documents`, `explain_result`, `get_corpus_status`,
  `cache_status`, `list_folders`, `list_file_types`, `list_jobs`, `get_job` — plus all MCP
  resource reads (`corpus://`, `job://`) and all registered prompts.
- **`agent-brain:index`** → `index_folder`, `add_documents`, `inject_documents`, `wait_for_job`.
- **`agent-brain:admin`** → `cancel_job`, `remove_folder`, `clear_cache`.
- **`agent-brain:subscribe`** → the subscription channels (`corpus://status`,
  `corpus://folders`, `job://<job_id>` subscriptions — SUB-01..05 machinery).

### Two registry tools the design table does NOT name (must be assigned — drift guard forces it)
- The live `TOOL_REGISTRY` contains 16 tools; the design Scope Table names all but two:
  - **`query_count`** → `agent-brain:read` (read-only count of indexed docs).
  - **`server_health`** → `agent-brain:read` (read-only health/status; mirrors
    `get_corpus_status`). (If research finds `server_health` should be reachable
    unauthenticated like `/healthz`, flag it — but the default is `agent-brain:read`, since it
    is a *tool* call on the authed `/mcp` path, not the public `/healthz` route.)
- Note the naming mismatch to resolve during planning: the design Scope Table writes
  `get_corpus_status` while the registry tool is `server_health` (+ `query_count`). Planner
  must reconcile names against the actual `TOOL_REGISTRY` keys — the registry keys win.

### Enforcement point (design Risk 4 — LOCKED: dispatch layer, not middleware)
- **Enforce per-tool scope inside `server.py::call_tool`** (the MCP low-level dispatch handler,
  currently `TOOL_REGISTRY.get(name)` → `spec.handler(...)` at ~line 276-315) via a
  `require_scope(required, token_scopes)` check BEFORE the handler runs. Phase 67's
  `RequireAuthMiddleware` only proves "is authenticated" — per-tool scope MUST be checked
  where the tool name is known.
- **Apply the same guard to resource reads** (`read_resource` / parameterized `corpus://`,
  `job://` handlers → `agent-brain:read`) and **subscription requests**
  (→ `agent-brain:subscribe`).
- **Reading the token's scopes is a RESEARCH ITEM:** the scopes come from Phase 67's
  `BearerAuthBackend` (which populates the authenticated user/scopes in the ASGI/SDK auth
  context). The exact accessor the low-level MCP `call_tool` handler uses to reach the current
  request's scopes (e.g. an `mcp.server.auth` context var / `get_access_token()` / the request
  context captured at handler-invocation, cf. server.py:725) MUST be confirmed by the
  researcher before planning the guard.

### Import-time drift guard (design-mandated — fail loud, not test-only)
- **At module import time** (`tools/__init__.py`), after both `TOOL_REGISTRY` and
  `TOOL_SCOPE_REQUIREMENTS` are defined, raise **`RuntimeError` naming the unassigned
  tool(s)** if any `TOOL_REGISTRY` key has no scope entry. The server MUST refuse to start on
  drift — relying only on a test is insufficient (tests may not run between commit and deploy).
- **Also ship a test** asserting (a) every registry tool has a scope, (b) every scope value is
  one of the 4 valid scopes, (c) the import-time guard actually raises when a tool is removed
  from the map.

### Insufficient-scope response shape (design §"Insufficient Scope Response" — LOCKED)
- On scope failure return:
  ```
  HTTP 403 Forbidden
  WWW-Authenticate: Bearer error="insufficient_scope",
                           scope="<REQUIRED scope, e.g. agent-brain:admin>",
                           resource_metadata="<PRM url>"
  ```
- The `scope` field names the **REQUIRED** scope (not the token's). `resource_metadata` is the
  PRM URL (same value Phase 67's middleware uses) so the client can re-discover the AS and
  request a higher scope (step-up). **MUST be 403, never 401.**
- Reconcile with how the MCP dispatch layer surfaces an HTTP 403 + header: a low-level tool
  handler returns MCP content/errors, not raw HTTP. The researcher MUST determine whether the
  403+WWW-Authenticate is emitted by raising an SDK auth error that the RS middleware/SDK
  translates to the HTTP response, vs. an MCP-level error mapping. Honor the SDK's own
  `insufficient_scope` mechanism if one exists (mcp 1.27.2 `RequireAuthMiddleware` supports
  `required_scopes` — investigate whether per-route/per-call required-scope plumbing can be
  reused instead of hand-rolling).

### Mode gating (backward-compatible)
- **Scope enforcement engages ONLY when `AGENT_BRAIN_AUTH=oauth`.** In `none`/`basic` modes
  there are no token scopes, so dispatch is unchanged — no regression to the loopback/LAN
  trust model. (The 824-test suite from Phase 67 must stay green.)

### Claude's Discretion
- `TOOL_SCOPE_REQUIREMENTS` dict vs a `scope` field on `ToolSpec` (slots) — either, pick the
  one that makes the import-time drift guard cleanest.
- Exact name/signature of the `require_scope()` helper and where it lives (a new
  `oauth/scopes.py` vs inline in `tools/__init__.py` / `server.py`).
- Whether to reuse the SDK `RequireAuthMiddleware(required_scopes=...)` per-call plumbing or
  hand-roll the dispatch-layer check (research-informed).
- The `server_health`-unauthenticated question, pending research (default: `agent-brain:read`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing Phase 68.**

### Governing design doc (READ FIRST — approved, human-signed-off 2026-06-14)
- `docs/plans/2026-06-14-mcp-v4-oauth-design.md`:
  - §"Scope-to-Tool Mapping" — the 4-scope × 16-tool table (the locked assignment), the
    single-source-of-truth + **import-time drift guard** mandate, and the
    §"Insufficient Scope Response" exact 403 + `WWW-Authenticate` header shape.
  - §"Threat Model → Risk 4: Per-Tool Scope Escalation" + §"Security Review Sign-Off → Risk 4"
    — why dispatch-layer `require_scope()` is mandatory and why 403≠401.

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — **OAUTH-06** (per-tool scope enforcement, 4 scopes → all tools,
  single SOT, 403 on insufficient scope).
- `.planning/ROADMAP.md` — Phase 68 goal + 4 success criteria (the acceptance gate). Note
  Phase 70 depends on Phase 68 (scope enforcement complete before split-AS integration tests).

### Prior phase context (the seam Phase 68 fills)
- `.planning/phases/67-co-located-as-rs-middleware/67-CONTEXT.md` — the RS verifier +
  `RequireAuthMiddleware` + `BearerAuthBackend` stack; Phase 67 left `required_scopes=[]` with
  an explicit "Phase 68 fills this" comment and kept `request.state.auth` claims reachable.
- `.planning/phases/67-co-located-as-rs-middleware/67-04-SUMMARY.md` — `LocalRs256Verifier`
  returns the SDK `AccessToken` (which carries `scopes`); the wiring in `http.py`.

### Specs (re-verify at authoring time via context7/WebFetch)
- **MCP Authorization 2025-11-25** — the auth profile; whether SEP-1880 per-tool scope
  enforcement has landed (design doc records Agent Brain uses `scope_guard`/`require_scope`,
  NOT SEP-1880, since SEP-1880 is an open proposal not in the spec).
- **RFC 6750** Bearer Token Usage — `WWW-Authenticate` `error="insufficient_scope"` format.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` — `TOOL_REGISTRY: dict[str, ToolSpec]`
  (the runtime tool SOT, 16 tools) + the `ToolSpec` class (`__slots__`: name, description,
  handler, input_model, output_model, annotations, emits_progress). Add
  `TOOL_SCOPE_REQUIREMENTS` here (or a `scope` slot on `ToolSpec`) + the import-time guard.
- `agent-brain-mcp/agent_brain_mcp/server.py :: call_tool` (~line 276-315) — the dispatch
  point: `spec = TOOL_REGISTRY.get(name)` → `spec.handler(...)`. The `require_scope()` check
  slots in here, before dispatch. Resource reads (`read_resource`, ~line 360-408) +
  subscription handlers are the other enforcement points. `server.py:725` captures the
  request context at handler-invocation — likely where token scopes are reachable.
- `agent-brain-mcp/agent_brain_mcp/oauth/verifier.py` — `LocalRs256Verifier` produces the SDK
  `AccessToken` carrying `scopes`; Phase 68 consumes those scopes.
- `agent-brain-mcp/agent_brain_mcp/http.py` — Phase 67 `RequireAuthMiddleware(...,
  required_scopes=[])` on the `/mcp` Mount; the PRM URL (`resource_metadata`) used in the 401
  is the same value the 403 must echo. mcp 1.27.2 `RequireAuthMiddleware` accepts
  `required_scopes` — investigate reuse.
- `agent-brain-mcp/tests/contract/_tool_matrix.py` — an existing contract-test tool matrix
  fixture; align the scope SOT/tests with it (and reconcile any tool-name drift).

### Established Patterns
- Tools are registered declaratively in `TOOL_REGISTRY` (name → `ToolSpec`); dispatch is
  centralized in `server.py::call_tool`. A single dispatch chokepoint makes one
  `require_scope()` call cover all tools.
- Phase 67 mode gating: OAuth behavior engages only when `AGENT_BRAIN_AUTH=oauth`; `none`/
  `basic` paths are untouched. Phase 68 follows the same gate.
- Import-time validation precedent: Phase 66/67 `check_auth_startup_gate()` exits on
  misconfig at boot — the drift guard is the same "fail loud at startup" philosophy.

### Integration Points
- Phase 68 consumes Phase 67's `AccessToken.scopes` at the `server.py` dispatch layer and
  replaces the `required_scopes=[]` placeholder semantics with per-tool enforcement.
- The scope list MUST match what PRM/OASM already advertise (the 4 scopes from Phase 66) — a
  single conceptual SOT across discovery (Phase 66) and enforcement (Phase 68).
- Phase 70 (split AS/RS) swaps the verifier but relies on the same `scopes` claim shape —
  keep the scope-extraction independent of the verifier implementation.

</code_context>

<specifics>
## Specific Ideas

- "One chokepoint, fail loud." The whole phase is: one scope map (SOT), one `require_scope()`
  check at the single `call_tool` dispatch point (+ resource/subscribe paths), and one
  import-time `RuntimeError` that stops the server if any tool is unscoped. Small surface,
  high correctness bar.
- The dominant failure mode (design Risk 4) is a middleware "is-authenticated" check that
  silently lets a `read`-scope token call an `admin` tool — invisible to smoke tests that use
  a full-scope admin token. The acceptance tests MUST use minimal-scope tokens against
  privileged tools (the ROADMAP SC#2/#3 cases) — that is the whole point.
- 403 `insufficient_scope` (NOT 401) is non-negotiable: 401 triggers re-auth, 403 triggers
  step-up scope upgrade. Wrong status breaks client recovery.

</specifics>

<deferred>
## Deferred Ideas

- `McpHttpBackend` client-side handling of the 403 step-up / scope-upgrade flow — Phase 69
  territory (OAUTH-07 covers the 401 dance; 403 step-up UX, if needed, rides with it or is a
  later refinement).
- SEP-1880 standardized per-tool scope enforcement — not in the 2025-11-25 spec; if it lands
  in a future revision it may replace the `require_scope` approach (design doc Deferred Items).
- Split AS/RS scope validation against an external IdP's scope claims (Keycloak) — Phase 70.
- Dynamic/per-folder or per-resource fine-grained scopes beyond the 4 coarse scopes — not in
  scope; the 4-scope model is locked.

</deferred>

---

*Phase: 68-per-tool-scope-enforcement*
*Context gathered: 2026-06-16*
