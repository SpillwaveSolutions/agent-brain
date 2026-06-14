# Agent Brain Roadmap

**Created:** 2026-02-07
**Last updated:** 2026-06-14 — v10.4 MCP v4: OAuth 2.1 + GraphRAG Stability (Phases 64-70); roadmap created
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Active milestone:** v10.4 — MCP v4: OAuth 2.1 + GraphRAG Stability (Phase 64-70)

## Milestones

- ✅ **v3.0 Advanced RAG** — Phases 1-4 (shipped 2026-02-10)
- ✅ **v6.0 PostgreSQL Backend** — Phases 5-10 (shipped 2026-02-13)
- ✅ **v6.0.4 Plugin & Install Fixes** — Phase 11 (shipped 2026-02-22)
- ✅ **v7.0 Index Management & Content Pipeline** — Phases 12-14 (shipped 2026-03-05)
- ✅ **v8.0 Performance & Developer Experience** — Phases 15-25 (shipped 2026-03-15)
- ✅ **v9.0 Multi-Runtime Support** — Multi-runtime converter system (shipped 2026-03-16)
- ✅ **v9.1.0 Generic Skills-Based Runtime Portability** — Phases 26-28 (shipped 2026-03-16)
- ✅ **v9.4.0 Documentation Accuracy Audit & Reliability Closure** — Phases 29-33, 36-40 (shipped 2026-03-20)
- ✅ **v9.3.0 LangExtract + Config Spec** — Phases 34-35 (shipped 2026-03-22)
- ✅ **v9.5.0 Config Validation & Language Support** — Phases 41-45 (shipped 2026-03-31)
- ⏸ **v9.6.0 Runtime Support Parity & Backlog Cleanup** — Phases 46-49 (parked; deferred to post-MCP. Archived: [v9.6.0-ROADMAP.md](milestones/v9.6.0-ROADMAP.md))
- ✅ **v10.0.x Patch Train** — bugfixes (shipped 2026-05-25 → 2026-05-27)
- ✅ **v10.1.0 MCP v1** — UDS transport + 7-tool stdio MCP + CLI dual transport (shipped 2026-05-30)
- ✅ **v10.1.2 MCP package rename + standalone user guide** — `agent-brain-mcp` PyPI distribution (shipped 2026-06-01)
- ✅ **v10.2 MCP v2 — Subscriptions, HTTP Transport, & Tool Completion** — Phases 50-55 (shipped 2026-06-03; 24/24 plans, 27/27 requirements). Archived: [v10.2-ROADMAP.md](milestones/v10.2-ROADMAP.md) | [v10.2-REQUIREMENTS.md](milestones/v10.2-REQUIREMENTS.md)
- ✅ **v10.3 MCP v3 — CLI-via-MCP + Framework Matrix** — Phases 56-63 (shipped 2026-06-14; 24/24 plans, 23/23 requirements). Archived: [v10.3-ROADMAP.md](milestones/v10.3-ROADMAP.md) | [v10.3-REQUIREMENTS.md](milestones/v10.3-REQUIREMENTS.md)
- 🔄 **v10.4 MCP v4 — OAuth 2.1 + GraphRAG Stability** — Phases 64-70 (in progress; 16 requirements)

## Phases

<details>
<summary>✅ v10.2 MCP v2 (Phases 50-55) — SHIPPED 2026-06-03</summary>

- [x] Phase 50: Server endpoint prep + v2 design doc (4/4 plans) — completed 2026-06-03
- [x] Phase 51: URI schemes + templates (4/4 plans) — completed 2026-06-03
- [x] Phase 52: Resource subscriptions (4/4 plans) — completed 2026-06-03
- [x] Phase 53: Streamable HTTP transport (3/3 plans) — completed 2026-06-03
- [x] Phase 54: 9 remaining MCP tools (4/4 plans) — completed 2026-06-03
- [x] Phase 55: Validation, contract tests & QA gate (5/5 plans) — completed 2026-06-03

Full details: [milestones/v10.2-ROADMAP.md](milestones/v10.2-ROADMAP.md)

</details>

<details>
<summary>✅ v10.3 MCP v3 — CLI-via-MCP + Framework Matrix (Phases 56-63) — SHIPPED 2026-06-14</summary>

**Goal:** Make the CLI a reference MCP client and validate the MCP server against the major LLM agent frameworks (OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Autogen, Mastra, Vercel AI SDK).

- [x] Phase 56: Design doc + CLI backend skeleton (3/3 plans) — completed 2026-06-06
- [x] Phase 57: CLI transport selector + byte-identical equivalence (3/3 plans) — completed 2026-06-06
- [x] Phase 58: Runtime discovery + helper commands (3/3 plans) — completed 2026-06-07
- [x] Phase 59: CLI prompts + resources commands (3/3 plans) — completed 2026-06-08
- [x] Phase 60: Subprocess hygiene + 1000-invocation orphan test (3/3 plans) — completed 2026-06-09
- [x] Phase 61: Python framework adapter matrix (4/4 plans) — completed 2026-06-11
- [x] Phase 62: TypeScript framework adapter matrix (2/2 plans) — completed 2026-06-12
- [x] Phase 63: Tooling + docs + integration page (3/3 plans) — completed 2026-06-12

Post-ship: CLI-MCP-04 DoD-anchor env-forwarding gap found by milestone audit and fixed on-branch (`fix(57)`).

Full details: [milestones/v10.3-ROADMAP.md](milestones/v10.3-ROADMAP.md) | Audit: [milestones/v10.3-MILESTONE-AUDIT.md](milestones/v10.3-MILESTONE-AUDIT.md)

</details>

<details>
<summary>🔄 v10.4 MCP v4 — OAuth 2.1 + GraphRAG Stability (Phases 64-70) — IN PROGRESS</summary>

**Goal:** Make Agent Brain safe to run remotely (OAuth 2.1 on the Streamable HTTP transport) and stabilize the GraphRAG/kuzu path. Bugs first (#178 kuzu SIGSEGV, #184 snapshot scope-gap, #194 subscriptions debug endpoint), then full OAuth 2.1 (#188) — design-doc-gated, design first, then incremental server-side build, client dance, split AS topology, and integration tests with a 90% oauth/ coverage gate.

- [ ] **Phase 64: GraphRAG Stability + Subscriptions Debug Endpoint** — No hard crashes under sustained GraphRAG indexing; graceful degradation and operator restore tools; health counters match reality; `/mcp/subscriptions` debug endpoint live
- [ ] **Phase 65: OAuth Design Doc + Security Review Gate** — Approved v4 design doc on disk, independent security review signed off, implementation blocked until gate passes
- [ ] **Phase 66: OAuth Settings Foundation + PRM/OASM Public Endpoints** — `AGENT_BRAIN_AUTH` toggle wired; well-known discovery endpoints return 200 without a token; `basic` mode formalized as the LAN bridge
- [ ] **Phase 67: Co-Located AS + RS Middleware** — Authorization code flow with PKCE S256 works end-to-end; tokens are issued, verified, and scoped; resource indicators bind `aud` to the canonical resource URI; client registration (CIMD/static) works
- [ ] **Phase 68: Per-Tool Scope Enforcement** — All 16 MCP tools enforce the correct scope; insufficient-scope returns 403 not 401; `_tool_matrix.py` SOT owns the scope map
- [ ] **Phase 69: McpHttpBackend Client-Side OAuth Dance** — `McpHttpBackend` handles the 401+WWW-Authenticate challenge, completes the PKCE dance via `OAuthClientProvider`, persists tokens via `FileTokenStorage` so Pattern A per-call invocations reuse the token
- [ ] **Phase 70: Split AS/RS + Keycloak-in-CI + Integration Tests** — Split topology JWKS verification works against Keycloak; token introspection/revocation endpoints operational; full E2E challenge-to-authorized-tool-call test passes; `agent_brain_mcp/oauth/` module at ≥90% coverage

</details>

## Phase Details

### Phase 64: GraphRAG Stability + Subscriptions Debug Endpoint
**Goal**: The GraphRAG/kuzu path never hard-crashes the server or silently under-reports; operators have tools to diagnose and restore; the subscriptions debug endpoint closes the v10.2 deferred item.
**Depends on**: Nothing (bugs-first, no new dependencies)
**Requirements**: GSTAB-01, GSTAB-02, GSTAB-03, HOUSE-01
**Success Criteria** (what must be TRUE):
  1. Operator can run a sustained GraphRAG indexing workload with `graphrag.store_type: kuzu` — if kuzu hits a native failure, the indexing job surfaces an error with a clear message and the server process continues running (no SIGSEGV process death); the `simple` store remains the documented fallback
  2. `agent-brain graph restore-from-snapshot [--snapshot PATH] [--dry-run]` replays the latest kuzu snapshot from disk; `agent-brain doctor` surfaces the stale-graph condition as a warning instead of reporting `OK`
  3. `GET /health/status` graph `entity_count` and `relationship_count` match what `SELECT COUNT(*)` returns from kuzu at query time — the `0 / 100` vs actual `5677 / 4366` class of discrepancy is gone
  4. `GET /mcp/subscriptions` returns 200 with current active subscription state (session IDs, subscribed URIs, uptime) without requiring a token; operator can `curl` it for live diagnosis without restarting the server
**Plans**: TBD

### Phase 65: OAuth Design Doc + Security Review Gate
**Goal**: A fully-specified, independently-reviewed design document exists on disk that governs all implementation decisions for Phases 66-70 — no OAuth code lands until this gate passes.
**Depends on**: Phase 64 (bugs resolved first, as scoped)
**Requirements**: OAUTH-01
**Success Criteria** (what must be TRUE):
  1. `docs/plans/2026-06-14-mcp-v4-oauth-design.md` exists, includes the threat model, AS/RS/public-route boundary diagram, token termination data flow (client OAuth token terminates at MCP boundary; MCP-to-REST leg keeps `AGENT_BRAIN_API_KEY`), scope-to-tool mapping table, canonical resource URI contract (`AGENT_BRAIN_OAUTH_RESOURCE`), DCR/CIMD policy decision, and explicit DPoP deferral rationale
  2. Design doc cites the verified live MCP Authorization spec version (and explicitly acknowledges whether the 2026-07-28 RC has landed and what it changes)
  3. An independent security reviewer has signed off on the design doc (documented in the doc's sign-off section) before any Phase 66+ implementation code is committed
  4. The design doc records the explicit decision on CIMD-vs-DCR registration and confirms DPoP can be deferred without violating any current-spec MUST
**Plans**: TBD

### Phase 66: OAuth Settings Foundation + PRM/OASM Public Endpoints
**Goal**: The OAuth discovery root is live — unauthenticated clients can find the authorization server and learn the PKCE requirement; the `basic` mode is formalized as the LAN bridge; all three auth-mode toggle paths are wired at the settings layer.
**Depends on**: Phase 65 (design doc approved)
**Requirements**: OAUTH-02, OAUTH-03, OAUTH-09
**Success Criteria** (what must be TRUE):
  1. `curl /.well-known/oauth-protected-resource` (no Authorization header) returns HTTP 200 with a valid RFC 9728 JSON document including `resource`, `authorization_servers`, and `scopes_supported` fields
  2. `curl /.well-known/oauth-authorization-server` (no Authorization header) returns HTTP 200 with a valid RFC 8414 JSON document that includes `code_challenge_methods_supported: ["S256"]` — absence of this field causes compliant MCP SDK clients to abort
  3. Both well-known endpoints return 200 even when `RequireAuthMiddleware` is wired (they are mounted outside the auth middleware scope; this is verified by an automated test before any further auth enforcement is added)
  4. `AGENT_BRAIN_AUTH=basic` formalizes the existing shared-secret Bearer path under the exclusive toggle; `none` / `basic` / `oauth` are mutually exclusive — a startup gate rejects invalid combinations and logs a clear error at boot
**Plans**: TBD

### Phase 67: Co-Located AS + RS Middleware
**Goal**: Token issuance and verification work end-to-end in a single binary — an MCP client can complete the authorization-code + PKCE dance against the co-located AS and receive a JWT that the RS validates on every subsequent call.
**Depends on**: Phase 66 (settings and discovery endpoints in place)
**Requirements**: OAUTH-04, OAUTH-05, OAUTH-08, OAUTH-10
**Success Criteria** (what must be TRUE):
  1. A compliant OAuth 2.1 client can complete the authorization-code flow with PKCE S256 against the co-located AS: `GET /authorize` issues a code, `POST /token` exchanges it for a signed JWT access token and rotating refresh token; attempts with `code_challenge_method=plain` or absent challenge are rejected with an error
  2. `RequireAuthMiddleware` returns 401 with a `WWW-Authenticate` header on requests to `/mcp` that carry no token or an expired/invalid-signature token; a valid token passes through to the MCP tool dispatch layer
  3. Every issued JWT has an `aud` claim bound to the canonical `AGENT_BRAIN_OAUTH_RESOURCE` URI (Resource Indicators, RFC 8707); the RS validates `aud` on every inbound token and rejects tokens where `aud` does not match — cross-service token reuse is prevented
  4. Client registration via CIMD (Client ID Metadata Document) and static pre-registration both work; the co-located AS fetches the `client_id` URL on CIMD registration with SSRF protection (domain allowlist)
  5. `AGENT_BRAIN_AUTH=oauth` and `AGENT_BRAIN_AUTH=basic` are mutually exclusive on the request path — an automated test proves a valid JWT fails the static-bearer check and a raw API key passes the static-bearer check, never crossing modes
**Plans**: TBD

### Phase 68: Per-Tool Scope Enforcement
**Goal**: Every MCP tool enforces exactly the scope it requires; a token with an insufficient scope returns 403 (not 401); the scope-to-tool mapping is the single source of truth co-located with `_tool_matrix.py`.
**Depends on**: Phase 67 (full token validation stack is testable)
**Requirements**: OAUTH-06
**Success Criteria** (what must be TRUE):
  1. An `agent-brain:read`-only token can call read-only tools (`search_documents`, `explain_result`, `list_folders`, `cache_status`, `list_jobs`, `get_job`, `list_file_types`, `get_corpus_status`) and receives a successful result
  2. An `agent-brain:read`-only token calling an `agent-brain:index` tool (`index_folder`, `add_documents`, `inject_documents`, `wait_for_job`) receives HTTP 403 with `WWW-Authenticate: Bearer error="insufficient_scope"` — not 401
  3. An `agent-brain:read`-only token calling an `agent-brain:admin` tool (`cancel_job`, `remove_folder`, `clear_cache`) receives HTTP 403 with `insufficient_scope`
  4. The scope-to-tool mapping is maintained as a single source of truth in `_tool_matrix.py` (or equivalent SOT) — a drift guard test at import time detects any tool added to the registry without a scope assignment
**Plans**: TBD

### Phase 69: McpHttpBackend Client-Side OAuth Dance
**Goal**: `McpHttpBackend` handles the full OAuth dance transparently — the CLI user authenticates once, tokens persist across Pattern A per-call invocations via `FileTokenStorage`, and subsequent calls reuse the cached token without re-triggering the browser redirect.
**Depends on**: Phase 67 (working AS to dance against)
**Requirements**: OAUTH-07
**Success Criteria** (what must be TRUE):
  1. `McpHttpBackend` connecting to an OAuth-protected MCP server receives a 401 + `WWW-Authenticate` challenge, transparently completes the PRM-discovery → OASM-discovery → PKCE-dance flow via the SDK `OAuthClientProvider`, and retries the original request with a valid Bearer token — from the CLI user's perspective, the first invocation opens a browser for login and subsequent invocations proceed without interaction
  2. Tokens are persisted to `FileTokenStorage` at `state_dir/mcp-oauth-tokens.json` (chmod 0o600); a second `McpHttpBackend` call (fresh Pattern A invocation) loads the cached token and does NOT re-trigger the browser dance if the token is still valid
  3. When the access token is expired but a refresh token exists, `McpHttpBackend` silently refreshes the token via `POST /token grant_type=refresh_token` and retries the original call — no user interaction required
  4. The MCP-to-REST API leg continues to use `AGENT_BRAIN_API_KEY` (static Bearer); an automated integration test asserts the outgoing REST call carries `X-API-Key: <api_key>` and does NOT carry the OAuth access token (confused-deputy prevention)
**Plans**: TBD

### Phase 70: Split AS/RS + Keycloak-in-CI + Integration Tests
**Goal**: The split AS/RS topology is validated end-to-end against Keycloak in CI; token introspection and revocation close the DoD; the full OAuth flow has a ≥90% coverage gate on `agent_brain_mcp/oauth/`.
**Depends on**: Phase 67 (middleware stack abstracted for verifier swap), Phase 68 (scope enforcement complete), Phase 69 (client dance complete)
**Requirements**: OAUTH-11, OAUTH-12
**Success Criteria** (what must be TRUE):
  1. A Keycloak-issued JWT (Keycloak ≥22, with RFC 8707 Resource Indicators enabled on the client) is accepted by the RS `JwksTokenVerifier` via cached JWKS (`PyJWKClient` with TTL + `kid`-miss on-demand refresh); the Keycloak container runs in CI on the `ubuntu-latest` runner
  2. Token introspection (RFC 7662) works for opaque-token / external-AS deployments: the RS calls the introspection endpoint and validates the returned `active: true` + `aud` claim; an introspected token with `active: false` is rejected with 401
  3. Token revocation (RFC 7009) is supported: a revoked token is rejected by the RS on next use (either via introspection or an in-memory revocation list for co-located AS)
  4. Full E2E integration test suite passes: 401 challenge → PRM discovery → OASM discovery → PKCE dance → authorized tool call → token refresh path → scope boundary (read-only token + admin tool returns 403) — all run against the official MCP SDK client
  5. `agent_brain_mcp/oauth/` module coverage is at or above 90% as reported by the standard `task before-push` coverage gate — this is the DoD coverage requirement and blocks the milestone from shipping
**Plans**: TBD

## Progress

| Phase                                                       | Milestone | Plans Complete | Status      | Completed  |
| ----------------------------------------------------------- | --------- | -------------- | ----------- | ---------- |
| 50. Server endpoint prep + v2 design doc                    | v10.2     | 4/4            | Complete    | 2026-06-03 |
| 51. URI schemes + templates                                 | v10.2     | 4/4            | Complete    | 2026-06-03 |
| 52. Resource subscriptions                                  | v10.2     | 4/4            | Complete    | 2026-06-03 |
| 53. Streamable HTTP transport                               | v10.2     | 3/3            | Complete    | 2026-06-03 |
| 54. 9 remaining MCP tools                                   | v10.2     | 4/4            | Complete    | 2026-06-03 |
| 55. Validation, contract tests & QA gate                    | v10.2     | 5/5            | Complete    | 2026-06-03 |
| 56. Design doc + CLI backend skeleton                       | v10.3     | 3/3            | Complete    | 2026-06-06 |
| 57. CLI transport selector + byte-identical equivalence     | v10.3     | 3/3            | Complete    | 2026-06-07 |
| 58. Runtime discovery + helper commands                     | v10.3     | 3/3            | Complete    | 2026-06-07 |
| 59. CLI prompts + resources commands                        | v10.3     | 3/3            | Complete    | 2026-06-09 |
| 60. Subprocess hygiene + 1000-invocation orphan test        | v10.3     | 3/3            | Complete    | 2026-06-09 |
| 61. Python framework adapter matrix                         | v10.3     | 4/4            | Complete    | 2026-06-11 |
| 62. TypeScript framework adapter matrix                     | v10.3     | 2/2            | Complete    | 2026-06-12 |
| 63. Tooling + docs + integration page                       | v10.3     | 3/3            | Complete    | 2026-06-12 |
| 64. GraphRAG stability + subscriptions debug endpoint       | v10.4     | 0/TBD          | Not started | -          |
| 65. OAuth design doc + security review gate                 | v10.4     | 0/TBD          | Not started | -          |
| 66. OAuth settings foundation + PRM/OASM public endpoints   | v10.4     | 0/TBD          | Not started | -          |
| 67. Co-located AS + RS middleware                           | v10.4     | 0/TBD          | Not started | -          |
| 68. Per-tool scope enforcement                              | v10.4     | 0/TBD          | Not started | -          |
| 69. McpHttpBackend client-side OAuth dance                  | v10.4     | 0/TBD          | Not started | -          |
| 70. Split AS/RS + Keycloak-in-CI + integration tests        | v10.4     | 0/TBD          | Not started | -          |

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-06-14 — v10.4 MCP v4: OAuth 2.1 + GraphRAG Stability roadmap created (7 phases, 64-70; 16/16 requirements mapped). Bugs first (Phase 64), then design-doc gate (Phase 65), then incremental OAuth build (Phases 66-70). Prior: v10.3 MCP v3 shipped (8 phases, 24 plans, 23/23 requirements). Milestone audit passed; CLI-MCP-04 DoD-anchor gap fixed on-branch.*
