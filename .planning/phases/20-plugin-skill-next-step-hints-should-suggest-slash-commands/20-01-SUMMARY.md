---
phase: 20-plugin-skill-next-step-hints-should-suggest-slash-commands
plan: 01
subsystem: plugin
tags: [claude-code, plugin, slash-commands, documentation, ux, autocomplete]

# Dependency graph
requires:
  - phase: 19-plugin-and-skill-updates-for-embedding-cache-management
    provides: plugin command files that were updated for embedding cache management
provides:
  - All 29 plugin command .md files use /agent-brain:agent-brain-{cmd} slash command format in guidance positions
  - Skill SKILL.md and reference docs use full slash command format in next-step hints
  - Users get Claude Code autocomplete when following next-step guidance
affects:
  - Any future plugin command files must use /agent-brain:agent-brain-{cmd} format in guidance prose

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Slash command format: /agent-brain:agent-brain-{cmd} (namespace:command) for Claude Code autocomplete"
    - "Bash execution blocks keep bare CLI; prose next-step hints use slash commands"

key-files:
  created: []
  modified:
    - agent-brain-plugin/commands/agent-brain-init.md
    - agent-brain-plugin/commands/agent-brain-setup.md
    - agent-brain-plugin/commands/agent-brain-start.md
    - agent-brain-plugin/commands/agent-brain-stop.md
    - agent-brain-plugin/commands/agent-brain-reset.md
    - agent-brain-plugin/commands/agent-brain-cache.md
    - agent-brain-plugin/commands/agent-brain-install.md
    - agent-brain-plugin/commands/agent-brain-config.md
    - agent-brain-plugin/commands/agent-brain-bm25.md
    - agent-brain-plugin/commands/agent-brain-embeddings.md
    - agent-brain-plugin/commands/agent-brain-folders.md
    - agent-brain-plugin/commands/agent-brain-graph.md
    - agent-brain-plugin/commands/agent-brain-help.md
    - agent-brain-plugin/commands/agent-brain-hybrid.md
    - agent-brain-plugin/commands/agent-brain-index.md
    - agent-brain-plugin/commands/agent-brain-inject.md
    - agent-brain-plugin/commands/agent-brain-jobs.md
    - agent-brain-plugin/commands/agent-brain-keyword.md
    - agent-brain-plugin/commands/agent-brain-list.md
    - agent-brain-plugin/commands/agent-brain-multi.md
    - agent-brain-plugin/commands/agent-brain-providers.md
    - agent-brain-plugin/commands/agent-brain-search.md
    - agent-brain-plugin/commands/agent-brain-semantic.md
    - agent-brain-plugin/commands/agent-brain-status.md
    - agent-brain-plugin/commands/agent-brain-summarizer.md
    - agent-brain-plugin/commands/agent-brain-types.md
    - agent-brain-plugin/commands/agent-brain-vector.md
    - agent-brain-plugin/commands/agent-brain-verify.md
    - agent-brain-plugin/commands/agent-brain-version.md
    - agent-brain-plugin/skills/using-agent-brain/SKILL.md
    - agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md
    - agent-brain-plugin/skills/configuring-agent-brain/references/installation-guide.md

key-decisions:
  - "All /agent-brain-{cmd} short-form slash commands replaced with /agent-brain:agent-brain-{cmd} full namespace form"
  - "Bash execution blocks (```bash``` fences) left unchanged with bare CLI commands"
  - "Usage sections, Related Commands tables, Output sections, Notes, and Examples all updated"

patterns-established:
  - "Plugin command guidance: always use /agent-brain:agent-brain-{cmd} in prose, /cmd in bash fences"
  - "Related Commands tables use full /namespace:command format for Claude Code autocomplete"

requirements-completed: [HINT-01, HINT-02, HINT-03]

# Metrics
duration: 25min
completed: 2026-03-13
---

# Phase 20 Plan 01: Plugin Slash Command Hints Summary

**All 29 plugin command files and 3 skill/reference docs updated to use /agent-brain:agent-brain-{cmd} slash command format in guidance positions, enabling Claude Code autocomplete for next-step hints**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-13T01:58:00Z
- **Completed:** 2026-03-13T02:23:32Z
- **Tasks:** 2
- **Files modified:** 32

## Accomplishments
- Updated all 29 command .md files: Usage sections, Related Commands tables, Output next-steps, Notes — all use full /agent-brain:agent-brain-{cmd} format
- Updated using-agent-brain/SKILL.md Progress Checklist and Lifecycle Commands table to slash command format
- Updated configuration-guide.md and installation-guide.md Next Steps sections
- Bash execution blocks (```bash``` fences) preserved with CLI commands throughout

## Task Commits

Each task was committed atomically:

1. **Task 1: Update all 29 command .md files** - `3938999` (feat)
2. **Task 2: Update skill files and reference docs** - `2873c53` (feat)

## Files Created/Modified

**Command files (29 total):**
- `agent-brain-plugin/commands/agent-brain-*.md` - All 29 command files updated with /agent-brain:agent-brain-{cmd} format

**Skill files (3 total):**
- `agent-brain-plugin/skills/using-agent-brain/SKILL.md` - Progress Checklist and Lifecycle Commands table updated
- `agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md` - Next Steps section updated
- `agent-brain-plugin/skills/configuring-agent-brain/references/installation-guide.md` - Next Steps section updated

## Decisions Made
- Applied full replace_all updates for each command name to ensure consistency
- Left configuring-agent-brain/SKILL.md bash blocks unchanged (Quick Setup Options A and B are execution blocks)
- Verification checklist backtick items in SKILL.md left as-is (they reference bash commands directly, not slash command guidance)

## Deviations from Plan

None - plan executed exactly as written. All 29 command files and all 4 skill/reference files updated as specified. Bash fences verified unchanged.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All plugin command and skill files now use consistent slash command format
- Users invoking next-step hints in Claude Code will get autocomplete suggestions
- Ready for any future plugin updates

---
*Phase: 20-plugin-skill-next-step-hints-should-suggest-slash-commands*
*Completed: 2026-03-13*
