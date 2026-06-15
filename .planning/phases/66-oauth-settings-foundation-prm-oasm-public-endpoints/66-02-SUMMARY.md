---
phase: 66
plan: "02"
subsystem: agent-brain-mcp
tags: [oauth, prm, oasm, well-known, discovery, mount-order, OAUTH-02, OAUTH-03]
dependency_graph:
  requires:
    - "agent_brain_mcp.config.check_auth_startup_gate() (Phase 66 Plan 01)"
    - "agent_brain_mcp.config.resolve_oauth_settings() (Phase 66 Plan 01)"
  provides:
    - "GET /.well-known/oauth-protected-resource → RFC 9728 PRM document (OAUTH-02)"
    - "GET /.well-known/oauth-protected-resource/mcp → same PRM document (RFC 9728 path-insertion)"
    - "GET /.well-known/oauth-authorization-server → RFC 8414 OASM document (OAUTH-03)"
    - "agent_brain_mcp.oauth_metadata.build_prm_document() — RFC 9728 builder"
    - "agent_brain_mcp.oauth_metadata.build_oasm_document() — RFC 8414 builder"
    - "http.py PRM_PATH / PRM_PATH_SUFFIXED / OASM_PATH constants (exported in __all__)"
  affects:
    - "Phase 67 (RequireAuthMiddleware wraps /mcp Mount; well-known routes already mounted above)"
    - "Phase 67 (adds /authorize /token /register /.well-known/jwks.json forward-refs)"
    - "Phase 64 HOUSE-01 (carries /mcp/subscriptions audit forward)"
tech_stack:
  added:
    - "starlette.testclient.TestClient — used for well-known route acceptance tests"
  patterns:
    - "Config-derived discovery documents: all field values read from env vars at request time"
    - "Base-URL fallback: resource/issuer fall back to request.base_url when env vars unset"
    - "Mount-order contract: well-known Routes at lower index than /mcp Mount in .routes list"
    - "Forward-reference OASM: advertises Phase-67 endpoint URIs before those routes exist"
key_files:
  created:
    - "agent-brain-mcp/agent_brain_mcp/oauth_metadata.py (build_prm_document + build_oasm_document)"
    - "agent-brain-mcp/tests/test_oauth_metadata_documents.py (25 tests)"
    - "agent-brain-mcp/tests/test_well_known_routes.py (33 tests)"
  modified:
    - "agent-brain-mcp/agent_brain_mcp/http.py (3 path constants + 3 Route handlers + startup gate + mount-order comment)"
decisions:
  - "oauth_metadata.py uses plain dicts (not Pydantic models) for RFC JSON — simpler, same JSONResponse outcome"
  - "code_challenge_methods_supported hardcoded to ['S256'] — spec-mandated, never configurable"
  - "Four scopes locked verbatim: agent-brain:read/index/admin/subscribe (design doc Scope-to-Tool Mapping)"
  - "base_url fallback in build_oasm_document() parameter unused in co-located shape; reserved for split-AS future"
  - "Autouse fixture in test_well_known_routes.py clears env vars to prevent dev-shell leakage"
  - "/mcp/subscriptions audit: NOT present in http.py — audit item is MOOT for Phase 66 (carry to Phase 64 HOUSE-01)"
metrics:
  duration_seconds: 924
  completed_date: "2026-06-14"
  tasks_completed: 3
  files_created: 3
  files_modified: 1
  tests_added: 58
---

# Phase 66 Plan 02: PRM/OASM Public Discovery Routes (OAUTH-02 / OAUTH-03) Summary

**One-liner:** RFC 9728 PRM + RFC 8414 OASM config-derived discovery documents wired as auth-exempt Routes above the /mcp Mount (mount-order contract), with S256-only PKCE and 4 locked agent-brain:* scopes, proven by 58 tests.

## What Was Built

### 1. `agent_brain_mcp/oauth_metadata.py` — Document Builders

Two pure functions that build RFC-valid JSON-serializable dicts from caller-provided config values (no env-var side effects in the builders themselves — callers read the env, builders are testable in isolation):

#### `build_prm_document(*, resource: str, authorization_servers: list[str]) -> dict`

RFC 9728 Protected Resource Metadata. Fields:
- `resource`: the canonical resource URI (from `AGENT_BRAIN_OAUTH_RESOURCE`)
- `authorization_servers`: list of AS issuer URIs (from `AGENT_BRAIN_OAUTH_ISSUER` or request base URL fallback)
- `scopes_supported`: LOCKED to `["agent-brain:read", "agent-brain:index", "agent-brain:admin", "agent-brain:subscribe"]` — design doc §"Scope-to-Tool Mapping", do NOT change without schema migration

#### `build_oasm_document(*, issuer: str, base_url: str) -> dict`

RFC 8414 Authorization Server Metadata. Fields:
- `issuer`: AS issuer URI
- `authorization_endpoint`, `token_endpoint`, `registration_endpoint`, `jwks_uri`: FORWARD-REFERENCES to Phase 67 routes — spec-valid now per RFC 8414 §2 (server MAY advertise before endpoints resolve)
- `code_challenge_methods_supported`: EXACTLY `["S256"]` — hardcoded-from-spec, non-negotiable. Absence or wrong value causes compliant MCP SDK clients to abort the OAuth dance silently.
- `grant_types_supported`: `["authorization_code", "refresh_token"]`
- `response_types_supported`: `["code"]`

### 2. `agent_brain_mcp/http.py` — Route Wiring

**Three new path constants** (all exported in `__all__`):
```python
PRM_PATH = "/.well-known/oauth-protected-resource"
PRM_PATH_SUFFIXED = "/.well-known/oauth-protected-resource/mcp"
OASM_PATH = "/.well-known/oauth-authorization-server"
```

**Startup gate wired at top of `build_asgi_app()`:**
```python
_config.check_auth_startup_gate()
```
Exits code 2 on invalid `AGENT_BRAIN_AUTH` or oauth-mode with missing/invalid `AGENT_BRAIN_OAUTH_RESOURCE`.

**Route handlers:** `oauth_protected_resource(request)` and `oauth_authorization_server(request)` — both call `resolve_oauth_settings()` and fall back to `str(request.base_url).rstrip("/")` when env vars are unset (discovery-first contract: the document is live in ALL modes).

**Mount-order contract (design doc Risk 3):**
```python
routes=[
    Route(HEALTHZ_PATH, healthz, methods=["GET"]),
    Route(PRM_PATH, oauth_protected_resource, methods=["GET"]),          # ABOVE /mcp
    Route(PRM_PATH_SUFFIXED, oauth_protected_resource, methods=["GET"]), # ABOVE /mcp
    Route(OASM_PATH, oauth_authorization_server, methods=["GET"]),       # ABOVE /mcp
    Mount(MCP_MOUNT_PATH, app=mcp_asgi_app),   # /mcp last
]
```

In-code comment: `"MOUNT-ORDER CONTRACT (design doc Risk 3): well-known + healthz routes are AUTH-EXEMPT and MUST precede any future RequireAuthMiddleware wrap (Phase 67). Reversing this deadlocks the OAuth dance."`

### 3. Test Coverage

- `test_oauth_metadata_documents.py` — 25 tests: PRM shape/fields/scopes, OASM shape/S256/endpoints, JSON-serializable
- `test_well_known_routes.py` — 33 tests:
  - SC#1: PRM base path 200 unauthenticated + all RFC 9728 fields
  - SC#1 variant: path-suffixed returns identical document
  - SC#2: OASM 200 unauthenticated + code_challenge_methods_supported == ["S256"] exact
  - SC#3: Mount-order proof — all 3 well-known indices < /mcp Mount index
  - Startup-gate proof: SystemExit(2) on oauth+no-resource, success on none and valid-oauth
  - Env-var reflection: resource from AGENT_BRAIN_OAUTH_RESOURCE, issuer from AGENT_BRAIN_OAUTH_ISSUER

## RESOLVED: /mcp/subscriptions Audit

**Finding:** The design doc (§"/mcp/subscriptions Auth-Exemption Scope") identified a Phase 66 action: "audit /mcp/subscriptions response contents before finalizing its auth-exempt status."

**Audit result:** `grep -rn "subscriptions" agent-brain-mcp/agent_brain_mcp/http.py` returns ONLY the `from .subscriptions import SubscriptionManager` import — there is NO `/mcp/subscriptions` Route or debug endpoint mounted in `http.py`. The only routes in the Phase-66-pre state are `/healthz` and `/mcp` (Mount).

**Disposition:** The design-doc audit item is **MOOT for Phase 66** — the endpoint does not exist to audit. The item carries forward to **Phase 64 HOUSE-01 / 64-04-PLAN.md**, which is the phase that would ship such a debug endpoint. It is NOT silently dropped — it is recorded here and tracked in the Phase 64 carry-forward backlog.

## Config-Derived Field Sourcing (Phase 67 Reuse Guide)

| Document | Field | Source | Fallback |
|----------|-------|--------|---------|
| PRM | `resource` | `AGENT_BRAIN_OAUTH_RESOURCE` | request base URL |
| PRM | `authorization_servers` | `[AGENT_BRAIN_OAUTH_ISSUER]` | `[request base URL]` |
| PRM | `scopes_supported` | LOCKED constant | N/A |
| OASM | `issuer` | `AGENT_BRAIN_OAUTH_ISSUER` | request base URL |
| OASM | `authorization_endpoint` | `{issuer}/authorize` | (forward-ref, Phase 67) |
| OASM | `token_endpoint` | `{issuer}/token` | (forward-ref, Phase 67) |
| OASM | `registration_endpoint` | `{issuer}/register` | (forward-ref, Phase 67) |
| OASM | `jwks_uri` | `{issuer}/.well-known/jwks.json` | (forward-ref, Phase 67) |
| OASM | `code_challenge_methods_supported` | `["S256"]` HARDCODED | N/A |

## Mount-Order Proof (Survives Phase 67)

The `TestMountOrderContract` class in `test_well_known_routes.py` iterates `build_asgi_app(server).routes`, finds the index of each well-known path and the `/mcp` Mount, and asserts `well_known_index < mcp_mount_index` for all three. This test MUST still pass after Phase 67 adds `RequireAuthMiddleware` wrapping the `/mcp` Mount — the well-known routes are already mounted at lower indices and are unaffected by any middleware scope around that Mount.

## Deviations from Plan

None — plan executed exactly as written.

One auto-fix applied (deviation Rule 1):
- Ruff reported unused `type: ignore` comments after mypy strict resolved the types correctly without suppression — removed 5 comments from `test_well_known_routes.py`.
- Ruff reported unused `import os` — removed.
- Black formatting: test file needed one line reformatted (trailing newlines) — fixed.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `agent-brain-mcp/agent_brain_mcp/oauth_metadata.py` | FOUND |
| `agent-brain-mcp/tests/test_oauth_metadata_documents.py` | FOUND |
| `agent-brain-mcp/tests/test_well_known_routes.py` | FOUND |
| Commit `1b7686f` (Task 1 — builders + tests) | FOUND |
| Commit `1a5e1d6` (Task 2 — http.py wiring) | FOUND |
| Commit `ef97ab9` (Task 3 — acceptance tests) | FOUND |
| Commit `2dd408d` (style — Black format fix) | FOUND |
| `task before-push` exits 0 (653 passed) | PASSED |
