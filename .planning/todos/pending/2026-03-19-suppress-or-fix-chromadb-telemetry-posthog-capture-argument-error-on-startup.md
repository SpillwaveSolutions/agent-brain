---
created: 2026-03-19T03:23:23.194Z
title: Suppress or fix ChromaDB telemetry PostHog capture() argument error on startup
area: tooling
files:
  - agent-brain-server/pyproject.toml
  - agent-brain-server/agent_brain_server/api/main.py
---

## Problem

Every server startup logs two benign but noisy errors:

```
ERROR chromadb.telemetry.product.posthog: Failed to send telemetry event ClientStartEvent:
  capture() takes 1 positional argument but 3 were given
ERROR chromadb.telemetry.product.posthog: Failed to send telemetry event ClientCreateCollectionEvent:
  capture() takes 1 positional argument but 3 were given
```

This is a ChromaDB/PostHog version mismatch — ChromaDB's telemetry calls PostHog's
`capture()` with 3 args but the installed PostHog version expects 1. Benign (no
functionality affected) but pollutes logs and confuses users into thinking something
is broken.

## Solution

**Approach A — Disable ChromaDB telemetry (quickest fix)**
Set environment variable at server startup:
```python
import os
os.environ["ANONYMIZED_TELEMETRY"] = "false"
```
Or in `.env`: `ANONYMIZED_TELEMETRY=false`
ChromaDB respects this flag and skips PostHog calls entirely.

**Approach B — Pin compatible ChromaDB + PostHog versions**
Find the ChromaDB version whose PostHog calls match the installed PostHog API.
More correct but requires version archaeology and constrains upgrades.

**Approach C — Suppress at logging level**
Add a log filter that drops ERROR messages from `chromadb.telemetry.product.posthog`.
Hides the symptom without fixing the cause — not recommended.

Approach A is the right call. Telemetry from a local development tool has no value.
