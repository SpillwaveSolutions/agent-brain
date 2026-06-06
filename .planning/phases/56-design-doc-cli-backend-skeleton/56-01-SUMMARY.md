---
phase: 56-design-doc-cli-backend-skeleton
plan: 01
subsystem: design-doc

tags: [mcp, v3, design-doc, backend-client, protocol, runtime-discovery]

# Dependency graph
requires:
  - phase: v10.2 Phases 50-55
    provides: 16-tool MCP surface, Streamable HTTP transport, resource subscriptions, parameterized URI templates, MIN_BACKEND_VERSION=10.2.0
provides:
  - v3 design doc filed at docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md
  - BackendClient Protocol surface locked (12 methods + ctx-mgr dunders + close)
  - cli_backend_transport named as third orthogonal transport axis
  - Backend class location locked (agent_brain_mcp/client.py)
  - Sync-facade-with-async-internals decision locked (Pattern A vs B deferred to plan execution)
  - mcp.runtime.json schema locked for Phase 58 prereq
  - MIN_BACKEND_VERSION stance for v3 documented (10.2.0 skeleton, 10.3.0 at v3 close)
  - Scope-doc backlink from docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md
affects: [Plan 56-02 (BackendClient Protocol), Plan 56-03 (McpStdioBackend + McpHttpBackend skeletons), Phase 57 (CLI transport selector), Phase 58 (runtime discovery + helper commands), Phase 61 (framework matrix scoping doc), v10.4 (#188 OAuth — depends on McpHttpBackend)]

# Tech tracking
tech-stack:
  added: []  # docs-only plan; no code/library additions
  patterns:
    - "Design-first per-milestone gating (v2 Phase 50 precedent reaffirmed)"
    - "Three orthogonal transport axes naming: cli_backend_transport (NEW v3), listen_transport (v2), backend_transport (v1)"
    - "Sync-facade with async-internal MCP SDK wrapping (canonical example: agent-brain-mcp http.run_http)"
    - "@runtime_checkable typing.Protocol over ABC for structural-typing backend conformance"

key-files:
  created:
    - "docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md (323 lines, 7 numbered sections)"
  modified:
    - "docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md (new ## Design doc section inserted between Definition of done and Source design)"

key-decisions:
  - "BackendClient Protocol style: @runtime_checkable typing.Protocol (not ABC); DocServeClient satisfies structurally without inheritance retrofit"
  - "Backend class location: McpStdioBackend + McpHttpBackend in agent-brain-mcp/agent_brain_mcp/client.py alongside ApiClient — keeps MCP SDK dep contained to the mcp package"
  - "Sync facade with async-internal: public methods are sync; internals wrap MCP SDK async calls via asyncio.run (Pattern A) OR persistent _loop attribute (Pattern B); choice deferred to Plan 56-02/56-03 measurement"
  - "MIN_BACKEND_VERSION = '10.2.0' in v3 skeleton; bump to '10.3.0' at v3 milestone close (Phase 63) — preserves the X.Y.Z mcp requires >= X.Y.0 server contract for upgrade ordering"
  - "cli_backend_transport named as the third orthogonal transport axis — explicit so v4 OAuth work cannot conflate it with listen_transport or backend_transport"
  - "No silent fallback (v10.2 HTTP-03 carry-forward): --transport mcp without agent-brain-mcp installed fails loudly; --mcp-transport http without runtime file (and no --mcp-url) fails loudly"
  - "reset() on BackendClient Protocol has no MCP tool equivalent in v2; Plan 56-03 skeleton will raise NotImplementedError; Phase 57+ decides whether to add reset_index tool or hold for v4"
  - "mcp.runtime.json schema locked (host, port, pid, started_at, transport='http' for v3, future-proof) — Phase 58 helper command writes it AFTER psutil socket-bind verification reusing v10.2 HTTP-02 pattern"

patterns-established:
  - "Three-axis transport naming: cli_backend_transport / listen_transport / backend_transport are orthogonal; design doc must name the axis explicitly to prevent future-milestone auth misrouting"
  - "Design-first hard gate per milestone — design doc is Plan 01, NO MCP-layer code lands until the doc is filed (v2 Phase 50 precedent codified for v3)"
  - "Soft CLI dep on agent-brain-mcp: CLI does NOT pin agent-brain-mcp in pyproject; --transport mcp surfaces a clear install hint if the import fails"
  - "Method ↔ MCP tool mapping table maintained in design doc; load-bearing pinning (search_documents tool name, etc.) tested at MCP-package level"

requirements-completed: [DESIGN-V3-01]

# Metrics
duration: ~7 min
completed: 2026-06-06
---

# Phase 56 Plan 01: v3 Design Doc — CLI-via-MCP Surgical Design Summary

**v3 design doc filed (323 lines, 7 sections) locking BackendClient Protocol surface, McpStdioBackend/McpHttpBackend class boundaries, cli_backend_transport as third orthogonal transport axis, sync-facade-with-async-internals decision, and mcp.runtime.json discovery schema — before any MCP-layer code lands in this milestone.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-06-06T21:30:27Z
- **Completed:** 2026-06-06T21:37:11Z
- **Tasks:** 3
- **Files modified:** 2 (1 created, 1 edited)

## Accomplishments

- Filed `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` (323 lines, all 7 numbered sections present) mirroring the v2 design doc structural template.
- Locked the `BackendClient` Protocol surface (`@runtime_checkable`, 12 public methods + 3 context-manager dunders + `close()`), with the method ↔ MCP-tool mapping table that Plans 56-02 / 56-03 build against.
- Named `cli_backend_transport` as the third orthogonal transport axis (distinct from `listen_transport` + `backend_transport`) — explicit to prevent v4 OAuth misrouting between axes.
- Locked `mcp.runtime.json` schema (`host`, `port`, `pid`, `started_at`, `transport`) for the Phase 58 prereq + the psutil-kernel-bind-then-write ordering reused from v10.2 HTTP-02.
- Documented the `MIN_BACKEND_VERSION` stance: hold at `"10.2.0"` in the v3 skeleton, bump to `"10.3.0"` at v3 close — keeps the long-standing upgrade-ordering contract clean.
- Explicit deferrals captured in §6: async-first `AsyncBackendClient` Protocol, v9.6.0 Runtime Parity unpark (routed to Phase 61 discuss-phase), v10.4 OAuth, persistent-`_loop` vs `asyncio.run` perf decision, CLI-via-MCP for `agent-brain-mcp`'s own CLI, framework matrix scoping doc.
- Linked the design doc from the v3 scope source-of-truth at `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` via a new `## Design doc` section inserted between `## Definition of done` and `## Source design`.

## Task Commits

All three tasks committed atomically in a single conventional commit per the plan's spec (Task 3 commits both docs together after `task before-push`):

1. **Task 1: File the v3 design doc** — `50de1a2` (docs)
2. **Task 2: Link the v3 design doc from the v3 scope doc** — `50de1a2` (docs, same commit)
3. **Task 3: Run task before-push and commit Plan 56-01 docs** — `50de1a2` (docs)

`task before-push` exited 0 (468 tests passed, 92% coverage, Black/Ruff/mypy strict all clean). Lock-drift warning on `agent-brain-mcp/poetry.lock` was the known #174 monorepo-bootstrap behavior; the guard auto-reverted, no impact on the commit.

## Files Created/Modified

- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` (created, 323 lines) — v3 surgical design doc covering CLI-via-MCP scope ONLY; 7 numbered sections (Context, Architecture deltas, Python surface decisions, Per-phase decisions, Risk register, Deferred/related work, Canonical references) + YAML frontmatter (`date: 2026-06-05`, `status: Plan for review`).
- `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` (modified) — inserted a new `## Design doc` section (lines 59-64) between `## Definition of done` and `## Source design`, linking the new design doc via relative path `../../plans/2026-06-05-mcp-v3-cli-via-mcp.md`.

## Decisions Made

Locked in §3 of the design doc (each listed in `key-decisions` frontmatter above):

- **`@runtime_checkable typing.Protocol` over ABC** (§3.3) — structural typing keeps `DocServeClient` conformance retrofit-free; tests can assert `isinstance(backend, BackendClient)`; mypy strict verifies the surface. PEP-544 isinstance cost accepted (instantiation is once-per-CLI-invocation).
- **Backend class location: `agent-brain-mcp/agent_brain_mcp/client.py`** (§3.1) — keeps the MCP SDK dep contained to the mcp package; agent-brain-cli takes only a SOFT (optional) dep. Alternative (`agent-brain-cli/client/mcp_backend.py`) rejected because it would bloat CLI install.
- **Sync facade with async-internal** (§3.2) — Pattern A (`asyncio.run` per call) vs Pattern B (persistent `_loop`) decision deferred to Plan 56-02/56-03 measurement. Either pattern satisfies the sync-facade public contract.
- **`MIN_BACKEND_VERSION` for v3** (§3.4) — skeleton holds at `"10.2.0"`; bump to `"10.3.0"` at v3 close (Phase 63) in lockstep with `agent-brain-rag = "^10.3.0"` pyproject pin. Preserves the X.Y.Z mcp requires >= X.Y.0 server upgrade-ordering contract.
- **No silent fallback** (§3.5) — v10.2 HTTP-03 carry-forward; `--transport mcp` without `agent-brain-mcp` installed fails loudly; `--mcp-transport http` without `mcp.runtime.json` (and no `--mcp-url`) fails loudly.

Explicit deferrals (§6):

- Async-first `AsyncBackendClient` Protocol variant — deferred to v10.4+; v3 ships sync-only per CONTEXT.md.
- v9.6.0 Runtime Parity unpark (Phases 47-49) — routed to `/gsd:discuss-phase 61`; NOT pre-decided here.
- OAuth 2.1 — v10.4 (#188); strictly depends on v10.3's `McpHttpBackend`.
- Persistent `_loop` vs `asyncio.run` — performance optimization deferred to Plan 56-03 execution.
- CLI-via-MCP for `agent-brain-mcp`'s own CLI — explicit non-goal in v3 per CONTEXT.md deferred ideas.
- Framework matrix scoping doc — separate lighter scoping doc filed at Phase 61 start.

## Deviations from Plan

None - plan executed exactly as written.

The plan structured the work so that Task 3 commits both docs together after a single `task before-push` pass (rather than committing Task 1 and Task 2 separately). This is the plan's intended atomicity boundary (docs-only plan, two coordinated files, single mandatory pre-push gate). No deviation from the plan's commit grouping.

## Issues Encountered

- **`task before-push` lock-drift warning** (informational, not a failure): the post-run `before_push_lock_guard.sh check` reported `agent-brain-mcp/poetry.lock` drifted during the gate run — this is the known monorepo-bootstrap drift issue (#174). The guard auto-reverted the lock; the docs-only commit was not affected. No action required; gate exited 0.

## User Setup Required

None — no external service configuration required (docs-only plan).

## Next Phase Readiness

- **Plan 56-02 ready to execute:** Design doc is in tree; reviewers can challenge the `BackendClient` Protocol surface and the sync-facade decision. Plan 56-02 lands the actual Protocol file at `agent-brain-cli/agent_brain_cli/client/protocol.py` matching the surface locked in §2.2.
- **Plan 56-03 ready to execute:** Design doc locks backend class location (§3.1), sync-facade pattern (§3.2), method ↔ MCP-tool mapping (§2.3), `MIN_BACKEND_VERSION` stance (§3.4), and the `reset()` `NotImplementedError` decision. Plan 56-03 lands `McpStdioBackend` + `McpHttpBackend` skeletons at `agent-brain-mcp/agent_brain_mcp/client.py`.
- **Phase 58 unblocked:** `mcp.runtime.json` schema is locked in §2.4 — Phase 58 helper command implementation can begin without further design work.
- **Phase 61 holding point:** v9.6.0 Runtime Parity unpark decision deferred here per CONTEXT.md; `/gsd:discuss-phase 61` will own that decision when the framework matrix kicks off.

No blockers.

---
*Phase: 56-design-doc-cli-backend-skeleton*
*Completed: 2026-06-06*

## Self-Check: PASSED

- FOUND: `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` (323 lines, 7 numbered sections)
- FOUND: `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` (`## Design doc` section inserted between `## Definition of done` and `## Source design`)
- FOUND: `.planning/phases/56-design-doc-cli-backend-skeleton/56-01-SUMMARY.md` (this file)
- FOUND: commit `50de1a2` — `docs(56-01): file v3 design doc — CLI-via-MCP scope (DESIGN-V3-01)` (touches both doc files, nothing else)
