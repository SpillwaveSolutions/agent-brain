# Phase 70: Split AS/RS + Keycloak-in-CI + Integration Tests - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

> The user delegated these decisions ("I trust your judgement"). Every decision below
> is grounded in the locked design doc (`docs/plans/2026-06-14-mcp-v4-oauth-design.md`),
> the ROADMAP Phase 70 success criteria (SC#1–5), and the existing CI/test conventions
> (the `postgres` service-container + opt-in `@pytest.mark.*` skip pattern). They are
> reasonable defaults — the planner may revisit any of them, but downstream agents
> should NOT re-ask the user.

<domain>
## Phase Boundary

Validate the **split AS/RS topology** (Agent Brain = RS only; external IdP = AS) end-to-end
against a **real Keycloak container in CI**, close the OAuth DoD with **token introspection
(RFC 7662)** and **revocation (RFC 7009) support**, and enforce a **≥90% coverage gate on
`agent_brain_mcp/oauth/`**.

This is the FINAL phase of milestone v10.4 (MCP v4: OAuth 2.1). It delivers:
- `JwksTokenVerifier` (PyJWKClient-backed) wired in by config in `http.py` — the seam left
  by Phase 67's `LocalRs256Verifier`.
- An introspection verifier path for opaque-token / external-AS deployments.
- Revocation enforcement (no new public endpoint — see Revocation decision).
- The full SC#4 E2E integration suite against the official MCP SDK client.
- The 90% oauth-module coverage gate that blocks the milestone from shipping.

**Out of scope:** New OAuth grant types, a `/revoke` public endpoint (deferred to v10.4.1
per design doc), DPoP, additional IdPs beyond Keycloak, audit-log middleware. The co-located
AS+RS machinery (Phases 66–69) is DONE — Phase 70 adds the split-topology strategy + the
CI/test infrastructure to prove the whole milestone.

</domain>

<decisions>
## Implementation Decisions

### Keycloak-in-CI placement (two-tier, path-filtered + nightly)
- **Fast tier (every PR, local):** mock-JWKS / mock-introspection backed tests run in the
  default `task before-push` suite and on every PR in `pr-qa-gate.yml`. No container.
- **Integration tier (real Keycloak container):** a dedicated CI job runs the real
  Keycloak ≥22 container as a GitHub Actions **service container** (mirroring the existing
  `postgres` service in `pr-qa-gate.yml`). It is triggered:
  - on PRs whose changes touch `agent-brain-mcp/**` (path filter — keeps unrelated PRs fast), AND
  - nightly via `e2e-nightly.yml` (cron + `workflow_dispatch`) for the full matrix.
- **Why:** the existing repo pattern is "service container for the heavy dependency, skip
  locally, run in CI." SC#1 only requires the container to "run in CI on `ubuntu-latest`" —
  it does NOT require it on every PR. Path-filtering keeps median PR latency/cost low while
  guaranteeing the split-AS path is gated whenever MCP/OAuth code changes.

### Revocation scope (enforcement-side; NO new public endpoint)
- Reconciles ROADMAP SC#3 ("revocation is supported") with design-doc Deferred §5
  ("RFC 7009 `/revoke` endpoint is not a normative MUST — consider for v10.4.1").
- "Supported" is delivered exactly as SC#3 phrases it ("either via introspection or an
  in-memory revocation list"):
  - **Split / opaque-token path:** revocation is honored **via introspection** — a token
    the IdP has revoked returns `active: false`, which the RS already maps to 401 (this is
    the SC#2 mechanism; revocation rides on it for free).
  - **Co-located path:** an **in-memory revocation list** (a `jti` / token-id denylist)
    checked by the verifier; a revoked token is rejected on next use.
- **We do NOT ship a public `POST /revoke` (RFC 7009) endpoint in this phase.** That is the
  v10.4.1 admin-UX item per the design doc. The DoD is met by enforcement, not by exposing
  a new route.

### Coverage gate wiring (dedicated per-module gate, measured in the CI integration job)
- Add a dedicated gate: `--cov=agent_brain_mcp.oauth --cov-fail-under=90`, surfaced as a
  task target (e.g. `task mcp:oauth-cov`) and wired so it BLOCKS the milestone independent
  of the repo-wide 50% coverage floor.
- **Authoritative measurement happens in the CI integration job** (the one with the Keycloak
  container), because Keycloak-dependent tests are skipped locally and would otherwise leave
  coverage holes that fail the 90% gate off-CI. Locally, the mock-backed fast tier should
  still cover the bulk of `oauth/` so the dev loop stays green; document that the binding
  90% gate is the CI job, not `task before-push` on a laptop.
- The planner should audit current `oauth/` coverage early and budget tests to close the gap
  (10 source modules already exist: verifier, provider, tokens, scopes, registration, keys,
  oauth_client, oauth_handlers, token_storage, __init__).

### Fast vs real-IdP test split (mirror the `@pytest.mark.postgres` convention)
- Introduce an opt-in **`keycloak` pytest marker** (register in `agent-brain-mcp/pyproject.toml`
  alongside `e2e`/`e2e_http`/`stress`) for tests that require the live container; they skip
  cleanly without it (same ergonomics as `postgres`/`e2e`).
- **Mock tier covers** (fast, every PR, local): `JwksTokenVerifier` unit behavior — JWKS fetch
  via an in-process mock `/jwks.json`, 5-min TTL caching, `kid`-miss on-demand refresh, `aud`
  (RFC 8707) validation, `exp`/`nbf` with 30s leeway, `iss` check; introspection-verifier
  logic against a mock introspection endpoint (`active:true`/`active:false`/`aud`).
- **Real-Keycloak tier covers** (slow, CI/nightly): actual Keycloak-issued JWT accepted via
  cached JWKS (SC#1); RFC 8707 Resource Indicators enabled per-client in the realm; opaque-token
  introspection round-trip (SC#2); and the full **SC#4 E2E flow against the official MCP
  Python SDK client**: 401 challenge → PRM discovery → OASM discovery → PKCE dance →
  authorized tool call → token-refresh path → scope boundary (read-only token + admin tool → 403).
- A reproducible Keycloak realm fixture (realm JSON import: client with Resource Indicators +
  the 4 agent-brain scopes) seeds the container deterministically.

### Live-spec re-verification obligation (carried from Phase 65 / design doc)
- The design doc (Spec Version Citation §, line ~58) makes Phase 70 responsible for
  **re-verifying the live MCP Authorization spec before finalizing** and acknowledging the
  **2026-07-28 RC** (MCP-goes-stateless / no-initialize handshake) status. Planner must
  include a research/verification task using context7 / WebFetch against the live spec.

### Claude's Discretion
- Exact Keycloak image tag/version (≥22), realm-import JSON shape, and container health-check.
- Whether the introspection verifier is a separate class or a mode of `JwksTokenVerifier`.
- Revocation-list data structure (set vs TTL cache) and where it's checked in the verify chain.
- Test file organization (extend existing `test_oauth_*.py` vs new `test_oauth_split_as_*.py` /
  `test_oauth_keycloak_e2e.py`).
- Whether the integration job lives in `pr-qa-gate.yml` (new job) or a new dedicated workflow.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### OAuth design contract (PRIMARY — governs all of Phases 66–70)
- `docs/plans/2026-06-14-mcp-v4-oauth-design.md` — the signed design doc. Phase 70 specifics:
  - §"Deployment Shape B: Split AS / RS (Phase 70)" (~line 691) — `JwksTokenVerifier`,
    PyJWKClient 5-min TTL + `kid`-miss refresh, `IntrospectionTokenVerifier` (RFC 7662),
    leeway=30s, Keycloak 22+ Resource Indicators per-client.
  - §"Token Validation on `/mcp`" (~line 311) — the 6-check order JWKS verification reuses.
  - §"Token Termination Data Flow" / "Termination Contract (OAUTH-08)" (~line 327/364) — the
    integration test that asserts the OAuth token is NOT forwarded upstream (confused-deputy).
  - §"Spec Version Citation" → "2026-07-28 RC Staleness Acknowledgement" (~line 45/58) —
    Phase 70's live-spec re-verification obligation.
  - §"Deferred Items" §5 (~line 741) — RFC 7009 `/revoke` endpoint deferral (the SC#3 tension).
  - §"Scope-to-Tool Mapping" (~line 400) — 4 scopes × 16 tools for the SC#4 scope-boundary test.

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — OAUTH-11 (split AS/RS, Keycloak-in-CI, JWKS) + OAUTH-12
  (introspection RFC 7662 + revocation RFC 7009). Lines 32–33, 86–87, 102.
- `.planning/ROADMAP.md` — Phase 70 goal + SC#1–5 (lines 166–176). SC#5 is the 90% DoD gate.
- Issue [#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188) — MCP v4 milestone.

### Prior-phase context (the seam Phase 70 plugs into)
- `.planning/phases/67-co-located-as-rs-middleware/67-CONTEXT.md` — RS verification middleware
  the verifier swap targets.
- `.planning/phases/65-oauth-design-doc-security-review-gate/65-CONTEXT.md` — locked library
  picks (`PyJWT[crypto] ^2.13`, `PyJWKClient`), scope design, deployment shapes.

### Existing code (verifier seam + CI patterns)
- `agent-brain-mcp/agent_brain_mcp/oauth/verifier.py` — `LocalRs256Verifier` + the documented
  "Phase 70 verifier seam" (stable `verify_token` signature; swap by config in `http.py`).
- `agent-brain-mcp/agent_brain_mcp/http.py` — Starlette app; where the verifier is selected and
  well-known/auth-exempt routes mount.
- `.github/workflows/pr-qa-gate.yml` — the `postgres` service-container pattern to mirror for Keycloak.
- `.github/workflows/e2e-nightly.yml` — cron + `workflow_dispatch` nightly harness for the full run.
- `agent-brain-mcp/pyproject.toml` §`markers` (~line 108) — opt-in marker convention to extend with `keycloak`.

### Live spec (re-verify at planning/authoring time)
- MCP Authorization spec **2025-11-25** (baseline) + check **2026-07-28 RC** status via
  context7 / WebFetch against the live modelcontextprotocol spec.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LocalRs256Verifier` / `build_local_verifier()` in `oauth/verifier.py` — stable
  `verify_token(token) -> AccessToken | None` seam; `JwksTokenVerifier` implements the same
  protocol and swaps in via `http.py` config. No changes to existing verifier code/tests.
- `mcp >= 1.27.2` SDK ships `IntrospectionTokenVerifier`, `RequireAuthMiddleware`,
  `BearerAuthBackend`, and an `OAuthClientProvider` usable as the SC#4 E2E client driver.
- `PyJWT[crypto] ^2.13` + bundled `PyJWKClient` (already recorded as the locked picks) — JWKS
  cache with TTL + `kid`-miss refresh comes from the library, not hand-rolled.
- The 14 existing `test_oauth_*.py` files (PKCE, confused-deputy, RS middleware, RS verifier,
  metadata docs, mode exclusion, client dance E2E, CIMD SSRF, token mint, etc.) establish the
  fixtures/patterns the split-AS + Keycloak tests extend.
- `_tool_matrix.py` — the 16-tool single source of truth backing the SC#4 scope-boundary assertion.

### Established Patterns
- **Heavy-dependency-in-CI pattern:** `pr-qa-gate.yml` runs PostgreSQL as a service container;
  `@pytest.mark.postgres` tests skip locally and run in CI with `DATABASE_URL` set. Keycloak
  mirrors this exactly (new `keycloak` marker + service container).
- **Opt-in slow-test markers gated behind task targets:** `e2e`, `e2e_http`, `stress` are
  excluded from `task before-push` and run via dedicated `task mcp:*` targets — the Keycloak
  integration suite follows the same opt-in ergonomics.
- **Coverage gate:** repo-wide floor is 50% (PR CI). Phase 70 adds a stricter per-module 90%
  gate scoped to `agent_brain_mcp.oauth` — additive, not a change to the global floor.

### Integration Points
- `http.py` verifier selection (`AGENT_BRAIN_AUTH=oauth` + split vs co-located config) — where
  `JwksTokenVerifier` activates.
- `agent-brain-mcp/pyproject.toml` `[tool.pytest.ini_options].markers` — register `keycloak`.
- `Taskfile.yml` (+ mcp includes) — new `task mcp:oauth-cov` / `task mcp:keycloak` targets.
- `.github/workflows/` — Keycloak service-container job (path-filtered PR + nightly).

</code_context>

<specifics>
## Specific Ideas

- The DoD is closed by **enforcement + proof**, not by adding API surface: revocation is honored
  in the verify chain (introspection `active:false` for split, `jti` denylist for co-located),
  and the split topology is proven by a real Keycloak container — no new public endpoints.
- Keep the fast/slow split sharp so the local dev loop and median PR stay green without a
  container, while the binding 90% gate and SC#1–4 proofs live in the Keycloak CI job.
- Honor the design doc's framing: this is "wire + configure" the SDK's split-AS machinery and
  prove it, not build OAuth verification from scratch.

</specifics>

<deferred>
## Deferred Ideas

- **Public `POST /revoke` (RFC 7009) endpoint** — operator/admin UX convenience; design doc
  defers to **v10.4.1**. Phase 70 supports revocation via enforcement only.
- **Additional IdPs** (Auth0, Cognito, Okta) — Keycloak is the DoD reference IdP; others are
  validated only by the spec-conformance of `JwksTokenVerifier`, not by dedicated CI matrices.
- **DPoP (RFC 9449)** — v10.5+ (no production Python lib; not a current-spec MUST).
- **Audit-log middleware** — own milestone; not required for OAUTH-01..12.
- **2026-07-28 RC (MCP-stateless) full adoption** — Phase 70 only *acknowledges* its status;
  adopting the no-initialize handshake is a future milestone.

</deferred>

---

*Phase: 70-split-as-rs-keycloak-in-ci-integration-tests*
*Context gathered: 2026-06-22*
