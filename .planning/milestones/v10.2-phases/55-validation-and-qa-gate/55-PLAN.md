# Phase 55 Plan: Validation, contract tests & QA gate integration

**Goal:** All 16 MCP tools, subscriptions, and the HTTP transport are covered by parameterized contract tests verified against the official MCP SDK. New packages folded into root `task before-push` and `task pr-qa-gate`.
**Requirements:** VAL-01, VAL-02, VAL-03, VAL-04
**Plan count:** 5
**Depends on:** Phases 50, 51, 52, 53, 54 (must be last — validates the full v2 surface)
**Closes:** DR-5 from `docs/plans/2026-05-28-mcp-uds-transport-design.md` §14 #5

## Plans

| # | Title | Requirements | Depends on | Parallel-safe with | Est. LOC |
|---|-------|--------------|------------|---------------------|----------|
| 01 | Contract test scaffolding (Layer 2 SDK fixture chain) | VAL-01 (scaffolding) | none | none — Plans 02–04 all consume this | ~180 (mostly fixtures + `_DEFAULT_RESPONSES` extensions) |
| 02 | 16-tool parameterized contract tests + resource templates assertion | VAL-01 | Plan 01 | Plans 03, 04 | ~280 (16-entry matrix + 4 test functions, mostly data) |
| 03 | Subscription lifecycle E2E test | VAL-02 | Plan 01 | Plans 02, 04 | ~180 (3 parametrized cases + disconnect test + helpers) |
| 04 | Streamable HTTP transport contract test | VAL-03 | Plan 01 | Plans 02, 03 | ~160 (HTTP fixture + 5 test functions) |
| 05 | Root QA gate integration + audit attestation | VAL-04 (closes DR-5) | Plans 01–04 | none — final plan | ~80 (Taskfile edits + VALIDATION.md + CHANGELOG) |

**Total estimated LOC:** ~880 (test code + Taskfile edits + audit doc). Production code change: ~0 — Phase 55 is verification-only by design (D-19).

## Execution Order

```
Wave 1 (sequential):
  Plan 01  ── scaffolds tests/contract/ + _DEFAULT_RESPONSES extensions
              + mcp:contract task wired up

Wave 2 (parallel, all depend only on Plan 01):
  Plan 02  ── 16-tool parametrized contract tests (VAL-01)
  Plan 03  ── subscription lifecycle + disconnect cleanup (VAL-02)
  Plan 04  ── Streamable HTTP transport SDK test (VAL-03)

Wave 3 (sequential, must follow Plans 02–04 merging clean):
  Plan 05  ── root before-push / pr-qa-gate integration + VALIDATION.md audit
              (closes DR-5; produces milestone exit gate doc)
```

Plans 02, 03, and 04 may be implemented and PR'd in any order once Plan 01
lands — they touch different test files and consume independent fixture
surfaces. Plan 05 is strictly last: it edits the root `Taskfile.yml` to fold
MCP/UDS into pre-push, which requires the test suites in Plans 02–04 to be
green first (otherwise root `task before-push` immediately breaks for every
developer).

## Coverage Check

Every requirement maps to at least one plan:

- **VAL-01** (16-tool parameterized contract tests against the official MCP SDK):
  - Plan 01 (scaffolding — defines the SDK fixture chain)
  - Plan 02 (the 16-tool happy-path + negative-arg matrix; also extends
    Layer 1 `test_each_tool.py` to 16 entries; resource templates check)
- **VAL-02** (Resource subscriptions tested end-to-end via SDK, including
  subscribe/unsubscribe/disconnect cleanup):
  - Plan 03 (parametrized over all three Phase 52 subscription URIs +
    disconnect-cleanup test that closes SUB-05 verification)
- **VAL-03** (Streamable HTTP transport tested via SDK HTTP client):
  - Plan 04 (5 SDK-driven tests over `streamablehttp_client`, covers
    initialize → tools → resources flow)
- **VAL-04** (New MCP packages folded into root `task before-push` +
  `task pr-qa-gate` — closes DR-5):
  - Plan 05 (Taskfile edits + VALIDATION.md attestation)

**No VAL requirements are unmapped.** VAL-05 is owned by Phase 50 (the v2
design doc); Plan 05 verifies it exists and §5 reflects the two-layer test
architecture decided in CONTEXT.md D-01, but does not own delivery.

## Cross-Phase Dependencies

**Phase 55 depends on:**
- **Phase 50:** `GET /query/chunk/{id}` and `GET /graph/entity/{type}/{id}`
  endpoints (Plan 01's `_DEFAULT_RESPONSES` stubs them; contract tests assert
  the MCP layer correctly forwards to those shapes). Also the v2 design doc
  (VAL-05) which Plan 05 verifies.
- **Phase 51:** Four URI scheme implementations (`chunk://`, `graph-entity://`,
  `job://`, `file://`) + `resources/templates/list` — Plan 02's resource
  templates test binds to these.
- **Phase 52:** Subscription cadence + disconnect cleanup — Plan 03 verifies
  end-to-end. If Phase 52 didn't expose a per-client subscription count
  observability surface, Plan 03 falls back to log-scraping AND files a
  follow-up GitHub issue (this is documented as expected behavior in
  CONTEXT.md D-06).
- **Phase 53:** Streamable HTTP transport (`--transport http --port`
  flags) — Plan 04 spawns the subprocess. Phase 53's own tests cover
  loopback-only and `--transport` rejection (D-10); Plan 04 only verifies the
  happy path via SDK HTTP client.
- **Phase 54:** All 9 new tool implementations — Plan 02's 16-entry matrix
  binds to the schemas Phase 54 declares. If Phase 54 renames a tool, Plan 02's
  `_tool_matrix.py` updates in one place (single source of truth shared by
  Layer 1 + Layer 2).

**Phase 55 produces (for downstream / milestone gate):**
- `VALIDATION.md` audit attestation that `gsd-complete-milestone` reads as
  the v10.2 milestone exit gate.
- Root `task before-push` / `task pr-qa-gate` that includes MCP/UDS — the
  v3 milestone (CLI-via-MCP) inherits this gate from day one.
- `tests/contract/_tool_matrix.py` as a stable contract surface that v3
  framework adapter matrix tests can re-use.

**Phase 55 does NOT produce:**
- New MCP features (D-19 — if a Phase 50–54 deliverable is broken, fix it in
  its originating phase, do not patch in Phase 55).
- New requirements (D-19).
- The `/mcp/subscriptions/__debug` endpoint (deferred — Plan 03 files as
  Phase 52 follow-up if needed).
- Performance/latency assertions (deferred — see Deferred Ideas in CONTEXT.md).

## Risk Register

Top risks identified during planning, in priority order:

1. **`/mcp/subscriptions` observability gap.** Phase 52 may not have exposed a
   per-client subscription-count surface. Plan 03 mitigates by falling back to
   log-scraping AND filing a follow-up issue — but the test is more fragile
   than a direct endpoint query. If log format changes, the test breaks
   silently.
   *Mitigation:* Plan 03's PR description must call out which path was taken;
   reviewer must confirm.

2. **Tool registry drift between Phase 54 and Phase 55.** If Phase 54 ships
   with fewer than 9 new tools or renames any, Plan 02's 16-entry matrix
   breaks.
   *Mitigation:* `_tool_matrix.py` is a single source of truth; cross-check
   against `agent_brain_mcp/tools/__init__.py::TOOL_REGISTRY` before locking
   the matrix. Plan 02 verification step explicitly asserts
   `tools/list | length == 16`.

3. **30s cadence vs CI runtime.** `corpus://status` ships with 30s cadence
   per Phase 52. A literal 30s sleep in CI is unacceptable.
   *Mitigation:* Plan 03's fixture overrides cadence via env var. If Phase 52
   didn't expose the knob, the test asserts subscribe/unsubscribe RPC roundtrip
   only (no cadence assertion for `corpus://status`) and files a Phase 52
   follow-up.

4. **`streamablehttp_client` greenfield.** Zero existing usages in the repo;
   Plan 04 is the first integration with `mcp.client.streamable_http`.
   *Mitigation:* Plan 01's smoke fixture surfaces SDK shape issues early. If
   Plan 04 iteration is painful, add an HTTP smoke variant to Plan 01.

5. **+60-90s local pre-push cost.** Adding MCP/UDS to root `task before-push`
   measurably slows the loop.
   *Mitigation:* Document in CHANGELOG and v2 design doc §5. If devs revolt,
   the v10.3 milestone can split heavy contract tests behind a `task ci-only`
   gate — but that is NOT a Phase 55 concern.

6. **`poetry.lock` drift from transitive `poetry install`.** Adding `task:
   uds:before-push` and `task: mcp:before-push` inside the root recipe runs
   `poetry install` for both packages. The existing `before_push_lock_guard.sh`
   wrapper should auto-revert any in-tree drift.
   *Mitigation:* Plan 05 verification step explicitly runs `task before-push`
   on a clean tree and confirms no `git status` drift afterward.

7. **Pre-push subprocess teardown leaks.** All four contract test plans spawn
   subprocesses (`agent-brain-mcp` stdio + HTTP). Leaked subprocesses across
   test runs corrupt subsequent fixtures.
   *Mitigation:* Plan 01 enforces the Phase 4 teardown contract verbatim
   (SIGTERM → 5s → SIGKILL → orphan `pgrep` scan that FAILS the test). Every
   downstream plan inherits this contract.

8. **macOS sockaddr_un 104-byte limit.** Any UDS-touching contract fixture
   must use `short_state_dir` (mkdtemp under `/tmp/abmcp-*`).
   *Mitigation:* Plan 01's fixture scaffolding inherits this pattern from
   `tests/e2e/conftest.py::short_state_dir`. Downstream plans don't need to
   re-derive.

9. **MCP SDK version drift.** Phase 50 pinned `mcp = "^1.12.0"`. If the SDK
   shipped a new minor during v10.2 implementation, contract test assertions
   may drift.
   *Mitigation:* D-03 forbids floating the SDK pin. Plan 05's audit step
   verifies `pyproject.toml` still pins the original v2 SDK version OR that
   the v2 design doc's "Spec versions" section was updated.

10. **DR-5 closure language correctness.** The audit must explicitly cite
    `docs/plans/2026-05-28-mcp-uds-transport-design.md §14 #5` and note
    "Resolved in v10.2 Phase 55" so future reviewers can confirm the cycle is
    closed.
    *Mitigation:* Plan 05's VALIDATION.md template includes the exact citation
    string; reviewer checks it word-for-word.

---
*Phase plan generated: 2026-06-02*
