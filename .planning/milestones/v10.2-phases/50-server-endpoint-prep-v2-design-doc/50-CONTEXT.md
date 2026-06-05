# Phase 50: Server endpoint prep + v2 design doc — Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Server-side prerequisites for MCP v2 are in place before any MCP-layer code lands:

1. v2 design doc filed at `docs/plans/2026-06-XX-mcp-v2-subscriptions.md` and approved (VAL-05)
2. `GET /query/chunk/{id}` endpoint shipped on `agent-brain-server` with O(1) lookup against both ChromaDB and Postgres backends (prereq for URI-01)
3. `GET /graph/entity/{type}/{id}` endpoint shipped on `agent-brain-server` against both Kuzu and SimplePropertyGraphStore graph stores (prereq for URI-02)
4. `roots/list` sandbox policy decided and documented (prereq for URI-04)

Phase 50 stops at the server boundary. MCP wire integration (`resources/read` with these schemes, `resources/templates/list`, etc.) is Phase 51.

</domain>

<decisions>
## Implementation Decisions

### A. `roots/list` sandbox policy (greenfield)
- **Sandbox model: hard whitelist** of canonical absolute paths derived from `folders.list()` (the existing source of truth for indexed folders)
- **Path canonicalization happens at read time**, not subscribe/list time — so policy stays current as folders are added/removed during the session
- **Deny by default for these patterns:**
  - Hidden dot-dirs and dot-files outside the indexed root (`.env`, `.git/*`, `.ssh/*`, `~/*` user-home patterns)
  - Any path that resolves (after symlink resolution) outside every indexed root
  - Any single-file read larger than **10 MB** (cap is configurable via server YAML, default 10 MB)
- **Symlinks are resolved before policy check.** If a symlink target falls outside all indexed roots, deny. No `--no-resolve` escape hatch in v2 (could land in v3 with auth)
- **`roots/list` response shape:** `{"roots": [{"uri": "file:///abs/path", "name": "folder-name"}, ...]}` per MCP spec
- **Deny response shape on `resources/read`:** structured MCP error code `RESOURCE_NOT_FOUND` (per MCP spec — do not leak whether path exists outside sandbox vs simply doesn't exist), with `data: {"reason": "outside_indexed_roots" | "size_limit" | "hidden_file"}` so MCP clients can surface a useful message

### B. `GET /graph/entity/{type}/{id}` endpoint
- **Response shape:** entity properties **plus immediate-neighbor (1-hop) relationships**, structured as `{"entity": {...}, "neighbors": {"incoming": [...], "outgoing": [...]}}`. Bare entity properties are insufficient — neighbors are what make GraphRAG addressable.
- **GraphRAG-disabled handling:** return **HTTP 503 Service Unavailable** with body `{"error": "graphrag_disabled", "hint": "set graphrag.enabled = true in config to enable graph-entity addressing"}`. Distinct from 404 (entity doesn't exist) — config state, not data state.
- **Entity type validation:** Accept the **17 valid types** from schema (SCHEMA-01). Reject unknown types with **400 Bad Request** + valid type list in body. Do not pass through unknown types.
- **Multi-backend coverage:** Both Kuzu and SimplePropertyGraphStore must support `get_entity_by_id(type, id)` returning `(entity, neighbors)`. New protocol method on the graph store interface.
- **Not-found:** 404 with `{"error": "entity_not_found", "type": "...", "id": "..."}`.

### C. `GET /query/chunk/{id}` endpoint
- **Response shape:** chunk content + full metadata fields (`source`, `chunk_id`, `parent_doc_id`, `token_count`, `summary` if present, `folder_id`, `language` if code). **Embeddings are NOT included** — they're large (~12 KB per chunk at 3072d × 4 bytes), MCP clients rarely use them, and they're available via separate `/query` if needed.
- **Backend behavior:** O(1) lookup via storage backend's `get_chunk_by_id(chunk_id)` method. New method on `StorageBackendProtocol` with ChromaDB and Postgres implementations.
- **Not-found:** 404 with `{"error": "chunk_not_found", "chunk_id": "..."}`. No 200-with-`found:false` semantics — proper HTTP status codes.
- **Auth:** None in v2 (matches v1 stance; auth is v4 work, tracked under #179 separately).

### D. v2 design doc depth (VAL-05)
- **Style: surgical**, ~200-400 lines. Mirrors v1 design doc (`2026-05-28-mcp-uds-transport-design.md`) which is 612 lines and considered the v1 reference.
- **Required sections:**
  1. Context (what v1 shipped, what v2 adds, what v2 explicitly defers)
  2. Architecture deltas vs v1 (subscriptions, transports, new tools)
  3. Per-phase decisions (one short subsection per Phase 50-55)
  4. Risk register (what could break v1 clients during the upgrade)
  5. Test strategy (per-phase test scope, MCP SDK contract test plan)
  6. Out of scope (v3/v4 boundaries explicit)
- **Filing convention:** `docs/plans/2026-06-{day}-mcp-v2-subscriptions.md` — date follows v1 convention. Slug deliberately mentions "subscriptions" (the lead deliverable) but the doc covers all of v2.
- **Approval gate:** Doc lands first in Phase 50 (before endpoint code). Endpoint code (decisions B/C) blocks on doc landing so reviewers can challenge the wire shapes before they ship.
- **Reference implementation NOT required** — planner produces per-phase plans. Design doc shows decisions + rationale + diagram-where-helpful + test plan only.

### Claude's Discretion
- Exact format of `roots/list` config knob in YAML (single `roots:` list vs nested under `mcp.sandbox.roots`)
- Whether to log denied reads at WARN or INFO (recommend WARN with rate-limit)
- Exact wording of MCP error reasons inside `data`
- Whether to bundle `GET /query/chunk/{id}` and `GET /graph/entity/{type}/{id}` into a single PR or split — planner decides based on review surface
- Diagram tool for the v2 design doc (mermaid vs ASCII)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### MCP design lineage
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` — v1 master design; §11 sequences v2/v3/v4, §15.1 sketches v2 scope. The v2 design doc filed in Phase 50 should follow this doc's structural pattern.
- `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` — v2 scope contract; defines DoD, what's deferred, and required SDK test coverage. Phase 50's endpoint contracts must match this doc's URI scheme definitions.
- `docs/roadmaps/mcp/README.md` — meta-roadmap that sequences v2 → v3 → v4 dependencies. Confirms v3 (#187) blocks on v2's HTTP transport (Phase 53), so Phase 50 work has downstream readers.

### Server architecture (existing patterns to extend)
- `agent-brain-server/agent_brain_server/api/routers/query.py` — existing query router; reference for FastAPI endpoint style, error handling, response models
- `agent-brain-server/agent_brain_server/api/routers/folders.py` — folder management; **source of truth for sandbox whitelist** (decision A reads from this)
- `agent-brain-server/agent_brain_server/storage/protocol.py` — `StorageBackendProtocol`; new `get_chunk_by_id` method goes here, both ChromaDB and Postgres backends implement
- `agent-brain-server/agent_brain_server/storage/chroma/backend.py` — ChromaDB implementation reference
- `agent-brain-server/agent_brain_server/storage/postgres/backend.py` — Postgres implementation reference
- `agent-brain-server/agent_brain_server/storage/graph_store.py` — graph store; new `get_entity_by_id` method goes here

### Existing requirements
- `.planning/REQUIREMENTS.md` §v1 — VAL-05 (design doc), URI-01/02/04 prerequisites (this phase enables them)
- `.planning/ROADMAP.md` Phase 50 — phase boundaries and 4 success criteria

### MCP protocol (external reference, not in-repo)
- MCP spec — `resources/templates/list`, `roots/list`, error code semantics. Phase 50 design doc should cite the spec version it targets. Latest spec at time of writing: 2026-03-26 revision.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`api/routers/query.py`** — FastAPI router pattern: dependency-injected services, Pydantic response models, structured error responses. New `chunk/{id}` route slots in here (likely as `routers/query.py:chunk_by_id` or a new `routers/chunks.py`).
- **`api/routers/folders.py`** — Source of truth for indexed folder roots. Decision A's sandbox whitelist reads from this — no separate roots config needed.
- **`storage/protocol.py`** — `StorageBackendProtocol` is the abstraction layer added in v6.0. Adding `get_chunk_by_id` here forces both backends to implement and gives contract tests for free.
- **`services/chunk_eviction_service.py`** — already does `delete_by_ids` against the storage protocol. Same lookup primitive as `get_chunk_by_id` — reference for performance/error patterns.
- **`storage/graph_store.py`** — graph store interface. Add `get_entity_by_id(type, id)` returning `(entity, neighbors)`. Implementations needed for Kuzu + SimplePropertyGraphStore.

### Established Patterns
- **OpenAPI-first** (constitution principle 2): Pydantic response models defined alongside endpoints. v2 design doc should commit response schemas in §2 (Architecture).
- **Contract tests at protocol layer** (v6.0 decision): backend tests use `pytest.mark.parametrize` across ChromaDB + Postgres. New `get_chunk_by_id` and `get_entity_by_id` tests follow this pattern.
- **No silent fallback** (v9.0 decision precedent): `--backend auto|http|embedded` selector with explicit failure. Apply same posture to graph-store backend selection in `GET /graph/entity` — fail loud if GraphRAG disabled.
- **Health endpoints by subsystem** (v6.0): `/health/postgres`, `/health/config`. Consider adding `/health/graph` for GraphRAG state — would simplify v2 503 error UX.

### Integration Points
- **Routers wire into `api/main.py`** via `app.include_router(...)`. New chunk and graph routers register there.
- **Settings exposed via `config/settings.py`**. New sandbox config (max read size, optional roots config override) lands as `Settings` fields.
- **Storage backend selected by factory in `storage/factory.py`** (or similar). Both new endpoints share that factory.

### Greenfield (no existing pattern)
- **No `allowed_root` / `sandbox` / `is_path_allowed` helper anywhere in the server.** Decision A creates a new module — recommend `agent_brain_server/security/file_sandbox.py` — with `canonicalize_path`, `is_path_allowed(path, roots)`, and the deny-by-default rules baked in. Reuse from Phase 51 onward when `file://` resources land.

</code_context>

<specifics>
## Specific Ideas

- The v2 design doc should call out **#179 API authentication design** in a "Future / Related Work" section so reviewers see how v2's no-auth stance composes with Jeremy's separate Bearer-token PR. Risk: if #179 lands mid-v10.2, the MCP server inherits an opt-in auth surface that the v2 design didn't plan for. Surface this explicitly.
- The v2 design doc should also note that **#178 (Kuzu SIGSEGV)** affects `GET /graph/entity` — if Kuzu corrupts, the endpoint returns 503 and the operator-workaround is `graphrag.store_type: simple` until #178 is fixed. Cite #178 in the risk register.

</specifics>

<deferred>
## Deferred Ideas

- **`POST /query/chunks` batch endpoint** (batch fetch by id list) — useful for MCP clients reading many chunks after a search, but not required for v2. Note for v10.3 / future.
- **`GET /graph/entity/{type}/{id}/neighbors?depth=2`** — deeper graph traversal endpoint. v2 covers 1-hop only; multi-hop deferred to v3 if framework adapters need it.
- **`PATCH /folders/{id}/sandbox_overrides`** — per-folder sandbox policy override (e.g., explicitly allow `.env` in a docs folder). Out of scope for v2; revisit if user feedback demands.
- **`roots/list` change notifications** — when folders are added/removed, MCP should notify subscribed clients. This is a Phase 52 (subscriptions) concern, not Phase 50; documented here so Phase 52's `corpus://folders` design picks it up.
- **Audit-log entries for denied reads** — log structured deny events to a security audit stream. Not in scope for v2; could land alongside #179 auth work.
- **Read-only mode flag for `GET /graph/entity`** — return entity properties without invoking the GraphRAG retriever (cheaper). Defer until performance measurement shows it's needed.

</deferred>

---

*Phase: 50-server-endpoint-prep-v2-design-doc*
*Context gathered: 2026-06-02*
