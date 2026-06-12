---
phase: 62-typescript-framework-adapter-matrix
plan: "01"
subsystem: framework-matrix/ts
tags: [typescript, vitest, pnpm, mcp, mastra, vercel-ai-sdk, harness, scaffold]
dependency_graph:
  requires:
    - "61-01: framework-matrix/_harness.py + conftest.py (values mirrored byte-for-byte)"
    - "60-02: SIGTERM->grace->SIGKILL teardown contract"
  provides:
    - "framework-matrix/ts/ scaffold with pnpm + vitest + TypeScript"
    - "src/corpus.ts: FRAMEWORK_CORPUS + SMOKE_TOOL/QUERY/ARGS + assertNonEmptySearch (5-shape)"
    - "src/harness.ts: findFreePort + startSeededServer + stdioServerParams + terminate + killStrayMcp"
    - "src/globalSetup.ts: vitest global setup with AB_FWM_STATE_DIR canonical handoff"
    - "test/corpus.test.ts: 32 server-free unit tests covering full 5-shape contract"
    - "test/isolation.test.ts: enforces TS suite absent from Python before-push chain"
  affects:
    - "Plan 62-02: Mastra + Vercel AI SDK smoke tests consume this harness"
    - "Phase 63: Taskfile target + nightly CI workflow build on this foundation"
tech_stack:
  added:
    - "pnpm 10.12.4 (packageManager pin)"
    - "vitest 4.1.8 (test runner)"
    - "typescript 6.0.3"
    - "@types/node 25.9.3"
    - "@mastra/mcp 1.9.1 (FRAME-06)"
    - "@ai-sdk/mcp 1.0.48 (FRAME-07)"
    - "@modelcontextprotocol/sdk 1.29.0"
    - "zod 4.4.3"
  patterns:
    - "TDD red-green cycle for corpus.test.ts"
    - "vitest globalSetup with process.env canonical handoff (AB_FWM_STATE_DIR)"
    - "SIGTERM->grace(10s server/5s child)->SIGKILL teardown (Phase 60 contract)"
    - "Proxy-based extraction-error tolerance test"
key_files:
  created:
    - framework-matrix/ts/package.json
    - framework-matrix/ts/pnpm-lock.yaml
    - framework-matrix/ts/tsconfig.json
    - framework-matrix/ts/vitest.config.ts
    - framework-matrix/ts/README.md
    - framework-matrix/ts/PINS.md
    - framework-matrix/ts/src/corpus.ts
    - framework-matrix/ts/src/harness.ts
    - framework-matrix/ts/src/globalSetup.ts
    - framework-matrix/ts/test/corpus.test.ts
    - framework-matrix/ts/test/isolation.test.ts
  modified: []
decisions:
  - "pnpm 10.12.4 pinned (resolved 2026-06-11 via pnpm --version)"
  - "@ai-sdk/mcp 1.0.48 used (not the ai package): plan referenced experimental_createMCPClient from ai package but current stable API is createMCPClient from @ai-sdk/mcp; PINS.md documents this"
  - "globalSetup exports async default function (not setup/teardown tuple) — vitest v2+ accepts return teardown function directly"
  - "TOLERANCE test uses JavaScript Proxy with throwing getter to simulate extraction exceptions faithfully (NaN from Number() does not throw in TS)"
  - "5000ms grace documented in harness.ts docstrings; 10000ms used at both globalSetup teardown and startSeededServer error-path cleanup"
metrics:
  duration: "13m"
  completed: "2026-06-12"
  tasks_completed: 3
  tests_passed: 40
  files_created: 11
---

# Phase 62 Plan 01: TypeScript Framework Matrix Scaffold Summary

One-liner: pnpm + vitest + TypeScript scaffold for agent-brain-mcp framework
adapter matrix with Phase 61-parity corpus contract, shared MCP subprocess
fixture, and server-free 5-shape assertNonEmptySearch unit test.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Scaffold pnpm + vitest + TypeScript with exact-pinned deps | ad130f2 | package.json, pnpm-lock.yaml, tsconfig.json, vitest.config.ts, README.md, PINS.md |
| 2 (TDD RED) | Failing test for assertNonEmptySearch 5-shape contract | a256652 | test/corpus.test.ts (32 tests), src/globalSetup.ts (placeholder) |
| 2 (TDD GREEN) | Port Phase 61 corpus contract + shared MCP fixture | f010192 | src/corpus.ts, src/harness.ts, src/globalSetup.ts (full) |
| 3 | Prove opt-in isolation from before-push chain | 6590103 | test/isolation.test.ts |

## Exact Pinned Versions

All versions resolved 2026-06-11 via `npm view <pkg> version`:

| Package | Version | Source URL |
|---------|---------|------------|
| pnpm | 10.12.4 | https://www.npmjs.com/package/pnpm/v/10.12.4 |
| vitest | 4.1.8 | https://www.npmjs.com/package/vitest/v/4.1.8 |
| typescript | 6.0.3 | https://www.npmjs.com/package/typescript/v/6.0.3 |
| @types/node | 25.9.3 | https://www.npmjs.com/package/@types/node/v/25.9.3 |
| @mastra/mcp | 1.9.1 | https://www.npmjs.com/package/@mastra/mcp/v/1.9.1 |
| @ai-sdk/mcp | 1.0.48 | https://www.npmjs.com/package/@ai-sdk/mcp/v/1.0.48 |
| @modelcontextprotocol/sdk | 1.29.0 | https://www.npmjs.com/package/@modelcontextprotocol/sdk/v/1.29.0 |
| zod | 4.4.3 | https://www.npmjs.com/package/zod/v/4.4.3 |

## Resolved pnpm Version

pnpm `10.12.4` — resolved via `pnpm --version` at execution time.

## Shared-Fixture Mechanism

`src/globalSetup.ts` is a vitest global setup that runs ONCE per `pnpm test`:

1. Calls `prerequisitesAvailable()` — checks `OPENAI_API_KEY` + `agent-brain-serve` + `agent-brain-mcp` on PATH.
2. If NOT ok: leaves `AB_FWM_STATE_DIR` UNSET, returns a no-op teardown. All server-dependent tests in 62-02 will skip; `corpus.test.ts` runs server-free.
3. If ok: creates `mkdtempSync(join(tmpdir(), "abfwm-"))` (short prefix dodges macOS 104-char AF_UNIX socket-path limit), calls `startSeededServer(stateDir)` to spawn + seed `agent-brain-serve`.
4. ALWAYS sets `process.env.AB_FWM_STATE_DIR = stateDir` — the mandatory canonical handoff both Plan 62-02 tests read.
5. Returns teardown: `terminate(serverChild, 10000)` (10s SERVER grace, mirrors conftest.py's `proc.wait(timeout=10)`) then `killStrayMcp()`.

The actual stdio `agent-brain-mcp` connections are opened per-test in 62-02 via `stdioServerParams(process.env.AB_FWM_STATE_DIR)`.

## task before-push Pass/Deselect Counts

```
task before-push (run from repo root, 2026-06-12):
  544 passed, 111 deselected, 7 warnings
```

Unchanged from the Phase 61-01 baseline (544 passed, 111 deselected). The new TS subtree changed nothing pytest collects — confirmed by the isolation test.

## server-free corpus.test.ts Result

```
pnpm vitest run test/corpus.test.ts:
  Test Files  1 passed (1)
      Tests  32 passed (32)
  Duration  ~200ms
```

No OPENAI_API_KEY or agent-brain-serve/mcp required.

## pnpm test (both test files)

```
pnpm test (from framework-matrix/ts/):
  Test Files  2 passed (2)
      Tests  40 passed (40)
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Vercel AI SDK package reference**

- **Found during:** Task 1 dependency resolution
- **Issue:** Plan referenced `ai` (Vercel AI SDK main package) as exporting `experimental_createMCPClient`. The current stable API (1.0.48) is `createMCPClient` from `@ai-sdk/mcp`, not the `ai` package. The `experimental_` prefix was dropped in the stable release.
- **Fix:** Added `@ai-sdk/mcp 1.0.48` as the dependency (which exports `createMCPClient` + `Experimental_StdioMCPTransport` from `@ai-sdk/mcp/mcp-stdio`). Documented in PINS.md with explanation. The `ai` package is not added as a standalone dep — Plan 62-02 will import from `@ai-sdk/mcp` directly.
- **Files modified:** framework-matrix/ts/package.json, framework-matrix/ts/PINS.md
- **Commit:** ad130f2

**2. [Rule 1 - Bug] TOLERANCE test approach for TypeScript**

- **Found during:** Task 2 TDD (2 tests failed after GREEN implementation)
- **Issue:** Two tolerance tests used literal objects like `{ structuredContent: "not a dict" }` and `{ structuredContent: { total_results: "not-a-number-but-non-null" } }`. In TypeScript, `Number("not-a-number-but-non-null")` returns `NaN` (does NOT throw), so `_countPayload` returns 0 cleanly — these objects don't trigger the extraction-exception tolerance branch. The tests were asserting the wrong behavior.
- **Fix:** Replaced with Proxy-based tests that throw on property access, accurately simulating the extraction-exception scenario the Python `except` block catches. Added clear JSDoc explaining the distinction between "extraction throws" (tolerance) vs "extractor returns 0" (not tolerance).
- **Files modified:** framework-matrix/ts/test/corpus.test.ts
- **Commit:** a256652 (test), f010192 (implementation)

## Self-Check: PASSED

Files exist:
- [x] framework-matrix/ts/package.json
- [x] framework-matrix/ts/pnpm-lock.yaml
- [x] framework-matrix/ts/tsconfig.json
- [x] framework-matrix/ts/vitest.config.ts
- [x] framework-matrix/ts/README.md
- [x] framework-matrix/ts/PINS.md
- [x] framework-matrix/ts/src/corpus.ts
- [x] framework-matrix/ts/src/harness.ts
- [x] framework-matrix/ts/src/globalSetup.ts
- [x] framework-matrix/ts/test/corpus.test.ts
- [x] framework-matrix/ts/test/isolation.test.ts

Commits exist:
- [x] ad130f2 (Task 1 scaffold)
- [x] a256652 (Task 2 TDD RED)
- [x] f010192 (Task 2 TDD GREEN)
- [x] 6590103 (Task 3 isolation)
