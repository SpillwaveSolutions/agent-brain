---
gsd_state_version: 1.0
milestone: v10.2
milestone_name: MCP v2 — Subscriptions, HTTP Transport, & Tool Completion
current_phase: 53
status: executing
stopped_at: Plan 53-01 complete — CLI transport flags + dispatcher refactor shipped.
last_updated: "2026-06-03T16:26:51.414Z"
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 6
  completed_plans: 0
---

# Agent Brain — Project State

**Last Updated:** 2026-06-03
**Current Milestone:** v10.2 MCP v2 — Subscriptions, HTTP Transport, & Tool Completion
**Status:** Executing Phase 53
**Current Phase:** 53

## Current Position

Phase: 53 (streamable-http-transport) — EXECUTING
Plan: 2 of 3 (Plan 01 complete; Plan 02 next — HTTP listener implementation)

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-03)

**Core value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Current focus:** Phase 53 — streamable-http-transport

## Milestone Summary

```
v3.0 Advanced RAG:           [██████████] 100% (shipped 2026-02-10)
v6.0 PostgreSQL Backend:     [██████████] 100% (shipped 2026-02-13)
v6.0.4 Plugin & Install:     [██████████] 100% (shipped 2026-02-22)
v7.0 Index Mgmt & Pipeline:  [██████████] 100% (shipped 2026-03-05)
v8.0 Performance & DX:       [██████████] 100% (shipped 2026-03-15)
v9.0 Multi-Runtime:          [██████████] 100% (shipped 2026-03-16)
v9.1.0 Skill-Runtime:        [██████████] 100% (shipped 2026-03-16)
v9.3.0 LangExtract+Config:   [██████████] 100% (shipped 2026-03-22)
v9.4.0 Doc Accuracy Audit:   [██████████] 100% (shipped 2026-03-20)
v9.5.0 Config Val & Lang:    [██████████] 100% (shipped 2026-03-31)
v9.6.0 Runtime Parity:       [██▌       ]  25% (1/4 phases — parked, deferred to post-MCP)
v10.0.0–v10.0.6 Patch Train: [██████████] 100% (shipped 2026-05-25 → 2026-05-27)
v10.1.0 MCP v1:              [██████████] 100% (shipped 2026-05-30; UDS + 7-tool stdio MCP + CLI dual transport)
v10.1.2 MCP package rename:  [██████████] 100% (shipped 2026-06-01; agent-brain-mcp PyPI distribution + standalone user guide)
v10.2 MCP v2:                [█████▌    ]  54% (Phases 50–51 complete + Phase 52 plans 1-4 complete + Phase 53 plan 1 complete — 13/24 plans)
```

## v10.2 Phase Progress

| Phase | Status | Requirements | Plans |
|-------|--------|--------------|-------|
| 50. Server endpoint prep + v2 design doc | ✓ Complete (2026-06-03) | VAL-05 ✓ | 4/4 |
| 51. URI schemes + templates | ✓ Complete (2026-06-03) | URI-01 ✓ · URI-02 ✓ · URI-03 ✓ · URI-04 ✓ · URI-05 ✓ | 4/4 |
| 52. Resource subscriptions | Executing (4/4 plans done; awaiting verifier) | **SUB-01 ✓**, **SUB-02 ✓**, **SUB-03 ✓**, **SUB-04 ✓**, **SUB-05 ✓** | 4/4 |
| 53. Streamable HTTP transport | Executing (1/3 plans done) | **HTTP-01 partial (Plan 01 — CLI surface)**, HTTP-02, **HTTP-03 ✓ (dispatcher level)** | 1/3 |
| 54. 9 remaining MCP tools | Planned, not started | TOOL-01..TOOL-09 | 0/4 |
| 55. Validation, contract tests & QA gate | Planned, not started | VAL-01, VAL-02, VAL-03, VAL-04 | 0/5 |

**Coverage:** 27/27 v1 requirements mapped to phases (no orphans, no duplicates)
**Total plans:** 24 (Phase 50: 4 ✓ · Phase 51: 4 · Phase 52: 4 · Phase 53: 3 · Phase 54: 4 · Phase 55: 5)
**Phase 50 shipped:** v2 design doc (486 lines) · `GET /query/chunk/{chunk_id}` (ChromaDB + Postgres) · `GET /graph/entity/{type}/{id}` (Kuzu + Simple, #178 503 fallback) · `agent_brain_server/security/file_sandbox.py` (4 deny reasons, 10 MiB cap) — full suite green: 1269 passed, 0 regressions, Black/Ruff/mypy strict all clean

**Phase 51 shipped:** Parameterized URI dispatcher + 4 handlers (`chunk://`, `graph-entity://`, `job://`, `file://`) + `resources/templates/list` advertising 4 RFC 6570 templates with byte-identical CONTEXT decision B strings + `MIN_BACKEND_VERSION` bumped to `10.2.0` + pyproject pins (`agent-brain-rag`, `agent-brain-uds`) bumped to `^10.2.0` in lockstep + `agent_brain_mcp.security` re-export shim sharing Phase 50's sandbox helpers without forking — 50 net new tests added across the four plans, 141 MCP tests + 416 monorepo tests passing at HEAD, Black/Ruff/mypy strict all clean, 3 layering contracts kept.

## v10.2 Cross-Phase Risk Register (from workflow summarizer)

Surface-level risks the planner agents identified across phases that need cross-phase attention during execution:

- **#178 Kuzu SIGSEGV carry-forward**: Phase 50 Plan 03 (multi-backend graph endpoint), Phase 51 Plan 02 (graph-entity:// returns 503 when Kuzu corrupts), Phase 55 Plan 03 (subscription e2e tolerates 503). Operator workaround: `graphrag.store_type: simple`.
- **#179 Bearer-token API auth mid-flight**: Phase 50 Plan 01 design doc surfaces composition explicitly; Phase 51 endpoints inherit middleware; Phase 53 USER_GUIDE two-axis diagram mitigates backend-vs-listen-axis confusion.
- **MCP SDK API drift**: Phase 51 Plan 04 (ResourceTemplate decorator), Phase 52 Plan 02 (ServerSession.send_resource_updated), Phase 53 Plan 01 (StreamableHTTPSessionManager existence), Phase 55 Plan 04 (streamablehttp_client) all bind to pinned SDK version. Phase 50 design doc pins 2026-03-26 spec; Phase 55 Plan 05 audits pyproject.toml still pins SDK version (D-03).
- **MIN_BACKEND_VERSION = 10.2.0** (Phase 51 Plan 04): forces release-train ordering — agent-brain-server 10.2.0 ships BEFORE agent-brain-mcp 10.2.0.
- **Phase 50 → Phase 51 surface contract**: Phase 51 Plan 03 imports Phase 50's `file_sandbox` helpers verbatim; signature drift would block file:// (mitigation: Phase 51 Plan 03 starts with import-verification step).
- **Phase 52 → Phase 54 contract**: Phase 54 Plan 04 (wait_for_job) reuses Phase 52 Plan 01's `SubscriptionManager.start_polling()` primitive — Plan 01 documents this as a public API guarantee.
- **+60-90s local pre-push cost** from Phase 55 Plan 05 folding MCP/UDS into root before-push — documented in CHANGELOG and v2 design doc.

Full cross-phase risk register: 17 items in the workflow summarizer output (saved alongside the workflow transcript).

## Accumulated Context

### Key Context Carried Forward

- **MCP v1 in production:** `agent-brain-mcp` is published to PyPI. Stdio transport, 7 tools, 5 read-only resources, 6 prompts. UDS transport (`agent-brain-uds`) is also live. CLI supports `--transport {auto,uds,http}`.
- **Source design exists:** `docs/plans/2026-05-28-mcp-uds-transport-design.md` is the master design for v1/v2/v3/v4. v2 work is scoped in `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` and tracked by umbrella issue #186.
- **Phase order is hard-blocking:** Phase 50 must precede Phase 51 (URI-01/02/04 need server endpoints); Phase 51 must precede Phase 52 (SUB-01 needs `job://` addressable); Phase 52 must precede Phase 54 (TOOL-04 `wait_for_job` needs notification infrastructure); Phase 55 must be last (folds packages into root QA gate). Phase 53 (HTTP transport) is independent of Phase 52 and can run in parallel.
- **Prerequisites for downstream milestones:** v3 (#187) depends on v2's HTTP transport (Phase 53). v4 (#188) depends on v3's `McpHttpBackend`.

### Decisions from Prior Milestones (still load-bearing)

- [v9.5.0]: Runtime install behavior covered structurally; headless parity through real external CLIs still unverified (v9.6.0 phases 47–49 deferred — re-evaluate during MCP v3)
- [v10.0.6]: Kuzu graph store self-heals from corruption via triplet snapshots (#166)
- [v10.1.0]: MCP v1 shipped — `agent-brain-mcp` package, UDS transport, 7-tool stdio server, CLI dual transport
- [v10.1.2]: PyPI package renamed to `agent-brain-mcp`; standalone MCP user guide added (commits `1e34818`, `cf7a364`)
- **Decision (2026-06-01):** Pivot away from MCP-is-out-of-scope stance recorded in PROJECT.md v9.6.0 era. MCP is now the active investment direction; that out-of-scope line has been removed.
- **Decision (2026-06-02):** v2 design doc (VAL-05) lands in Phase 50, *before* MCP-layer implementation, so reviewers can challenge the subscription/transport approach before code lands.
- **Decision (2026-06-03, Plan 51-04):** The four `uriTemplate` strings advertised by `resources/templates/list` (`chunk://{chunk_id}`, `graph-entity://{type}/{id}`, `job://{job_id}`, `file://{+path}`) are a forward-compatibility commitment per Phase 51 CONTEXT decision B — once published in 10.2.0, MCP client libraries lock onto them and changes are breaking. The strings are pinned by `test_registry_uri_templates_match_expected_set` against silent drift.
- **Decision (2026-06-03, Plan 51-04):** `file://{+path}` uses RFC 6570 reserved expansion (operator `+`) rather than the default expansion (`{path}`). Default expansion percent-encodes `/` as `%2F`, which is the WRONG behavior for filesystem paths. Pinned by `test_file_template_uses_reserved_expansion`.
- **Decision (2026-06-03, Plan 51-04):** Release-train coupling locked in two places. Runtime `MIN_BACKEND_VERSION = "10.2.0"` (refuses startup against older server) + install-time pyproject pin `agent-brain-rag = "^10.2.0"`. `agent-brain-server 10.2.0` MUST publish to PyPI BEFORE `agent-brain-mcp 10.2.0`; existing lockstep release flow (`.claude/commands/ag-brain-release.md`) handles propagation timing.
- **Decision (2026-06-03, Plan 51-04):** `resources.subscribe` capability stays `False` through Phase 51. Phase 52 owns flipping it; Phase 51 explicitly preserves the v1 wire shape so clients that don't yet understand subscriptions are unaffected.
- **Decision (2026-06-03, Plan 51-01):** Parameterized URI dispatcher in `agent_brain_mcp/resources/parameterized.py` uses a *single* `ParsedURI` dataclass (all per-scheme fields optional, only the relevant ones populated) and a *closed* `PARAMETERIZED_SCHEMES` frozenset with NotImplementedError-raising placeholders for `chunk`/`graph-entity`/`file`. Plans 51-02 and 51-03 swap the placeholder values in `PARAMETERIZED_HANDLERS` without touching the dispatcher or the registry shape. Error-data shapes for malformed-URI (`{uri, reason}`) vs backend-404 (`{scheme, <id>, httpStatus, cause}`) are intentionally different — see module docstring.
- **Decision (2026-06-03, Plan 51-02):** Per-scheme error refinement preserves the *original* `McpError.code` and only enriches `data`. For `graph-entity` 503 responses, the handler additionally extracts a `reason` slug (`graphrag_disabled` or `kuzu_unavailable`) from the Phase 50 server's detail body via a forgiving substring scan against a closed reason set — operators (and MCP clients) can route on `data.reason` without re-parsing `data.cause`. This handles the #178 Kuzu SIGSEGV fallback transparently across the MCP boundary.
- **Decision (2026-06-03, Plan 51-02):** `graph-entity://` URI parser allows entity ids containing `/` (e.g., `graph-entity://Function/AuthService/login` → entity_id=`AuthService/login`). Phase 50 decision B explicitly permits hierarchical ids; the parser treats `raw_path.lstrip("/").rstrip("/")` as the FULL id including inner slashes. Phase 50's FastAPI path-style `{entity_id}` route honors this verbatim.
- **Decision (2026-06-03, Plan 51-03):** SHARE-don't-fork sandbox helper. `agent_brain_mcp/security/__init__.py` is a pure re-export shim of Phase 50's `agent_brain_server/security/file_sandbox.py`. The shim's docstring forbids any logic. Forking would create silent policy drift between server-side and MCP-side `file://` reads — load-bearing security invariant from CONTEXT specifics #2.
- **Decision (2026-06-03, Plan 51-03):** Dispatcher dual-return signature. The parameterized handler return type widened from `Awaitable[str]` to `Awaitable[str | ReadResourceContents]`. JSON-backed schemes (`job`, `chunk`, `graph-entity`) still return `str` (wrapped as `application/json`); `file://` returns `ReadResourceContents` directly so it can carry a per-file `mime_type` and optional `bytes` payload (auto-base64-encoded as `BlobResourceContents` by the MCP SDK at the wire boundary). Single `isinstance` check at the dispatch boundary; fully backward-compatible.
- **Decision (2026-06-03, Plan 51-03):** `file://` URI accepts ONLY the canonical three-slash form (`file:///abs/path`). The two-slash form (`file://host/path`) is rejected with `reason: "missing_path"` because urlsplit reads `host` as the authority, which would otherwise be a relative-path-smuggling vector against the sandbox check.
- **Decision (2026-06-03, Plan 51-03):** NO cache on `list_folders()`. Allowed roots refresh on every `file://` read (regression-pinned by `test_read_file_uri_roots_refresh_on_each_read`). Stale roots would silently widen the sandbox after operator folder mutations — CONTEXT decision E load-bearing.
- **Decision (2026-06-03, Plan 52-01):** `SubscriptionManager` public API is LOCKED on first commit. The `start_polling(session, uri, interval_s, fetcher, on_change, drop_keys=None)` signature, plus `unsubscribe / cleanup_session / cleanup_all / is_subscribed / active_count`, plus `canonical_hash` + `DEFAULT_DROP_KEYS` + `SubscribableUriRejected`, are imported verbatim by Plans 02/03/04 AND by Phase 54 Plan 04 (`wait_for_job` progress notifications reuse the polling primitive). The Phase 54 reuse contract is cited in every module-level docstring under `agent_brain_mcp/subscriptions/`.
- **Decision (2026-06-03, Plan 52-01):** Synchronous registry pop in `unsubscribe / cleanup_session / cleanup_all`. The plan's original spec relied on the polling-task `try/finally` block to clean the registry, but when a task is cancelled BEFORE its coroutine starts running (the load-bearing subscribe-then-unsubscribe race), asyncio skips the body entirely — finally never runs. Fixed by making the primary cleanup synchronous; the finally remains as defense-in-depth for the case where the loop crashes mid-iteration, with an identity check (`current is asyncio.current_task()`) to avoid evicting a re-subscribed task that took the same slot. Pinned by `test_subscribe_then_immediate_unsubscribe_cancels_before_first_poll`.
- **Decision (2026-06-03, Plan 52-01):** `DEFAULT_DROP_KEYS` is a `frozenset` (immutable, hashable) containing `{timestamp, updated_at, elapsed_ms, polled_at, now}` — the CONTEXT-mandated 5-key allowlist for volatile fields that `canonical_hash` strips at every nesting depth. Recursive strip means uvicorn's deep-embedded request timestamps inside `corpus://status` payloads do NOT cause spurious `notifications/resources/updated` every 30s. Pinned by `test_deeply_nested_timestamp_dropped` and 4 sibling tests.
- **Decision (2026-06-03, Plan 52-01):** Fetcher exception inside the polling loop is logged via `logger.exception` and the loop proceeds to the next interval. A transient HTTP 5xx from `agent-brain-server` MUST NOT tear down a long-running subscription. Pinned by `test_loop_survives_fetcher_exception_and_keeps_polling`.
- **Decision (2026-06-03, Plan 52-02):** MCP SDK 1.12.x hardcodes `resources.subscribe=False` at `mcp/server/lowlevel/server.py:211` with no opt-in knob on `NotificationOptions` and no derivation from `_subscribe_resource_handler` presence. Phase 52 flips the capability via a `_patched_get_capabilities` wrapper installed inside `build_server()`. Documented inline with a line-number reference; future SDK upgrades can drop the wrapper if/when the capability becomes flag-driven. Pinned by `test_capabilities_advertise_subscriptions` + `test_e2e_initialize_advertises_subscribe_capability`.
- **Decision (2026-06-03, Plan 52-02):** Subscribable allowlist enforced via TWO-step gate: (1) `_is_known_uri` checks `RESOURCE_REGISTRY` + `PARAMETERIZED_SCHEMES` → produces `SubscribableUriRejected(reason="unknown_uri")` for misses; (2) `resolve_policy` looks up `SUBSCRIPTION_POLICIES` (exact-then-scheme) → produces `SubscribableUriRejected(reason="not_subscribable")` for known-but-non-subscribable URIs (`corpus://config`, `chunk://`, `graph-entity://`, `file://`). Order matters — clients distinguish "we don't know that scheme" from "we know it but you can't subscribe."
- **Decision (2026-06-03, Plan 52-02):** Duplicate subscribe is pre-checked at the wire handler via `manager.is_subscribed()`. Without this, `manager.start_polling`'s `RuntimeError("Already subscribed")` would surface as a generic internal error. Pre-check produces `SubscribableUriRejected(reason="duplicate_subscribe")` with the proper `-32602` code; Phase 52 CONTEXT decision A picks strict rejection so the polling-task lifecycle stays deterministic.
- **Decision (2026-06-03, Plan 52-02):** Manager ownership uses `server._subscription_manager` private-attr workaround for Plan 02; Plan 04 refactors `build_server()` to return `(server, manager)` so `run_stdio`'s `finally` block can call `manager.cleanup_all()` cleanly. Pinned by `test_build_server_attaches_subscription_manager` so future readers see the contract.
- **Decision (2026-06-03, Plan 52-02):** `policies.py` registry key shape is either exact URI (`corpus://status`) OR scheme prefix ending in `://` (`job://`). `resolve_policy` tries exact first, then scheme-prefix — exact-URI entries always win over scheme entries. Pinned by `test_exact_uri_policy_wins_over_scheme`. Critical for Plan 03 where `corpus://status` (exact) and a future per-scheme `corpus://` entry must not collide.
- **Decision (2026-06-03, Plan 52-02):** `SubscriptionPolicy` is a `runtime_checkable` `Protocol` (not an ABC). Plan 03's concrete policies will be plain dataclasses that happen to satisfy the Protocol; structural typing keeps test stubs lightweight (no inheritance required for `monkeypatch.setitem` fixtures). Stub policies installed via `monkeypatch.setitem(SUBSCRIPTION_POLICIES, ...)` are ADDITIVE so Plan 03's real policies can coexist with test stubs without breakage.
- **Decision (2026-06-03, Plan 52-02):** Test pattern: integration tests INLINE the `async with create_connected_server_and_client_session` block rather than wrapping it in a `pytest_asyncio.fixture` — fixture-wrapped harness trips anyio's `RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` because the fixture's enter/exit cross task boundaries. Documented inline in `TestSubscribeHandlerDispatch` so future contributors don't fall into the same trap.
- **Decision (2026-06-03, Plan 52-03):** `SubscriptionTerminated` is a control-flow sentinel, NOT an error. Plan 03's `JobPolicy.fetcher` raises it when the polled job reports status in `TERMINAL_JOB_STATUSES = {completed, failed, cancelled}`. `_poll_loop` catches the sentinel BEFORE the generic `except Exception` (which logs+continues), emits one final `on_change` with the terminal payload (if provided), and returns. Plan 01's synchronous-cleanup contract is preserved verbatim — the finally block + `unsubscribe`/`cleanup_*` synchronous paths both scrub the registry. Pinned by `test_manager_catches_subscription_terminated_and_emits_final` + `test_job_policy_running_to_completed_lifecycle`.
- **Decision (2026-06-03, Plan 52-03):** `CorpusStatusPolicy.drop_keys = DEFAULT_DROP_KEYS | {request_id}`. Uvicorn's `GET /health/status` payload embeds a per-request UUID; without dropping it the SHA-256 churns every 30s regardless of actual change. `CorpusFoldersPolicy.drop_keys = DEFAULT_DROP_KEYS | {last_polled}` but PRESERVES `last_indexed` — that's a real change signal that file watcher + index job completion update. Pinned by `test_corpus_status_drop_keys_suppress_request_id_churn` + `test_corpus_folders_last_indexed_change_is_not_suppressed`.
- **Decision (2026-06-03, Plan 52-03):** `CorpusFoldersPolicy.__init__` accepts `interval_s` so the module-level registry instantiation reads from `mcp_subscription_settings.folders_active_interval_s` at import time. Tests inject 0.05s for speed. The 60s "safety poll" cadence (`folders_safety_interval_s`) is exposed as a settings field for operator pre-staging but Plan 03 does NOT wire it through the polling loop — v2 has no separate no-subscriber branch (CONTEXT decision E + specifics §3). Reserved for a future v3 micro-plan if 5s active cadence proves insufficient.
- **Decision (2026-06-03, Plan 52-03):** `MCPSubscriptionSettings` Pydantic `BaseModel` with `Field(default=..., gt=0)` validation on both interval fields. Non-positive intervals would starve the polling loop (0) or invert asyncio.sleep's contract (<0). Non-numeric env vars raise `RuntimeError` at config-module import with the offending env var name surfaced — clear failure mode at startup, not at runtime. Two new env vars: `AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_ACTIVE_INTERVAL_S` (5.0 default) + `AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_SAFETY_INTERVAL_S` (60.0 default). No hot reload — restart MCP server to pick up changes.
- **Decision (2026-06-03, Plan 52-03):** `SubscriptionPolicy` Protocol attributes refactored from settable class-level vars (`uri_pattern: str, ...`) to read-only `@property` declarations. Mypy strict refuses dataclass instances with effectively read-only attributes as matches for a Protocol with settable attributes. Properties express the read-only intent at the type level and let mypy admit `@dataclass` (non-frozen) implementations. Runtime `isinstance(policy, SubscriptionPolicy)` still works via `@runtime_checkable`. Pinned by `test_*_policy_satisfies_protocol` tests.
- **Decision (2026-06-03, Plan 52-03):** `build_fetcher` extracted from `@staticmethod` inside the dataclasses to module-level `_build_*_fetcher` functions assigned via `field(default=_build_*_fetcher)`. Mypy treats `@staticmethod` as a method descriptor, not a plain `Callable`, and refuses Protocol structural matches. Module-level functions produce a plain `function`-typed instance attribute that satisfies `PolicyFetcherFactory` verbatim. Documented inline in `policies.py` with explanation.
- **Decision (2026-06-03, Plan 52-04):** `build_server()` signature changed from `Server` to `tuple[Server, SubscriptionManager]`. Plan 02's `server._subscription_manager` private-attr workaround is PRESERVED for backwards compatibility — the same `SubscriptionManager` instance is reachable both via tuple unpacking and via the private attr. `test_build_server_attaches_subscription_manager` was extended to assert identity-equality between the two surfaces so future contributors see the contract: new code prefers tuple unpacking; legacy callers keep working.
- **Decision (2026-06-03, Plan 52-04):** `run_stdio(server, subscription_manager)` body wrapped in `try / finally`; the finally calls `subscription_manager.cleanup_all()` UNCONDITIONALLY on every exit path (graceful stdio EOF, exception, mid-loop crash) with an info-level log line when ≥1 task was cancelled. `cleanup_all` is idempotent (empty registry returns 0) so re-entrancy is safe. The HTTP transport analog (Phase 53) inherits this design verbatim — documented in the v2 design doc §3.3.1 risk carry-forward.
- **Decision (2026-06-03, Plan 52-04):** `_poll_loop` gains an EXPLICIT `except asyncio.CancelledError` clause that DEBUG-logs `session_id_short + uri` then RE-RAISES. Re-raising is load-bearing: Plan 01's `finally` block + the manager's primary synchronous-cleanup paths both rely on the cancellation propagating. Plan 04's leaked-task assertion test (`test_disconnect_cleans_up_polling_tasks`) is the diagnostic motivation — without the explicit log, debugging a hung polling task in CI required ratcheting the root logger to DEBUG; the targeted log is cheaper.
- **Decision (2026-06-03, Plan 52-04):** SDK e2e pattern for collecting notifications uses `ClientSession(read, write, message_handler=collector)` where `collector` filters `ServerNotification` whose `.root` is a `ResourceUpdatedNotification`. The SDK 1.12.x exposes this kwarg at `mcp/client/session.py:121`; the spike resolved Plan 04's risk register flag about "may need to read messages off the underlying read stream manually." Documented in `_make_collector` docstring so future contributors don't repeat the spike.
- **Decision (2026-06-03, Plan 52-04):** Disconnect-cleanup primary assertion is COUNTER-BASED (deterministic): the subprocess writes its fetch count to a file path passed via `FETCHER_COUNTER_PATH` env var; the test waits until counter ≥ 2 to prove polling fired, then exits the stdio_client context, then waits 1.5s and asserts the counter delta ≤ 1 (allows ≤1 in-flight poll that crossed the cancellation boundary). No psutil thread-count dependence. The risk register's psutil cross-check was deemed unnecessary once the counter assertion proved stable across 3 consecutive runs.
- **Decision (2026-06-03, Plan 52-04):** Disconnect test catches `builtins.BaseExceptionGroup` and filters out `anyio.BrokenResourceError`. The SDK's `stdio_client` task group surfaces this when the subprocess emits a final in-flight notification AFTER the client closed its read side; the noise is harmless (the subprocess write succeeds; the parent stopped reading) and Plan 04's cleanup hook still fires correctly on the subprocess side. The filter is documented inline with a multi-line comment; non-`BrokenResourceError` exceptions are re-raised so real bugs aren't swallowed. The same filter pattern will likely extend to Phase 53's HTTP-transport e2e tests with a different exception class for HTTP framing — added to the v2 design doc §3.3.1 risk register.
- **Decision (2026-06-03, Plan 52-04):** Two-sessions test scoped to CROSS-PROCESS isolation (not in-process). For stdio, each `stdio_client` invocation spawns its own MCP subprocess; the "two sessions on one process" semantic only applies to Streamable HTTP (Phase 53). The "real" multi-session isolation is Plan 01's `test_two_sessions_for_same_uri_get_independent_tasks` which runs inside a single asyncio loop. Plan 04's e2e test verifies the trivial-but-load-bearing property that session A's process exit doesn't affect session B's notification stream — documented in the test docstring + v2 design doc.
- **Decision (2026-06-03, Plan 52-04):** SUB-04 conformance pins BOTH the minimal URI-only shape (the v2 default — Plan 02's `on_change` closure calls `ServerSession.send_resource_updated(uri)` which builds the minimal form) AND the optional `_meta.revision` envelope (CONTEXT decision C "when known" path). Even though v2 doesn't populate revision today, the contract is locked here so any future revision-bearing path stays spec-conformant. `canonical_hash` is independently verified against `hashlib.sha256(json.dumps(stripped, sort_keys=True, separators=(",", ":")))` — pins the digest computation against accidental drift.
- **Decision (2026-06-03, Plan 53-01):** Two-axis transport labels on the `Server` instance. Phase 52's single `build_server(transport=)` kwarg is split into orthogonal `backend_transport=` (how MCP talks to `agent-brain-serve`) and `listen_transport=` (how the MCP client reaches this server). Phase 53 D-01 mandate. Both surfaced as private Server attributes (`_agent_brain_backend_transport` + `_agent_brain_listen_transport`) for in-process testing; Plan 03 will wire them into the MCP `initialize` `serverInfo._meta` blob over the wire.
- **Decision (2026-06-03, Plan 53-01):** Backwards-compat alias for legacy `build_server(transport=)`. Routes to `backend_transport` with `warnings.warn(..., DeprecationWarning, stacklevel=2)`. Keeps Plan 52's tuple-return contract intact and lets every existing build_server() call site (39 references across 15 test files via `_, srv = build_server(client)`) continue to work without coordinated rename pressure. Slated for full removal in Phase 55. When both `transport=` and `backend_transport=` are passed, the legacy `transport=` wins — keeps the migration path single-knob (replacing `transport=X` with `backend_transport=X` doesn't accidentally drop the value mid-edit). Pinned by `test_legacy_transport_kwarg_does_not_override_explicit_backend`.
- **Decision (2026-06-03, Plan 53-01):** Legacy `_agent_brain_transport` private attribute kept as one-way shim mirroring `backend_transport` only (NOT `listen_transport`). No production tests read it (verified by grep), but the shim costs nothing and protects any downstream observability/debug code that may sample the private attribute. Inline comment marks the shim for Phase 55 removal.
- **Decision (2026-06-03, Plan 53-01):** `run_http(server, subscription_manager, *, host, port)` stub signature mirrors `run_stdio(server, subscription_manager)`. The manager parameter is unused in Plan 01 (stub raises `NotImplementedError("HTTP transport implemented in Plan 02")`) but is in the signature so Plan 02 inherits the Phase 52 Plan 04 disconnect-cleanup contract symmetrically across both transports — the HTTP-side `try/finally` will need to call `manager.cleanup_all()` the same way `run_stdio` does. Phase 53 carry-forward from v2 design doc §3.3.1 "HTTP transport analog inherits this design verbatim."
- **Decision (2026-06-03, Plan 53-01):** `main_async` dispatcher raises `ValueError(f"Unknown transport: {transport!r}")` for unrecognized values. Click's `Choice(case_sensitive=False)` already rejects bogus values at the CLI layer — the `ValueError` branch is the defensive guard for direct callers (tests, embeddings) that bypass the CLI wrapper. No-silent-fallback (HTTP-03) extended to the runtime-error path: if `run_http` raises (e.g., port-in-use `OSError`), the error propagates verbatim — the dispatcher does NOT silently retry with `run_stdio`. Pinned by `test_no_silent_fallback_on_http_runtime_error`.
- **Decision (2026-06-03, Plan 53-01):** `AGENT_BRAIN_MCP_TRANSPORT` env var is documented as reserved-but-not-honored per Phase 53 D-02. The `--transport` help text explicitly says so ("AGENT_BRAIN_MCP_TRANSPORT env is reserved but NOT honored in v2 (Phase 53 D-02).") to head off operator confusion. No negative-space test (would be brittle); Plan 03 USER_GUIDE.md update will repeat the warning.

### Blockers/Concerns

- **#178 Kuzu SIGSEGV during sustained GraphRAG indexing** — workaround exists (`graphrag.store_type: simple`), not blocking v10.2 but should be tracked separately
- **#184 GraphSnapshotManager auto-replay scope-gap** — Kuzu-adjacent, not blocking v10.2
- **#179 API authentication design** — green-lit 2026-06-01; Jeremy implementing under separate PR; secure-by-default key generation. NOT a v10.2 milestone deliverable (MCP v2 explicitly says "loopback only, no auth yet — auth is v4")

### Open GitHub Issues Relevant to v10.2 Scope

- **#186** — MCP v2 umbrella (this milestone)
- **#189** — MCP roadmap meta (parent tracker)
- **#187** — MCP v3 (next milestone candidate; blocked on v2 HTTP transport = Phase 53)
- **#188** — MCP v4 OAuth (blocked on v3 `McpHttpBackend`)
- **#167** — original MCP server design issue (v1 implementation tracker; v1 has shipped, can be closed if not already)

### Other Open Issues (NOT in v10.2 scope)

Feature backlog (#152, #154, #155, #156, #157, #158, #160, #162, #163, #164) and bugs (#178, #184) and security (#179) tracked separately; revisit during v10.3 / v11 planning.

## Session Continuity

**Last Session:** 2026-06-03T16:26:51.410Z
**Stopped At:** Plan 53-01 complete — `--transport [stdio|http]` / `--host` / `--port` Click options shipped on `agent-brain-mcp`; `build_server()` refactored to split Phase 52's single `transport=` kwarg into orthogonal `backend_transport=` / `listen_transport=` axes (Phase 53 D-01) with backwards-compat `transport=` deprecation alias emitting `DeprecationWarning(stacklevel=2)` and routing to `backend_transport`; legacy `_agent_brain_transport` private attribute kept as one-way shim mirroring `backend_transport` (Phase 55 removal noted); both new axis labels (`_agent_brain_backend_transport`, `_agent_brain_listen_transport`) surfaced on Server instance for in-process testing (Plan 03 will wire over the wire via `serverInfo._meta`); `run_http(server, manager, *, host, port)` stub raises `NotImplementedError("HTTP transport implemented in Plan 02")` with the manager parameter in place so Plan 02 inherits the Phase 52 Plan 04 disconnect-cleanup contract symmetrically; `main_async()` accepts new `transport`/`host`/`port` kwargs and dispatches stdio→`run_stdio(server, manager)` vs http→`run_http(server, manager, host=host, port=port)` vs invalid→`ValueError("Unknown transport: …")` (no-silent-fallback HTTP-03 invariant pinned by `test_no_silent_fallback_on_http_runtime_error`); 24 net new tests across 2 new files + 1 smoke touch (10 `tests/test_cli_transport_flags.py` + 13 `tests/test_dispatch.py` + 1 `tests/test_smoke.py` legacy-alias assertion); 250 prior tests unchanged → 274 MCP tests passing; full `task before-push` exit 0 (416 monorepo tests, 3 layering contracts kept, Black + Ruff + mypy strict all clean); 2 atomic commits (`3e76220` feat, `52ddfdf` test). MCP SDK availability gate cleared on first run (`from mcp.server.streamable_http_manager import StreamableHTTPSessionManager`). 1 plan deviation auto-applied (Rule 2 — added `test_no_silent_fallback_on_http_runtime_error` to pin HTTP-03 dispatcher invariant the plan listed but didn't enumerate in test cases). Plan 53-02 (HTTP listener implementation) unblocked.
**Resume File:** `.planning/phases/53-streamable-http-transport/plans/02-http-listener.md` (TBD; Plan 02 will swap the `run_http` stub for in-process uvicorn wrapping the SDK's `StreamableHTTPSessionManager` at `/mcp` + `/healthz` probe + loopback host whitelist enforcement per D-08)
**Next Action:** Plan 53-02 — HTTP listener implementation. Plan 01's `run_http(server, manager, *, host, port)` stub is the swap point; Plan 02 must (a) replace `raise NotImplementedError` with the in-process uvicorn + StreamableHTTPSessionManager wiring, (b) enforce the loopback whitelist (`127.0.0.1` / `localhost` / `::1`) per D-08, (c) add the `/healthz` probe per D-07, (d) wrap port-in-use OSError as `click.ClickException` per D-12, (e) wire the symmetric disconnect-cleanup hook (`manager.cleanup_all()` in `try/finally`) mirroring `run_stdio`. Plan 53-03 ships SDK smoke + USER_GUIDE.md update. Phase 52 still pending verifier scoring (Wave 4) — orchestrator should run that in parallel with Plan 53-02 execution since the two are independent.

## Recommended Execution Order

Per workflow summarizer (verified ready_to_execute: true):

1. **Phase 50** — Foundation (design doc + 2 endpoints + sandbox helpers). MUST land first.
2. **Phase 51** — URI schemes (depends on Phase 50 endpoints + file_sandbox)
3. **Phase 52** — Subscriptions (depends on Phase 51's job:// URI registration)
4. **Phase 53** — Streamable HTTP transport (independent of Phase 52; can run in parallel with 51-52)
5. **Phase 54** — 9 remaining tools (depends on Phase 52's ProgressNotifier for wait_for_job; should land after Phase 53 so new tools surface on both transports)
6. **Phase 55** — Validation + QA gate (validates Phases 50-54; must be last; verification-only, no new production code)

---
*State updated: 2026-06-03 — Plan 52-04 shipped (build_server tuple refactor + run_stdio disconnect cleanup hook + _poll_loop explicit CancelledError clause + 9 SUB-04 notification-shape conformance tests + 5 SDK-driven e2e subscription tests covering SUB-01/02/03/05 end-to-end + Phase 50 v2 design doc §3.3.1 Phase 52 ship-outcome subsection); +24 tests across MCP package (9 SUB-04 + 5 e2e + Plan 03 e2e re-included when full suite runs); 265 MCP tests passing; 416 monorepo tests passing; Phase 52 plans 1-4 all complete; SUB-01..05 all closed and end-to-end validated against the real MCP wire via the official Python SDK; 12/24 plans complete across the v10.2 milestone; Phase 52 awaiting verifier scoring (Wave 4); Phase 53 (Streamable HTTP transport) is the next workable phase.*

*State updated: 2026-06-03 — Plan 53-01 shipped (CLI `--transport`/`--host`/`--port` Click options + `build_server()` two-axis split with `transport=` DeprecationWarning alias + `run_http()` NotImplementedError stub awaiting Plan 02 + `main_async()` dispatcher with no-silent-fallback invariant); +24 tests across MCP package (10 CLI flag + 13 dispatcher + 1 smoke); 274 MCP tests passing (was 250); 416 monorepo tests passing; 2 atomic commits (`3e76220` feat, `52ddfdf` test) + this metadata commit; HTTP-01 partial (CLI surface) + HTTP-03 ✓ (dispatcher-level explicit selection / no silent fallback); 13/24 plans complete across the v10.2 milestone; Phase 53-02 (HTTP listener implementation) is the next workable plan within Phase 53.*
