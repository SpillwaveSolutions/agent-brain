---
phase: 54-remaining-mcp-tools
type: phase-index
milestone: v10.2-mcp-v2
goal: "All 9 remaining tools from the original 16-tool design are exposed by agent-brain-mcp with parameter schemas derived from existing server routes. wait_for_job emits notifications/progress every <=2s."
requirements: [TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08, TOOL-09]
depends_on_phases: [50, 52]
prerequisite_for_phases: [55]
plan_count: 4
---

# Phase 54 Plan: 9 remaining MCP tools

**Goal:** The MCP server exposes all 16 tools from the original design. Clients can drive the full indexing/folder/cache/file-type lifecycle and observe long-running jobs via progress notifications. All schemas are minimal hand-written projections of the existing FastAPI routes — no new server endpoints land in Phase 54.

**Requirements:** TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08, TOOL-09
**Plan count:** 4

## Plans

| # | Title | Requirements | Depends on | Parallel-safe with | Est. LOC |
|---|-------|--------------|------------|---------------------|----------|
| 01 | Phase 54 foundation: schemas + ApiClient methods | (foundation for 01-09) | none — first plan | none | ~280 |
| 02 | Read-only tools: explain_result, list_folders, cache_status, list_file_types | TOOL-01, TOOL-05, TOOL-07, TOOL-09 | 01 | 03 | ~260 |
| 03 | Mutating tools: add_documents, inject_documents, remove_folder, clear_cache | TOOL-02, TOOL-03, TOOL-06, TOOL-08 | 01 | 02 | ~290 |
| 04 | Progress-emitting tool: wait_for_job | TOOL-04 | 01, Phase 52 (ProgressNotifier shape) | 02, 03 | ~220 |

**Total estimated LOC (incl. tests):** ~1,050

## Execution Order

```
Wave 1 (sequential foundation):
  Plan 01 — schemas + ApiClient methods

Wave 2 (parallel — all depend only on Plan 01):
  Plan 02 — read-only tools
  Plan 03 — mutating tools
  Plan 04 — wait_for_job  (additionally requires Phase 52 to have landed)
```

Plan 04 is the only plan with a cross-phase blocker. If Phase 52 has not finalized the `ProgressNotifier` injection contract on `ToolSpec`/`call_tool`, hold Plan 04 until it has; Plans 02 and 03 can ship independently.

## Coverage Check

Every requirement maps to at least one plan:

- **TOOL-01** (`explain_result`): Plan 02
- **TOOL-02** (`add_documents`): Plan 03
- **TOOL-03** (`inject_documents`): Plan 03
- **TOOL-04** (`wait_for_job` with progress): Plan 04
- **TOOL-05** (`list_folders`): Plan 02
- **TOOL-06** (`remove_folder`): Plan 03
- **TOOL-07** (`cache_status`): Plan 02
- **TOOL-08** (`clear_cache`): Plan 03
- **TOOL-09** (`list_file_types`): Plan 02

All 9 TOOL requirements covered. No double-mapping. No gaps.

## Cross-Phase Dependencies

**Incoming (Phase 54 depends on):**

- **Phase 50** — Server endpoint prep / v2 design doc filed. Phase 54 does NOT add new server endpoints (Decision A in 54-CONTEXT.md); all 9 tools wrap existing routes. The v2 design doc (`docs/plans/2026-06-XX-mcp-v2-subscriptions.md`) must be updated to enumerate the 9 tools and `wait_for_job`'s progress contract.
- **Phase 52** — `notifications/progress` send primitive + `ProgressNotifier` injection contract on `ToolSpec`/`server.call_tool`. **Only Plan 04 (`wait_for_job`) consumes this.** Plans 02 and 03 are independent of Phase 52.

**Outgoing (Phase 54 unblocks):**

- **Phase 55** — Validation, contract tests & QA gate integration. Requires all 9 tools registered in `TOOL_REGISTRY` so the parameterized MCP SDK contract test (VAL-01) sees the full 16-tool surface. Also requires the `list_file_types` MCP-side preset table for the cross-package equality assertion against the CLI's `FILE_TYPE_PRESETS`.
- **v3 framework adapters** — full 16-tool surface available to OpenAI Agents SDK, LangChain, LlamaIndex, Mastra, Pydantic AI, Vercel AI SDK once Phase 54 ships.

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Schema drift between MCP-side hand-written models and server's Pydantic models | Medium | Medium — silent client/server validation mismatch | Plan 01 explicitly enumerates the constraint-by-constraint comparison checklist; Phase 55 contract tests catch the rest |
| Phase 52's `ProgressNotifier` contract changes after Plan 04 is drafted | Medium | High — Plan 04 needs rework | Plan 04 is sequenced last; review Phase 52's `tools/__init__.py` ToolSpec extension before drafting Plan 04's handler signature |
| `FILE_TYPE_PRESETS` drift between CLI and MCP copies | High | Low — only affects `list_file_types` accuracy | Plan 02 vendors the dict verbatim from `agent-brain-cli/agent_brain_cli/commands/types.py` and adds a comment pointing to it; Phase 55 contract test asserts `MCP_PRESETS == CLI_PRESETS` |
| `wait_for_job` runaway when client disconnects mid-poll | Medium | Medium — leaked indexing job + leaked polling task | Plan 04 specifies `asyncio.CancelledError` propagation in `finally:` plus a `client.cancel_job(job_id)` call on cancellation |
| `inject_documents` allowlist 403 (issue #181) surprises MCP clients | Medium | Low — confusing UX | Plan 03 requires the tool description to explicitly call out "scripts must be allowlisted server-side"; matches CLI's `inject.py` UX |
| `explain_result` re-execution makes it expensive to call in a loop | Medium | Low — but user surprise factor | Plan 02 requires the tool description to explicitly warn "not for high-frequency calls" and recommend `search_documents(..., explain=true)` directly for bulk |
| `_summarize()` in `server.py` becomes a long if/elif chain with 16 tools | High | Low — pure style concern | Acceptable; v1 already establishes the pattern, refactor deferred |
| `additionalProperties: false` mismatch in JSON Schema generation for new Pydantic models | Low | High — silent MCP client validation failures | Plan 01 uses the existing `json_schema()` helper which already sets this; smoke test in Plan 01 asserts every new schema has `additionalProperties: false` |

## Quality Gates (per plan, per CLAUDE.md)

Every plan in Phase 54 must:

- Pass `task before-push` from the repo root (Black, Ruff, mypy strict, pytest with >50% coverage). Per-plan failure to do so means the plan is incomplete.
- Pass `task mcp:test` and `task mcp:pr-qa-gate` from `agent-brain-mcp/`.
- Pass `task check:layering` — the import-linter contracts from v1 (§9 of `2026-05-28-mcp-uds-transport-design.md`) MUST stay green. New tool modules import only from `agent_brain_mcp.client`, `agent_brain_mcp.schemas`, `agent_brain_mcp.errors`, `agent_brain_server.models` (for shape mirroring only — no service/api/storage/indexing imports), and stdlib.
- Add tests alongside implementation (test-alongside principle from PROJECT.md §Architecture).

## Out of Scope for Phase 54

(These belong to Phase 55, future phases, or different milestones — listed here so reviewers can challenge inclusion.)

- Parameterized MCP SDK contract tests for all 16 tools — **Phase 55, VAL-01.** Phase 54 only adds per-tool unit + smoke tests.
- Root `task before-push` integration of the MCP package — **Phase 55, VAL-04.** Phase 54 uses per-package gates only.
- New server endpoints (`GET /index/types`, `POST /query/explain` with chunk-id lookup) — **Deferred to v3** per 54-CONTEXT.md `<deferred>` section.
- MCP progress notifications for `add_documents` / `inject_documents` themselves — clients use `wait_for_job` separately. Deferred per CONTEXT.
- Tool-level rate limiting on destructive tools — out of scope for v2 (local-first, single-user).

---

*Phase plan generated: 2026-06-02*
*Planner: gsd-planner under /gsd:plan-phase auto mode*
*Source design: docs/plans/2026-05-28-mcp-uds-transport-design.md §11, §15.1*
*Scope contract: docs/roadmaps/mcp/v2-subscriptions-and-resources.md*
*Phase context: .planning/phases/54-remaining-mcp-tools/54-CONTEXT.md*
