---
created: 2026-06-09T17:02:00.000Z
title: Horizontal scaling — move fcntl lock + local job queue into Postgres to unblock multi-replica
area: architecture
parent_plan: docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md
followup_of: §2, §10.3
files:
  - agent-brain-server/agent_brain_server/locking.py
  - agent-brain-server/agent_brain_server/services/  # job queue service + storage
  - agent-brain-server/agent_brain_server/runtime.py
---

## Problem

The enterprise plan locks compute to **single-instance** because `locking.py` uses `fcntl`
advisory file locks and the job queue is local JSON, both scoped to one `.agent-brain/` state
dir. A second replica would corrupt that state or fail to coordinate. Cloud Run `min=max=1`
enforces single-writer today — but that caps throughput and removes HA.

This is the prerequisite for any multi-replica / autoscaling deployment.

## Scope

- Replace the file lock with **Postgres advisory locks** (`pg_advisory_lock`) or a
  leader-election row so coordination is durable + network-safe.
- Move the job queue from local JSON into a **Postgres queue table** (`SELECT ... FOR UPDATE
  SKIP LOCKED` worker pattern) so multiple workers can drain it safely.
- Keep the file-lock path as a fallback for local/single-instance (chroma backend, dev).
- Revisit `runtime.json` discovery for a multi-replica world.

## Prerequisites

Postgres backend is the active store (it already is for the cloud path). GCP phases 1–5 landed.

## Acceptance

- Two server replicas against one Cloud SQL instance coordinate correctly: exactly one indexer
  drains a given job; no double-processing; clean failover when the leader dies.
- Single-instance / chroma path still works unchanged.
- Stress test: N replicas, M jobs, zero duplicate completions.

## Notes

Pairs with the split read/write tiers follow-up — do this first.
