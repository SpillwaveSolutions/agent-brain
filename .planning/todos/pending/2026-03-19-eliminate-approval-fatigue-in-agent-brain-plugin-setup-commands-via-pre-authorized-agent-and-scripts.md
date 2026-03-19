---
created: 2026-03-19T03:00:48.828Z
title: Eliminate approval fatigue in agent-brain-plugin setup commands via pre-authorized agent and scripts
area: tooling
files:
  - agent-brain-plugin/agents/setup-assistant.md
  - agent-brain-plugin/commands/agent-brain-config.md
  - agent-brain-plugin/commands/agent-brain-install.md
  - agent-brain-plugin/commands/agent-brain-setup.md
  - agent-brain-plugin/commands/agent-brain-init.md
  - agent-brain-plugin/commands/agent-brain-start.md
  - agent-brain-plugin/commands/agent-brain-verify.md
  - agent-brain-plugin/scripts/ab-setup-check.sh
---

## Problem

When users run `/agent-brain-config`, `/agent-brain-install`, and other setup commands,
Claude Code prompts for permission on every inline bash command — `$()` substitution,
`&&` chaining, `curl` calls, file edits. This creates severe approval fatigue:
5-10 prompts per command, interrupting the wizard flow.

Root cause: `setup-assistant.md` has no `allowed_tools` declaration, so every bash
call negotiates permissions at runtime instead of being pre-approved.

Additionally, complex detection logic lives as inline bash in command markdown files
(e.g., multi-command Ollama check, PyPI version fetch with `$()`) rather than in
consolidated scripts — meaning each subcommand needs its own permission approval.

Affected commands: `agent-brain-config`, `agent-brain-install`, `agent-brain-setup`,
`agent-brain-init`, `agent-brain-start`, `agent-brain-verify`.

Config paths needing pre-approved write access:
- `.claude/agent-brain/`
- `.agent-brain/`
- `~/.config/agent-brain/`

## Solution

Use the "Policy Island" pattern (fork + pre-authorized agent) from the article
"Mastering Agent Skills in Claude Code 2.1: Escape Approval Fatigue with a Pre-Authorized Agent".

Three approaches in priority order:

**Approach C (do first): Scripts-first**
Move all complex inline bash detection into scripts in the skill's `scripts/` directory:
- `ab-setup-check.sh` — already exists, fix path detection when plugin installed
- `ab-pypi-version.sh` — replace inline `curl | python3` PyPI version fetch
- `ab-uv-check.sh` — replace inline uv/pipx install check
Each script = one permission line instead of 5+ inline commands.

**Approach A (next): Add `allowed_tools` to `setup-assistant.md`**
Add full `allowed_tools` block covering:
- `Bash(bash*scripts/ab-*.sh*)` — all setup scripts
- `Bash(curl*pypi.org*)`, `Bash(curl*localhost:11434*)` — network checks
- `Bash(uv*)`, `Bash(pipx*)`, `Bash(ollama*)`, `Bash(agent-brain*)` — CLI tools
- `Bash(docker*)` — optional postgres setup
- `Read`, `Edit`, `Write` — config file management
- Glob-scoped `rm`, `mkdir` for config dirs only

**Approach B (then): Bind all 6 commands to the agent**
Add to each affected command's frontmatter:
```yaml
context: fork
agent: setup-assistant
```
This makes permissions propagate from agent → skill → command automatically.
Zero runtime prompts once agent is approved.

Reference: Policy Islands pattern — skills store scripts, agent declares permissions,
commands bind to agent via `context: fork` + `agent: setup-assistant`.
