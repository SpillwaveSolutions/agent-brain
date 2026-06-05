---
phase: 24-setup-agent-permissions-and-helper-script-to-eliminate-permission-prompts
plan: "01"
subsystem: agent-brain-plugin
tags: [permissions, setup-wizard, plugin, settings-json]
dependency_graph:
  requires: []
  provides:
    - agent-brain-plugin/templates/settings.json
    - agent-brain-plugin/commands/agent-brain-setup.md (Step 0 bootstrap)
  affects:
    - agent-brain-plugin/commands/agent-brain-setup.md
tech_stack:
  added: []
  patterns:
    - Write-tool-first permission bootstrap (avoids Bash permission gates)
    - Canonical settings.json template for Claude permission allowlist
key_files:
  created:
    - agent-brain-plugin/templates/settings.json
  modified:
    - agent-brain-plugin/commands/agent-brain-setup.md
decisions:
  - "Write tool (always pre-authorized) used instead of Bash to create .claude/settings.json — bypasses all permission gates"
  - "Full JSON permission block inlined in agent-brain-setup.md — command is self-contained, no file-path dependency"
  - "MERGE semantics on existing settings.json — avoids destroying custom user permissions"
  - "24 Bash entries in allowlist covering: agent-brain, lsof, ollama, docker, mkdir, cat, jq, mv, du, ps, pgrep, pip, pipx, uv, python, python3, rg, wc, curl, ls, find, chmod, grep, bash"
metrics:
  duration: "5 min"
  completed: "2026-03-15"
  tasks_completed: 2
  files_changed: 2
---

# Phase 24 Plan 01: Permission Bootstrap Template and Setup Wizard Step 0 Summary

**One-liner:** Write-tool-first permission bootstrap in agent-brain-setup.md writes .claude/settings.json before any Bash calls, eliminating all wizard permission prompts on fresh projects.

## What Was Built

### Task 1: Create settings.json permission template
Created `agent-brain-plugin/templates/settings.json` — an auditable canonical template listing all 24 Bash permission entries required to run the setup wizard without interruption. The template uses `_comment_groupN` JSON keys to document the purpose of each group of entries.

### Task 2: Add Step 0 permission bootstrap to agent-brain-setup.md
Inserted a new **Step 0: Bootstrap Permissions** section into `agent-brain-plugin/commands/agent-brain-setup.md` immediately before Step 1. Step 0:
- Checks if `.claude/settings.json` already exists and contains `Bash(agent-brain:*)`
- If absent, instructs the AI to use the **Write tool** (not Bash) to create the file — the Write tool has no permission gate
- Inlines the full JSON permission block directly in the command for self-contained bootstrap
- Adds merge semantics: if file already exists with custom content, add missing entries rather than replace
- Updates the Output section to show `[0/10] Bootstrapping permissions... .claude/settings.json [WRITTEN]`

## Verification Results

- `settings.json` is valid JSON: confirmed via `python3 -c "import json; json.load(...)"`
- Template contains all required entries (24 total): `Bash(agent-brain:*)`, `Bash(lsof:*)`, `Bash(docker:*)`, `Bash(ollama:*)`, `Bash(mkdir:*)`, `Bash(cat:*)`, `Bash(jq:*)`, `Bash(mv:*)`, `Bash(du:*)`, `Bash(ps:*)`, `Bash(pgrep:*)`, `Bash(pip:*)`, `Bash(pipx:*)`, `Bash(uv:*)`, `Bash(python:*)`, `Bash(rg:*)`, `Bash(wc:*)`
- `agent-brain-setup.md` contains "Step 0: Bootstrap Permissions" before "Step 1: Check Installation Status" (line 25 vs line 77)
- 185 CLI tests pass: no regressions

## Commits

- `91af829` — feat(24-01): add settings.json permission template and Step 0 bootstrap to agent-brain-setup.md

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `agent-brain-plugin/templates/settings.json` exists: FOUND
- `agent-brain-plugin/commands/agent-brain-setup.md` contains Step 0: FOUND
- Commit `91af829` exists: FOUND
