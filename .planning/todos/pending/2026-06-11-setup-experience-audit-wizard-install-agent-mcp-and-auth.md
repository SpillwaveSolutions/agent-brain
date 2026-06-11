---
created: 2026-06-11T00:00:00.000Z
title: Setup-experience audit — wizard + install-agent coverage for MCP transport + API-key auth + upgrade migration
area: cli
followup_of: Phase 61 discuss-phase (2026-06-11)
candidate: own phase (own discuss/plan cycle)
files:
  - agent-brain-cli/agent_brain_cli/commands/config.py        # config wizard
  - agent-brain-cli/agent_brain_cli/commands/install_agent.py
  - agent-brain-cli/agent_brain_cli/commands/init.py          # API-key generation
  - agent-brain-cli/agent_brain_cli/config_migrate.py
  - agent-brain-cli/agent_brain_cli/migration.py
  - agent-brain-plugin/skills/configuring-agent-brain/**
  - agent-brain-plugin/agents/setup-assistant.md
---

## Problem

The setup surface (config wizard + `install-agent` + the configuring-agent-brain
skill / setup-assistant agent) predates the MCP transport and the API-key auth
flow. Quick scan: `commands/config.py` (the wizard) has only ~2 combined
references to mcp/api_key/auth. So a user setting up Agent Brain today does NOT
get a seamless, guided path to:
- configure the MCP transport (`agent-brain mcp start`, `mcpServers` JSON for
  clients, `--transport mcp` usage), and
- set up / understand API-key auth (`agent-brain init` auto-generates a key into
  `.agent-brain/config.json`; non-loopback binds now refuse to boot without it).

**Premise correction (important):** **OAuth is NOT shipped.** It is MCP v4 /
[#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188) / v10.4 —
only a `v4 (OAUTH-01)` placeholder comment exists in `agent-brain-mcp/.../http.py`.
The shipped auth is API-key / RFC 6750 Bearer (v10.2.1 #179 → v10.3.0 #199). Do
NOT build OAuth wizard steps; scope this audit to the API-key/Bearer flow.

## Backwards-compatibility status (already in good shape — verify, don't rebuild)

- The auth change kept the v1 `X-API-Key` header AND `AGENT_BRAIN_API_KEY` env
  working through a deprecation window (CHANGELOG [10.3.0] §Migration).
- Migration infra exists: `config_migrate.py`, `migration.py`,
  `tests/test_config_migrate.py`.
- The ONE breaking edge: a server binding a **non-loopback** host now refuses to
  boot (exit 2) unless `API_KEY` is set or `INSECURE_NO_AUTH=true` is passed.
  Loopback dev is unaffected (warns + starts).

## Solution (scope for the audit phase)

1. Audit the config wizard (`config.py`) + `install-agent` + the
   configuring-agent-brain skill + setup-assistant agent for MCP-transport and
   API-key coverage; list concrete gaps.
2. Add guided steps so MCP setup + API-key auth are seamless from a fresh install
   AND from an upgrade (detect pre-auth config, offer to generate a key / explain
   the non-loopback breaking change).
3. Verify the upgrade migration path end-to-end for a user coming from a pre-auth
   (≤10.1.x) version: does `config_migrate` cover the new keys? Is there a clear
   message for the non-loopback refuse-to-boot case?
4. Update docs (configuring-agent-brain skill installation/configuration guides).

## Acceptance

- Wizard/install-agent walk a new user through MCP transport config + API-key
  auth without external docs.
- Upgrade path from a pre-auth version produces a working, auth-correct config
  (or a clear, actionable migration message) — covered by a test.
- Docs reflect the shipped auth model (API-key/Bearer) and explicitly note OAuth
  is future/v4.

## Notes

Surfaced during Phase 61 discuss-phase from the question "is the wizard/install
up to date with MCP + OAuth, seamless, and backwards-compatible?" Strong
candidate for its own `/gsd:discuss-phase` + `/gsd:plan-phase` cycle. NOT part of
Phase 61 (framework matrix).
