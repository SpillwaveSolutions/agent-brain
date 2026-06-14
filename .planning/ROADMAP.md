# Agent Brain Roadmap

**Created:** 2026-02-07
**Last updated:** 2026-06-14 — v10.3 MCP v3 shipped (Phases 56-63); awaiting next milestone
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Active milestone:** none — v10.3 shipped; run `/gsd:new-milestone` to scope the next

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

## Progress

| Phase                                                       | Milestone | Plans Complete | Status      | Completed  |
| ----------------------------------------------------------- | --------- | -------------- | ----------- | ---------- |
| 50. Server endpoint prep + v2 design doc                    | v10.2     | 4/4            | Complete    | 2026-06-03 |
| 51. URI schemes + templates                                 | v10.2     | 4/4            | Complete    | 2026-06-03 |
| 52. Resource subscriptions                                  | v10.2     | 4/4            | Complete    | 2026-06-03 |
| 53. Streamable HTTP transport                               | v10.2     | 3/3            | Complete    | 2026-06-03 |
| 54. 9 remaining MCP tools                                   | v10.2     | 4/4            | Complete    | 2026-06-03 |
| 55. Validation, contract tests & QA gate                    | v10.2     | 5/5            | Complete    | 2026-06-03 |
| 56. Design doc + CLI backend skeleton                       | 3/3 | Complete    | 2026-06-06 | -          |
| 57. CLI transport selector + byte-identical equivalence     | 3/3 | Complete    | 2026-06-07 | -          |
| 58. Runtime discovery + helper commands                     | 3/3 | Complete    | 2026-06-07 | -          |
| 59. CLI prompts + resources commands                        | 3/3 | Complete    | 2026-06-09 | -          |
| 60. Subprocess hygiene + 1000-invocation orphan test        | 3/3 | Complete    | 2026-06-09 | -          |
| 61. Python framework adapter matrix                         | 4/4 | Complete    | 2026-06-11 | -          |
| 62. TypeScript framework adapter matrix                     | 2/2 | Complete    | 2026-06-12 | -          |
| 63. Tooling + docs + integration page                       | 3/3 | Complete    | 2026-06-12 | -          |

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-06-14 — v10.3 MCP v3 shipped (8 phases, 24 plans, 23/23 requirements). Milestone audit passed; CLI-MCP-04 DoD-anchor gap fixed on-branch. Next: `/gsd:new-milestone`.*
