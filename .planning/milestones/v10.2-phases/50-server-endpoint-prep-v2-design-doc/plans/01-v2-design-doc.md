# Plan 01: v2 design doc — surgical design for subscriptions, transports, endpoints, sandbox

**Phase:** 50 — Server endpoint prep + v2 design doc
**Requirements covered:** VAL-05
**Depends on:** none — first plan
**Parallel-safe with:** none (this is the approval gate for Plans 02, 03, 04)
**Status:** Not started

## Goal

File the v2 design doc at `docs/plans/2026-06-{day}-mcp-v2-subscriptions.md` so reviewers can challenge response shapes, subscription cadences, transport selection, and the `roots/list` sandbox policy **before** any endpoint or MCP-layer code lands. The doc commits the contracts that Phases 51-55 will plan against — once approved, response shapes and decisions are locked.

Style is surgical (~200-400 lines), mirroring the v1 reference doc (`docs/plans/2026-05-28-mcp-uds-transport-design.md`, 612 lines). The doc is decisions + rationale + diagrams + test plan — **not** a reference implementation. Per-phase planners write the implementation plans.

## Acceptance Criteria

- [ ] File `docs/plans/2026-06-02-mcp-v2-subscriptions.md` exists in the repo (date follows v1 convention; `02` matches today; "subscriptions" slug is the lead deliverable but the doc covers all of v2)
- [ ] Doc length is approximately 200-400 lines (target ~300; v1 reference is 612 — v2 doc is shorter because v1 already established the package layering and import-linter contracts)
- [ ] Doc contains the six required sections in order:
  1. Context (what v1 shipped, what v2 adds, what v2 explicitly defers)
  2. Architecture deltas vs v1 (subscriptions, Streamable HTTP transport, new tools, new endpoints, sandbox module)
  3. Per-phase decisions (one short subsection per Phase 50-55)
  4. Risk register (what could break v1 clients during the upgrade)
  5. Test strategy (per-phase test scope, MCP SDK contract test plan)
  6. Out of scope (v3/v4 boundaries explicit)
- [ ] §2 commits **locked response shapes** for the two new endpoints (`GET /query/chunk/{id}` and `GET /graph/entity/{type}/{id}`) per CONTEXT.md decisions B and C — verbatim, so Plans 02/03 implement them as written
- [ ] §2 commits the **`roots/list` sandbox policy** per CONTEXT.md decision A (hard whitelist, read-time canonicalization, deny-by-default rules, symlink resolution, 10 MB cap, `RESOURCE_NOT_FOUND` deny shape)
- [ ] §3 (per-phase decisions) covers Phases 50-55 with one short subsection each — Phase 50 captures decisions A/B/C/D; Phases 51-55 reference the scope doc and list the contracts they consume from Phase 50
- [ ] §4 (risk register) explicitly cites:
  - Issue #178 (Kuzu SIGSEGV) — affects `GET /graph/entity`; 503 + `graphrag.store_type: simple` workaround documented
  - Issue #179 (Bearer-token auth) — surface how v2's no-auth stance composes with Jeremy's separate PR; risk: opt-in auth surface inherited if #179 merges mid-v10.2
- [ ] §5 (test strategy) declares the MCP SDK contract test plan (16-tool parametrized suite scheduled for Phase 55; subscription E2E test; Streamable HTTP SDK test) and references the storage-protocol contract test pattern from v6.0
- [ ] §6 (out of scope) explicitly lists CLI-via-MCP (v3), framework adapter matrix (v3), OAuth (v4), MCP sampling/completion, plugin auto-registration, per-folder sandbox overrides, batch chunk endpoint, multi-hop graph traversal
- [ ] Diagrams use Mermaid or ASCII (planner's discretion per CONTEXT.md) — at minimum: one architecture-delta diagram showing the new subscription notification flow vs v1's request/response, and one sandbox-policy flowchart for `file://` reads
- [ ] Doc links back to: scope contract (`docs/roadmaps/mcp/v2-subscriptions-and-resources.md`), v1 reference (`docs/plans/2026-05-28-mcp-uds-transport-design.md`), umbrella issue #186, and the four GitHub issues filed at v1 ship (v2 issue + meta-issue + future v3/v4)
- [ ] Doc commits to MCP spec revision target (the latest spec at time of writing, 2026-03-26 revision per CONTEXT.md canonical refs)
- [ ] Frontmatter follows v1 doc convention: title, date, status (`Plan for review`), supersedes (none — additive to v1), one-line summary
- [ ] Doc passes `task before-push` (no Markdown lint regressions; line length not enforced for prose but code blocks respect 88-char Python style)

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `docs/plans/2026-06-02-mcp-v2-subscriptions.md` | create | The v2 design doc itself (~300 lines target) |

## Implementation Steps

1. **Read inputs (no code yet).** Re-read in order:
   - `docs/plans/2026-05-28-mcp-uds-transport-design.md` (v1 reference — structural template)
   - `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` (scope contract — DoD + deferred items)
   - `.planning/phases/50-server-endpoint-prep-v2-design-doc/50-CONTEXT.md` (decisions A/B/C/D verbatim)
   - `.planning/REQUIREMENTS.md` (VAL-05 + URI/SUB/HTTP/TOOL traceability)
   - `.planning/ROADMAP.md` Phases 50-55 (per-phase success criteria)

2. **Draft §1 Context (~40 lines).** Three subsections:
   - What v1 shipped (7 tools / 5 resources / 6 prompts / stdio / UDS / `corpus://*`)
   - What v2 adds (subscriptions + 4 deferred URI schemes + Streamable HTTP + 9 tools)
   - What v2 explicitly defers to v3/v4 (CLI-via-MCP, frameworks, OAuth)
   Cite scope doc + v1 doc + umbrella #186.

3. **Draft §2 Architecture deltas (~80 lines).** Include:
   - Mermaid (or ASCII) architecture diagram showing: stdio + Streamable HTTP transports → MCP server → existing FastAPI backend, with the subscription notification path overlaid
   - **Locked response shape: `ChunkRecord`** — paste the Pydantic shape verbatim from CONTEXT.md decision C. Include fields (`source`, `chunk_id`, `parent_doc_id`, `token_count`, `summary?`, `folder_id`, `language?`); explicitly note embeddings excluded with rationale
   - **Locked response shape: `GraphEntityRecord`** — paste from CONTEXT.md decision B. Include 1-hop neighbors structure `{"entity": {...}, "neighbors": {"incoming": [...], "outgoing": [...]}}`; 503 for GraphRAG-disabled; 400 for unknown entity type with valid type list; 404 for entity-not-found
   - **`roots/list` sandbox policy** — paste from CONTEXT.md decision A. Include: hard whitelist from `folders.list()`; read-time canonicalization; deny-by-default rules (hidden dot-files outside roots, symlink-escape, >10 MB cap); MCP deny response uses `RESOURCE_NOT_FOUND` with `data: {"reason": ...}`
   - Sandbox decision flowchart (Mermaid) for `file://` reads

4. **Draft §3 Per-phase decisions (~80 lines).** One subsection per phase:
   - Phase 50: decisions A/B/C/D (this doc itself). Link to plans 01-04.
   - Phase 51: URI schemes + `resources/templates/list`. Consumes ChunkRecord, GraphEntityRecord, file_sandbox from Phase 50.
   - Phase 52: Subscriptions. Polling cadences (1s job, 30s status, watcher-driven folders). Per-client subscription tracker. Cleanup on disconnect.
   - Phase 53: Streamable HTTP transport. `--transport http` flag. Loopback bind only (127.0.0.1). No auth (v4).
   - Phase 54: 9 tools. `wait_for_job` progress notifications (≤2s cadence). Other 8 tools map 1:1 to existing HTTP routes.
   - Phase 55: Validation. 16-tool parameterized SDK contract suite. Subscription E2E. HTTP transport SDK test. Root `task before-push` integration (closes DR-5).

5. **Draft §4 Risk register (~40 lines).** Tabular: risk | likelihood | impact | mitigation. Must include:
   - Kuzu SIGSEGV (#178) — affects `GET /graph/entity`; mitigation: 503 + operator workaround
   - Bearer-token auth (#179) — interaction with v2's no-auth stance; mitigation: design doc surfaces composition, endpoints follow router pattern so middleware applies uniformly
   - v1 client compatibility — v2 is purely additive (new endpoints, new MCP capabilities advertised in `initialize`). v1 clients ignoring new capabilities continue to work unchanged.
   - Subscription leak on disconnect — mitigation: Phase 52 includes disconnect cleanup test (SUB-05)
   - Streamable HTTP non-loopback exposure — mitigation: Phase 53 binds 127.0.0.1 only, asserted by test

6. **Draft §5 Test strategy (~40 lines).** Per-phase test scope:
   - Phase 50: backend contract tests for `get_chunk_by_id` and `get_entity_by_id` (parametrized ChromaDB + Postgres for chunk; Kuzu + SimplePropertyGraphStore for graph). curl smoke for endpoints. file_sandbox unit tests (positive + negative corpus).
   - Phase 51: MCP `resources/read` tests for all four schemes; `resources/templates/list` test.
   - Phase 52: MCP SDK E2E subscription test (subscribe → receive updates → unsubscribe → disconnect cleanup).
   - Phase 53: MCP SDK HTTP client test.
   - Phase 54: 9 new tool tests + `wait_for_job` progress notification cadence test.
   - Phase 55: 16-tool parametrized SDK contract suite; root `task before-push` integration.

7. **Draft §6 Out of scope (~20 lines).** Bullet list with reasons, mirroring `docs/roadmaps/mcp/v2-subscriptions-and-resources.md`. Add:
   - Deferred items from CONTEXT.md: `POST /query/chunks` batch endpoint, deep graph traversal, per-folder sandbox overrides, `roots/list` change notifications (Phase 52 concern), audit-log entries, read-only mode flag for graph entity endpoint.

8. **Draft frontmatter and links section.** YAML frontmatter at top: title, date (2026-06-02), status (`Plan for review`), supersedes (none). Add canonical-refs section at bottom linking scope doc, v1 doc, umbrella #186, and the four GitHub issues from v1 ship.

9. **Self-review.** Verify acceptance criteria checklist. Trim or expand as needed to hit ~200-400 line target. No reference implementation — decisions + rationale + diagrams + test plan only.

10. **Write the file** using the Write tool to `docs/plans/2026-06-02-mcp-v2-subscriptions.md`.

## Verification

- **Line-count check:** `wc -l docs/plans/2026-06-02-mcp-v2-subscriptions.md` returns a number in the range 200-450.
- **Section-presence check:** `grep -E '^## ' docs/plans/2026-06-02-mcp-v2-subscriptions.md` lists at least the six required top-level sections (Context, Architecture deltas, Per-phase decisions, Risk register, Test strategy, Out of scope).
- **Locked response shape check:** `grep -A 12 'ChunkRecord' docs/plans/2026-06-02-mcp-v2-subscriptions.md` shows the response shape; `grep -A 12 'GraphEntityRecord' ...` shows the entity+neighbors shape.
- **Risk register check:** `grep -E '#178|#179' docs/plans/2026-06-02-mcp-v2-subscriptions.md` returns both issue references.
- **Cross-reference check:** `grep -E '2026-05-28-mcp-uds-transport-design|v2-subscriptions-and-resources|/186' docs/plans/2026-06-02-mcp-v2-subscriptions.md` returns all three canonical links.
- **Manual review gate:** Doc is reviewed and approved by the project owner before Plans 02/03/04 begin implementation. Per CONTEXT.md decision D, endpoint code blocks on doc landing so reviewers can challenge wire shapes before they ship.
- **Pre-push gate:** `task before-push` exits 0. The doc is a Markdown file with no code, so Black/Ruff/mypy don't apply, but the gate must still pass on the working tree.

## Risk Notes

- **Risk: scope creep.** Once writing a design doc, every reviewer wants to add their pet section. Mitigation: enforce the ~400-line ceiling. Anything that doesn't fit the six required sections moves to a follow-up doc or stays a deferred item.
- **Risk: response-shape drift in subsequent plans.** If Plans 02/03 deviate from the doc's locked shapes, the doc loses its purpose. Mitigation: Plan 02 and Plan 03 acceptance criteria reference the doc's §2 verbatim. Plans 02/03 cannot pass review without matching §2.
- **Risk: approval bottleneck.** The doc is a hard gate for Wave 2. Mitigation: keep doc surgical; commit to a 1-business-day review window; if review extends past 2 days, escalate or fork the gate (let Plan 04 — sandbox module — proceed since its surface area is server-internal and design-stable).
- **Risk: future-work churn.** v3/v4 design docs may rewrite parts of §6 (out of scope). That's expected and fine — v2 doc is v2's contract, not a forever artifact.

---
*Plan 01 of Phase 50*
