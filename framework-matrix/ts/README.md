# Framework Matrix — Phase 62 TypeScript Framework Adapter Tests

This directory contains the **Phase 62 TypeScript framework adapter matrix**: opt-in smoke
tests that validate `agent-brain-mcp` as an MCP server against two major TypeScript/JavaScript
AI SDK frameworks.

## What is this?

Each test connects to a live `agent-brain-mcp` server (over stdio), calls the
`search_documents` tool, and asserts a non-empty result list. This is a
**connectivity/contract proof** — not a test of any LLM model. No model API keys are
required for the MCP tool call itself; `OPENAI_API_KEY` is only needed by
`agent-brain-serve` to embed the corpus on first index.

## Tested Frameworks

| Framework | Package | Adapter primitive | Requirement |
|-----------|---------|-------------------|-------------|
| Mastra | `@mastra/mcp` | `MCPClient` stdio constructor | FRAME-06 |
| Vercel AI SDK | `@ai-sdk/mcp` | `createMCPClient` + `Experimental_StdioMCPTransport` | FRAME-07 |

Both tests land in Plan 62-02. This plan (62-01) ships the shared foundation scaffold.

## Framework Tests (Plan 62-02)

Both tests closed in Plan 62-02 use the shared seeded server from globalSetup.

### FRAME-06: Mastra (`test/mastra.test.ts`)

- Package: `@mastra/mcp` 1.9.1 (`MCPClient` stdio constructor)
- Flow: `MCPClient({ servers: { agentBrain: { command, args, env } } })` →
  `listToolsets()` → assert `search_documents` present → `tool.execute(SMOKE_ARGS)` →
  `assertNonEmptySearch(result)` → `disconnect()`
- Teardown method: `client.disconnect()`

### FRAME-07: Vercel AI SDK (`test/vercel-ai-sdk.test.ts`)

- Package: `@ai-sdk/mcp` 1.0.48 (`createMCPClient` / `experimental_createMCPClient`)
- Transport: `StdioClientTransport({ command, args, env })` from
  `@modelcontextprotocol/sdk/client/stdio.js`
- Flow: `experimental_createMCPClient({ transport })` → `client.tools()` →
  assert `search_documents` present → `tool.execute(SMOKE_ARGS)` →
  `assertNonEmptySearch(result)` → `close()`
- Package deviation: The plan referenced `experimental_createMCPClient` from `ai`.
  The stable API is `createMCPClient` in `@ai-sdk/mcp`, which also exports
  `experimental_createMCPClient` as an alias. The `ai` package is NOT installed.
  See `PINS.md` and `62-01-SUMMARY.md` for the full deviation rationale.

### Running both with a single command

```bash
# From framework-matrix/ts/ — runs ALL 4 test files in one invocation:
pnpm test
# Output: mastra.test.ts + vercel-ai-sdk.test.ts + corpus.test.ts + isolation.test.ts
```

Without `OPENAI_API_KEY` / binaries: the server-dependent tests skip gracefully
(the skip reason is logged: `[mastra] SKIPPED: ...` / `[vercel-ai-sdk] SKIPPED: ...`).
`corpus.test.ts` (32 tests) and `isolation.test.ts` (8 tests) always pass.

### Failure fingerprinting (`src/fingerprint.ts`)

All five stages of each framework test are wrapped via `stage(framework, stageLabel, fn)`.
A failure surfaces as:

```
[mastra] connect failed: <original error>
[mastra] list-tools failed: ...
[mastra] call failed: ...
[mastra] assert failed: ...
[mastra] disconnect failed: ...

[vercel-ai-sdk] connect failed: <original error>
[vercel-ai-sdk] list-tools failed: ...
... (same pattern)
```

NOT opaque Node stack traces — Success Criterion 4 of the Phase 62 ROADMAP.
Stages include `disconnect` so teardown failures also fingerprint cleanly.

## Tests are OPT-IN (NOT in `task before-push`)

The TypeScript suite does **NOT** run in `task before-push` or the PR gate. It is
opt-in: run explicitly with `pnpm test` from this directory. The Taskfile operator
target and nightly CI workflow land in **Phase 63** — this phase ships the harness
and foundation only.

Never include `framework-matrix/ts/` in any package's `testpaths` or default pytest
`addopts`, and never add a `pnpm`/`vitest` step to the root `Taskfile.yml`
`before-push` chain.

## Prerequisites

- **pnpm** — install via `corepack enable pnpm` (Node 16.9+)
- **`agent-brain-serve`** on PATH — install `agent-brain-rag` into your Python environment
- **`agent-brain-mcp`** on PATH — install `agent-brain-ag-mcp` into your Python environment
- **`OPENAI_API_KEY`** — required for corpus embedding on first index

When any prerequisite is missing, the global setup detects it and skips the
server-dependent tests gracefully. The server-free unit test (`corpus.test.ts`) always
runs.

## Bootstrap and Run

```bash
# From this directory (framework-matrix/ts/):
pnpm install          # Install exact-pinned dependencies (generates pnpm-lock.yaml)
pnpm test             # Run all tests (vitest run)

# Watch mode for development:
pnpm test:watch
```

## Architecture

- `src/corpus.ts` — Phase 61 smoke contract constants (`SMOKE_TOOL`, `SMOKE_QUERY`,
  `SMOKE_ARGS`, `FRAMEWORK_CORPUS`) + `assertNonEmptySearch` (5-shape normalizer).
  Mirrors `framework-matrix/_harness.py` byte-for-byte.
- `src/harness.ts` — shared MCP subprocess fixture: `startSeededServer` (seeds
  agent-brain-serve with the tiny corpus), `stdioServerParams` (stdio launch spec for
  both framework tests), `terminate` (SIGTERM→grace→SIGKILL teardown), `findFreePort`,
  `prerequisitesAvailable`, `killStrayMcp`.
- `src/globalSetup.ts` — vitest global setup that runs ONCE per `pnpm test`. Checks
  prerequisites; if ok, spawns + seeds `agent-brain-serve` and sets
  `process.env.AB_FWM_STATE_DIR` for both framework tests.
- `test/corpus.test.ts` — server-free unit test of `assertNonEmptySearch` across all
  5 result shapes. Passes on any machine (no server, no OPENAI_API_KEY needed).
- `test/isolation.test.ts` — enforces that this TS suite is absent from the Python
  `before-push` chain (reads the 4 package pyproject.toml files + root Taskfile and
  asserts none contains `framework-matrix/ts`).

## Dependency Pins

All dependencies are **exact-pinned** (no `^` or `~` ranges). See `PINS.md` for the
full pin manifest with source URLs and the date pinned.

## Phase Notes

- **Phase 61**: Python framework matrix (`framework-matrix/`) — OpenAI Agents SDK,
  LangChain, LlamaIndex, Pydantic AI, Autogen.
- **Phase 62**: TypeScript framework matrix (this directory) — Mastra, Vercel AI SDK.
- **Phase 63**: Operator Taskfile target + nightly CI workflow.

## Canonical References

- Python harness analogue: `framework-matrix/_harness.py` + `framework-matrix/conftest.py`
- Phase 61 decisions: `.planning/phases/61-python-framework-adapter-matrix/61-01-SUMMARY.md`
- Phase 62 context: `.planning/phases/62-typescript-framework-adapter-matrix/62-CONTEXT.md`
