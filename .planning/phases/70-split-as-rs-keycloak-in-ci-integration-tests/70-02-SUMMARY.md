---
phase: 70-split-as-rs-keycloak-in-ci-integration-tests
plan: 02
subsystem: agent-brain-mcp/oauth/testing
tags: [oauth, keycloak, split-as-rs, jwks, introspection, ci, github-actions, pytest]
dependency_graph:
  requires:
    - phase: 70-01
      provides: JwksTokenVerifier + IntrospectionTokenVerifier (verifier.py)
  provides:
    - keycloak pytest marker (registered + excluded from fast tier)
    - scripts/keycloak_bootstrap.sh (Admin REST API realm bootstrap + audience mapper)
    - tests/conftest_keycloak.py (keycloak_available + keycloak_token_for_scope + keycloak_access_token fixtures)
    - tests/conftest.py bridge import (fixtures discoverable by pytest)
    - tests/test_oauth_keycloak_e2e.py (SC#1/#2/#3 integration tests)
    - .github/workflows/mcp-keycloak-integration.yml (path-filtered PR CI job)
    - .github/workflows/e2e-nightly.yml (mcp-keycloak-nightly job added)
  affects:
    - 70-03 (scope-boundary tests consume keycloak_token_for_scope factory)
    - CI pipeline (new workflow triggered on agent-brain-mcp/** PRs + nightly)
tech_stack:
  added: []
  patterns:
    - "step-level docker run start-dev for Keycloak in CI (NOT services: block — RESEARCH Pitfall 5/6)"
    - "oidc-audience-mapper as RFC 8707 workaround (Keycloak lacks native Resource Indicators until 26.8)"
    - "conftest_keycloak.py bridge import pattern: re-export fixtures in conftest.py so pytest discovers them"
    - "keycloak_available session fixture for clean skip (mirrors @pytest.mark.postgres convention)"
    - "keycloak_token_for_scope factory fixture for parametrizable ROPC token minting"
key_files:
  created:
    - scripts/keycloak_bootstrap.sh
    - agent-brain-mcp/tests/conftest_keycloak.py
    - agent-brain-mcp/tests/test_oauth_keycloak_e2e.py
    - .github/workflows/mcp-keycloak-integration.yml
  modified:
    - agent-brain-mcp/pyproject.toml
    - agent-brain-mcp/tests/conftest.py
    - .github/workflows/e2e-nightly.yml
key-decisions:
  - "Keycloak started via step-level docker run start-dev (NOT services: block) to reliably support start-dev command override on ubuntu-latest"
  - "Audience scope mapper (oidc-audience-mapper, Included Custom Audience) binds aud claim as RFC 8707 workaround — identical security property to native Resource Indicators"
  - "conftest_keycloak.py fixture file is NOT auto-loaded by pytest; fixtures are re-exported via bridge import in conftest.py"
  - "keycloak_available is session-scoped so the skip fires once per session (not per test)"
  - "keycloak_token_for_scope returns a Callable[[str], str] factory; keycloak_access_token delegates to it (no duplication)"
  - "SC#3 revocation uses POST /protocol/openid-connect/revoke with public client (no secret needed for token owner)"
requirements-completed: [OAUTH-11, OAUTH-12]
duration: 25min
completed: "2026-06-22"
---

# Phase 70 Plan 02: Keycloak CI Integration Tests Summary

**Real Keycloak 26.1 container in CI via step-level docker run start-dev; SC#1 (JWT via JWKS), SC#2 (introspection), SC#3 (revoked-token rejection) expressed as @pytest.mark.keycloak tests with clean-skip when no container is present.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-22T18:43:15Z
- **Completed:** 2026-06-22T19:08:00Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Registered `keycloak` pytest marker in `agent-brain-mcp/pyproject.toml` (alongside e2e/e2e_http/contract/stress) and extended `addopts` exclusion so the fast tier skips container-backed tests cleanly (1021 passed, 115 deselected after addition)
- Created `scripts/keycloak_bootstrap.sh` — idempotent bash script that bootstraps the `agent-brain` realm, public MCP client, audience scope mapper (RFC 8707 workaround), test user, confidential RS client, and 4 agent-brain scopes via the Admin REST API
- Established the `conftest_keycloak.py` bridge import pattern: fixtures in the non-auto-loaded file are re-exported in `tests/conftest.py` with `from tests.conftest_keycloak import ... # noqa: F401` so pytest fixture discovery works
- Created `tests/test_oauth_keycloak_e2e.py` with 4 `@pytest.mark.keycloak` tests proving SC#1 (JWT accepted via JWKS), SC#1-supporting (kid present in JWKS), SC#2 (introspection active:true), and SC#3 (revoked token rejected active:false)
- Created `.github/workflows/mcp-keycloak-integration.yml` — path-filtered PR workflow (triggers on `agent-brain-mcp/**`) running Keycloak 26.1 via step-level docker run + realm bootstrap + `task mcp:keycloak`
- Added `mcp-keycloak-nightly` job to `e2e-nightly.yml` with the same step-level Keycloak start-dev pattern while preserving the existing `e2e-cli` job and cron schedule

## Task Commits

Each task was committed atomically:

1. **Task 1: Register keycloak marker + realm bootstrap script** - `91cc5c5` (feat)
2. **Task 2: Keycloak fixtures + conftest bridge + SC#1/#2/#3 e2e tests** - `4508156` (feat)
3. **Task 3: Keycloak step-level docker-run CI job + nightly trigger** - `b79a2c6` (feat)

## Files Created/Modified

- `agent-brain-mcp/pyproject.toml` - Added keycloak marker + extended addopts exclusion
- `scripts/keycloak_bootstrap.sh` - Admin REST API realm bootstrap (RFC 8707 deviation documented)
- `agent-brain-mcp/tests/conftest_keycloak.py` - Keycloak-tier fixtures (available/access_token/token_for_scope)
- `agent-brain-mcp/tests/conftest.py` - Bridge import for keycloak fixture discovery
- `agent-brain-mcp/tests/test_oauth_keycloak_e2e.py` - SC#1/#2/#3 Keycloak-backed e2e tests
- `.github/workflows/mcp-keycloak-integration.yml` - New path-filtered PR workflow
- `.github/workflows/e2e-nightly.yml` - Added mcp-keycloak-nightly job

## Decisions Made

- **step-level docker run**: GitHub Actions service containers do not reliably support command overrides; Keycloak's default `start` mode requires TLS and fails health checks. Using step-level `docker run ... start-dev` is the only reliable approach (RESEARCH Pitfall 5/6).
- **oidc-audience-mapper**: Keycloak lacks native RFC 8707 Resource Indicators until version 26.8 (unreleased). The audience scope mapper binds `aud == AGENT_BRAIN_OAUTH_RESOURCE` in issued JWTs — identical security property. Deviation documented in script header comment.
- **conftest bridge pattern**: `conftest_keycloak.py` keeps keycloak concerns isolated; the bridge import in `conftest.py` is the minimal non-invasive way to make pytest discover the fixtures.
- **session-scoped keycloak_available**: Skips fire once per session rather than per test, avoiding repeated skip messages.
- **Callable[[str], str] return type**: `keycloak_token_for_scope` returns a properly typed factory; `keycloak_access_token` delegates to it to avoid code duplication while exporting both names.
- **RFC 7009 revocation for SC#3**: POST to `/protocol/openid-connect/revoke` with the public client (no secret required since token owner is the same client) is the correct Keycloak revocation path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Typing] Replaced `object` return type with `Callable[[str], str]`**
- **Found during:** Task 2 verification (mypy check)
- **Issue:** Plan spec used `object` as the return annotation for `keycloak_token_for_scope`; mypy flagged unused `type: ignore` comments and `no-any-return` in the dependent fixture
- **Fix:** Added `from collections.abc import Callable`; changed return type to `Callable[[str], str]`; updated `keycloak_access_token` to call directly without cast
- **Files modified:** `tests/conftest_keycloak.py`, `tests/test_oauth_keycloak_e2e.py`
- **Verification:** `mypy tests/conftest_keycloak.py tests/test_oauth_keycloak_e2e.py` → Success

**2. [Rule 2 - Formatting/Linting] Ruff I001 import order in conftest.py**
- **Found during:** Task 2 verification (ruff check)
- **Issue:** Bridge import was placed between `import os` and the stdlib block; ruff I001 requires sorted/grouped imports
- **Fix:** Moved bridge import after all stdlib + third-party imports
- **Files modified:** `agent-brain-mcp/tests/conftest.py`
- **Verification:** `ruff check tests/conftest.py` → All checks passed

**3. [Rule 2 - Formatting/Linting] E501 line-length violations in conftest_keycloak.py and test file**
- **Found during:** Task 2 verification (ruff check)
- **Issue:** 4 lines exceeded the 88-char limit (docstring text + pytest.skip message + assert string)
- **Fix:** Wrapped long strings across multiple lines (string continuation)
- **Files modified:** `tests/conftest_keycloak.py`, `tests/test_oauth_keycloak_e2e.py`
- **Verification:** `ruff check` → All checks passed; Black reformatted assertion grouping

---

**Total deviations:** 3 auto-fixed (1 typing, 2 formatting/linting)
**Impact on plan:** All auto-fixes required for type-safety and code quality. No scope creep. Plan logic executed exactly as specified.

## Issues Encountered

None — plan executed with only minor type annotation and linting adjustments.

## Next Phase Readiness

- `keycloak_token_for_scope` factory fixture is ready for 70-03 scope-boundary tests (can mint read-only tokens via `scope="openid agent-brain:read"`)
- `keycloak_available` session fixture provides the skip gate for all keycloak-tier tests
- Bootstrap script creates all 4 agent-brain scopes needed by 70-03
- CI workflow is path-filtered and will run automatically on MCP/OAuth PRs

---
*Phase: 70-split-as-rs-keycloak-in-ci-integration-tests*
*Completed: 2026-06-22*
