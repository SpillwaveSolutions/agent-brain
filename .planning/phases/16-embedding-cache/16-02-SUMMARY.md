---
phase: 16-embedding-cache
plan: 02
subsystem: cli
tags: [click, rich, cache, embedding-cache, api-client, cli-commands]

# Dependency graph
requires:
  - phase: 16-01
    provides: "EmbeddingCacheService + GET /index/cache/status + DELETE /index/cache API endpoints"
provides:
  - "agent-brain cache status: Rich table showing entry_count, hit_rate, hits, misses, mem_entries, size"
  - "agent-brain cache clear: confirmation prompt with entry count; --yes/-y to skip"
  - "DocServeClient.cache_status() and DocServeClient.clear_cache() API client methods"
  - "agent-brain status embedding_cache summary line: N entries, X% hit rate (H hits, M misses)"
  - "embedding_cache field in status --json output (null for fresh installs)"
  - "12 new CLI tests in test_cache_command.py covering all cache command paths"
affects:
  - "17-query-cache: CLI patterns for cache commands established here"

# Tech tracking
tech-stack:
  added: []  # No new dependencies; Click + Rich already in use
  patterns:
    - "cache_group() Click group pattern: subcommands as @cache_group.command() decorators"
    - "Confirmation pattern for destructive ops: get count first, then Confirm.ask() with count in message"
    - "embedding_cache: dict | None on IndexingStatus dataclass — None = fresh install (omit from display)"

key-files:
  created:
    - "agent-brain-cli/agent_brain_cli/commands/cache.py"
    - "agent-brain-cli/tests/test_cache_command.py"
  modified:
    - "agent-brain-cli/agent_brain_cli/client/api_client.py"
    - "agent-brain-cli/agent_brain_cli/commands/__init__.py"
    - "agent-brain-cli/agent_brain_cli/cli.py"
    - "agent-brain-cli/agent_brain_cli/commands/status.py"
    - "agent-brain-cli/tests/test_cli.py"

key-decisions:
  - "embedding_cache field on IndexingStatus dataclass defaults to None — existing code unaffected, status.py skips section when None"
  - "cache status only fetches count in cache clear confirmation; no pre-fetch in --yes path (avoids extra API call)"
  - "cache status --json outputs raw API dict directly (no reshaping) — matches server response 1:1"

patterns-established:
  - "Subcommand pattern: use @cache_group.command('subname') not separate @click.command + group.add_command"
  - "Connection-safe confirmation: fetch count inside try/except so confirmation still shows even if count fetch fails (shows 0)"

requirements-completed:
  - ECACHE-03
  - ECACHE-05

# Metrics
duration: 4min
completed: 2026-03-10
---

# Phase 16 Plan 02: CLI Cache Commands Summary

**`agent-brain cache` command group (status + clear) wired to /index/cache API, plus embedding cache metrics in `agent-brain status`, with 12 tests and `task before-push` passing at 155/155 CLI tests**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-10T16:47:28Z
- **Completed:** 2026-03-10T16:51:42Z
- **Tasks:** 2
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments

- Created `cache.py` command group: `cache status` (Rich table + `--json`) and `cache clear` (confirmation prompt with count + `--yes` bypass) wired to the Plan 01 API endpoints (ECACHE-05)
- Added `DocServeClient.cache_status()` (GET /index/cache/status) and `DocServeClient.clear_cache()` (DELETE /index/cache) to api_client.py
- Added `embedding_cache: dict | None` field to `IndexingStatus` dataclass; `agent-brain status` shows summary line when non-null; `--json` includes the field (ECACHE-03)
- 12 new tests in `test_cache_command.py` covering all help, status, and clear paths; `task before-push` exits 0 (893 server + 155 CLI tests pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: API client methods + cache CLI commands** - `85615e6` (feat)
2. **Task 2: Status command integration + health endpoint + tests** - `01e62ee` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `agent-brain-cli/agent_brain_cli/commands/cache.py` - `cache_group` with `cache status` and `cache clear` subcommands (112 lines, 90% coverage)
- `agent-brain-cli/tests/test_cache_command.py` - 12 tests for all cache command paths
- `agent-brain-cli/agent_brain_cli/client/api_client.py` - `cache_status()`, `clear_cache()` methods; `embedding_cache` on `IndexingStatus`
- `agent-brain-cli/agent_brain_cli/commands/__init__.py` - Export `cache_group`
- `agent-brain-cli/agent_brain_cli/cli.py` - Register `cache_group`; add Cache Commands section to help text
- `agent-brain-cli/agent_brain_cli/commands/status.py` - Show `embedding_cache` line in table and JSON output
- `agent-brain-cli/tests/test_cli.py` - Fixed mock to set `embedding_cache=None` (JSON serialization fix)

## Decisions Made

- **`embedding_cache: dict | None` on `IndexingStatus`** with `None` default: all existing code unaffected; `status.py` silently skips the section for fresh installs where the server returns no `embedding_cache` key.
- **No pre-fetch in `--yes` path**: `cache clear --yes` calls `clear_cache()` directly, skipping the count lookup. Only the interactive (non-`--yes`) path fetches status first for the prompt message.
- **Connection-safe count fetch**: In `cache clear` without `--yes`, count fetch is wrapped in try/except — confirmation still shows even if the first fetch fails (shows 0). This avoids a confusing error before the real destructive operation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MagicMock JSON serialization error in existing test_cli.py**
- **Found during:** Task 2 verification (`task before-push`)
- **Issue:** `test_status_json_output` in `tests/test_cli.py` left `mock_status.embedding_cache` unset. After adding `embedding_cache` to the JSON output in `status.py`, `json.dumps()` tried to serialize a `MagicMock` object, raising `TypeError: Object of type MagicMock is not JSON serializable`. Exit code 1.
- **Fix:** Added `mock_status.embedding_cache = None` to the test setup; also added assertion `assert output["indexing"]["embedding_cache"] is None`.
- **Files modified:** `agent-brain-cli/tests/test_cli.py`
- **Verification:** `task before-push` passes; all 155 CLI tests pass.
- **Committed in:** `01e62ee` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug in existing test)
**Impact on plan:** Required for correctness. No scope creep. Plan objectives fully met.

## Issues Encountered

None — the circular import pattern from Plan 01 did not recur (CLI only calls API endpoints, no server-side Python imports involved). The only issue was the existing test mock incompatibility caught by `task before-push`.

## User Setup Required

None - no external service configuration required. The `cache` commands connect to the running server using the same URL as all other CLI commands.

## Next Phase Readiness

- Phase 16 (Embedding Cache) is now fully complete: server-side service (Plan 01) + CLI commands (Plan 02)
- Phase 17 (Query Cache) can proceed — `index_generation` counter infrastructure is ready
- All `task before-push` checks pass; CLI has 155 tests, server has 893 tests

## Self-Check: PASSED

- cache.py: FOUND
- test_cache_command.py: FOUND
- 16-02-SUMMARY.md: FOUND
- Commit 85615e6 (Task 1): FOUND
- Commit 01e62ee (Task 2): FOUND

---
*Phase: 16-embedding-cache*
*Completed: 2026-03-10*
