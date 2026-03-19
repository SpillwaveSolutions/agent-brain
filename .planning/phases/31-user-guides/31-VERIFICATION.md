---
phase: 31-user-guides
verified: 2026-03-19
status: passed
requirements_verified: [GUIDE-01, GUIDE-02, GUIDE-03, GUIDE-04, GUIDE-05]
---

# Phase 31: User Guides - Verification

## Phase Goal

All user-facing guides accurately reflect v7-v9 features so a new user can follow them from start to finish without encountering stale instructions.

## Success Criteria Verification

### Criterion 1: USER_GUIDE.md reflects folder management, file type presets, content injection, eviction, file watcher, embedding cache, and multi-runtime install features

**Status:** PASSED

**Evidence:** Plan 31-01 added 6 dedicated sections to `docs/USER_GUIDE.md` in commit `6e5dc6a`: Folder Management, File Type Presets, Content Injection, Chunk Eviction, File Watcher, and Embedding Cache. An Index Management Commands table was added with folders, inject, types, and cache commands. Install-agent was added to the Setup Commands table. Command count was updated from 24 to 30. All v7-v9 features (folder management introduced in v7.0, file watcher and embedding cache in v8.0, multi-runtime install in v9.0/v9.1) are now reflected in USER_GUIDE.md.

### Criterion 2: QUICK_START.md installation steps execute successfully on a clean machine without errors or missing steps

**Status:** PASSED

**Evidence:** Plan 31-01 updated `docs/QUICK_START.md` in commit `5ccc896` to add file type preset examples and folder management usage to Step 6, and added a new "Install for Other AI Runtimes" section before the All-in-One Setup section. Stale `.claude/agent-brain/` path references were corrected to `.agent-brain/` throughout (carried forward from Phase 29 and 30 corrections). The installation steps now accurately reflect the current install flow including multi-runtime install-agent commands for claude, opencode, gemini, codex, and skill-runtime targets.

### Criterion 3: PLUGIN_GUIDE.md accurately describes all current plugin slash commands, agents, and skills

**Status:** PASSED

**Evidence:** Plan 31-02 updated `docs/PLUGIN_GUIDE.md` in commit `262564f` to document all 30 commands (up from 24), adding a dedicated Index Management Commands section between Server and Setup commands. New command groups added: Folder Management (folders list/add/remove), Index Commands (inject), Cache Management (cache status/clear), File Type Commands (types list), and Runtime Installation (install-agent). Skills and agents descriptions were updated with v7-v9 features including embedding cache, folder management, multi-runtime, and PostgreSQL error handling.

### Criterion 4: POSTGRESQL_SETUP.md Docker Compose instructions produce a working PostgreSQL backend when followed

**Status:** PASSED

**Evidence:** Plan 31-02 updated `docs/POSTGRESQL_SETUP.md` in commit `3900ccf` to add a complete config.yaml example with storage.backend and storage.postgres.* keys, DATABASE_URL override documentation, and AGENT_BRAIN_STORAGE_BACKEND environment variable. All env vars and Docker template details were verified against source code. The config.yaml approach (rather than env vars alone) is now documented to match the canonical configuration method used in practice.

### Criterion 5: GRAPHRAG_GUIDE.md query examples return results consistent with current graph query behavior

**Status:** PASSED

**Evidence:** Plan 31-02 updated `docs/GRAPHRAG_GUIDE.md` in commit `3071b9d` to add a config.yaml section with graphrag.* keys, an env-to-YAML mapping table, and a ChromaDB backend requirement note documenting that graph and multi query modes require ChromaDB (not PostgreSQL). All query example commands and configuration keys were verified against the source code implementation. The guide now accurately describes current graph query behavior including the backend constraint.

## Requirements Verified

- GUIDE-01: USER_GUIDE.md reflects all v7-v9 features (folder management, file type presets, content injection, eviction, file watcher, embedding cache, multi-runtime install) -- PASSED
- GUIDE-02: QUICK_START.md installation steps accurate for clean machine setup -- PASSED
- GUIDE-03: PLUGIN_GUIDE.md documents all 30 current plugin commands, agents, and skills -- PASSED
- GUIDE-04: POSTGRESQL_SETUP.md Docker Compose instructions accurate with config.yaml example -- PASSED
- GUIDE-05: GRAPHRAG_GUIDE.md query examples consistent with current graph query behavior -- PASSED

## Plans Completed

- 31-01-PLAN.md: Update USER_GUIDE.md and QUICK_START.md — added 6 new feature sections to USER_GUIDE.md, added file type presets/folder management/multi-runtime install to QUICK_START.md
- 31-02-PLAN.md: Update PLUGIN_GUIDE.md, POSTGRESQL_SETUP.md, and GRAPHRAG_GUIDE.md — expanded PLUGIN_GUIDE to 30 commands, added config.yaml examples to both PostgreSQL and GraphRAG guides

## Summary

Phase 31 successfully updated all five user-facing guides to accurately reflect v7-v9 features. A new user following any of these guides from start to finish will find accurate instructions: USER_GUIDE.md has all v7-v9 feature sections, QUICK_START.md has correct install steps, PLUGIN_GUIDE.md covers all 30 commands, POSTGRESQL_SETUP.md has correct config.yaml examples, and GRAPHRAG_GUIDE.md accurately documents graph query behavior with backend requirements.
