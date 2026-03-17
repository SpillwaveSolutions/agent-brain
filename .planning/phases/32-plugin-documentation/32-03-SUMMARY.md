---
phase: 32-plugin-documentation
plan: 03
subsystem: documentation
tags: [plugin, skills, agents, reference-guides, v7, v8, v9, multi-runtime]

requires:
  - phase: 32-plugin-documentation
    provides: "Audited plugin command files (plans 01-02)"
provides:
  - "16 audited skill reference guides with v7-v9 feature coverage"
  - "3 audited agent descriptions matching actual CLI capabilities"
affects: [33-cross-references-metadata]

tech-stack:
  added: []
  patterns: ["documentation-audit-against-source-code"]

key-files:
  created: []
  modified:
    - agent-brain-plugin/skills/using-agent-brain/references/installation-guide.md
    - agent-brain-plugin/skills/using-agent-brain/references/provider-configuration.md
    - agent-brain-plugin/skills/using-agent-brain/references/api_reference.md
    - agent-brain-plugin/skills/using-agent-brain/references/hybrid-search-guide.md
    - agent-brain-plugin/skills/using-agent-brain/references/vector-search-guide.md
    - agent-brain-plugin/skills/using-agent-brain/references/integration-guide.md
    - agent-brain-plugin/skills/using-agent-brain/references/interactive-setup.md
    - agent-brain-plugin/skills/using-agent-brain/references/server-discovery.md
    - agent-brain-plugin/skills/using-agent-brain/references/troubleshooting-guide.md
    - agent-brain-plugin/skills/using-agent-brain/references/version-management.md
    - agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md
    - agent-brain-plugin/skills/configuring-agent-brain/references/installation-guide.md
    - agent-brain-plugin/skills/configuring-agent-brain/references/provider-configuration.md
    - agent-brain-plugin/skills/configuring-agent-brain/references/troubleshooting-guide.md
    - agent-brain-plugin/agents/research-assistant.md
    - agent-brain-plugin/agents/search-assistant.md
    - agent-brain-plugin/agents/setup-assistant.md

key-decisions:
  - "SentenceTransformers documented as reranker provider (not embedding) to match source code"
  - "Fixed stale .claude/doc-serve path references to .agent-brain in server-discovery and integration guides"
  - "Version history updated to include v7.0 through v9.1.0 releases"

patterns-established:
  - "Documentation audit: cross-reference plugin docs with source code enums and CLI commands"

requirements-completed: [PLUGDOC-02, PLUGDOC-03]

duration: 10min
completed: 2026-03-16
---

# Phase 32 Plan 03: Skill Reference Guides and Agent Descriptions Audit Summary

**Audited 16 skill reference guides and 3 agent descriptions to reflect v7-v9 features including file watcher, embedding cache, multi-runtime install, and all 7 providers**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-17T02:04:40Z
- **Completed:** 2026-03-17T02:14:25Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments
- All 16 skill reference guides updated with v7-v9 feature coverage (file watcher, embedding cache, multi-runtime install, folder management, file type presets, content injection, reranking, query cache)
- Both provider-configuration guides now include SentenceTransformers reranker as the 7th provider type
- Both installation guides now document multi-runtime install with all 5 supported runtimes (claude, opencode, gemini, codex, skill-runtime)
- All 3 agent descriptions updated to match actual CLI capabilities and v7-v9 features
- Fixed stale path references (.claude/doc-serve -> .agent-brain) in server-discovery and integration guides

## Task Commits

Each task was committed atomically:

1. **Task 1: Audit skill reference guides (16 files)** - `1f97dfc` (docs)
2. **Task 2: Audit agent description files (3 files)** - `2bf3a60` (docs, bundled with 31-02 summary commit)

## Files Created/Modified

### Skill Reference Guides (14 modified)
- `agent-brain-plugin/skills/using-agent-brain/references/installation-guide.md` - Added multi-runtime install section, key features table
- `agent-brain-plugin/skills/using-agent-brain/references/provider-configuration.md` - Added SentenceTransformers reranker section
- `agent-brain-plugin/skills/using-agent-brain/references/api_reference.md` - Added types, inject, config, install-agent CLI commands
- `agent-brain-plugin/skills/using-agent-brain/references/hybrid-search-guide.md` - Added embedding cache and query cache section
- `agent-brain-plugin/skills/using-agent-brain/references/vector-search-guide.md` - Added embedding cache section
- `agent-brain-plugin/skills/using-agent-brain/references/integration-guide.md` - Fixed stale path, added file watcher and cache integration
- `agent-brain-plugin/skills/using-agent-brain/references/interactive-setup.md` - Added v8/v9 feature setup section
- `agent-brain-plugin/skills/using-agent-brain/references/server-discovery.md` - Fixed stale .claude/agent-brain path to .agent-brain
- `agent-brain-plugin/skills/using-agent-brain/references/troubleshooting-guide.md` - Added file watcher, cache, multi-runtime troubleshooting
- `agent-brain-plugin/skills/using-agent-brain/references/version-management.md` - Added v7-v9 release notes and version history
- `agent-brain-plugin/skills/configuring-agent-brain/references/configuration-guide.md` - Added file watcher, embedding cache, reranking, folder mgmt, types, injection, multi-runtime sections
- `agent-brain-plugin/skills/configuring-agent-brain/references/installation-guide.md` - Added multi-runtime install, key features table
- `agent-brain-plugin/skills/configuring-agent-brain/references/provider-configuration.md` - Added SentenceTransformers reranker section
- `agent-brain-plugin/skills/configuring-agent-brain/references/troubleshooting-guide.md` - Added file watcher, cache, multi-runtime troubleshooting

### Agent Descriptions (3 modified)
- `agent-brain-plugin/agents/research-assistant.md` - Added file type filtering, folder management, file watcher sections
- `agent-brain-plugin/agents/search-assistant.md` - Added graph/multi modes, folder filtering, job queue, cache monitoring
- `agent-brain-plugin/agents/setup-assistant.md` - Added multi-runtime install, all 7 providers, file watcher, cache, reranking

## Decisions Made
- SentenceTransformers is a reranker provider (not embedding/summarization) per source code `RerankerProviderType` enum -- documented accordingly
- Fixed stale `.claude/doc-serve` and `.claude/agent-brain` path references to `.agent-brain` in discovery and integration guides
- BM25 and graph search guides required no v7-v9 updates (they document search algorithms, not features)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed stale runtime path references**
- **Found during:** Task 1 (reference guide audit)
- **Issue:** server-discovery.md and integration-guide.md referenced `.claude/doc-serve/runtime.json` and `.claude/agent-brain/runtime.json` instead of current `.agent-brain/runtime.json`
- **Fix:** Updated path references to `.agent-brain/runtime.json`
- **Files modified:** server-discovery.md, integration-guide.md
- **Committed in:** `1f97dfc`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Bug fix necessary for correctness. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All plugin documentation (commands, skills, agents) is now audited for v7-v9 accuracy
- Phase 33 (Cross-References & Metadata) can proceed with all audited docs

---
*Phase: 32-plugin-documentation*
*Completed: 2026-03-16*
