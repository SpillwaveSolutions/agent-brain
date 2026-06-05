---
phase: 22-restore-setup-wizard-with-full-configuration-prompts
plan: "01"
subsystem: plugin
tags:
  - setup-wizard
  - plugin-commands
  - configuration
  - documentation
dependency_graph:
  requires: []
  provides:
    - Full interactive wizard in agent-brain-setup.md covering all 5 config dimensions
    - GraphRAG and query mode documentation in SKILL.md and configuration-guide.md
  affects:
    - agent-brain-plugin/commands/agent-brain-setup.md
    - agent-brain-plugin/skills/configuring-agent-brain/SKILL.md
    - agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md
tech_stack:
  added: []
  patterns:
    - AskUserQuestion blocks for interactive wizard flow
    - Python yaml.dump for safe config.yaml serialization
key_files:
  created: []
  modified:
    - agent-brain-plugin/commands/agent-brain-setup.md
    - agent-brain-plugin/skills/configuring-agent-brain/SKILL.md
    - agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md
decisions:
  - query.default_mode written as YAML comment only (server has no global default_mode config key yet)
  - Python yaml.dump used for safe YAML serialization in wizard config write step
  - chmod 600 applied to config.yaml automatically after write
  - Wizard detects existing config and offers update vs fresh vs skip options
metrics:
  duration: "~10 min"
  completed_date: "2026-03-12"
  tasks_completed: 2
  files_modified: 3
---

# Phase 22 Plan 01: Restore Setup Wizard with Full Configuration Prompts — Summary

**One-liner**: Full interactive `/agent-brain-setup` wizard with 6 AskUserQuestion blocks for embedding, summarization, storage, GraphRAG, query mode, and API keys — writes comprehensive config.yaml before init/start.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add full wizard steps to /agent-brain-setup command | 3831db7 | agent-brain-plugin/commands/agent-brain-setup.md |
| 2 | Update SKILL.md and configuration-guide.md with wizard coverage | 9fc13d5 | SKILL.md, configuration-guide.md |

## What Was Built

### Task 1: Full Interactive Wizard in agent-brain-setup.md

Rewrote the `agent-brain-setup.md` command to include a complete 6-step wizard before running `agent-brain init` and `agent-brain start`:

- **Step 2**: Embedding provider (Ollama FREE / OpenAI / Cohere / Google Gemini / Custom)
- **Step 3**: Summarization provider (Ollama FREE / Mistral / Anthropic / OpenAI / Gemini / Grok)
- **Step 4**: Storage backend (ChromaDB default vs PostgreSQL + pgvector)
- **Step 5**: GraphRAG (disabled / SimplePropertyGraphStore / Kuzu persistent)
- **Step 6**: Default query mode (constrained by GraphRAG selection: hybrid/semantic/bm25 or +graph/multi)
- **Step 7**: Write comprehensive config.yaml using Python yaml.dump, detect existing config, chmod 600, security warning
- **Step 8**: Verify connectivity with `agent-brain verify` before init

The wizard now contains 6 AskUserQuestion blocks (requirement: >= 5). Step count updated from 5 to 10 in the Output section.

### Task 2: Updated SKILL.md and configuration-guide.md

**SKILL.md additions:**
- New "## Setup Wizard" section after Quick Setup with full wizard flow documentation
- Tables of all embedding/summarization provider options and their config keys
- "### GraphRAG Configuration" subsection with YAML keys, env var table, and note about `--include-code`
- "### Query Mode Selection" subsection with mode table, which modes require GraphRAG, and per-request usage

**configuration-guide.md additions:**
- Added `storage:`, `graphrag:`, and `# query.default_mode` blocks to the "Complete config.yaml example"
- Existing "## GraphRAG Configuration (Feature 113)" section already present — no duplication

## Decisions Made

1. `query.default_mode` written as YAML comment only — server has no global default_mode config key (per research); mode is per-request via `--mode` flag
2. Python `yaml.dump` used for safe config.yaml serialization — avoids manual YAML string quoting errors
3. `chmod 600` applied automatically — security enforcement without extra user steps
4. Existing config detection offers update/fresh/skip — preserves user's existing configuration

## Deviations from Plan

None — plan executed exactly as written.
