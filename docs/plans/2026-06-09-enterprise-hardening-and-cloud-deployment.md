---
title: Enterprise Hardening + Cloud Deployment Design
status: planning
date: 2026-06-09
author: Rick Hightower
scope: agent-brain-server, agent-brain-mcp, deployment, skills
primary_target: GCP single-instance container + Cloud SQL (pgvector)
followups: AWS, Azure, horizontal scaling, split tiers, in-house MCP control plane
related:
  - docs/roadmaps/mcp/v4-oauth-for-remote.md   # issue #188 — OAuth pulled forward
  - docs/roadmaps/mcp/README.md                # MCP meta-roadmap
  - docs/DEPLOYMENT.md
  - docs/POSTGRESQL_SETUP.md
---

# Enterprise Hardening + Cloud Deployment Design

> **This is a planning document only.** No code, no IaC, and no `.planning/` phase
> directories are produced by it. It defines the design, the phased roadmap, and the
> follow-up issues to seed later. Implementation is picked up phase-by-phase, each behind
> its own `task before-push` + `task pr-qa-gate` gate.

---

## 1. Context — why this exists

Agent Brain today is a **single-developer, loopback-trust** system. The PostgreSQL + pgvector
backend (`agent-brain-server/agent_brain_server/storage/postgres/`) is genuinely
production-grade — HNSW vector search (cosine / L2 / inner-product), `tsvector` full-text,
async SQLAlchemy pool with retry — but everything *around* it assumes a trusted local machine:

- The FastAPI server defaults to loopback and only optionally checks an `X-API-Key`.
- The MCP server has **zero authentication** — any client that reaches its HTTP port gets
  all 15 tools, including the 5 that mutate or delete corpus state.
- Credentials live in `.env` files / `DATABASE_URL`; there is no secrets-manager integration.
- There is no server `Dockerfile`, no IaC, and no cloud deployment path.

The June-2026 enterprise MCP direction is the opposite of "everyone runs local servers on
laptops." The dominant pattern is to **treat MCP servers like privileged internal APIs**:
centrally governed, identity-aware, least-privilege, audited, and fronted by a gateway
(Cloudflare's reference architecture; the MCP 2025-11-25 authorization + security-best-practices
specs). Local MCP servers are increasingly viewed as *high risk* (RCE incidents, supply-chain,
poor admin visibility).

**Goal of this doc:** close the gap between "runs on a laptop" and "runs as governed remote
infrastructure," delivering a **GCP single-instance reference deployment first**, with AWS and
Azure as phased follow-ups — and shipping **deployment skills** so users can reproduce each.

### 1.1 Intended outcome

- Agent Brain runs as a single, pinned, governed container in the cloud with managed
  Postgres+pgvector, secrets from a vault, identity at the edge, and **per-tool authorization +
  audit inside the MCP server** (defense in depth — the gateway cannot do identity propagation
  for us).
- Operators get copy-pasteable IaC and a `deploying-agent-brain-gcp` skill.
- A clear, phased path exists for AWS/Azure and for eventual horizontal scale-out.

### 1.2 Hardening baseline (verified against the code, 2026-06-09)

| Area | Exists today | Gap to close |
|------|--------------|--------------|
| Postgres / pgvector | `storage/postgres/{config,connection,schema,vector_ops,keyword_ops}.py`; `schema.py:71` runs `CREATE EXTENSION IF NOT EXISTS vector` | `connection.py:62` `create_async_engine` has **no `connect_args`/SSL**; no IAM auth; creds via `DATABASE_URL`/YAML only |
| Secrets | env vars + `.env`; `runtime.json` chmod `0o600` | **No secrets-manager integration** (GCP Secret Manager / AWS Secrets Manager / Azure Key Vault) |
| FastAPI auth | loopback startup gate (`api/main.py` `_check_api_key_startup_gate`); optional constant-time `X-API-Key` (`api/security.py`) | `CORS allow_origins=["*"]` (`api/main.py:753`); no TLS in-process; no rate limit; no request/audit log; unstructured `basicConfig` (`api/main.py:65`) |
| MCP transport | loopback-only HTTP + DNS-rebinding protection (`http.py`); subprocess hygiene — pinned cwd, env allowlist, SIGTERM→SIGKILL (Phase 60) | — (good; needs auth before public exposure) |
| **MCP auth** | **none** | No authn, no per-tool authz, no scope model, no audit. OAuth roadmapped to v4 (#188), unbuilt |
| Mutating tools | `index_folder`, `add_documents`, `inject_documents`, `remove_folder`, `cancel_job`, `clear_cache` — only Pydantic `confirm: Literal[True]` gates | **No default-deny on writes**; all 15 tools visible/callable by any client |
| Multi-instance | file-lock single-writer per state dir (`locking.py`, `fcntl`); local JSON job queue | Conflicts with autoscaling → **drives the single-instance compute decision** |
| Deploy | `templates/docker-compose.postgres.yml` (Postgres only); PyPI publish CI | No server `Dockerfile`, no IaC, no k8s/Helm, no cloud deploy |

### 1.3 Locked decisions (from requirements Q&A)

1. **Compute = single-instance container** (Cloud Run `min=max=1`, or one k8s pod). This
   preserves `locking.py`'s single-writer invariant and the local job queue. Horizontal scaling
   and split read/write tiers are **spec'd as follow-ups**, not built now.
2. **MCP governance = server-side OAuth 2.1 + per-tool authz + audit, behind a managed gateway.**
   Pull the v4 OAuth design (#188) forward into the MCP server; let the gateway own
   SSO / MFA / device-posture. Smallest correct net-new Python footprint.
3. **Cloud = GCP first**, AWS + Azure phased, each with its own **deployment skill**.

---

## 2. Target architecture (GCP single-instance reference)

```
MCP / API client
  │  HTTPS
  ▼
Google Cloud Load Balancer + IAP        ← identity-aware gateway: SSO, MFA, context-aware access,
  │  (signed identity header / OIDC)        device posture, group-based access, edge audit
  ▼
Cloud Run service "agent-brain"  (ingress=internal-and-cloud-load-balancing, min=max=1)
  ├─ agent-brain-serve   FastAPI :8000   — X-API-Key + CORS allowlist + structured/audit logs
  └─ agent-brain-mcp     Streamable HTTP :8765 — OAuth 2.1 Bearer (audience-bound) +
  │                                            per-tool authz (default-deny writes) +
  │                                            tools/list filtering + audit log
  ▼
Cloud SQL for PostgreSQL + pgvector     ← private IP (Serverless VPC connector),
  (HNSW + tsvector)                         IAM database auth via Auth Proxy / Python Connector
  ▼
Secret Manager                          ← OPENAI/ANTHROPIC keys, AGENT_BRAIN_API_KEY, DB creds
Cloud Logging / Monitoring              ← structured app logs + audit events → SIEM export
```

**Defense-in-depth principle:** IAP authenticates the *human/workload at the edge*, but the MCP
server still performs **identity propagation, per-tool authorization, and audit**. We do **not**
let the MCP server become a generic service-account proxy, and we **reject token passthrough**
(the MCP server validates that the token's `aud` is itself). This is exactly the anti-pattern the
MCP security spec warns about.

Why single-instance is *correct*, not a shortcut: `locking.py` uses `fcntl` advisory locks and a
local JSON job queue scoped to one `.agent-brain/` state dir. A second replica would either
corrupt that state or silently fail to coordinate. Cloud SQL holds the vector data (durable,
shared-ready), but the **writer/coordinator must be single** until the lock + queue move into
Postgres (see §10 follow-ups). Cloud Run `min=max=1` enforces exactly that.

---

## 3. Cloud Postgres + pgvector access (explicit ask)

### 3.1 Add TLS/SSL + IAM to the connection layer

**Files:** `storage/postgres/config.py`, `storage/postgres/connection.py`.

- Extend `PostgresConfig` with SSL fields: `ssl_mode` (`disable|require|verify-ca|verify-full`),
  `ssl_root_cert`, `ssl_cert`, `ssl_key`. asyncpg does **not** read `sslmode` from the URL the
  way psycopg does — build a `ssl.SSLContext` and pass it via `create_async_engine(...,
  connect_args={"ssl": ctx})` at `connection.py:62`.
- Add a `connection_strategy` selector with two managed options for GCP (others in §7):
  - **Cloud SQL Auth Proxy sidecar** *(recommended for the single container)* — the proxy
    terminates TLS and performs IAM auth; the app connects to `127.0.0.1:5432` in-pod. Zero
    cert handling in Python.
  - **`cloud-sql-python-connector`** with `enable_iam_auth=True` (passwordless IAM DB auth) —
    integrates directly with the async engine via a custom `creator`/`async_creator`.
- Keep the current `DATABASE_URL` / YAML path as the **local-dev / non-cloud** default.

### 3.2 pgvector enablement is already handled

`schema.py:71` already issues `CREATE EXTENSION IF NOT EXISTS vector;`. Cloud SQL for PostgreSQL,
AWS RDS (≥ PG 15.2), and Azure Flexible Server all support pgvector via their extension
allowlists — so the only operator step is enabling the extension on the instance / flag
(`cloudsql.enable_pgvector`-style flag or allowlist entry), which the deploy skill will script.

### 3.3 Credentials never in `.env` for prod

DB credentials (or, preferably, **no password at all** via IAM auth) are resolved through the
secrets abstraction in §4, not from `DATABASE_URL` in a committed/mounted file.

---

## 4. Secrets management abstraction (net-new)

**Files:** new module under `agent_brain_server/config/` (e.g. `secrets.py`); wired into
`settings.py` + `provider_config.py`.

- A pluggable resolver: `env` (current default, unchanged behavior), `gcp-secret-manager`,
  `aws-secrets-manager`, `azure-key-vault`.
- Selected by `AGENT_BRAIN_SECRETS_BACKEND`; secret *references* use a `secret://...` syntax
  (e.g. `secret://gcp/projects/PROJ/secrets/openai-key/versions/latest`).
- Resolves: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` (and other provider keys),
  `AGENT_BRAIN_API_KEY`, and the DB credential set.
- **Reuse** the existing `provider_config.py` precedence chain (`api_key` field → `api_key_env`)
  as the fallback so nothing breaks for local users.
- Maps the enterprise control: *"Vault-managed; no user-local `.env` secrets for production."*

---

## 5. FastAPI server hardening

**File:** `api/main.py` (+ `api/security.py`).

| Control | Change | Location |
|---------|--------|----------|
| CORS | Replace `allow_origins=["*"]` with `AGENT_BRAIN_CORS_ORIGINS` allowlist; default empty (deny) | `api/main.py:753` |
| Structured logging | Replace `basicConfig` with JSON formatter + correlation-ID injection | `api/main.py:65` |
| Request/audit middleware | Per-request log: principal, route, status, latency, correlation ID; log auth decisions distinctly | new middleware in `api/main.py` |
| Rate limiting | Per-API-key / per-IP limiter middleware | new middleware |
| TLS | Terminate at the gateway (documented); optional uvicorn `certfile/keyfile` for non-gateway installs | docs + `main.py` startup |
| Metrics *(medium)* | Optional `/metrics` Prometheus endpoint | new router |

The loopback startup gate and constant-time `X-API-Key` check already exist and stay — the API
key becomes the **service-to-service credential between the gateway and FastAPI**, sourced from
the secrets backend.

---

## 6. MCP server-side authN + authZ + audit (core of the hardening)

This is where most net-new security logic lands. It pulls the v4 OAuth roadmap (#188) forward.

**Files:** `agent_brain_mcp/http.py`; **new siblings** `agent_brain_mcp/security/auth.py` and
`agent_brain_mcp/security/authz.py`; new `agent_brain_mcp/audit.py`; wired into
`tools/__init__.py` (dispatch) and `server.py` (`tools/list` handler).

> ⚠️ **Do not modify `agent_brain_mcp/security/__init__.py`.** It is a deliberate *pure
> re-export shim* for the server-side `file_sandbox` (single source of truth, "SHARE, do not
> fork"). New auth/authz logic goes in **sibling modules**, never in the shim.

### 6.1 Authentication — OAuth 2.1 Bearer on Streamable HTTP

- Validate Bearer JWTs: **audience-bound** (verify `aud == this MCP server`), short-lived,
  signature-verified against the IdP's JWKS. **Reject token passthrough.**
- Serve OAuth 2.0 **Protected Resource Metadata** at `/.well-known/oauth-protected-resource`
  per MCP spec 2025-11-25, so clients can discover the authorization server.
- IdP is pluggable: Google Identity (GCP), Entra (Azure), Cognito (AWS), or any generic OIDC.
- **stdio transport stays local-trust** (documented) — it runs as a child of a trusted local
  client; subprocess hygiene from Phase 60 already covers it.

### 6.2 Authorization — progressive least privilege

Scope model (illustrative):

```
mcp:discover        corpus:search       corpus:index
corpus:inject       corpus:remove       jobs:read
jobs:cancel         cache:read          cache:clear
```

- **Default-deny** on the 5 mutating tools (`index_folder`, `add_documents`, `inject_documents`,
  `remove_folder`, `cancel_job`/`clear_cache`) unless the caller's token carries the matching
  write scope. Read tools require the relevant read scope.
- Decision tuple, enforced server-side at dispatch:
  `principal + client + tool + resource + scope → allow / deny / require-approval`.
- Avoid wildcard / omnibus scopes (`corpus:*`); log scope elevation.

### 6.3 Progressive tool disclosure

Filter `tools/list` by the caller's scopes — high-risk tools are **invisible** until policy
allows. This implements the "don't dump every tool schema into model context" / Code-Mode-lite
control (security + token-cost win), wired into the `server.py` list handler.

### 6.4 Audit logging

**File:** new `agent_brain_mcp/audit.py`. Emit one structured JSON event per tool call:
`{principal, client, tool, resource, scope, decision, correlation_id, result_status, ts}` →
stdout → Cloud Logging → SIEM export. This is the single biggest observability gap today.

### 6.5 Step-up / approval for high-risk tools *(spec now, build later)*

`remove_folder`, `clear_cache`, and `inject_documents` (arbitrary enrichment scripts) require an
**elevated scope or an approval flag** beyond the existing `confirm: Literal[True]`.

### 6.6 Web-security fundamentals once HTTP is publicly reachable

- Non-deterministic session IDs bound to identity; never use a session as authentication.
- Keep DNS-rebinding protection (already present).
- SSRF/egress note: the MCP server makes no outbound calls except to the local backend; document
  egress allowlists at the gateway/VPC level.

---

## 7. AWS + Azure (described, phased — not built now)

| Concern | GCP (primary) | AWS (follow-up) | Azure (follow-up) |
|---------|---------------|-----------------|-------------------|
| Managed Postgres + pgvector | Cloud SQL for PostgreSQL | RDS for PostgreSQL (≥ PG15.2) | Azure DB for PostgreSQL Flexible Server |
| DB auth | IAM auth (Auth Proxy / Python Connector) | RDS IAM auth (+ optional RDS Proxy) | Managed Identity |
| Vector ext enablement | enable `vector` | enable `vector` | `azure.extensions` allowlist |
| Compute (single-instance) | Cloud Run `min=max=1` | ECS Fargate (desired=1) / App Runner | Container Apps (min=max=1) |
| Secrets | Secret Manager | Secrets Manager | Key Vault |
| Identity-aware gateway | LB + IAP | ALB + Cognito / API Gateway authorizer | App Gateway + Entra / APIM |
| Logs → SIEM | Cloud Logging | CloudWatch | Azure Monitor |
| Skill | `deploying-agent-brain-gcp` | `deploying-agent-brain-aws` | `deploying-agent-brain-azure` |

---

## 8. Hardening checklist → agent-brain file mapping

| Control area | Control | Where it lands |
|--------------|---------|----------------|
| Auth | OAuth 2.1 / OIDC, SSO, MFA, PRM | Gateway (IAP) + `security/auth.py` + `/.well-known/oauth-protected-resource` |
| Tokens | Audience-bound, short-lived, no passthrough, no broad scopes | `security/auth.py` (aud check), scope model in `security/authz.py` |
| Authorization | Per-tool, per-resource, per-user, server-side | `security/authz.py` + `tools/__init__.py` dispatch |
| Tool exposure | Progressive disclosure | `server.py` `tools/list` filter |
| Writes | Default-deny + audit events | dispatch guard + `audit.py` |
| Secrets | Vault-managed; no user-local `.env` in prod | `config/secrets.py` (§4) |
| Runtime | Remote, containerized, single-instance, patched | `Dockerfile` + Cloud Run (§9 P5) |
| Network | Egress allowlists, loopback/gateway, CORS allowlist | gateway/VPC + `api/main.py:753` |
| Data (DLP) | Redaction, classification-aware responses | **follow-up** (§10) |
| Logging | Tool-call audit (user, client, resource, scope, result) | `audit.py` + FastAPI request middleware |
| Governance | Approved registry; owner/review per server | **follow-up** (in-house control plane, §10) |
| Detection | Shadow-MCP / unauthorized servers | **follow-up** (§10) |
| Testing | Prompt-injection, SSRF, auth-bypass, replay | per-phase test suites |

---

## 9. Phased roadmap (outline only — no phase dirs created yet)

- **Phase 1 — Secrets + Postgres TLS/IAM (GCP):** secrets abstraction (§4); SSL fields + IAM
  connection strategy on the Postgres layer (§3); Cloud SQL pgvector enablement.
- **Phase 2 — FastAPI hardening:** CORS allowlist, structured logging + correlation IDs,
  request/audit middleware, rate limiting (§5).
- **Phase 3 — MCP authentication:** OAuth 2.1 Bearer validation + Protected Resource Metadata +
  audience binding (§6.1).
- **Phase 4 — MCP authorization + audit:** scope model, per-tool default-deny, `tools/list`
  filtering, audit log (§6.2–6.4).
- **Phase 5 — GCP deploy artifacts + skill:** multi-stage `Dockerfile`; Terraform for Cloud Run
  (`min=max=1`) + Cloud SQL + Secret Manager + VPC connector + IAP; `deploying-agent-brain-gcp`
  skill (fits the `configuring-agent-brain` / `using-agent-brain` family).
- **Phase 6 — Step-up approval + observability:** elevated-scope/approval for high-risk tools
  (§6.5); optional `/metrics`; SIEM export wiring.

Each phase, when implemented, carries its own `task before-push` + `task pr-qa-gate`; deploy
phases additionally require `terraform plan` + a Cloud Run smoke test.

---

## 10. Follow-up issues → seed in `.planning/todos/pending/`

Captured as TODO stubs (`.planning/todos/pending/`, convention `YYYY-MM-DD-slug.md`) **and filed
as GitHub issues** — spec'd here but not built in this effort:

1. **AWS reference deployment + `deploying-agent-brain-aws` skill** (RDS + ECS/App Runner +
   Secrets Manager + Cognito/API GW). — [#200](https://github.com/SpillwaveSolutions/agent-brain/issues/200)
2. **Azure reference deployment + `deploying-agent-brain-azure` skill** (Flexible Server +
   Container Apps + Key Vault + Entra/APIM). — [#201](https://github.com/SpillwaveSolutions/agent-brain/issues/201)
3. **Horizontal scaling:** move the `fcntl` lock + local JSON job queue into Postgres
   (advisory locks / queue table) — unblocks multi-replica. Touches `locking.py` + job queue. — [#202](https://github.com/SpillwaveSolutions/agent-brain/issues/202)
4. **Split read/write tiers:** one indexer/writer instance + N read-only query replicas;
   read/write DB role separation. — [#203](https://github.com/SpillwaveSolutions/agent-brain/issues/203)
5. **Full in-house MCP control plane:** internal registry/portal, policy engine, **shadow-MCP
   detection** (monitor `/mcp`, `/mcp/sse`, JSON-RPC `initialize`/`tools/call`/`prompts/get`),
   per-group tool exposure. — [#204](https://github.com/SpillwaveSolutions/agent-brain/issues/204)
6. **DLP / classification-aware response redaction.** — [#205](https://github.com/SpillwaveSolutions/agent-brain/issues/205)

---

## 11. Verification (for this planning pass)

This pass is planning-only; "done" means the doc is correct and actionable:

1. ✅ Doc exists at `docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md`.
2. Every hardening control maps to a file/module that actually exists (cross-checked against the
   live code on 2026-06-09: `schema.py:71`, `api/main.py:753`/`:65`, `connection.py:62`,
   `security/__init__.py` shim).
3. The GCP topology is internally consistent — single-instance preserves `locking.py`; the Cloud
   SQL access path (Auth Proxy / Connector + IAM) is named.
4. Follow-up TODO stubs are enumerated for `.planning/todos/pending/`.
5. Repo convention honored (per `CLAUDE.md`): the plan lives under `docs/plans/`; no code touched,
   so `task before-push` is N/A this pass and is noted as the gate for every implementation phase.
