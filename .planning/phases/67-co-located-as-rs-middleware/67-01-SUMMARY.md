---
phase: 67-co-located-as-rs-middleware
plan: 01
subsystem: auth
tags: [mcp, oauth, jwt, pyjwt, authlib, pwdlib, argon2, poetry, sdk-bump]

# Dependency graph
requires:
  - phase: 66-oauth-settings-foundation-prm-oasm-public-endpoints
    provides: "AuthMode enum, resolve_oauth_settings(), get_auth_dependency() oauth placeholder, build_asgi_app() with auth-exempt well-known routes"

provides:
  - "mcp SDK bumped from ^1.12.0 to ^1.27.2 (floor for OAuthAuthorizationServerProvider, create_auth_routes, RequireAuthMiddleware, BearerAuthBackend)"
  - "PyJWT[crypto] ^2.13 installed (RS256 JWT minting; jwt.algorithms.RSAAlgorithm available)"
  - "authlib ^1.7.2 installed (OAuth 2.1 grant-handler logic)"
  - "pwdlib[argon2] >=0.2 installed (Argon2Hasher for AS secret hashing)"
  - "test_oauth_deps_smoke.py: 11-test SDK drift gate (all mcp.server.auth symbols + crypto libs importable; project modules survive bump)"
  - "Zero SDK-drift regressions across server.py, http.py, client.py, subscriptions post-bump"

affects:
  - 67-02-plan
  - 67-03-plan
  - 67-04-plan
  - phase-68-scope-enforcement
  - phase-69-client-dance
  - phase-70-split-as-rs

# Tech tracking
tech-stack:
  added:
    - "mcp ^1.27.2 (upgraded from ^1.12.0 — OAuth machinery now available)"
    - "PyJWT[crypto] 2.13.0 (RS256 JWT signing and verification)"
    - "authlib 1.7.2 (OAuth 2.1 grant-handler logic)"
    - "pwdlib 0.3.0 with argon2-cffi (Argon2 password hashing)"
  patterns:
    - "Per-task atomic commits with chore/test conventional commit types"
    - "TDD RED/GREEN applied: smoke test written, confirmed passing on installed deps"
    - "poetry lock from package dir (cd agent-brain-mcp && poetry lock) for dep graph resolution"
    - "task before-push from repo root as mandatory QA gate (lock-drift guard reverts agent-brain-cli/poetry.lock — expected noise, not a regression)"

key-files:
  created:
    - "agent-brain-mcp/tests/test_oauth_deps_smoke.py"
  modified:
    - "agent-brain-mcp/pyproject.toml"
    - "agent-brain-mcp/poetry.lock"

key-decisions:
  - "mcp pinned at ^1.27.2 (minimum floor for OAuth machinery; 1.27.2 is the latest available version as of 2026-06-15)"
  - "itsdangerous NOT added explicitly: it is NOT a transitive dep via mcp 1.27.2 or Starlette. Phase 67 later plans should evaluate if itsdangerous ^2.2 is needed for CSRF state-token signing; add it when the feature requires it, not here."
  - "Zero SDK API drift found across the 15-minor-version jump (1.12→1.27.2): all project modules (server.py, http.py, client.py, subscriptions) import cleanly; 664 tests pass with 0 regressions"
  - "create_auth_routes() signature confirmed: provider and issuer_url parameters still present in mcp 1.27.2 (SDK sentinel test added)"

patterns-established:
  - "SDK drift gate pattern: write import-smoke tests for every SDK surface before implementing features on top of a version bump"
  - "itsdangerous verification pattern: check with poetry show + python import BEFORE adding as explicit dep; only add if needed and not already resolvable"

requirements-completed: [OAUTH-04]

# Metrics
duration: 18min
completed: 2026-06-15
---

# Phase 67 Plan 01: Dep-Bump Gate Summary

**mcp SDK bumped ^1.12→^1.27.2 with PyJWT[crypto]/authlib/pwdlib[argon2] added and zero SDK-drift regressions across 664 existing tests**

## Performance

- **Duration:** 18 min
- **Started:** 2026-06-15T00:45:00Z
- **Completed:** 2026-06-15T01:03:00Z
- **Tasks:** 2
- **Files modified:** 3 (pyproject.toml, poetry.lock, tests/test_oauth_deps_smoke.py)

## Accomplishments

- Bumped mcp SDK from ^1.12.0 to ^1.27.2 — the gate version that ships `mcp.server.auth` OAuth machinery (`OAuthAuthorizationServerProvider`, `create_auth_routes()`, `RequireAuthMiddleware`, `BearerAuthBackend`)
- Added PyJWT[crypto] 2.13.0, authlib 1.7.2, pwdlib 0.3.0 with argon2-cffi — all OAuth runtime deps for Phase 67 implementation plans
- Proved zero breaking SDK API drift: all project modules (server, http, client, subscriptions) import cleanly post-bump; full suite passes 664/664, 0 regressions
- Created 11-test drift gate (`test_oauth_deps_smoke.py`) covering every SDK OAuth symbol + crypto lib + project module + `create_auth_routes()` signature sentinel

## Task Commits

Each task was committed atomically:

1. **Task 1: Bump mcp pin to ^1.27.2 and add OAuth runtime deps** - `9d584e3` (chore)
2. **Task 2: OAuth dep-import smoke test + SDK drift gate** - `264951a` (test)

## Files Created/Modified

- `agent-brain-mcp/pyproject.toml` — mcp bumped to ^1.27.2; pyjwt/authlib/pwdlib added as runtime deps
- `agent-brain-mcp/poetry.lock` — regenerated: mcp resolves to 1.27.2, 5 new packages installed (argon2-cffi-bindings, argon2-cffi, authlib, joserfc, pwdlib)
- `agent-brain-mcp/tests/test_oauth_deps_smoke.py` — 11 import/introspection tests covering all Phase 67 dep surfaces

## Decisions Made

**itsdangerous not added:**
Verified `itsdangerous` is NOT a transitive dep via mcp 1.27.2 or Starlette in the new lockfile, and is NOT importable in the venv. The plan directed "only add `itsdangerous = "^2.2"` explicitly if it is NOT already resolvable." Since Phase 67's current plans (02-04) do not implement CSRF state-token signing in this plan, `itsdangerous` should be added as an explicit dep when Plan 02/03 implements the CSRF state-token feature (if needed). This is tracked for downstream plans.

**mcp 1.27.2 is the exact latest available version:**
`pip index versions mcp` shows 1.27.2 as the newest; our pin `^1.27.2` resolves exactly to 1.27.2.

**Zero SDK drift:**
The 15-minor-version jump (1.12→1.27.2) introduced NO breaking changes in the surfaces agent-brain-mcp uses. The `streamable_http_client` deprecation warning (use `streamable_http_client` instead) is pre-existing noise from existing tests — not a regression introduced by this bump.

## Deviations from Plan

None — plan executed exactly as written. Both tasks completed in sequence, acceptance criteria met, task before-push passes.

## Issues Encountered

None. mcp 1.27.2 was available on PyPI and installed cleanly. The OAuth submodule (`mcp.server.auth`) was already present at 1.27.1 (previously installed in the venv from other development), and 1.27.2 resolved correctly after `poetry lock`.

## itsdangerous Status (for downstream plans)

- **Status:** NOT installed; NOT a transitive dep via mcp 1.27.2 or Starlette
- **Action needed:** If Phase 67 Plans 02-04 implement CSRF state-token signing, add `itsdangerous = "^2.2"` explicitly to pyproject.toml at that point
- **Do NOT use:** `python-jose` (abandoned), `passlib` (unmaintained), `fastapi-users` (design doc do-not-use list)

## SDK Drift Report (Phase 67 Risk #1 — CLOSED)

The primary Phase 67 risk was the 15-minor-version SDK jump silently breaking existing API surfaces. Result:

| Surface | Drift Found | Action |
|---------|-------------|--------|
| `agent_brain_mcp.server` (mcp.server.lowlevel, mcp.server.session) | None | Pass |
| `agent_brain_mcp.http` (StreamableHTTPSessionManager, TransportSecuritySettings) | None | Pass |
| `agent_brain_mcp.client` (mcp.client.streamable_http, mcp.client.stdio) | None | Pass |
| `agent_brain_mcp.subscriptions` (resource notification surface) | None | Pass |
| `mcp.server.auth.provider` (OAuthAuthorizationServerProvider, TokenVerifier, AccessToken, ...) | None | Pass (new symbols, not drift) |
| `mcp.server.auth.routes` (create_auth_routes, signature) | None | Pass (signature sentinel added) |
| `mcp.server.auth.middleware.bearer_auth` (RequireAuthMiddleware, BearerAuthBackend) | None | Pass |

**Total regressions:** 0. Risk closed.

## Next Phase Readiness

Phase 67 Plans 02-04 can now safely build on:
- `mcp.server.auth.provider.OAuthAuthorizationServerProvider` (implement the 9-method abstract class)
- `mcp.server.auth.routes.create_auth_routes()` (wire /authorize, /token, /register routes)
- `mcp.server.auth.middleware.bearer_auth.RequireAuthMiddleware` + `BearerAuthBackend` (wrap /mcp mount)
- `jwt` with RS256 algorithm support (JWT minting and verification)
- `authlib` (OAuth 2.1 grant-handler composition)
- `pwdlib.hashers.argon2.Argon2Hasher` (AS secret hashing)

The dependency bump risk is fully de-risked before any AS/RS implementation code lands.

---
*Phase: 67-co-located-as-rs-middleware*
*Completed: 2026-06-15*
