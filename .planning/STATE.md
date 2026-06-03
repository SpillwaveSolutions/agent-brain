---
gsd_state_version: 1.0
milestone: v10.2
milestone_name: MCP v2 — Subscriptions, HTTP Transport, & Tool Completion
current_phase: 51
status: executing
stopped_at: "Plan 51-01 complete (job:// dispatcher shipped) — resume at Plan 51-02 (chunk:// + graph-entity://)"
last_updated: "2026-06-03T05:22:19Z"
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 24
  completed_plans: 5
---

# Agent Brain — Project State

**Last Updated:** 2026-06-03
**Current Milestone:** v10.2 MCP v2 — Subscriptions, HTTP Transport, & Tool Completion
**Status:** Executing Phase 51
**Current Phase:** 51

## Current Position

Phase: 51 (uri-schemes-templates) — EXECUTING
Plan: 2 of 4 (Plan 51-01 shipped 2026-06-03)

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-03)

**Core value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Current focus:** Phase 51 — uri-schemes-templates

## Milestone Summary

```
v3.0 Advanced RAG:           [██████████] 100% (shipped 2026-02-10)
v6.0 PostgreSQL Backend:     [██████████] 100% (shipped 2026-02-13)
v6.0.4 Plugin & Install:     [██████████] 100% (shipped 2026-02-22)
v7.0 Index Mgmt & Pipeline:  [██████████] 100% (shipped 2026-03-05)
v8.0 Performance & DX:       [██████████] 100% (shipped 2026-03-15)
v9.0 Multi-Runtime:          [██████████] 100% (shipped 2026-03-16)
v9.1.0 Skill-Runtime:        [██████████] 100% (shipped 2026-03-16)
v9.3.0 LangExtract+Config:   [██████████] 100% (shipped 2026-03-22)
v9.4.0 Doc Accuracy Audit:   [██████████] 100% (shipped 2026-03-20)
v9.5.0 Config Val & Lang:    [██████████] 100% (shipped 2026-03-31)
v9.6.0 Runtime Parity:       [██▌       ]  25% (1/4 phases — parked, deferred to post-MCP)
v10.0.0–v10.0.6 Patch Train: [██████████] 100% (shipped 2026-05-25 → 2026-05-27)
v10.1.0 MCP v1:              [██████████] 100% (shipped 2026-05-30; UDS + 7-tool stdio MCP + CLI dual transport)
v10.1.2 MCP package rename:  [██████████] 100% (shipped 2026-06-01; agent-brain-mcp PyPI distribution + standalone user guide)
v10.2 MCP v2:                [█▌        ]  17% (Phase 50 complete — 4/24 plans · VERIFICATION passed)
```

## v10.2 Phase Progress

| Phase | Status | Requirements | Plans |
|-------|--------|--------------|-------|
| 50. Server endpoint prep + v2 design doc | ✓ Complete (2026-06-03) | VAL-05 ✓ | 4/4 |
| 51. URI schemes + templates | In progress (Plan 01 shipped 2026-06-03) | URI-03 ✓ · URI-01/02/04/05 pending | 1/4 |
| 52. Resource subscriptions | Planned, not started | SUB-01, SUB-02, SUB-03, SUB-04, SUB-05 | 0/4 |
| 53. Streamable HTTP transport | Planned, not started | HTTP-01, HTTP-02, HTTP-03 | 0/3 |
| 54. 9 remaining MCP tools | Planned, not started | TOOL-01..TOOL-09 | 0/4 |
| 55. Validation, contract tests & QA gate | Planned, not started | VAL-01, VAL-02, VAL-03, VAL-04 | 0/5 |

**Coverage:** 27/27 v1 requirements mapped to phases (no orphans, no duplicates)
**Total plans:** 24 (Phase 50: 4 ✓ · Phase 51: 4 · Phase 52: 4 · Phase 53: 3 · Phase 54: 4 · Phase 55: 5)
**Phase 50 shipped:** v2 design doc (486 lines) · `GET /query/chunk/{chunk_id}` (ChromaDB + Postgres) · `GET /graph/entity/{type}/{id}` (Kuzu + Simple, #178 503 fallback) · `agent_brain_server/security/file_sandbox.py` (4 deny reasons, 10 MiB cap) — full suite green: 1269 passed, 0 regressions, Black/Ruff/mypy strict all clean

## v10.2 Cross-Phase Risk Register (from workflow summarizer)

Surface-level risks the planner agents identified across phases that need cross-phase attention during execution:

- **#178 Kuzu SIGSEGV carry-forward**: Phase 50 Plan 03 (multi-backend graph endpoint), Phase 51 Plan 02 (graph-entity:// returns 503 when Kuzu corrupts), Phase 55 Plan 03 (subscription e2e tolerates 503). Operator workaround: `graphrag.store_type: simple`.
- **#179 Bearer-token API auth mid-flight**: Phase 50 Plan 01 design doc surfaces composition explicitly; Phase 51 endpoints inherit middleware; Phase 53 USER_GUIDE two-axis diagram mitigates backend-vs-listen-axis confusion.
- **MCP SDK API drift**: Phase 51 Plan 04 (ResourceTemplate decorator), Phase 52 Plan 02 (ServerSession.send_resource_updated), Phase 53 Plan 01 (StreamableHTTPSessionManager existence), Phase 55 Plan 04 (streamablehttp_client) all bind to pinned SDK version. Phase 50 design doc pins 2026-03-26 spec; Phase 55 Plan 05 audits pyproject.toml still pins SDK version (D-03).
- **MIN_BACKEND_VERSION = 10.2.0** (Phase 51 Plan 04): forces release-train ordering — agent-brain-server 10.2.0 ships BEFORE agent-brain-mcp 10.2.0.
- **Phase 50 → Phase 51 surface contract**: Phase 51 Plan 03 imports Phase 50's `file_sandbox` helpers verbatim; signature drift would block file:// (mitigation: Phase 51 Plan 03 starts with import-verification step).
- **Phase 52 → Phase 54 contract**: Phase 54 Plan 04 (wait_for_job) reuses Phase 52 Plan 01's `SubscriptionManager.start_polling()` primitive — Plan 01 documents this as a public API guarantee.
- **+60-90s local pre-push cost** from Phase 55 Plan 05 folding MCP/UDS into root before-push — documented in CHANGELOG and v2 design doc.

Full cross-phase risk register: 17 items in the workflow summarizer output (saved alongside the workflow transcript).

## Accumulated Context

### Key Context Carried Forward

- **MCP v1 in production:** `agent-brain-mcp` is published to PyPI. Stdio transport, 7 tools, 5 read-only resources, 6 prompts. UDS transport (`agent-brain-uds`) is also live. CLI supports `--transport {auto,uds,http}`.
- **Source design exists:** `docs/plans/2026-05-28-mcp-uds-transport-design.md` is the master design for v1/v2/v3/v4. v2 work is scoped in `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` and tracked by umbrella issue #186.
- **Phase order is hard-blocking:** Phase 50 must precede Phase 51 (URI-01/02/04 need server endpoints); Phase 51 must precede Phase 52 (SUB-01 needs `job://` addressable); Phase 52 must precede Phase 54 (TOOL-04 `wait_for_job` needs notification infrastructure); Phase 55 must be last (folds packages into root QA gate). Phase 53 (HTTP transport) is independent of Phase 52 and can run in parallel.
- **Prerequisites for downstream milestones:** v3 (#187) depends on v2's HTTP transport (Phase 53). v4 (#188) depends on v3's `McpHttpBackend`.

### Decisions from Prior Milestones (still load-bearing)

- [v9.5.0]: Runtime install behavior covered structurally; headless parity through real external CLIs still unverified (v9.6.0 phases 47–49 deferred — re-evaluate during MCP v3)
- [v10.0.6]: Kuzu graph store self-heals from corruption via triplet snapshots (#166)
- [v10.1.0]: MCP v1 shipped — `agent-brain-mcp` package, UDS transport, 7-tool stdio server, CLI dual transport
- [v10.1.2]: PyPI package renamed to `agent-brain-mcp`; standalone MCP user guide added (commits `1e34818`, `cf7a364`)
- **Decision (2026-06-01):** Pivot away from MCP-is-out-of-scope stance recorded in PROJECT.md v9.6.0 era. MCP is now the active investment direction; that out-of-scope line has been removed.
- **Decision (2026-06-02):** v2 design doc (VAL-05) lands in Phase 50, *before* MCP-layer implementation, so reviewers can challenge the subscription/transport approach before code lands.
- **Decision (2026-06-03, Plan 51-01):** Parameterized URI dispatcher in `agent_brain_mcp/resources/parameterized.py` uses a *single* `ParsedURI` dataclass (all per-scheme fields optional, only the relevant ones populated) and a *closed* `PARAMETERIZED_SCHEMES` frozenset with NotImplementedError-raising placeholders for `chunk`/`graph-entity`/`file`. Plans 51-02 and 51-03 swap the placeholder values in `PARAMETERIZED_HANDLERS` without touching the dispatcher or the registry shape. Error-data shapes for malformed-URI (`{uri, reason}`) vs backend-404 (`{scheme, <id>, httpStatus, cause}`) are intentionally different — see module docstring.

### Blockers/Concerns

- **#178 Kuzu SIGSEGV during sustained GraphRAG indexing** — workaround exists (`graphrag.store_type: simple`), not blocking v10.2 but should be tracked separately
- **#184 GraphSnapshotManager auto-replay scope-gap** — Kuzu-adjacent, not blocking v10.2
- **#179 API authentication design** — green-lit 2026-06-01; Jeremy implementing under separate PR; secure-by-default key generation. NOT a v10.2 milestone deliverable (MCP v2 explicitly says "loopback only, no auth yet — auth is v4")

### Open GitHub Issues Relevant to v10.2 Scope

- **#186** — MCP v2 umbrella (this milestone)
- **#189** — MCP roadmap meta (parent tracker)
- **#187** — MCP v3 (next milestone candidate; blocked on v2 HTTP transport = Phase 53)
- **#188** — MCP v4 OAuth (blocked on v3 `McpHttpBackend`)
- **#167** — original MCP server design issue (v1 implementation tracker; v1 has shipped, can be closed if not already)

### Other Open Issues (NOT in v10.2 scope)

Feature backlog (#152, #154, #155, #156, #157, #158, #160, #162, #163, #164) and bugs (#178, #184) and security (#179) tracked separately; revisit during v10.3 / v11 planning.

## Session Continuity

**Last Session:** 2026-06-03T05:22:19Z
**Stopped At:** Plan 51-01 complete (job:// dispatcher + parameterized handler infrastructure shipped; 21 new tests; 4 commits 4bc2901..b84890c; all four MCP quality gates green + task before-push exit 0)
**Resume File:** `.planning/phases/51-uri-schemes-templates/plans/02-chunk-and-graph-entity-uris.md`
**Next Action:** `/gsd:execute-plan 51 02` — execute Plan 51-02 (chunk:// + graph-entity:// handlers, swap NotImplementedError placeholders in PARAMETERIZED_HANDLERS, add ApiClient.get_chunk + get_graph_entity methods)

## Recommended Execution Order

Per workflow summarizer (verified ready_to_execute: true):

1. **Phase 50** — Foundation (design doc + 2 endpoints + sandbox helpers). MUST land first.
2. **Phase 51** — URI schemes (depends on Phase 50 endpoints + file_sandbox)
3. **Phase 52** — Subscriptions (depends on Phase 51's job:// URI registration)
4. **Phase 53** — Streamable HTTP transport (independent of Phase 52; can run in parallel with 51-52)
5. **Phase 54** — 9 remaining tools (depends on Phase 52's ProgressNotifier for wait_for_job; should land after Phase 53 so new tools surface on both transports)
6. **Phase 55** — Validation + QA gate (validates Phases 50-54; must be last; verification-only, no new production code)

---
*State updated: 2026-06-03 — Plan 51-01 shipped (parameterized URI dispatcher + job:// handler); Phase 51 1/4 plans complete; URI-03 closed*
