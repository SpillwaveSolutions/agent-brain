---
title: Enterprise GCP-Core Hardening — Execution Plan (#219)
status: planning
date: 2026-06-23
author: Rick Hightower
tracks: "#219"
design_doc: docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md
supersedes_phasing_in: docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md §9
---

# Enterprise GCP-Core Hardening — Execution Plan (#219)

## Context

The Enterprise Hardening design doc (`2026-06-09-...`) defined a 6-phase roadmap for taking Agent
Brain from "laptop loopback-trust" to "governed remote GCP deployment." It was written **before
v10.4 shipped**, so two of its phases are now largely done. This plan **reconciles the design
against the shipped code** (verified 2026-06-23) and lays out only the work that actually remains,
phase-by-phase, each behind `task before-push` + `task pr-qa-gate`.

Goal unchanged: a single, pinned, governed Cloud Run container (`min=max=1`) with managed
Postgres+pgvector, vault-sourced secrets, identity at the edge (IAP), and per-tool authz + audit
inside the MCP server. Single-instance is **by design** — it preserves `locking.py`'s `fcntl`
single-writer invariant and the local JSON job queue (horizontal scale-out is #202, split tiers
#203).

## Reconciliation: what v10.4 already shipped (do NOT rebuild)

| Design §/phase | Shipped in v10.4? | Evidence |
|---|---|---|
| §6.1 / P3 — OAuth 2.1 Bearer authn, PRM/OASM discovery, `aud` binding, confused-deputy | ✅ **Done** | `agent_brain_mcp/oauth/{verifier,provider,registration,scopes,tokens}.py`, `oauth_metadata.py` |
| §6.2 / P4 — 4-scope model, per-tool mapping (single source of truth + import-time drift guard), default-deny dispatch | ✅ **Done** | `oauth/scopes.py` (`require_scope`), `http.py` `ScopeEnforcementMiddleware`, `server.py` `_enforce_scope` |
| §6.3 — Progressive tool disclosure (`tools/list` scope filtering) | ❌ **Not done** | `server.py:304` `list_tools()` returns all 16 tools unfiltered |
| §6.4 — Structured tool-call audit log (`audit.py`) | ❌ **Not done** | no `agent_brain_mcp/audit.py`; v10.4 changelog deferred it ("its own future milestone") |
| §3 / P1 — Postgres TLS/SSL + IAM connection strategy | ❌ **Not done** | no `ssl`/`connect_args` in `storage/postgres/connection.py` |
| §4 / P1 — Secrets abstraction (`config/secrets.py`) | ❌ **Not done** | file absent |
| §5 / P2 — FastAPI CORS allowlist, structured logging, request/audit middleware, rate limit | ❌ **Not done** | `api/main.py:767` `allow_origins=["*"]`; `:65` `basicConfig` |
| §9 P5 — `Dockerfile`, Terraform, IAP, `deploying-agent-brain-gcp` skill | ❌ **Not done** | no server `Dockerfile` |
| §6.5 / P6 — Step-up approval for high-risk tools; `/metrics`; SIEM wiring | ❌ **Not done** | — |

**Net effect:** the design's P3 is complete and P4 is ~80% complete. Remaining GCP-core work =
P1, P2, P5, the two P4 leftovers (`tools/list` filtering + audit log), and P6 (recommend defer).

---

## Execution phases (reconciled)

Sequencing favors **independent, shippable slices** first; the deploy phase (P-E) depends on all
code phases landing. Suggested order: **P-A → P-B → P-C → P-D → P-E**, with P-F deferred.

### Phase P-A — Secrets abstraction + Postgres TLS/IAM  (design P1)
**Why first:** everything else in prod needs vault-sourced creds and an encrypted DB path; it's
self-contained and unblocks the deploy phase.
- New `agent_brain_server/config/secrets.py`: pluggable resolver (`env` default unchanged,
  `gcp-secret-manager` for this milestone), `secret://...` reference syntax, selected by
  `AGENT_BRAIN_SECRETS_BACKEND`. **Reuse** the existing `provider_config.py` precedence chain
  (`api_key` → `api_key_env`) as fallback.
- `storage/postgres/config.py`: add `ssl_mode|ssl_root_cert|ssl_cert|ssl_key` +
  `connection_strategy` selector.
- `storage/postgres/connection.py:62`: build `ssl.SSLContext`, pass via `connect_args={"ssl": ctx}`
  (asyncpg ignores URL `sslmode`); add Cloud SQL strategy (Auth Proxy sidecar = recommended; or
  `cloud-sql-python-connector` with `enable_iam_auth=True`).
- Local-dev `DATABASE_URL`/YAML path stays the default → no break for existing users.

### Phase P-B — FastAPI server hardening  (design P2)
- `api/main.py:767`: replace `allow_origins=["*"]` with `AGENT_BRAIN_CORS_ORIGINS` allowlist
  (default empty = deny).
- `api/main.py:65`: replace `basicConfig` with JSON formatter + correlation-ID injection.
- New request/audit middleware: per-request `{principal, route, status, latency, correlation_id}`;
  log auth decisions distinctly.
- Per-API-key / per-IP rate-limit middleware.
- The existing loopback gate + constant-time `X-API-Key` stay; the key becomes the
  gateway→FastAPI service credential, sourced from P-A's secrets backend.

### Phase P-C — MCP progressive tool disclosure  (design P4 leftover, §6.3)
- `server.py` `list_tools()`: filter the returned tools by the caller's granted scopes
  (`request.state.auth`), reusing `TOOL_SCOPE_REQUIREMENTS` + `require_scope` — high-risk tools are
  invisible until policy allows. Mode-gated to `oauth` (stdio/local-trust returns all, unchanged).
- This is the smallest phase: the scope map and verifier already exist; only the list handler
  changes. Security + token-cost win.

### Phase P-D — MCP tool-call audit log  (design P4 leftover, §6.4)
- New `agent_brain_mcp/audit.py`: one structured JSON event per call
  `{principal, client, tool, resource, scope, decision, correlation_id, result_status, ts}` →
  stdout → Cloud Logging.
- Wire at the dispatch seam in `tools/__init__.py` / `server.py` `call_tool` (where `_enforce_scope`
  already runs). **Do NOT touch `security/__init__.py`** — it is a pure re-export shim ("SHARE,
  do not fork"); new logic goes in sibling modules.

### Phase P-E — GCP deploy artifacts + skill  (design P5)
- Multi-stage server `Dockerfile` (+ pinned base, non-root).
- Terraform: Cloud Run service `min=max=1` (`ingress=internal-and-cloud-load-balancing`), Cloud SQL
  + pgvector enablement, Secret Manager, Serverless VPC connector, LB + IAP.
- `deploying-agent-brain-gcp` skill (fits the `configuring-agent-brain` / `using-agent-brain`
  family).
- Extra gates this phase: `terraform plan` + a Cloud Run smoke test, on top of `before-push`.

### Phase P-F — Step-up approval + observability  *(recommend DEFER to a follow-up)*  (design P6)
- Elevated-scope / approval flag for `remove_folder`, `clear_cache`, `inject_documents` beyond the
  existing `confirm: Literal[True]`.
- Optional `/metrics` Prometheus endpoint; SIEM export wiring.
- **Recommendation:** not required for a correct, governed single-instance GCP deploy; file as a
  separate issue and ship P-A…P-E as the #219 milestone.

---

## Out of scope (explicit follow-ups, already tracked)
- #200 AWS reference deployment + skill · #201 Azure + skill
- #202 horizontal scaling (move `fcntl` lock + job queue into Postgres) · #203 split read/write tiers
- #204 in-house MCP control plane (registry/portal/policy engine/shadow-MCP) — separate epic
- #205 DLP / classification-aware redaction

## Verification (per phase + milestone)
- **Every phase:** `task before-push` (exit 0) + `task pr-qa-gate` before its PR; new code keeps
  coverage ≥ the gate.
- **P-A:** unit tests for `secrets.py` resolver (env + gcp paths, `secret://` parsing); Postgres
  connection test with SSL context against a TLS-enabled local PG (or mocked `connect_args`).
- **P-B:** middleware tests — CORS denied by default / allowed for listed origin; JSON log shape +
  correlation-ID propagation; rate-limit 429.
- **P-C:** `tools/list` returns a scope-filtered subset for a read-only token; full set for stdio.
- **P-D:** one audit event per call with the full tuple; redaction of secret-bearing args.
- **P-E:** `terraform plan` clean; container builds; Cloud Run smoke test (`/health`, an
  authenticated `corpus:search` through IAP).
- **Milestone:** end-to-end — deploy to GCP, OAuth dance from the CLI through IAP, default-deny
  proven on a write tool without `agent-brain:index`, audit events visible in Cloud Logging.

## First concrete step
Update #219's checklist to mark OAuth authn + scope-enforcement authz as **shipped in v10.4** and
re-scope its remaining items to P-A…P-E, then open the milestone and start with **Phase P-A**.
