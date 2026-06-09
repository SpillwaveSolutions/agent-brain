---
created: 2026-06-09T17:03:00.000Z
title: Split read/write tiers — single indexer/writer + N read-only query replicas
area: architecture
parent_plan: docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md
followup_of: §2, §10.4
files:
  - agent-brain-server/agent_brain_server/api/main.py
  - agent-brain-server/agent_brain_server/storage/postgres/config.py
  - agent-brain-server/agent_brain_server/services/  # query vs indexing services
---

## Problem

Most enterprise load is **read** (search/query); writes (indexing/inject) are bursty and must
stay single-writer until the lock+queue move into Postgres. A middle ground between
single-instance and full horizontal scale: one writer + many stateless read replicas.

## Scope

- A **read-only server mode** (e.g. `AGENT_BRAIN_ROLE=query`) that exposes only read tools/
  endpoints, never acquires the write lock, and connects with a **read-only DB role** (or a
  Cloud SQL read replica).
- One **writer/indexer** instance handles `index/inject/remove` + the job queue.
- DB role separation: least-privilege read role for query replicas; write role only for the
  indexer (maps the least-privilege control).
- MCP authz scope model already supports this — query replicas reject write scopes outright.

## Prerequisites

Horizontal-scaling follow-up (lock+queue → Postgres) for the writer side, OR keep the writer as
the single-instance container and only scale the read tier.

## Acceptance

- N query replicas behind the LB serve search; writer handles indexing.
- A write tool against a query replica is rejected (role + scope).
- Read replica DB user cannot mutate (verified at the DB grant level).
