---
status: complete
phase: 15-file-watcher-and-background-incremental-updates
source: 15-01-SUMMARY.md, 15-02-SUMMARY.md
started: 2026-03-09T00:00:00Z
updated: 2026-03-09T01:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server. Start fresh with `agent-brain start`. Server boots without errors. `agent-brain status` returns healthy response including a `file_watcher` section.
result: issue
reported: "agent-brain start + status works and shows file_watcher, but startup logs contain error-level entries (telemetry errors), so not without errors literally."
severity: cosmetic

### 2. Folders Add with --watch auto Flag
expected: Running `agent-brain folders add ./src --watch auto` succeeds and the folder is queued for indexing with watch_mode=auto. No CLI errors about unknown flags.
result: pass

### 3. Folders Add with --watch auto --debounce Custom
expected: Running `agent-brain folders add ./src --watch auto --debounce 10` succeeds. The custom debounce value (10 seconds) is sent to the server (visible in the index request body).
result: pass

### 4. Folders List Shows Watch Column
expected: `agent-brain folders list` shows a "Watch" column. Folders with watch_mode=auto show "auto", folders without show "off".
result: issue
reported: "Could not fully validate Watch column values (auto/off) in live output because current run ended with No folders indexed yet."
severity: major

### 5. Jobs Table Shows Source Column
expected: `agent-brain jobs` shows a "Source" column. Manually triggered jobs show "manual". Watcher-triggered jobs would show "auto".
result: pass

### 6. Health Endpoint File Watcher Status
expected: `curl http://localhost:<port>/health/status` (or `agent-brain status`) includes a `file_watcher` section showing `running: true/false` and `watched_folders` count.
result: pass

### 7. Backward Compatibility — Existing Folders Load
expected: If you had folders indexed before Phase 15 (v7.0 era), they still load correctly from the JSONL file. No errors about missing watch_mode or watch_debounce_seconds fields. They default to watch_mode=off.
result: pass

### 8. JobRecord Source Field Defaults to Manual
expected: Any job created via manual `agent-brain index` shows source="manual" in `agent-brain jobs` output. The source field is present in job detail view.
result: pass

### 9. Job Worker Applies Watch Config After Completion
expected: After a job completes for a folder registered with --watch auto, the FileWatcherService starts watching that folder. Visible in /health/status (watched_folders count increases by 1).
result: issue
reported: "watch-auto jobs are failing before completion (Verification failed: No chunks found in vector store), so watched_folders stays 0."
severity: blocker

### 10. Watch Exclusion Patterns
expected: The file watcher excludes .git/, node_modules/, __pycache__/, dist/, build/, .next/, coverage/ directories. Changes inside these directories do not trigger a reindex.
result: pass

### 11. Plugin API Reference Documents Watch
expected: `agent-brain-plugin/skills/using-agent-brain/references/api_reference.md` contains documentation about the --watch flag, watch_mode column in folders list, Source column in jobs, and a File Watcher section.
result: pass

### 12. Plugin Index Command Documents Watch
expected: `agent-brain-plugin/commands/agent-brain-index.md` includes --watch and --debounce parameters with usage examples.
result: pass

## Summary

total: 12
passed: 9
issues: 3
pending: 0
skipped: 0

## Gaps

- truth: "Server boots without error-level log entries"
  status: failed
  reason: "User reported: startup logs contain telemetry errors"
  severity: cosmetic
  test: 1
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "folders list shows Watch column with auto/off values from successful jobs"
  status: failed
  reason: "User reported: Could not validate because no folders indexed (blocked by #9)"
  severity: major
  test: 4
  root_cause: "Blocked by test 9 — jobs fail before completion so no folders appear in list"
  artifacts: []
  missing: []
  debug_session: ""

- truth: "After job completes with watch_mode=auto, FileWatcherService starts watching"
  status: failed
  reason: "User reported: watch-auto jobs failing with Verification failed: No chunks found in vector store"
  severity: blocker
  test: 9
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
