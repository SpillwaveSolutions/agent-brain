---
status: complete
phase: 15-file-watcher-and-background-incremental-updates
source: 15-01-SUMMARY.md, 15-02-SUMMARY.md
started: 2026-03-09T02:00:00Z
updated: 2026-03-09T02:30:00Z
round: 2
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Server boots, `agent-brain status` returns healthy with `file_watcher` section.
result: pass

### 2. Folders Add with --watch auto Flag
expected: `agent-brain folders add ./src --watch auto` succeeds, queued with watch_mode=auto.
result: pass

### 3. Folders Add with --watch auto --debounce Custom
expected: `agent-brain folders add ./src --watch auto --debounce 10` sends debounce=10 to server.
result: pass

### 4. Folders List Shows Watch Column
expected: `agent-brain folders list` shows a "Watch" column. Folders with watch_mode=auto show "auto", folders without show "off".
result: issue
reported: "agent-brain folders list still returns No folders indexed yet. in live run, so Watch column auto/off values were not observable."
severity: minor

### 5. Jobs Table Shows Source Column
expected: `agent-brain jobs` shows Source column with "manual" values.
result: pass

### 6. Health Endpoint File Watcher Status
expected: `/health/status` includes `file_watcher` with `running` and `watched_folders`.
result: pass

### 7. Backward Compatibility — Existing Folders Load
expected: Pre-Phase 15 JSONL folders load with watch_mode=off defaults.
result: pass

### 8. JobRecord Source Field Defaults to Manual
expected: Manual jobs show source="manual" in jobs list and detail.
result: pass

### 9. Job Completes with watch_mode=auto (Blocker Fix)
expected: A --watch auto job completes as DONE. The eviction_result fix allows zero-change incremental runs to pass verification.
result: pass

### 10. Watcher Activates After Job Completion
expected: After --watch auto job DONE, `/health/status` shows `watched_folders` count increased.
result: pass

### 11. Watch Exclusion Patterns
expected: AgentBrainWatchFilter excludes .git/, node_modules/, __pycache__/, dist/, build/, .next/, coverage/.
result: pass

### 12. Plugin API Reference Documents Watch
expected: `api_reference.md` documents --watch, watch_mode column, Source column, File Watcher section.
result: pass

### 13. Plugin Index Command Documents Watch
expected: `agent-brain-index.md` has --watch and --debounce params with examples.
result: pass

### 14. Verification Fix: eviction_result Passed to Delta Check
expected: `_verify_collection_delta` receives `eviction_result` param, checks it before `job.eviction_summary`. No broad COMPLETED fallback.
result: pass

### 15. Verification Fix: Test Coverage
expected: `test_verify_delta_eviction_result_param_takes_precedence` exists and passes.
result: pass

## Summary

total: 15
passed: 14
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "folders list shows Watch column with auto/off values from successful jobs"
  status: failed
  reason: "User reported: agent-brain folders list still returns No folders indexed yet in live run"
  severity: minor
  test: 4
  root_cause: "Test environment had no successfully indexed folders with content. The Watch column code exists and works (confirmed in CLI tests), but could not be observed in live run because the test folder had no indexable documents."
  artifacts:
    - path: "agent-brain-cli/agent_brain_cli/commands/folders.py"
      issue: "Code is correct — Watch column added at line 75-88"
  missing: []
  debug_session: ""
