---
phase: 66
plan: "01"
subsystem: agent-brain-mcp
tags: [oauth, auth-mode, startup-gate, config, OAUTH-09]
dependency_graph:
  requires: []
  provides:
    - "agent_brain_mcp.config.AuthMode (str, Enum over {none, basic, oauth})"
    - "agent_brain_mcp.config.resolve_auth_mode() → AuthMode | None"
    - "agent_brain_mcp.config.resolve_oauth_settings() → (resource, issuer)"
    - "agent_brain_mcp.config.check_auth_startup_gate() → None | sys.exit(2)"
    - "agent_brain_mcp.config.get_auth_dependency() — single selector seam"
  affects:
    - "Phase 67 (RequireAuthMiddleware wires into get_auth_dependency() seam)"
    - "Phase 66 Plan 02 (public routes / PRM endpoint reads resolve_oauth_settings)"
tech_stack:
  added:
    - "AuthMode(str, Enum) — Python 3.10 compat (not enum.StrEnum which is 3.11+)"
    - "urllib.parse.urlparse — scheme + fragment validation for OAuth resource URI"
  patterns:
    - "Gate-before-accessor split: _raw_auth_mode() for gate, resolve_auth_mode() for app"
    - "Pure-read resolver + single validation gate (mirrors SECURITY-01 server pattern)"
    - "Mutual-exclusion selector via get_auth_dependency() — one value per mode, never two"
key_files:
  created:
    - "agent-brain-mcp/tests/test_auth_mode_config.py (20 tests)"
    - "agent-brain-mcp/tests/test_mcp_startup_gate.py (31 tests)"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/config.py (AuthMode + gate + selector added)"
decisions:
  - "AuthMode uses class AuthMode(str, Enum) not enum.StrEnum — repo targets Python 3.10+"
  - "_raw_auth_mode() / resolve_auth_mode() split: gate reads raw string; app code reads enum AFTER gate passes"
  - "resolve_oauth_settings() is pure-read (no exceptions); gate owns all validation + exit paths"
  - "get_auth_dependency() oauth branch raises NotImplementedError (Phase-67 placeholder); selector seam exists now"
  - "check_auth_startup_gate() rejects fragment URIs per RFC 8707 §2 (MUST NOT contain fragment)"
metrics:
  duration_seconds: 656
  completed_date: "2026-06-14"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  tests_added: 51
---

# Phase 66 Plan 01: AuthMode Settings Foundation (OAUTH-09) Summary

**One-liner:** `AuthMode(str, Enum)` over {none, basic, oauth} with startup gate exiting code 2 on invalid toggle or oauth-mode absent/scheme-less resource URI, plus mutual-exclusion `get_auth_dependency()` selector seam for Phase 67.

## What Was Built

Added the OAUTH-09 auth-mode settings foundation to `agent_brain_mcp/config.py`:

### AuthMode Enum

```python
class AuthMode(str, Enum):
    none = "none"
    basic = "basic"
    oauth = "oauth"
```

Python 3.10 compatible (`str, Enum` subclass rather than `enum.StrEnum` which is 3.11+). Members are both enum values and strings (`isinstance(AuthMode.none, str)` is True).

### Gate-Before-Accessor Design

Two distinct primitives resolve the env var:

- `_raw_auth_mode() -> str | None`: Returns the lowercased `AGENT_BRAIN_AUTH` value or None if unset. Used exclusively by the startup gate to detect invalid values BEFORE constructing an enum member.
- `resolve_auth_mode() -> AuthMode | None`: Returns the validated `AuthMode` member. Returns `None` for invalid values (but normal app code never sees `None` because the gate runs at startup and exits on bad values).

This split keeps the `sys.exit(2)` path in one place (`check_auth_startup_gate`) while letting `resolve_auth_mode()` stay a clean typed accessor for post-gate callers.

### OAuth Settings Resolver

`resolve_oauth_settings() -> tuple[str | None, str | None]` reads `AGENT_BRAIN_OAUTH_RESOURCE` and `AGENT_BRAIN_OAUTH_ISSUER`. Empty strings normalize to `None`. Pure-read — no validation, no exceptions. The startup gate owns all validation.

### Startup Gate

`check_auth_startup_gate()` is the boot-time guard (OAUTH-09, mirrors SECURITY-01 server-side pattern):

1. Unset `AGENT_BRAIN_AUTH` → treat as "none" → return `None` silently.
2. Raw value NOT in `{none, basic, oauth}` → `logger.critical(...)` naming `AGENT_BRAIN_AUTH` + bad value → `sys.exit(2)`.
3. Mode == "oauth": validate `AGENT_BRAIN_OAUTH_RESOURCE`:
   - Absent/empty/whitespace-only → `sys.exit(2)` naming `AGENT_BRAIN_OAUTH_RESOURCE`.
   - No scheme (bare hostname) → `sys.exit(2)`.
   - Contains fragment (`#`) → `sys.exit(2)` (RFC 8707 §2 MUST NOT contain fragment).
   - Valid `https://` or `http://` URI → return `None` silently.
4. `none`/`basic` modes → return `None` silently (resource not required).

### Auth-Dependency Selector

`get_auth_dependency()` is the mutual-exclusion seam for Phase 67:

| Mode | Returns |
|------|---------|
| `none` | `None` (no-op — no auth on request path) |
| `basic` | `"basic-bearer"` (existing SECURITY-01 shared-secret path marker) |
| `oauth` | raises `NotImplementedError` (Phase-67 placeholder) |

In-code comment: "Phase 66 wires the selector + validation; the oauth middleware it selects arrives in Phase 67 (RequireAuthMiddleware)."

## Env Vars Documented

| Env Var | Default | Description |
|---------|---------|-------------|
| `AGENT_BRAIN_AUTH` | (unset → `none`) | Auth mode: `none`, `basic`, or `oauth` |
| `AGENT_BRAIN_OAUTH_RESOURCE` | None | RFC 8707 canonical resource URI (required in oauth mode) |
| `AGENT_BRAIN_OAUTH_ISSUER` | None | Authorization Server issuer URI (optional) |

## Exit-Code-2 Paths

Both paths are guarded by `logger.critical` before `sys.exit(2)`:

1. `AGENT_BRAIN_AUTH` set to an invalid value (not in `{none, basic, oauth}`)
2. `AGENT_BRAIN_AUTH=oauth` with `AGENT_BRAIN_OAUTH_RESOURCE` absent, empty, scheme-less, or containing a fragment

## Test Coverage

- `test_auth_mode_config.py`: 20 tests — enum shape, case-insensitive resolution, pure-read resolver, empty→None normalization
- `test_mcp_startup_gate.py`: 31 tests — all valid modes pass silently, 7 invalid toggle values exit 2, 5 oauth resource failure modes, fragment rejection, none/basic don't require resource, 5 selector mutual-exclusion assertions
- Total: **51 tests green**

## Deviations from Plan

None — plan executed exactly as written.

The implementation wrote both tests and implementation atomically per the TDD flow (RED was confirmed via ImportError before the GREEN implementation was added to config.py; for Task 2 the tests passed immediately against the already-present Task 1 implementation + Task 2 additions made in the same implementation step).

One auto-fix applied per deviation Rule 2:
- Ruff reported `AuthMode` unused import in `test_mcp_startup_gate.py` — removed (it's used in `test_auth_mode_config.py` instead).

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `agent-brain-mcp/tests/test_auth_mode_config.py` | FOUND |
| `agent-brain-mcp/tests/test_mcp_startup_gate.py` | FOUND |
| `.planning/phases/66-.../66-01-SUMMARY.md` | FOUND |
| Commit `0ce436e` (Task 1) | FOUND |
| Commit `44901ce` (Task 2) | FOUND |
