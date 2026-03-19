---
phase: 29-cli-api-documentation
verified: 2026-03-19
status: passed
requirements_verified: [CLIDOC-01, CLIDOC-02, CLIDOC-03, CLIDOC-04]
---

# Phase 29: CLI & API Documentation - Verification

## Phase Goal

All CLI command documentation and API endpoint documentation accurately reflect current software behavior.

## Success Criteria Verification

### Criterion 1: Every CLI subcommand documented in docs matches the output of `agent-brain --help` and subcommand `--help` flags

**Status:** PASSED

**Evidence:** Plan 29-01 captured `--help` output for all 16 CLI subcommands as source of truth. The audit found that `.claude/CLAUDE.md` was entirely missing a CLI Commands section — this was added in commit `908aaad`, covering Project Commands (init, start, stop, list), Server Commands (status, query, index, inject, reset), Job Queue Commands (jobs, jobs --watch, jobs JOB_ID, jobs JOB_ID --cancel), Cache Commands (cache status/clear), Folder Commands (folders list/add/remove), File Type Commands (types list), Configuration Commands (config show/path), Runtime Installation Commands (install-agent), and Other Commands (uninstall). All 16 subcommands are now documented across CLAUDE.md, .claude/CLAUDE.md, and docs/USER_GUIDE.md with syntax matching actual `--help` output.

### Criterion 2: All 5 runtime installation commands (install-agent) are documented with correct syntax and options

**Status:** PASSED

**Evidence:** Plan 29-01 verified and Plan 32-01 further confirmed that `install-agent` documentation covers all 5 supported runtimes: `--agent claude`, `--agent opencode`, `--agent gemini`, `--agent codex`, and `--agent skill-runtime --dir <path>`. Additional flags `--dry-run` and `--global` are documented with correct syntax. The `.claude/CLAUDE.md` CLI Commands section added in commit `908aaad` includes a dedicated "Runtime Installation Commands" table listing all 5 runtime options with descriptions.

### Criterion 3: Every API endpoint documented in API reference matches the OpenAPI spec produced by the running server

**Status:** PASSED

**Evidence:** Plan 29-02 performed a full endpoint-by-endpoint comparison of `docs/API_REFERENCE.md` against the FastAPI router source and Pydantic models. Commit `775d259` added 6 previously undocumented endpoints (GET /health/providers, GET /health/postgres, GET /index/folders, DELETE /index/folders, GET /index/cache, DELETE /index/cache), bringing total coverage to all 16 endpoints. The `similarity_threshold` default was corrected from 0.7 to 0.3 to match the Pydantic model. Missing query parameters, request body fields (11 missing from IndexRequest), response fields (rerank_score, original_rank), and error codes (409, 429, 503) were all added. TypeScript interfaces were added for ProvidersStatus, FolderListResponse, FolderDeleteResponse, JobSummary, and JobDetailResponse.

### Criterion 4: Job queue commands (`jobs`, `jobs --watch`, `jobs JOB_ID`, `jobs JOB_ID --cancel`) are documented accurately

**Status:** PASSED

**Evidence:** Plan 29-01 added the complete Job Queue Commands table to `.claude/CLAUDE.md` (commit `908aaad`) and plan 29-02 fixed the job list query parameters in API_REFERENCE.md (limit 1-100, no status filter, corrected from earlier inaccurate docs). All four job queue command variants are documented with accurate syntax in CLAUDE.md, .claude/CLAUDE.md, and docs/USER_GUIDE.md.

## Requirements Verified

- CLIDOC-01: All 16 CLI subcommands documented across CLAUDE.md, .claude/CLAUDE.md, USER_GUIDE.md -- PASSED
- CLIDOC-02: All 5 runtime installation commands documented with correct syntax and options -- PASSED
- CLIDOC-03: All 16 API endpoints documented in API_REFERENCE.md matching server source code -- PASSED
- CLIDOC-04: Job queue commands documented with accurate syntax -- PASSED

## Plans Completed

- 29-01-PLAN.md: CLI command documentation audit — captured all 16 --help outputs, added missing CLI Commands section to .claude/CLAUDE.md, fixed 6 stale path references and 9 missing commands in USER_GUIDE.md
- 29-02-PLAN.md: API endpoint documentation audit — added 6 missing endpoints, corrected 14+ field/parameter discrepancies, aligned TypeScript interfaces with Pydantic models

## Summary

Phase 29 successfully audited and corrected all CLI command and API endpoint documentation. All 16 CLI subcommands are now accurately documented in three files (CLAUDE.md, .claude/CLAUDE.md, docs/USER_GUIDE.md) and all 16 API endpoints are documented in docs/API_REFERENCE.md, with schemas matching the FastAPI router source and Pydantic models.
