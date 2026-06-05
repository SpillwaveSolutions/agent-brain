# Phase 24: Setup Agent Permissions and Helper Script to Eliminate Permission Prompts — Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate Claude Code permission prompts that block automated Agent Brain setup. The current setup wizard (`/agent-brain-setup`, `/agent-brain-config`, `/agent-brain-init`, `/agent-brain-start`, `/agent-brain-verify`) runs shell commands for config file detection, Ollama connectivity checks, large-dir scanning, directory creation, and server spawn — all of which may trigger interactive permission prompts that halt the agent mid-flow.

The fix covers two complementary approaches:
1. A **pre-approved permission preset** embedded in a project-level `.claude/settings.json` (or documentation on how to populate `settings.local.json`) that allows the specific Bash commands the wizard uses.
2. An optional **helper shell script** that bundles the non-interactive setup steps so the agent can invoke one pre-approved command instead of many individual commands.

Project-level state (`.claude/agent-brain/`) and the CLI commands themselves are NOT changed. This phase is plugin-layer only — changes are to `.claude/settings.json`, plugin markdown, and potentially a new helper script.

</domain>

<problem_statement>
## Problem Statement

### What Breaks Without Permissions

During a fresh setup on a new project, Claude Code agents run the following operations that each require explicit user approval if not pre-authorized:

| Step | Commands / Operations | Permission Category |
|------|----------------------|---------------------|
| Config detection | `ls ~/.agent-brain/config.yaml .claude/agent-brain/config.yaml 2>/dev/null` | `Bash(ls:*)` |
| Ollama check (method 1) | `curl -s --connect-timeout 3 http://localhost:11434/ 2>/dev/null` | `Bash(curl:*)` |
| Ollama check (method 2) | `lsof -i :11434 2>/dev/null \| head -3` | `Bash(lsof:*)` |
| Ollama check (method 3) | `ollama list 2>/dev/null \| head -10` | `Bash(ollama:*)` |
| PostgreSQL port scan | `lsof -i :$port -sTCP:LISTEN >/dev/null 2>&1` (loop 5432-5442) | `Bash(lsof:*)` |
| Docker check | `docker --version`, `docker compose version` | `Bash(docker:*)` |
| Docker container status | `docker ps --filter name=agent-brain-postgres ...` | `Bash(docker:*)` |
| Docker container start | `docker compose ... up -d` | `Bash(docker:*)` |
| Directory creation | `mkdir -p ~/.agent-brain` or `mkdir -p ~/.config/agent-brain` | `Bash(mkdir:*)` |
| Config file write | `cat > ~/.agent-brain/config.yaml << 'EOF'` | `Bash(cat:*)` |
| Large-dir scan | `find . -maxdepth 3 -type d ...` + `du -sh "$dir"` + `find "$dir" -type f \| wc -l` | `Bash(find:*)`, `Bash(du:*)` |
| CLI invocations | `agent-brain init`, `agent-brain start`, `agent-brain status`, `agent-brain --version` | `Bash(agent-brain:*)` |
| File permissions | `chmod 600 ~/.agent-brain/config.yaml` | `Bash(chmod:*)` (already allowed) |
| PyPI version check | `curl -sf https://pypi.org/pypi/agent-brain-rag/json \| python3 -c ...` | `Bash(curl:*)` |
| Process check | `ps aux \| grep agent-brain` | `Bash(ps:*)` |
| Server process query | `pgrep -fl agent_brain_server` | `Bash(pgrep:*)` |
| Server health check | `curl -s http://127.0.0.1:.../health` | `Bash(curl:*)` |
| jq config update | `cat config.json \| jq '...' > /tmp/config.json && mv /tmp/config.json ...` | `Bash(jq:*)`, `Bash(mv:*)` |

### Net effect

In the worst case, a completely fresh project triggers **15+ permission prompts** before the wizard completes. The user must repeatedly click "Allow" for benign operations, breaking the agent's flow and defeating the purpose of an automated wizard.

</problem_statement>

<current_permissions>
## Current Permission Allowlist (settings.local.json)

The repo's `.claude/settings.local.json` already authorizes the following (relevant subset):

```json
"Bash(curl:*)",
"Bash(ls:*)",
"Bash(find:*)",
"Bash(chmod:*)",
"Bash(grep:*)",
"Bash(bash:*)",
"Bash(python3:*)",
"Bash(kill:*)"
```

### What Is Missing

These commands are NOT in the current allowlist and will trigger prompts during setup:

| Missing Entry | Used By |
|---------------|---------|
| `Bash(agent-brain:*)` | Every wizard step — CLI is the primary interface |
| `Bash(lsof:*)` | Ollama port check, PostgreSQL port scan |
| `Bash(ollama:*)` | Ollama model list check |
| `Bash(docker:*)` | Docker version check, container management |
| `Bash(mkdir:*)` | Config directory creation |
| `Bash(cat:*)` | Config file write via heredoc |
| `Bash(du:*)` | Large-dir size scan |
| `Bash(ps:*)` | Process existence check |
| `Bash(pgrep:*)` | Server process grep |
| `Bash(jq:*)` | JSON config manipulation |
| `Bash(mv:*)` | Atomic config file replacement |
| `Bash(pip:*)` | pip install checks |
| `Bash(pipx:*)` | pipx installation |
| `Bash(uv:*)` | uv tool install |
| `Bash(conda:*)` | conda env creation |
| `Bash(python:*)` | Python invocations during install |
| `Bash(rg:*)` | ripgrep used in setup.md for backend detection |

### What settings.local.json Is vs. What Users Need

`settings.local.json` is a **developer-only** file (gitignored-style, personal). It does NOT propagate to end-user projects. End users have no pre-populated allowlists when they first run `/agent-brain-setup` in their project.

The question for Phase 24 is: what mechanism gives end-user projects the right allowlist without requiring manual configuration?

</current_permissions>

<permission_model>
## Claude Code Permission Model

Claude Code recognizes two settings files per project:

| File | Scope | Committed? | Description |
|------|-------|-----------|-------------|
| `.claude/settings.json` | Project-wide | Yes (checked in) | Shared with team, applies to all |
| `.claude/settings.local.json` | Personal override | No (gitignored) | Per-developer overrides |

Both files have the same structure:
```json
{
  "permissions": {
    "allow": ["Bash(cmd:*)", "Read(path)"],
    "deny": []
  }
}
```

Permission entries for Bash follow the pattern `Bash(command:arguments_prefix)`. The `*` glob matches any argument string.

### Key Insight

When a user runs `/agent-brain-setup` in their project, Claude Code looks for `.claude/settings.json` in that project directory. If the file exists and pre-authorizes the relevant commands, the wizard runs without interruption.

**The solution**: `agent-brain init` (Phase 22 onward) already creates `.claude/agent-brain/config.json`. It could also write or merge a `.claude/settings.json` with the required wizard permissions. Alternatively, `/agent-brain-setup` can detect the absence of permissions and write the file before proceeding.

</permission_model>

<operations_catalog>
## Catalog of All Permission-Triggering Operations in Setup Flow

### Group 1: Detection / Read-Only (Safe to Always Allow)

These are read-only checks that pose no security risk:

```
Bash(agent-brain:*)         — primary CLI tool
Bash(lsof:*)                — network/port detection
Bash(ollama:*)              — model list check
Bash(docker:*)              — Docker version + container status
Bash(ps:*)                  — process list check
Bash(pgrep:*)               — process grep
Bash(du:*)                  — disk usage check
Bash(wc:*)                  — word/line count (used in find pipes)
```

### Group 2: Configuration Writes (Moderate — Writes to Well-Known Dirs)

These create config directories and files in standard locations:

```
Bash(mkdir:*)               — create ~/.config/agent-brain/, .claude/agent-brain/
Bash(cat:*)                 — write config.yaml via heredoc
Bash(jq:*)                  — JSON manipulation for config.json updates
Bash(mv:*)                  — atomic config file replacement (/tmp → final path)
Bash(tee:*)                 — alternative to cat for writing files
```

### Group 3: Installation (Higher Privilege — Modify Python Environment)

These install software and should be asked about once, not per-command:

```
Bash(pip:*)                 — pip install
Bash(pipx:*)                — pipx install
Bash(uv:*)                  — uv tool install
Bash(conda:*)               — conda env management
Bash(python:*)              — Python invocations
```

### Group 4: Network (External Calls)

These make outbound network requests:

```
Bash(curl:*)                — Already in allowlist; used for Ollama check + PyPI version
```

### Group 5: Service Management (Side Effects on Local State)

```
Bash(docker:*)              — docker compose up -d starts a container
Bash(kill:*)                — Already in allowlist; used for agent-brain stop
```

</operations_catalog>

<gaps_and_approaches>
## Gaps and Proposed Approaches

### Gap 1: No `.claude/settings.json` in End-User Projects

**Problem:** New users have no pre-approved allowlist in their project. The setup wizard triggers prompts for every command.

**Approach A: `agent-brain init` writes permissions automatically**

When `agent-brain init` creates `.claude/agent-brain/config.json`, it also writes (or merges into) `.claude/settings.json` at the project root. The file contains all wizard-required permissions pre-approved.

Pros:
- Self-healing: any project that runs `agent-brain init` gets the permissions
- No manual user action
- Permissions are scoped to the project

Cons:
- `agent-brain init` requires Bash permission itself (chicken-and-egg for first run)
- Writing to `.claude/settings.json` merges with user's existing permissions — could conflict
- Users may not want all these permissions auto-injected

**Approach B: Plugin command writes permissions on first run**

The `/agent-brain-setup` or `/agent-brain-init` plugin command (markdown), before running any Bash, checks for and writes a `.claude/settings.json` if missing. This is executed by the LLM, not the CLI, so it uses the Write tool (not Bash), which is pre-authorized.

Pros:
- No CLI changes needed — pure markdown/plugin change
- Write tool doesn't require pre-authorization
- Can be smarter: only add missing entries, not replace whole file

Cons:
- Relies on LLM doing the right thing
- Write tool writes files atomically, which may break existing settings.json formatting

**Approach C: Ship a `settings.json` template in the plugin**

Add `agent-brain-plugin/templates/settings.json` with all wizard permissions pre-populated. The `/agent-brain-setup` command copies this into the project if `.claude/settings.json` doesn't exist, or instructs the user to do it.

Pros:
- Explicit, auditable — users can see exactly what permissions are granted
- Doesn't require CLI changes
- Can be version-controlled

Cons:
- Manual step (user must copy or approve the copy)
- Doesn't auto-merge with existing settings.json

**Approach D: Document the permissions and tell users to add them manually**

Add a "Pre-Flight Permissions" step to `/agent-brain-setup` that checks for the permissions and explains what to add.

Pros:
- Transparent
- User controls their permissions

Cons:
- Worst UX — exactly the problem we're trying to eliminate

---

### Gap 2: Large-Dir Scan Is Slow and Noisy

**Problem:** `/agent-brain-config` Step 6 runs `find . -maxdepth 3 -type d | while read d; do find "$d" ... | wc -l; done` which:
1. Requires multiple `find` commands (already allowed but still prompts for non-allowlisted users)
2. Can be very slow on large repos
3. Shows a lot of intermediate output

**Approach:** Replace the shell loop with a single `agent-brain scan` CLI subcommand (or reuse existing folder detection logic). One pre-authorized `Bash(agent-brain:*)` call replaces 10+ individual `find`/`du`/`wc` calls.

---

### Gap 3: Ollama Check Uses 3 Methods, 2 of Which Need New Permissions

**Problem:** `/agent-brain-config` Step 2 checks Ollama via curl (allowed), lsof (not allowed), and `ollama list` (not allowed). Without `lsof` and `ollama`, the check degrades to curl-only.

**Approach:** Move the Ollama connectivity check into a single `agent-brain check-ollama` (or `agent-brain verify --ollama`) CLI command. One `Bash(agent-brain:*)` call replaces 3 separate method calls.

---

### Gap 4: PostgreSQL Port Scan Loop (11 lsof calls)

**Problem:** The port scan loop in `/agent-brain-config` and `/agent-brain-setup` runs `lsof -i :$port` 11 times. Even if lsof is allowed, this is 11 prompts without allowlisting.

**Approach:** Add `agent-brain find-port [--start 5432 --end 5442]` or inline port availability check into `agent-brain start --postgres`. One call replaces 11 lsof calls.

---

### Gap 5: Helper Script vs. Consolidated CLI Commands

Two implementation strategies compete:

**Strategy 1: Shell Helper Script**

Create `agent-brain-plugin/scripts/setup-permissions.sh` that runs all the setup detection in one shell script:
```bash
#!/usr/bin/env bash
# Pre-flight checks for agent-brain setup
# Usage: bash setup-permissions.sh
...
```

The plugin pre-authorizes this specific script path:
```json
"Bash(bash agent-brain-plugin/scripts/setup-permissions.sh:*)"
```

Pros:
- Single permission entry covers all sub-operations
- Script can be inspected/audited easily
- Works with existing permission model

Cons:
- Script path must be pre-known (absolute or relative to CWD)
- Doesn't help with the initial `.claude/settings.json` bootstrap

**Strategy 2: CLI Subcommands**

Add subcommands to `agent-brain-cli` that consolidate detection:
- `agent-brain check` — checks installation, providers, Ollama, Docker
- `agent-brain scan` — large-dir scan, returns JSON
- `agent-brain find-port [--start N --end N]` — port availability

Plugin uses `Bash(agent-brain:*)` for everything. One allowlist entry covers all wizard operations.

Pros:
- Cleanest solution — agent-brain becomes self-contained
- `Bash(agent-brain:*)` is already the natural permission entry
- No script path management

Cons:
- Requires CLI changes (out of scope for "plugin-only" phase)
- Adds surface area to the CLI

---

### Recommended Approach

Combine the following:

1. **Approach B** for bootstrapping: The `/agent-brain-setup` plugin command uses the `Write` tool to create/merge `.claude/settings.json` before running any Bash. This breaks the chicken-and-egg problem.

2. **Approach C** as a template: Ship `agent-brain-plugin/templates/settings.json` with the full permission set documented. The setup command can reference this template when writing.

3. **Strategy 1 (helper script)** for consolidating detection-only operations: Create `agent-brain-plugin/scripts/ab-setup-check.sh` to bundle config detection, Ollama check, Docker check, and large-dir scan into a single script invocation. Add `Bash(bash:*)` (already in allowlist) plus the specific script path.

4. **Deferred**: CLI subcommands (`agent-brain check`, `agent-brain scan`) are a better long-term solution but require CLI changes. Mark as follow-on work for Phase 25 or a separate micro-phase.

</gaps_and_approaches>

<code_context>
## Relevant Files

### Plugin Commands (Read-Only for Phase 24 Research)

- `/agent-brain-plugin/commands/agent-brain-setup.md` — orchestrates full setup; runs ls, curl, lsof, mkdir, agent-brain commands
- `/agent-brain-plugin/commands/agent-brain-config.md` — provider selection; runs curl (Ollama), lsof (port scan), du/find (large-dir), mkdir, cat (config write), chmod, jq
- `/agent-brain-plugin/commands/agent-brain-init.md` — runs `agent-brain init` + `ls -la`
- `/agent-brain-plugin/commands/agent-brain-install.md` — runs pip/pipx/uv/conda + curl (PyPI check)
- `/agent-brain-plugin/commands/agent-brain-start.md` — runs ls + `agent-brain start` + `agent-brain status`
- `/agent-brain-plugin/commands/agent-brain-verify.md` — runs agent-brain + python + ls + curl

### CLI Commands

- `/agent-brain-cli/agent_brain_cli/commands/init.py` — creates `.claude/agent-brain/` dirs and `config.json`
- `/agent-brain-cli/agent_brain_cli/commands/start.py` — spawns uvicorn server subprocess; reads/writes `runtime.json`; updates `~/.agent-brain/registry.json`

### Permission Files

- `/.claude/settings.local.json` — developer personal allowlist (not end-user facing)
- No `.claude/settings.json` exists at project root (needs to be created for team/plugin use)

### Plugin Templates

- `/agent-brain-plugin/templates/` — contains `docker-compose.postgres.yml`; could also host `settings.json`

</code_context>

<specifics>
## Specific Findings

### What the Wizard Actually Needs (Minimal Allowlist)

Based on reading all setup command files, the minimum permission set to run the full wizard without prompts is:

```json
{
  "permissions": {
    "allow": [
      "Bash(agent-brain:*)",
      "Bash(lsof:*)",
      "Bash(ollama:*)",
      "Bash(docker:*)",
      "Bash(mkdir:*)",
      "Bash(cat:*)",
      "Bash(jq:*)",
      "Bash(mv:*)",
      "Bash(du:*)",
      "Bash(ps:*)",
      "Bash(pgrep:*)",
      "Bash(pip:*)",
      "Bash(pipx:*)",
      "Bash(uv:*)",
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(rg:*)",
      "Bash(curl:*)",
      "Bash(ls:*)",
      "Bash(find:*)",
      "Bash(chmod:*)",
      "Bash(grep:*)",
      "Bash(wc:*)",
      "Bash(bash:*)"
    ]
  }
}
```

Note: `curl`, `ls`, `find`, `chmod`, `grep`, `python3`, `bash` are already in `settings.local.json`. The new additions needed are: `agent-brain`, `lsof`, `ollama`, `docker`, `mkdir`, `cat`, `jq`, `mv`, `du`, `ps`, `pgrep`, `pip`, `pipx`, `uv`, `python`, `rg`, `wc`.

### The Chicken-and-Egg Problem

The `/agent-brain-setup` command must write `.claude/settings.json` BEFORE running any Bash. Since `Write` tool is always available (not permission-gated), the command can:
1. Use `Write` tool to create `.claude/settings.json` with the required entries
2. Tell the user: "I've created `.claude/settings.json` with the permissions required for setup. Please approve the file write, then I'll proceed."
3. After the file is written, subsequent Bash calls will be pre-authorized.

### Helper Script Scope

If a helper script is created, its primary job should be **detection + read-only checks** (no writes, no installs):

```bash
#!/usr/bin/env bash
# ab-setup-check.sh — Agent Brain pre-flight checks
# Outputs JSON with current state for the setup wizard
{
  "agent_brain_installed": ...,
  "agent_brain_version": ...,
  "config_file_found": ...,
  "config_file_path": ...,
  "ollama_running": ...,
  "ollama_models": [...],
  "docker_available": ...,
  "python_version": ...,
  "api_keys": { "openai": ..., "anthropic": ... },
  "large_dirs": [...]
}
```

The wizard reads this JSON once and branches based on state — no further detection commands needed.

### Impact on Phase 22 (Setup Wizard)

Phase 22 restores the full setup wizard. Phase 24 removes the permission friction that makes the Phase 22 wizard frustrating. They are complementary: Phase 22 adds the wizard steps, Phase 24 ensures those steps run without interruption. Phase 24 **must follow** Phase 22 (wizard must be complete before we can enumerate all its permission needs).

Phase 24 depends on Phase 23 (XDG migration) because the new config paths introduced in Phase 23 (`~/.config/agent-brain/`) will be referenced in the setup commands. The allowlist and helper script must account for both old (`~/.agent-brain/`) and new (`~/.config/agent-brain/`) paths.

</specifics>
