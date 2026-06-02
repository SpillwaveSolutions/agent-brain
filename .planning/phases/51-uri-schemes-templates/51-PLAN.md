---
phase: 51-uri-schemes-templates
type: phase-index
plan_count: 4
requirements: [URI-01, URI-02, URI-03, URI-04, URI-05]
depends_on_phase: [50-server-endpoint-prep-v2-design-doc]
prerequisite_for_phase: [52-resource-subscriptions]
---

# Phase 51 Plan: URI schemes + templates

**Goal:** All four deferred URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`) are addressable via MCP `resources/read`, and `resources/templates/list` advertises them so model clients can discover them programmatically.

**Requirements:** URI-01, URI-02, URI-03, URI-04, URI-05
**Plan count:** 4
**Depends on:** Phase 50 (URI-01/02/04 require new server endpoints + sandbox design)
**Prerequisite for:** Phase 52 (SUB-01 — `job://` must be addressable first)

## Plans

| # | Title | Requirements | Depends on | Parallel-safe with | Est. LOC |
|---|-------|--------------|------------|---------------------|----------|
| 01 | Parameterized URI dispatcher + `job://` handler | URI-03 | none (first plan) | none | ~250 |
| 02 | `chunk://` + `graph-entity://` handlers + ApiClient extensions | URI-01, URI-02 | 01 | 03 | ~280 |
| 03 | `file://` handler with sandbox enforcement | URI-04 | 01 | 02 | ~290 |
| 04 | `resources/templates/list` handler + `MIN_BACKEND_VERSION` bump | URI-05 | 01, 02, 03 | none | ~180 |

**Total estimated LOC:** ~1,000 (code + tests)

## Execution Order

- **Wave 1 (sequential, foundation):** Plan 01 — establishes the `ParsedURI` dataclass, `parameterized.py` dispatch module, and `read_resource` scheme-prefix routing. Lands `job://` as the simplest exemplar (reuses existing `ApiClient.get_job()`).
- **Wave 2 (parallel):** Plan 02 and Plan 03 — each lands one or two new scheme handlers on top of the dispatcher. They touch disjoint files (`parameterized.py` is append-only per scheme; `client.py` modified only by 02; `security/` module added only by 03). Both can be developed and reviewed concurrently.
- **Wave 3 (sequential, finalization):** Plan 04 — wires the `@server.list_resource_templates()` handler advertising all four schemes, bumps `MIN_BACKEND_VERSION` to `"10.2.0"`, and adds the end-to-end test exercising all four schemes through the official MCP SDK.

## Coverage Check

Every requirement maps to at least one plan:

- **URI-01** (`chunk://` via `resources/read`): Plan 02
- **URI-02** (`graph-entity://` via `resources/read`): Plan 02
- **URI-03** (`job://` via `resources/read`): Plan 01
- **URI-04** (`file://` gated by indexed roots): Plan 03
- **URI-05** (`resources/templates/list` advertises all four): Plan 04

## Cross-Phase Dependencies

**Assumes Phase 50 has shipped:**
- `GET /query/chunk/{id}` endpoint (consumed by Plan 02's `ApiClient.get_chunk()`)
- `GET /graph/entity/{type}/{id}` endpoint (consumed by Plan 02's `ApiClient.get_graph_entity()`)
- `agent_brain_server/security/file_sandbox.py` module exporting `is_path_allowed`, `canonicalize_path`, `MAX_READ_BYTES` (consumed by Plan 03)
- `docs/plans/2026-06-XX-mcp-v2-subscriptions.md` design doc (VAL-05) — Phase 51 plans reference its per-phase decisions section

**Produces for Phase 52:**
- `ParsedURI` dataclass and URI-parsing helpers in `agent_brain_mcp/resources/parameterized.py` — Phase 52's `resources/subscribe` handler reuses the same parser to extract `job_id` from `job://<id>` (CONTEXT.md decision F)
- `job://` as an addressable resource — SUB-01 subscribes to this URI

## Risk Register

1. **Phase 50 sandbox helper re-export contract drift.** If `agent_brain_server/security/file_sandbox.py` ships with a different signature than Plan 03 assumes, the `file://` handler will fail to import. Mitigation: Plan 03 includes an explicit verification step that imports the helper from the server package before writing any handler code.
2. **`MIN_BACKEND_VERSION = "10.2.0"` release-train coupling.** The MCP package release in this milestone MUST follow `agent-brain-server 10.2.0`. Plan 04 documents this in the design doc's release-plan section. CI release script must be updated (out of scope for Phase 51 — Phase 55 handles).
3. **`{+path}` reserved expansion in `file://` template** is a forward-incompatible commitment — once advertised, clients lock onto it. Plan 04 includes a checkpoint asking for confirmation that the template strings are reviewed before merge (this also satisfies the CONTEXT.md specific item #1).
4. **Risk #178 (Kuzu SIGSEGV) carry-forward.** If the operator runs with Kuzu enabled, `graph-entity://*` reads may surface as `SERVICE_INDEXING` (503 passthrough). Plan 02's tests cover both the success path and the 503-passthrough path; operator workaround is `graphrag.store_type: simple` (documented in design doc).
5. **`asyncio.to_thread` discipline for sync httpx.** All three server-backed handlers must wrap `httpx` calls in `asyncio.to_thread`; missing this freezes stdio. Plan 01 establishes the pattern in the `job://` handler; Plans 02 and 03 mirror it. Cross-cutting lint rule is out of scope (handled by review).
6. **Sandbox roots cache decision (re-fetch every read).** Plan 03 deliberately does no caching — folder list is re-fetched on every `file://` read to prevent stale-root sandbox-widening. This is a hot-path cost the design doc must acknowledge. If profiling reveals it dominates, a short-TTL cache is a future optimization.

## Quality Gate (applies to every plan)

Each plan's verification section MUST include:

```bash
task before-push       # Black + Ruff + mypy strict + pytest, exits 0
task pr-qa-gate        # End-to-end QA, exits 0
task mcp:test          # Per-package MCP test gate, exits 0
task mcp:contract      # Pinned MCP SDK contract test, exits 0
task check:layering    # import-linter contracts hold, exits 0
```

Per the v1 precedent (`docs/plans/2026-05-28-mcp-uds-transport-design.md` §12.1), MCP-package quality runs through per-package `task mcp:*` until Phase 55 folds it into root `task before-push` (VAL-04).

## Layering Contracts (must continue to hold)

- `agent_brain_mcp` MUST NOT import from `agent_brain_server.services`, `.api`, `.indexing`, `.storage`
- `agent_brain_mcp` MAY import from `agent_brain_server.models` (existing) and `agent_brain_server.security` (NEW — Plan 03 adds this import)
- Plan 03 may need a new `.importlinter` allowance for the `security` subpackage; verify in Plan 03's implementation step.

---
*Phase plan generated: 2026-06-02*
