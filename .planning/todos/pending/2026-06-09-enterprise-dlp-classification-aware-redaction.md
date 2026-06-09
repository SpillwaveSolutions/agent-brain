---
created: 2026-06-09T17:05:00.000Z
title: DLP — classification-aware response redaction for search/MCP results
area: security
parent_plan: docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md
issue: https://github.com/SpillwaveSolutions/agent-brain/issues/205
followup_of: §8, §10.6
files:
  - agent-brain-server/agent_brain_server/services/query_service.py
  - agent-brain-mcp/agent_brain_mcp/tools/search.py
---

## Problem

Search/MCP results can surface secrets, PII, or content above a caller's clearance. The core
plan adds authn/authz/audit but not **data-loss prevention** on the response payload itself —
the "Data: DLP, redaction, classification-aware responses" row of the hardening checklist.

## Scope

- Classify indexed content (or chunk metadata) by sensitivity tier.
- At query time, filter/redact results the caller isn't cleared for, based on the
  `data_classification` dimension of the authz decision.
- Redact obvious secret patterns (keys, tokens) from returned snippets.
- Emit an audit event when redaction occurs.

## Prerequisites

MCP authz scope model + audit (GCP phases 4) shipped; ideally the in-house policy engine so
classification rules are centrally managed.

## Acceptance

- A low-clearance principal cannot retrieve high-classification chunks.
- Secret-pattern snippets are redacted in returned results.
- Redaction events appear in the audit log.
