---
phase: 66-oauth-settings-foundation-prm-oasm-public-endpoints
verified: 2026-06-14T00:00:00Z
status: passed
score: 4/4 success criteria verified
re_verification: false
---

# Phase 66: OAuth Settings Foundation + PRM/OASM Public Endpoints Verification Report

**Phase Goal:** The OAuth discovery root is live — unauthenticated clients can find the authorization server and learn the PKCE requirement; the `basic` mode is formalized as the LAN bridge; all three auth-mode toggle paths are wired at the settings layer.
**Verified:** 2026-06-14
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC#1 | `GET /.well-known/oauth-protected-resource` returns HTTP 200 with RFC 9728 JSON (resource, authorization_servers, scopes_supported) | VERIFIED | `build_prm_document()` in `oauth_metadata.py` returns dict with exactly those three keys; `TestPrmBasePathUnauthenticated` (8 tests) asserts 200 + all fields via `TestClient` with no auth header |
| SC#2 | `GET /.well-known/oauth-authorization-server` returns HTTP 200 with RFC 8414 JSON including `code_challenge_methods_supported: ["S256"]` | VERIFIED | `build_oasm_document()` in `oauth_metadata.py` hardcodes `"code_challenge_methods_supported": ["S256"]`; `TestOasmUnauthenticated` (11 tests) asserts 200 + exact S256 value |
| SC#3 | Both well-known endpoints return 200 even when `RequireAuthMiddleware` is added in Phase 67 (proven by mount-order test) | VERIFIED | `TestMountOrderContract` (5 tests) iterates `build_asgi_app(server).routes` and asserts each well-known Route index < Mount("/mcp") index; comment at routes list explicitly names Phase 67 survival contract |
| SC#4 | `AGENT_BRAIN_AUTH=basic` formalizes shared-secret Bearer; `none`/`basic`/`oauth` are mutually exclusive; startup gate rejects invalid combinations with exit code 2 | VERIFIED | `AuthMode(str, Enum)` in `config.py` has exactly {none, basic, oauth}; `check_auth_startup_gate()` calls `sys.exit(2)` on invalid toggle and on oauth-mode absent/scheme-less/fragment resource; `get_auth_dependency()` returns exactly one value per mode; 51 tests in `test_auth_mode_config.py` + `test_mcp_startup_gate.py` |

**Score:** 4/4 success criteria verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-mcp/agent_brain_mcp/config.py` | AuthMode enum, OAuth settings resolver, check_auth_startup_gate(), get_auth_dependency() | VERIFIED | `class AuthMode(str, Enum)` with none/basic/oauth; `_raw_auth_mode()`, `resolve_auth_mode()`, `resolve_oauth_settings()`, `check_auth_startup_gate()`, `get_auth_dependency()` all present and substantive (272 lines of new code + existing backend client code) |
| `agent-brain-mcp/agent_brain_mcp/oauth_metadata.py` | build_prm_document() + build_oasm_document() | VERIFIED | New file; `build_prm_document()` with resource/authorization_servers/scopes_supported; `build_oasm_document()` with all RFC 8414 fields + `code_challenge_methods_supported: ["S256"]`; forward-reference comment block present |
| `agent-brain-mcp/agent_brain_mcp/http.py` | Well-known Routes mounted above /mcp Mount; startup gate called | VERIFIED | PRM_PATH, PRM_PATH_SUFFIXED, OASM_PATH constants defined and exported; three Route handlers added; `_config.check_auth_startup_gate()` called at top of `build_asgi_app()`; MOUNT-ORDER CONTRACT comment at routes list; routes list order: healthz → PRM → PRM_SUFFIXED → OASM → Mount(/mcp) |
| `agent-brain-mcp/tests/test_auth_mode_config.py` | 20 tests for AuthMode + settings resolver | VERIFIED | 20 tests covering enum shape, case-insensitive resolution, pure-read resolver, empty-string normalization |
| `agent-brain-mcp/tests/test_mcp_startup_gate.py` | 31 tests for startup gate + selector | VERIFIED | 31 tests: valid modes silent, 7 invalid toggle values exit 2, 5 resource failure modes, fragment rejection, none/basic no-resource, selector mutual exclusion |
| `agent-brain-mcp/tests/test_oauth_metadata_documents.py` | 25 tests for PRM/OASM builders | VERIFIED | 25 tests: PRM shape/fields/scopes, OASM shape/S256/endpoint derivation, JSON-serializability |
| `agent-brain-mcp/tests/test_well_known_routes.py` | 33 tests for unauthenticated 200 + mount-order | VERIFIED | 33 tests: SC#1 PRM base path, SC#1 path-suffixed identical document, SC#2 OASM with exact S256, SC#3 mount-order proof, startup-gate-at-build-time proof, env-var reflection tests |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `http.py::build_asgi_app` | `config.check_auth_startup_gate` | Called at top of function before any route construction | WIRED | `_config.check_auth_startup_gate()` is the first statement in `build_asgi_app()` body (line 211) |
| `http.py::build_asgi_app` | `oauth_metadata.build_prm_document` | `oauth_protected_resource` handler calls it via `_oauth_metadata.build_prm_document(...)` | WIRED | Handler at lines 224-243 calls `_config.resolve_oauth_settings()` + `_oauth_metadata.build_prm_document()` + returns `JSONResponse(doc)` |
| `http.py::build_asgi_app` | `oauth_metadata.build_oasm_document` | `oauth_authorization_server` handler calls it via `_oauth_metadata.build_oasm_document(...)` | WIRED | Handler at lines 245-264 calls `_config.resolve_oauth_settings()` + `_oauth_metadata.build_oasm_document()` + returns `JSONResponse(doc)` |
| `config.py::check_auth_startup_gate` | `sys.exit(2)` | Invalid toggle value or oauth-mode absent/empty/scheme-less/fragment resource | WIRED | Three `sys.exit(2)` calls present: (1) invalid toggle, (2) absent/empty resource in oauth mode, (3) scheme-less or fragment URI |
| `config.py::get_auth_dependency` | `AuthMode` toggle | Single selector keyed on `resolve_auth_mode()` result | WIRED | Three branches: `AuthMode.none` → None, `AuthMode.basic` → "basic-bearer", oauth → NotImplementedError (Phase 67 placeholder) |
| PRM document `resource` field | `AGENT_BRAIN_OAUTH_RESOURCE` | `resolve_oauth_settings()` read at request time; fallback to `str(request.base_url).rstrip("/")` | WIRED | `resource_env, issuer_env = _config.resolve_oauth_settings()` then `resource = resource_env or base_url` |
| Well-known Routes | Mounted ABOVE `/mcp` Mount | Position in `Starlette(routes=[...])` list | WIRED | Routes list: healthz (idx 0), PRM (idx 1), PRM_SUFFIXED (idx 2), OASM (idx 3), Mount(/mcp) (idx 4) — confirmed by `TestMountOrderContract` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OAUTH-09 | 66-01-PLAN.md | Auth mode toggle `{none, basic, oauth}` mutually exclusive; startup gate; `basic` formalizes SECURITY-01 | SATISFIED | `AuthMode` enum in config.py; `check_auth_startup_gate()` + `get_auth_dependency()`; 51 tests green |
| OAUTH-02 | 66-02-PLAN.md | PRM at `/.well-known/oauth-protected-resource` (+ path-suffixed) returns 200 unauthenticated with RFC 9728 fields | SATISFIED | `PRM_PATH` + `PRM_PATH_SUFFIXED` Routes in http.py; `build_prm_document()` in oauth_metadata.py; 33 acceptance tests green |
| OAUTH-03 | 66-02-PLAN.md | OASM at `/.well-known/oauth-authorization-server` returns 200 with `code_challenge_methods_supported: ["S256"]` | SATISFIED | `OASM_PATH` Route in http.py; `build_oasm_document()` hardcodes `["S256"]`; 11 OASM tests + 25 document tests green |

REQUIREMENTS.md shows all three marked `[x]` (complete) with "Phase 66 | Complete" in the requirements table.

---

### Scope Guard (Absent Items — Correct Absence)

The following items from Phases 67-70 are correctly NOT present in this phase:

| Item | Expected Absent | Confirmed |
|------|-----------------|-----------|
| `/authorize` route | Yes — Phase 67 | Confirmed: grep for `/authorize` in http.py returns only comments and forward-reference strings in oauth_metadata.py docstring |
| `/token` route | Yes — Phase 67 | Confirmed: only in OASM document `token_endpoint` forward-reference value |
| `/register` route | Yes — Phase 67 | Confirmed: only in OASM document `registration_endpoint` forward-reference value |
| `/.well-known/jwks.json` route | Yes — Phase 67 | Confirmed: only in OASM document `jwks_uri` forward-reference value |
| `RequireAuthMiddleware` (as import or instantiation) | Yes — Phase 67 | Confirmed: appears only in comments/docstrings naming it as Phase 67 target |
| `_tool_matrix.py` | Yes — Phase 68 (OAUTH-06) | Confirmed: file does not exist |
| `FileTokenStorage` | Yes — Phase 67/OAUTH-07 | Confirmed: not present anywhere in mcp package |

---

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, no empty implementations, no stub return values in the phase-66 added code. The oauth-branch `NotImplementedError` in `get_auth_dependency()` is intentional and documented as a Phase 67 placeholder (not a stub — it is the correct behavior for the selector seam).

---

### Test Run Results

**Command:** `cd agent-brain-mcp && poetry run pytest tests/test_well_known_routes.py tests/test_oauth_metadata_documents.py tests/test_auth_mode_config.py tests/test_mcp_startup_gate.py -q`

**Result:** `109 passed in 0.44s`

Breakdown:
- `test_auth_mode_config.py`: 20 tests
- `test_mcp_startup_gate.py`: 31 tests (per summary; 51 total Plan 01 tests align with 20 + 31)
- `test_oauth_metadata_documents.py`: 25 tests
- `test_well_known_routes.py`: 33 tests

---

### Human Verification Required

None. All Phase 66 deliverables are automated-testable:
- HTTP endpoint behavior verified via Starlette `TestClient` (no Authorization header)
- Startup gate verified via `pytest.raises(SystemExit)` with `exc_info.value.code == 2`
- Mount-order contract verified by iterating `build_asgi_app().routes` and comparing indices
- No visual, real-time, or external-service dependencies in this phase

---

## Gaps Summary

No gaps. All four success criteria are fully satisfied in the actual codebase.

The phase goal is achieved: the OAuth discovery root is live (PRM + OASM public routes serve RFC-valid documents unauthenticated), `basic` mode is formalized under the exclusive `AuthMode` toggle, and all three auth-mode paths (`none`/`basic`/`oauth`) are wired with a startup gate that exits code 2 on misconfiguration. The mount-order contract is proven by an automated test that will survive Phase 67 without modification.

---

_Verified: 2026-06-14_
_Verifier: Claude (gsd-verifier)_
