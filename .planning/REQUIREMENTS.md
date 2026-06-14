# Requirements: Agent Brain v10.4 — MCP v4 (OAuth 2.1) + GraphRAG Stability

**Defined:** 2026-06-14
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Milestone source:** Issue [#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188) (MCP v4) · design sketch `docs/roadmaps/mcp/v4-oauth-for-remote.md` · master design `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v4 row), §15.3 · bugs [#178](https://github.com/SpillwaveSolutions/agent-brain/issues/178), [#184](https://github.com/SpillwaveSolutions/agent-brain/issues/184)
**Prereqs (already shipped):** v10.3 — `McpHttpBackend` over Streamable HTTP (the hard dependency); v10.2.1 SECURITY-01 — static Bearer/`API_KEY` auth on REST routers.
**Research:** `.planning/research/SUMMARY.md` — verified against live MCP Authorization spec **2025-11-25**. Key finding: the `mcp` Python SDK (≥1.27.2) ships the OAuth machinery on both sides (`OAuthClientProvider`, `OAuthAuthorizationServerProvider`, `TokenVerifier`/`RequireAuthMiddleware`) — this milestone wires + configures + mints JWTs, it does not build OAuth from scratch.

## v1 Requirements (this milestone)

### GraphRAG Stability (bugs first)

- [ ] **GSTAB-01**: Sustained GraphRAG indexing with `graphrag.store_type: kuzu` no longer crashes the server with SIGSEGV (#178) — eliminated at root cause OR robustly mitigated (bounded memory / batch-commit / checkpoint) with graceful degradation so a kuzu-native failure never kills the indexing job or server process. The `simple` store remains the documented fallback.
- [ ] **GSTAB-02**: Operator can replay the latest graph snapshot into kuzu when kuzu opens cleanly but the live graph is stale after an `AGENT_BRAIN_JOB_TIMEOUT` rollback (#184 bug 1), via `agent-brain graph restore-from-snapshot [--snapshot PATH] [--dry-run]` (and/or a `doctor` restore mode); `doctor` surfaces the stale-graph condition instead of reporting `OK`.
- [ ] **GSTAB-03**: `/health/status` graph `entity_count` / `relationship_count` are derived from a live kuzu COUNT at query time and match kuzu's actual contents (#184 bug 2) — no stale-counter under-reporting (the `0 / 100` vs real `5677 / 4366` discrepancy is gone).

### OAuth 2.1 — Resource Server + Co-located Authorization Server (MUST per MCP spec)

- [x] **OAUTH-01**: v4 OAuth design doc filed and **independent security review gate passed before implementation** — cites the verified live MCP authorization spec version, includes an AS/RS/public-route boundary diagram, and shows the token-termination data flow (client OAuth token terminates at the MCP boundary; the MCP→REST leg keeps `AGENT_BRAIN_API_KEY`).
- [ ] **OAUTH-02**: Protected Resource Metadata (RFC 9728) served at `/.well-known/oauth-protected-resource` (+ the path-suffixed variant), publicly reachable with NO token (returns 200) — verified by an unauthenticated `curl` before any other auth code lands.
- [ ] **OAUTH-03**: Authorization Server Metadata (RFC 8414) served at `/.well-known/oauth-authorization-server`, advertising `code_challenge_methods_supported: ["S256"]` (absence makes compliant MCP clients abort).
- [ ] **OAUTH-04**: Co-located Authorization Server issues tokens via authorization-code + PKCE (S256-only; rejects `plain`/missing challenge), mints JWTs (`PyJWT[crypto]`), and serves a JWKS endpoint — wired through the SDK `OAuthAuthorizationServerProvider`.
- [ ] **OAUTH-05**: Resource Server verifies inbound tokens (signature, `exp`/`nbf` with clock-skew leeway, `aud` == canonical resource URI), gated by `AGENT_BRAIN_AUTH=oauth` (default `none`); the well-known + `authorize`/`token` routes are excluded from the auth dependency.
- [ ] **OAUTH-06**: Per-tool scope enforcement maps the 4 scopes (`agent-brain:read` / `:index` / `:admin` / `:subscribe`) to all 16 MCP tools via a single source-of-truth (`_tool_matrix.py`-style); a valid token with an insufficient scope returns **403** (distinct from a 401 missing/invalid-token).
- [ ] **OAUTH-07**: `McpHttpBackend` handles the 401 + `WWW-Authenticate` challenge and the full OAuth dance via the SDK `OAuthClientProvider`, persisting tokens in a `FileTokenStorage` keyed to `state_dir` so per-call (Pattern A) invocations reuse the token instead of re-triggering the browser dance.
- [ ] **OAUTH-08**: Resource Indicators (RFC 8707) — the client sends `resource` in both authorization and token requests, the AS binds `aud` to the resource URI, and the RS validates it; the MCP server NEVER forwards the client's OAuth token upstream to the REST backend (confused-deputy prevention).
- [x] **OAUTH-09**: `AGENT_BRAIN_AUTH=basic` formalizes the existing shared-secret Bearer auth (SECURITY-01) under the new toggle as a LAN migration bridge; the toggle is exclusive (exactly one of `none` / `basic` / `oauth`, never double-auth).
- [ ] **OAUTH-10**: Client registration via CIMD (Client ID Metadata Documents — the spec's preferred SHOULD path) and static pre-registration; DCR (RFC 7591) optional/MAY, rate-limited + domain-allowlisted (with SSRF protection on metadata fetches) if enabled.

### OAuth 2.1 — Split AS/RS (external IdP)

- [ ] **OAUTH-11**: Split AS/RS mode — the RS verifies JWTs against an external IdP via cached JWKS (`kid`-miss on-demand refresh + TTL jitter), verified end-to-end against **Keycloak-in-CI** with RFC 8707 Resource Indicators enabled (Keycloak ≥22).
- [ ] **OAUTH-12**: Token introspection (RFC 7662) + revocation (RFC 7009) supported for opaque-token / external-AS deployments.

### Housekeeping

- [ ] **HOUSE-01**: `/mcp/subscriptions` debug endpoint exposes active subscription state for operators (#194 — deferred from v10.2 VAL-02, where disconnect-cleanup tests fell back to stderr-scraping).

## v2 Requirements (deferred to future milestone)

### Auth hardening
- **DPoP (RFC 9449)** — token binding. **Forced-deferred:** no production-grade Python DPoP library exists as of June 2026 (Authlib issue #315 open since 2021); the MCP 2025-11-25 core spec lists DPoP as optional (lives in the ext-auth extension repo). Revisit v10.5+.
- **Audit logging** — tamper-evident structured audit event per authorized call + SIEM export. Substantial; pairs with the enterprise control-plane track (#204). Its own milestone.

### Enterprise Hardening & Cloud Deployment (#200-205)
- Secrets abstraction, GCP/AWS/Azure reference deployments, Postgres lock+queue for multi-replica (#202), read/write split (#203), in-house MCP control plane (#204), DLP classification-aware redaction (#205). Parent plan `docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md`. OAuth (v10.4) is a prerequisite for the governed-MCP pieces.

### Feature backlog
- Claude-native provider (#164), batch query endpoint (#163), Rust CLI rewrite (#162), schema-versioned entity types (#160) + user-defined graph schemas RFC (#183), VS Code extension (#158), multi-repo federated search (#157), streaming updates (#156), per-source-type embeddings (#155), GraphRAG agentic workflow (#154), Voyage AI provider (#152).

### CLI polish
- Drop EOL Gemini runtime support; setup-experience audit (config wizard + `install-agent` for MCP transport + API-key auth — pairs with OAuth setup UX).

## Out of Scope

Explicit exclusions to prevent scope creep.

| Feature | Reason |
|---------|--------|
| DPoP token binding | No production Python library (June 2026); optional in the core MCP spec — defer to v10.5+ |
| Audit logging of authorized calls | Substantial standalone effort; its own milestone (pairs with #204 control plane) |
| Multi-replica / horizontal scaling (#202/#203) | Depends on moving the fcntl lock + job queue into Postgres — separate enterprise track |
| External cloud reference deployments (#200/#201) | AWS/Azure/GCP IaC + skills — separate enterprise track |
| Rust CLI rewrite (#162) | Large, no near-term forcing function; Python CLI is fit-for-purpose |
| Tool-level scope spec compliance via SEP-1880 | Still an open MCP proposal; route/middleware-layer scope mapping is the correct approach until it lands |

## Traceability

Which phases cover which requirements. Filled by roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| GSTAB-01 | Phase 64 | Pending |
| GSTAB-02 | Phase 64 | Pending |
| GSTAB-03 | Phase 64 | Pending |
| OAUTH-01 | Phase 65 | Complete |
| OAUTH-02 | Phase 66 | Pending |
| OAUTH-03 | Phase 66 | Pending |
| OAUTH-04 | Phase 67 | Pending |
| OAUTH-05 | Phase 67 | Pending |
| OAUTH-06 | Phase 68 | Pending |
| OAUTH-07 | Phase 69 | Pending |
| OAUTH-08 | Phase 67 | Pending |
| OAUTH-09 | Phase 66 | Complete |
| OAUTH-10 | Phase 67 | Pending |
| OAUTH-11 | Phase 70 | Pending |
| OAUTH-12 | Phase 70 | Pending |
| HOUSE-01 | Phase 64 | Pending |

**Coverage:**
- v1 requirements: 16 total (3 GraphRAG stability + 12 OAuth + 1 housekeeping)
- Mapped to phases: 16/16 (roadmap created 2026-06-14)
- Unmapped: 0 — all requirements covered

**Phase mapping:**
- Phase 64: GSTAB-01, GSTAB-02, GSTAB-03, HOUSE-01 (4 requirements — bugs first)
- Phase 65: OAUTH-01 (1 requirement — design doc + security review gate)
- Phase 66: OAUTH-02, OAUTH-03, OAUTH-09 (3 requirements — settings + public discovery endpoints)
- Phase 67: OAUTH-04, OAUTH-05, OAUTH-08, OAUTH-10 (4 requirements — co-located AS + RS middleware)
- Phase 68: OAUTH-06 (1 requirement — per-tool scope enforcement)
- Phase 69: OAUTH-07 (1 requirement — client-side OAuth dance)
- Phase 70: OAUTH-11, OAUTH-12 (2 requirements — split AS/RS + integration tests)

---
*Requirements defined: 2026-06-14*
*Last updated: 2026-06-14 — initial definition after research-first OAuth study; scope confirmed: full DoD (co-located + split-IdP), audit logging deferred, DPoP forced-deferred.*
