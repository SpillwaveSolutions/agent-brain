---
title: Backlog Survey & Roadmap — What's Left To Do (post-v10.4)
status: survey
date: 2026-06-23
author: Rick Hightower
---

# Backlog Survey & Roadmap — What's Left To Do (post-v10.4)

## Context

v10.4 (MCP v4 OAuth 2.1 + GraphRAG stability) shipped to PyPI on 2026-06-23 (tag `v10.4.0`,
PR #217). This document surveys remaining work across the repo `TODO.md`, the planning backlog
(`docs/plans/`), and GitHub issues. It flags stale/already-shipped tracking, groups the rest by
theme, and recommends the next milestone with rough sequencing.

> **Issue hygiene already applied (2026-06-23):** #178, #188, #194 closed (shipped in v10.4);
> #189 meta-epic updated + closed; `TODO.md` refreshed to point here. The "remaining" lists below
> reflect the state *after* that cleanup.

---

## Key finding: the backlog was partly stale

v10.4 shipped work whose tracking issues were still `OPEN`, and `TODO.md`'s only entry had already
shipped. GitHub's auto-close didn't fire because the "closes #X" references lived in changelog
prose (a separate `docs(changelog)` commit), not in the PR-merge closing position.

| Item | Was | Reality | Action taken |
|------|-----|---------|--------------|
| #188 MCP v4 OAuth 2.1 | OPEN | Shipped v10.4 (Phases 64–70) | **Closed** |
| #178 kuzu SIGSEGV | OPEN | Fixed v10.4 (GSTAB-01, out-of-process spawn) | **Closed** |
| #194 /mcp/subscriptions debug endpoint | OPEN | Shipped v10.4 (HOUSE-01) | **Closed** |
| #189 MCP roadmap meta-issue | OPEN, boxes unchecked | v1–v4 all shipped | **Updated + closed** |
| `TODO.md` | Listed native MCP server (#153/#167) as pending | #167 closed (shipped) | **Refreshed** → points here |

---

## Remaining open issues, grouped by theme

### A. Enterprise Hardening + Cloud Deployment  ← recommended next milestone
Design doc: `docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md` (GCP-first).

- **GCP-first core — now tracked as #219:** server `Dockerfile`, IaC, Secret
  Manager integration, Postgres SSL/IAM auth, CORS allowlist (today `allow_origins=["*"]`),
  structured + audit logging, per-tool MCP authz (default-deny on the 6 mutating tools),
  `tools/list` filtering, and a `deploying-agent-brain-gcp` skill. **This is phase-1.**
- #200 — AWS reference deployment (RDS pgvector + ECS/App Runner) + skill
- #201 — Azure reference deployment (Flexible Server pgvector + Container Apps) + skill
- #202 — Horizontal scaling: move `fcntl` lock + local JSON job queue into Postgres
- #203 — Split read/write tiers: single indexer + N read-only query replicas
- #204 — In-house MCP control plane (registry/portal, policy engine, shadow-MCP detection) — **epic, likely its own milestone**
- #205 — DLP: classification-aware response redaction for search/MCP results

### B. GraphRAG enhancements
- #183 — RFC: user-defined domain schemas for graph mode
- #160 — Schema-versioned entity types (package/module/class/method, design doc, PRD, runbook)
- #154 — GraphRAG agentic workflow (reflect / re-query / synthesize)

### C. Providers / embeddings
- #164 — Claude-native provider (no API key — use Claude's context for embed/summary/extract)
- #152 — Voyage AI embedding provider (Voyage 4)
- #155 — Per-source-type embedding models (code vs doc)

### D. Query / retrieval features
- #163 — Batch query endpoint + CLI batching at transport layer
- #157 — Multi-repository federated search (cross-project RRF fusion)
- #156 — LiveVectorLake-style streaming updates (hot/cold tiers + temporal queries)

### E. Clients / IDE
- #162 — Rust CLI rewrite (UDS-first, fast startup)
- #158 — VS Code extension

### F. Tech debt / bugs
- #218 — Keycloak-in-CI OAuth E2E fails (400 at token endpoint). Non-blocking, known
  (harness bootstrap issue, not a shipped-code defect); the unit/contract suite passes and
  `agent_brain_mcp/oauth/` holds ≥90% coverage behind a binding CI gate.

---

## Recommended sequencing

1. **Issue hygiene** — done (this survey).
2. **Enterprise Hardening — GCP-first core** — the named next candidate and the only theme with a
   ready, code-verified design doc. Plan it phase-by-phase (Dockerfile → secrets → logging/audit →
   per-tool authz → GCP deploy skill). #200–#203/#205 are explicit follow-ups; #204 is a separate
   epic/milestone.
3. **Then pick by demand** among Providers (B/C — smallest, highest-leverage; #164 Claude-native
   and #152 Voyage are well-scoped), GraphRAG (#160/#183/#154), or Query (#163 batch is small).
4. **Larger client bets last** — #162 Rust CLI and #158 VS Code extension are big, independent,
   and not on the critical path.

### Rough effort (t-shirt)
| Theme | Size | Notes |
|-------|------|-------|
| Issue hygiene | XS | Done |
| Enterprise GCP core | L | Multi-phase; design doc exists, code gap is real |
| #200/#201 cloud follow-ups | M each | Mirror GCP core per provider + skill |
| #204 control plane | XL | Own milestone/epic |
| Providers (#164/#152/#155) | S–M | Pluggable-provider framework already exists |
| GraphRAG (#160/#183/#154) | M–L | #154 agentic is the largest |
| Query (#163/#157/#156) | S/M/L | #163 small; #156 large |
| #162 Rust CLI / #158 VS Code | L each | Independent, defer |

---

## Verification (post-hygiene)
- Open issue count dropped from 22 → 18 after closing #178/#188/#194/#189, then 18 → 19 after
  filing the GCP-core tracking issue (#219).
- `TODO.md` no longer references the shipped native MCP server.
- The GCP-core issue (#219) links the design doc and follow-ups #200–#205.
