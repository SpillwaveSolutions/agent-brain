# Requirements: Agent Brain — v10.2 MCP v2

**Defined:** 2026-06-02
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Source design:** `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11, §15.1
**Scope doc:** `docs/roadmaps/mcp/v2-subscriptions-and-resources.md`
**Umbrella issue:** [#186](https://github.com/SpillwaveSolutions/agent-brain/issues/186)

## v1 Requirements

Requirements for v10.2 MCP v2 — Subscriptions, HTTP Transport, & Tool Completion. Each maps to a roadmap phase.

### Resource Subscriptions (SUB)

- [ ] **SUB-01**: Client can call `resources/subscribe` on a `job://<id>` resource and receive `notifications/resources/updated` events at 1s cadence while the job is active
- [ ] **SUB-02**: Client can subscribe to `corpus://status` and receive update notifications at 30s cadence
- [ ] **SUB-03**: Client can subscribe to `corpus://folders` and receive watcher-driven update notifications when indexed folders change
- [ ] **SUB-04**: Server emits `notifications/resources/updated` messages conforming to the current MCP spec, including resource URI and revision metadata
- [ ] **SUB-05**: Server tracks per-client subscriptions and cleans up subscriptions on client disconnect

### Deferred URI Schemes (URI)

- [x] **URI-01**: Client can read `chunk://<chunk_id>` resources via MCP `resources/read` (requires new `GET /query/chunk/{id}` server endpoint with O(1) lookup) — shipped 2026-06-03 in Plan 51-02
- [x] **URI-02**: Client can read `graph-entity://<type>/<id>` resources via MCP `resources/read` (requires new `GET /graph/entity/{type}/{id}` server endpoint) — shipped 2026-06-03 in Plan 51-02
- [x] **URI-03**: Client can read `job://<job_id>` resources via MCP `resources/read` (uses existing `GET /index/jobs/{id}` endpoint) — shipped 2026-06-03 in Plan 51-01
- [x] **URI-04**: Client can read `file://<abs-path>` resources gated by indexed roots and MCP `roots/list` sandboxing — shipped 2026-06-03 in Plan 51-03
- [ ] **URI-05**: Server responds to MCP `resources/templates/list` with templates for `chunk://`, `graph-entity://`, `job://`, and `file://` schemes

### Streamable HTTP Transport (HTTP)

- [ ] **HTTP-01**: Operator can run `agent-brain-mcp --transport http` to start the MCP server over Streamable HTTP
- [ ] **HTTP-02**: Streamable HTTP transport binds loopback only (127.0.0.1); v2 ships no MCP authentication (auth is reserved for v4)
- [ ] **HTTP-03**: Stdio transport continues to work alongside HTTP; transport selection is controlled by the `--transport` flag with no silent fallback

### Tool Completion (TOOL)

- [ ] **TOOL-01**: Client can call `explain_result` and receive provenance and scoring breakdown for a query result
- [ ] **TOOL-02**: Client can call `add_documents` with a path list to start an indexing job and receive the job id
- [ ] **TOOL-03**: Client can call `inject_documents` with an enrichment-script path and a folder path to start an injection-aware indexing job
- [ ] **TOOL-04**: Client can call `wait_for_job` to block until job completion; while the job runs, `wait_for_job` emits `notifications/progress` at least every 2s
- [ ] **TOOL-05**: Client can call `list_folders` and receive the list of indexed folders with chunk counts and last-indexed metadata
- [ ] **TOOL-06**: Client can call `remove_folder` with a folder path to remove all indexed chunks for that folder
- [ ] **TOOL-07**: Client can call `cache_status` and receive embedding-cache statistics
- [ ] **TOOL-08**: Client can call `clear_cache` to clear the embedding cache
- [ ] **TOOL-09**: Client can call `list_file_types` and receive available file-type presets

### Validation & Quality (VAL)

- [ ] **VAL-01**: All 16 MCP tools (7 from v1 + 9 from v2) covered by parameterized contract tests verified against the official MCP SDK
- [ ] **VAL-02**: Resource subscriptions tested end-to-end against the official MCP SDK, including subscribe / unsubscribe / disconnect cleanup
- [ ] **VAL-03**: Streamable HTTP transport tested via the official MCP SDK HTTP client
- [ ] **VAL-04**: New MCP packages folded into root `task before-push` and `task pr-qa-gate` (closes DR-5 from v1 design)
- [x] **VAL-05**: Own v2 design doc filed at `docs/plans/2026-06-02-mcp-v2-subscriptions.md` — **Complete in Phase 50** (commit `a94d9d5`)

## v2 Requirements (Deferred to v10.3 / MCP v3)

### CLI-via-MCP (CLI-MCP)

- **CLIMCP-01**: `agent-brain` CLI can speak MCP over its `McpHttpBackend` against a remote Agent Brain instance
- **CLIMCP-02**: Framework adapters in scope: OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, Autogen

### Remote Auth (deferred to v4)

- **OAUTH-01**: OAuth 2.1 Protected Resource Metadata
- **OAUTH-02**: OAuth 2.1 Dynamic Client Registration
- **OAUTH-03**: OAuth 2.1 Resource Indicators
- **OAUTH-04**: Optional DPoP support

## Out of Scope

Explicitly excluded from v10.2. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| MCP CLI-via-MCP and framework matrix | Deferred to v3 (#187); requires v2's HTTP transport to land first |
| OAuth 2.1 for remote MCP instances | Deferred to v4 (#188); requires v3's `McpHttpBackend` |
| MCP sampling / completion (LLM-in-the-server) | Advanced pattern not needed for tool/resource/subscription completeness |
| MCP plugin auto-registration | Requires manifest design; deferred to a follow-up milestone |
| MCP authentication on Streamable HTTP transport | v2 is loopback-only by design; auth ships in v4 with OAuth 2.1 |
| Multi-instance / remote MCP federation | Out of scope for v2; tracked separately as #157 |
| Bearer-token API key auth on FastAPI endpoints (#179) | Separate workstream from MCP; tracked under its own PR by Jeremy |
| Reviving v9.6.0 phases 47–49 (Codex/OpenCode/Gemini parity) | Deferred — re-evaluate during v3 framework matrix work |

## Traceability

Phase mapping for v10.2. Phase numbering continues sequentially from v9.6.0 (last phase: 49 deferred). v10.0.x and v10.1.x patch trains were not formally phase-numbered.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SUB-01 | Phase 52 | Pending |
| SUB-02 | Phase 52 | Pending |
| SUB-03 | Phase 52 | Pending |
| SUB-04 | Phase 52 | Pending |
| SUB-05 | Phase 52 | Pending |
| URI-01 | Phase 51 | Complete (2026-06-03, Plan 51-02) |
| URI-02 | Phase 51 | Complete (2026-06-03, Plan 51-02) |
| URI-03 | Phase 51 | Complete (2026-06-03, Plan 51-01) |
| URI-04 | Phase 51 | Complete (2026-06-03, Plan 51-03) |
| URI-05 | Phase 51 | Pending |
| HTTP-01 | Phase 53 | Pending |
| HTTP-02 | Phase 53 | Pending |
| HTTP-03 | Phase 53 | Pending |
| TOOL-01 | Phase 54 | Pending |
| TOOL-02 | Phase 54 | Pending |
| TOOL-03 | Phase 54 | Pending |
| TOOL-04 | Phase 54 | Pending |
| TOOL-05 | Phase 54 | Pending |
| TOOL-06 | Phase 54 | Pending |
| TOOL-07 | Phase 54 | Pending |
| TOOL-08 | Phase 54 | Pending |
| TOOL-09 | Phase 54 | Pending |
| VAL-01 | Phase 55 | Pending |
| VAL-02 | Phase 55 | Pending |
| VAL-03 | Phase 55 | Pending |
| VAL-04 | Phase 55 | Pending |
| VAL-05 | Phase 50 | ✓ Complete (2026-06-03) |

**Notes on phase assignment:**
- **Phase 50 (server-side endpoint prep)** has no requirement IDs directly assigned for endpoint work — the new endpoints (`GET /query/chunk/{id}`, `GET /graph/entity/{type}/{id}`) and the `roots/list` sandbox design are *prerequisites* for URI-01, URI-02, and URI-04 (which land in Phase 51). VAL-05 (file v2 design doc) is the one named requirement assigned to Phase 50 so the doc lands before MCP-layer implementation.
- **Phase 53 (Streamable HTTP transport)** is independent of Phase 52 (Resource subscriptions) and can be executed in parallel.
- **Phase 54 (TOOL-04 `wait_for_job` with progress notifications)** depends on the notification infrastructure built in Phase 52; the other 8 tools in Phase 54 do not have that dependency but ship together for cohesion.
- **Phase 55** must be last — VAL-04 (`task before-push` integration) requires all packages to be in scope.

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27 ✓
- Unmapped: 0 ✓
- Double-mapped: 0 ✓

---
*Requirements defined: 2026-06-02*
*Last updated: 2026-06-02 — traceability populated by gsd-roadmapper (Phases 50-55)*
*Previous milestone requirements (v9.6.0) archived at `.planning/milestones/v9.6.0-REQUIREMENTS.md`*
