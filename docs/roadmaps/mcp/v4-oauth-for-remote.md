---
roadmap: mcp-v4
status: planned
source_design: docs/plans/2026-05-28-mcp-uds-transport-design.md
milestone: MCP v4 (OAuth for remote)
---

# MCP v4 — OAuth 2.1 for remote Agent Brain instances

> Issue body for `gh issue create --body-file docs/roadmaps/mcp/v4-oauth-for-remote.md`.
> See plan `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v4 row) and §15.3.

## Context

v1–v3 are all localhost-trust. To run Agent Brain remotely (CI box, shared dev server, hosted SaaS) and have MCP clients consume it safely, the resource server needs real auth. Per the current MCP authorization spec, Protected Resource Metadata is required for protected servers; Dynamic Client Registration is MAY (not MUST).

## Scope

### Standards stack

- **OAuth 2.1** (consolidated spec) for authorization grants.
- **PKCE (RFC 7636)** — mandatory for all public clients (every MCP client is public).
- **Protected Resource Metadata (RFC 9728)** — required by MCP spec; exposed at `/.well-known/oauth-protected-resource`.
- **Dynamic Client Registration (RFC 7591)** — MAY per current spec; ship it for ergonomics.
- **Authorization Server Metadata (RFC 8414)** — at `/.well-known/oauth-authorization-server`.
- **Resource Indicators (RFC 8707)** — bind tokens to a specific Agent Brain resource URI.
- **Token Introspection (RFC 7662)**.
- **Revocation (RFC 7009)**.
- **DPoP (RFC 9449)** — optional, for token binding.

### Deployment shapes supported

- **Co-located AS/RS** — single binary, self-hosted single-user; JWT-signed tokens, no introspection.
- **Split AS/RS** — enterprise (Auth0 / Keycloak / Cognito / custom); JWKS-cached verification.

### Scope design

- `agent-brain:read` — all `readOnlyHint: true` tools + resource reads.
- `agent-brain:index` — `index_folder`, `add_documents`, `inject_documents`, `wait_for_job`.
- `agent-brain:admin` — `cancel_job`, `remove_folder`, `clear_cache`.
- `agent-brain:subscribe` — long-lived resource subscriptions.

### Token lifecycle

- 15-min access tokens.
- Rotating 30-day refresh tokens.
- Replay detection (RFC 6749 §10.4).

### MCP client side

- `McpHttpBackend` (from v3) handles the `WWW-Authenticate` challenge and the OAuth dance per spec.

### Server-side

- Middleware in `agent-brain-server` toggled by `AGENT_BRAIN_AUTH=oauth` (default `none`).

### Migration path

- v1.x adds `AGENT_BRAIN_AUTH=basic` (shared secret bearer) as a LAN bridge before full OAuth ships.

## Threat model (must be in design doc)

- **Token theft** via curl/log capture → short-lived access tokens + refresh; DPoP where supported.
- **Replay** → DPoP / TLS-binding / short TTLs.
- **Cross-tenant data leakage** → resource-scoped tokens; `aud` claim validation.
- **Confused deputy** → per-resource token isolation per MCP authorization spec.

## Prerequisites

- v3 shipped (`McpHttpBackend` exists).
- Independent security review of the design doc before implementation.
- Test coverage gate ≥ 90% on the new `oauth/` middleware.

## Definition of done

- Own design doc filed.
- Co-located AS/RS deployment works end-to-end.
- Split AS/RS verified against at least one external IdP (Keycloak in CI).
- `WWW-Authenticate` challenge → MCP client OAuth dance → authorized tool call works against the official MCP SDK client.
- Audit log for every authorized call (separate concern — may need its own milestone).

## Source design

`docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v4 row), §15.3.
