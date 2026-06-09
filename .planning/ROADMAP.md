# Agent Brain Roadmap

**Created:** 2026-02-07
**Last updated:** 2026-06-05 — v10.3 MCP v3 milestone scoped (Phases 56-63)
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Active milestone:** v10.3 MCP v3 — CLI-via-MCP + Framework Matrix ([#187](https://github.com/SpillwaveSolutions/agent-brain/issues/187))

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
- 🚧 **v10.3 MCP v3 — CLI-via-MCP + Framework Matrix** — Phases 56-63 (in progress; scope [#187](https://github.com/SpillwaveSolutions/agent-brain/issues/187))

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

## v10.3 MCP v3 — CLI-via-MCP + Framework Matrix

**Goal:** Make the CLI a reference MCP client and validate the MCP server against the major LLM agent frameworks (OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, Autogen).

**Granularity:** standard
**Phase count:** 8 (Phases 56-63)
**v1 requirements:** 23 (1 design + 7 CLI/transport + 3 discovery + 2 hygiene + 7 framework + 3 tooling/docs)
**Coverage:** 23/23 mapped (no orphans, no duplicates)

### Phases (summary checklist)

- [x] **Phase 56: Design doc + CLI backend skeleton** — File the v3 design doc first; land `McpStdioBackend` + `McpHttpBackend` against the `DocServeClient` shape (completed 2026-06-06)
- [x] **Phase 57: CLI transport selector + byte-identical equivalence** — `--transport mcp` + `--mcp-transport stdio|http` wired; results match `--transport uds` byte-for-byte (completed 2026-06-06)
- [x] **Phase 58: Runtime discovery + helper commands** — `mcp.runtime.json` schema + `agent-brain mcp start/stop` with loopback bind, port auto-allocation, psutil verification (completed 2026-06-07)
- [x] **Phase 59: CLI prompts + resources commands** — `agent-brain prompt <name>`, `agent-brain resources list/read <uri>` with sandbox + binary/JSON content handling (completed 2026-06-08)
- [ ] **Phase 60: Subprocess hygiene + 1000-invocation orphan test** — Pinned cwd, env allowlist, SIGTERM/SIGKILL escalation, opt-in stress test
- [ ] **Phase 61: Python framework adapter matrix** — Smoke tests for OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Autogen
- [ ] **Phase 62: TypeScript framework adapter matrix** — Smoke tests for Mastra + Vercel AI SDK in `framework-matrix/ts/`
- [ ] **Phase 63: Tooling + docs + integration page** — `task mcp:framework-matrix`, nightly advisory CI workflow, `docs/INTEGRATIONS.md` with 7 framework pages + 5 config recipes

### Phase Details

### Phase 56: Design doc + CLI backend skeleton
**Goal:** File the v3 design doc so reviewers can challenge the `McpStdioBackend` + `McpHttpBackend` shape BEFORE MCP-layer code lands; then land the BackendClient Protocol + both backend classes as skeletons (non-trivial methods raise NotImplementedError; Phase 57+ wires them).
**Depends on:** v10.2 (Phases 50-55) — needs Streamable HTTP transport + 16-tool MCP surface as the integration target
**Requirements:** DESIGN-V3-01, CLI-MCP-01, CLI-MCP-02
**Success Criteria** (what must be TRUE):
  1. `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` exists, covers CLI backend abstraction + runtime discovery + framework matrix scope, and links from `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` (mirrors v10.2 Phase 50 design-first precedent)
  2. `McpStdioBackend` exposes the full `DocServeClient` surface (query, list_folders, etc.); replacing one for the other inside a unit test passes without code changes (skeleton may raise NotImplementedError for non-trivial methods — signatures must be in place)
  3. `McpHttpBackend` declares the BackendClient Protocol surface for `streamablehttp_client` against a future `agent-brain-mcp --transport http` listener (skeleton; Phase 57 wires real SDK calls)
  4. Both backends pass an `isinstance(backend, BackendClient)` parity assertion against the runtime_checkable Protocol shipped in Plan 02
  5. Skeleton stubs raise NotImplementedError with the literal sentinel "Wired in Phase 57+" so Phase 57 tests can grep for it
**Plans:** 3/3 plans complete
- [ ] 56-01-PLAN.md — File v3 design doc at docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md mirroring v2 doc structure (DESIGN-V3-01; docs-only; design-first gate)
- [ ] 56-02-PLAN.md — Land BackendClient runtime_checkable Protocol in agent_brain_cli/client/protocol.py + isinstance regression test asserting DocServeClient conformance
- [ ] 56-03-PLAN.md — Land McpStdioBackend + McpHttpBackend skeletons in agent_brain_mcp/client.py satisfying BackendClient (CLI-MCP-01, CLI-MCP-02); non-trivial methods raise NotImplementedError("Wired in Phase 57+")

### Phase 57: CLI transport selector + byte-identical equivalence
**Goal:** Wire `--transport mcp` + `--mcp-transport stdio|http` into the Click CLI with explicit selection (no silent fallback, mirroring v10.2 HTTP-03); pin the v3 Definition of Done — byte-identical query results between `--transport mcp` and `--transport uds` for the same backend state.
**Depends on:** Phase 56 (needs both backend classes implemented)
**Requirements:** CLI-MCP-03, CLI-MCP-04
**Success Criteria** (what must be TRUE):
  1. `agent-brain --transport mcp query "X"` succeeds and routes through `McpStdioBackend` by default
  2. `agent-brain --transport mcp --mcp-transport http query "X"` succeeds and routes through `McpHttpBackend`
  3. Invalid combinations (e.g., `--mcp-transport http` without an `--mcp-url` and no `mcp.runtime.json`) fail with a clear error and a non-zero exit code; NO silent fallback to stdio or UDS
  4. Contract test asserts the JSON output of `agent-brain --transport mcp query "X"` equals the output of `agent-brain --transport uds query "X"` byte-for-byte after stripping timestamps + elapsed fields
**Plans:** 3/3 plans complete
- [ ] 57-01-PLAN.md — Wire `--transport mcp` + `--mcp-transport stdio|http` + `--mcp-url` flags, `resolve_mcp_transport` config helper, `open_backend` dispatcher rename + 20-callsite swap (CLI-MCP-03)
- [ ] 57-02-PLAN.md — Wire `query()` on both McpStdioBackend + McpHttpBackend via `stdio_client` / `streamablehttp_client` + the byte-identical-equivalence DoD anchor contract test (CLI-MCP-04)
- [ ] 57-03-PLAN.md — Wire remaining 10 BackendClient methods on both backends per design doc §2.3 mapping table; `reset()` stays NotImplementedError with the verbatim §3.5 wording (CLI-MCP-03 close)

### Phase 58: Runtime discovery + helper commands
**Goal:** Make the MCP HTTP listener self-advertising: define the `mcp.runtime.json` schema, land `agent-brain mcp start` (loopback bind, port auto-allocation, psutil socket-bind verification — reuses v10.2 HTTP-02 pattern), and `agent-brain mcp stop` (SIGTERM/SIGKILL escalation, runtime file cleanup).
**Depends on:** Phase 57 (CLI auto-discovers via `mcp.runtime.json` when `--mcp-url` is omitted)
**Requirements:** CLI-MCP-08, CLI-MCP-09, CLI-MCP-10
**Success Criteria** (what must be TRUE):
  1. `agent-brain mcp start` launches `agent-brain-mcp --transport http` as a background process on a free loopback port and writes `<state_dir>/mcp.runtime.json` with `{host, port, pid, started_at, transport}` only AFTER the listener is verifiably accepting connections (psutil socket-bind check)
  2. `agent-brain --transport mcp --mcp-transport http query "X"` with no `--mcp-url` reads `mcp.runtime.json` and connects successfully
  3. `agent-brain mcp stop` reads `mcp.runtime.json`, sends SIGTERM, escalates to SIGKILL after a configurable grace period, and removes `mcp.runtime.json` on clean exit (or after SIGKILL)
  4. Concurrent `agent-brain mcp start` invocations against an already-running instance fail fast with a clear "already running on port N" error and a non-zero exit code (no double-bind, no orphan)
**Plans:** 3/3 plans complete
- [ ] 58-01-PLAN.md — mcp_runtime.py shared helpers + psutil verifier + 0o600 perms + psutil dep added to agent-brain-cli (CLI-MCP-08 prereq foundation)
- [ ] 58-02-PLAN.md — agent-brain mcp start Click sub-group: port allocation, lock acquisition, detached Popen with start_new_session=True, psutil-verified write of mcp.runtime.json (CLI-MCP-09)
- [ ] 58-03-PLAN.md — agent-brain mcp stop (os.killpg SIGTERM grace SIGKILL cleanup) + McpHttpBackend.__init__ discovery + resolve_mcp_transport section 3.5 wording swap + end-to-end integration test (CLI-MCP-08 close + CLI-MCP-10)

### Phase 59: CLI prompts + resources commands
**Goal:** Expose the MCP `prompts/get` + `resources/list` + `resources/read` surfaces via human-friendly CLI commands. Operators can invoke any of the 6 v1 prompts, enumerate all static + templated URIs, and read content with correct sandboxing and binary/JSON content-type handling.
**Depends on:** Phase 57 (uses `McpStdioBackend` + `McpHttpBackend`)
**Requirements:** CLI-MCP-05, CLI-MCP-06, CLI-MCP-07
**Success Criteria** (what must be TRUE):
  1. `agent-brain prompt <name>` expands and prints any of the 6 v1 prompts (`audit_indexed_folders`, `compare_search_modes`, `explain_architecture`, `find_callers`, `find_implementation`, `onboard_to_codebase`); unknown names exit non-zero with the available list in the error
  2. `agent-brain resources list` enumerates all 5 static URIs + 4 templated URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`) with their mime types
  3. `agent-brain resources read <uri>` calls MCP `resources/read` and prints content with correct content-type handling: JSON pretty-printed, text passed through, binary blobs surfaced as a base64 marker or `--output-file` redirect (no raw bytes to stdout)
  4. `agent-brain resources read file:///disallowed/path` is rejected with the same `outside_indexed_roots` reason the MCP server returns (sandbox respected at the CLI layer too)
**Plans:** 3/3 plans complete
- [ ] 59-01-PLAN.md — McpBackend Protocol + 5 skeleton methods on both backends + open_mcp_backend factory + isinstance pinning (CLI-MCP-05 foundation)
- [ ] 59-02-PLAN.md — Wire 5 methods on both backends via asyncio.run Pattern A + agent-brain prompt command with --arg KEY=VALUE multi + --json flag + unknown-name handling (CLI-MCP-05)
- [ ] 59-03-PLAN.md — agent-brain resources Click sub-group (list + read) with content-type dispatch + end-to-end integration test covering all 4 ROADMAP SCs including file:// sandbox rejection (CLI-MCP-06 + CLI-MCP-07)

### Phase 60: Subprocess hygiene + 1000-invocation orphan test
**Goal:** Lock MCP stdio subprocess hygiene as a contract BEFORE the framework matrix lands — pinned cwd (no `cwd=None` inheritance), env sanitized to an explicit allowlist (drop API keys unless explicitly forwarded), SIGTERM → SIGKILL escalation with configurable grace, and an opt-in 1000-invocation pgrep test proving no orphans survive a tight tear-down loop.
**Depends on:** Phase 57 (extends `McpStdioBackend` subprocess management)
**Requirements:** MCPHYG-01, MCPHYG-02
**Success Criteria** (what must be TRUE):
  1. `McpStdioBackend.__init__` pins `cwd` to an explicit value (never `cwd=None`) and filters `env` through a documented allowlist; `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` are NOT propagated unless explicitly opted in via constructor arg
  2. `McpStdioBackend.close()` sends SIGTERM, waits `grace_period_s` (configurable, default ≤5s), then escalates to SIGKILL; the grace period is honored by a unit test using a stub child that ignores SIGTERM
  3. `task mcp:stress:orphan-test` drives `McpStdioBackend` through 1000 query→close cycles in a tight loop; `pgrep -f agent-brain-mcp` returns no surviving PIDs after each tear-down (asserted per-iteration); the task is opt-in (NOT in `task before-push` — slow) and surfaces leak counts in the failure message
  4. Phase 61 + 62 framework tests inherit the hygiene contract automatically by going through `McpStdioBackend` rather than spawning raw subprocesses
**Plans:** 2/3 plans executed
- [x] 60-01-PLAN.md — DEFAULT_ENV_ALLOWLIST module constant + McpStdioBackend.__init__ extended with env_allowlist/forward_env/grace_period_s kwargs + cwd snapshot/validation (MCPHYG-01 foundation half)
- [x] 60-02-PLAN.md — Hygienic stdio_client wrapper + weakref/threading.Lock in-flight tracker + close() SIGTERM→SIGKILL escalation + SIGTERM-ignoring stub child fixture (MCPHYG-01 close() half)
- [ ] 60-03-PLAN.md — agent-brain-mcp/tests/stress/test_orphan_subprocess.py @pytest.mark.stress + psutil children delta primary assert + pgrep diagnostic + task mcp:stress:orphan-test target (MCPHYG-02)

### Phase 61: Python framework adapter matrix
**Goal:** Validate the MCP server against the 5 Python LLM agent frameworks via smoke tests that each connect, call `search_documents`, and assert non-empty results. SDK versions pinned in `framework-matrix/requirements.txt` to control churn.
**Depends on:** Phase 60 (every test goes through hygienic `McpStdioBackend` to avoid re-discovering orphan-process bugs); v10.2 (16-tool MCP surface as the integration target)
**Requirements:** FRAME-01, FRAME-02, FRAME-03, FRAME-04, FRAME-05
**Success Criteria** (what must be TRUE):
  1. OpenAI Agents SDK adapter smoke test connects via both `MCPServerStdio` AND `MCPServerStreamableHttp`, calls `search_documents`, and asserts a non-empty result list
  2. LangChain, LlamaIndex, Pydantic AI, and Autogen (AG2) each have a smoke test that connects to `agent-brain-mcp`, calls `search_documents`, and asserts a non-empty result list
  3. `framework-matrix/requirements.txt` (or per-framework venvs) pins every SDK version with a comment noting the source URL and pin date; running the suite produces no `pip install` upgrade messages
  4. Each smoke test runs in <30s in isolation (tight tear-down via Phase 60 hygiene); zero orphan subprocesses survive between frameworks
**Plans:** TBD

### Phase 62: TypeScript framework adapter matrix
**Goal:** Mirror Phase 61 for the 2 TypeScript frameworks under a separate `framework-matrix/ts/` harness (node + pnpm/npm), sharing a single subprocess fixture where possible. Mastra + Vercel AI SDK smoke tests connect, call `search_documents`, assert non-empty results.
**Depends on:** Phase 60 (subprocess hygiene contract); Phase 61 (matrix layout precedent)
**Requirements:** FRAME-06, FRAME-07
**Success Criteria** (what must be TRUE):
  1. `framework-matrix/ts/` exists with `package.json`, pinned SDK versions, and a single MCP subprocess fixture shared by both Mastra + Vercel AI SDK tests
  2. Mastra adapter smoke test (`@mastra/mcp`) connects to `agent-brain-mcp`, calls `search_documents`, and asserts a non-empty result list
  3. Vercel AI SDK adapter smoke test (`experimental_createMCPClient`) connects to `agent-brain-mcp`, calls `search_documents`, and asserts a non-empty result list
  4. Both TS tests run with a single `npm test` (or `pnpm test`) invocation; failures fingerprint cleanly to per-framework error messages (not opaque node tracebacks)
**Plans:** TBD

### Phase 63: Tooling + docs + integration page
**Goal:** Land the operator-facing surface for v10.3: a Taskfile target that runs the full 7-framework matrix opt-in, a nightly advisory CI workflow on `main`, and `docs/INTEGRATIONS.md` with one short page per framework PLUS a "config recipes" section for 5 editor-side integrations (Goose, Continue.dev, Cline, Cursor, Cody) that ship docs-only in v10.3.
**Depends on:** Phase 61 + Phase 62 (needs the actual smoke tests to wire into the task target and CI)
**Requirements:** TOOLING-V3-01, TOOLING-V3-02, DOCS-V3-01
**Success Criteria** (what must be TRUE):
  1. `task mcp:framework-matrix` runs all 7 framework smoke tests sequentially with per-framework setup/teardown; gated behind `FRAMEWORK_MATRIX=1` env or explicit `--force`; documented as slow + opt-in in the Taskfile and `docs/INTEGRATIONS.md`
  2. `.github/workflows/framework-matrix.yml` runs `task mcp:framework-matrix` against `main` on a nightly cron; failure does NOT block PRs (advisory only — framework drift is expected); job results published as a GitHub status check tagged `advisory`
  3. `docs/INTEGRATIONS.md` ships with one short copy-pasteable page per framework (server command, transport, capabilities) for all 7 smoke-tested frameworks PLUS a separate "config recipes" section for Goose, Continue.dev, Cline, Cursor, and Cody (config-only, no smoke test in v10.3)
  4. `docs/INTEGRATIONS.md` includes a SDK-pinning note pointing at `framework-matrix/requirements.txt` (and the TS equivalent) so operators know how to align their environment with the tested versions
**Plans:** TBD

### Notes

- **Open scope question (deferred to `/gsd:discuss-phase` 61):** Whether to fold v9.6.0 Runtime Parity Phases 47-49 (headless Codex/OpenCode/Gemini execution verification) into v10.3 as a parallel track. The framework matrix work already exercises external CLIs, so the surface overlaps — decision deferred to discuss-phase 61 (framework matrix); the surface overlaps if we unpark.
- **Phase 56 design-first precedent:** Design doc MUST land before Phase 57+ MCP code (v2 Phase 50 precedent — reviewers challenge the shape BEFORE implementation).
- **Phase 60 hygiene-before-frameworks ordering:** Phase 60 subprocess hygiene MUST land before Phase 61 framework matrix so framework smoke tests inherit the hygiene contract automatically (avoiding every framework test re-discovering orphan-process bugs independently).
- **Framework SDK churn risk:** SDK versions pinned in `framework-matrix/requirements.txt` (Python) and `framework-matrix/ts/package.json` (TS); called out in DOCS-V3-01. Nightly CI is advisory only (TOOLING-V3-02) — framework drift is expected and does not block PRs.
- **Loopback-only stays:** v10.3 keeps the loopback-only HTTP transport; OAuth 2.1 for remote MCP is held for v10.4 ([#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188)) which depends on v10.3's `McpHttpBackend`.

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
| 60. Subprocess hygiene + 1000-invocation orphan test        | 1/3 | In Progress|  | -          |
| 61. Python framework adapter matrix                         | v10.3     | 0/TBD          | Not started | -          |
| 62. TypeScript framework adapter matrix                     | v10.3     | 0/TBD          | Not started | -          |
| 63. Tooling + docs + integration page                       | v10.3     | 0/TBD          | Not started | -          |

---
*Roadmap created: 2026-02-07*
*Last updated: 2026-06-08 — Phase 59 planned (3 plans: McpBackend Protocol + skeletons + factory; wire 5 methods + agent-brain prompt; agent-brain resources sub-group + e2e). Next: `/gsd:execute-phase 59` to ship Wave 1 (59-01).*
