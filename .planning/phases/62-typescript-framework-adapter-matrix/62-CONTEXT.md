# Phase 62: TypeScript framework adapter matrix - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning
**Source:** plan-phase inline decisions (research disabled at config; mirrors Phase 61 planning path)

<domain>
## Phase Boundary

Mirror the just-completed Phase 61 (Python framework adapter matrix) for the **2 TypeScript
frameworks** under a **separate `framework-matrix/ts/` harness** (Node + pnpm). Two smoke tests —
**Mastra** (`@mastra/mcp`) and **Vercel AI SDK** (`experimental_createMCPClient`) — each connect to
`agent-brain-mcp`, call the `search_documents` tool, and assert a non-empty result list.

In scope:
- `framework-matrix/ts/` Node project (`package.json`, `tsconfig.json`, pinned SDK versions)
- A SINGLE shared MCP subprocess fixture consumed by both framework tests
- Two opt-in smoke tests (Mastra, Vercel AI SDK) following connect → call `search_documents` → assert non-empty
- Per-framework README docs (mirror Phase 61 subdir READMEs)

Out of scope:
- Any change to the Python `framework-matrix/` harness (Phase 61, complete)
- The `task mcp:framework-matrix` task target + nightly CI + `docs/INTEGRATIONS.md` (those are Phase 63)
- Wiring the TS suite into `task before-push` (opt-in only, exactly like Phase 61's `framework` marker)
- LLM/model-provider calls — tests are KEYLESS, exercising only the MCP tool surface

</domain>

<decisions>
## Implementation Decisions

### Toolchain (LOCKED — user decision 2026-06-11)
- **Package manager: pnpm** — pin via `package.json` `"packageManager": "pnpm@<exact>"`; assume corepack/pnpm available on PATH. Document the pnpm requirement in the `ts/README.md`.
- **Test runner: vitest** — `"scripts": { "test": "vitest run" }`; single `pnpm test` runs BOTH framework tests (SC4).
- **Language: TypeScript** via vitest's native ESM/TS support (`typescript`, `@types/node` as devDeps); no separate compile step required for tests.

### Harness layout (mirror Phase 61 precedent)
- Root: `framework-matrix/ts/` — sibling to the Python framework dirs, NOT nested inside them.
- A **single shared MCP subprocess fixture** (e.g. `framework-matrix/ts/src/harness.ts` or a vitest
  setup/helper) that spawns `agent-brain-mcp` over stdio ONCE and is consumed by both tests — satisfies
  SC1's "single MCP subprocess fixture shared by both Mastra + Vercel AI SDK tests".
- Reuse the Phase 61 tiny keyless corpus concept: index a small fixture corpus containing the
  `authenticate` token so `search_documents` returns non-empty deterministically. Prefer reusing the
  EXISTING seeded-server approach over inventing a new corpus — share the Python `_harness.py`
  `FRAMEWORK_CORPUS` shape / `SMOKE_QUERY` / `SMOKE_TOOL` / `SMOKE_ARGS` values so Python and TS assert
  against the same fixture data.

### Subprocess hygiene (inherit Phase 60 contract)
- Spawn the MCP server child via a hygienic pattern with **SIGTERM → grace wait → SIGKILL** teardown in
  the fixture's `afterAll`/teardown — mirror the Phase 60 / Phase 61 `conftest.py` teardown so zero
  orphan subprocesses survive between the two TS tests.

### Pins (mirror Phase 61 requirements.txt discipline)
- Every dependency in `package.json` exact-pinned (no `^`/`~` ranges) with a comment or companion note
  recording the **source URL + pin date** (`pinned: 2026-06-11`). Lockfile (`pnpm-lock.yaml`) committed.
- Pin at minimum: `@mastra/mcp`, `ai` (Vercel AI SDK) + any required `@ai-sdk/*` MCP client pieces,
  `@modelcontextprotocol/sdk` (transport), `vitest`, `typescript`, `@types/node`.

### Opt-in isolation (mirror Phase 61 `framework` marker)
- The TS suite MUST NOT run in `task before-push` or any Python pytest collection. It runs ONLY via an
  explicit `pnpm test` (or a future Phase 63 `task mcp:framework-matrix` target). Verify the TS dir is
  absent from all 4 package pyprojects + root Taskfile default paths.

### Failure fingerprinting (SC4)
- Test failures must surface a clean per-framework error message (which framework, which step: connect /
  list-tools / call / assert) — NOT an opaque Node stack trace. Wrap the connect→call→assert flow so the
  thrown assertion identifies the framework + stage.

### Claude's Discretion
- Exact vitest config (`vitest.config.ts`) shape, fixture file naming, and whether the shared fixture is
  a vitest global-setup vs an imported helper invoked in each test's `beforeAll`.
- Exact mechanism for spawning + readiness-polling the MCP server in Node (stdio vs the `agent-brain mcp
  start` HTTP listener) — prefer stdio for parity with Phase 61's default and tightest teardown.
- How to seed/index the corpus from Node (reuse an existing seeded-server helper vs a small index step).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 61 precedent (the pattern to mirror)
- `framework-matrix/README.md` — matrix layout + opt-in contract + bootstrap usage
- `framework-matrix/_harness.py` — `FRAMEWORK_CORPUS`, `SMOKE_QUERY` / `SMOKE_TOOL` / `SMOKE_ARGS`,
  `assert_non_empty_search` result-shape normalizer, `assert_no_orphans` — replicate the SAME smoke
  query/tool/args + corpus tokens in TS
- `framework-matrix/conftest.py` — seeded MCP server fixture + `http_mcp_listener` factory + SIGTERM
  teardown + session-autouse orphan guard (the hygiene pattern to mirror in TS)
- `framework-matrix/pytest.ini` — opt-in `framework` marker absent from before-push (the isolation
  precedent the TS suite must mirror)
- `framework-matrix/openai-agents/test_openai_agents_smoke.py` — closest analogue: an SDK that speaks MCP
  over stdio + HTTP, connect → call `search_documents` → `assert_non_empty_search`
- `.planning/phases/61-python-framework-adapter-matrix/61-01-SUMMARY.md` through `61-04-SUMMARY.md` —
  the as-built decisions (pin format, teardown contract, factory-fixture refactor)

### Subprocess hygiene contract (Phase 60)
- `agent-brain-mcp/agent_brain_mcp/client.py` — `McpStdioBackend` env allowlist + cwd pinning +
  `close()` SIGTERM→grace→SIGKILL escalation (the hygiene contract the TS fixture mirrors conceptually)

### Roadmap / requirements
- `.planning/ROADMAP.md` — Phase 62 section (goal, 4 success criteria, FRAME-06/07)
- `.planning/REQUIREMENTS.md` — FRAME-06, FRAME-07 definitions

</canonical_refs>

<specifics>
## Specific Ideas

- Requirements: **FRAME-06** (Mastra `@mastra/mcp`), **FRAME-07** (Vercel AI SDK
  `experimental_createMCPClient`).
- `pnpm test` is the single entry point that runs both tests (SC4).
- Keep the same smoke contract values as Phase 61 (`search_documents` tool, the `authenticate`-bearing
  tiny corpus) so the Python and TS matrices assert against identical fixture data.

</specifics>

<deferred>
## Deferred Ideas

- `task mcp:framework-matrix` task target, nightly advisory CI workflow, and `docs/INTEGRATIONS.md`
  (7 framework pages + 5 config recipes) — all explicitly **Phase 63**.

</deferred>

---

*Phase: 62-typescript-framework-adapter-matrix*
*Context gathered: 2026-06-11 via plan-phase inline decisions (pnpm + vitest locked by user)*
