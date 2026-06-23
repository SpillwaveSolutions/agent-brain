# Split AS/RS Deployment Guide

Operator documentation for deploying `agent-brain-mcp` in split Authorization
Server / Resource Server (AS/RS) mode — where an external IdP (e.g. Keycloak)
issues tokens and the MCP server acts only as the RS.

Phase 70 implementation. Design doc: `docs/plans/2026-06-14-mcp-v4-oauth-design.md`.

---

## Deployment Shapes

### Shape A: Co-Located AS+RS (default)

The MCP server is both the AS (issues tokens, hosts `/authorize`, `/token`,
`/.well-known/jwks.json`) and the RS (validates tokens on `/mcp`).

Use when: building a self-contained demo, local development, or when you do not
have an external IdP. Set `AGENT_BRAIN_AUTH=oauth` with `AGENT_BRAIN_OAUTH_RESOURCE`
and NO `AGENT_BRAIN_OAUTH_JWKS_URI` or `AGENT_BRAIN_OAUTH_INTROSPECTION_URL`. The
verifier selector (`build_verifier()`) falls back to `LocalRs256Verifier`, which
validates tokens signed by the server's own RS256 keypair.

### Shape B: Split AS / RS (external IdP)

The external IdP (e.g. Keycloak, Auth0, Okta) acts as the AS. The MCP server acts
ONLY as the RS — it validates inbound Bearer tokens but does not issue them. The
`/authorize`, `/token`, and `/register` endpoints on the MCP server are NOT used; the
IdP owns the authorization code flow.

Use when: integrating with an existing enterprise IdP, deploying in production with
Keycloak, or when the token issuer and resource server are operated by different teams.

---

## Environment Variables

All variables are read at startup by `build_asgi_app()` via `config.py`.

| Variable | Required | Description |
|---|---|---|
| `AGENT_BRAIN_AUTH` | Yes | Set to `oauth` to enable OAuth mode. |
| `AGENT_BRAIN_OAUTH_RESOURCE` | Yes (oauth mode) | Canonical MCP server URI. Bound as the `aud` claim in issued/validated tokens (RFC 8707). Must be a non-empty URI with a scheme. Example: `https://mcp.example.com/mcp`. The startup gate exits code 2 if unset when `AGENT_BRAIN_AUTH=oauth`. |
| `AGENT_BRAIN_OAUTH_ISSUER` | Recommended | The external IdP issuer URI. MUST equal the `iss` claim in tokens exactly, including the realm path for Keycloak (see Pitfall 7 below). Example: `http://idp:8080/realms/agent-brain`. |
| `AGENT_BRAIN_OAUTH_JWKS_URI` | Split AS/RS | If set, selects `JwksTokenVerifier`. Points at the IdP's public JWKS endpoint. Example: `http://idp:8080/realms/agent-brain/protocol/openid-connect/certs`. **Takes precedence over `INTROSPECTION_URL` if both are set.** |
| `AGENT_BRAIN_OAUTH_INTROSPECTION_URL` | Split AS/RS (opaque tokens) | If set (and `JWKS_URI` is not set), selects `IntrospectionTokenVerifier` for RFC 7662 token introspection. Use for opaque tokens that cannot be validated locally. |
| `AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID` | With introspection | RS client ID for the introspection endpoint (Basic auth). |
| `AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET` | With introspection | RS client secret for the introspection endpoint. |

### Verifier Selector Precedence

`build_verifier()` selects the verifier class based on these env vars (highest wins):

1. `AGENT_BRAIN_OAUTH_JWKS_URI` set → `JwksTokenVerifier` (remote JWKS, JWT validation)
2. `AGENT_BRAIN_OAUTH_INTROSPECTION_URL` set → `IntrospectionTokenVerifier` (RFC 7662)
3. Neither set → `LocalRs256Verifier` (co-located AS/RS fallback — Shape A)

### Example: Keycloak Split Mode

```bash
export AGENT_BRAIN_AUTH=oauth
export AGENT_BRAIN_OAUTH_RESOURCE=https://mcp.example.com/mcp
export AGENT_BRAIN_OAUTH_ISSUER=http://idp:8080/realms/agent-brain
export AGENT_BRAIN_OAUTH_JWKS_URI=http://idp:8080/realms/agent-brain/protocol/openid-connect/certs
agent-brain-mcp
```

### Example: Opaque Token Introspection

```bash
export AGENT_BRAIN_AUTH=oauth
export AGENT_BRAIN_OAUTH_RESOURCE=https://mcp.example.com/mcp
export AGENT_BRAIN_OAUTH_ISSUER=https://idp.example.com
export AGENT_BRAIN_OAUTH_INTROSPECTION_URL=https://idp.example.com/oauth/introspect
export AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_ID=agent-brain-rs
export AGENT_BRAIN_OAUTH_INTROSPECTION_CLIENT_SECRET=<rs-client-secret>
agent-brain-mcp
```

---

## Keycloak Configuration

### Realm Bootstrap

The `scripts/keycloak_bootstrap.sh` script automates realm setup via the Keycloak
Admin REST API. It creates:

- Realm `agent-brain` with direct-access grants enabled
- Public MCP client `agent-brain-mcp` with `directAccessGrantsEnabled=true`
- Confidential RS client `agent-brain-rs` (for introspection endpoint auth)
- Test user `testuser/testpass`
- Four client scopes: `agent-brain:read`, `agent-brain:index`, `agent-brain:admin`,
  `agent-brain:subscribe`
- An `oidc-audience-mapper` (Included Custom Audience) on the `agent-brain-mcp`
  client that binds `aud=AGENT_BRAIN_OAUTH_RESOURCE` in issued JWTs

See the script header comment for the full step-by-step sequence.

### RFC 8707 Deviation: Audience Scope Mapper

**Keycloak lacks native Resource Indicators (RFC 8707) until version 26.8
(unreleased as of June 2026).** The workaround is to bind the `aud` claim via an
audience scope mapper:

1. In the Keycloak Admin UI (or bootstrap script): Client → `agent-brain-mcp` →
   Client Scopes → Add dedicated scope → Mappers → Create mapper of type
   **"Audience"** (or `oidc-audience-mapper` via Admin REST API).
2. Set **"Included Custom Audience"** to the value of `AGENT_BRAIN_OAUTH_RESOURCE`
   (e.g. `http://localhost:8000`).
3. Enable **"Add to access token"**.

This produces JWTs where `aud` equals `AGENT_BRAIN_OAUTH_RESOURCE`, satisfying the
RS-side `aud` validation in `JwksTokenVerifier` and `IntrospectionTokenVerifier`.
The security property is identical to native Resource Indicators: the token is
audience-restricted to the specific RS.

When Keycloak 26.8+ ships with native RFC 8707 support, the mapper can be replaced
by the standard `resource` request parameter — no RS-side code change needed.

### Pitfall 7: Issuer Must Include the Full Realm Path

Keycloak's `iss` claim includes the realm path:

```
http://idp:8080/realms/agent-brain   ← CORRECT
http://idp:8080                       ← WRONG — mismatch → 401
```

Set `AGENT_BRAIN_OAUTH_ISSUER` to the full realm URL including `/realms/<realm>`.

---

## Revocation Behavior

### Split AS/RS path (JwksTokenVerifier / IntrospectionTokenVerifier)

- **IntrospectionTokenVerifier**: token revocation is honored automatically.
  On the next introspection call after a revoke event, the IdP returns
  `active: false` and `IntrospectionTokenVerifier.verify_token()` returns `None`
  (rejected). The RS does not cache `active: true` responses between calls.

- **JwksTokenVerifier**: token revocation is NOT reflected in the JWKS — JWTs
  are stateless and the verifier validates the signature only. For immediate
  revocation with the JWKS path, deploy with the `IntrospectionTokenVerifier`
  instead (or combine with a jti denylist sidecar at the API gateway layer).

### Co-located AS/RS path (LocalRs256Verifier)

Uses the in-memory jti denylist (`InMemoryTokenStore.revoke_by_jti()`). Revocation
is effective immediately within the same server process. The denylist is not
persisted across restarts (suitable for short-lived dev/CI deployments; use the
introspection path for production).

### No Public `/revoke` Endpoint

A public RFC 7009 `/revoke` endpoint is NOT shipped in this phase. The jti denylist
is internal. Revocation for production deployments is delegated to the external IdP
(Shape B). A public `/revoke` endpoint is deferred to v10.4.1.

---

## Token Validation Steps (RS path)

`RequireAuthMiddleware` + `ScopeEnforcementMiddleware` perform these checks on every
`/mcp` request (see design doc §"Token Validation on /mcp"):

1. `Authorization: Bearer <token>` header present — else 401
2. Token signature valid (JWKS kid lookup or introspection `active: true`) — else 401
3. `exp` not in the past (+ 30-second clock skew leeway) — else 401
4. `nbf` not in the future — else 401
5. `iss` matches `AGENT_BRAIN_OAUTH_ISSUER` — else 401
6. `aud` includes `AGENT_BRAIN_OAUTH_RESOURCE` — else 401
7. Scope sufficient for the requested tool (per `TOOL_SCOPE_REQUIREMENTS`) — else **403**
   `WWW-Authenticate: Bearer error="insufficient_scope"`

Step 7 returning **403** (not 401) is the SC#4 scope-boundary contract (OAUTH-06):
authentication passed, authorization failed. Clients MUST NOT retry step 7 failures
without requesting a new token with the required scope.

---

## Related

- Design doc: `docs/plans/2026-06-14-mcp-v4-oauth-design.md` §"Deployment Shape B"
- Keycloak bootstrap: `scripts/keycloak_bootstrap.sh`
- Verifier classes: `agent_brain_mcp/oauth/verifier.py`
- Config reader: `agent_brain_mcp/config.py` (`resolve_split_as_settings()`)
- CI integration test job: `.github/workflows/mcp-keycloak-integration.yml`
