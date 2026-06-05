# Phase 20: Plugin Skill Next-Step Hints Should Suggest Slash Commands - Research

**Researched:** 2026-03-12
**Domain:** Claude Code plugin command files (Markdown), slash command UX
**Confidence:** HIGH

## Summary

Phase 20 is a pure documentation/content fix with zero Python code changes. Every command file
in `agent-brain-plugin/commands/` is a Markdown file that Claude Code interprets as a slash
command. When a command's output section includes "Next steps" with `agent-brain start` (a bare
CLI invocation), Claude cannot autocomplete it. When the hint uses `/agent-brain:agent-brain-start`
(a slash command), Claude's autocomplete picks it up and the user can invoke it directly.

The fix requires auditing every command's `## Output` and related guidance sections and replacing
bare CLI invocations in "next step" positions with the canonical slash command form. The change is
purely textual — no Python, no tests, no server logic.

The plugin's namespace is `agent-brain` (from `.claude-plugin/plugin.json`), so all slash commands
take the form `/agent-brain:agent-brain-{command}`. For example, `agent-brain start` becomes
`/agent-brain:agent-brain-start`.

**Primary recommendation:** Audit all 29 command `.md` files for bare CLI hints in next-step
positions and replace them with the corresponding `/agent-brain:agent-brain-{command}` form.
Execution blocks inside ` ```bash ``` ` code fences should stay as CLI commands — only the
human-facing "what to do next" guidance should use slash commands.

## Phase Requirements

This phase defines new requirements (TBD per roadmap). Based on the problem statement, the
requirements are:

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| HINT-01 | All "Next steps" guidance in command files uses slash commands, not bare CLI commands | Direct: every `## Output` section found with CLI commands in next-step text |
| HINT-02 | Execution blocks (```bash``` fences) keep CLI commands — only guidance prose changes | Separation of execution from guidance is already the pattern in the codebase |
| HINT-03 | Skill SKILL.md files use slash command form in quick-start / server-management sections where they suggest follow-on actions | Using-agent-brain SKILL.md Server Management section uses bare CLI in its "Quick Start" checklist |
| HINT-04 | Slash command format used is `/agent-brain:agent-brain-{cmd}` (namespace:command) | Confirmed from plugin.json plugin name "agent-brain" and problem description example |
</phase_requirements>

---

## Standard Stack

### Core

| Item | Value | Purpose | Why This |
|------|-------|---------|----------|
| File format | Markdown (`.md`) | Claude Code command definition | Format required by Claude Code plugin system |
| Plugin namespace | `agent-brain` (from `.claude-plugin/plugin.json`) | Prefix for slash commands | Defines the `/agent-brain:` prefix |
| Slash command form | `/agent-brain:agent-brain-{cmd}` | What users type in Claude Code | Namespace + command name as defined in frontmatter |

### No Installation Needed

This phase touches Markdown files only. No `npm install`, `poetry install`, or dependency changes.

---

## Architecture Patterns

### Plugin Command Structure

Each file in `agent-brain-plugin/commands/` is one slash command:

```
agent-brain-plugin/
  commands/
    agent-brain-init.md          -> /agent-brain:agent-brain-init
    agent-brain-start.md         -> /agent-brain:agent-brain-start
    agent-brain-stop.md          -> /agent-brain:agent-brain-stop
    agent-brain-index.md         -> /agent-brain:agent-brain-index
    agent-brain-status.md        -> /agent-brain:agent-brain-status
    agent-brain-search.md        -> /agent-brain:agent-brain-search
    agent-brain-query.md         (not present — search aliases cover this)
    ...
  skills/
    using-agent-brain/SKILL.md   -> skill loaded for knowledge
    configuring-agent-brain/SKILL.md
```

### Pattern: Execution vs Guidance Sections

Command files have a consistent structure:

- `## Execution` — contains ```` ```bash```` blocks with CLI commands to run. **Keep CLI here.**
- `## Output` — describes what Claude should display. **Slash commands go here.**
- `## Error Handling` — error table with `Resolution` column. CLI acceptable here (terminal recovery).
- `## Related Commands` — table linking to other slash commands. **Already uses slash commands — keep.**
- `## Notes` — prose. **Any follow-on action hints should use slash commands.**

### Pattern: Correct Slash Command Form

```
/agent-brain:agent-brain-start          (start server)
/agent-brain:agent-brain-stop           (stop server)
/agent-brain:agent-brain-init           (initialize project)
/agent-brain:agent-brain-index <path>   (index documents)
/agent-brain:agent-brain-status         (check status)
/agent-brain:agent-brain-search "q"     (hybrid search)
/agent-brain:agent-brain-jobs           (list jobs)
/agent-brain:agent-brain-cache status   (cache metrics)
/agent-brain:agent-brain-reset          (clear index)
/agent-brain:agent-brain-verify         (verify setup)
/agent-brain:agent-brain-config         (configure)
```

### Anti-Patterns to Avoid

- **Changing bash execution blocks:** `## Execution` sections with ` ```bash ``` ` fences contain
  CLI commands that Claude actually runs. Do NOT change `agent-brain start` inside a bash fence.
- **Changing error recovery CLI commands:** Resolution columns in error tables often show terminal
  commands. These are acceptable to leave as CLI since they are manual recovery steps, not next-step
  suggestions to Claude.
- **Mixing formats:** A single "Next steps" list should use ALL slash commands, not a mix of
  `/agent-brain:agent-brain-start` and `agent-brain index ./docs`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Plugin command dispatch | Custom routing logic | Claude Code plugin system | The platform handles routing from slash command to .md file |
| Slash command autocomplete | Any code | Just use the `/namespace:command` format in text | Claude Code auto-indexes plugin commands for autocomplete |

---

## Common Pitfalls

### Pitfall 1: Changing Bash Execution Blocks

**What goes wrong:** Replacing `agent-brain start` inside ` ```bash ``` ` with
`/agent-brain:agent-brain-start`. Claude Code parses the Bash tool call from those blocks — it
cannot run a slash command as a bash command.

**Why it happens:** The pattern looks identical at a glance.

**How to avoid:** Only change bare CLI commands in prose, output examples, and "Next steps" lists
OUTSIDE of ` ```bash ``` ` fences.

**Warning signs:** If a suggested next step is inside a triple-backtick code block.

### Pitfall 2: Wrong Slash Command Format

**What goes wrong:** Writing `/agent-brain-start` (without namespace prefix) instead of
`/agent-brain:agent-brain-start`.

**Why it happens:** The README and some existing files use the short form without namespace prefix
when documenting commands from inside the plugin itself. But the correct autocomplete-triggering
form is always `/{namespace}:{command}`.

**How to avoid:** Always use the full `/agent-brain:agent-brain-{cmd}` form in next-step hints.

**Note:** The problem description confirms the correct form is `/agent-brain:agent-brain-start`,
not `/agent-brain-start`.

### Pitfall 3: Missing the skill SKILL.md Quick Start

**What goes wrong:** Fixing all command files but leaving SKILL.md "Quick Start" checklist using
bare CLI.

**Why it happens:** Skills are not commands — they are loaded differently — but they still surface
guidance to Claude.

**How to avoid:** The `using-agent-brain/SKILL.md` Server Management section has a "Quick Start"
and "Lifecycle Commands" table that uses bare CLI. These should be updated to slash commands in
the hint/guidance form.

### Pitfall 4: Incomplete Audit

**What goes wrong:** Fixing the obvious `agent-brain-init.md` but missing subtler hints in other
files (error handling sections, notes sections).

**How to avoid:** Use a systematic grep pass to find ALL bare CLI commands in non-bash-fence
positions across all 29 command files and both skill files.

---

## Code Examples

### Current State (WRONG — bare CLI in next-step output)

From `agent-brain-init.md`, lines 62-65 — the "Output" section sample:

```
Next steps:
  1. Start server: agent-brain start
  2. Index documents: agent-brain index ./docs
  3. Search: agent-brain query "your query"
```

### Correct State (RIGHT — slash commands in next-step output)

```
Next steps:
  1. Start server: /agent-brain:agent-brain-start
  2. Index documents: /agent-brain:agent-brain-index ./docs
  3. Search: /agent-brain:agent-brain-search "your query"
```

### Keep as-is (bash execution block — correct to leave as CLI)

From `agent-brain-init.md`, `## Execution` section:

```bash
agent-brain init
```

This stays as CLI — Claude runs this via the Bash tool.

### Current State (WRONG — agent-brain-setup.md "Quick start" section)

```
Next steps:
  1. Index documents: /agent-brain-index <path>    <- missing namespace
  2. Search: /agent-brain-search "your query"       <- missing namespace

Quick start:
  agent-brain index ./docs                          <- bare CLI
  agent-brain query "authentication"               <- bare CLI
```

### Correct State

```
Next steps:
  1. Index documents: /agent-brain:agent-brain-index <path>
  2. Search: /agent-brain:agent-brain-search "your query"

Quick start:
  /agent-brain:agent-brain-index ./docs
  /agent-brain:agent-brain-search "authentication"
```

---

## Full File Audit

### Files with confirmed bare CLI in next-step / guidance positions

| File | Location | Current text | Fix needed |
|------|----------|--------------|------------|
| `commands/agent-brain-init.md` | Lines 62-65, Output section | `agent-brain start`, `agent-brain index ./docs`, `agent-brain query "your query"` | Replace with slash commands |
| `commands/agent-brain-setup.md` | Lines 174-180, Output section | `/agent-brain-index <path>` (missing namespace), `agent-brain index ./docs`, `agent-brain query "authentication"` | Fix namespace + replace bare CLI |
| `commands/agent-brain-start.md` | Line 83, Output section | `agent-brain status`, `agent-brain stop`, `agent-brain stop && agent-brain start` | Replace with slash commands |
| `commands/agent-brain-reset.md` | Line 93, Output section | `agent-brain index <path>` | Replace with slash command |
| `commands/agent-brain-cache.md` | Line 170, Output section | "reindex to rebuild the cache" (prose — no CLI but could link slash command) | Add `/agent-brain:agent-brain-index` reference |
| `commands/agent-brain-stop.md` | Line 83, Notes section | `agent-brain start` | Replace with slash command |
| `skills/using-agent-brain/SKILL.md` | Lines 272-285, Server Management "Quick Start" | `agent-brain init`, `agent-brain start`, `agent-brain index ./docs`, etc. | Replace with slash commands |
| `skills/configuring-agent-brain/SKILL.md` | Lines 42-62, Quick Setup | `agent-brain init`, `agent-brain start`, `agent-brain status` | Replace with slash commands |
| `skills/configuring-agent-brain/references/configuration-guide.md` | Lines 469-471, Next Steps | `agent-brain init`, `agent-brain start`, `agent-brain index /path/to/docs` | Replace with slash commands |
| `skills/configuring-agent-brain/references/installation-guide.md` | Lines 394-395, Next Steps | `agent-brain init`, `agent-brain start` | Replace with slash commands |

### Files with confirmed correct slash command patterns (no changes needed)

| File | Status |
|------|--------|
| `commands/agent-brain-install.md` | Already uses `/agent-brain-config`, `/agent-brain-init`, `/agent-brain-start` — but MISSING namespace prefix; needs `:agent-brain:` prefix |
| `commands/agent-brain-config.md` | Next steps use `/agent-brain-init`, `/agent-brain-start` — MISSING namespace prefix |
| `commands/agent-brain-bm25.md` | Related Commands use correct `/agent-brain-vector` etc — but still MISSING namespace prefix |

**Important finding:** Multiple files already use `/agent-brain-{cmd}` (short form without namespace
`agent-brain:`) in "Related Commands" tables. Per the problem description, the correct form is
`/agent-brain:agent-brain-{cmd}`. This means the Related Commands tables also need updating for
all files that omit the namespace prefix.

**Exception:** Files installed inside the plugin directory itself may work without the namespace
prefix when referenced locally. Verify this with the problem owner — the problem description
explicitly uses `/agent-brain:agent-brain-start` with the full prefix. Apply full prefix everywhere
to be consistent.

---

## Complete Command Mapping

All 29 command files and their slash command equivalents:

| File | Slash Command |
|------|--------------|
| `agent-brain-bm25.md` | `/agent-brain:agent-brain-bm25` |
| `agent-brain-cache.md` | `/agent-brain:agent-brain-cache` |
| `agent-brain-config.md` | `/agent-brain:agent-brain-config` |
| `agent-brain-embeddings.md` | `/agent-brain:agent-brain-embeddings` |
| `agent-brain-folders.md` | `/agent-brain:agent-brain-folders` |
| `agent-brain-graph.md` | `/agent-brain:agent-brain-graph` |
| `agent-brain-help.md` | `/agent-brain:agent-brain-help` |
| `agent-brain-hybrid.md` | `/agent-brain:agent-brain-hybrid` |
| `agent-brain-index.md` | `/agent-brain:agent-brain-index` |
| `agent-brain-init.md` | `/agent-brain:agent-brain-init` |
| `agent-brain-inject.md` | `/agent-brain:agent-brain-inject` |
| `agent-brain-install.md` | `/agent-brain:agent-brain-install` |
| `agent-brain-jobs.md` | `/agent-brain:agent-brain-jobs` |
| `agent-brain-keyword.md` | `/agent-brain:agent-brain-keyword` |
| `agent-brain-list.md` | `/agent-brain:agent-brain-list` |
| `agent-brain-multi.md` | `/agent-brain:agent-brain-multi` |
| `agent-brain-providers.md` | `/agent-brain:agent-brain-providers` |
| `agent-brain-reset.md` | `/agent-brain:agent-brain-reset` |
| `agent-brain-search.md` | `/agent-brain:agent-brain-search` |
| `agent-brain-semantic.md` | `/agent-brain:agent-brain-semantic` |
| `agent-brain-setup.md` | `/agent-brain:agent-brain-setup` |
| `agent-brain-start.md` | `/agent-brain:agent-brain-start` |
| `agent-brain-status.md` | `/agent-brain:agent-brain-status` |
| `agent-brain-stop.md` | `/agent-brain:agent-brain-stop` |
| `agent-brain-summarizer.md` | `/agent-brain:agent-brain-summarizer` |
| `agent-brain-types.md` | `/agent-brain:agent-brain-types` |
| `agent-brain-vector.md` | `/agent-brain:agent-brain-vector` |
| `agent-brain-verify.md` | `/agent-brain:agent-brain-verify` |
| `agent-brain-version.md` | `/agent-brain:agent-brain-version` |

---

## Validation Architecture

`workflow.nyquist_validation` key is absent from `.planning/config.json` — treated as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None applicable — this phase contains no Python code |
| Config file | N/A |
| Quick run command | Manual inspection: `grep -r "agent-brain " agent-brain-plugin/commands/ \| grep -v "^\`\`\`"` |
| Full suite command | `grep -rn "agent-brain " agent-brain-plugin/ \| grep -v "bash\|^\`\`\`\|/agent-brain:"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| HINT-01 | All Next-steps guidance uses slash commands | manual-only | `grep -rn "Next steps" agent-brain-plugin/commands/` then visual inspect | N/A |
| HINT-02 | Bash fences unchanged | manual-only | Read each changed file and verify bash blocks unchanged | N/A |
| HINT-03 | SKILL.md quick-start sections use slash commands | manual-only | Inspect `skills/*/SKILL.md` | N/A |
| HINT-04 | Format is `/agent-brain:agent-brain-{cmd}` | manual-only | `grep -rn "/agent-brain-" agent-brain-plugin/ \| grep -v "agent-brain:agent-brain"` should return only external references | N/A |

**Justification for manual-only:** These are Markdown content changes with no executable code.
Automated unit tests would just re-implement the same regex check in a different language — the
manual grep pass is the correct verification approach for this phase.

### Wave 0 Gaps

None — no test infrastructure needed for Markdown-only changes.

---

## Open Questions

1. **Short form vs full namespace form in Related Commands tables**
   - What we know: Most Related Commands tables already use `/agent-brain-{cmd}` (short, no namespace)
   - What's unclear: Whether Claude Code resolves these correctly inside a plugin context without the namespace prefix
   - Recommendation: Use the full `/agent-brain:agent-brain-{cmd}` form everywhere for consistency; matches the problem description example

2. **Skill SKILL.md Quick Setup bash blocks**
   - What we know: `configuring-agent-brain/SKILL.md` Quick Setup sections have bash blocks like `agent-brain init` inside ` ```bash ``` ` fences
   - What's unclear: Should these be changed? They are not "next step hints" — they are setup instructions that Claude executes
   - Recommendation: Leave bash execution blocks as CLI; only update prose "next step" text and verification checklists

---

## Sources

### Primary (HIGH confidence)

- Direct file inspection: `agent-brain-plugin/commands/agent-brain-init.md` — confirmed bare CLI in Output next-steps (lines 62-65)
- Direct file inspection: `agent-brain-plugin/.claude-plugin/plugin.json` — confirmed plugin namespace is `agent-brain`
- Direct file inspection: Problem description in additional_context — confirms `/agent-brain:agent-brain-start` is the correct form

### Secondary (MEDIUM confidence)

- Grep across all 29 command files + skill files — identified all locations needing changes
- Pattern observation: "Related Commands" sections already use `/agent-brain-{cmd}` consistently — confirms Claude Code renders these as clickable links

### Tertiary (LOW confidence)

- None

---

## Metadata

**Confidence breakdown:**
- Scope of changes: HIGH — all files identified via direct inspection
- Correct slash command format: HIGH — confirmed from problem description + plugin.json
- Whether short `/agent-brain-{cmd}` vs full `/agent-brain:agent-brain-{cmd}` is required: MEDIUM — problem description strongly implies full form, but not tested in production

**Research date:** 2026-03-12
**Valid until:** 2026-06-12 (stable — Markdown content, plugin format unlikely to change)
