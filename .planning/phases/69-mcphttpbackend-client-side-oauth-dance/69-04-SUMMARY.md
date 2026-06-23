---
phase: 69-mcphttpbackend-client-side-oauth-dance
plan: "04"
subsystem: mcp-client-oauth
tags: [oauth, confused-deputy, e2e, integration-test, oauth-08, client-side]
dependency_graph:
  requires: ["69-03"]
  provides: ["OAUTH-07"]
  affects: ["test_oauth_confused_deputy.py", "test_oauth_client_dance_e2e.py"]
tech_stack:
  added:
    - "pytest integration tests for the MCP->REST confused-deputy boundary (SC#4/OAUTH-08)"
    - "Hermetic OAuth dance e2e tests (SC#1/#2/#3) — no real network/browser"
  patterns:
    - "FileTokenStorage seeding to simulate persisted-token Pattern A reuse"
    - "redirect_handler spy to assert browser fires once (SC#1) / never (SC#2/#3)"
    - "Storage-layer assertion for SC#2 reuse invariant (SDK invokes redirect only on full dance)"
key_files:
  created:
    - "agent-brain-mcp/tests/test_oauth_confused_deputy.py (SC#4/OAUTH-08 — 3 cases incl. combined assertion)"
    - "agent-brain-mcp/tests/test_oauth_client_dance_e2e.py (SC#1/#2/#3 — dance, reuse, refresh)"
  modified: []
decisions:
  - "Confused-deputy test targets the real seam: config.py _open_http_client / open_backend_client (sole X-API-Key injection point for the MCP->REST leg)"
  - "SC#4 proven with both conditions: X-API-Key present AND the OAuth access-token value absent from every outgoing REST header (even when a token exists in storage)"
  - "SC#2 asserted at the storage layer — the correctness invariant is that a fresh Pattern A call loads the cached token without invoking redirect_handler"
  - "Tests are hermetic — mock AS/SDK boundary, seed FileTokenStorage, spy redirect_handler; no real browser or network"
metrics:
  duration: "~22 minutes (completed inline after transient 529 on the executor)"
  completed: "2026-06-17T00:45:00Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 0
requirements: [OAUTH-07]
---

# Phase 69 Plan 04: Confused-Deputy + OAuth Dance E2E Tests Summary

**One-liner:** Proof layer for the client-side OAuth dance — a dedicated confused-deputy integration test (SC#4/OAUTH-08: X-API-Key upstream, OAuth token never forwarded) plus hermetic e2e tests for 401→dance→retry (SC#1), persist→reuse-without-redance (SC#2), and expired→silent-refresh (SC#3).

## What Was Built

### Task 1: Confused-deputy integration test (`test_oauth_confused_deputy.py`)

Targets the real MCP→REST seam in `agent_brain_mcp/config.py` (`_open_http_client` / `open_backend_client`) — the sole `X-API-Key` injection point for the upstream REST leg. Three cases:

1. `test_x_api_key_header_is_set` — when `AGENT_BRAIN_API_KEY` is set, the upstream client carries `X-API-Key`.
2. `test_no_authorization_header_on_upstream_client` — the upstream client has NO `Authorization` header; the MCP→REST leg authenticates via `X-API-Key` exclusively.
3. `test_x_api_key_and_no_authorization_together` — **the combined assertion the plan requires**: `X-API-Key` present AND `Authorization` absent simultaneously. With an OAuth token seeded into `FileTokenStorage`, the test confirms the OAuth access-token value never appears in any outgoing REST header (the explicit confused-deputy guard).

### Task 2: OAuth dance e2e tests (`test_oauth_client_dance_e2e.py`)

Hermetic — mocks the AS/SDK boundary, seeds `FileTokenStorage`, and uses a `redirect_handler` spy. Covers:

- **SC#1** — 401 + WWW-Authenticate triggers the SDK dance (PRM → OASM → DCR → PKCE → token); the `redirect_handler` spy fires exactly once and a valid Bearer is obtained.
- **SC#2** — a second Pattern A invocation loads the seeded token from `FileTokenStorage` and the `redirect_handler` spy is NOT called again (storage-layer reuse invariant — the SDK only invokes `redirect_handler` on a full dance).
- **SC#3** — pre-seeded expired access token + valid refresh token → silent refresh via `POST /token grant_type=refresh_token`; `redirect_handler` NOT called, refreshed token used.

### Task 3: Quality gate

Refined both test files for Black/Ruff/mypy-strict cleanliness, then ran the full repo gate.

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| `test_oauth_confused_deputy.py` asserts X-API-Key present | PASS |
| `test_oauth_confused_deputy.py` asserts OAuth token NOT forwarded upstream | PASS (combined case) |
| `test_oauth_client_dance_e2e.py` covers SC#1 (dance+retry, browser once) | PASS |
| `test_oauth_client_dance_e2e.py` covers SC#2 (reuse without re-dance) | PASS |
| `test_oauth_client_dance_e2e.py` covers SC#3 (silent refresh) | PASS |
| New tests pass | PASS (15 tests) |
| `task before-push` exits 0 | PASS (974 passed, 91% coverage) |

## Deviations from Plan

**Executor interrupted by transient API 529 (Overloaded) during Task 3.** Tasks 1 and 2 had already committed (`485cb26`, `253e742`); the working-tree test refinements (green, 15 passing) and the Task-3 bookkeeping were finished inline by the orchestrator after spot-checks confirmed the substantive work was complete and the full gate green. The finalization was committed as `1a8f1d9`. No content was lost; this is a runtime-availability deviation, not a code deviation.

## Self-Check: PASSED

- FOUND: agent-brain-mcp/tests/test_oauth_confused_deputy.py
- FOUND: agent-brain-mcp/tests/test_oauth_client_dance_e2e.py
- FOUND commit 485cb26 (Task 1 confused-deputy)
- FOUND commit 253e742 (Task 2 dance e2e)
- FOUND commit 1a8f1d9 (Task 3 quality-gate finalization)
- `task before-push` exits 0 (974 passed, 91% coverage)
