---
created: 2026-06-09T17:01:00.000Z
title: Azure reference deployment (Flexible Server pgvector + Container Apps) + deploying-agent-brain-azure skill
area: deployment
parent_plan: docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md
followup_of: §7, §10.2
files:
  - agent-brain-server/agent_brain_server/storage/postgres/{config,connection}.py
  - agent-brain-server/agent_brain_server/config/secrets.py  # net-new (Phase 1)
  - (new) deploy/azure/ Terraform/Bicep
  - (new) skills/deploying-agent-brain-azure/
---

## Problem

Azure follow-up to the GCP-first enterprise hardening plan: managed Postgres+pgvector +
single-instance container + identity-aware edge, plus a deployment skill.

## Scope

- **DB:** Azure Database for PostgreSQL Flexible Server; enable `vector` via the
  `azure.extensions` allowlist; **Managed Identity** auth (wire §3 connection strategy).
- **Secrets:** Azure Key Vault backend in the §4 secrets abstraction.
- **Compute (single-instance):** Azure Container Apps (min=max=1).
- **Gateway:** Application Gateway + Entra ID (or APIM) as the identity-aware edge; MCP server
  retains per-tool authz + audit.
- **Logs:** Azure Monitor → SIEM export.
- **Skill:** `deploying-agent-brain-azure`.

## Prerequisites

GCP phases 1–5 landed (core security + secrets abstraction + Dockerfile).

## Acceptance

- Terraform/Bicep applies a working single-instance Azure stack.
- MCP query works through the App Gateway/Entra edge with a valid token; unauthorized tool call
  rejected; audit event reaches Azure Monitor.
- Skill validated end-to-end.
