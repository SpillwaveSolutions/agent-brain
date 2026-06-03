---
phase: 52-resource-subscriptions
verified: 2026-06-03T00:00:00Z
status: passed
score: 5/5 must-haves verified
verifier_mode: initial
---

# Phase 52: Resource subscriptions Verification Report

**Phase Goal:** MCP clients can subscribe to live resources and receive spec-compliant `notifications/resources/updated` events at policy-defined cadences, with per-client subscription tracking and disconnect cleanup.
**Verified:** 2026-06-03 (initial verification — no prior `52-VERIFICATION.md` existed)
**Status:** PASSED
**Requirements scope:** SUB-01, SUB-02, SUB-03, SUB-04, SUB-05 (5/5 covered)
**Method:** Read actual source files; ran full pytest suite + e2e marker subset; ran `task check:layering`. Did not trust SUMMARY.md claims — every observable truth re-verified against the codebase.

---

## Goal Achievement

### Observable Truths (5/5 verified)

| #   | Truth                                                                                                                                      | Status      | Evidence                                                                                                              |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------ | ----------- | --------------------------------------------------------------------------------------------------------------------- |
| 1   | Client can `resources/subscribe` to `job://<id>` and receive ≥2 `notifications/resources/updated` at ~1s cadence until job terminates      | PASS        | `policies.py:222-248` (`JobPolicy.interval_s = 1.0`); `policies.py:154-185` fetcher + terminal-status catch; e2e `test_subscribe_job_emits_until_terminal` passes |
| 2   | Client can `resources/subscribe` to `corpus://status` and receive updates at ~30s cadence on change                                        | PASS        | `policies.py:250-267` (`CorpusStatusPolicy.interval_s = 30.0`); drops `request_id` to defeat uvicorn UUID churn; e2e `test_subscribe_corpus_status_emits_on_change` passes |
| 3   | Client can `resources/subscribe` to `corpus://folders` and receive updates at configurable cadence (default 5s) on folder mutation         | PASS        | `policies.py:270-323` (`CorpusFoldersPolicy.interval_s = 5.0` default, configurable); `config.py:87-95` settings field; e2e `test_subscribe_folders_active_cadence` passes |
| 4   | Every `notifications/resources/updated` payload conforms to MCP spec 2025-03-26 (`ResourceUpdatedNotificationParams`)                      | PASS        | `tests/test_notification_shape.py` — 9 unit tests; SHA-256 revision is 64-char lowercase hex; round-trips via `model_dump_json` / `model_validate_json` |
| 5   | Server tracks per-session subscriptions; on client disconnect, polling tasks are cancelled; no leaked tasks                                | PASS        | `server.py:580-616` (`run_stdio` try/finally → `cleanup_all`); `manager.py:104-186, 321-402` synchronous-registry cleanup; e2e `test_disconnect_cleans_up_polling_tasks` (counter-based deterministic) passes |

**Score:** 5/5 truths verified

### Required Artifacts (all PASS)

| Artifact                                                                                          | Expected                                                                          | Status | Evidence (file:line)                                                                                       |
| ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------- |
| `agent_brain_mcp/subscriptions/__init__.py`                                                       | Re-exports public surface                                                          | PASS   | `__init__.py:39-67` exports 14 symbols including all Policy classes + Manager + canonical_hash             |
| `agent_brain_mcp/subscriptions/manager.py` :: `SubscriptionManager`                               | Full lifecycle: start_polling/unsubscribe/cleanup_session/cleanup_all/is_subscribed/active_count | PASS   | `manager.py:66-420` — all 6 methods present, synchronous-registry contract preserved                       |
| `agent_brain_mcp/subscriptions/payloads.py` :: `canonical_hash` + `DEFAULT_DROP_KEYS`              | SHA-256 with sorted JSON + 5-key drop set                                          | PASS   | `payloads.py:40-48` drop set = `{timestamp, updated_at, elapsed_ms, polled_at, now}`; `payloads.py:73-105` returns 64-char hex |
| `agent_brain_mcp/subscriptions/policies.py` :: `JobPolicy`                                         | interval_s=1.0; terminal-status sentinel                                          | PASS   | `policies.py:222-248`; `policies.py:181-182` raises `SubscriptionTerminated(payload)` on terminal status   |
| `agent_brain_mcp/subscriptions/policies.py` :: `CorpusStatusPolicy`                                | interval_s=30.0                                                                   | PASS   | `policies.py:250-267`                                                                                       |
| `agent_brain_mcp/subscriptions/policies.py` :: `CorpusFoldersPolicy`                               | interval_s settings-driven, default 5.0                                            | PASS   | `policies.py:270-302`; `policies.py:320-322` injects from `mcp_subscription_settings.folders_active_interval_s` |
| `agent_brain_mcp/subscriptions/errors.py` :: `SubscribableUriRejected` + `SubscriptionTerminated` | Three reason codes + sentinel exception                                            | PASS   | `errors.py:37-66` reasons `unknown_uri`/`not_subscribable`/`duplicate_subscribe`; `errors.py:73-122` sentinel  |
| `agent_brain_mcp/server.py` :: `build_server` tuple return                                         | `tuple[Server, SubscriptionManager]`                                              | PASS   | `server.py:168-170` signature; `server.py:525` returns `(server, subscription_manager)`                    |
| `agent_brain_mcp/server.py` :: `run_stdio` disconnect-cleanup hook                                 | try/finally calling `cleanup_all`                                                  | PASS   | `server.py:580-616` `try`/`finally` block calling `subscription_manager.cleanup_all()` on every exit path  |
| `agent_brain_mcp/server.py` :: `_patched_get_capabilities` wrapper                                 | Flips SDK hardcoded `subscribe=False` to `True`                                    | PASS   | `server.py:493-522`; cross-verified SDK pin `mcp = "^1.12.0"` (`pyproject.toml:28`) still hardcodes `subscribe=False` at `mcp/server/lowlevel/server.py:212` |
| `agent_brain_mcp/config.py` :: `MCPSubscriptionSettings`                                            | Pydantic settings with gt=0 validation                                             | PASS   | `config.py:63-104`; `config.py:107-153` env-var ingestion with clear RuntimeError on parse failure          |
| `tests/test_notification_shape.py`                                                                 | SUB-04 spec-conformance unit tests                                                | PASS   | 9 tests across 3 classes pinning minimal shape, revision envelope, and method literal                       |
| `tests/e2e/test_e2e_subscriptions.py`                                                               | 5 SDK-driven e2e tests for SUB-01/02/03/05                                         | PASS   | 5 tests defined; all 5 passing under `pytest -m e2e`                                                        |
| `tests/test_initialize.py` :: `test_capabilities_advertise_subscriptions`                          | Inverted v1 assertion — `subscribe is True`                                        | PASS   | `test_initialize.py:71-98`; plus `test_capabilities_subscribe_independent_of_resources_changed_flag` pins wrapper contract |

### Key Link Verification

| From                                  | To                                                          | Via                                                                | Status | Detail                                                                                           |
| ------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------------------ |
| `server.handle_subscribe`             | `SubscriptionManager.start_polling`                         | `subscription_manager.start_polling(session=..., fetcher=..., on_change=...)` | WIRED  | `server.py:464-471` — captures owning session, passes fetcher from `policy.build_fetcher`        |
| `handle_subscribe.on_change` closure  | `ServerSession.send_resource_updated`                       | `session.send_resource_updated(AnyUrl(changed_uri))`               | WIRED  | `server.py:455-459`                                                                              |
| `JobPolicy` fetcher                   | `ApiClient.get_job`                                          | `asyncio.to_thread(api_client.get_job, job_id)`                    | WIRED  | `policies.py:180`                                                                                |
| `CorpusStatusPolicy` fetcher          | `ApiClient.server_status`                                    | `asyncio.to_thread(api_client.server_status)`                      | WIRED  | `policies.py:200`                                                                                |
| `CorpusFoldersPolicy` fetcher         | `ApiClient.list_folders`                                     | `asyncio.to_thread(api_client.list_folders)`                       | WIRED  | `policies.py:217`                                                                                |
| `run_stdio` finally                   | `SubscriptionManager.cleanup_all`                            | `cleaned = subscription_manager.cleanup_all()` in `finally`        | WIRED  | `server.py:604-615`                                                                              |
| `_poll_loop` cancellation             | `_tasks.pop` + `_last_hash.pop`                              | `try/finally` with identity-check guard                            | WIRED  | `manager.py:301-319`                                                                             |
| `_poll_loop` SubscriptionTerminated   | one final on_change, then clean exit                        | `except SubscriptionTerminated: await on_change(uri, final); return` | WIRED  | `manager.py:239-268`                                                                             |
| `_poll_loop` explicit `CancelledError`| DEBUG log + re-raise                                         | `except asyncio.CancelledError: ... raise`                         | WIRED  | `manager.py:224-238`                                                                             |
| `_patched_get_capabilities`           | `caps.resources.subscribe = True`                            | In-place mutation of pydantic `ServerCapabilities`                 | WIRED  | `server.py:505-522`                                                                              |
| `CorpusFoldersPolicy` interval        | `mcp_subscription_settings.folders_active_interval_s`        | Module-load injection                                              | WIRED  | `policies.py:320-322` + `config.py:160`                                                          |

### Requirements Coverage

| Requirement | Source Plan(s)         | Description                                                                         | Status     | Evidence                                                                                                       |
| ----------- | ---------------------- | ----------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------- |
| SUB-01      | 03 (impl), 04 (e2e)    | `job://<id>` 1s polling + terminal-status auto-cancel                                | SATISFIED  | `policies.py:222-248` + `policies.py:154-185` + `tests/e2e/test_e2e_subscriptions.py::test_subscribe_job_emits_until_terminal` |
| SUB-02      | 03 (impl), 04 (e2e)    | `corpus://status` 30s polling                                                       | SATISFIED  | `policies.py:250-267` + `tests/e2e/test_e2e_subscriptions.py::test_subscribe_corpus_status_emits_on_change`     |
| SUB-03      | 03 (impl), 04 (e2e)    | `corpus://folders` settings-driven cadence (default 5s)                              | SATISFIED  | `policies.py:270-322` + `config.py:63-104` + `tests/e2e/test_e2e_subscriptions.py::test_subscribe_folders_active_cadence` |
| SUB-04      | 01 (hash), 02 (wire), 04 (test) | `notifications/resources/updated` conforms to MCP spec 2025-03-26               | SATISFIED  | `payloads.py:73-105` SHA-256; `server.py:455-459` wired to `send_resource_updated`; `tests/test_notification_shape.py` 9 tests pass |
| SUB-05      | 01 (registry), 04 (cleanup) | Per-session tracking + disconnect cleanup                                       | SATISFIED  | `manager.py:91-97` `_tasks` registry; `server.py:580-616` try/finally cleanup; `tests/e2e/test_e2e_subscriptions.py::test_disconnect_cleans_up_polling_tasks` (counter-based) passes |

No orphaned requirements. No requirement IDs declared in plan frontmatters that are missing from REQUIREMENTS.md mapping. All 5 IDs appear in `REQUIREMENTS.md §"Resource Subscriptions (SUB)"` and all 5 are marked `[x]` shipped.

### Spot-Checked Acceptance Criteria

I opened the actual implementation file for each of these to verify against SUMMARY claims:

1. **SUB-01 terminal auto-cancel** — verified `policies.py:181-182` reads `payload.get("status") in TERMINAL_JOB_STATUSES` and raises `SubscriptionTerminated(payload)`. The constant at `policies.py:92` is `frozenset({"completed", "failed", "cancelled"})` matching CONTEXT decision B. `manager.py:239-268` catches the sentinel, emits one final on_change, returns. Pinned by `test_job_policy_running_to_completed_lifecycle` (`tests/subscriptions/test_policy_integration.py:168`).
2. **SUB-04 64-char hex revision** — verified `payloads.py:104-105` returns `hashlib.sha256(...).hexdigest()`. Pinned by `test_revision_is_64_char_hex_sha256` (`tests/test_notification_shape.py:93-108`) which asserts `len == 64` and all chars in `"0123456789abcdef"`.
3. **SUB-05 try/finally cleanup** — verified `server.py:580-616` wraps `await server.run(...)` in `try/finally`. The `finally` calls `subscription_manager.cleanup_all()` unconditionally. `manager.py:381-402` `cleanup_all()` SYNCHRONOUSLY pops the registry first then cancels tasks (the contract that lets the e2e counter test pass). Pinned by e2e `test_disconnect_cleans_up_polling_tasks`.

### Capability-Flip Patched-Wrapper Verification

| Check                                                                    | Status | Detail                                                                                                                                                  |
| ------------------------------------------------------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SDK still hardcodes `subscribe=False` (justifies wrapper)                | TRUE   | `.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py:212` reads `subscribe=False, listChanged=notification_options.resources_changed`      |
| SDK version pin                                                           | `^1.12.0` | `agent-brain-mcp/pyproject.toml:28`                                                                                                                |
| `_patched_get_capabilities` installed in `build_server`                  | TRUE   | `server.py:505-522` captures original then assigns wrapper to `server.get_capabilities`                                                                 |
| Wrapper flips `caps.resources.subscribe` to True                          | TRUE   | `server.py:518-519` `if caps.resources is not None: caps.resources.subscribe = True`                                                                    |
| Wrapper leaves `listChanged` driven by `notification_options`             | TRUE   | `test_capabilities_subscribe_independent_of_resources_changed_flag` (`test_initialize.py:100-121`) passes — proves listChanged passes through cleanly  |
| Capability advertisement test pins `subscribe is True`                    | TRUE   | `test_capabilities_advertise_subscriptions` (`test_initialize.py:71-98`) passes                                                                         |

### start_polling Locked Signature (Phase 54 Contract)

Verified `manager.py:104-112`:

```python
def start_polling(
    self,
    session: Any,
    uri: str,
    interval_s: float,
    fetcher: Fetcher,
    on_change: OnChange,
    drop_keys: set[str] | frozenset[str] | None = None,
) -> None:
```

Matches the locked signature documented in the prompt. `Fetcher` and `OnChange` are exported type aliases at `__init__.py:40, 52-67` so Phase 54 TOOL-04 can import them verbatim without touching internals.

### Race-Safe Synchronous Cleanup Contract (Plan 01 Lock)

Verified through `manager.py`:
- `start_polling` writes `self._tasks[key] = task` AFTER `asyncio.create_task` but BEFORE returning (`manager.py:167-179`)
- `unsubscribe` pops the registry slot BEFORE calling `task.cancel()` (`manager.py:336-342`)
- `cleanup_session` snapshots victims then pops each before `task.cancel()` (`manager.py:367-372`)
- `cleanup_all` clears the dict synchronously then cancels (`manager.py:395-399`)
- `_poll_loop` finally uses identity-check guard to NOT evict a re-subscribed task (`manager.py:310-313`)

Pinned by `test_subscribe_then_immediate_unsubscribe_cancels_before_first_poll` (`tests/subscriptions/test_manager.py:152-190`) which uses an asyncio.Event that never fires — the test passes, proving the race-safe contract is intact.

### Anti-Patterns Found

None. No `TODO/FIXME/XXX/HACK`, no stub returns, no `console.log`-only handlers, no empty implementations in subscription paths. The two `del uri` lines at `policies.py:197, 214` are explicit "parameter accepted for Protocol-signature consistency" — documented inline; not a stub.

---

## Layering Verification

```
task check:layering
```

Result: **3 kept, 0 broken** (157 files, 390 dependencies analyzed). Contracts kept:
- `server has no upward deps`
- `uds touches only server.models`
- `mcp never calls server internals`

Manual grep `grep -rn "agent_brain_cli" agent_brain_mcp/` returns only a single doc-comment reference at `client.py:8` ("does NOT depend on agent_brain_cli") — no imports.

---

## Regression Verification (Phases 50, 51)

| Test Module                                           | Tests | Status |
| ----------------------------------------------------- | ----- | ------ |
| `tests/test_resources_list.py`                        | included in 75-test batch | PASS |
| `tests/test_resources_read.py`                        | included in 75-test batch | PASS |
| `tests/test_resources_read_parameterized.py` (URI-01/02/03) | included in 75-test batch | PASS |
| `tests/test_resources_read_file.py` (URI-04)          | included in 75-test batch | PASS |
| `tests/test_resources_templates_list.py` (URI-05)     | included in 75-test batch | PASS |

Phase 51 regression: **75/75 pass** (0.83s).

**Full MCP suite:** `poetry run pytest -q` → **250 passed, 43 deselected** (5.02s).
**Full e2e suite:** `poetry run pytest -q -m e2e` → **15 passed, 28 skipped** (15.28s). Skips are tests requiring a live server (`test_e2e_index_and_query.py`, etc.), not subscription-related.

The previously documented v1 test `test_capabilities_have_no_subscriptions` is deleted (correctly) and replaced with `test_capabilities_advertise_subscriptions` per the plan.

---

## Notable Implementation Decisions (For Design Doc Cross-Reference)

1. **`build_server` now returns `tuple[Server, SubscriptionManager]`** (Plan 04 refactor). The Plan 02 private attribute `server._subscription_manager` is retained for backwards compatibility because `test_build_server_attaches_subscription_manager` pinned it. Test asserts `private_attr is manager` to enforce single-instance.
2. **`folders_safety_interval_s` field is defined in settings but NOT wired through the polling loop in Plan 03.** Documented as reserved for a v3 micro-plan if the 5s active cadence proves insufficient. This is a deliberate scope reduction from CONTEXT decision B (5s active / 60s safety) — only the active cadence is implemented. Re-flagged here so the v2 design doc reflects the as-shipped behavior.
3. **`SubscriptionPolicy` uses Protocol read-only `@property` attributes** instead of mutable dataclass fields. Required because mypy + runtime_checkable Protocol conformance against dataclass instances is strict about mutable-vs-read-only attribute compatibility. Test stubs in e2e use simple classes with class-level attributes that structurally satisfy the Protocol.
4. **Notification revision is NOT populated by Plan 02 today.** `handle_subscribe.on_change` closure (`server.py:455-459`) calls `session.send_resource_updated(AnyUrl(uri))` — URI only, no `_meta.revision`. The `canonical_hash` helper exists and is unit-tested as a 64-char SHA-256 producer, but the current wire shape is URI-only (which is spec-compliant per CONTEXT decision C — revision is OPTIONAL "when known"). `tests/test_notification_shape.py` pins BOTH shapes so future revision-bearing emissions stay spec-conformant.
5. **Disconnect e2e test uses counter-based deterministic assertion**, not `psutil.Process.threads()` (despite Plan 04 risk register §7 mentioning psutil). The counter approach reads a tmp-file integer written on every poll — strictly more reliable than psutil thread snapshots. The implementation catches `BrokenResourceError` in an `ExceptionGroup` (Python 3.11+ builtin) because the SDK surfaces an expected anyio error when the subprocess emits a final in-flight message after the client closed its read stream. This is documented inline at `test_e2e_subscriptions.py:489-499` — harmless SDK quirk, not a Phase 52 bug.

---

## Gaps Summary

None. All 5 Success Criteria from ROADMAP.md verified, all 5 SUB requirements satisfied, all key links wired, no anti-patterns, layering intact, regression clean. Phase 52 is complete and ready to unblock Phase 53 (Streamable HTTP) and Phase 54 TOOL-04 (`wait_for_job` reusing `start_polling`).

---

*Verified: 2026-06-03*
*Verifier: Claude (gsd-verifier, goal-backward verification mode)*
