---
title: MCP v4 OAuth 2.1 Design
status: draft
milestone: "v10.4 MCP v4: OAuth 2.1 + GraphRAG Stability"
requirement: OAUTH-01
governs: "Phases 66-70"
authored: "2026-06-14"
author: "GSD Plan 65-01"
---

# MCP v4 OAuth 2.1 Design

This document is the OAUTH-01 deliverable and the binding contract for all implementation
decisions in Phases 66-70. It describes the full OAuth 2.1 integration for the Agent Brain
MCP v4 milestone. No OAuth code is written, installed, or imported until this document is
reviewed and signed off (Phase 65-02, Security Review Sign-Off).

---

## Spec Version Citation

### Authoritative Baseline

The authoritative normative baseline for this design is **MCP Authorization 2025-11-25**,
fetched verbatim on 2026-06-14 from
`https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization`.

This baseline was re-verified at authoring time on **2026-06-14** via Context7
(`/modelcontextprotocol/modelcontextprotocol`, source reputation: High, benchmark score:
85.1). The live spec as of the authoring date is consistent with the 2025-11-25 version:
CIMD (Client ID Metadata Documents) is the preferred `SHOULD` path; DCR (RFC 7591) is
`MAY`/deprecated/backwards-compat; RFC 8707 Resource Indicators `resource` parameter is
`MUST` in both authorization and token requests; PKCE S256 is mandatory.

### Live Spec Status on 2026-06-14

The live draft authorization specification page was queried on the authoring date
2026-06-14. The fetched content references source files from
`modelcontextprotocol/modelcontextprotocol` at the 2025-11-25 branch and is consistent
with that baseline. **No evidence of the 2026-07-28 RC (MCP-goes-stateless /
no-initialize handshake) was found in the authorization spec content fetched on
2026-06-14.** The stateless migration RC is tracked separately and had not landed in the
normative authorization spec as of the authoring date.

### 2026-07-28 RC Staleness Acknowledgement

A 2026-07-28 Release Candidate is anticipated that would remove the MCP `initialize`
handshake (the "MCP-goes-stateless" migration). This RC is in progress; this design
document is written and must be signed off **before** that RC lands. The staleness risk
is:

- **Session-based auth assumptions:** The current spec defines token validation in the
  context of a session established by the `initialize` handshake. If the 2026-07-28 RC
  removes the `initialize` handshake, session-based token caching strategies may need
  revision. The implementation MUST be designed so that `RequireAuthMiddleware` validates
  the Bearer token on every HTTP request — this is already the recommended approach and
  is stateless by nature, so the MCP stateless RC would not invalidate this design.
- **Mitigation:** Phase 70 (Integration Tests) must re-verify the live spec before
  shipping v10.4. If the 2026-07-28 RC has landed by then, the team must confirm no
  normative MUST-level changes affect the shipped implementation and file an issue if
  amendments are required.

**The design is written against 2025-11-25 and explicitly acknowledges the 2026-07-28 RC
as an anticipated but not-yet-landed spec revision. Implementors MUST re-check the live
spec before shipping Phase 70.**

### Phase 70 Spec Re-Verification (2026-06-22)

**Verification date:** 2026-06-22
**Verified by:** Phase 70 Plan 03 execution (context7 query against
`/modelcontextprotocol/modelcontextprotocol` + `/modelcontextprotocol/python-sdk`)

**(a) 2026-07-28 RC / SEP-2575 (PR #2575) status:**
The RC is published as a formal blog post
(`blog/content/posts/2026-05-21-mcp-2026-07-28-rc.md`) and the SEP-2575 document is in
the `seps/` directory. The RC introduces a stateless protocol core, an Extensions
framework, and "enhanced authorization aligned with OAuth and OpenID Connect". As of
2026-06-22 the normative authorization spec document has NOT been updated to mark the
2025-11-25 baseline as superseded — the RC is an announced release candidate, not yet
the normative stable spec. The RC target date (2026-07-28) has not yet passed.

**(b) Auth-logic impact of the stateless RC:**
SEP-2575 ("Stateless MCP") explicitly states: *"Without a session handshake, each
request in stateless MCP must be independently authenticated and authorized.
Implementations must ensure that authentication is not bypassed by removing the
initialization phase. This proposal does not introduce additional security concerns
beyond per-request authentication."* This CONFIRMS the design's assumption. The
`RequireAuthMiddleware` in this implementation already validates the Bearer token on
every `/mcp` HTTP request, independently of the `initialize` handshake. No auth-logic
change is required for Phase 70.

**(c) mcp Python SDK version in pyproject.toml:**
`^1.27.2` (floor set in Phase 67 Plan 01). The Python SDK context7 result shows
new extension classes (`ClientCredentialsOAuthProvider`, `PrivateKeyJWTOAuthProvider`)
and a migration guide note about `OAuthClientMetadata.application_type="web"` for
non-localhost redirect URIs. The core `RequireAuthMiddleware`, `BearerAuthBackend`,
`OAuthClientProvider`, and `create_auth_routes()` APIs show no breaking changes
from the Phase 67–70 implementation baseline. **No SDK bump is required for Phase 70.**
If the 2026-07-28 RC lands and ships with a new `mcp` Python SDK release (anticipated
v1.28.0+), a follow-up issue should evaluate whether any auth API changes require
amendment — file as part of the v10.4.1 patch planning.

**(d) Conclusion:**
`RequireAuthMiddleware` validates Bearer tokens per-request, independently of the
`initialize` handshake. This is stateless by nature and forward-compatible with the
2026-07-28 RC's stateless protocol core. **No auth-logic change required for Phase 70.**
The Phase 70 obligation (re-verify before shipping v10.4) is CLOSED.

---

## Framing: Wire + Configure + Mint, Not Build-From-Scratch

### What the MCP SDK Already Provides

The `mcp` Python SDK at version `>= 1.27.2` (current stable: 1.27.2, released 2026-05-29)
ships complete OAuth protocol machinery on both sides. This milestone does **not** build
OAuth from scratch; it wires, configures, and mints JWTs against existing SDK primitives:

**Authorization Server (AS) side — `mcp.server.auth`:**
- `OAuthAuthorizationServerProvider` — abstract base; implement its 9 methods to plug in
  custom token issuance, storage, and client registration.
- `create_auth_routes()` — creates the full AS route set: `/authorize`, `/token`,
  `/register` (DCR/CIMD), `/.well-known/oauth-authorization-server`.

**Resource Server (RS) side — `mcp.server.auth`:**
- `RequireAuthMiddleware` — Starlette ASGI middleware that enforces Bearer token presence
  on all wrapped routes; issues 401 with `WWW-Authenticate` on missing/invalid tokens.
- `BearerAuthBackend` — Starlette authentication backend that validates the Bearer token
  and populates `request.state.auth` with claims (including `scopes`).

**Client side — `mcp.client.auth`:**
- `OAuthClientProvider` (implementing `httpx.Auth`) — handles the full client-side
  401-dance: PRM discovery, AS metadata discovery, PKCE S256 code challenge generation,
  authorization code flow with loopback callback, token refresh.

### Library Additions to Record (Not Install This Phase)

These libraries are the intended additions for Phases 66-70. They are recorded here as
the binding choice for implementation phases. Do NOT install or import them until the
applicable implementation phase.

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| `PyJWT[crypto]` | `^2.13` | JWT signing (RS256) + JWKS-cached verify | Replaces python-jose (abandoned 2021, Python 3.10+ compat failures) |
| `authlib` | `^1.7.2` | OAuth grant handlers for `OAuthAuthorizationServerProvider` impl | Released 2026-05-06; no DPoP — matches deferral decision |
| `pwdlib[argon2]` | `>=0.2` | Argon2id password hashing for co-located AS user store | Replaces passlib (unmaintained) |
| `PyJWKClient` | bundled with PyJWT | Split-AS JWKS verification (5-min TTL + kid-miss refresh) | |
| `itsdangerous` | `^2.2` | CSRF state token signing for authorization code flow | Likely already a Starlette transitive dep — verify before adding |

**Do NOT use:**
- `python-jose` — abandoned since 2021; Python 3.10+ compatibility issues confirmed.
- `passlib` — unmaintained.
- `fastapi-users` — opinionated coupling; harder to compose with existing structure.

---

## Threat Model

> **Dominant risk class: Authorization CONFUSION, not authentication bypass.**
>
> All four converged risks identified during research are authorization confusion
> attacks — situations where a valid token is misused at the wrong service, wrong
> scope, or wrong layer. This framing drives the countermeasures in Phases 66-70.

### Risk 1: Confused-Deputy / Token Passthrough (OAUTH-08)

**Attack:** The MCP server receives a valid OAuth Bearer token from the MCP client and
naively forwards it as the authorization header on outgoing calls to the `agent-brain-server`
REST API. The REST API sees a token issued for the MCP server and may (if poorly
configured) accept it — making the MCP server a confused deputy that acts on behalf of
the client against a backend it controls.

**Why this is the dominant class:** Confused-deputy attacks are the most frequently
exploited class in service-to-service architectures. The confusion arises because
developers conflate the two independent auth layers: (1) client → MCP server (OAuth
Bearer) and (2) MCP server → REST API (API key). The symmetry of "Bearer token in, Bearer
token out" is a natural but incorrect implementation pattern.

**Mitigation (mandatory for Phase 67):** The MCP server MUST use `AGENT_BRAIN_API_KEY`
in the `X-API-Key` header on all calls to `agent-brain-server`. The client's OAuth
access token MUST be consumed and validated at the MCP boundary and MUST NOT be set on
the outgoing REST call. An integration test (Phase 70) MUST assert that the outgoing
REST call carries `X-API-Key` and does not carry the OAuth access token.

**OAUTH-01 reference:** See Token Termination Data Flow section.

---

### Risk 2: aud-Claim Omission (OAUTH-08, OAUTH-05)

**Attack:** The RS validates the token's signature, expiry, and issuer — but does not
validate the `aud` (audience) claim. An attacker who has a valid Bearer token for a
different service (e.g., a token issued to access a logging API) presents it to the MCP
RS. The RS accepts it because the signature is valid and the token has not expired.

**Why this is the dominant class:** `aud` omission is the single most common OAuth RS
implementation error. It is also the error that RFC 8707 Resource Indicators were
specifically designed to prevent: by binding the `aud` claim in every issued JWT to the
canonical resource URI, and requiring the RS to validate `aud` on every inbound token,
cross-service token reuse is structurally prevented.

**Mitigation (mandatory for Phase 67):** Every issued JWT MUST have an `aud` claim bound
to `AGENT_BRAIN_OAUTH_RESOURCE` (the canonical MCP server URI). The RS MUST validate
`aud == AGENT_BRAIN_OAUTH_RESOURCE` on every inbound token and MUST reject tokens where
`aud` does not match. The `resource` parameter MUST be sent in both `/authorize` and
`/token` requests (RFC 8707).

---

### Risk 3: Well-Known-Behind-Auth Deadlock

**Attack (or misconfiguration):** The `/.well-known/oauth-protected-resource`,
`/.well-known/oauth-authorization-server`, and `/.well-known/jwks.json` endpoints are
accidentally placed behind `RequireAuthMiddleware`. A new MCP client tries to start the
OAuth dance — it needs to fetch PRM to discover the AS, but the PRM endpoint requires a
token the client does not yet have. The OAuth dance cannot start. The system is
permanently deadlocked for any new client.

**Why this is the dominant class:** This is a mount-order bug that is trivially introduced
by wrapping the entire Starlette app with middleware before adding the well-known routes.
The bug is not visible in unit tests that only test the happy path (authenticated calls)
and can silently ship in a build where the developer tested from a browser that retained
a token from a previous session.

**Mitigation (mandatory for Phase 66):** Well-known routes (`/.well-known/*`, `/authorize`,
`/token`, `/healthz`, `/mcp/subscriptions`) MUST be added to the Starlette `routes` list
BEFORE the app is wrapped with `RequireAuthMiddleware`. Phase 66's primary acceptance
test is `curl /.well-known/oauth-protected-resource` without a token returning 200. No
further Phase 67 work proceeds until this test passes.

---

### Risk 4: Per-Tool Scope Escalation

**Attack:** The RS middleware validates that the request carries a valid Bearer token with
any valid scope — but does not validate that the token's scope includes the scope required
by the specific MCP tool being called. A client with only `agent-brain:read` scope calls
`cancel_job` (which requires `agent-brain:admin`). The tool dispatches and executes the
privileged operation.

**Why this is the dominant class:** Middleware-level "is authenticated" checks are easier
to implement than per-tool scope guards, and the scope-escalation gap is not visible in
basic smoke tests that use a full-scope admin token. The gap is only caught when testing
with a minimal-scope token against a privileged tool.

**Mitigation (mandatory for Phase 68):** Every MCP tool MUST be guarded by
`require_scope(scope)` at the dispatch layer, keyed to the `TOOL_SCOPE_REQUIREMENTS`
table co-located with `_tool_matrix.py`. Insufficient scope MUST return HTTP 403 with
`WWW-Authenticate: Bearer error="insufficient_scope"` — NOT 401 (which signals an invalid
or missing token, and would incorrectly trigger a re-authentication flow rather than a
scope-upgrade flow).

---

## AS / RS / Public-Route Boundary

### Architecture Diagram

The following diagram shows the Starlette ASGI app in `agent_brain_mcp/http.py` with the
critical auth boundary. Auth-EXEMPT routes are mounted BEFORE the auth middleware
wraps the app.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Starlette ASGI App  (agent_brain_mcp/http.py :: build_asgi_app())  │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  AUTH-EXEMPT ROUTES  (mounted BEFORE RequireAuthMiddleware)   │   │
│  │                                                                │   │
│  │  GET /.well-known/oauth-protected-resource  → PRM (RFC 9728) │   │
│  │  GET /.well-known/oauth-authorization-server → OASM (RFC 8414)│   │
│  │  GET /.well-known/jwks.json  → RS256 public key (custom route)│   │
│  │  GET|POST /authorize          → AS authorization endpoint     │   │
│  │  POST /token                  → AS token endpoint             │   │
│  │  POST /register               → AS client registration (CIMD) │   │
│  │  GET /healthz                 → liveness probe (no auth)      │   │
│  │  GET /mcp/subscriptions       → Phase-64 debug endpoint       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  RequireAuthMiddleware  (wraps the MCP mount only)            │   │
│  │                                                                │   │
│  │  POST /mcp  → MCP Streamable HTTP transport (auth-ENFORCED)   │   │
│  │              └── BearerAuthBackend validates Bearer token      │   │
│  │              └── populates request.state.auth.scopes           │   │
│  │              └── dispatch → tool handler → scope_guard check   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### /mcp/subscriptions Auth-Exemption Scope

The boundary diagram lists `GET /mcp/subscriptions` as auth-exempt. This endpoint was
added in Phase 64 as a debug/monitoring route. For v10.4 and beyond, this exemption MUST
be intentional and documented:

- If `/mcp/subscriptions` returns only non-sensitive operational metadata (active
  subscription counts, no user-specific data), auth-exemption is acceptable for
  observability purposes.
- If `/mcp/subscriptions` returns any client-specific data (which subscriptions a
  particular user has, subscription content, or job-related data), it MUST be moved
  behind `RequireAuthMiddleware` in `oauth` mode.

**Phase 66 action required:** Audit `/mcp/subscriptions` response contents before
finalizing its auth-exempt status. If in doubt, put it behind auth — it can be exempted
later, but a data-exposure bug shipped in an auth-exempt endpoint is harder to walk back.

### Mount-Order Constraint (Critical)

The SDK's `create_auth_routes()` output and the custom `/.well-known/jwks.json` route
MUST be added to the Starlette `routes` list BEFORE the `Starlette` app instance is
created and BEFORE the app is wrapped with `RequireAuthMiddleware`. The pseudo-code
contract:

```python
# CORRECT — well-known routes precede middleware
routes = build_well_known_routes(config)  # returns auth-exempt routes
routes += [Route("/mcp", mcp_handler)]
app = Starlette(routes=routes)
if auth_mode == "oauth":
    app = RequireAuthMiddleware(app, backend=BearerAuthBackend(verifier))
```

Reversing this order — wrapping the app first, then adding routes — places `/.well-known/`
behind auth enforcement and deadlocks the OAuth dance (Risk 3 above).

### SDK Gap: No Built-In JWKS Endpoint

The MCP SDK does NOT ship a `GET /.well-known/jwks.json` endpoint. The co-located AS
MUST add a custom public route that exposes the RS256 public key as a JWKS JSON document.
This route MUST be mounted in the auth-exempt section and MUST NOT require a Bearer token.
This is a known SDK gap to be addressed in Phase 67.

### PKCE S256-Only: Advertisement Is Insufficient — Rejection Required

The OASM MUST include `code_challenge_methods_supported: ["S256"]` so that compliant MCP
clients know S256 is the only supported method. However, advertising S256 is not sufficient
on its own: the co-located AS MUST actively REJECT any `/authorize` request where
`code_challenge_method` is `plain` or is absent. Specifically:

- If `code_challenge_method=plain` is received: respond HTTP 400 with
  `error=invalid_request`, `error_description="PKCE plain method not supported"`.
- If `code_challenge` is present but `code_challenge_method` is absent: reject the request
  (absence implies the default, which in OAuth 2.0 was `plain`; in OAuth 2.1 PKCE is
  mandatory and S256 is the only permissible method).
- If `code_challenge` is entirely absent: reject the request — PKCE is mandatory for all
  public clients per OAuth 2.1 and the MCP 2025-11-25 spec.

This explicit rejection gate MUST be a Phase 66/67 contract test (not just an OASM
advertisement check), because a non-compliant or malicious client may ignore the
advertisement and submit `plain` anyway.

### Token Validation on `/mcp`

When a request reaches `/mcp`, the following checks MUST pass in order:

1. Bearer token present in `Authorization: Bearer <token>` header
2. Token signature valid (RS256, verified against JWKS)
3. Token not expired (`exp` claim)
4. Token `iss` matches the configured issuer (`AGENT_BRAIN_OAUTH_ISSUER` or co-located AS URL)
5. Token `aud` == `AGENT_BRAIN_OAUTH_RESOURCE` (canonical MCP server URI, RFC 8707)
6. Token `scope` satisfies the per-tool `require_scope()` guard

Failure at checks 1-5: HTTP 401 with `WWW-Authenticate: Bearer resource_metadata="..."`.
Failure at check 6: HTTP 403 with `WWW-Authenticate: Bearer error="insufficient_scope", scope="<required>", resource_metadata="..."`.

---

## Token Termination Data Flow

### Overview

There are exactly **two independent, non-overlapping auth layers** in the v10.4
architecture. They MUST NOT be conflated or bridged.

```
Layer 1: MCP Client → MCP Server
         Authorization: Bearer <oauth_access_token>
         (OAuth 2.1 Bearer token; validated at MCP boundary; NEVER forwarded)

Layer 2: MCP Server → agent-brain REST API
         X-API-Key: <AGENT_BRAIN_API_KEY>
         (Static API key; unchanged from SECURITY-01 / v10.2.1)
```

### Sequence Diagram

```
MCP Client                MCP Server (agent_brain_mcp)      agent-brain-server (REST API)
    │                               │                                   │
    │── POST /mcp ──────────────────►                                   │
    │   Authorization: Bearer <tok>  │                                   │
    │                               │ validate tok (BearerAuthBackend)  │
    │                               │   - sig ✓, exp ✓, aud ✓          │
    │                               │   - populate request.state.auth   │
    │                               │   - scope_guard check             │
    │                               │                                   │
    │                               │── POST /query ────────────────────►
    │                               │   X-API-Key: AGENT_BRAIN_API_KEY  │
    │                               │   (OAuth token NOT forwarded)     │
    │                               │                                   │
    │                               │◄── 200 OK ────────────────────────│
    │◄── 200 MCP result ────────────│                                   │
```

### Termination Contract (OAUTH-08)

The client's OAuth access token:
- MUST be validated at the MCP server boundary (signature, expiry, issuer, audience, scope)
- MUST be consumed at the MCP boundary and NOT forwarded to any downstream service
- MUST NOT appear in the `Authorization` or `X-API-Key` header on outgoing REST calls

The MCP server's outbound call to `agent-brain-server`:
- MUST use `AGENT_BRAIN_API_KEY` in the `X-API-Key` header, exactly as it does in
  SECURITY-01 (v10.2.1 `docs/plans/2026-06-05-issue-179-api-key-auth.md`)
- MUST NOT send the OAuth Bearer token as the auth credential on the REST leg
- This invariant applies in ALL three auth modes (`none`, `basic`, `oauth`): the
  MCP-to-REST leg ALWAYS uses `AGENT_BRAIN_API_KEY` via `X-API-Key`. The mode toggle
  controls the MCP client → MCP server boundary only. No mode may change the outbound
  credential on the MCP server → REST API leg.

This contract prevents the confused-deputy attack (Risk 1 above, OAUTH-08). An automated
integration test in Phase 70 MUST assert:
- outgoing REST call carries `X-API-Key: <value>`
- outgoing REST call does NOT carry `Authorization: Bearer <oauth_access_token>`
- this assertion MUST be verified for all three auth modes, not just `oauth` mode

### Why Two Independent Layers

The `agent-brain-server` REST API is a local/LAN service; its `AGENT_BRAIN_API_KEY`
auth model is the SECURITY-01 shared-secret LAN bridge. The MCP server is the remote
access boundary where OAuth 2.1 authorization is enforced. These two trust boundaries
operate at different network layers and MUST remain independent. Forwarding the OAuth
token to the REST API would:
1. Make the REST API depend on OAuth infrastructure it is not configured to validate.
2. Allow a token issued to one MCP client to make arbitrary REST calls if the OAuth
   validation is ever relaxed on the REST side.
3. Constitute a confused-deputy vulnerability exploitable by a rogue MCP client.

---

## Scope-to-Tool Mapping

### Overview

Agent Brain v10.4 defines **4 OAuth scopes** covering all **16 MCP tools** (plus
subscription channels). This table is the conceptual single-source-of-truth, co-located
with `_tool_matrix.py` in the MCP package. Any tool added to the registry MUST be
assigned to a scope in `_tool_matrix.py`; a drift guard test at import time detects
unassigned tools.

**Scope semantics:** a token with scope `S` MAY call any tool in scope `S`. A token
with insufficient scope receives HTTP 403 with
`WWW-Authenticate: Bearer error="insufficient_scope"` — NOT 401 (the token is valid;
the scope is not sufficient for the requested tool).

**Drift guard — fail loudly at import time (mandatory for Phase 68):** Any tool registered
in `_tool_matrix.py` that does not have a corresponding entry in `TOOL_SCOPE_REQUIREMENTS`
MUST raise a `RuntimeError` at module import time (not merely in a test run). This ensures
a tool added without a scope assignment can never silently pass scope enforcement — the
server will refuse to start with an actionable error. The error message MUST name the
unassigned tool(s). Relying only on test-time detection is insufficient because tests may
not be run between a commit and a deploy.

### Scope Table

| Scope | Tools Covered |
|-------|--------------|
| `agent-brain:read` | `search_documents`, `explain_result`, `get_corpus_status`, `cache_status`, `list_folders`, `list_file_types`, `list_jobs`, `get_job` — plus all MCP resource reads (`corpus://`, `job://`) and all registered prompts |
| `agent-brain:index` | `index_folder`, `add_documents`, `inject_documents`, `wait_for_job` |
| `agent-brain:admin` | `cancel_job`, `remove_folder`, `clear_cache` |
| `agent-brain:subscribe` | Guards the SUB-01..05 subscription machinery: `corpus://status`, `corpus://folders`, `job://<job_id>` subscriptions |

Total: 8 read tools + 4 index tools + 3 admin tools + subscription channel = 15 named
tools + the subscribe scope guarding subscription channels = the 16-tool surface
co-located with `_tool_matrix.py`.

### Insufficient Scope Response

When a tool call fails scope validation the RS MUST return:

```
HTTP 403 Forbidden
WWW-Authenticate: Bearer error="insufficient_scope",
                         scope="agent-brain:admin",
                         resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"
```

The `scope` field names the REQUIRED scope (not the token's scope). The `resource_metadata`
field allows the client to re-discover the AS and request a higher scope. The HTTP status
MUST be 403, not 401. Using 401 here is incorrect: a 401 signals invalid or missing
credentials, which would trigger a re-authentication flow. A 403 signals valid credentials
with insufficient permissions, which triggers a scope-upgrade (step-up authorization) flow.

---

## Canonical Resource URI Contract

### Definition

`AGENT_BRAIN_OAUTH_RESOURCE` is the single environment variable that defines the canonical
URI of the MCP server. It is used:
- By the AS: to bind the `aud` claim in every issued JWT (Resource Indicators, RFC 8707)
- By the RS: to validate `aud` on every inbound Bearer token
- By the PRM (`/.well-known/oauth-protected-resource`): as the `resource` field
- By the client: as the `resource` parameter in both `/authorize` and `/token` requests

### RFC 8707 Rules

Per RFC 8707 (Resource Indicators for OAuth 2.0):
1. The `resource` parameter MUST be included in both the authorization request (`/authorize`)
   and the token request (`POST /token`).
2. The AS MUST bind the `aud` claim in the issued JWT to the value of the `resource`
   parameter.
3. The RS MUST validate that the `aud` claim in the inbound token equals the canonical
   resource URI. Tokens where `aud` does not match MUST be rejected.

### Format Rules

The canonical resource URI MUST conform to RFC 8707 Section 2:
- MUST have a URI scheme (`https://` in production; `http://` permitted for loopback only)
- MUST NOT contain a fragment (`#`)
- SHOULD omit a trailing slash

**Worked Example:**
```
AGENT_BRAIN_OAUTH_RESOURCE=https://mcp.example.com/mcp
```

This value appears as:
- `aud: "https://mcp.example.com/mcp"` in every issued JWT
- `resource: "https://mcp.example.com/mcp"` in client authorization and token requests
- `"resource": "https://mcp.example.com/mcp"` in the PRM JSON document

### Startup Gate: AGENT_BRAIN_OAUTH_RESOURCE Must Be Non-Empty in oauth Mode

When `AGENT_BRAIN_AUTH=oauth`, the server startup gate MUST verify that
`AGENT_BRAIN_OAUTH_RESOURCE` is set, non-empty, and syntactically valid as a URI with a
scheme. If the env var is absent or empty, the startup gate MUST refuse to start (log a
critical error and exit with code 2). **Rationale:** If `AGENT_BRAIN_OAUTH_RESOURCE` is
not set, the RS would validate `aud == ""` or `aud == None`, effectively disabling
audience validation and allowing any token with a valid signature to be accepted by any
AS — the exact `aud`-omission attack Risk 2 is designed to prevent.

This startup gate is a mandatory Phase 66 contract (co-located with the `AGENT_BRAIN_AUTH`
toggle validation already described in the Auth-Mode Toggle section).

### Anti-Patterns to Avoid

- **Trailing-slash inconsistency:** `https://mcp.example.com/mcp` and
  `https://mcp.example.com/mcp/` are different strings. A token issued for the trailing-slash
  URI will fail `aud` validation against the non-trailing-slash RS. The canonical URI is
  the authoritative form; it MUST be consistent everywhere.
- **Hard-coding:** Never hard-code the canonical URI in code. It MUST always derive from
  `AGENT_BRAIN_OAUTH_RESOURCE` at runtime.
- **No-scheme URIs:** `mcp.example.com/mcp` is not a valid resource URI. The scheme is
  required.
- **Empty env var:** `AGENT_BRAIN_OAUTH_RESOURCE=""` is not a valid fallback. The startup
  gate MUST reject an empty value in `oauth` mode (see Startup Gate section above).

---

## Registration Policy: CIMD over DCR

### Decision

**Client ID Metadata Documents (CIMD)** is the preferred (`SHOULD`) registration path
for this milestone, used alongside static pre-registration for the self-hosted single-user
shape.

**Dynamic Client Registration (DCR, RFC 7591)** is `MAY`/deprecated in the 2025-11-25
MCP Authorization spec (retained for backwards compatibility only). DCR may be shipped
as a CIMD fallback at most, or omitted entirely for the single-user shape. This decision
is locked (65-CONTEXT.md).

This satisfies ROADMAP SC#4: explicit CIMD-vs-DCR decision recorded.

### CIMD Registration Flow

On CIMD registration, the AS receives a `client_id` that is a URL (e.g.,
`https://mcp-client.example.com/.well-known/mcp-client`). The AS fetches this URL to
retrieve the client's metadata JSON document.

### SSRF Mitigation (Mandatory)

The AS MUST validate the `client_id` URL against a **domain allowlist** before fetching
it. Without this check, an attacker can register a client with a `client_id` URL pointing
to an internal network resource (e.g., `http://169.254.169.254/latest/meta-data/` — AWS
IMDS) and cause the AS to exfiltrate the metadata.

Required controls:
1. Parse the `client_id` URL and extract the hostname.
2. Validate the hostname against a configured `AGENT_BRAIN_OAUTH_CLIENT_ID_ALLOWLIST`
   (list of trusted domains or CIDR ranges).
3. Reject registration with HTTP 400 if the hostname is not in the allowlist.
4. Block private IP ranges (`10.x`, `172.16-31.x`, `192.168.x`, `127.x`, `169.254.x`,
   `::1`, link-local) unconditionally, regardless of the allowlist.
5. Set a short HTTP timeout (e.g., 5s) on the fetch to prevent slowloris-style DoS.
6. **DNS rebinding mitigation (mandatory):** After DNS resolution and immediately before
   the HTTP fetch, re-validate that the resolved IP address is NOT a private/loopback/
   link-local address. Allowlist hostname validation alone is insufficient because an
   attacker can register `evil.allowlisteddomain.com` with DNS that temporarily resolves
   to `169.254.169.254` (DNS rebinding). The implementation MUST use a library or custom
   wrapper that performs post-resolution IP validation (e.g., a custom `httpx` transport
   that intercepts the connection attempt after DNS resolution and checks the IP). Phase 67
   MUST include a test that asserts a `client_id` whose DNS resolves to an RFC-1918 address
   is rejected even when the hostname passes the allowlist check.

SSRF prevention is a security MUST for any AS that supports CIMD registration (Phase 67).

---

## DPoP Deferral Rationale

### Decision: DPoP Deferred to v10.5+

DPoP (Demonstrating Proof-of-Possession, RFC 9449) is **forced-deferred to v10.5+**.
It will NOT be implemented in this milestone (v10.4, Phases 66-70).

### Rationale

1. **No production-grade Python DPoP library exists as of 2026-06-14.** The primary
   Python OAuth library, Authlib, has an open feature request for DPoP support (issue #315,
   open since 2021). No release has shipped DPoP support as of the authoring date.

2. **DPoP is NOT in the MCP Authorization core spec (2025-11-25).** DPoP lives in the
   optional/additive `ext-auth` extensions repository, separate from the normative core
   authorization specification. It is not a MUST requirement of the current spec.

### No MUST Violation

**Deferring DPoP to v10.5+ does NOT violate any current-spec MUST.** This is confirmed
by the authoritative baseline (MCP Authorization 2025-11-25): DPoP is an optional
extension in the `ext-auth` repo and carries no normative MUST obligation in the core
spec. Implementing OAuth 2.1 without DPoP is fully spec-compliant for this milestone.

This satisfies ROADMAP SC#4: DPoP deferral confirmed to violate no current-spec MUST.

### Re-evaluation Trigger for v10.5+

Re-evaluate DPoP when any of the following are true:
- Authlib issue #315 is closed with a shipped DPoP implementation
- An alternative production-grade Python DPoP library is available
- The MCP core spec upgrades DPoP from optional/additive to a normative MUST

---

## Auth-Mode Toggle and Deployment Shapes

### AGENT_BRAIN_AUTH Toggle

`AGENT_BRAIN_AUTH` is a runtime environment variable controlling the authentication mode
for the MCP server. The three modes are **mutually exclusive** and managed by a startup
gate that rejects invalid combinations.

| Value | Mode | Description |
|-------|------|-------------|
| `none` | **Default** | No authentication. Preserves all pre-v10.4 behavior. Suitable for local/loopback-only deployments. No token validation, no middleware. |
| `basic` | **LAN Bridge** | Formalizes the v10.2.1 SECURITY-01 shared-secret Bearer path. Uses `AGENT_BRAIN_API_KEY` via `X-API-Key` header. Suitable for LAN deployments behind a firewall. |
| `oauth` | **Full OAuth 2.1** | Full OAuth 2.1 with PKCE S256, Resource Indicators, CIMD registration, and per-tool scope enforcement. Required for remote/internet-exposed deployments. |

**Startup gate:** At server startup in `build_asgi_app()`, the auth mode is read from
`AGENT_BRAIN_AUTH`. If the value is not in `{none, basic, oauth}`, the server logs a
critical error and exits with code 2. The three modes are mutually exclusive — the
dependency injection system wires exactly ONE auth dependency via `get_auth_dependency()`
based on the toggle value. A request can never be validated by more than one auth layer.

**`basic` mode details:** In `basic` mode, `AGENT_BRAIN_AUTH=basic` uses the
`AGENT_BRAIN_API_KEY` (static Bearer) path formalized in SECURITY-01. This is the LAN
bridge that preserves the existing security posture for local network deployments. The
MCP-to-REST leg also uses `AGENT_BRAIN_API_KEY` via `X-API-Key` (unchanged from
SECURITY-01).

### Deployment Shape A: Co-Located AS + RS (Phases 66-69)

In this topology, a single `agent-brain-mcp` binary serves both the Authorization Server
(AS) and the Resource Server (RS) endpoints.

```
┌─────────────────────────────────────────────────────────┐
│  agent-brain-mcp (single binary, AGENT_BRAIN_AUTH=oauth) │
│                                                           │
│  AS endpoints (auth-exempt):                              │
│  - GET /.well-known/oauth-authorization-server            │
│  - GET /.well-known/oauth-protected-resource              │
│  - GET /.well-known/jwks.json  (CUSTOM ROUTE — SDK gap)   │
│  - GET|POST /authorize                                    │
│  - POST /token                                            │
│  - POST /register                                         │
│                                                           │
│  RS endpoint (auth-enforced):                             │
│  - POST /mcp  (RequireAuthMiddleware + BearerAuthBackend) │
│                                                           │
│  Token store: IN-MEMORY                                   │
│  JWT signing: PyJWT RS256 (private key in memory)         │
│  JWKS endpoint: custom route (public key only)            │
└─────────────────────────────────────────────────────────┘
```

**Key trade-offs for co-located AS:**

- **In-memory token store:** Access tokens, refresh tokens, and authorization codes are
  stored in process memory. A process restart invalidates all active sessions. Users must
  re-authenticate after a server restart. **This is a known trade-off — document
  explicitly in operator guides** so operators are not surprised by session loss on deploy.
- **SDK JWKS gap:** The `mcp` SDK does NOT provide `GET /.well-known/jwks.json`. The
  co-located AS MUST add a custom FastAPI/Starlette route that serializes the RS256
  public key as a JWKS JSON document. This route MUST be mounted in the auth-exempt
  section.
- **No introspection required:** Since the AS and RS are co-located and share the JWT
  signing key, the RS can verify tokens locally without network calls. Token introspection
  (RFC 7662) is only needed for the split AS/RS topology (Phase 70).

**Token lifecycle:** Access tokens expire after 15 minutes. Refresh tokens are rotating
with a 30-day validity. All MCP clients are public clients (per spec); PKCE S256 is
mandatory.

### Client-Side Token Storage: FileTokenStorage chmod 0o600 Required (Pattern A)

`McpHttpBackend` uses Pattern A (a fresh subprocess/client per MCP tool call). An
in-memory `TokenStorage` is discarded on each call, re-triggering the full browser OAuth
dance (redirect, user interaction) on every invocation. `FileTokenStorage` keyed to
`state_dir/mcp-oauth-tokens.json` MUST be used to persist the token across Pattern A
invocations.

**Security requirement (mandatory for Phase 69):** The `FileTokenStorage` implementation
MUST create its token file with permissions `0o600` (owner-read/write only). Creating it
with default umask permissions (typically `0o644`) exposes OAuth tokens to any local user
on the system. The implementation MUST call `os.chmod(path, 0o600)` immediately after
creating or writing the file. A test MUST assert the file is not world-readable after a
token is stored.

### Deployment Shape B: Split AS / RS (Phase 70)

In this topology, `agent-brain-mcp` is the RS only. The AS is an external IdP (Keycloak,
Auth0, Cognito, etc.).

```
┌──────────────────────────────────┐     ┌──────────────────────────────┐
│  External IdP (e.g. Keycloak)    │     │  agent-brain-mcp (RS only)   │
│                                  │     │                               │
│  - /authorize                    │     │  RS endpoint (auth-enforced): │
│  - /token                        │     │  - POST /mcp                  │
│  - /.well-known/openid-config    │     │                               │
│  - /jwks.json                    │     │  JwksTokenVerifier:           │
│                                  │     │  - PyJWKClient (5-min TTL)    │
└──────────────────────────────────┘     │  - kid-miss on-demand refresh │
          │  issues JWT                  │  - leeway=30s (clock skew)    │
          ▼                              │                               │
  MCP Client ──── Bearer JWT ───────────► RS validates via JWKS          │
                                        └──────────────────────────────┘
```

**Key implementation notes for Phase 70:**
- `JwksTokenVerifier` uses `PyJWKClient` with a 5-minute TTL cache and `kid`-miss
  on-demand refresh (prevents JWKS rotation cache stampede).
- Token introspection (`IntrospectionTokenVerifier`, RFC 7662) as fallback for opaque
  tokens (e.g., Keycloak opaque tokens when JWT is disabled).
- Clock skew tolerance: `leeway=30s` in JWT validation.
- Keycloak 22+: RFC 8707 Resource Indicators must be explicitly enabled per-client in
  the Keycloak realm configuration — verify before Phase 70 CI setup.

### Deferred Items

The following items are explicitly out of scope for v10.4 and must be recorded here so
they are not silently omitted:

1. **DPoP (RFC 9449)** — deferred to v10.5+ (see DPoP Deferral Rationale section).

2. **SEP-1880 per-tool scope enforcement proposal** — this is an open proposal, not in
   the 2025-11-25 MCP Authorization spec. Agent Brain's per-tool scope enforcement is
   `scope_guard`-based (a `require_scope(scope)` callable at the tool dispatch layer),
   not SEP-1880. If SEP-1880 is standardized in a future spec revision, it may replace
   the `scope_guard` approach.

3. **Device Authorization Grant (RFC 8628)** — the MCP spec does not require the Device
   Authorization Grant for MCP clients. PKCE + loopback redirect is the MCP-specified
   path. The Device Grant is deferred as a future consideration for headless/non-interactive
   deployment scenarios.

4. **Audit log middleware** — may need its own milestone. Not required for OAUTH-01..12.

5. **Token revocation endpoint (RFC 7009)** — admin UX convenience for operator-initiated
   session invalidation. Not a normative MUST for this milestone; consider for v10.4.1.

---

## Security Review Sign-Off

> **Status: ADVERSARIAL REVIEW COMPLETE — Awaiting Human Sign-Off**

An independent adversarial security review of this design document was conducted by
GSD Plan 65-02 on 2026-06-14. The review probed each of the four threat-model risks
plus five additional security probes. Seven findings were identified; all have been
resolved by edits applied directly to the relevant sections of this document (recorded
below). The document is now ready for human sign-off.

No Phase 66+ implementation code may be committed until the project owner has signed off
in the "Human Sign-Off" subsection below.

Review status: COMPLETE

---

### Adversarial Review Findings

**Reviewer:** GSD Plan 65-02 (independent structured adversarial read — 2026-06-14)
**Method:** Adversarial structured read against all four threat-model risks plus five
additional probes from the 65-PLAN review_targets block and SUMMARY.md "Gaps to Address."

---

#### Risk 1: Confused-Deputy / Token Passthrough (OAUTH-08)

**Finding: PASS with one precision gap — GAP CLOSED**

The "Token Termination Data Flow" section provides a sequence diagram, a two-layer
architecture explanation, and a termination contract. Phase 70 integration tests are
mandated to assert the outgoing REST call carries `X-API-Key` and NOT the OAuth token.

**Gap found:** The termination contract said the `AGENT_BRAIN_API_KEY`/`X-API-Key`
invariant applies "in SECURITY-01" but did not explicitly state it applies in ALL three
auth modes (`none`, `basic`, `oauth`). A developer reading the doc could interpret the
constraint as OAuth-mode-specific, missing that the MCP-to-REST leg is ALWAYS API-key
authenticated regardless of the mode toggle.

**Resolution (applied):** The "Termination Contract (OAUTH-08)" section was updated to
explicitly state: "This invariant applies in ALL three auth modes (`none`, `basic`,
`oauth`). The mode toggle controls the MCP client → MCP server boundary only." The Phase
70 integration test assertion was also updated to verify all three auth modes, not just
`oauth` mode.

**Residual risk:** None. The confused-deputy design is unambiguous.

---

#### Risk 2: aud-Claim Omission (OAUTH-08, OAUTH-05)

**Finding: PASS with one critical missing startup gate — GAP CLOSED**

The "Canonical Resource URI Contract" section correctly specifies RFC 8707 `resource`
parameter requirements, `aud` binding in issued JWTs, and RS-side `aud` validation. The
token validation sequence (steps 1-6) explicitly calls out `aud == AGENT_BRAIN_OAUTH_RESOURCE`
as step 5.

**Gap found:** The document did not specify what happens when `AGENT_BRAIN_OAUTH_RESOURCE`
is not set (absent or empty). If the env var is missing, the RS would evaluate
`aud == ""` or `aud == None`, which either rejects all tokens (DoS) or silently disables
audience validation depending on implementation (critical security failure). This is the
exact attack Risk 2 is designed to prevent, re-introduced through a missing config check.

**Resolution (applied):** A new "Startup Gate: AGENT_BRAIN_OAUTH_RESOURCE Must Be
Non-Empty in oauth Mode" subsection was added to the Canonical Resource URI Contract
section: when `AGENT_BRAIN_AUTH=oauth`, the startup gate MUST verify `AGENT_BRAIN_OAUTH_RESOURCE`
is set, non-empty, and syntactically valid as a URI with a scheme; on failure, exit code
2 with a critical log. The "Anti-Patterns to Avoid" section was also updated to include
`AGENT_BRAIN_OAUTH_RESOURCE=""` as an explicit anti-pattern.

**Residual risk:** None. The aud validation chain is now specified end-to-end including
the startup precondition.

---

#### Risk 3: Well-Known-Behind-Auth Deadlock

**Finding: PASS with one ambiguity requiring a Phase 66 audit action**

The "AS / RS / Public-Route Boundary" section includes a boundary diagram listing all
auth-exempt routes, the correct mount-order constraint with pseudo-code, and Phase 66's
primary acceptance test (`curl /.well-known/oauth-protected-resource` without a token
returning 200). The mount-order constraint is clearly stated and specific enough to
prevent the deadlock pattern in Phase 66 implementation.

**Gap found:** The boundary diagram lists `GET /mcp/subscriptions` as auth-exempt. This
endpoint was added in Phase 64 as a debug route. The doc did not specify what data this
endpoint returns or whether its auth-exemption was intentional in `oauth` mode. If
`/mcp/subscriptions` returns any client-specific data (job IDs, user subscription state),
an auth-exempt placement leaks that data to any unauthenticated caller.

**Resolution (applied):** A new "/mcp/subscriptions Auth-Exemption Scope" subsection was
added to the AS/RS Boundary section: Phase 66 MUST audit `/mcp/subscriptions` response
contents before finalizing its auth-exempt status, with the explicit guidance that if
in doubt, the endpoint should be placed behind auth.

**Residual risk:** Low. The audit action is required before Phase 66 ships. The well-known
deadlock for OAuth discovery routes is fully mitigated.

---

#### Risk 4: Per-Tool Scope Escalation

**Finding: PASS with one implementation gap — GAP CLOSED**

The "Scope-to-Tool Mapping" section defines all 4 scopes × 16 tools, specifies HTTP 403
on insufficient scope (not 401), and names the `scope_guard` pattern at the dispatch
layer. The scope table covers all 16 tools explicitly.

**Gap found:** The doc said "a drift guard test at import time detects unassigned tools."
Relying on test-time detection means a developer can add a tool to `_tool_matrix.py`,
skip running tests, and ship an unguarded tool to production. The guarantee needs to be
at module import time (server startup), not test run time.

**Resolution (applied):** The Scope-to-Tool Mapping section was updated: the drift guard
MUST raise a `RuntimeError` at module import time (not merely in a test run) if any tool
in `_tool_matrix.py` lacks a `TOOL_SCOPE_REQUIREMENTS` entry. This prevents the server
from starting with an unguarded tool.

**Residual risk:** None. The scope escalation gap is structurally closed by import-time
enforcement.

---

#### Additional Probe: CIMD SSRF Allowlist Completeness

**Finding: GAP FOUND — CLOSED**

The "SSRF Mitigation (Mandatory)" subsection correctly mandates an allowlist, blocking
private IP ranges, and a request timeout. However, it did not address DNS rebinding
attacks: an attacker can register a hostname that passes the allowlist check (`evil.mycompany.com`)
but has DNS that temporarily resolves to `169.254.169.254` (AWS IMDS) at fetch time.
The hostname-only allowlist is insufficient against this attack class.

**Resolution (applied):** A control #6 was added to the SSRF Mitigation list:
"After DNS resolution, re-validate that the resolved IP is NOT a private/loopback/
link-local address." The implementation MUST use post-resolution IP validation in the
HTTP transport layer. Phase 67 MUST include a test asserting a `client_id` whose DNS
resolves to an RFC-1918 address is rejected even when the hostname is on the allowlist.

**Residual risk:** Low. Requires careful implementation of the DNS rebinding mitigation
in Phase 67 (the test gate captures any omission).

---

#### Additional Probe: FileTokenStorage chmod 0o600

**Finding: GAP FOUND — CLOSED**

The research SUMMARY explicitly identified `FileTokenStorage` with `chmod 0o600` as
required for Pattern A token persistence. The design doc's architecture section mentioned
`FileTokenStorage keyed to state_dir` but did not specify the file permission requirement.
On a multi-user system, default umask permissions (`0o644`) would expose OAuth tokens to
any local user.

**Resolution (applied):** A new "Client-Side Token Storage: FileTokenStorage chmod 0o600
Required (Pattern A)" subsection was added to the Auth-Mode Toggle and Deployment Shapes
section. It specifies that `FileTokenStorage` MUST create its token file with `0o600`
permissions via `os.chmod()` immediately after creation/write, and a test MUST assert
the file is not world-readable.

**Residual risk:** None. The file permission requirement is now explicit and testable.

---

#### Additional Probe: PKCE S256-Only — Advertisement vs. Rejection

**Finding: GAP FOUND — CLOSED**

The doc mandated `code_challenge_methods_supported: ["S256"]` in the OASM and stated
"PKCE S256 mandatory." However, advertising S256 in OASM is not the same as rejecting
requests that submit `plain` — a malicious or non-compliant client that ignores the
advertisement and submits `code_challenge_method=plain` would not be blocked unless the
AS explicitly rejects it.

**Resolution (applied):** A new "PKCE S256-Only: Advertisement Is Insufficient — Rejection
Required" subsection was added to the AS/RS Boundary section. The AS MUST actively REJECT
`/authorize` requests where `code_challenge_method=plain`, where `code_challenge_method`
is absent, or where `code_challenge` itself is absent. Each case must return HTTP 400 with
`error=invalid_request`. This must be a Phase 66/67 contract test, not just an OASM
advertisement check.

**Residual risk:** None. The S256-only enforcement is now specified at the protocol level.

---

#### Additional Probe: In-Memory Token Store Restart Trade-Off

**Finding: PASS — adequately documented**

The deployment shapes section explicitly calls out the in-memory token store trade-off:
"A process restart invalidates all active sessions. Users must re-authenticate after a
server restart. This is a known trade-off — document explicitly in operator guides."

No gap found. This is a documented design decision, not an undisclosed risk.

---

#### Additional Probe: 2026-07-28 RC Staleness Acknowledgement

**Finding: PASS — explicitly and accurately documented**

The "Spec Version Citation" section explicitly acknowledges the 2026-07-28 RC, states
it had not landed in the authorization spec as of the authoring date, and mandates that
Phase 70 must re-verify the live spec before shipping. The mitigation (stateless-by-nature
`RequireAuthMiddleware` validates every HTTP request independently of the `initialize`
handshake) is correct.

No gap found.

---

### Summary of Findings

| # | Risk / Probe | Verdict | Action |
|---|-------------|---------|--------|
| 1 | Confused-deputy / token passthrough | PASS with gap | GAP CLOSED: termination contract updated to cover all 3 auth modes |
| 2 | aud-claim omission | PASS with gap | GAP CLOSED: startup gate added for missing AGENT_BRAIN_OAUTH_RESOURCE |
| 3 | Well-known-behind-auth deadlock | PASS with audit item | Phase 66 action added: audit /mcp/subscriptions auth-exempt status |
| 4 | Per-tool scope escalation | PASS with gap | GAP CLOSED: drift guard changed from test-time to import-time RuntimeError |
| 5 | CIMD SSRF allowlist | GAP | GAP CLOSED: DNS rebinding mitigation (post-resolution IP check) added as control #6 |
| 6 | FileTokenStorage chmod 0o600 | GAP | GAP CLOSED: 0o600 permission requirement added with test assertion |
| 7 | PKCE S256-only rejection | GAP | GAP CLOSED: AS rejection gate added for plain/absent challenge method |
| 8 | In-memory token store trade-off | PASS | Adequately documented; no action needed |
| 9 | 2026-07-28 RC staleness | PASS | Explicitly acknowledged with mitigation; no action needed |

**All gaps have been closed by edits applied to the relevant sections of this document.**
The design as amended is ready for human sign-off and Phase 66 implementation.

---

### Human Sign-Off

> **Status: APPROVED**

By signing off, the project owner confirms:
- The threat model is accurate and the four converged risks are adequately mitigated
  by the countermeasures defined in this document (including the seven gap-fixes applied
  by the adversarial review).
- The scope-to-tool mapping is correct and complete.
- The CIMD-over-DCR decision is accepted.
- The DPoP deferral is accepted.
- The canonical resource URI contract (`AGENT_BRAIN_OAUTH_RESOURCE`) is understood,
  including the startup gate requirement that rejects a missing/empty value in `oauth` mode.
- The FileTokenStorage `chmod 0o600` requirement is accepted.
- The PKCE S256-only rejection requirement is accepted.
- The DNS rebinding SSRF mitigation requirement is accepted.
- Phase 66+ implementation may begin once this section reads APPROVED.

**Status: APPROVED**

_Approver: Rick Hightower (project owner)_
_Date: 2026-06-14_
_Conditions: None — approved as the binding design contract for Phases 66-70. The seven adversarial-review gap-fixes (DNS-rebinding SSRF post-resolution IP check, empty-`AGENT_BRAIN_OAUTH_RESOURCE` startup gate, import-time scope drift guard, PKCE `plain` rejection, FileTokenStorage `0o600`, all-mode token-termination contract, `/mcp/subscriptions` exemption audit) are accepted as binding requirements on the downstream phases._
