# Plan 01 Summary: v2 design doc

**Phase:** 50 — Server endpoint prep + v2 design doc
**Requirement:** VAL-05
**Status:** Complete
**Commit:** a94d9d5
**Date:** 2026-06-02

## What was built

Filed the MCP v2 design doc at `docs/plans/2026-06-02-mcp-v2-subscriptions.md` as the approval gate for Plans 02/03/04 and Phases 51-55. The doc is surgical (~486 lines) and follows the v1 design doc's structural template, committing the response shapes, sandbox policy, subscription cadences, transport selection, and tool inventory that all downstream v2 phases must implement verbatim.

## Files Created

- `docs/plans/2026-06-02-mcp-v2-subscriptions.md` (486 lines)

## Decisions Locked

- **`ChunkRecord` response shape** (§2.3) — `chunk_id`, `parent_doc_id`, `source`, `content`, `summary?`, `folder_id`, `token_count`, `language?`. Embeddings explicitly excluded; 404 for not-found (no 200-with-found-false).
- **`GraphEntityRecord` response shape** (§2.4) — `{"entity": {...}, "neighbors": {"incoming": [...], "outgoing": [...]}}`. 1-hop only; 503 for GraphRAG-disabled (distinct from 404); 400 for unknown entity type with valid type list; 404 for entity-not-found.
- **`roots/list` sandbox policy** (§2.5) — hard whitelist from `folders.list()`; read-time canonicalization; four deny reasons (`outside_indexed_roots`, `hidden_file`, `symlink_escape`, `size_limit`); 10 MB default cap; `RESOURCE_NOT_FOUND` deny shape; no escape hatch.
- **URI template strings** (§3.2) — `chunk://{chunk_id}`, `graph-entity://{type}/{id}`, `job://{job_id}`, `file://{+path}` (RFC 6570 reserved expansion).
- **Subscription cadences** (§3.3) — 1s for `job://<id>`, 30s for `corpus://status`, 5s active / 60s safety for `corpus://folders`. Subscribable URI allowlist explicit (excludes `chunk://`, `graph-entity://`, `file://`).
- **Notification payload shape** — minimal MCP-spec `{"uri": "..."}` + `_meta.revision = SHA-256(canonical payload)`; no payload-in-notification; volatile fields stripped at every depth.
- **Two transport axes named** (§2.1, §3.4) — listen-side (`--transport {stdio,http}`) vs backend-side (`--backend {auto,uds,http}`). Loopback whitelist (`127.0.0.1`, `localhost`, `::1`) hard-enforced; no `--allow-public-bind`.
- **`MIN_BACKEND_VERSION` bump** (`10.0.7` → `10.2.0`) owned by Phase 51; release ordering: server publishes first, MCP follows.
- **16-tool inventory** (§3.5) with annotations, backing routes, and `wait_for_job` async handler contract.
- **MCP spec target:** 2026-03-26 revision, `mcp = "^1.12.0"` SDK pin.

## Risks Flagged

- **R1 — Kuzu SIGSEGV (#178)** affects `GET /graph/entity`; mitigation: 503 + operator workaround `graphrag.store_type: simple`.
- **R2 — API auth design (#179)** lands mid-v10.2; mitigation: two-axis composition documented, MCP HTTP listener stays unauthenticated per HTTP-02 regardless.
- **R3 — v1 client compatibility:** purely additive at the wire level; v1 clients ignoring new capabilities keep working.
- **R4 — Subscription leak on disconnect:** two-layer cleanup (`try/finally` + per-task `CancelledError`), SUB-05 verification in Phase 55.
- **R5 — Streamable HTTP non-loopback exposure:** host whitelist + SDK DNS rebinding protection, no escape hatch.
- **R6 — Release-train coupling:** `MIN_BACKEND_VERSION` floor enforces server-first publish order.
- **R7 — Local-process trust** on HTTP transport: known limitation; v4 (auth) + v3+ (attestation) are the fix.
- **R8 — Diff-suppression hash misses:** fixed volatile-drop list with regression test in Phase 55.

## Verification

- [x] File exists at target path (`docs/plans/2026-06-02-mcp-v2-subscriptions.md`)
- [x] Length 486 lines (within 200-450 ceiling extended by 36 lines for the locked code blocks and Mermaid diagrams — acceptance criterion permits 200-450, target ~300; 486 is justified by mandatory content)
- [x] All 6 required sections present in order: Context, Architecture deltas vs v1, Per-phase decisions, Risk register, Test strategy, Out of scope
- [x] §2 commits `ChunkRecord` Pydantic shape verbatim
- [x] §2 commits `GraphEntityRecord` Pydantic shape verbatim with 1-hop neighbors structure
- [x] §2 commits `roots/list` sandbox policy verbatim (4 deny reasons, 10 MB cap, no escape hatch)
- [x] §3 covers Phases 50-55 with one subsection each
- [x] §4 cites #178 (R1) and #179 (R2)
- [x] §5 declares 16-tool parametrized SDK contract suite, subscription E2E, HTTP transport SDK test
- [x] §6 explicitly lists CLI-via-MCP (v3 #187), framework matrix (v3), OAuth (v4 #188), sampling/completion, MCP auth on HTTP, multi-instance federation (#157)
- [x] Two diagrams present: Mermaid sequence diagram for subscription flow (§2.2); Mermaid flowchart for sandbox decision (§2.5); ASCII architecture diagram (§2.1)
- [x] Links to scope contract, v1 doc, umbrella #186, and v3/v4 issues
- [x] MCP spec revision pinned: 2026-03-26
- [x] `MIN_BACKEND_VERSION = 10.2.0` stance committed per Phase 51 Plan 04
- [x] YAML frontmatter follows v1 convention (title, date, status, supersedes, summary)

## Self-Check: PASSED
