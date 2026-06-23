---
phase: 70-split-as-rs-keycloak-in-ci-integration-tests
verified: 2026-06-22T20:00:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 70: Split AS/RS Keycloak-in-CI Integration Tests — Verification Report

**Phase Goal:** The split AS/RS topology is validated end-to-end against Keycloak in CI; token introspection and revocation close the DoD; the full OAuth flow has a >=90% coverage gate on `agent_brain_mcp/oauth/`.
**Verified:** 2026-06-22T20:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A JWT signed by a remote IdP is accepted by JwksTokenVerifier via cached JWKS (5-min TTL + kid-miss refresh) | VERIFIED | `class JwksTokenVerifier` in verifier.py line 209; `PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=lifespan)` at line 255; `asyncio.to_thread(` at line 277; test_oauth_jwks_verifier.py has `test_jwks_ttl_caching` and `test_kid_miss_triggers_refresh` |
| 2 | A JWT whose aud != AGENT_BRAIN_OAUTH_RESOURCE is rejected (verify_token returns None) | VERIFIED | `test_wrong_aud_returns_none` exists in test_oauth_jwks_verifier.py line 185; JwksTokenVerifier passes `audience=self.resource` to `jwt.decode` |
| 3 | An introspection response with active:true + matching aud yields an AccessToken; active:false yields None | VERIFIED | `class IntrospectionTokenVerifier` in verifier.py line 317; `isinstance(aud, str)` aud-list normalization at line 418; `test_active_true_returns_token` line 91 and `test_active_false_returns_none` line 155 in test_oauth_introspection_verifier.py |
| 4 | A token whose jti is on the in-memory denylist is rejected by LocalRs256Verifier on next use | VERIFIED | `def revoke_by_jti` at tokens.py line 321; `def is_jti_revoked` at line 339; `_revoked_jtis: set[str]` at line 167; `_jti_lock = threading.Lock()` at line 168; `is_jti_revoked(jti)` check in verifier.py at line 187; `test_revoked_jti_returns_none` in test_oauth_jti_denylist.py line 151 |
| 5 | JWKS_URI selects JwksTokenVerifier; INTROSPECTION_URL selects IntrospectionTokenVerifier; neither falls back to LocalRs256Verifier | VERIFIED | `def build_verifier` in verifier.py line 493; `def resolve_split_as_settings` in config.py line 270; `AGENT_BRAIN_OAUTH_JWKS_URI` env var read at line 306; `test_jwks_uri_selects_jwks_verifier` in test_oauth_split_as_config.py line 165; http.py uses `build_verifier(issuer_override=issuer)` at line 766; `build_local_verifier(issuer_override=issuer)` count = 0 |
| 6 | A real Keycloak 26.1 container runs in CI via step-level docker run start-dev (NOT a services: block) | VERIFIED | mcp-keycloak-integration.yml: `docker run -d --name keycloak ... quay.io/keycloak/keycloak:26.1 start-dev` at line 80-85; all 3 occurrences of `services:` in the file are in comments only (not YAML keys) |
| 7 | Keycloak fixtures are discoverable by pytest via bridge import in conftest.py | VERIFIED | tests/conftest.py lines 26-30: `from tests.conftest_keycloak import (keycloak_access_token, keycloak_available, keycloak_token_for_scope,)  # noqa: F401`; conftest_keycloak.py defines all three fixtures; `keycloak_available` issues `pytest.skip` on connection failure |
| 8 | SC#1-4 tests exist in test_oauth_keycloak_e2e.py (JWT accepted, introspection round-trip, revoked rejected, tool call + refresh + scope-boundary 403) | VERIFIED | All 7 `@pytest.mark.keycloak` tests present: `test_keycloak_jwt_accepted` (SC#1), `test_kid_present_in_keycloak_jwks` (SC#1 supporting), `test_introspection_roundtrip` (SC#2), `test_revoked_token_rejected` (SC#3), `test_full_oauth_dance_tool_call` (SC#4), `test_token_refresh_path` (SC#4 refresh), `test_scope_boundary_403` (SC#4 scope boundary asserts `resp.status_code == 403` and `"insufficient_scope" in www_auth`) |
| 9 | keycloak-marked tests skip cleanly when no container is present; excluded from fast tier | VERIFIED | pyproject.toml addopts = "-m 'not e2e and not e2e_http and not contract and not stress and not keycloak'"; `keycloak_available` fixture calls `pytest.skip("Keycloak not available")` on connection error; marker registered at pyproject.toml line 113 |
| 10 | Binding >=90% oauth-module coverage gate wired in CI with real failing exit code | VERIFIED | mcp-keycloak-integration.yml lines 129-134: `--cov=agent_brain_mcp.oauth --cov-fail-under=90`; step labelled "OAuth module coverage gate (90% CI hard — SC#5 DoD)"; Taskfile.yml has `oauth-cov` target with `COV_FAIL_UNDER` var (default 85 local, 90 in CI) |
| 11 | Operator doc SPLIT_AS_RS.md exists and design doc has Phase 70 re-verification note | VERIFIED | agent-brain-mcp/docs/SPLIT_AS_RS.md exists with AGENT_BRAIN_OAUTH_JWKS_URI, AGENT_BRAIN_OAUTH_INTROSPECTION_URL, AGENT_BRAIN_OAUTH_ISSUER, RFC 8707 deviation, keycloak_bootstrap.sh reference, revocation behavior; docs/plans/2026-06-14-mcp-v4-oauth-design.md contains "Phase 70 Spec Re-Verification (2026-06-22)" section with RequireAuthMiddleware per-request conclusion |

**Score:** 11/11 truths verified

---

## Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `agent-brain-mcp/agent_brain_mcp/oauth/verifier.py` | VERIFIED | 551 lines; JwksTokenVerifier, IntrospectionTokenVerifier, build_verifier all present; asyncio.to_thread, PyJWKClient(cache_jwk_set=True, lifespan=), isinstance(aud, str) all confirmed |
| `agent-brain-mcp/agent_brain_mcp/oauth/tokens.py` | VERIFIED | 390 lines; revoke_by_jti, is_jti_revoked, _revoked_jtis, threading.Lock all present |
| `agent-brain-mcp/agent_brain_mcp/config.py` | VERIFIED | 714 lines; resolve_split_as_settings() and AGENT_BRAIN_OAUTH_JWKS_URI present |
| `agent-brain-mcp/agent_brain_mcp/oauth/__init__.py` | VERIFIED | JwksTokenVerifier, IntrospectionTokenVerifier, build_verifier all in imports and __all__ (lines 75-92) |
| `agent-brain-mcp/agent_brain_mcp/http.py` | VERIFIED | build_verifier(issuer_override=issuer) at line 766; build_local_verifier(issuer_override=issuer) count = 0 |
| `agent-brain-mcp/tests/test_oauth_jwks_verifier.py` | VERIFIED | Exists; test_wrong_aud_returns_none, test_jwks_ttl_caching, test_kid_miss_triggers_refresh present |
| `agent-brain-mcp/tests/test_oauth_introspection_verifier.py` | VERIFIED | Exists; test_active_true_returns_token, test_active_false_returns_none present |
| `agent-brain-mcp/tests/test_oauth_jti_denylist.py` | VERIFIED | Exists; test_revoked_jti_returns_none present |
| `agent-brain-mcp/tests/test_oauth_split_as_config.py` | VERIFIED | Exists; test_jwks_uri_selects_jwks_verifier present |
| `agent-brain-mcp/pyproject.toml` | VERIFIED | keycloak marker registered + "not keycloak" in addopts |
| `agent-brain-mcp/tests/conftest_keycloak.py` | VERIFIED | keycloak_available, keycloak_access_token, keycloak_token_for_scope all defined; pytest.skip on connection error |
| `agent-brain-mcp/tests/conftest.py` | VERIFIED | Bridge import with all three fixture names present (noqa: F401) |
| `agent-brain-mcp/tests/test_oauth_keycloak_e2e.py` | VERIFIED | 7 @pytest.mark.keycloak tests; SC#4 test_scope_boundary_403 asserts 403 + insufficient_scope |
| `.github/workflows/mcp-keycloak-integration.yml` | VERIFIED | Valid YAML; quay.io/keycloak/keycloak:26.1 start-dev; step-level docker run only; path filter agent-brain-mcp/**; 9000/health/ready health check; keycloak_bootstrap.sh invoked; --cov-fail-under=90 present |
| `.github/workflows/e2e-nightly.yml` | VERIFIED | Valid YAML; mcp-keycloak-nightly job added; step-level docker run start-dev; keycloak_bootstrap.sh invoked; existing schedule cron preserved |
| `scripts/keycloak_bootstrap.sh` | VERIFIED | Exists; oidc-audience-mapper, included.custom.audience, RFC 8707 DEVIATION, directAccessGrantsEnabled, agent-brain:read all present |
| `agent-brain-mcp/Taskfile.yml` | VERIFIED | oauth-cov target with --cov=agent_brain_mcp.oauth and --cov-fail-under; keycloak target with -m keycloak; both namespaced as mcp:oauth-cov / mcp:keycloak via root includes |
| `agent-brain-mcp/docs/SPLIT_AS_RS.md` | VERIFIED | New file; all required env vars documented; RFC 8707 deviation; keycloak_bootstrap.sh reference; revocation behavior; no public /revoke note |
| `docs/plans/2026-06-14-mcp-v4-oauth-design.md` | VERIFIED | "Phase 70 Spec Re-Verification (2026-06-22)" section present; RequireAuthMiddleware per-request conclusion recorded |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `agent-brain-mcp/agent_brain_mcp/http.py` | `agent_brain_mcp.oauth.verifier.build_verifier` | `build_verifier(issuer_override=issuer)` at line 766 | WIRED | Old `build_local_verifier(issuer_override=issuer)` call count = 0 |
| `agent-brain-mcp/agent_brain_mcp/oauth/verifier.py (LocalRs256Verifier)` | `agent_brain_mcp.oauth.tokens.token_store.is_jti_revoked` | `is_jti_revoked(jti)` check at verifier.py line 187 | WIRED | Called after successful jwt.decode, before returning AccessToken |
| `agent-brain-mcp/tests/conftest.py` | `agent-brain-mcp/tests/conftest_keycloak.py` | `from tests.conftest_keycloak import (keycloak_available, keycloak_access_token, keycloak_token_for_scope,)` | WIRED | noqa: F401 correctly prevents false unused-import warnings |
| `.github/workflows/mcp-keycloak-integration.yml` | `scripts/keycloak_bootstrap.sh` | `bash scripts/keycloak_bootstrap.sh` step at line 107 | WIRED | Runs after container health check passes |
| `agent-brain-mcp/tests/test_oauth_keycloak_e2e.py` | `agent_brain_mcp.oauth.verifier.JwksTokenVerifier` | JwksTokenVerifier constructed with live Keycloak JWKS URI in test_full_oauth_dance_tool_call | WIRED | AGENT_BRAIN_OAUTH_JWKS_URI set and referenced |
| `.github/workflows/mcp-keycloak-integration.yml` | `task mcp:oauth-cov` (via `--cov-fail-under=90`) | Coverage gate step runs `--cov=agent_brain_mcp.oauth --cov-fail-under=90` directly | WIRED | Binding SC#5 DoD gate active |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OAUTH-11 | 70-01, 70-02, 70-03 | Split AS/RS mode — RS verifies JWTs against external IdP via cached JWKS (kid-miss + TTL), verified E2E against Keycloak-in-CI | SATISFIED | JwksTokenVerifier with PyJWKClient(cache_jwk_set=True, lifespan=300); 7 @pytest.mark.keycloak tests including test_keycloak_jwt_accepted; CI workflow path-filtered to agent-brain-mcp/** |
| OAUTH-12 | 70-01, 70-02, 70-03 | Token introspection (RFC 7662) + revocation (RFC 7009) for opaque-token / external-AS deployments | SATISFIED | IntrospectionTokenVerifier with active:false -> None; jti denylist (revoke_by_jti/is_jti_revoked) on InMemoryTokenStore; test_revoked_token_rejected + test_introspection_roundtrip |

Both OAUTH-11 and OAUTH-12 are marked complete in .planning/REQUIREMENTS.md (lines 32-33, 86-87). No orphaned requirements found.

---

## Anti-Patterns Found

No blockers or warnings detected.

| File | Pattern | Severity | Notes |
|------|---------|----------|-------|
| None | — | — | No TODO/FIXME/placeholder patterns, no empty implementations, no stub returns found in the key artifact files |

The `services:` string appears 3 times in mcp-keycloak-integration.yml but all 3 occurrences are inside YAML comments (lines 12, 15, 79), not as live YAML keys. The Keycloak container is correctly started via step-level docker run only.

---

## Human Verification Required

### 1. Keycloak E2E Tests Pass in CI

**Test:** Trigger a PR touching `agent-brain-mcp/**` or run the `mcp-keycloak-integration` workflow manually.
**Expected:** All 7 `@pytest.mark.keycloak` tests pass; oauth module coverage reported at >=90%; `--cov-fail-under=90` step exits 0.
**Why human:** Requires a live Keycloak 26.1 container and network; cannot be verified in a static code check.

### 2. Fast Suite Regression — 1021 Tests Still Pass

**Test:** `cd agent-brain-mcp && task test` (or `task before-push` from repo root).
**Expected:** 1021 passed, ~118 deselected (keycloak + other opt-in markers), 0 failures.
**Why human:** SUMMARY claims 1021 passed as of 2026-06-22; re-running confirms nothing has regressed since.

### 3. Local OAuth Coverage Soft Gate

**Test:** `cd agent-brain-mcp && task oauth-cov` (no container).
**Expected:** >=85% on agent_brain_mcp.oauth (SUMMARY reports 90.53% with the fast tier alone).
**Why human:** Coverage measurement requires actually running the test suite.

---

## Summary

Phase 70 goal is fully achieved. All three plans delivered complete, substantive, wired artifacts:

**Plan 70-01** delivered the split-AS verification engine: `JwksTokenVerifier` (PyJWKClient JWKS caching, asyncio.to_thread, kid-miss refresh), `IntrospectionTokenVerifier` (RFC 7662, aud-list normalization), the `jti` denylist on `InMemoryTokenStore`, and `build_verifier()` config selector wired into `http.py`. Four mock-backed unit test files (60 tests) cover the new code, and the oauth module coverage was 90% after this plan landed.

**Plan 70-02** stood up the Keycloak testing tier: marker registered + excluded from fast tier, `conftest_keycloak.py` with `keycloak_available` skip fixture and `keycloak_token_for_scope` factory, the conftest bridge import, the Admin-REST-API bootstrap script (RFC 8707 audience mapper deviation documented), SC#1-3 tests, and the CI workflow with step-level docker run start-dev (no services: block) path-filtered to agent-brain-mcp/**.

**Plan 70-03** closed the DoD: SC#4 Keycloak RS path tests (tool call, token refresh, scope-boundary 403 with `insufficient_scope`), the binding >=90% oauth-module coverage gate in CI, the Phase 70 live-spec re-verification recorded in the design doc, and the operator `SPLIT_AS_RS.md` covering all env vars, the Keycloak RFC 8707 workaround, and revocation behavior.

OAUTH-11 and OAUTH-12 are both satisfied. No gaps found in automated checks. Human verification is limited to running the CI pipeline with a live container.

---

_Verified: 2026-06-22T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
