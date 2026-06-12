---
phase: 62-typescript-framework-adapter-matrix
verified: 2026-06-12T00:00:00Z
status: passed
score: 4/4 success criteria verified
re_verification: false
---

# Phase 62: TypeScript Framework Adapter Matrix Verification Report

**Phase Goal:** Mirror Phase 61 for the 2 TypeScript frameworks under a separate `framework-matrix/ts/` harness (node + pnpm), sharing a single subprocess fixture where possible. Mastra + Vercel AI SDK smoke tests connect, call `search_documents`, assert non-empty results.
**Verified:** 2026-06-12
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `framework-matrix/ts/` exists with `package.json`, pinned SDK versions, and a SINGLE shared MCP subprocess fixture (globalSetup) consumed by both tests | VERIFIED | All 14 required files git-tracked; `package.json` has `"packageManager": "pnpm@10.12.4"`, all deps exact-pinned (no `^`/`~`), `pnpm-lock.yaml` committed; `src/globalSetup.ts` seeds server ONCE and sets `process.env.AB_FWM_STATE_DIR` as canonical handoff |
| 2 | Mastra adapter smoke test (`@mastra/mcp`) connects to `agent-brain-mcp`, calls `search_documents`, asserts non-empty | VERIFIED | `test/mastra.test.ts` imports `MCPClient` from `@mastra/mcp`, calls `stdioServerParams`, wraps all 5 stages (`connect`, `list-tools`, `call`, `assert`, `disconnect`) via `stage("mastra", ...)`, calls `assertNonEmptySearch(result)` |
| 3 | Vercel AI SDK adapter smoke test connects to `agent-brain-mcp`, calls `search_documents`, asserts non-empty | VERIFIED | `test/vercel-ai-sdk.test.ts` imports `experimental_createMCPClient` from `@ai-sdk/mcp` (legitimate deviation — same symbol, correct stable package), uses `StdioClientTransport`, wraps all 5 stages via `stage("vercel-ai-sdk", ...)`, calls `assertNonEmptySearch(result)` |
| 4 | Both TS tests run with a single `pnpm test`; failures fingerprint cleanly to per-framework error messages | VERIFIED | `vitest.config.ts` includes `test/**/*.test.ts` under one run; `src/fingerprint.ts` exports `stage(framework, stage, fn)` wrapping errors as `[framework] stage failed: ...`; both tests use all 5 stage literals including `disconnect`; SUMMARY confirms 4 test files / 42 tests pass in one `pnpm test` |

**Score:** 4/4 success criteria verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `framework-matrix/ts/package.json` | `"test": "vitest run"`, `"packageManager": "pnpm@..."`, exact-pinned deps | VERIFIED | `"test": "vitest run"` present; `"packageManager": "pnpm@10.12.4"`; all 7 deps exact-pinned; no `^`/`~` found |
| `framework-matrix/ts/pnpm-lock.yaml` | committed, frozen lockfile | VERIFIED | File git-tracked (88KB); lockfileVersion 9.0 |
| `framework-matrix/ts/src/corpus.ts` | SMOKE_TOOL/QUERY/ARGS + 4-file corpus + assertNonEmptySearch | VERIFIED | Exports `SMOKE_TOOL = "search_documents"`, `SMOKE_QUERY = "authenticate user login"`, `SMOKE_ARGS`, `FRAMEWORK_CORPUS` (4 keys: auth.py, auth.md, query_service.py, config.md), `assertNonEmptySearch` with full 5-shape dispatch |
| `framework-matrix/ts/src/harness.ts` | shared fixture: startSeededServer + stdioServerParams + SIGTERM->SIGKILL teardown | VERIFIED | `spawn("agent-brain-serve", ...)` + `spawn("agent-brain-mcp", ...)` + `["--backend","uds","--state-dir",...]`; `kill("SIGTERM")` first, `kill("SIGKILL")` escalation; 10000ms SERVER grace, 5000ms MCP-child grace; no `kill("SIGINT")` |
| `framework-matrix/ts/src/globalSetup.ts` | vitest globalSetup: prerequisitesAvailable check, AB_FWM_STATE_DIR handoff, 10s teardown | VERIFIED | `process.env["AB_FWM_STATE_DIR"] = stateDir` (mandatory handoff); `terminate(serverChild, 10000)`; no-op teardown when prereqs missing |
| `framework-matrix/ts/src/fingerprint.ts` | `stage(framework, stage, fn)` wrapper; union includes `disconnect` | VERIFIED | 59 lines; `Stage = "connect" | "list-tools" | "call" | "assert" | "disconnect"`; re-throws `[framework] stage failed: ...` with `.cause` preserved |
| `framework-matrix/ts/test/mastra.test.ts` | FRAME-06: @mastra/mcp connect -> search_documents -> assertNonEmptySearch | VERIFIED | All 5 `stage("mastra", ...)` calls present; imports `SMOKE_TOOL`, `SMOKE_ARGS`, `assertNonEmptySearch`, `stdioServerParams`; graceful skip when `AB_FWM_STATE_DIR` unset |
| `framework-matrix/ts/test/vercel-ai-sdk.test.ts` | FRAME-07: experimental_createMCPClient connect -> search_documents -> assertNonEmptySearch | VERIFIED | All 5 `stage("vercel-ai-sdk", ...)` calls present; imports `experimental_createMCPClient` from `@ai-sdk/mcp`; graceful skip when `AB_FWM_STATE_DIR` unset |
| `framework-matrix/ts/test/corpus.test.ts` | server-free unit test: 5-shape assertNonEmptySearch | VERIFIED | 32 tests covering all 5 shapes + 0-count throws + null/undefined throws + TOLERANCE branch (Proxy-based) |
| `framework-matrix/ts/test/isolation.test.ts` | asserts TS suite absent from 4 pyprojects + Taskfile | VERIFIED | Walks to repo root, reads 4 pyproject.toml files + Taskfile.yml, asserts none contains `"framework-matrix/ts"`; `pnpm` and `vitest` also absent from Taskfile |
| `framework-matrix/ts/vitest.config.ts` | globalSetup wired + generous timeouts | VERIFIED | `globalSetup: ["./src/globalSetup.ts"]`, `testTimeout: 240_000`, `hookTimeout: 240_000`, `include: ["test/**/*.test.ts"]` |
| `framework-matrix/ts/PINS.md` | every dep + version + source URL + pin date | VERIFIED | All 7 deps documented with npmjs.com source URLs and `pinned: 2026-06-11`; API drift deviation noted |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/harness.ts` | agent-brain-mcp stdio subprocess | `spawn("agent-brain-mcp", ...)` with `["--backend","uds","--state-dir",...]` | WIRED | `stdioServerParams()` builds exact spec; both tests consume it via `stdioServerParams(stateDir)` |
| `src/harness.ts` | agent-brain-serve (seeded corpus over UDS) | `spawn("agent-brain-serve", ...)` + `POST /index/` + `/health/status` poll | WIRED | `startSeededServer()` implements full seeded-server flow with 60s startup + 180s indexing deadlines |
| `src/globalSetup.ts` | both framework tests (62-02) | `process.env.AB_FWM_STATE_DIR` canonical handoff | WIRED | Set unconditionally when server is seeded; both `mastra.test.ts` and `vercel-ai-sdk.test.ts` read `process.env["AB_FWM_STATE_DIR"]` in `beforeAll` and skip when unset |
| `package.json` | pnpm | `"packageManager": "pnpm@10.12.4"` field | WIRED | `"packageManager": "pnpm@10.12.4"` present |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FRAME-06 | 62-01, 62-02 | Mastra adapter smoke test via `@mastra/mcp` | SATISFIED | `test/mastra.test.ts` connects via `MCPClient`, calls `search_documents`, asserts non-empty; all 5 stages fingerprinted; marked Complete in REQUIREMENTS.md |
| FRAME-07 | 62-01, 62-02 | Vercel AI SDK adapter smoke test via `experimental_createMCPClient` | SATISFIED | `test/vercel-ai-sdk.test.ts` connects via `experimental_createMCPClient` from `@ai-sdk/mcp`, calls `search_documents`, asserts non-empty; all 5 stages fingerprinted; marked Complete in REQUIREMENTS.md |

### API Drift Deviation (Documented, Not a Gap)

**SC3 / FRAME-07 — `experimental_createMCPClient` import path:**

The success criterion and plan text specify `experimental_createMCPClient` from the `ai` package. The executor found this symbol lives in `@ai-sdk/mcp@1.0.48` (the stable, purpose-built MCP client package), where it is exported as both `createMCPClient` (stable name) and `experimental_createMCPClient` (backward-compat alias). The `ai` package is not installed.

The implementation imports `experimental_createMCPClient` from `@ai-sdk/mcp` — the exact symbol name the plan requires, from the correct installed package. FRAME-07 intent is satisfied: Vercel AI SDK MCP client connects, calls `search_documents`, asserts non-empty. This deviation is CORRECT and RESOLVED, documented in PINS.md, 62-01-SUMMARY.md, and the test file's JSDoc header.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/corpus.ts` | 28 | `# Placeholder: delegate to identity provider.` inside Python string literal (corpus file content) | Info | Not a TS implementation placeholder — this is intentional Python source code stored as a string constant in the test corpus. Expected and correct. |
| `src/harness.ts` | 111, 280 | `return null` | Info | Both are correct: `_which()` returns null when binary not found (expected sentinel); `_pollHealth()` returns null on timeout (expected timeout indicator). Neither is a stub — both are functioning return values used by the caller. |

No blockers found. No genuine empty implementations. No TODO/FIXME/HACK patterns.

### Human Verification Required

None. All automated checks pass. The tests skip gracefully without `OPENAI_API_KEY` (correct precedent from Phase 61); when prerequisites are present the live integration path runs. The fingerprint check was manually verified by the executor (temporary dead state dir confirmed `[vercel-ai-sdk] list-tools failed: ...` output, then reverted).

### Summary

Phase 62 goal is fully achieved. All 14 required files are git-tracked and substantive. The single shared MCP subprocess fixture (`globalSetup.ts` + `AB_FWM_STATE_DIR` env var) is correctly wired to both framework tests. Both smoke tests implement the complete connect -> list-tools -> call -> assert -> disconnect flow via the fingerprint wrapper. Exact dependency pins with committed lockfile and PINS.md source records satisfy the Phase 61 discipline precedent. The TypeScript suite is provably isolated from the Python `task before-push` chain (enforced by `isolation.test.ts`). All 7 commits referenced in the summaries exist in git history. FRAME-06 and FRAME-07 are both marked Complete in REQUIREMENTS.md.

---

_Verified: 2026-06-12_
_Verifier: Claude (gsd-verifier)_
