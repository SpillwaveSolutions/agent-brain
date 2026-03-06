---
created: 2026-02-26T00:00:00.000Z
title: Update agent plugin and skills for latest CLI/server features
area: plugin
files:
  - agent-brain-plugin/
  - agent-brain-skill/
---

## Problem

The agent-brain-plugin and agent-brain-skill packages are behind the latest CLI and server features added in Phase 12 (Folder Management & File Type Presets) and the include_types pipeline fix. Users interacting through Claude Code skills and plugin commands cannot access:

1. **Folder management** — `folders list`, `folders add`, `folders remove` CLI commands have no plugin/skill equivalents
2. **File type presets** — `types list`, `types show` CLI commands and `--include-type` flag not exposed in plugin/skill
3. **Job queue commands** — `jobs`, `jobs --watch`, `jobs JOB_ID`, `jobs JOB_ID --cancel` may not be fully reflected
4. **Include types on index** — `index --include-type python` capability not available via plugin slash commands

## Solution

Audit all CLI commands and server API endpoints against plugin commands/skills. For each gap:

1. Add corresponding plugin slash commands (in agent-brain-plugin)
2. Update skill documentation (in agent-brain-skill) to reference new capabilities
3. Ensure plugin commands call the correct CLI or API endpoints
4. Add any missing server API client methods needed by the plugin

### Specific additions needed:
- `/agent-brain-folders` command (list, add, remove subcommands)
- `/agent-brain-types` command (list, show subcommands)
- Update `/agent-brain-index` to support `--include-type` flag
- Verify `/agent-brain-jobs` command completeness
- Update SKILL.md with new capabilities documentation
