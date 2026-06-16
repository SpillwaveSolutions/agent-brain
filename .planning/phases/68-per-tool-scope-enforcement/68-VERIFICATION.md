---
phase: 68-per-tool-scope-enforcement
verified: 2026-06-16T22:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Phase 68: Per-Tool Scope Enforcement Verification Report

**Phase Goal:** Every MCP tool enforces exactly the scope it requires; a token with an insufficient scope returns 403 (not 401); the scope-to-tool mapping is the single source of truth co-located with the tool registry, protected by an import-time drift guard.

**Verified:** 2026-06-16T22:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An `agent-brain:read`-only token can call all 9 read tools and succeeds (SC#1) | VERIFIED | `TestSC1ReadTokenOnReadTools.test_sc1_all_read_tools_pass_guard` parametrized over 9 read tools; `test_sc1_list_folders_with_read_token_passes_guard` round-trips 200 via fake backend. 916 tests pass. |
| 2 | An `agent-brain:read`-only token calling any index tool returns HTTP 403 with `WWW-Authenticate: Bearer error="insufficient_scope"` — NOT 401 (SC#2) | VERIFIED | `TestSC1ReadTokenOnReadTools.test_sc2_all_index_tools_403_with_read_token` parametrized over all 4 index tools; `test_403_not_401_insufficient_scope` confirms status != 401; Level B TestClient `test_sc2_read_token_on_index_tool_returns_403` asserts `response.status_code == 403` and `scope="agent-brain:index"` in WWW-Authenticate. |
| 3 | An `agent-brain:read`-only token calling any admin tool returns HTTP 403 insufficient_scope (SC#3) | VERIFIED | `TestSC1ReadTokenOnReadTools.test_sc3_all_admin_tools_403_with_read_token` parametrized over 3 admin tools; Level B tests `test_sc3_read_token_on_admin_tool_returns_403`, `test_sc3_read_token_on_remove_folder_returns_403`, `test_sc3_read_token_on_clear_cache_returns_403` each assert `status_code == 403` and `scope="agent-brain:admin"` in WWW-Authenticate. |
| 4 | Scope-to-tool mapping is a single SOT covering ALL 16 TOOL_REGISTRY keys; import-time drift guard raises RuntimeError naming any unassigned tool (SC#4) | VERIFIED | `tools/__init__.py` lines 339-435: `TOOL_SCOPE_REQUIREMENTS` (16 entries) + `_assert_every_tool_has_scope()` called at module bottom. `test_scope_map_covers_all_registry_tools` asserts set equality; `test_drift_guard_raises_runtime_error_on_missing_tool` proves `RuntimeError` naming "clear_cache". |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent-brain-mcp/agent_brain_mcp/oauth/scopes.py` | `VALID_SCOPES` frozenset, `InsufficientScopeError` with `.required`, `require_scope()` pure helper | VERIFIED | File exists (134 lines). `VALID_SCOPES` = 4-scope frozenset. `InsufficientScopeError.__init__` stores `self.required`. `require_scope()` raises on absent scope including empty list (deny-by-default). |
| `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` | `TOOL_SCOPE_REQUIREMENTS` dict (16 keys) + import-time drift guard | VERIFIED | Lines 339-443: `TOOL_SCOPE_REQUIREMENTS` with 16 entries across 3 scope tiers; `_scope_drift()` pure helper; `_assert_every_tool_has_scope()` called at line 435; `"TOOL_SCOPE_REQUIREMENTS"` in `__all__` at line 439. |
| `agent-brain-mcp/agent_brain_mcp/http.py` | `ScopeEnforcementMiddleware` pre-dispatch ASGI guard; middleware composition: `AuthenticationMiddleware` outermost | VERIFIED | Class at line 201. Buffers body with `more_body` loop. `_required_scope()` maps 4 method patterns. `_send_403()` emits `status=403` + `Bearer error="insufficient_scope", scope="<required>", resource_metadata=...`. Wired at line 721: `AuthenticationMiddleware(RequireAuthMiddleware(ScopeEnforcementMiddleware(mcp_asgi_app, ...), ...), backend=backend)`. |
| `agent-brain-mcp/agent_brain_mcp/server.py` | `_enforce_scope()` defense-in-depth at 4 dispatch points, mode-gated to oauth | VERIFIED | Lines 89-120: `_enforce_scope()` early-returns if `resolve_auth_mode() != AuthMode.oauth`. Called at: `call_tool` (line 335, via `TOOL_SCOPE_REQUIREMENTS[name]`), `read_resource` (line 403), `get_prompt` (line 496), `handle_subscribe` (line 552). `handle_unsubscribe` intentionally unguarded. |
| `agent-brain-mcp/tests/test_tool_scope_sot.py` | SOT tests: completeness, valid values, locked assignment, drift guard raises, require_scope round-trip | VERIFIED | 31 tests (per summary). Parametrizes 16 tool/scope pairs via `_LOCKED_ASSIGNMENTS`. Proves `_assert_every_tool_has_scope()` raises `RuntimeError` with message containing "clear_cache". Includes empty-granted-scopes deny-by-default case. |
| `agent-brain-mcp/tests/test_tool_scope_enforcement.py` | SC#1/#2/#3 acceptance tests + resource/subscribe/prompt gates + real HTTP 403 via TestClient | VERIFIED | 61 tests (per summary). Level A: `_required_scope` unit tests, `_send_403` emission unit tests, `_enforce_scope` unit tests. Level B: `TestScopeEnforcementHTTP` class drives real HTTP 403 via Starlette `TestClient`. `TestResourceAndPromptGates` covers resources/read, resources/subscribe, prompts/get. `TestModeGating` proves none/basic no-op. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tools/__init__.py` module import | `TOOL_SCOPE_REQUIREMENTS` vs `TOOL_REGISTRY.keys()` | `_assert_every_tool_has_scope()` raising `RuntimeError` at line 435 | WIRED | `_assert_every_tool_has_scope()` is called at module bottom (line 435), not just in tests. `set(TOOL_SCOPE_REQUIREMENTS) == set(TOOL_REGISTRY)` confirmed via `python -c` import check. |
| `oauth/scopes.py` `require_scope` | `InsufficientScopeError` | `raise InsufficientScopeError(required, ...)` at line 134 | WIRED | Confirmed in source. |
| `POST /mcp` JSON-RPC body | `TOOL_SCOPE_REQUIREMENTS[name]` | `ScopeEnforcementMiddleware._required_scope()` buffers body, parses method+params | WIRED | `http.py` line 340: `return TOOL_SCOPE_REQUIREMENTS.get(name) if name else None`. |
| Insufficient scope decision | HTTP 403 `WWW-Authenticate: Bearer error="insufficient_scope"` | `_send_403()` emits `http.response.start` with `status=403` directly via ASGI send | WIRED | Confirmed at `http.py` lines 352-396. Status is literal `403`, never `401`. |
| `AuthenticationMiddleware` sets `scope["user"]` | `ScopeEnforcementMiddleware` reads `scope.get("user").scopes` | `ScopeEnforcementMiddleware` is wrapped INSIDE `AuthenticationMiddleware` | WIRED | Actual code at line 721: `AuthenticationMiddleware(RequireAuthMiddleware(ScopeEnforcementMiddleware(...)), backend=backend)`. Auth outermost, runs first, populates `scope["user"]`. |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| OAUTH-06 | 68-01, 68-02 | Per-tool scope enforcement, 16 tools, single SOT, 403 on insufficient scope | SATISFIED | `TOOL_SCOPE_REQUIREMENTS` (16 keys), `ScopeEnforcementMiddleware`, `_enforce_scope`, 92 tests (31 SOT + 61 enforcement) all pass. `[x]` in REQUIREMENTS.md line 24. |
| OAUTH-07 | Phase 69 (NOT Phase 68) | McpHttpBackend client-side OAuth dance | PENDING (correctly so) | `[ ]` in REQUIREMENTS.md line 25. Traceability table: `OAUTH-07 | Phase 69 | Pending`. The 68-02-SUMMARY.md erroneously claims `requirements-completed: [OAUTH-07]` — this is a summary-document error; the canonical REQUIREMENTS.md and ROADMAP.md both correctly show OAUTH-07 as Pending/Phase 69. No OAUTH-07 implementation code was found in Phase 68 artifacts. |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `agent-brain-mcp/agent_brain_mcp/http.py` | 19-22 (module docstring) | Middleware composition order in docstring shows old incorrect order `RequireAuthMiddleware(AuthenticationMiddleware(ScopeEnforcementMiddleware(...)))` | INFO (documentation only) | Docstring was not updated after the bug-fix that swapped to `AuthenticationMiddleware(RequireAuthMiddleware(ScopeEnforcementMiddleware(...)))` at line 721. Actual runtime code is correct and tests pass. |
| `agent-brain-mcp/.planning/phases/68-per-tool-scope-enforcement/68-02-SUMMARY.md` | line 49 | `requirements-completed: [OAUTH-07]` | INFO (summary doc only) | The summary incorrectly claims OAUTH-07 was completed by this phase. OAUTH-07 remains Pending in all canonical tracking files (REQUIREMENTS.md, ROADMAP.md). No OAUTH-07 implementation exists in the Phase 68 codebase. Not a functional gap. |

---

### Human Verification Required

None required — all acceptance criteria are verified programmatically.

---

### Gaps Summary

No gaps. All 4 ROADMAP success criteria are verified against the actual codebase:

- SC#1: 9 read tools verified with `agent-brain:read` token via parametrized Level B tests.
- SC#2: All 4 index tools (index_folder, add_documents, inject_documents, wait_for_job) return HTTP 403 with `insufficient_scope` — verified via Level B TestClient.
- SC#3: All 3 admin tools (cancel_job, remove_folder, clear_cache) return HTTP 403 with `insufficient_scope` — verified via Level B TestClient.
- SC#4: `set(TOOL_SCOPE_REQUIREMENTS) == set(TOOL_REGISTRY)` (16 == 16), import-time `RuntimeError` guard fires at module bottom (not test-only), drift test proves message names "clear_cache" on removal.

The two documentation inconsistencies (docstring in `http.py` and summary-level OAUTH-07 claim) are non-functional and do not affect goal achievement.

Test run: 916 passed, 0 failed, 0 regressions (full `agent-brain-mcp` suite including Phase 66 well-known route regression and Phase 67 RS middleware regression).

---

_Verified: 2026-06-16T22:00:00Z_
_Verifier: Claude (gsd-verifier)_
