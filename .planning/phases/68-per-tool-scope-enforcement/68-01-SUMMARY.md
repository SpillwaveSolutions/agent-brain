---
phase: 68-per-tool-scope-enforcement
plan: "01"
subsystem: auth
tags: [oauth, scopes, mcp, tool-registry, drift-guard, jwt]

requires:
  - phase: 67-co-located-as-rs-middleware
    provides: "LocalRs256Verifier returning AccessToken.scopes; BearerAuthBackend populating request.state.auth; RequireAuthMiddleware(required_scopes=[]) placeholder"
  - phase: 66-oauth-design
    provides: "4 locked scopes (read/index/admin/subscribe) advertised in PRM/OASM; _OAUTH_SCOPES in http.py"

provides:
  - "oauth/scopes.py: VALID_SCOPES frozenset, InsufficientScopeError with .required, require_scope() pure helper"
  - "tools/__init__.py: TOOL_SCOPE_REQUIREMENTS dict (16 keys) + _scope_drift() + import-time _assert_every_tool_has_scope() RuntimeError guard"
  - "tests/test_tool_scope_sot.py: 31 tests proving completeness, valid values, locked assignment, drift guard raises, require_scope round-trip"

affects:
  - 68-02-dispatch-layer-scope-enforcement
  - phase-70-split-as-rs

tech-stack:
  added: []
  patterns:
    - "Import-time drift guard: _assert_every_tool_has_scope() at module bottom raises RuntimeError naming unassigned tools — same fail-fast philosophy as _assert_matrix_covers_registry() in contract/_tool_matrix.py"
    - "Pure scope helper: require_scope(required, token_scopes) is side-effect-free; holds no request context; trivially testable; verifier-swappable in Phase 70"
    - "Deny-by-default: require_scope with empty token_scopes raises — no implicit trust for unscoped tokens"

key-files:
  created:
    - agent-brain-mcp/agent_brain_mcp/oauth/scopes.py
    - agent-brain-mcp/tests/test_tool_scope_sot.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/tools/__init__.py

key-decisions:
  - "TOOL_SCOPE_REQUIREMENTS as separate dict (not ToolSpec slot) keeps drift guard a pure dict-vs-dict comparison without editing all 16 ToolSpec constructors"
  - "server_health -> agent-brain:read (registry key wins over design table's get_corpus_status label)"
  - "query_count -> agent-brain:read (not named in design Scope Table; read-only document count)"
  - "_scope_drift() extracted as pure helper callable by tests without module-level monkeypatching"
  - "_VALID_SCOPES_LOCAL inline frozenset in tools/__init__.py avoids circular import; test asserts it matches VALID_SCOPES"
  - "wait_for_job -> agent-brain:index (even though readOnlyHint=True in annotations; it spawns job waits and is a mutation-gating operation)"

patterns-established:
  - "Fail-loud at startup: import-time RuntimeError prevents server starting with unscoped tools"
  - "SOT tests pin locked assignment parametrically — 16 tool/scope pairs fail explicitly on re-scope"

requirements-completed: [OAUTH-06]

duration: 20min
completed: 2026-06-16
---

# Phase 68 Plan 01: Scope SOT + Import-Time Drift Guard Summary

**Per-tool OAuth scope single source of truth (TOOL_SCOPE_REQUIREMENTS, 16 keys) with import-time RuntimeError drift guard and require_scope() + InsufficientScopeError helper for Plan 02's dispatch-layer enforcement**

## Performance

- **Duration:** 20 min
- **Started:** 2026-06-16T19:23:07Z
- **Completed:** 2026-06-16T19:43:07Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `oauth/scopes.py` with `VALID_SCOPES` frozenset, `InsufficientScopeError` (`.required` attribute carries the REQUIRED scope for WWW-Authenticate), and `require_scope()` pure deny-by-default helper
- Added `TOOL_SCOPE_REQUIREMENTS` (16 entries, all 3 scope tiers) + `_scope_drift()` helper + `_assert_every_tool_has_scope()` import-time guard to `tools/__init__.py` — server refuses to start if any tool lacks a scope
- Shipped 31 SOT tests: completeness (set equality), valid-scope values, 16-pair locked assignment (parametrized), RuntimeError drift guard proves naming of removed tool, require_scope round-trip including empty-granted-scopes deny-by-default
- `task before-push` exits 0: 855 passed, 0 regressions, Black/Ruff/mypy strict all clean

## Task Commits

1. **Task 1: Create oauth/scopes.py** - `37e60ec` (feat)
2. **Task 2: TOOL_SCOPE_REQUIREMENTS + drift guard + SOT tests** - `dbc5fc5` (feat)

## Files Created/Modified

- `agent-brain-mcp/agent_brain_mcp/oauth/scopes.py` — VALID_SCOPES, InsufficientScopeError, require_scope() (new)
- `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` — TOOL_SCOPE_REQUIREMENTS + _scope_drift() + _assert_every_tool_has_scope() + updated __all__ (modified)
- `agent-brain-mcp/tests/test_tool_scope_sot.py` — 31-test SOT suite (new)

## Decisions Made

- **TOOL_SCOPE_REQUIREMENTS dict (not ToolSpec slot):** Keeps drift guard a clean dict-vs-dict set comparison; avoids editing all 16 ToolSpec constructor calls (ToolSpec uses `__slots__`, a new field would require slots + __init__ changes for every tool entry).
- **server_health and query_count both → agent-brain:read:** Registry keys win over the design table's labeling (`get_corpus_status`). Both are read-only operations on the authed `/mcp` path.
- **_scope_drift() extracted as pure testable helper:** Allows tests to call drift detection logic with doctored inputs without importlib.reload or module-level monkeypatching; production guard calls it at zero-arg module bottom.
- **_VALID_SCOPES_LOCAL inline frozenset in tools/__init__.py:** Avoids potential circular import if oauth.scopes ever gains a transitive dep on tools; test asserts literal equality with VALID_SCOPES.

## Deviations from Plan

None — plan executed exactly as written. The only iteration was applying Black formatting + Ruff lint fixes (import sort + 3 E501 lines) before the final before-push run — normal code-style cleanup, not a behavioral deviation.

## Issues Encountered

- Black reformatted both files after initial write; Ruff found 3 remaining E501 lines (long f-strings in test assertion messages) and 2 import-sort issues that `--fix` auto-resolved. Corrected before commit.

## User Setup Required

None — no external service configuration required. This plan adds data structures and a pure helper only; no dispatch wiring yet (Plan 02).

## Next Phase Readiness

- `require_scope()` + `InsufficientScopeError` ready for Plan 02's pre-dispatch ASGI guard in `server.py::call_tool`
- `TOOL_SCOPE_REQUIREMENTS[tool_name]` gives the required scope string at dispatch time
- Phase 67's `request.state.auth` (AccessToken.scopes) provides the granted scopes for the require_scope() call
- No changes to `none`/`basic` mode behavior — scope enforcement engages only when AGENT_BRAIN_AUTH=oauth (Plan 02 adds the mode gate)

---
*Phase: 68-per-tool-scope-enforcement*
*Completed: 2026-06-16*
