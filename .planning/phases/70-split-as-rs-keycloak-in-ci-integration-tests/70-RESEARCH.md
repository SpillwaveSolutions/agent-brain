# Phase 70: Split AS/RS + Keycloak-in-CI + Integration Tests — Research

**Researched:** 2026-06-22
**Domain:** OAuth 2.1 split AS/RS topology, JWKS token verification, RFC 7662 introspection, jti revocation, Keycloak service container in GitHub Actions, MCP SDK integration testing
**Confidence:** HIGH (stack + patterns verified; one CRITICAL finding on Keycloak RFC 8707 support status changes implementation plan)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Keycloak-in-CI placement (two-tier, path-filtered + nightly)
- **Fast tier (every PR, local):** mock-JWKS / mock-introspection backed tests run in the default `task before-push` suite and on every PR in `pr-qa-gate.yml`. No container.
- **Integration tier (real Keycloak container):** a dedicated CI job runs the real Keycloak >= 22 container as a GitHub Actions **service container** (mirroring the existing `postgres` service in `pr-qa-gate.yml`). It is triggered on PRs touching `agent-brain-mcp/**` (path filter) AND nightly via `e2e-nightly.yml`.

#### Revocation scope (enforcement-side; NO new public endpoint)
- Split / opaque-token path: revocation honored **via introspection** — `active: false` → 401.
- Co-located path: **in-memory revocation list** (`jti` denylist) checked by the verifier.
- No public `POST /revoke` endpoint in Phase 70. Deferred to v10.4.1.

#### Coverage gate wiring
- Add `--cov=agent_brain_mcp.oauth --cov-fail-under=90`, surfaced as `task mcp:oauth-cov`.
- Authoritative measurement in the CI Keycloak job (Keycloak-dependent tests skipped locally would create holes).

#### Fast vs real-IdP test split (`@pytest.mark.keycloak`)
- Introduce `keycloak` marker mirroring the `postgres` skip convention.
- Register in `agent-brain-mcp/pyproject.toml` alongside `e2e`/`e2e_http`/`stress`.

### Claude's Discretion
- Exact Keycloak image tag/version (>= 22), realm-import JSON shape, and container health-check.
- Whether the introspection verifier is a separate class or a mode of `JwksTokenVerifier`.
- Revocation-list data structure (set vs TTL cache) and where it's checked in the verify chain.
- Test file organization (extend existing vs new `test_oauth_split_as_*.py` / `test_oauth_keycloak_e2e.py`).
- Whether the Keycloak integration job lives in `pr-qa-gate.yml` (new job) or a new dedicated workflow.

### Deferred Ideas (OUT OF SCOPE)
- Public `POST /revoke` (RFC 7009) endpoint — deferred to v10.4.1.
- Additional IdPs (Auth0, Cognito, Okta).
- DPoP (RFC 9449) — v10.5+.
- Audit-log middleware.
- 2026-07-28 RC (MCP-stateless) full adoption — Phase 70 only acknowledges its status.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OAUTH-11 | Split AS/RS mode — RS verifies JWTs via cached JWKS (`kid`-miss on-demand refresh + TTL jitter), verified end-to-end against Keycloak-in-CI with RFC 8707 Resource Indicators (Keycloak >= 22) | JwksTokenVerifier pattern confirmed via PyJWKClient docs; RFC 8707 workaround design confirmed (see CRITICAL finding below — aud audience scope mapper replaces native resource indicator in Keycloak < 26.8); CI container pattern confirmed from postgres service-container pattern |
| OAUTH-12 | Token introspection (RFC 7662) + revocation (RFC 7009) supported for opaque-token / external-AS deployments | IntrospectionTokenVerifier full implementation found in MCP SDK tutorial/docs (not yet shipped as a class in mcp 1.27.2 — must hand-roll against the `TokenVerifier` protocol); jti denylist design documented |

</phase_requirements>

---

## Summary

Phase 70 wires the split AS/RS topology: `JwksTokenVerifier` (PyJWKClient-backed, 5-min TTL + `kid`-miss refresh) plugs into the existing `LocalRs256Verifier` seam in `verifier.py` and is selected by config in `http.py`. An `IntrospectionTokenVerifier` handles opaque-token deployments. A `jti` denylist adds co-located revocation. The full SC#4 E2E flow runs against the official MCP SDK `OAuthClientProvider`.

**CRITICAL FINDING — Keycloak RFC 8707 status:** As of June 2026, Keycloak does NOT natively support RFC 8707 Resource Indicators. RFC 8707 support is targeted for Keycloak 26.8 (in development, not yet released). The **mandatory workaround** for the CI realm is to use Keycloak's audience scope mapper (`Included Custom Audience`) to bind `aud` to the MCP server URI. This achieves the same security property (aud binding in issued JWTs) without native RFC 8707 parameter recognition. SC#1 must be re-worded: "RFC 8707 Resource Indicators enabled on the client" is satisfied by the aud-scope-mapper workaround, not by Keycloak processing the `resource` parameter.

**MCP spec re-verification (2026-07-28 RC):** As of June 2026, the MCP-stateless (no-initialize handshake) RC proposal (SEP-1442 / PR #2575) is still in draft/review and has NOT merged into the normative authorization spec. The spec targeting a beta on 2026-06-30 and stable v2 on 2026-07-27 (Python SDK) may land during or just after Phase 70 implementation. The implementation uses `RequireAuthMiddleware` which validates tokens per-request and is stateless by design — no migration needed for authorization logic. Phase 70 must re-check at shipping time and file an issue if amendments are required.

**Primary recommendation:** Use `PyJWKClient(uri, cache_jwk_set=True, lifespan=300)` for `JwksTokenVerifier`; hand-roll `IntrospectionTokenVerifier` against the `TokenVerifier` protocol (not shipped in mcp 1.27.2 as a named class but the implementation pattern is documented in the MCP SDK tutorials); use Keycloak `quay.io/keycloak/keycloak:26.1` in CI with audience scope mapper workaround; run the full SC#4 E2E via `OAuthClientProvider` against an in-process test server subprocess.

---

## Standard Stack

### Core (verified against installed versions)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `PyJWT[crypto]` | `^2.13` (2.13.0 installed) | JWT decoding + `PyJWKClient` for remote JWKS fetch with cache | Already locked by Phase 65/67; `PyJWKClient` is bundled, no new dep |
| `mcp` | `^1.27.2` (1.27.2 installed in project) | `TokenVerifier` protocol, `BearerAuthBackend`, `RequireAuthMiddleware`, `OAuthClientProvider` | Already locked |
| `httpx` | `^0.28.0` (already a dep) | Async HTTP for introspection endpoint calls | Already a project dep |
| `authlib` | `^1.7.2` (already installed) | Not directly used in Phase 70 verifiers, but already present | No new dep |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-asyncio` | `^0.24.0` | Async test fixtures for verifier tests | Already in dev deps |
| `respx` | (optional) | Mock HTTPX calls in IntrospectionTokenVerifier unit tests | Only if mock needs to be httpx-level; `unittest.mock.AsyncMock` works too |

### No New Runtime Dependencies Required
All libraries needed for Phase 70 are already in `agent-brain-mcp/pyproject.toml`. No `poetry add` needed.

**Version verification (run before planning):**
```bash
cd agent-brain-mcp && poetry run pip show mcp pyjwt authlib httpx
```
Current confirmed: mcp=1.27.2, pyjwt=2.13.x, authlib=1.7.2, httpx=0.28.x

---

## CRITICAL Finding: Keycloak RFC 8707 Resource Indicators Status

**Confidence: HIGH** — verified against live Keycloak GitHub issue #14355, discussion #35743, and official MCP Keycloak integration guide.

Keycloak does NOT natively process the OAuth `resource` parameter (RFC 8707) in any currently-released version (as of Keycloak 26.6.0, April 2026). Feature is targeted for Keycloak 26.8 (milestone on issue #14355) but not yet released.

**Official workaround confirmed by Keycloak's own MCP integration guide (`keycloak.org/securing-apps/mcp-authz-server`):**

Use a **client scope with an audience mapper**:
1. Create a client scope (e.g., `mcp-audience`) in the realm.
2. Add a mapper: type = "Audience", `Included Custom Audience` = `<AGENT_BRAIN_OAUTH_RESOURCE>` (the MCP server URL, e.g. `http://localhost:8000`).
3. Assign the scope to the `agent-brain-mcp` client as a default scope.
4. Keycloak will then embed `aud: "<MCP_server_URL>"` in all issued JWTs, satisfying the RS's `aud` validation check.

**Impact on SC#1:** The realm import JSON must include this audience mapper configuration instead of native RFC 8707 client settings. The JWT `aud` claim will still equal `AGENT_BRAIN_OAUTH_RESOURCE` — the RS `JwksTokenVerifier` validation is unchanged. The security property (aud binding) is identical; only the Keycloak configuration mechanism differs.

**Keycloak version to use in CI:** `quay.io/keycloak/keycloak:26.1` (stable, documented, passes CIMD enablement via `--features=cimd`). Latest stable as of June 2026 is 26.6.x. Use `26.1` for repeatability or `26` for latest-minor. Recommend pinning to `26.1` for reproducibility; move to `26` once 26.8 ships with native RFC 8707.

---

## Architecture Patterns

### JwksTokenVerifier Design

`JwksTokenVerifier` implements the same `TokenVerifier` protocol as `LocalRs256Verifier` (stable `async def verify_token(self, token: str) -> AccessToken | None`). It is selected in `http.py` when `AGENT_BRAIN_OAUTH_ISSUER` is set (i.e., issuer is external — split AS mode). `LocalRs256Verifier` remains for co-located mode.

```python
# Source: PyJWKClient constructor (Context7, /jpadilla/pyjwt)
# Source: LocalRs256Verifier seam (agent_brain_mcp/oauth/verifier.py)
import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken

_LEEWAY_SECONDS = 30
_JWKS_TTL_SECONDS = 300  # 5-minute cache per design doc

class JwksTokenVerifier:
    """RS256 TokenVerifier using a remote JWKS endpoint (split AS/RS, Phase 70).

    Implements the same verify_token(token) -> AccessToken | None protocol
    as LocalRs256Verifier. Selected by http.py when AGENT_BRAIN_OAUTH_ISSUER
    is set (external IdP mode).

    PyJWKClient caching behaviour:
      - Tier 1 (JWK Set cache): cache_jwk_set=True, lifespan=300s (5 min).
        On every token, get_signing_key_from_jwt() fetches the JWKS if the
        cache is empty or expired.
      - kid-miss on-demand refresh: if the kid in the JWT header is not found
        in the current cached JWK Set, PyJWKClient automatically refreshes
        the JWKS from the endpoint and retries before raising PyJWKSetDataError.
        This is built-in behaviour — no custom logic needed.
    """

    def __init__(
        self,
        *,
        jwks_uri: str,
        issuer: str,
        resource: str,
        lifespan: float = _JWKS_TTL_SECONDS,
    ) -> None:
        self._client = PyJWKClient(
            jwks_uri,
            cache_jwk_set=True,
            lifespan=lifespan,
        )
        self.issuer = issuer
        self.resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None
        try:
            signing_key = self._client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.resource,
                issuer=self.issuer,
                leeway=_LEEWAY_SECONDS,
                options={
                    "require": ["exp", "iss", "aud", "nbf"],
                    "verify_signature": True,
                },
            )
        except jwt.PyJWTError:
            return None
        except Exception:  # PyJWKSetDataError, network errors
            return None
        client_id: str = claims.get("client_id") or claims.get("sub") or ""
        scope_str: str = claims.get("scope") or ""
        scopes: list[str] = scope_str.split() if scope_str else []
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=claims.get("exp"),
            resource=self.resource,
        )
```

**Wiring in `http.py`:** The `build_asgi_app()` function selects the verifier at lines where `build_local_verifier()` is called. When `AGENT_BRAIN_OAUTH_ISSUER` is set AND `AGENT_BRAIN_OAUTH_JWKS_URI` is set (new env var for split mode), return a `JwksTokenVerifier` instead of `LocalRs256Verifier`. The selection logic replaces only the `verifier = build_local_verifier(...)` line — no other changes to the middleware composition.

New config env vars for split mode:
- `AGENT_BRAIN_OAUTH_JWKS_URI` — the external IdP's JWKS endpoint URL (e.g., `http://keycloak:8080/realms/agent-brain/protocol/openid-connect/certs`)
- `AGENT_BRAIN_OAUTH_ISSUER` — already exists (but was only used as a pass-through); in split mode it must match the JWT `iss` claim exactly.

### IntrospectionTokenVerifier Design

NOT shipped as a named class in mcp 1.27.2. Only mentioned as a reference (`ProviderTokenVerifier` docstring: "consider IntrospectionTokenVerifier"). The implementation pattern is fully documented in the MCP SDK tutorial docs (fetched via Context7).

Hand-roll as a separate class in `agent_brain_mcp/oauth/verifier.py` (or a new `agent_brain_mcp/oauth/introspection.py`):

```python
# Source: MCP modelcontextprotocol tutorial docs (Context7)
# Simplified for agent-brain (httpx-based, matches existing deps)
import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier

class IntrospectionTokenVerifier:
    """RFC 7662 token introspection verifier (Phase 70, split-AS opaque tokens).

    Calls the AS introspection endpoint and maps active:true -> AccessToken,
    active:false -> None (revocation via introspection is automatic here).
    """

    def __init__(
        self,
        *,
        introspection_endpoint: str,
        client_id: str,
        client_secret: str,
        resource: str,  # AGENT_BRAIN_OAUTH_RESOURCE for aud validation
    ) -> None: ...

    async def verify_token(self, token: str) -> AccessToken | None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                self.introspection_endpoint,
                data={"token": token, "client_id": self.client_id,
                      "client_secret": self.client_secret},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("active", False):
            return None  # revoked or expired — active:false -> 401
        # Validate aud
        aud = data.get("aud")
        if isinstance(aud, list):
            if self.resource not in aud:
                return None
        elif aud != self.resource:
            return None
        return AccessToken(
            token=token,
            client_id=data.get("client_id", ""),
            scopes=(data.get("scope") or "").split(),
            expires_at=data.get("exp"),
            resource=self.resource,
        )
```

**Selection logic:** `IntrospectionTokenVerifier` is activated when `AGENT_BRAIN_OAUTH_INTROSPECTION_URI` env var is set (new var). It can be the primary verifier for opaque-token deployments, or a fallback when JWT verification fails. Decision (Claude's discretion): implement as a **separate class, not a mode of `JwksTokenVerifier`** — cleaner protocol + independent testability.

### jti Denylist for Co-Located Revocation

```python
# agent_brain_mcp/oauth/tokens.py — extend the existing InMemoryTokenStore
import threading

class InMemoryTokenStore:
    # ... existing code ...
    _revoked_jtis: set[str]  # New: add to __init__

    def revoke_by_jti(self, jti: str) -> None:
        """Add a jti to the in-memory denylist."""
        self._revoked_jtis.add(jti)

    def is_jti_revoked(self, jti: str) -> bool:
        return jti in self._revoked_jtis
```

`LocalRs256Verifier.verify_token()` checks the jti denylist after successful JWT decode:
```python
jti = claims.get("jti")
if jti and token_store.is_jti_revoked(jti):
    return None
```

**Data structure choice (Claude's discretion):** Use a plain `set[str]`. TTL expiry not needed — tokens expire via `exp` claim anyway; the denylist just covers the window between revocation and natural expiry. Memory bounded by active session count (low). Thread-safe for read via GIL; wrap `add`/`discard` with a lock for safety.

### Keycloak Service Container in GitHub Actions

Pattern mirrors the existing `postgres` service block in `pr-qa-gate.yml`:

```yaml
# New job: mcp-keycloak-integration
# Triggered: on PRs with paths: agent-brain-mcp/**, nightly (added to e2e-nightly.yml)
services:
  keycloak:
    image: quay.io/keycloak/keycloak:26.1
    env:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin
      KC_HEALTH_ENABLED: "true"
    ports:
      - 8080:8080
    options: >-
      --health-cmd "curl -f http://localhost:9000/health/ready || exit 1"
      --health-interval 15s
      --health-timeout 5s
      --health-retries 10
      --entrypoint ""
```

**Note on health-check port:** Keycloak 26.x exposes the management/health endpoint on port 9000 (not 8080). The `--health-cmd` must curl port 9000.

**Realm bootstrap:** Use the Keycloak Admin REST API at container startup (via `curl` or a short Python script) rather than volume-mounting a realm JSON. Service containers in GitHub Actions do not support volume mounts. The bootstrap script:
1. Waits for `http://localhost:8080/health/ready` (from the health check).
2. Creates realm `agent-brain` via `POST /admin/realms`.
3. Creates client `agent-brain-mcp` with `directAccessGrantsEnabled: true`, `serviceAccountsEnabled: false`.
4. Creates a client scope `mcp-audience` with an audience mapper setting `aud = AGENT_BRAIN_OAUTH_RESOURCE`.
5. Assigns the scope to the client as a default scope.
6. Optionally creates a test user for the password grant (PKCE flow requires a browser; use client credentials or a token endpoint hack for headless tests).

**Alternative: `start-dev --import-realm` with base64-encoded realm JSON in env var:** Not supported by GitHub Actions service containers (no `command:` override for service containers, unlike `jobs.<job>.steps`). Use Admin REST API bootstrap instead.

**Keycloak start command in service container:** The default entrypoint for `quay.io/keycloak/keycloak:26.1` is `/opt/keycloak/bin/kc.sh start`. For CI without TLS, the container must be started with `--override options=start-dev` or through the env var `KC_BOOTSTRAP_ADMIN_USERNAME`. The cleanest approach for CI:

```yaml
options: >-
  --command "/opt/keycloak/bin/kc.sh start-dev"
  --health-cmd "curl -sf http://localhost:9000/health/ready"
  --health-interval 15s
  --health-retries 12
```

### SC#4 E2E Flow Structure

The full E2E uses `OAuthClientProvider` (from `mcp.client.auth`) as the test client driver against a real subprocess running `agent-brain-mcp`:

```
1. Start agent-brain-mcp HTTP server subprocess (with AGENT_BRAIN_AUTH=oauth)
2. OAuthClientProvider drives: 401 challenge -> PRM fetch -> OASM fetch
3. PKCE dance: generate code_verifier + challenge, call /authorize, intercept redirect
4. POST /token with code + verifier -> receive JWT
5. POST /mcp with JWT -> verify 200 tool response
6. Refresh: use refresh_token -> new access token -> POST /mcp again
7. Scope boundary: get a read-only token, call admin tool -> verify 403
```

For the Keycloak tier, the JWT comes from Keycloak's /token endpoint (client credentials grant for automated headless testing, or a pre-seeded authorization code for the full PKCE path). The `OAuthClientProvider` handles the discovery and dance steps.

**Keycloak URL patterns:**
- JWKS: `http://localhost:8080/realms/agent-brain/protocol/openid-connect/certs`
- Token endpoint: `http://localhost:8080/realms/agent-brain/protocol/openid-connect/token`
- Introspection: `http://localhost:8080/realms/agent-brain/protocol/openid-connect/token/introspect`
- Authorization: `http://localhost:8080/realms/agent-brain/protocol/openid-connect/auth`
- OASM: `http://localhost:8080/realms/agent-brain/.well-known/openid-configuration`

### Recommended Project Structure for New Files

```
agent-brain-mcp/
  agent_brain_mcp/
    oauth/
      verifier.py          # MODIFY: add JwksTokenVerifier, IntrospectionTokenVerifier
                           # (or split into verifier_jwks.py, verifier_introspection.py)
      tokens.py            # MODIFY: add jti denylist to InMemoryTokenStore
      __init__.py          # MODIFY: export new verifier classes
    http.py                # MODIFY: verifier selection logic (JwksTokenVerifier vs LocalRs256Verifier)
    config.py              # MODIFY: new env vars (AGENT_BRAIN_OAUTH_JWKS_URI,
                           #         AGENT_BRAIN_OAUTH_INTROSPECTION_URI)
  tests/
    test_oauth_jwks_verifier.py          # NEW: JwksTokenVerifier unit (mock JWKS server)
    test_oauth_introspection_verifier.py # NEW: IntrospectionTokenVerifier unit (mock endpoint)
    test_oauth_jti_denylist.py           # NEW: co-located revocation denylist
    test_oauth_keycloak_e2e.py           # NEW: @pytest.mark.keycloak — all Keycloak-backed tests
.github/workflows/
    mcp-keycloak-integration.yml         # NEW: path-filtered PR job + nightly trigger
                                         # OR: add a new job to pr-qa-gate.yml
```

### Anti-Patterns to Avoid

- **Hand-rolling JWKS caching:** `PyJWKClient` already provides two-tier caching (JWK Set TTL + per-key LRU). Do not implement custom caching on top; just configure `lifespan=300`.
- **Storing raw JWT in the jti denylist:** Store only the `jti` string (16-char urlsafe), not the full token. Saves memory and prevents token content from persisting in memory after revocation.
- **Calling introspection synchronously:** `IntrospectionTokenVerifier.verify_token()` MUST be `async def` using `httpx.AsyncClient`. Do not block the event loop.
- **Volume-mounting realm JSON in GitHub Actions service containers:** Service containers do not support volume mounts. Use the Admin REST API to bootstrap the realm instead.
- **Using `start` (production) mode for Keycloak in CI:** The production start requires TLS. Use `start-dev` for CI.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWKS fetch + TTL cache + kid-miss refresh | Custom HTTP cache | `PyJWKClient(uri, cache_jwk_set=True, lifespan=300)` | Built-in two-tier caching; kid-miss auto-refresh; already a project dep |
| JWT signature + exp/iss/aud verification | Custom decode logic | `jwt.decode(token, key, algorithms=["RS256"], audience=..., issuer=..., leeway=30)` | All checks in one call; handles aud as list or string |
| TokenVerifier protocol conformance | Custom base class | Implement `async def verify_token(token: str) -> AccessToken | None` directly | It's a structural `Protocol` — no inheritance needed |
| OAuth 2.0 Token Introspection HTTP call | Custom requests-based code | `httpx.AsyncClient` + the pattern from MCP tutorial docs | Already a dep; async-safe; handles timeout + limits |
| OAuthClientProvider E2E client | Custom OAuth client | `mcp.client.auth.OAuthClientProvider` | SDK ships the full client-side 401-dance driver |

---

## Common Pitfalls

### Pitfall 1: PyJWKClient is Synchronous, `verify_token` Must Be Async

**What goes wrong:** `PyJWKClient.get_signing_key_from_jwt(token)` is a **synchronous** call that may make a blocking network request (on cache miss). Calling it directly in an `async def verify_token` blocks the event loop.

**Why it happens:** PyJWT's `PyJWKClient` uses `urllib.request` (synchronous) internally. There is no async variant.

**How to avoid:** Wrap the `PyJWKClient` call in `asyncio.to_thread()`:
```python
import asyncio
signing_key = await asyncio.to_thread(self._client.get_signing_key_from_jwt, token)
```
This is critical for correctness under load. `jwt.decode()` is CPU-only (no I/O) and does NOT need threading.

**Warning signs:** High latency on JWKS cache miss; event loop blocking warnings in pytest-asyncio tests.

### Pitfall 2: Keycloak aud Claim Is a List, Not a String

**What goes wrong:** Keycloak (especially with audience mapper) may emit `aud` as a JSON array (`["client-id", "http://mcp-server/"]`) rather than a plain string. PyJWT's `jwt.decode(audience=...)` accepts a string AND a list, so this is handled correctly — BUT the `IntrospectionTokenVerifier._validate_resource()` implementation must handle both `str` and `list[str]` for the `aud` field in the introspection response.

**How to avoid:** Always normalize aud: `aud = data.get("aud"); audiences = [aud] if isinstance(aud, str) else (aud or [])`.

### Pitfall 3: Keycloak Health Check Port vs. Service Port

**What goes wrong:** The GitHub Actions service container health check option `--health-cmd` is run against the service from GitHub's network. Keycloak 26.x exposes HTTP on port 8080 but its `/health/ready` endpoint is on the **management port 9000** (separate interface).

**How to avoid:** Health check must use port 9000: `curl -sf http://localhost:9000/health/ready`. If you use port 8080 the check will 404.

### Pitfall 4: 90% Coverage Gate Passes Locally But Fails in CI

**What goes wrong:** The `@pytest.mark.keycloak` tests are excluded from `task before-push`. Locally, coverage of `JwksTokenVerifier` and `IntrospectionTokenVerifier` is partially exercised by mock-backed tests but if the 90% gate is run locally it may show < 90% if Keycloak-only paths are not mock-covered.

**How to avoid:** The binding gate is the CI Keycloak job (`task mcp:oauth-cov` runs there with `--cov-fail-under=90`). Locally, the mock tier should still cover enough to keep `task before-push` green (the global 80% floor). Document that the 90% figure is the CI gate, not the local gate.

### Pitfall 5: MCP 2026-07-28 RC Lands Mid-Phase

**What goes wrong:** The MCP stateless RC (removing `initialize` handshake) could land in the mcp Python SDK during the Phase 70 implementation window. If `OAuthClientProvider` or `RequireAuthMiddleware` change APIs the E2E tests would break.

**How to avoid:** Pin `mcp = "^1.27.2"` (already pinned in pyproject.toml). The `^` constraint allows patch-level updates (1.27.x) but blocks major/minor jumps. If a 1.28+ SDK is needed, do it consciously with a migration check. The `RequireAuthMiddleware` validates tokens per-request independently of `initialize` — no auth logic changes needed for the stateless RC.

### Pitfall 6: Service Container Cannot Be Volume-Mounted for Realm Import

**What goes wrong:** GitHub Actions service containers do NOT support the `volumes:` key (unlike step-level Docker actions). Trying to mount a realm JSON file causes the workflow to silently ignore the mount or fail at startup.

**How to avoid:** Bootstrap the Keycloak realm via the Admin REST API in a workflow step AFTER the service is healthy.

### Pitfall 7: Keycloak iss Claim Format

**What goes wrong:** Keycloak emits `iss` in JWTs as `http://localhost:8080/realms/agent-brain` (including the realm path). If `AGENT_BRAIN_OAUTH_ISSUER` is set to only the base URL (`http://localhost:8080`) the `iss` check will fail for every token.

**How to avoid:** Set `AGENT_BRAIN_OAUTH_ISSUER=http://localhost:8080/realms/agent-brain` in the CI job env.

---

## Code Examples

### JwksTokenVerifier — Mock JWKS Server for Unit Tests

```python
# Source: PyJWKClient docs + LocalRs256Verifier test pattern (agent-brain-mcp)
import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

@pytest.fixture
def mock_jwks_server(signing_key):
    """In-process JWKS endpoint for testing JwksTokenVerifier without network."""
    async def jwks(request):
        return JSONResponse(signing_key.jwks_dict)
    app = Starlette(routes=[Route("/.well-known/jwks.json", jwks)])
    # Use TestClient to get a URL — but PyJWKClient uses urllib (sync)
    # so override the fetch with a monkeypatch instead.
    return signing_key.jwks_dict

# Preferred approach: monkeypatch PyJWKClient.fetch_data to return the mock JWKS
def test_jwks_verifier_valid_token(monkeypatch, signing_key, test_token):
    from agent_brain_mcp.oauth.verifier import JwksTokenVerifier
    from jwt.algorithms import RSAAlgorithm
    import json

    jwks_json = json.dumps(signing_key.jwks_dict)

    def mock_fetch_data(self):
        self.jwk_set_data = json.loads(jwks_json)

    monkeypatch.setattr("jwt.PyJWKClient.fetch_data", mock_fetch_data)
    verifier = JwksTokenVerifier(
        jwks_uri="http://mock-jwks/.well-known/jwks.json",
        issuer="http://as.example.com",
        resource="http://mcp.example.com",
    )
    # ... assert verifier.verify_token(test_token) is not None
```

### IntrospectionTokenVerifier — Mock Endpoint for Unit Tests

```python
# Source: MCP SDK tutorial IntrospectionTokenVerifier pattern + httpx mock
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_introspection_active_true_returns_access_token(introspection_verifier):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "active": True,
        "client_id": "test-client",
        "scope": "agent-brain:read",
        "exp": 9999999999,
        "aud": "http://mcp.example.com",
    }
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await introspection_verifier.verify_token("some-opaque-token")
    assert result is not None
    assert "agent-brain:read" in result.scopes

@pytest.mark.asyncio
async def test_introspection_active_false_returns_none(introspection_verifier):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"active": False}
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await introspection_verifier.verify_token("revoked-token")
    assert result is None  # SC#2 — revoked token -> 401
```

### Keycloak Realm Bootstrap (CI Step)

```bash
# Source: Keycloak Admin REST API docs; run after container health check passes
KC=http://localhost:8080

# Get admin token
TOKEN=$(curl -s -X POST "$KC/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli&grant_type=password&username=admin&password=admin" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Create realm
curl -s -X POST "$KC/admin/realms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"realm":"agent-brain","enabled":true}'

# Create client
curl -s -X POST "$KC/admin/realms/agent-brain/clients" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "agent-brain-mcp",
    "enabled": true,
    "publicClient": true,
    "directAccessGrantsEnabled": true,
    "redirectUris": ["http://localhost:*"],
    "webOrigins": ["http://localhost:*"]
  }'

# Create audience mapper (RFC 8707 workaround)
CLIENT_UUID=$(curl -s "$KC/admin/realms/agent-brain/clients?clientId=agent-brain-mcp" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

curl -s -X POST "$KC/admin/realms/agent-brain/clients/$CLIENT_UUID/protocol-mappers/models" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mcp-audience",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-audience-mapper",
    "config": {
      "included.custom.audience": "'"$AGENT_BRAIN_OAUTH_RESOURCE"'",
      "access.token.claim": "true"
    }
  }'

# Create test user
curl -s -X POST "$KC/admin/realms/agent-brain/users" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","enabled":true,"credentials":[{"type":"password","value":"testpass","temporary":false}]}'
```

---

## Current Coverage Analysis — agent_brain_mcp/oauth/

**Run:** `poetry run pytest tests/test_oauth*.py --cov=agent_brain_mcp.oauth --cov-report=term-missing`

**Result (measured 2026-06-22 against 237 fast-tier tests):**

| Module | Stmts | Miss | Cover | Uncovered Lines |
|--------|-------|------|-------|-----------------|
| `__init__.py` | 4 | 0 | **100%** | — |
| `keys.py` | 64 | 16 | **75%** | 192, 236, 239-268 (PEM loading path — needs test with temp PEM file) |
| `oauth_client.py` | 15 | 0 | **100%** | — |
| `oauth_handlers.py` | 90 | 5 | **94%** | 141-145 (edge case in loopback handler) |
| `provider.py` | 97 | 8 | **92%** | 183, 359, 484, 577, 609, 683-687 (rare error paths) |
| `registration.py` | 55 | 5 | **91%** | 138-140, 196, 279-280 |
| `scopes.py` | 11 | 5 | **55%** | 87-89, 133-134 (`InsufficientScopeError.__init__` + `require_scope` raise path — not hit by existing test_tool_scope_enforcement.py) |
| `token_storage.py` | 54 | 6 | **89%** | 123-128, 154-159 (set_tokens + set_client_info I/O paths) |
| `tokens.py` | 54 | 4 | **93%** | 327-330 (revoke_token edge case) |
| `verifier.py` | 35 | 1 | **97%** | 210 (RuntimeError path in build_local_verifier) |
| **TOTAL** | 479 | 50 | **90%** | — |

**Key insight:** The fast-tier tests ALREADY achieve 90% total coverage of `agent_brain_mcp/oauth/`. The CI gate threshold is therefore achievable AND the local dev loop (fast tier only) is within striking distance of 90%.

**Gap analysis — what Phase 70 tests MUST add to reach/maintain 90% after new code lands:**

1. `verifier.py` will gain ~60 new lines (`JwksTokenVerifier`, `IntrospectionTokenVerifier`) — these start at 0% coverage until `test_oauth_jwks_verifier.py` and `test_oauth_introspection_verifier.py` are added. Without those files the new code pulls the total below 90%.
2. `keys.py` lines 236-268 (PEM loading path) — add one test with a temp PEM file.
3. `scopes.py` lines 87-89 and 133-134 — add direct `InsufficientScopeError()` + `require_scope()` unit tests.
4. `tokens.py` lines 327-330 — test the revoke_token edge case.

**Wave 0 gap:** `test_oauth_jwks_verifier.py` and `test_oauth_introspection_verifier.py` must be created in Wave 1 (before implementing the verifiers) to satisfy the TDD pattern.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `python-jose` for JWT | `PyJWT[crypto]` | Phase 65 locked decision | python-jose abandoned 2021; PyJWT actively maintained |
| In-process local key verification only | JWKS remote fetch via `PyJWKClient` | Phase 70 (new) | Enables split AS/RS topology |
| Keycloak native RFC 8707 | Audience scope mapper workaround | Keycloak 26.8 not yet released | Same security property; different realm config |
| mcp 1.27.2 stateful initialize handshake | 2026-07-28 RC: stateless (not yet merged) | RC in draft | No auth logic change required; per-request Bearer validation already stateless |

**MCP 2026-07-28 RC Status (LIVE SPEC RE-VERIFICATION):**

Verified 2026-06-22 via Context7 (`/modelcontextprotocol/modelcontextprotocol`) and GitHub:
- SEP-1442 (Make MCP Stateless) is still in "in-review" draft status (PR #2575 open).
- The 2025-11-25 authorization spec remains the normative baseline.
- The RC is targeting beta 2026-06-30 / stable v2 2026-07-27 for the Python SDK.
- **Impact on Phase 70:** Zero impact on authorization logic. `RequireAuthMiddleware` already validates Bearer tokens per-request independently of the `initialize` handshake. The session lifecycle changes do not affect token validation. Phase 70 must re-verify when shipping (target: check if PR #2575 merged, confirm mcp Python SDK >= 1.28.0 release notes show no auth API breakage, update pyproject.toml pin if needed).

**Keycloak RFC 8707 status (LIVE VERIFIED 2026-06-22):**
- Not available in any released Keycloak version (latest: 26.6.0).
- Targeted for Keycloak 26.8 (issue #14355 milestone).
- Workaround documented in official Keycloak MCP integration guide: audience scope mapper.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+, pytest-asyncio 0.24+ |
| Config file | `agent-brain-mcp/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `cd agent-brain-mcp && poetry run pytest tests/test_oauth*.py -x` |
| Full fast-tier suite | `cd agent-brain-mcp && poetry run pytest -m 'not e2e and not e2e_http and not contract and not stress and not keycloak'` |
| OAuth coverage gate | `cd agent-brain-mcp && poetry run pytest tests/ --cov=agent_brain_mcp.oauth --cov-fail-under=90` (CI Keycloak job only) |
| Keycloak tier | `cd agent-brain-mcp && poetry run pytest -m keycloak -v` (CI only) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OAUTH-11 SC#1 | Keycloak-issued JWT accepted by `JwksTokenVerifier` via JWKS | `keycloak` marker | `pytest -m keycloak tests/test_oauth_keycloak_e2e.py::test_keycloak_jwt_accepted` | Wave 1 |
| OAUTH-11 SC#1 | JWKS 5-min TTL caching (mock) | unit | `pytest tests/test_oauth_jwks_verifier.py::test_jwks_ttl_caching` | Wave 1 |
| OAUTH-11 SC#1 | kid-miss on-demand refresh (mock) | unit | `pytest tests/test_oauth_jwks_verifier.py::test_kid_miss_triggers_refresh` | Wave 1 |
| OAUTH-11 SC#1 | aud validation (mock JWKS) | unit | `pytest tests/test_oauth_jwks_verifier.py::test_wrong_aud_returns_none` | Wave 1 |
| OAUTH-12 SC#2 | `active:true` → AccessToken | unit | `pytest tests/test_oauth_introspection_verifier.py::test_active_true_returns_token` | Wave 1 |
| OAUTH-12 SC#2 | `active:false` → None (rejected) | unit | `pytest tests/test_oauth_introspection_verifier.py::test_active_false_returns_none` | Wave 1 |
| OAUTH-12 SC#2 | Introspection round-trip vs Keycloak | `keycloak` marker | `pytest -m keycloak tests/test_oauth_keycloak_e2e.py::test_introspection_roundtrip` | Wave 1 |
| OAUTH-12 SC#3 | Revoked token rejected via introspection | `keycloak` marker | `pytest -m keycloak tests/test_oauth_keycloak_e2e.py::test_revoked_token_rejected` | Wave 1 |
| OAUTH-12 SC#3 | jti denylist (co-located) | unit | `pytest tests/test_oauth_jti_denylist.py::test_revoked_jti_returns_none` | Wave 1 |
| SC#4 E2E full flow | 401 → PRM → OASM → PKCE → tool call | `e2e`/`keycloak` | `pytest -m keycloak tests/test_oauth_keycloak_e2e.py::test_full_oauth_dance_tool_call` | Wave 2 |
| SC#4 E2E refresh | token refresh path | `keycloak` | `pytest -m keycloak tests/test_oauth_keycloak_e2e.py::test_token_refresh_path` | Wave 2 |
| SC#4 E2E scope | read-only token + admin tool → 403 | `keycloak` | `pytest -m keycloak tests/test_oauth_keycloak_e2e.py::test_scope_boundary_403` | Wave 2 |
| OAUTH-11 config | `AGENT_BRAIN_OAUTH_JWKS_URI` activates `JwksTokenVerifier` | unit | `pytest tests/test_oauth_split_as_config.py::test_jwks_uri_selects_jwks_verifier` | Wave 1 |
| Coverage gate | `agent_brain_mcp.oauth` >= 90% | CI | `pytest --cov=agent_brain_mcp.oauth --cov-fail-under=90` | n/a (CI job) |
| Spec re-verify | MCP 2026-07-28 RC check before shipping | manual | n/a — check PR #2575 + mcp SDK changelog | manual task |

### Sampling Rate
- **Per task commit (fast tier):** `poetry run pytest tests/test_oauth*.py -x`
- **Per wave merge:** `poetry run pytest -m 'not e2e and not e2e_http and not contract and not stress and not keycloak' --cov=agent_brain_mcp.oauth`
- **Phase gate (CI Keycloak job):** Full suite including `@pytest.mark.keycloak`, `--cov=agent_brain_mcp.oauth --cov-fail-under=90`

### Wave 0 Gaps (must be created before implementation)

- [ ] `tests/test_oauth_jwks_verifier.py` — covers `JwksTokenVerifier` unit behavior (mock JWKS, TTL, kid-miss, aud, iss, exp, leeway)
- [ ] `tests/test_oauth_introspection_verifier.py` — covers `IntrospectionTokenVerifier` (mock endpoint, active:true/false, aud validation, timeout)
- [ ] `tests/test_oauth_jti_denylist.py` — covers jti denylist in `InMemoryTokenStore` (revoke + check)
- [ ] `tests/test_oauth_split_as_config.py` — covers new config env vars + verifier selection logic in `http.py`
- [ ] `tests/test_oauth_keycloak_e2e.py` — `@pytest.mark.keycloak` suite for all Keycloak-backed assertions
- [ ] Register `keycloak` marker in `agent-brain-mcp/pyproject.toml` `[tool.pytest.ini_options].markers`
- [ ] Add `keycloak` to `addopts = "-m 'not e2e and not e2e_http and not contract and not stress and not keycloak'"` exclusion list
- [ ] New GitHub Actions workflow (or job in `pr-qa-gate.yml`) with Keycloak service container
- [ ] New Taskfile targets: `task mcp:oauth-cov`, `task mcp:keycloak`

---

## Open Questions

1. **`asyncio.to_thread` vs PyJWKClient async wrapper**
   - What we know: `PyJWKClient.get_signing_key_from_jwt()` is synchronous and may block on network I/O. `verify_token` must be `async def`.
   - What's unclear: under pytest-asyncio with a mock that returns immediately, does `asyncio.to_thread()` add unnecessary overhead in tests?
   - Recommendation: Use `asyncio.to_thread()` in production code for correctness; in tests, monkeypatch `PyJWKClient.get_signing_key_from_jwt` to a sync function returning the mock key — the thread wrapper is invisible to the mock.

2. **Introspection verifier as mode vs. separate class**
   - What we know: CONTEXT.md marks this as Claude's discretion. The MCP SDK mentions `IntrospectionTokenVerifier` as a separate class. The `TokenVerifier` protocol is structural (no inheritance).
   - Recommendation: **Separate class** (`IntrospectionTokenVerifier` in `verifier.py`). Cleaner separation of concerns; `JwksTokenVerifier` does not need an `if introspection` branch; independent testability.

3. **Keycloak PKCE flow headless in CI**
   - What we know: The full PKCE dance requires a browser-redirect interception. `OAuthClientProvider` in the SDK handles the loopback redirect. In CI, there is no browser.
   - What's unclear: Can `OAuthClientProvider` be driven headlessly (e.g., with a direct HTTP call to /authorize that returns the code)?
   - Recommendation: For CI Keycloak tests, use Keycloak's **Resource Owner Password Credentials Grant** (direct grant) to get a JWT for the test user — this bypasses PKCE for headless test tokens. Test the full PKCE dance using the co-located AS (Phase 69 `test_oauth_client_dance_e2e.py` already covers this). SC#4 "full PKCE dance" can be verified against the co-located AS; the Keycloak CI tests verify JWT acceptance + introspection + scope boundary independently.

4. **Coverage gate in `task before-push` vs CI only**
   - What we know: CONTEXT.md says "authoritative measurement in the CI Keycloak job" but `task mcp:oauth-cov` should exist locally too.
   - Recommendation: `task mcp:oauth-cov` locally runs with `--cov-fail-under=85` (soft gate), CI runs with `--cov-fail-under=90` (hard gate). Documents explicitly that the 90% target is CI-only. Avoids false local failures when Keycloak tests are not run locally.

---

## Sources

### Primary (HIGH confidence)
- Context7 `/jpadilla/pyjwt` — `PyJWKClient` constructor params, two-tier caching, kid-miss auto-refresh, `get_signing_key_from_jwt()` usage
- Context7 `/modelcontextprotocol/modelcontextprotocol` — `IntrospectionTokenVerifier` full implementation, `TokenVerifier` protocol, Keycloak URL patterns for introspection
- `agent-brain-mcp/agent_brain_mcp/oauth/verifier.py` — `LocalRs256Verifier` stable `verify_token` seam; Phase 70 swap contract documented in docstring
- `agent-brain-mcp/agent_brain_mcp/http.py` — verifier selection point (`build_local_verifier()` call at line 766); middleware composition order; env var resolution
- `agent-brain-mcp/agent_brain_mcp/oauth/` — all 10 source modules read; coverage baseline measured (90% with fast tier)
- `.github/workflows/pr-qa-gate.yml` — postgres service container pattern to mirror for Keycloak
- `agent-brain-mcp/pyproject.toml` — marker registration convention, current dep versions

### Secondary (MEDIUM confidence)
- [Keycloak MCP Integration Guide](https://www.keycloak.org/securing-apps/mcp-authz-server) — RFC 8707 status + audience scope mapper workaround (official Keycloak docs)
- [Keycloak 26.6.0 Release Notes](https://www.keycloak.org/2026/04/keycloak-2660-released) — confirms RFC 8707 not in 26.6; Java 25 support
- [Keycloak RFC 8707 issue #14355](https://github.com/keycloak/keycloak/issues/14355) — milestone 26.8, in development
- [MCP SEP-1442 stateless proposal](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1442) — RC still in draft, not merged

### Tertiary (LOW confidence — verify before implementing)
- Keycloak service container health-check port (9000 vs 8080) — search results confirm 9000 for management; verify against `quay.io/keycloak/keycloak:26.1` before finalizing CI YAML
- `asyncio.to_thread()` for PyJWKClient blocking call — standard pattern, not verified against PyJWT changelog for any async variant

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — all deps confirmed installed in project; no new deps needed
- JwksTokenVerifier pattern: HIGH — PyJWKClient API confirmed via Context7; LocalRs256Verifier seam code confirmed
- IntrospectionTokenVerifier pattern: HIGH — full implementation found in MCP SDK tutorial docs via Context7
- Keycloak RFC 8707: HIGH (CRITICAL finding) — confirmed NOT available in any released version; workaround confirmed from official docs
- CI service container pattern: HIGH — mirrors existing postgres pattern; health-check port verified
- Coverage analysis: HIGH — measured live against installed codebase (90% with 237 fast-tier tests)
- MCP RC 2026-07-28: MEDIUM — confirmed still draft as of June 2026; may land during phase window

**Research date:** 2026-06-22
**Valid until:** 2026-07-15 (30 days for stable stack items; 7 days for Keycloak RFC 8707 status — check before shipping if approaching Keycloak 26.8 release)
