---
phase: 70-split-as-rs-keycloak-in-ci-integration-tests
plan: 03
subsystem: agent-brain-mcp/oauth
tags: [oauth, keycloak, split-as-rs, e2e, coverage-gate, ci, docs, spec-verification]
dependency_graph:
  requires:
    - phase: 70-01
      provides: JwksTokenVerifier + IntrospectionTokenVerifier + build_verifier()
    - phase: 70-02
      provides: keycloak pytest marker + conftest_keycloak.py fixtures + CI workflow
  provides:
    - SC#4 Keycloak E2E tests (test_full_oauth_dance_tool_call, test_token_refresh_path,
        test_scope_boundary_403) in test_oauth_keycloak_e2e.py
    - task mcp:oauth-cov (85% local soft / 90% CI hard with COV_FAIL_UNDER var)
    - task mcp:keycloak (runs @pytest.mark.keycloak suite)
    - mcp-keycloak-integration.yml binding 90% oauth-module coverage gate (SC#5 DoD)
    - docs/plans/2026-06-14-mcp-v4-oauth-design.md Phase 70 Spec Re-Verification note
    - agent-brain-mcp/docs/SPLIT_AS_RS.md operator doc
  affects:
    - CI pipeline (binding 90% gate in mcp-keycloak-integration.yml)
    - v10.4 milestone DoD (SC#4 + SC#5 closed)
tech_stack:
  added: []
  patterns:
    - "In-process ASGI TestClient pattern for keycloak E2E (no subprocess; oauth
      env vars set before build_asgi_app() call so JwksTokenVerifier picks up live
      Keycloak JWKS URI)"
    - "try/finally env var cleanup in keycloak E2E tests (no monkeypatch needed)"
    - "Taskfile vars block with COV_FAIL_UNDER default for local-vs-CI coverage threshold"
    - "Step-level coverage gate after keycloak tests in CI workflow (authoritative 90%)"
key_files:
  created:
    - agent-brain-mcp/docs/SPLIT_AS_RS.md
  modified:
    - agent-brain-mcp/tests/test_oauth_keycloak_e2e.py
    - agent-brain-mcp/Taskfile.yml
    - .github/workflows/mcp-keycloak-integration.yml
    - docs/plans/2026-06-14-mcp-v4-oauth-design.md
decisions:
  - "SC#4 Keycloak tests use in-process TestClient (build_asgi_app() + JwksTokenVerifier
    pointing at live Keycloak JWKS URI) rather than spawning a subprocess — avoids
    fake-backend complexity and tests the exact auth middleware chain"
  - "try/finally env var cleanup pattern (no monkeypatch fixture) — keycloak tests are
    function-scoped and env vars must be cleaned up to avoid leaking into other tests"
  - "COV_FAIL_UNDER task var defaults to 85 locally; CI passes 90 — Pitfall 4 from
    RESEARCH (local fast tier skips keycloak paths, CI includes them for full picture)"
  - "spec re-verification performed via context7 /modelcontextprotocol/modelcontextprotocol;
    SEP-2575 confirms per-request auth is required; RequireAuthMiddleware forward-compatible"
  - "No public /revoke endpoint shipped in Phase 70 — deferred to v10.4.1"
metrics:
  duration: 35 minutes
  completed_date: "2026-06-22"
  tasks_completed: 3
  files_created: 1
  files_modified: 4
---

# Phase 70 Plan 03: SC#4 Keycloak E2E + Coverage Gate + Operator Docs Summary

**One-liner:** SC#4 Keycloak RS path tests (tool call, refresh, scope-boundary 403), binding 90% oauth-module coverage gate in CI (SC#5 DoD), Phase 70 live-spec re-verification discharged, and operator split-AS/RS deployment doc with RFC 8707 Keycloak workaround.

## What Was Built

### Task 1: SC#4 Keycloak E2E Suite

Three new `@pytest.mark.keycloak` tests added to `test_oauth_keycloak_e2e.py` (file now covers SC#1-4):

1. **`test_full_oauth_dance_tool_call`** (SC#4 core): builds the full ASGI app in-process
   with `AGENT_BRAIN_OAUTH_JWKS_URI` pointing at the live Keycloak realm certs endpoint.
   Sends a `tools/call` (get_corpus_status) request with a Keycloak JWT as Bearer. The
   `JwksTokenVerifier` fetches the real JWKS and validates the token — auth layers must
   not reject the call (not 401/403). Docstring references Phase 69's
   `test_oauth_client_dance_e2e.py` (TestSC1DanceAndRetry) as the PKCE-dance leg.

2. **`test_token_refresh_path`** (SC#4 refresh): performs a real Keycloak token refresh
   via `POST /protocol/openid-connect/token` (grant_type=refresh_token), then verifies
   the refreshed JWT passes the RS auth layers.

3. **`test_scope_boundary_403`** (SC#4 scope boundary — headline OAUTH-06 cross-check):
   mints a read-only token via `keycloak_token_for_scope("openid agent-brain:read")`,
   calls `clear_cache` (admin tool requiring `agent-brain:admin`), and asserts HTTP 403
   with `WWW-Authenticate: Bearer error="insufficient_scope"` (NOT 401).

All tests skip cleanly without a container (keycloak_available session fixture) and are
excluded from the fast tier. Total keycloak tests: 7 (4 from Plan 02 + 3 new).

### Task 2: Coverage Gate Task Targets and CI Wiring

**Taskfile.yml** — two new bare targets (root `includes: mcp:` aliases them as
`task mcp:oauth-cov` / `task mcp:keycloak`):

- `oauth-cov`: runs `--cov=agent_brain_mcp.oauth --cov-fail-under={{.COV_FAIL_UNDER | default "85"}}`.
  Default COV_FAIL_UNDER=85 locally (Pitfall 4 — keycloak paths skipped without container).
  CI passes COV_FAIL_UNDER=90. Documents that the BINDING 90% gate runs authoritatively
  in the CI Keycloak job.
- `keycloak`: runs `pytest {{.TEST_DIR}} -v -m keycloak`. deps: [install].

**mcp-keycloak-integration.yml** — added "OAuth module coverage gate (90% CI hard — SC#5 DoD)"
step after the existing Keycloak integration test step. Runs the full suite
`-m 'not e2e and not contract and not stress'` (includes keycloak-marked tests) with
`--cov=agent_brain_mcp.oauth --cov-fail-under=90`. YAML validated; step has a COMMENT
marking it as the binding SC#5 DoD gate.

### Task 3: Spec Re-Verification + Operator Docs

**Design doc** — appended "Phase 70 Spec Re-Verification (2026-06-22)" section under
the "2026-07-28 RC Staleness Acknowledgement" section:
- RC status: published blog post + SEP-2575 doc; normative authorization spec not yet
  updated (RC target date 2026-07-28 not yet passed as of 2026-06-22)
- SEP-2575 confirms: "each request must be independently authenticated and authorized"
  → RequireAuthMiddleware per-request validation is stateless by nature, forward-compatible
- mcp SDK `^1.27.2` — no breaking auth API changes found; no bump required for Phase 70
- Conclusion: no auth-logic change required; Phase 70 obligation CLOSED

**SPLIT_AS_RS.md** — new operator doc covering:
- Shape A (co-located AS+RS) vs Shape B (split AS/RS) deployment shapes
- Full env var table: AGENT_BRAIN_OAUTH_RESOURCE/ISSUER/JWKS_URI/INTROSPECTION_URL +
  CLIENT_ID/SECRET; verifier selector precedence (JWKS_URI > INTROSPECTION_URL > LocalRs256)
- Keycloak configuration section with RFC 8707 deviation (audience scope mapper workaround)
- Pitfall 7: issuer must include full realm path (`/realms/agent-brain`)
- Revocation behavior (split: introspection active:false; co-located: jti denylist;
  no public /revoke in this phase)
- Token validation steps 1-7 with 403 vs 401 distinction

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | SC#4 Keycloak E2E suite | `08dd178` | test_oauth_keycloak_e2e.py (+3 tests) |
| 2 | Coverage gate + CI wiring | `a52d834` | Taskfile.yml, mcp-keycloak-integration.yml |
| 3 | Spec re-verification + operator docs | `c36dd21` | design doc, SPLIT_AS_RS.md |

## Acceptance Criteria — Verified

- `test_full_oauth_dance_tool_call`, `test_token_refresh_path`, `test_scope_boundary_403` in test_oauth_keycloak_e2e.py
- `test_scope_boundary_403` uses `keycloak_token_for_scope("openid agent-brain:read")` and asserts `403` + `insufficient_scope`
- `test_full_oauth_dance_tool_call` references `AGENT_BRAIN_OAUTH_JWKS_URI` and `test_oauth_client_dance_e2e` in docstring
- `pytest -m keycloak tests/test_oauth_keycloak_e2e.py --collect-only -q` collects 7 tests cleanly
- Fast tier (`-m 'not e2e and not e2e_http and not contract and not stress and not keycloak'`) excludes all 7
- Taskfile.yml contains `oauth-cov` and `keycloak` targets
- `oauth-cov` contains `--cov=agent_brain_mcp.oauth` and `--cov-fail-under`
- `keycloak` target contains `-m keycloak`
- `task --list` (root) shows `mcp:oauth-cov` and `mcp:keycloak`
- `mcp-keycloak-integration.yml` contains `--cov=agent_brain_mcp.oauth` and `--cov-fail-under=90`
- `mcp-keycloak-integration.yml` is valid YAML (python3 yaml.safe_load exits 0)
- Design doc contains `Phase 70 Spec Re-Verification` with date and RequireAuthMiddleware per-request conclusion
- `SPLIT_AS_RS.md` exists and contains `AGENT_BRAIN_OAUTH_JWKS_URI`, `AGENT_BRAIN_OAUTH_INTROSPECTION_URL`, `AGENT_BRAIN_OAUTH_ISSUER`
- `SPLIT_AS_RS.md` documents RFC 8707 Keycloak deviation (audience scope mapper) and references `keycloak_bootstrap.sh`
- `SPLIT_AS_RS.md` documents revocation (introspection active:false + jti denylist) and no public /revoke
- `task before-push` exits 0: 1021 passed, 118 deselected
- `task pr-qa-gate` exits 0: 91% overall coverage (80% gate)
- `task mcp:oauth-cov` passes 85% local soft gate: 90.53% oauth module coverage

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed incorrect `_config_mod._signing_key_singleton` reset**
- **Found during:** Task 1 — mypy check on test_oauth_keycloak_e2e.py
- **Issue:** `_build_keycloak_app_client()` attempted to reset `agent_brain_mcp.config._signing_key_singleton` but that attribute does not exist on config.py — it lives on `agent_brain_mcp.oauth.keys`. Since these tests use `JwksTokenVerifier` (JWKS_URI path, not the local RS256 keypair), no singleton reset is needed.
- **Fix:** Removed the `import agent_brain_mcp.config as _config_mod` line and the `_config_mod._signing_key_singleton = None` assignment. `build_asgi_app()` reads env vars at call time via `config.py` without any cached singleton for the split-AS path.
- **Files modified:** `agent-brain-mcp/tests/test_oauth_keycloak_e2e.py`
- **Commit:** `08dd178`

**2. [Rule 2 - Linting] Ruff I001 import order in test file**
- **Found during:** Task 1 — ruff check
- **Issue:** Local imports inside `_build_keycloak_app_client()` were in non-canonical order (stdlib → from-import ordering violation)
- **Fix:** `ruff check --fix` auto-resolved
- **Files modified:** `agent-brain-mcp/tests/test_oauth_keycloak_e2e.py`
- **Commit:** `08dd178`

## Self-Check: PASSED

All created/modified files exist and all task commits verified.
