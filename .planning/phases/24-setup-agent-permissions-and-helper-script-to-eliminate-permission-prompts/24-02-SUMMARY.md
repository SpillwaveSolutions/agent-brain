---
phase: 24-setup-agent-permissions-and-helper-script-to-eliminate-permission-prompts
plan: "02"
subsystem: agent-brain-plugin
tags: [environment-detection, plugin, bash-script, json-output, setup-wizard]
dependency_graph:
  requires:
    - 24-01 (settings.json template, Step 0 bootstrap in agent-brain-setup.md)
  provides:
    - agent-brain-plugin/scripts/ab-setup-check.sh
    - agent-brain-plugin/commands/agent-brain-config.md (updated Step 2 + Step 6)
    - agent-brain-plugin/commands/agent-brain-setup.md (Step 1 pre-flight)
  affects:
    - agent-brain-plugin/commands/agent-brain-config.md
    - agent-brain-plugin/commands/agent-brain-setup.md
tech_stack:
  added:
    - bash script for JSON environment detection
  patterns:
    - Single-invocation pre-flight detection outputting structured JSON
    - SETUP_STATE variable shared across wizard steps
    - Fallback documentation preserved for missing script case
key_files:
  created:
    - agent-brain-plugin/scripts/ab-setup-check.sh
  modified:
    - agent-brain-plugin/commands/agent-brain-config.md
    - agent-brain-plugin/commands/agent-brain-setup.md
decisions:
  - "ab-setup-check.sh uses set -uo pipefail (not -e) to prevent aborting on missing tools like ollama/docker"
  - "Script uses || true and explicit if/fi blocks for Ollama/Docker checks — safe under set -u"
  - "JSON output constructed manually with heredoc — no jq dependency required for output"
  - "SETUP_STATE variable stored in memory for reuse across Steps 2-12 in setup wizard"
  - "Both agent-brain-config.md and agent-brain-setup.md retain fallback documentation for cases where ab-setup-check.sh is not found"
  - "Large directory detection uses existing known dir list (not open-ended find) for deterministic fast results"
metrics:
  duration: "7 min"
  completed: "2026-03-15"
  tasks_completed: 2
  files_changed: 3
---

# Phase 24 Plan 02: ab-setup-check.sh Environment Detection Script Summary

**One-liner:** Single-invocation ab-setup-check.sh script consolidates Ollama 3-method check, port scan, Docker detection, and large-dir scan into one JSON output, replacing scattered individual Bash calls in the setup wizard.

## What Was Built

### Task 1: Create ab-setup-check.sh detection script
Created `agent-brain-plugin/scripts/ab-setup-check.sh` — a portable bash script that:
- Detects Agent Brain installation and version
- Finds config file across XDG + legacy paths (`.claude/agent-brain/`, `~/.config/agent-brain/`, `~/.agent-brain/`)
- Checks Ollama using all 3 methods (curl, lsof, ollama list) — OLLAMA_RUNNING is true if any method succeeds
- Collects installed Ollama model names as a JSON array
- Detects Docker and Docker Compose availability
- Detects Python version
- Reports API key presence (boolean only — key values never printed)
- Scans ports 5432-5442 for the first available PostgreSQL port
- Scans current directory for common large dirs (node_modules, .venv, etc.) with size and file count
- Outputs a single valid JSON object to stdout
- Uses `set -uo pipefail` (not `-e`) to avoid aborting on missing optional tools

### Task 2: Update agent-brain-config.md and agent-brain-setup.md
Updated `agent-brain-plugin/commands/agent-brain-config.md`:
- **Step 2** now runs `ab-setup-check.sh` and parses `SETUP_STATE` into `OLLAMA_RUNNING`, `CONFIG_FILE`, `DOCKER_AVAILABLE`, `AVAILABLE_PORT` variables
- **Step 6** reads `large_dirs` from `SETUP_STATE` instead of running a `find/du/wc` loop as primary path
- Both steps retain fallback documentation for the case where `ab-setup-check.sh` is not found

Updated `agent-brain-plugin/commands/agent-brain-setup.md`:
- **Step 1** now runs `ab-setup-check.sh` and stores `SETUP_STATE` for use across Steps 2-12
- Reduces cognitive overhead by collecting all environment state upfront in one call

## Verification Results

- Script is executable: confirmed via `test -x`
- Script outputs valid JSON: confirmed via `python3 -m json.tool`
- All required keys present: `agent_brain_installed`, `config_file_found`, `ollama_running`, `docker_available`, `available_postgres_port`, `large_dirs`
- agent-brain-config.md references ab-setup-check.sh: 3 occurrences
- agent-brain-setup.md references ab-setup-check.sh: 1 occurrence
- 185 CLI tests pass: no regressions

## Commits

- `e791023` — feat(24-02): add ab-setup-check.sh and update config/setup commands to use it

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `agent-brain-plugin/scripts/ab-setup-check.sh` exists and is executable: FOUND
- `agent-brain-plugin/commands/agent-brain-config.md` references ab-setup-check.sh: FOUND
- `agent-brain-plugin/commands/agent-brain-setup.md` references ab-setup-check.sh: FOUND
- Commit `e791023` exists: FOUND
