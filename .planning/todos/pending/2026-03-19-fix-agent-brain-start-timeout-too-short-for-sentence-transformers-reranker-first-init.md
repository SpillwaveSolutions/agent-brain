---
created: 2026-03-19T03:23:23.194Z
title: Fix agent-brain start timeout too short for sentence-transformers reranker first init
area: tooling
files:
  - agent-brain-server/agent_brain_server/api/main.py
  - agent-brain-cli/agent_brain_cli/commands/
---

## Problem

`agent-brain start` fails on first run when the sentence-transformers reranker is
enabled. The startup health check times out before the cross-encoder model finishes
loading (downloading + initializing on first use). The server IS healthy once loaded
— the check just gives up too early.

Observed: server started successfully via `--foreground` but failed silently in
background mode. The reranker (cross-encoder/ms-marco-MiniLM-L-6-v2) adds several
seconds of init time that exceeds the default 30s startup check window.

Workaround: `agent-brain start --timeout 60`

## Solution

Three approaches:

**Approach A — Increase default startup timeout**
Change default from 30s → 90s for the startup health poll. Simple, no architecture
change. May mask other real startup failures.

**Approach B — Lazy-load the reranker**
Don't load the sentence-transformers model at startup. Load it on first query that
requests reranking. Server starts fast, first reranked query is slow.
Better UX overall — zero-cost startup, pay on first use.

**Approach C — Startup readiness signal**
Add a `/health/ready` endpoint that returns 200 only after all providers (including
reranker) are fully initialized. CLI polls this instead of `/health`. More accurate
than a timeout — no guessing required.

Approach B is cleanest long-term. Approach A is the fastest fix.
