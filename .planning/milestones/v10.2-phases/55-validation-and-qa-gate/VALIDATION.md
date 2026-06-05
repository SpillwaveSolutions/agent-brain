# Phase 55 Validation — v10.2 MCP v2 milestone exit gate

**Phase:** 55 — Validation, contract tests & QA gate integration
**Milestone:** v10.2 — MCP v2 (Subscriptions, HTTP Transport, & Tool Completion)
**Date:** 2026-06-03
**Sign-off attestation for `gsd-complete-milestone`.**

## Requirements coverage

| REQ    | Status      | Plan  | Notes |
|--------|-------------|-------|-------|
| VAL-01 | ✅ Complete | 55-02 | 16-tool parameterized contract suite — Layer 1 (in-process, `tests/test_each_tool.py`, 16 rows) + Layer 2 (SDK over stdio, `tests/contract/test_tools_contract.py`) sharing the single-source matrix `tests/contract/_tool_matrix.py`. 32 SDK tool assertions (16 happy + 16 negative) + 6 resources assertions (4 templates + v1 corpus list + 4 per-scheme reads). Commits: `86999e0`, `c3b6f1f`, `4a6b51c`, `3e07334`. |
| VAL-02 | ✅ Complete | 55-03 | Subscription lifecycle + disconnect cleanup E2E — 4 SDK-driven tests in `tests/contract/test_subscription_lifecycle.py`: 3 parameterized happy-path (`job://`, `corpus://status`, `corpus://folders`) + 1 disconnect-cleanup via raw `subprocess.Popen` EOF path. Phase 52 ships no observability endpoint per CONTEXT D-06; verification via stderr-log scrape for the `"subscription cleanup: cancelled"` literal at `server.py:984-987`. Follow-up issue [#194](https://github.com/SpillwaveSolutions/agent-brain/issues/194) filed proposing `/mcp/subscriptions/__debug` for v10.3+. Commits: `0c156fd`, `0c3c9ec`. |
| VAL-03 | ✅ Complete | 55-04 | Streamable HTTP transport SDK test — 5 SDK-driven contract tests in `tests/contract/test_http_transport_contract.py` via `mcp.client.streamable_http.streamablehttp_client` (initialize / tools/list==16 / tools/call(server_health) / resources/list⊇{5 v1 corpus URIs} / resources/read(corpus://config)) + 1 mount-path sanity pin = 6 tests proving transport-equivalence with Plan 02's stdio surface. New `mcp_http_session` factory cascade-reuses Phase 53 Plan 03's `mcp_http_subprocess` + `fake_http_server_module` from `tests/conftest.py` — no duplicate HTTP harness. Commit: `9b8eda6`. |
| VAL-04 | ✅ Complete | 55-05 | MCP + UDS folded into root `task before-push` + `task pr-qa-gate`. Per-package `before-push` sub-tasks added to `agent-brain-mcp/Taskfile.yml` and `agent-brain-uds/Taskfile.yml`; root recipes invoke them inside the existing lock-guard wrapping (issue #174 preserved). Stale "NOT wired into root" v1 header comments replaced with v10.2 attribution citing DR-5 closure. Commits: `0391a27`, `a7ca7c9`. |

## DR-5 closure

**Resolved in v10.2 Phase 55** (this plan; commits `0391a27` + `a7ca7c9`).

Source citation: `docs/plans/2026-05-28-mcp-uds-transport-design.md` §14 #5:

> "New packages don't join root `before-push` in v1. They have their own
> `pr-qa-gate`. Folds into root only after 10.1.0 ships green and one release
> cycle elapses (target: 10.2.0). Matches `2026-mcp-server-design.md`
> precedent."

v10.1 shipped green on 2026-05-30 (`agent-brain-mcp` v10.1.0) and 2026-05-29
(v10.1.1 workflow fix) and 2026-06-01 (v10.1.2 PyPI rename); one release cycle
has elapsed. v10.2 Phase 55 Plan 05 lands the integration:

- `Taskfile.yml::before-push` now invokes `task: uds:before-push` +
  `task: mcp:before-push` after the existing `test:cov` step and before the
  final "All checks passed" echo. The lock guard (`before_push_lock_guard.sh
  start` + deferred `check`) still wraps the whole body, so any in-tree
  `poetry.lock` drift from the new MCP/UDS `poetry install` calls is
  auto-detected and reverted (issue #174 mechanism preserved).
- `Taskfile.yml::pr-qa-gate` now invokes `task: uds:pr-qa-gate` +
  `task: mcp:pr-qa-gate` after `cli:pr-qa-gate`.
- `agent-brain-mcp/Taskfile.yml::before-push` and
  `agent-brain-uds/Taskfile.yml::before-push` are new tasks of the form
  `format:check → lint → typecheck → test:cov`, mirroring the root recipe.

## QA gate attestation

- Root `task before-push` exit code: **0** (160s wall-clock, including MCP/UDS).
- Root `task pr-qa-gate` exit code: **0** (152s wall-clock).
- `task check:layering` exit code: **0** — 3 contracts kept (`server has no
  upward deps`, `uds touches only server.models`, `mcp never calls server
  internals`), 164 files / 414 dependencies analyzed. Phase 53's HTTP transport
  deps (uvicorn, starlette) did NOT break the `mcp must never call server
  internals` contract — DR-5's load-bearing layering invariant is intact.
- `agent-brain-mcp` coverage: **91.83%** (above 80% floor — security-boundary
  code per v1 plan §9 / Phase 55 Plan 02 Plan 05 D-14).
- `agent-brain-uds` coverage: **99%** (above 80% floor — same security boundary
  rationale; 32 tests / 1.29s).
- `agent-brain-mcp` fast-path: **460 passed / 96 deselected** (contract suite
  stays opt-in via the `-m contract` marker).
- `agent-brain-mcp` contract suite (`task mcp:contract`): **49 tests / 24.73s**
  (39 → 43 in Plan 03 → 49 in Plan 04; Plan 05 adds no new tests).
- CI workflow: existing `.github/workflows/*.yml` that invokes
  `task before-push` / `task pr-qa-gate` picks up the MCP/UDS additions
  automatically — no new workflow YAML required per CONTEXT D-15.

## Coverage delta

| Package           | Coverage | Floor | Test count | Notes |
|-------------------|----------|-------|------------|-------|
| agent-brain-mcp   | 91.83%   | 80%   | 460 (fast) + 49 (contract) | Above floor; +9 fast-path tests vs Plan 02 baseline; contract suite +10 vs Plan 02 (39 → 49) |
| agent-brain-uds   | 99%      | 80%   | 32         | Unchanged behavior from v10.1; smoke test loosened to MAJOR.MINOR.PATCH regex (was hardcoded "10.0.7", silently broken since 10.1.0 PyPI bump — caught by this plan's standalone `task uds:before-push` run) |

## Follow-ups filed

- **GitHub issue [#194](https://github.com/SpillwaveSolutions/agent-brain/issues/194)** —
  proposes `GET /mcp/subscriptions/__debug` endpoint gated behind
  `AGENT_BRAIN_DEBUG=1` for v10.3+. Filed by Plan 03 because Phase 52 ships
  no observability endpoint for per-session subscription counts; Plan 03's
  disconnect-cleanup test currently falls back to stderr log scraping per
  CONTEXT D-06 ("recommended fallback for D-06: file as a Phase 52 follow-up
  issue rather than a Phase 55 task"). Stderr scrape works today; the
  follow-up replaces it with cleaner instrumentation later.

## Pre-push wall-clock delta

| Recipe              | Wall-clock | Delta vs pre-Phase-55 |
|---------------------|------------|----------------------|
| `task before-push`  | 160s       | +approx 60-90s (matches plan estimate; per-package MCP install + 460 tests adds ~18s; UDS install + 32 tests adds ~5s; the rest is poetry install warm-up and dependency resolution that the lock guard immediately reverts) |
| `task pr-qa-gate`   | 152s       | +approx 60-90s (similar shape — MCP/UDS per-package `pr-qa-gate` runs format:check + lint + mypy + coverage with `--cov-fail-under=80` enforcement) |

Documented in `docs/CHANGELOG.md` v10.2.0 entry so developers aren't surprised
by the new local cost. CI cost is unchanged — the workflow already runs the
full monorepo per CONTEXT D-15.

## Risk register status

- **#178 Kuzu SIGSEGV** — still tracked; `graph-entity://` resource handler
  returns 503 with `reason="kuzu_unavailable"` slug per Phase 51 Plan 02
  decision. Operator workaround: `graphrag.store_type: simple`. Not blocking
  v10.2 ship.
- **#179 Bearer-token API auth** — design doc surfaces composition explicitly;
  v10.2 ships without auth on the HTTP MCP transport (loopback-only mitigates
  the gap). v4 (#188) ships OAuth 2.1.
- **MCP SDK pin** — `mcp = "^1.12.0"` (verified at execution time; no bump
  needed for v10.2). Future SDK drift handled by defensive `*_` unpack on
  `streamablehttp_client` yield tuple per Phase 53 Plan 03 risk #1.

## v2 design doc (VAL-05) verification

`docs/plans/2026-06-02-mcp-v2-subscriptions.md` exists (shipped in Phase 50
via VAL-05). §5 "Test strategy" reflects the two-layer architecture from
CONTEXT D-01 (Layer 1 in-process parametrized + Layer 2 SDK-driven contract).
No drift; no Phase 50 follow-up PR needed.

## Milestone status

**v10.2 MCP v2 — READY FOR RELEASE**

All 4 phase requirements (VAL-01..04) + DR-5 closure verified end-to-end:

- 16-tool MCP surface (7 v1 + 9 v2) covered by parameterized SDK contract
  tests over stdio (Plan 02) and HTTP (Plan 04) — transport-equivalence
  proven.
- Resource subscriptions exercised end-to-end (subscribe / notify / unsubscribe
  / disconnect cleanup) over stdio with all three Phase 52 subscribable URIs
  (`job://`, `corpus://status`, `corpus://folders`) — Plan 03.
- Streamable HTTP transport (loopback-only) tested via official MCP SDK HTTP
  client (`streamablehttp_client`) — Plan 04.
- Root `task before-push` and `task pr-qa-gate` now include MCP + UDS
  packages; exit 0 on a clean working tree — Plan 05.

24/24 plans complete across the v10.2 milestone (Phase 50: 4/4, Phase 51: 4/4,
Phase 52: 4/4, Phase 53: 3/3, Phase 54: 4/4, Phase 55: 5/5).

---

*Phase: 55-validation-and-qa-gate*
*Validation completed: 2026-06-03*
*Sign-off: Plan 55-05*
