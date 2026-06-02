# Phase 52 Plan: Resource subscriptions

**Goal:** MCP clients can subscribe to live resources and receive spec-compliant `notifications/resources/updated` events, with proper per-client subscription tracking and cleanup on disconnect.
**Requirements:** SUB-01, SUB-02, SUB-03, SUB-04, SUB-05
**Plan count:** 4
**Depends on:** Phase 51 (`job://<id>` URI must be addressable before SUB-01 can subscribe to it)
**Prerequisite for:** Phase 54 TOOL-04 (`wait_for_job` reuses Phase 52 polling primitive for `notifications/progress`)

## Plans

| # | Title | Requirements | Depends on | Parallel-safe with | Est. LOC |
|---|-------|--------------|------------|---------------------|----------|
| 01 | Subscription manager core (greenfield package) | SUB-04, SUB-05 (foundation) | none — first plan | none (all subsequent plans depend on it) | ~280 (200 code + 80 unit tests) |
| 02 | MCP wire integration & capability flip | SUB-04 | 01 | 03 (different files, but logically sequential — 03 needs 02's handler to register) | ~180 (100 code + 80 tests; deletes ~20 LOC) |
| 03 | Per-URI polling policies & change-stream | SUB-01, SUB-02, SUB-03 | 01 (manager primitive) | 02 (policies are passed into handlers, but can land in parallel commits if 02 lands first) | ~280 (180 code + 100 tests) |
| 04 | Disconnect cleanup + SDK e2e validation | SUB-05, SUB-01, SUB-02, SUB-03 | 01, 02, 03 | none — last plan | ~220 (60 production code + 160 e2e tests) |

**Total est. LOC:** ~960 lines (code + tests), within phase budget.

## Execution Order

```
Wave 1 (foundation):       Plan 01
Wave 2 (parallel-safe):    Plan 02 + Plan 03 (02 must land first by 1 commit so 03's
                                              policies have a handler to register against;
                                              practically: sequential commits, same PR feasible)
Wave 3 (integration):      Plan 04 (depends on 01+02+03)
```

In practice this is one PR per plan (atomic commits), but a single milestone PR is also feasible
because plans 02 and 03 don't touch the same files.

## Coverage Check

Every requirement maps to at least one plan:

- **SUB-01** (`job://<id>` 1s cadence subscription): Plan 03 (policy) + Plan 04 (e2e test)
- **SUB-02** (`corpus://status` 30s cadence): Plan 03 (policy) + Plan 04 (e2e test)
- **SUB-03** (`corpus://folders` watcher-driven 5s active / 60s safety): Plan 03 (policy) + Plan 04 (e2e test)
- **SUB-04** (spec-compliant `notifications/resources/updated` payload with URI + `_meta.revision`): Plan 01 (payload hashing helper, payload shape) + Plan 02 (wires `ServerSession.send_resource_updated`)
- **SUB-05** (per-client tracking + disconnect cleanup): Plan 01 (manager registry shape) + Plan 04 (`run_stdio` try/finally + leaked-task assertion test)

## Cross-Phase Dependencies

**Upstream (this phase depends on):**
- **Phase 51** must land `job://<id>` URI in `RESOURCE_REGISTRY` first — Plan 02's subscribe handler validates URIs against that registry and the per-URI allowlist `{job://, corpus://status, corpus://folders}`.
- **Phase 50** carries spec version pin (2025-03-26) and no-auth stance; both inherited into Plan 01's payload shape.

**Downstream (this phase unblocks):**
- **Phase 54 TOOL-04** (`wait_for_job` with `notifications/progress` every ≤2s) reuses Plan 01's `SubscriptionManager.start_polling(session, uri, interval_s, fetcher, on_change)` as its progress emitter. Plan 01 **must** expose this primitive as a public method with a documented contract.
- **Phase 53 Streamable HTTP transport** inherits the cleanup hook pattern Plan 04 establishes (`run_stdio` try/finally analog for HTTP disconnect). Phase 53's plan should reference Plan 04's cleanup contract as the model.

## Risk Register

1. **MCP SDK `ServerSession.send_resource_updated()` is async and per-session.** Polling tasks must capture the owning `ServerSession` at subscribe time (from `server.request_context.session`) rather than looking it up later. Mitigated in Plan 01's manager API: `start_polling(session, ...)` takes the session as a required arg.
2. **Subscription leak via subprocess crash.** If the MCP server process dies mid-poll, no cleanup hook fires. Mitigation: every polling task wraps its body in `try/except CancelledError` and self-removes from the registry on exit — belt-and-suspenders against partial cleanup (Plan 01 + Plan 04).
3. **Diff-suppression hash regressions.** `corpus://status` payload from `/health/status` includes uvicorn timestamp fields. If the hash normalizer doesn't strip `timestamp`, `updated_at`, `elapsed_ms`, `polled_at` (and any future volatile keys), the 30s subscription will emit every poll regardless of real change. Mitigation: Plan 01's `canonical_hash(payload, drop=...)` takes the drop-set as an explicit parameter; Plan 03's policy declares it per URI; Plan 04 has an e2e test that asserts no notification fires when only the timestamp changed.
4. **Polling task race on rapid subscribe → unsubscribe.** Manager must be safe against `unsubscribe()` arriving before `subscribe()`'s `asyncio.create_task` has even scheduled. Mitigation: Plan 01 registers the task synchronously in the dict before calling `create_task`, and `unsubscribe()` cancels via the dict entry which is always set.
5. **Spec drift.** MCP spec 2025-03-26 `ResourceUpdatedNotificationParams` is what Plan 01 + Plan 02 target. If the spec rev advances mid-implementation, the `_meta` shape may shift. Mitigation: Phase 50's design doc pins the spec rev; Plan 02's tests assert against the pinned version in `agent-brain-mcp/.venv/.../mcp/types.py`.
6. **`corpus://folders` watcher hook not yet greenfield.** Plan 03 uses time-based polling (5s active / 60s safety) without inventing a server-side watcher push. If a watcher hook is added later, the policy can swap to push without changing the subscribe wire contract. Documented as acceptable v2 latency (≤5s) in the design doc per Phase 52 context decision E.
7. **Test flakiness on disconnect-cleanup assertion.** `psutil`-based "no leaked tasks" check is timing-dependent. Mitigation: Plan 04 polls `psutil.Process.threads()` for up to 2s after SIGTERM rather than asserting in a single shot.

## Quality Gate

Every plan must pass:
- `task before-push` (Black, Ruff, mypy strict, pytest) from repo root
- `task mcp:pr-qa-gate` from `agent-brain-mcp/`
- No regression in existing v1 MCP tests (`test_initialize.py::test_capabilities_have_no_subscriptions` is **deleted** in Plan 02 and replaced with `test_capabilities_advertise_subscriptions`)

## Coverage Check Summary

| Requirement | Plan(s) | Verification |
|-------------|---------|--------------|
| SUB-01 | 03, 04 | E2E SDK test: subscribe to `job://<live-job>`, assert ≥3 `notifications/resources/updated` within 5s |
| SUB-02 | 03, 04 | E2E SDK test: subscribe to `corpus://status`, mock `/health/status` to flip a field, assert exactly 1 notification within 35s |
| SUB-03 | 03, 04 | E2E SDK test: subscribe to `corpus://folders`, mutate folder list via `FolderManager`, assert notification within 6s (5s active cadence) |
| SUB-04 | 01, 02, 04 | Unit test on payload shape: `params.uri == "<resource_uri>"` + `params._meta["revision"]` is a hex SHA-256 string |
| SUB-05 | 01, 04 | E2E SDK test: subscribe, SIGTERM the client subprocess, poll `psutil.Process.threads()` from server side for 2s — no polling threads remain |

---
*Phase plan generated: 2026-06-02*
