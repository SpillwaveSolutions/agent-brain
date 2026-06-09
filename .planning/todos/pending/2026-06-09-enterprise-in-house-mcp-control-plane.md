---
created: 2026-06-09T17:04:00.000Z
title: In-house MCP control plane — registry/portal, policy engine, shadow-MCP detection
area: governance
parent_plan: docs/plans/2026-06-09-enterprise-hardening-and-cloud-deployment.md
issue: https://github.com/SpillwaveSolutions/agent-brain/issues/204
followup_of: §6, §8, §10.5
files:
  - (new) control-plane service (separate component)
  - agent-brain-mcp/agent_brain_mcp/security/authz.py  # policy hook integration point
---

## Problem

The core plan hardens a *single* governed MCP server (authn + per-tool authz + audit behind a
gateway). The larger enterprise pattern (Cloudflare-style) adds an org control plane:
**central registry + identity-aware portal + policy engine + shadow-MCP detection**. This is a
big, separate effort — captured so it isn't lost.

## Scope

- **Internal MCP registry:** owner, purpose, data classification, risk tier, approved tools,
  scopes, review date per server.
- **Portal / gateway:** per-group tool exposure (finance read-only vs engineering read/write),
  DLP guardrails, centralized logging, cost controls.
- **Policy engine:** externalize the `principal + client + tool + resource + environment +
  data_classification + risk_level → allow/deny/require-approval` decision so it's managed
  centrally, not hard-coded per server. The MCP server's `security/authz.py` becomes a
  policy-engine client.
- **Shadow-MCP detection:** monitor traffic for `/mcp`, `/mcp/sse`, and JSON-RPC methods
  (`initialize`, `tools/list`, `tools/call`, `prompts/get`) to unknown endpoints; flag
  developer-laptop local MCP processes and third-party marketplaces.
- **Progressive tool disclosure at scale** (Code-Mode): search-tool + execute-tool sandbox
  pattern to keep model context cost flat as servers are added.

## Prerequisites

Per-server hardening (GCP phases 3–4) shipped — the per-tool authz hook is the integration seam.

## Acceptance

- Registry enforces owner + review date before a server is reachable via the portal.
- Policy changes take effect without redeploying individual MCP servers.
- Shadow-MCP detector flags an unapproved endpoint in a test trace.

## Notes

Likely its own milestone/roadmap (analogous to MCP v2/v3/v4). Pair with the DLP follow-up.
