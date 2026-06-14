# Phase 64: GraphRAG Stability + Subscriptions Debug Endpoint - Context

**Gathered:** 2026-06-14
**Status:** Ready for planning

> Decisions captured autonomously at the user's direction ("just fix it"). Defaults
> chosen to honor the ROADMAP success criteria and reuse existing #166 prior art.
> Downstream agents may refine HOW within these boundaries.

<domain>
## Phase Boundary

Make the kuzu/GraphRAG path never hard-crash the server or silently under-report,
give operators tools to diagnose and restore a stale graph, and ship the deferred
`/mcp/subscriptions` debug endpoint. Scope is the four mapped requirements only:
GSTAB-01 (#178 SIGSEGV), GSTAB-02 (#184 bug 1 stale-graph restore), GSTAB-03
(#184 bug 2 health-count accuracy), HOUSE-01 (#194 subscriptions debug endpoint).

OAuth 2.1 and any larger graph rework belong to Phases 65-70 and the enterprise
backlog — out of scope here.

</domain>

<decisions>
## Implementation Decisions

### GSTAB-01 — SIGSEGV degradation behavior (#178)
- **Guarantee:** A kuzu-native failure (SIGSEGV / catalog corruption) MUST NOT kill
  the server process. The success criterion is "no SIGSEGV process death," so the
  kuzu write/commit path is **isolated out-of-process** — a native crash becomes a
  catchable non-zero child exit, not a parent death. (In-process `try/except` cannot
  catch a SIGSEGV; the existing `IndexError`/`RuntimeError` recovery in `graph_store`
  stays as the second line of defense for non-fatal pybind11 errors.)
- **Work preservation:** Reuse the existing #166 snapshot/batch-commit machinery
  (`graph_snapshot.py`, hybrid cadence) so a crash loses ~one batch, not everything.
- **Operator experience on failure:** The indexing job surfaces a **clear, structured
  error message** (names the failure, points at the `simple` fallback). The server
  keeps running. Vector + BM25 indexing for the same job still commit — graph failure
  degrades that job to "no graph this run," it does not abort the whole index.
- **No silent config rewrite:** On repeated kuzu failure, do NOT auto-switch the
  configured `graphrag.store_type`. The `simple` store remains the **documented
  manual fallback** the operator opts into — degradation is per-job, config is theirs.

### GSTAB-02 — Restore command & doctor UX (#184 bug 1)
- **Command:** `agent-brain graph restore-from-snapshot [--snapshot PATH] [--dry-run] [--yes]`
  - `--snapshot` optional → defaults to the latest valid snapshot on disk.
  - Default (no flags): print a summary of what WILL be restored, then require
    confirmation; `--yes` skips the prompt for non-interactive/CI use.
  - `--dry-run` reports the plan and exits without mutating kuzu.
- **doctor:** plain `agent-brain doctor` **WARNs** on the stale-graph condition
  (snapshot newer / larger than live kuzu contents) instead of reporting `OK`.
  `agent-brain doctor --fix` offers the restore — consistent with the existing
  v10.0.5 safe-idempotent `--fix` framework and the #166 graph self-heal pattern.

### GSTAB-03 — Health count semantics (#184 bug 2)
- `/health/status` graph `entity_count` / `relationship_count` are derived from a
  **live kuzu `COUNT(*)` at query time**, not the in-memory `self._entity_count` /
  `self._relationship_count` bookkeeping that drifts after a rollback.
- **TTL cache:** wrap the live COUNT in a short TTL cache (~5s) so health-poll storms
  don't issue a graph query per request. Only computed when graph is enabled and
  `store_type == kuzu`.
- **kuzu unreachable:** if the live COUNT query itself fails, report **last-known
  counts with a degraded/stale marker** — do NOT report `0`, which would read as
  "empty graph" and hide an outage. The existing non-chroma backend `0/0` override
  in `health.py` stays as-is (that path genuinely has no graph).

### HOUSE-01 — Subscriptions debug endpoint (#194)
- **Route:** `GET /mcp/subscriptions` on the MCP Streamable-HTTP Starlette app,
  mounted alongside `/healthz` in `http.py`. Returns **200 + JSON**, **no token**
  (loopback-only, same trust model as `/healthz` and the existing no-auth banner).
- **Payload (per current SubscriptionManager state):**
  ```json
  {
    "transport": "http",
    "server_uptime_s": 1234.5,
    "active_count": 2,
    "subscriptions": [
      {
        "session_id": "<8-char truncated>",
        "uri": "job://job_abc123",
        "cadence_s": 1.0,
        "started_at": "2026-06-14T10:00:00Z",
        "last_notified_at": "2026-06-14T10:01:23Z"
      }
    ]
  }
  ```
  Session IDs are **truncated** (manager already has `_truncate_session_id`) — never
  expose full session object ids. Add a snapshot/introspection method to
  `SubscriptionManager` rather than reaching into `_tasks` from the route.
- **stdio transport:** stdio has no HTTP listener, so the endpoint **does not exist**
  under stdio mode. This is expected and documented — operators needing the debug
  view run the HTTP transport. No shim, no fake endpoint.

### Claude's Discretion
- Exact out-of-process isolation mechanism for kuzu (subprocess vs. process pool vs.
  forked worker), child-exit signaling, and timeout handling.
- TTL cache implementation details and exact cache window.
- Snapshot selection/validation internals for restore.
- JSON field naming nits and uptime measurement source.
- Test structure (recovery tests, count-accuracy tests, endpoint contract tests).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### GraphRAG stability (GSTAB-01/02/03)
- `docs/plans/issue-166-kuzu-resilience.md` — existing kuzu durability/self-heal +
  snapshot design (snapshot format, hybrid cadence, recovery flow, doctor `--fix`).
  This phase EXTENDS this work; reuse its modules and patterns.
- `docs/plans/2026-05-26-graph-search-restoration.md` — graph search restoration context.
- `agent-brain-server/agent_brain_server/storage/graph_store.py` — `_initialize_kuzu_store`,
  `_open_kuzu_with_recovery`, `_restore_from_snapshot_if_available`, `_update_counts`,
  and the `self._entity_count` / `self._relationship_count` bookkeeping that GSTAB-03 replaces.
- `agent-brain-server/agent_brain_server/storage/graph_snapshot.py` — `SnapshotTriplet`,
  snapshot writer/reader/rotator (work-preservation layer for GSTAB-01).
- `agent-brain-server/agent_brain_server/api/routers/health.py` §174-187 — graph_index
  status assembly + the non-chroma `0/0` override (GSTAB-03 touches this).
- `agent-brain-cli/agent_brain_cli/commands/doctor.py` — `--fix` framework to extend (GSTAB-02).

### Subscriptions debug endpoint (HOUSE-01)
- `docs/plans/2026-06-02-mcp-v2-subscriptions.md` — v2 subscriptions design (the deferred
  VAL-02 item this closes).
- `agent-brain-mcp/agent_brain_mcp/subscriptions/manager.py` — `SubscriptionManager`,
  `_tasks` keyed by `(id(session), uri)`, `_truncate_session_id`, `active_count`.
- `agent-brain-mcp/agent_brain_mcp/http.py` — Starlette app, `/healthz` route, loopback
  enforcement, `build_asgi_app` (where `/mcp/subscriptions` mounts).

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — GSTAB-01, GSTAB-02, GSTAB-03, HOUSE-01 (full text).
- `.planning/ROADMAP.md` — Phase 64 goal + 4 success criteria.
- GitHub issues: `#178` (SIGSEGV), `#184` (stale-graph + count under-report),
  `#194` (subscriptions debug endpoint), `#166` (kuzu durability prior art).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `graph_snapshot.py` snapshot machinery (atomic write, rotation, replay) — the
  GSTAB-01 work-preservation layer already exists; this phase wires isolation + restore CLI around it.
- `graph_store._restore_from_snapshot_if_available` — restore primitive the
  GSTAB-02 CLI command and `doctor --fix` call into.
- `doctor.py` `--fix` framework (safe/idempotent/offline) — GSTAB-02 plugs a new
  stale-graph check + restore action into it.
- `SubscriptionManager` already tracks all needed state and truncates session ids —
  HOUSE-01 just needs a read-only snapshot method + a route.
- `http.py` `/healthz` route + loopback security model — HOUSE-01's `/mcp/subscriptions`
  mirrors it exactly (no-token, loopback).

### Established Patterns
- Self-heal: detect → loud actionable log → rename (never delete) → retry
  (`graph_store.py` recovery path). GSTAB-01/02 follow it.
- Structured user-facing `RuntimeError` naming the path + suggesting the env/fallback.

### Integration Points
- Kuzu write/commit path inside `indexing/graph_index.build_from_documents()` → wrap
  in out-of-process isolation (GSTAB-01).
- `/health/status` graph block in `api/routers/health.py` → swap bookkeeping counters
  for live-COUNT-with-TTL (GSTAB-03).
- MCP HTTP Starlette routes in `http.py` → add `/mcp/subscriptions` (HOUSE-01).
- CLI `graph` command group + `doctor` → add `restore-from-snapshot` and stale check (GSTAB-02).

</code_context>

<specifics>
## Specific Ideas

- "Just fix it." Operator-facing behavior should be boringly safe: server never dies,
  errors are legible, restore is explicit (confirm or `--yes`), health numbers are
  true, and the debug endpoint is a plain unauthenticated `curl` on loopback.
- The `0 / 100` vs real `5677 / 4366` discrepancy from #184 is the concrete anti-goal
  for GSTAB-03 — counts must match a live `SELECT COUNT(*)`.

</specifics>

<deferred>
## Deferred Ideas

- OAuth 2.1 on the HTTP transport (auth on `/mcp/subscriptions` and friends) — Phases 65-70.
- Auto-switching `store_type` to `simple` on persistent kuzu failure — intentionally
  NOT done; config stays operator-owned. Revisit only if operators ask.
- Job resume/checkpoint across pipeline phases — out of scope per #166 follow-ups.

</deferred>

---

*Phase: 64-graphrag-stability-subscriptions-debug-endpoint*
*Context gathered: 2026-06-14*
