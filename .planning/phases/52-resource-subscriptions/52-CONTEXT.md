# Phase 52: Resource subscriptions — Context

**Gathered:** 2026-06-02
**Status:** Ready for planning

<domain>
## Phase Boundary

MCP clients can subscribe to live resources and receive spec-compliant `notifications/resources/updated` events, with per-client subscription tracking and disconnect cleanup. Phase 52 ships:

1. MCP server advertises `resources.subscribe: true` in `initialize` capabilities (flipping the v1 default of `false` set in `agent-brain-mcp/agent_brain_mcp/server.py`).
2. `resources/subscribe` and `resources/unsubscribe` handlers wired via the MCP SDK's `@server.subscribe_resource()` / `@server.unsubscribe_resource()` decorators (`mcp/server/lowlevel/server.py:408-432`).
3. A **SubscriptionManager** that tracks `(session_id, uri) → polling_task` and emits `notifications/resources/updated` via `ServerSession.send_resource_updated(uri)` on the **owning session only**.
4. Per-URI cadence policies:
   - `job://<id>` → 1s polling against `GET /index/jobs/{id}`; auto-cancels when job reaches a terminal state (`completed | failed | cancelled`).
   - `corpus://status` → 30s polling against `GET /health/status`; emits only when the polled payload changed.
   - `corpus://folders` → watcher-driven; new server endpoint or in-process subscription hook on `FolderManager.{add,remove}_folder()` and the `FileWatcherService` change pipeline so the MCP server learns about folder mutations without a 30s poll.
5. Disconnect cleanup: when an MCP session closes (stdio EOF, HTTP transport disconnect), every polling task owned by that session is cancelled and the subscription registry entry is removed. Verified by SDK e2e test that asserts no orphan tasks.
6. Payload conforms to the **2025-03-26 MCP spec** for `ResourceUpdatedNotificationParams` — at minimum `{uri: AnyUrl}`; the spec's optional `revision` / `_meta` fields are filled by the server when known (e.g., job state hash, folder list hash).

Phase 52 stops at the MCP wire boundary. Phase 53 (Streamable HTTP transport) and Phase 54 (`wait_for_job` progress notifications, which reuses the same notification plumbing) are downstream consumers.

</domain>

<decisions>
## Implementation Decisions

### A. Subscription ownership model — per-session, not per-URI
- **Decision:** Subscriptions are keyed by `(session_id, uri)` — multiple MCP clients can subscribe to the same `corpus://status` independently and each gets their own polling task. Disconnect of session A does not affect session B's subscriptions to the same URI.
- **Rationale:** Matches MCP spec semantics (subscriptions are session-scoped). Avoids the harder shared-poller refcount design until v3 when CLI-via-MCP could fan out. Simpler eviction logic.
- **`session_id` source:** From `server.request_context.session` (per `mcp/server/lowlevel/server.py:240`). The SDK exposes one `ServerSession` per stdio process; for Phase 53's Streamable HTTP transport, each HTTP session is a distinct `ServerSession` and the same identity scheme applies.
- **Storage:** `SubscriptionManager` lives in `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` (new module). Holds `dict[tuple[int, str], asyncio.Task]` keyed by `(id(session), uri)`.

### B. Polling vs change-stream per URI
- **Decision:** **Hybrid.** Polling for resources that already have a polled REST representation; change-stream for resources where polling is wasteful.
  - `job://<id>` → **1s poll** of `GET /index/jobs/{id}` (only emit on payload diff via SHA-256 of normalized JSON; suppress trivial timestamp-only churn by hashing the payload **without** any `timestamp` / `updated_at` field).
  - `corpus://status` → **30s poll** of `GET /health/status` (only emit on diff).
  - `corpus://folders` → **change-stream.** New in-process pub-sub hook fires on `FolderManager` mutations + on `FileWatcherService` job-completion events (when a watcher-triggered index job finishes, folder state may have new `chunk_count` / `last_indexed`). Falls back to a 60s safety poll so a missed signal can't strand a subscriber.
- **Rationale:** Folders mutate on operator action — a 30s poll wastes RTT and adds visible lag. Jobs mutate continuously while running, polling is fine. Status mutates rarely, 30s is appropriate.
- **Diff suppression:** Always hash the *normalized* payload (sorted keys, drop volatile fields like `timestamp`, `elapsed_ms`). Don't send `notifications/resources/updated` if the hash matches the last sent value for that `(session_id, uri)`.

### C. Notification payload shape
- **Decision:** Minimal MCP-spec-compliant payload: `{"uri": "<resource_uri>"}`. Add `_meta.revision` = SHA-256(canonical payload) so clients can short-circuit `resources/read` when the revision they already cached matches.
- **No payload-in-notification:** v2 follows MCP spec — the notification is a *poke*, clients re-read via `resources/read`. Bundling payload would couple subscription wire format to resource schema and bloat notifications.
- **Spec target:** 2025-03-26 MCP spec revision (matches Phase 50 design doc's spec citation). `ResourceUpdatedNotificationParams` per `mcp/types.py` already supports the optional `_meta` field.

### D. Disconnect detection & cleanup
- **Decision:** Cleanup hooks at two layers:
  1. **MCP SDK layer:** wrap the SDK's `Server.run(...)` invocation so its exit (stdio EOF, HTTP disconnect) triggers `SubscriptionManager.cleanup_session(session_id)`. Use `try / finally` in `run_stdio()` (`server.py:248-270`) and an analog for the HTTP variant in Phase 53.
  2. **Per-task guard:** every polling task is wrapped in `try/except CancelledError` — when the manager cancels it, the task swallows the error cleanly and removes its registry entry. Belt-and-suspenders against partial cleanup.
- **Test gate:** SDK e2e test spawns the MCP server as a subprocess, subscribes to `job://<live-job>`, terminates the client, then asserts via subprocess introspection (`/proc/<pid>/task/` on Linux, `psutil.Process.threads()` cross-platform) that the polling tasks have exited within 2s.
- **No global timeout fallback.** If cleanup hooks fail, the test catches it — we don't ship a "kill after 5 minutes idle" sweep, which would mask real bugs.

### E. New server-side endpoint for folder change events?
- **Decision:** **No new HTTP endpoint.** The MCP server already runs in-process polling for `corpus://folders` (current v1 uses `GET /index/folders/`). Phase 52's `corpus://folders` change-stream is implemented entirely **client-side in the MCP server process** — it just polls more aggressively (5s) when there's an active subscriber, and otherwise the 60s safety poll. This keeps `agent-brain-server` unchanged and avoids inventing a long-polling HTTP API mid-milestone.
- **Rationale:** Adding a server-side change-event endpoint expands scope to FastAPI streaming (SSE/WebSocket), which has zero existing precedent in `agent-brain-server/agent_brain_server/api/` (verified — no `StreamingResponse` usage). That belongs in a future milestone if Phase 52's polling cadence proves insufficient. For v2 we deliver subscription semantics; the underlying delivery is opaque to MCP clients.
- **Trade-off acknowledged:** Lag between folder mutation and `notifications/resources/updated` is bounded at 5s (active subscriber) or 60s (safety poll), not "instant." The v2 design doc must document this explicitly so reviewers don't expect <1s latency.

### F. Concurrency & event-loop hygiene
- **Decision:** Polling tasks run on the **same asyncio loop** as the MCP server, started via `asyncio.create_task(...)` from the `@server.subscribe_resource()` handler. Sync HTTP calls inside the polling loop are wrapped in `asyncio.to_thread(...)` — same pattern as `server.py:130, 158` for tool/resource handlers.
- **Rationale:** Matches v1 hygiene precedent (plan §6.4 / §12.3 #12). A blocking httpx call in `async def` would freeze stdio and break MCP `notifications/cancelled`.
- **No new thread pool.** Default `asyncio` to-thread pool (default size = `min(32, os.cpu_count() + 4)`) is more than enough for the worst case of ~16 concurrent subscriptions per session.

### G. Carry-forward from Phase 50
- **No-auth stance carries forward.** v2 MCP server stays loopback-only; subscriptions inherit that — no per-subscription auth check (auth is v4).
- **GraphRAG-503 handling carries forward.** If a `chunk://` or `graph-entity://` subscription request lands here (it shouldn't — Phase 50's decision was that only `job://`, `corpus://status`, `corpus://folders` are subscribable), the manager rejects with MCP error `-32602 InvalidParams` and `data.reason: "not_subscribable"`. Document the subscribable-URI allowlist in the v2 design doc.
- **Spec version pin.** Phase 50 cited MCP spec 2025-03-26; Phase 52 uses the same revision for `ResourceUpdatedNotificationParams` shape — keep the v2 design doc's spec target consistent.

### Claude's Discretion
- Exact name of the new module (`subscriptions/manager.py` vs `subscriptions.py` — recommend the subpackage for room to grow with `policies.py`, `payloads.py`).
- Whether to expose subscription metrics via a new `corpus://subscriptions` resource for debugging (recommend: no, keep surface tight in v2).
- Logging level for subscribe/unsubscribe/disconnect events (recommend INFO with `session_id` truncated to 8 chars).
- Whether the safety-poll cadence for `corpus://folders` is 30s or 60s — recommend 60s since the 5s "active" cadence handles the responsive case.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope contracts
- `.planning/REQUIREMENTS.md` — SUB-01 through SUB-05; this phase's full requirement scope
- `.planning/ROADMAP.md` — Phase 52 block (success criteria, dependency on Phase 51 for `job://` URI)
- `docs/roadmaps/mcp/v2-subscriptions-and-resources.md` — v2 scope contract; "Resource subscriptions" section defines DoD per-URI cadences
- `.planning/phases/50-server-endpoint-prep-v2-design-doc/50-CONTEXT.md` — carries: no-auth stance, GraphRAG-503 handling, spec version pin (2025-03-26)

### Prior MCP design
- `docs/plans/2026-05-28-mcp-uds-transport-design.md` — v1 master design; §6.1 declares the `resources.subscribe: false` capability that Phase 52 flips, §6.4 establishes the async/to_thread pattern Phase 52's polling tasks follow, §11 (v2 row) sketches subscription scope

### v1 MCP server code (modify in-place)
- `agent-brain-mcp/agent_brain_mcp/server.py` — `build_server()` is where new `@server.subscribe_resource()` / `@server.unsubscribe_resource()` handlers register; `run_stdio()` (line 248) is where the `try/finally` for session disconnect cleanup goes; `NotificationOptions` (line 258) gains `resources_changed=True` semantic equivalence
- `agent-brain-mcp/agent_brain_mcp/resources/corpus.py` — `RESOURCE_REGISTRY` is consulted by the subscribe handler to validate the URI is known; Phase 51 will add `job://`, so this registry grows
- `agent-brain-mcp/agent_brain_mcp/client.py` — `ApiClient` is the polling client; new `get_job(job_id)` method already exists, `server_status()` already exists, `list_folders()` already exists

### MCP SDK references (read these before writing handlers)
- `agent-brain-mcp/.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py:408-432` — `subscribe_resource()` and `unsubscribe_resource()` decorators (handler signature: `async def(uri: AnyUrl) -> None`)
- `agent-brain-mcp/.venv/lib/python3.12/site-packages/mcp/server/session.py:226` — `ServerSession.send_resource_updated(uri)` — the helper that emits `notifications/resources/updated`
- `agent-brain-mcp/.venv/lib/python3.12/site-packages/mcp/server/lowlevel/server.py:240` — `request_context` accessor — gives polling tasks access to the owning `ServerSession`

### Server-side data sources (do NOT modify in this phase)
- `agent-brain-server/agent_brain_server/api/routers/jobs.py` — `GET /index/jobs/{id}` is what `job://` subscriptions poll
- `agent-brain-server/agent_brain_server/api/routers/health.py` — `GET /health/status` is what `corpus://status` subscriptions poll
- `agent-brain-server/agent_brain_server/api/routers/folders.py` — `GET /index/folders/` is what `corpus://folders` polls; folder mutation hooks live in `FolderManager.{add,remove}_folder()`
- `agent-brain-server/agent_brain_server/services/file_watcher_service.py` — watcher pipeline; relevant only because Phase 52 documents that watcher-triggered job completions are the "interesting" `corpus://folders` change events

### v1 e2e test precedent
- `agent-brain-mcp/tests/e2e/test_e2e_resources.py:40` — `test_resources_subscribe_returns_method_not_found` is the v1 test asserting subscribe is rejected; Phase 52 deletes this and replaces it with positive subscription e2e tests
- `agent-brain-mcp/tests/test_initialize.py:32` — `test_capabilities_have_no_subscriptions` will need an inversion in Phase 52

### MCP spec (external)
- MCP spec 2025-03-26 — sections: "Resource subscriptions", "ResourceUpdatedNotification". Phase 52's design doc subsection must cite the spec section by name; the optional `_meta.revision` field comes from this spec.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`agent_brain_mcp/server.py:82-210` (`build_server()`)** — single-function server builder where every MCP capability is registered. Phase 52 adds two new decorator-registered handlers here and flips the `NotificationOptions` defaults at lines 258-262.
- **`agent_brain_mcp/client.py` `ApiClient`** — already wraps `httpx.Client` for the three URI types Phase 52 polls (`get_job`, `server_status`, `list_folders`). No new HTTP wrapping needed — polling tasks reuse this client.
- **`agent_brain_mcp/resources/corpus.py` `RESOURCE_REGISTRY`** — central URI → handler dispatch table. Phase 52 adds a parallel `SUBSCRIBABLE_URIS` set (or a `subscribable: bool` field on `ResourceSpec`) to gate which URIs subscribe handlers accept.
- **`run_stdio()` at `server.py:248`** — the natural place to add a `try / finally` that calls `SubscriptionManager.cleanup_all()` on disconnect.

### Established Patterns
- **`asyncio.to_thread(handler, ...)` for sync httpx calls** (`server.py:130, 158`). New polling tasks MUST follow this pattern — direct httpx inside `async def` would freeze stdio.
- **`McpError(ErrorData(...))` for protocol-level errors** (`server.py:111, 117, 152, 191`). Subscription rejection (unknown URI, not-subscribable URI) uses the same machinery — `INVALID_PARAMS` code from `errors.py`.
- **`AnyUrl` normalization with trailing-slash stripping** (`server.py:149`). Subscribe handler must apply the same normalization to match the registry.
- **v1 capability test pattern at `test_initialize.py:32`** — Phase 52's new capability test inverts this; reuses the same fixture machinery.

### Integration Points
- **MCP SDK `Server.subscribe_resource()` decorator** — gives Phase 52 a one-line registration point. Handler signature is `async def(uri: AnyUrl) -> None`; the SDK auto-wraps it into `SubscribeRequest` / `EmptyResult`.
- **`ServerSession.send_resource_updated(uri)`** — single async call to emit `notifications/resources/updated`. Phase 52's polling tasks call this on the session captured from `request_context` at subscribe time.
- **`NotificationOptions(resources_changed=...)` at `server.py:258`** — currently `False`. The MCP SDK uses this to decide whether to advertise the capability. Phase 52 flips it (this is what makes `initialize` advertise `resources.subscribe: true`).

### Greenfield (no existing pattern)
- **No `SubscriptionManager` anywhere.** Phase 52 creates the first subscription bookkeeping in the entire repo. Recommend `agent-brain-mcp/agent_brain_mcp/subscriptions/__init__.py` + `manager.py` + `policies.py` (per-URI cadence + diff hashing). ~250 LOC, all in the MCP package — `agent-brain-server` stays untouched.
- **No notification-payload hashing helper.** New module `subscriptions/payloads.py` adds `canonical_hash(payload: dict, drop: set[str]) -> str` that normalizes JSON (sorted keys, drop volatile fields) and SHA-256 hashes for the `_meta.revision` field and diff-suppression.
- **No disconnect cleanup hook in `run_stdio()`.** Today the `async with mcp.server.stdio.stdio_server() as ...` block exits silently on EOF. Phase 52 wraps the inner `await server.run(...)` in `try / finally` so `SubscriptionManager.cleanup_session(...)` fires.
- **No e2e test pattern that asserts background task lifecycle.** `tests/e2e/test_e2e_resources.py` only tests synchronous `resources/list` / `resources/read`. Phase 52 introduces the first "spawn → subscribe → disconnect → assert task gone" test.

</code_context>

<specifics>
## Specific Ideas

- The v2 design doc subsection for Phase 52 must explicitly enumerate the **subscribable URI allowlist**: `job://<id>`, `corpus://status`, `corpus://folders`. Reviewers will ask why `chunk://` and `graph-entity://` aren't subscribable — answer: their data is content-addressed (hash of payload doesn't change unless the chunk/entity is reindexed, and reindex already mutates `job://`). Document this so it's a deliberate decision, not an omission.
- The `corpus://folders` polling cadence (5s active / 60s safety) must be **configurable via server settings** (read at MCP server startup, no hot-reload in v2). Recommend `mcp.subscription.folders_active_interval_s` and `mcp.subscription.folders_safety_interval_s` — file in `agent-brain-mcp/agent_brain_mcp/config.py`.
- The diff-suppression hash MUST strip `timestamp`, `updated_at`, `elapsed_ms`, `polled_at` keys at every depth. Otherwise `corpus://status` will emit every 30s regardless of actual change because uvicorn's `/health/status` includes a request timestamp. The v2 design doc should call out the exact key allowlist.
- The disconnect-cleanup test (success criterion #5) needs a **deterministic disconnect** trigger — recommend SIGTERM on the spawned MCP subprocess + 1s wait, then `psutil.Process.is_running()` is False AND `psutil.Process.threads()` from the parent shows the asyncio thread terminated cleanly. The "no leaked polling tasks" assertion is the hardest part of Phase 52's test surface.
- TOOL-04 (`wait_for_job` with progress notifications, Phase 54) will reuse Phase 52's polling-task infrastructure. Phase 52's `SubscriptionManager` should expose its polling primitive as a **public method** (`start_polling(session, uri, interval_s, fetcher, on_change)`) so Phase 54 can call it for progress notifications without duplicating the loop. Document this contract in the design doc.
- The v2 design doc risk register must call out **subscription leak in HTTP transport (Phase 53)**: if Streamable HTTP loses its connection without graceful close, the SDK's session cleanup may not fire. Phase 52's manager should additionally listen for `asyncio.CancelledError` in the polling loop and self-remove from the registry as a defense-in-depth. The Phase 53 plan inherits this concern.

</specifics>

<deferred>
## Deferred Ideas

- **Subscribable `chunk://` and `graph-entity://`** — content-addressed resources whose payload changes only on reindex. v2 sticks to time-varying resources; revisit if framework adapters in v3 demand it.
- **Server-side SSE/long-polling endpoint for folder change events** — would replace Phase 52's 5s active poll with a push channel. Deferred to v10.3+ if subscriber-side polling proves a bottleneck.
- **`corpus://jobs` subscription** (collection-level, all-jobs aggregate) — useful for IDE "show all running jobs" panels. Out of scope for v2; v2 only subscribes to a specific `job://<id>`.
- **Subscription persistence across MCP server restarts** — v2 treats subscriptions as ephemeral per-session. Persistence (e.g., write subscription set to `<state_dir>/mcp/subscriptions.jsonl`) is a separate UX concern.
- **Backpressure / rate-limit on `notifications/resources/updated`** — v2 caps via the polling cadence itself. If clients can't keep up, the MCP SDK's send-queue will block — accept that for v2; revisit if real users complain.
- **`resources/listChanged` notification** when the MCP server's static resource set changes — adjacent to subscriptions but distinct; v2 capability stays `listChanged: false`. Could land in v3 if dynamic resource discovery becomes a real need.
- **OpenTelemetry traces for subscription lifecycle** — observability nice-to-have, not in v2 scope. Add when MCP traffic volume justifies it.
- **`notifications/resources/updated` payload inlining** — sending changed payload in the notification (vs MCP's poke-and-reread model). Out of scope; would be a non-standard MCP extension and not portable across clients.

</deferred>

---

*Phase: 52-resource-subscriptions*
*Context gathered: 2026-06-02*
