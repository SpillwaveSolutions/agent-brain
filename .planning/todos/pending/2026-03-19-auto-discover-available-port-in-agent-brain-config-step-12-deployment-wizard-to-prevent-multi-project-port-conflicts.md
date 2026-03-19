---
created: 2026-03-19T03:12:01.497Z
title: Auto-discover available port in agent-brain-config Step 12 deployment wizard to prevent multi-project port conflicts
area: tooling
files:
  - agent-brain-plugin/commands/agent-brain-config.md:997-1047
---

## Problem

The `/agent-brain-config` wizard Step 12 (Server & Deployment Configuration) offers:
1. Local (Default) — hardcoded 127.0.0.1:8000
2. Custom port — manual entry

Users running one Agent Brain instance per project (the intended multi-instance
architecture) will get port conflicts if they accept the default 8000. The wizard
gives no help avoiding this — the user must manually track which ports are in use.

Precedent exists in Step 5 (PostgreSQL): it already scans ports 5432-5442 and
auto-discovers a free one. The same pattern should apply to the API server port.

## Solution

Three approaches:

**Approach A — Random available port (recommended)**
Scan 8000-8300, pick a random free port, present as the suggested default:
```
Found available port: 8147
Use port 8147? (Enter to confirm, or type a custom port):
```
Random selection is collision-resistant when multiple projects set up simultaneously.

**Approach B — Lowest available port (deterministic)**
Same scan, pick the first free port. 8000 if available, 8001 if not, etc.
Predictable — projects get consistent ports if setup order is consistent.
Same pattern as the existing PostgreSQL port discovery.

**Approach C — Show what's running, then suggest**
Scan 8000-8300, detect active `agent-brain` processes via `lsof` or by reading
`.agent-brain/runtime.json` files in known project dirs. Show:
```
Port 8000: in use by agent-brain (~/projects/my-docs)
Port 8001: available
Suggested port: 8001
```
Most informative but most complex. Good for power users.

## Implementation Notes

- Port scan reuses the pattern from Step 5 (PostgreSQL port discovery)
- The discovered port should be written to `.claude/agent-brain/config.yaml`
  as `server.port` and also to `.agent-brain/runtime.json` on start
- The scan range 8000-8300 gives 301 possible ports — ample for any workstation
- Script candidate: `ab-port-scan.sh` in `agent-brain-plugin/scripts/`
  (keeps inline bash out of the command markdown, fits the policy island pattern)
- The `agent-brain start` command already handles port from config — no server
  changes needed, this is purely a wizard UX improvement

## Scan snippet (for reference)

```bash
SCAN_START=8000
SCAN_END=8300
AVAILABLE_PORTS=()
for port in $(seq $SCAN_START $SCAN_END); do
  if ! lsof -i :$port -sTCP:LISTEN >/dev/null 2>&1; then
    AVAILABLE_PORTS+=($port)
  fi
done
# Approach A: random
API_PORT=${AVAILABLE_PORTS[$RANDOM % ${#AVAILABLE_PORTS[@]}]}
# Approach B: first available
API_PORT=${AVAILABLE_PORTS[0]}
echo "Suggested port: $API_PORT"
```
