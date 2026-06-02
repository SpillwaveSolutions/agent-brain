---
created: 2026-03-19T03:19:05.927Z
title: Fix two permission gaps in setup-assistant agent — scoped Bash for scripts and Write/Edit for ~/.agent-brain/** config paths
area: tooling
files:
  - agent-brain-plugin/agents/setup-assistant.md
  - agent-brain-plugin/commands/agent-brain-config.md:56-63
  - agent-brain-plugin/scripts/ab-setup-check.sh
tracked_in:
  - https://github.com/SpillwaveSolutions/agent-brain/issues/172
---

> **Tracked in:** [#172](https://github.com/SpillwaveSolutions/agent-brain/issues/172) — Related: [#170](https://github.com/SpillwaveSolutions/agent-brain/issues/170), [#171](https://github.com/SpillwaveSolutions/agent-brain/issues/171)

## Problem

Cross-referencing the `/agent-brain-config` execution trace against pre-approved
permissions reveals exactly two gaps that cause runtime prompts:

**Gap 1: `bash "$SCRIPT"` — running ab-setup-check.sh**
The command runs as `SETUP_STATE=$(bash "$SCRIPT")`. No `Bash(bash *)` rule exists
in the agent. Claude Code prompts because `bash` as a command isn't pre-approved.

**Gap 2: `Write(~/.agent-brain/config.yaml)`**
User settings only allow `Write(~/.claude/**)`. Writing to `~/.agent-brain/` has
no pre-approval anywhere — not in global settings, not in the agent.

All other commands in the config wizard execution trace ARE already approved:
- `agent-brain config path/show` → `Bash(agent-brain *)` ✅
- `find ... ab-setup-check.sh` → `Bash(find *)` ✅
- `uv pip install ...` → already in local settings ✅
- `python3 -c ...` → `Bash(python3 *)` ✅
- `mkdir -p ~/.agent-brain` → `Bash(mkdir -p *)` ✅
- `grep -n ... ~/.zshrc` → `Bash(grep *)` ✅
- `echo "..." >> ~/.zshrc` → `Bash(echo *)` ✅

## Solution

Two fixes, applied together (Approach C + B from brainstorm):

**Fix 1: Change script invocation pattern**
Instead of `bash "$SCRIPT"`, call the script directly by full path:
```bash
# Before (triggers prompt):
SETUP_STATE=$(bash "$SCRIPT")

# After (no prompt needed with path-specific permission):
SETUP_STATE=$(~/.claude/plugins/agent-brain/scripts/ab-setup-check.sh)
```
Then the permission becomes path-specific, not broad `bash *`.

**Fix 2: Add missing permissions to `setup-assistant.md` allowed_tools**
```yaml
allowed_tools:
  # Script execution (path-scoped, not broad bash *)
  - "Bash(~/.claude/plugins/agent-brain/scripts/*)"
  - "Bash(.claude/plugins/agent-brain/scripts/*)"

  # Config file write access (all three locations)
  - "Write(~/.agent-brain/**)"
  - "Edit(~/.agent-brain/**)"
  - "Write(~/.config/agent-brain/**)"
  - "Edit(~/.config/agent-brain/**)"
  - "Write(.claude/agent-brain/**)"
  - "Edit(.claude/agent-brain/**)"
```

Do NOT add these to global `~/.claude/settings.json` — that expands permissions
for all Claude sessions. Keep them scoped to the agent (policy island pattern).

## Why Not `Bash(bash *)`

`Bash(bash *)` would approve running ANY bash script — too broad. Path-scoped
patterns like `Bash(~/.claude/plugins/agent-brain/scripts/*)` limit approval to
only the known plugin scripts. This is the minimum necessary permission.
