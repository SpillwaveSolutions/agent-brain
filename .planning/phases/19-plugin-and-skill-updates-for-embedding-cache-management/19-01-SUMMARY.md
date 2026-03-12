---
phase: 19-plugin-and-skill-updates-for-embedding-cache-management
plan: 01
subsystem: plugin
tags: [embedding-cache, claude-code-plugin, slash-commands, skills, api-reference, markdown]

# Dependency graph
requires:
  - phase: 16-embedding-cache
    provides: "agent-brain cache CLI commands (cache status, cache clear) and REST endpoints (GET/DELETE /index/cache)"

provides:
  - "/agent-brain-cache slash command with status and clear subcommands + confirmation gate"
  - "CACHE COMMANDS category in agent-brain-help.md display section and command reference table"
  - "GET /index/cache and DELETE /index/cache documented in api_reference.md with response schemas"
  - "Cache Management section in using-agent-brain SKILL.md with when-to-check/when-to-clear guidance"
  - "Cache performance check step in search-assistant.md agent"
  - "EMBEDDING_CACHE_MAX_MEM_ENTRIES and EMBEDDING_CACHE_MAX_DISK_MB in configuring-agent-brain SKILL.md"

affects: [using-agent-brain, configuring-agent-brain, search-assistant, agent-brain-plugin]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Subcommand parameter pattern in plugin command files (status|clear via single agent-brain-cache.md)"
    - "Confirmation gate pattern for destructive cache operations (per agent-brain-reset.md convention)"
    - "Cache trigger phrases in SKILL.md YAML description for automatic skill activation"

key-files:
  created:
    - agent-brain-plugin/commands/agent-brain-cache.md
  modified:
    - agent-brain-plugin/commands/agent-brain-help.md
    - agent-brain-plugin/skills/using-agent-brain/references/api_reference.md
    - agent-brain-plugin/skills/using-agent-brain/SKILL.md
    - agent-brain-plugin/agents/search-assistant.md
    - agent-brain-plugin/skills/configuring-agent-brain/SKILL.md

key-decisions:
  - "Single agent-brain-cache.md with subcommand parameter (not two separate files) — consistent with existing multi-operation pattern"
  - "Cache Management section placed before When Not to Use in SKILL.md — maintains logical flow from operations to boundaries"
  - "Confirmation gate for cache clear documents manual prompt text — matches agent-brain-reset.md destructive operation pattern"
  - "Both /index/cache and /index/cache/ documented in API reference — FastAPI trailing-slash alias behavior needs explicit documentation"
  - "Cache env vars added to configuring-agent-brain, not using-agent-brain — follows skill scope boundary (config vs usage)"

patterns-established:
  - "Subcommand parameter pattern: single command file with required subcommand parameter for multi-operation commands"
  - "Trigger phrase extension: append new capabilities to YAML description without replacing existing phrases"
  - "Section placement: new operational sections go before When Not to Use in SKILL.md"

requirements-completed: [XCUT-03]

# Metrics
duration: 2min
completed: 2026-03-12
---

# Phase 19 Plan 01: Plugin and Skill Updates for Embedding Cache Management Summary

**New `/agent-brain-cache` slash command (status + clear with confirmation gate) + API reference docs for `GET/DELETE /index/cache` + cache-aware skill guidance and agent hints across 6 plugin files**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-12T22:10:28Z
- **Completed:** 2026-03-12T22:13:15Z
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 updated)

## Accomplishments

- Created `agent-brain-cache.md` slash command with both status and clear subcommand execution flows, confirmation gate for destructive clear, error handling table, and `--url` / `--json` / `--yes` parameter documentation
- Updated `agent-brain-help.md` with CACHE COMMANDS category in both the human-readable display section and the command reference table (both locations per research pitfall warning)
- Added `## Cache Endpoints` section to `api_reference.md` with correct paths (`GET /index/cache`, `DELETE /index/cache`), full response schemas, field descriptions, trailing-slash alias note, and 503 error documentation
- Added Cache Management section to `using-agent-brain/SKILL.md` with when-to-check and when-to-clear guidance plus cache trigger phrases in YAML description
- Added cache performance check step (step 6) to `search-assistant.md` with actionable advice for low hit rates and provider changes
- Added `EMBEDDING_CACHE_MAX_MEM_ENTRIES` and `EMBEDDING_CACHE_MAX_DISK_MB` env vars plus Embedding Cache Tuning note to `configuring-agent-brain/SKILL.md`

## Task Commits

Each task was committed atomically:

1. **Task 1: Create cache slash command + update help + update API reference** - `f4626a9` (feat)
2. **Task 2: Update skills and agent for cache awareness** - `f6338b3` (feat)

## Files Created/Modified

- `agent-brain-plugin/commands/agent-brain-cache.md` — New slash command for cache status and clear with subcommand parameter, confirmation gate, output formats, and error handling
- `agent-brain-plugin/commands/agent-brain-help.md` — Added CACHE COMMANDS category block and agent-brain-cache row in Command Reference table
- `agent-brain-plugin/skills/using-agent-brain/references/api_reference.md` — Added Cache Endpoints section (GET/DELETE /index/cache) and cache CLI commands to CLI Commands Reference
- `agent-brain-plugin/skills/using-agent-brain/SKILL.md` — Added cache trigger phrases to YAML description, Cache Management to Contents, Cache Management section before When Not to Use
- `agent-brain-plugin/agents/search-assistant.md` — Added cache trigger pattern and cache performance check step in assistance flow
- `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` — Added EMBEDDING_CACHE_MAX_MEM_ENTRIES and EMBEDDING_CACHE_MAX_DISK_MB rows plus Embedding Cache Tuning section

## Decisions Made

- Single `agent-brain-cache.md` with a required `subcommand` parameter (`status` | `clear`) — matches the multi-operation pattern used elsewhere in the plugin; avoids proliferating command files
- Confirmation gate for clear mirrors `agent-brain-reset.md` pattern exactly — users clearing the embedding cache should see the same confirmation UX as clearing the document index
- Both `/index/cache` and `/index/cache/` documented with trailing-slash alias note — research identified this as pitfall 3 (FastAPI 307 redirect behavior)
- Cache env vars placed in `configuring-agent-brain` (not `using-agent-brain`) — respects skill scope boundary: config skill owns all tunables, usage skill owns operational guidance
- Cache Management section added before "When Not to Use" in SKILL.md — consistent with existing section ordering (operational sections before scope/boundary sections)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The embedding cache is automatic and requires no setup.

## Next Phase Readiness

- Phase 19 Plan 01 complete: all 6 plugin files updated with embedding cache management surface
- Plugin users can now check and clear the embedding cache entirely through Claude Code without dropping to terminal
- XCUT-03 requirement (plugin skills and commands updated for new CLI features) is satisfied
- Closes the plugin/skill gap from Phase 16 backend work

---
*Phase: 19-plugin-and-skill-updates-for-embedding-cache-management*
*Completed: 2026-03-12*
