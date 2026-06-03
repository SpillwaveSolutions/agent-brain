# Agent Brain Roadmap — v10.2 MCP v2

**Created:** 2026-02-07
**Last updated:** 2026-06-02 — v10.2 MCP v2 milestone (Phases 50-55) replaces parked v9.6.0
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Active milestone:** v10.2 — MCP v2 (Subscriptions, HTTP Transport, & Tool Completion)
**Source design:** `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11, §15.1
**Scope doc:** `docs/roadmaps/mcp/v2-subscriptions-and-resources.md`
**Umbrella issue:** [#186](https://github.com/SpillwaveSolutions/agent-brain/issues/186)

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
- ✅ **v10.2 MCP v2 — Subscriptions, HTTP Transport, & Tool Completion** — Phases 50-55 (24/24 plans complete 2026-06-03; READY FOR RELEASE — awaiting `gsd-complete-milestone` + release workflow)

## Phases

- [x] **Phase 50: Server endpoint prep + v2 design doc** — File v2 design doc, add `GET /query/chunk/{id}` + `GET /graph/entity/{type}/{id}` endpoints, settle `roots/list` sandbox design (completed 2026-06-03)
- [x] **Phase 51: URI schemes + templates** — Implement `chunk://`, `graph-entity://`, `job://`, `file://` resources + `resources/templates/list` (completed 2026-06-03)
- [x] **Phase 52: Resource subscriptions** — `resources/subscribe` + per-resource polling cadence + `notifications/resources/updated` + disconnect cleanup (completed 2026-06-03)
- [x] **Phase 53: Streamable HTTP transport** — `--transport http` on `agent-brain-mcp` with loopback bind and explicit transport selection (completed 2026-06-03)
- [x] **Phase 54: 9 remaining MCP tools** — `explain_result`, `add_documents`, `inject_documents`, `wait_for_job` (with progress), `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, `list_file_types` (completed 2026-06-03)
- [x] **Phase 55: Validation, contract tests & QA gate integration** — 16-tool parameterized SDK contract tests, subscription E2E test, HTTP transport SDK test, root `task before-push` integration (completed 2026-06-03)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 50. Server endpoint prep + v2 design doc | 0/0 | Complete    | 2026-06-03 |
| 51. URI schemes + templates | 4/4 | Complete    | 2026-06-03 |
| 52. Resource subscriptions | 4/4 | Complete    | 2026-06-03 |
| 53. Streamable HTTP transport | 3/3 | Complete    | 2026-06-03 |
| 54. 9 remaining MCP tools | 0/1 | Complete    | 2026-06-03 |
| 55. Validation, contract tests & QA gate | 5/5 | Complete    | 2026-06-03 |

## Phase Details

### Phase 50: Server endpoint prep + v2 design doc
**Goal**: Server-side prerequisites for v2 are in place — new lookup endpoints exist, the sandbox design for `roots/list`-gated `file://` reads is decided, and the v2 design doc is filed before any MCP-layer code lands
**Depends on**: Nothing (first phase of milestone; v10.1.2 already shipped)
**Requirements**: VAL-05
**Prerequisites for**: URI-01 (needs `GET /query/chunk/{id}`), URI-02 (needs `GET /graph/entity/{type}/{id}`), URI-04 (needs `roots/list` sandbox design)
**Success Criteria** (what must be TRUE):
  1. `docs/plans/2026-06-XX-mcp-v2-subscriptions.md` design doc is filed and approved before MCP-layer phases begin
  2. `GET /query/chunk/{id}` returns a single chunk record with O(1) lookup behavior verifiable via curl against a running `agent-brain-serve` instance
  3. `GET /graph/entity/{type}/{id}` returns the requested entity payload (or 404) verifiable via curl against a corpus with GraphRAG enabled
  4. `roots/list` sandbox design is decided and documented — clients can enumerate which absolute paths are addressable via `file://` and which are denied
**Plans**: TBD

---

### Phase 51: URI schemes + templates
**Goal**: All four deferred URI schemes are addressable via MCP `resources/read`, and `resources/templates/list` advertises them so model clients can discover them programmatically
**Depends on**: Phase 50 (URI-01/02/04 require the new server endpoints + sandbox design)
**Requirements**: URI-01, URI-02, URI-03, URI-04, URI-05
**Success Criteria** (what must be TRUE):
  1. An MCP client can call `resources/read` with `chunk://<chunk_id>` and receive the chunk's content + metadata as JSON
  2. An MCP client can call `resources/read` with `graph-entity://<type>/<id>` and receive the entity payload
  3. An MCP client can call `resources/read` with `job://<job_id>` and receive current job state (preparing the URI for subscription in Phase 52)
  4. An MCP client can call `resources/read` with `file://<abs-path>` and either receive file contents (when the path is inside indexed roots) or a `roots/list`-sandbox denial error
  5. An MCP client calling `resources/templates/list` receives templates for all four schemes (`chunk://`, `graph-entity://`, `job://`, `file://`)
**Plans**: TBD

---

### Phase 52: Resource subscriptions
**Goal**: MCP clients can subscribe to live resources and receive spec-compliant update notifications, with proper per-client subscription tracking and cleanup on disconnect
**Depends on**: Phase 51 (SUB-01 requires `job://<id>` to be addressable first)
**Requirements**: SUB-01, SUB-02, SUB-03, SUB-04, SUB-05
**Success Criteria** (what must be TRUE):
  1. An MCP client can `resources/subscribe` to `job://<id>` for an active indexing job and receive `notifications/resources/updated` events at approximately 1s cadence until the job terminates
  2. An MCP client can `resources/subscribe` to `corpus://status` and receive update notifications at approximately 30s cadence
  3. An MCP client can `resources/subscribe` to `corpus://folders` and receive update notifications driven by the file watcher when indexed folders change
  4. Every `notifications/resources/updated` payload conforms to the current MCP spec (resource URI + revision metadata present and well-formed)
  5. When an MCP client disconnects, its subscriptions are released; the server holds no leaked polling tasks for that client
**Plans**: TBD

---

### Phase 53: Streamable HTTP transport
**Goal**: Operators can run `agent-brain-mcp` over Streamable HTTP alongside stdio, with explicit transport selection and loopback-only bind (auth deferred to v4)
**Depends on**: Phase 50 (design doc); independent of Phase 52 — can execute in parallel
**Requirements**: HTTP-01, HTTP-02, HTTP-03
**Success Criteria** (what must be TRUE):
  1. `agent-brain-mcp --transport http` starts an MCP server reachable by the official MCP SDK HTTP client; stdio mode continues to work unchanged when `--transport http` is not passed
  2. The Streamable HTTP server binds to `127.0.0.1` only — a connection attempt from a non-loopback address is rejected at the network layer
  3. `--transport` selection is explicit — passing an invalid or unavailable transport produces a clear startup error with no silent fallback to a different transport
**Plans**: TBD

---

### Phase 54: 9 remaining MCP tools
**Goal**: The MCP server exposes all 16 tools from the original design — clients can drive the full indexing/folder/cache/file-type lifecycle and observe long-running jobs via progress notifications
**Depends on**: Phase 52 (TOOL-04 `wait_for_job` requires the notification infrastructure from subscriptions)
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08, TOOL-09
**Success Criteria** (what must be TRUE):
  1. An MCP client can call `explain_result` for a query result id and receive provenance (source paths) and scoring breakdown (vector/BM25/rerank components)
  2. An MCP client can call `add_documents` with a path list and receive a `{job_id, status}` response that resolves through the existing job queue
  3. An MCP client can call `inject_documents` with an enrichment-script path and a folder path and receive a `{job_id, status}` response
  4. An MCP client can call `wait_for_job` for an active job and receive `notifications/progress` events at least every 2s until the job terminates, then a final completion result
  5. An MCP client can call `list_folders`, `remove_folder`, `cache_status`, `clear_cache`, and `list_file_types` and receive payloads consistent with the existing CLI/HTTP behavior for each operation
**Plans**: 4/4 complete
  - [x] **Plan 01** — Schemas + ApiClient + FILE_TYPE_PRESETS foundation (locks 18 Pydantic schemas, 5 ApiClient methods, vendored preset table). Shipped 2026-06-03.
  - [x] **Plan 02** — Read-only tool handlers (explain_result, list_folders, cache_status, list_file_types). TOOL-01/05/07/09 complete; TOOL_REGISTRY 7 -> 11; +15 fast-lane MCP tests (400 -> 415); 4 atomic commits (07ee21a / 720c27d / c27c9b2 / b310230) on main; all quality gates green. Shipped 2026-06-03.
  - [x] **Plan 03** — Mutating tool handlers (add_documents, inject_documents, remove_folder, clear_cache). TOOL-02/03/06/08 complete; TOOL_REGISTRY 11 -> 15; +18 fast-lane MCP tests (415 -> 433); 4 atomic commits (bd5cb02 / 0768ac6 / 095f5f2 / c6301b6) on main; all quality gates green. Shipped 2026-06-03.
  - [x] **Plan 04** — wait_for_job async handler with notifications/progress. TOOL-04 complete; TOOL_REGISTRY 15 -> 16 (final v2 count); first async tool handler in codebase; `ToolSpec.emits_progress` field + branched `server.call_tool` dispatch + `_build_progress_notifier` closure factory; inline poll loop (chose over reusing Phase 52 `start_polling` — both valid per objective); +18 tests (433 -> 451 fast-lane + 1 new e2e); 4 atomic commits (f95e0ce / e7d8fec / 4a2c1e0 / 7a691e7) on main; all quality gates green. Shipped 2026-06-03.

---

### Phase 55: Validation, contract tests & QA gate integration
**Goal**: v2 is end-to-end verified against the official MCP SDK, and the new MCP packages join the root quality gates so future regressions are caught locally before push
**Depends on**: Phases 50-54 (must be last — validates everything the prior phases shipped; closes out DR-5 by folding MCP packages into root `task before-push`)
**Requirements**: VAL-01, VAL-02, VAL-03, VAL-04
**Success Criteria** (what must be TRUE):
  1. A parameterized contract test suite runs all 16 MCP tools (7 from v1 + 9 from v2) against the official MCP SDK client and asserts each tool's input/output schema and behavior
  2. An end-to-end subscription test against the official MCP SDK verifies subscribe → receive updates → unsubscribe and verifies that client disconnect releases subscriptions server-side (SUB-05)
  3. A Streamable HTTP transport test exercises the MCP server via the official MCP SDK HTTP client and confirms the full initialize / tools / resources flow works
  4. `task before-push` and `task pr-qa-gate` from the repo root include the new MCP packages and exit 0 on a clean working tree (closes DR-5 from the v1 plan)
**Plans**:
  - [x] **Plan 01** — Contract test scaffolding (`mcp_stdio_session` factory + autouse D-17 orphan scan + bundled fake-server script + 8 v2 endpoint stubs in `_DEFAULT_RESPONSES` + `contract` pytest marker + `task contract` wiring). 3 atomic commits (f0b5966 / fb24ab9 / 2e92dcc) on main; all quality gates green. Shipped 2026-06-03.
  - [x] **Plan 02** — 16-tool parameterized contract tests (VAL-01). `_tool_matrix.py` SOT shared by Layer 1 (in-process) and Layer 2 (SDK) with import-time drift guard; 32 SDK tool contract assertions (16 happy + 16 negative) + 6 resources contract assertions (4 templates lock + 5 v1 corpus list + 4 per-scheme read round-trips). Layer 1 expanded from 7 to 16 tools. 4 atomic commits (86999e0 / c3b6f1f / 4a6b51c / 3e07334) on main; all quality gates green. Shipped 2026-06-03.
  - [x] **Plan 03** — Subscription lifecycle E2E (VAL-02). 3 parameterized happy-path tests (job://, corpus://status, corpus://folders) + 1 disconnect-cleanup test using raw `subprocess.Popen` for the EOF code path; cadence override via bundled fast-cadence script (monkeypatches `SUBSCRIPTION_POLICIES[*].interval_s` from env vars before `build_server`); stderr-scrape verification for Phase 52's `"subscription cleanup: cancelled"` log line (CONTEXT D-06 fallback — Phase 52 ships no debug endpoint); follow-up GitHub issue #194 filed proposing `/mcp/subscriptions/__debug` for v10.3+. 2 atomic commits (0c156fd / 0c3c9ec) on main; contract suite 39 → 43 tests (+4.32s); all quality gates green. Shipped 2026-06-03.
  - [x] **Plan 04** — Streamable HTTP transport contract tests (VAL-03). 5 SDK-driven contract tests in `tests/contract/test_http_transport_contract.py` (initialize / tools/list==16 / tools/call(server_health) / resources/list⊇{5 v1 corpus URIs} / resources/read(corpus://config)) + 1 mount-path sanity pin = 6 new tests proving the SAME 16-tool surface + 5 v1 corpus URIs surface over HTTP that Plan 02 pinned over stdio (transport-equivalence proof). New `mcp_http_session` factory fixture (parallel to Plan 01's `mcp_stdio_session` callable shape) reuses Phase 53 Plan 03's `mcp_http_subprocess` + `fake_http_server_module` from `tests/conftest.py` via pytest's parent-conftest cascade — no duplicate HTTP harness in `tests/contract/`. Defensive `*_` unpack on `streamablehttp_client` yield tuple absorbs additive SDK signature evolution. Autouse orphan-scan regex widened to also catch `fake_mcp_http_server.py`. Per CONTEXT D-10: loopback-rejection / `--transport`-rejection tests stay in Phase 53 — Plan 04 only proves happy-path SDK round-trip. NO root Taskfile changes (Plan 05). 1 atomic commit (9b8eda6) on main; contract suite 43 → 49 tests (+3.76s); all quality gates green. Shipped 2026-06-03.
  - [x] **Plan 05** — Root QA gate integration (VAL-04, closes DR-5). agent-brain-mcp + agent-brain-uds folded into root `task before-push` + `task pr-qa-gate`; per-package `before-push` tasks added (format:check → lint → typecheck → test:cov) to both Taskfiles; root recipes invoke sub-tasks inside the existing lock-guard wrapping (issue #174 mechanism preserved). Stale `# NOT wired into root` v1 headers replaced with v10.2 attribution citing DR-5 closure. VALIDATION.md milestone exit-gate attestation produced (VAL-01..04 all ✓, QA gate exit 0, coverage 91.83% MCP / 99% UDS, +60-90s wall-clock delta as planned). CHANGELOG `[10.2.0]` entry shipped consolidating full v10.2 narrative + DR-5 closure callout. ONE auto-fixed deviation: Rule 3 blocking — agent-brain-uds smoke test version assertion loosened from hardcoded "10.0.7" to MAJOR.MINOR.PATCH regex (was silently broken since 10.1.0 PyPI bump). 3 atomic commits (0391a27 / a7ca7c9 / 2ccbb84) on main; MANDATORY FINAL `task before-push` from repo root exit 0 in 162s (the DR-5 closure attestation); all quality gates green. Shipped 2026-06-03.

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-06-03 — v10.2 milestone COMPLETE (24/24 plans across Phases 50-55); Plan 55-05 closed VAL-04 + DR-5; milestone READY FOR RELEASE*
