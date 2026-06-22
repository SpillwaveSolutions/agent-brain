---
phase: 70-split-as-rs-keycloak-in-ci-integration-tests
plan: 01
subsystem: agent-brain-mcp/oauth
tags: [oauth, split-as-rs, jwks, introspection, jti-denylist, verifier, config]
dependency_graph:
  requires: []
  provides:
    - JwksTokenVerifier (agent_brain_mcp.oauth.verifier)
    - IntrospectionTokenVerifier (agent_brain_mcp.oauth.verifier)
    - build_verifier() selector (agent_brain_mcp.oauth.verifier)
    - jti denylist (agent_brain_mcp.oauth.tokens.InMemoryTokenStore)
    - resolve_split_as_settings() (agent_brain_mcp.config)
  affects:
    - agent-brain-mcp/agent_brain_mcp/oauth/verifier.py
    - agent-brain-mcp/agent_brain_mcp/oauth/tokens.py
    - agent-brain-mcp/agent_brain_mcp/oauth/__init__.py
    - agent-brain-mcp/agent_brain_mcp/config.py
    - agent-brain-mcp/agent_brain_mcp/http.py
tech_stack:
  added: []
  patterns:
    - asyncio.to_thread() for sync PyJWKClient in async verify_token (Pitfall 1)
    - isinstance(aud, str) check for RFC 7662 aud list normalization (Pitfall 2)
    - threading.Lock() for jti denylist write safety
    - build_verifier() config-driven selector pattern
key_files:
  created:
    - agent-brain-mcp/tests/test_oauth_jwks_verifier.py
    - agent-brain-mcp/tests/test_oauth_introspection_verifier.py
    - agent-brain-mcp/tests/test_oauth_jti_denylist.py
    - agent-brain-mcp/tests/test_oauth_split_as_config.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/oauth/verifier.py
    - agent-brain-mcp/agent_brain_mcp/oauth/tokens.py
    - agent-brain-mcp/agent_brain_mcp/oauth/__init__.py
    - agent-brain-mcp/agent_brain_mcp/config.py
    - agent-brain-mcp/agent_brain_mcp/http.py
decisions:
  - "JwksTokenVerifier uses asyncio.to_thread() to wrap the synchronous PyJWKClient.get_signing_key_from_jwt() call"
  - "IntrospectionTokenVerifier is a separate class (not a mode of JwksTokenVerifier) for cleaner protocol and independent testability"
  - "jti denylist uses plain set[str] with threading.Lock for writes; GIL-safe for reads"
  - "build_verifier() selector: JWKS_URI > INTROSPECTION_URL > LocalRs256Verifier (co-located fallback)"
  - "aud list normalization in IntrospectionTokenVerifier: isinstance(aud, str) -> [aud]; isinstance(aud, list) -> list[str]; else -> []"
metrics:
  duration: 28 minutes
  completed_date: "2026-06-22"
  tasks_completed: 3
  files_created: 4
  files_modified: 5
---

# Phase 70 Plan 01: Split-AS Verifier Classes + jti Denylist Summary

**One-liner:** JwksTokenVerifier (PyJWKClient JWKS + asyncio.to_thread), IntrospectionTokenVerifier (RFC 7662 + aud-list normalization), jti denylist on InMemoryTokenStore, and build_verifier() config selector wired into http.py.

## What Was Built

Three TDD-verified verification capabilities behind the existing stable `verify_token(token) -> AccessToken | None` protocol:

1. **JwksTokenVerifier** (OAUTH-11): Remote JWKS verification via `PyJWKClient` with `cache_jwk_set=True`, `lifespan=300s`. Wraps synchronous `get_signing_key_from_jwt()` in `asyncio.to_thread()` to avoid blocking the event loop (Pitfall 1 from RESEARCH). kid-miss on-demand refresh is handled internally by `PyJWKClient`.

2. **IntrospectionTokenVerifier** (OAUTH-12 SC#2/SC#3): RFC 7662 introspection via `httpx.AsyncClient`. `active:false` → None (revocation via introspection is automatic). Normalizes `aud` field per Pitfall 2: string → `[aud]`; list → `list[str]`; absent → `[]`.

3. **jti denylist on InMemoryTokenStore** (OAUTH-12 SC#3): `_revoked_jtis: set[str]` + `_jti_lock: threading.Lock` added to `InMemoryTokenStore.__init__`. `revoke_by_jti(jti)` stores only the jti string (never the full JWT). `LocalRs256Verifier.verify_token` checks `token_store.is_jti_revoked(jti)` after successful decode, before returning `AccessToken`.

4. **build_verifier() selector**: Config-driven factory in `verifier.py` selecting `JwksTokenVerifier` (JWKS_URI set), `IntrospectionTokenVerifier` (INTROSPECTION_URL set), or `LocalRs256Verifier` (neither set — backward-compatible co-located default). Wired into `http.py` replacing the single `build_local_verifier()` call.

5. **resolve_split_as_settings()**: New config reader in `config.py` for `AGENT_BRAIN_OAUTH_JWKS_URI`, `AGENT_BRAIN_OAUTH_INTROSPECTION_URL`, `AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID`, `AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET`, `AGENT_BRAIN_OAUTH_ISSUER`. Empty/whitespace → None normalization. Keycloak iss format documented (realm path required).

## Tasks Completed

| Task | Name | Commits | Files |
|------|------|---------|-------|
| 1 | JwksTokenVerifier + IntrospectionTokenVerifier | `2050384` (RED) + `2ac84a7` (GREEN) | verifier.py + 2 test files |
| 2 | jti denylist + LocalRs256Verifier check | `66a7d04` (RED) + `2048ebc` (GREEN) | tokens.py + verifier.py + test file |
| 3 | Split-AS config + build_verifier() + http.py wiring | `4a020bc` (RED) + `173d36b` (GREEN) | config.py + verifier.py + __init__.py + http.py + test file |
| QA | Black/Ruff/mypy fixes | `d177c73` | 6 files |

## Acceptance Criteria — Verified

- `class JwksTokenVerifier` and `class IntrospectionTokenVerifier` exist in `verifier.py`
- `asyncio.to_thread(` present in `JwksTokenVerifier.verify_token` (Pitfall 1)
- `PyJWKClient(` with `cache_jwk_set=True` and `lifespan=` present
- `isinstance(aud, str)` present in `IntrospectionTokenVerifier.verify_token` (Pitfall 2)
- `def revoke_by_jti` and `def is_jti_revoked` in `tokens.py`
- `self._revoked_jtis` and `import threading` in `tokens.py`
- `is_jti_revoked(jti)` inside `LocalRs256Verifier.verify_token`
- `def resolve_split_as_settings` and `AGENT_BRAIN_OAUTH_JWKS_URI` in `config.py`
- `def build_verifier` in `verifier.py`
- `JwksTokenVerifier`, `IntrospectionTokenVerifier`, `build_verifier` in `oauth/__init__.__all__`
- `build_verifier(issuer_override=issuer)` in `http.py`; `build_local_verifier(issuer_override=issuer)` count = 0
- `LocalRs256Verifier` class signature unchanged
- All 4 new test files: 26 + 13 + 9 + 12 = 60 tests passing
- `task before-push` exits 0; `agent_brain_mcp.oauth` coverage = 90%

## Coverage Results

```
agent_brain_mcp/oauth/__init__.py         5      0   100%
agent_brain_mcp/oauth/tokens.py          62      4    94%
agent_brain_mcp/oauth/verifier.py       112     10    91%
TOTAL (oauth module):                   565     54    90%
```

Fast tier: 1021 passed, 111 deselected, 0 failures.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PyJWKSetDataError import failure**
- **Found during:** Task 1 GREEN phase
- **Issue:** `from jwt import PyJWKSetDataError` — wrong name; actual class is `PyJWKSetError`
- **Fix:** Updated test to use `PyJWKSetError`
- **Files modified:** `tests/test_oauth_jwks_verifier.py`
- **Commit:** `2ac84a7`

**2. [Rule 2 - Mypy] IntrospectionTokenVerifier type errors**
- **Found during:** QA phase (before-push mypy check)
- **Issue:** `data.get("aud")` returns `object`; `[aud]` produced `list[object]`; `int(data["exp"])` failed mypy call-overload check
- **Fix:** Explicit `isinstance` branches producing `list[str]`; `int(str(exp_raw))` for exp conversion
- **Files modified:** `agent_brain_mcp/oauth/verifier.py`
- **Commit:** `d177c73`

**3. [Rule 2 - Formatting/Linting] Black/Ruff E501 issues**
- **Found during:** QA phase (before-push)
- **Issue:** 5 files with Black format violations; 15 Ruff E501 lines in docstrings/comments
- **Fix:** Black auto-format; manual docstring shortening
- **Files modified:** 5 files
- **Commit:** `d177c73`

## Self-Check: PASSED

All created files exist. All 7 task commits verified in git log.
