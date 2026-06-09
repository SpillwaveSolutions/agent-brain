---
created: 2026-06-09T17:00:00.000Z
title: AWS reference deployment (RDS pgvector + ECS/App Runner) + deploying-agent-brain-aws skill
area: deployment
parent_plan: docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md
followup_of: §7, §10.1
files:
  - agent-brain-server/agent_brain_server/storage/postgres/{config,connection}.py
  - agent-brain-server/agent_brain_server/config/secrets.py  # net-new (Phase 1)
  - (new) deploy/aws/ Terraform
  - (new) skills/deploying-agent-brain-aws/
---

## Problem

The enterprise hardening plan delivers GCP first. AWS is a phased follow-up: enterprises
running on AWS need a managed Postgres+pgvector + single-instance container path that matches
the GCP reference topology, plus a skill so they can reproduce it.

## Scope

- **DB:** RDS for PostgreSQL (≥ PG 15.2), pgvector extension enabled, **RDS IAM auth**
  (optional RDS Proxy). Wire the §3 SSL/IAM connection strategy for the RDS variant.
- **Secrets:** AWS Secrets Manager backend in the §4 secrets abstraction.
- **Compute (single-instance):** ECS Fargate (desired=1) or App Runner.
- **Gateway:** ALB + Cognito (or API Gateway authorizer) as the identity-aware edge; MCP server
  still does per-tool authz + audit.
- **Logs:** CloudWatch → SIEM export.
- **Skill:** `deploying-agent-brain-aws` — copy-pasteable walkthrough.

## Prerequisites

GCP phases 1–5 landed (secrets abstraction + Postgres SSL/IAM + MCP authn/authz + Dockerfile)
so AWS is mostly an IaC + secrets-backend + skill effort, not new core code.

## Acceptance

- Terraform applies a working single-instance AWS stack; `terraform plan` clean.
- `agent-brain --transport mcp query "X"` works through the ALB/Cognito edge with a valid token.
- Unauthorized tool call rejected; audit event emitted to CloudWatch.
- Skill validated end-to-end by a fresh operator.
