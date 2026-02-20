---
created: 2026-02-20T19:24:12.153Z
title: Config not hot-reloaded after yaml changes
area: api
severity: cosmetic
files:
  - agent-brain-server/agent_brain_server/config/settings.py
  - agent-brain-server/agent_brain_server/config/provider_config.py
---

## Problem

After updating `config.yaml` (e.g., changing `storage.postgres.port` from 5433 to 5434), the server error logs still showed the old port (`localhost:5433`) on the first job attempt. After restarting the server, it correctly used 5434.

This suggests config is loaded once at startup and cached. Users who change config.yaml expect changes to take effect, but they don't without a server restart.

## Solution

This is cosmetic/low-priority since `agent-brain stop && agent-brain start` is a quick workaround. Options:

1. **Document the behavior:** Add a note to the config command output: "Restart the server after config changes: `agent-brain stop && agent-brain start`"
2. **Add a reload command:** `agent-brain reload` that sends SIGHUP or similar to the running server to re-read config
3. **Watch config file:** Use `watchdog` or similar to auto-reload on config.yaml changes (over-engineering for now)

Option 1 is sufficient. Option 2 would be nice-to-have for a future release.
