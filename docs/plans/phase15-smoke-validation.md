# Phase 15 Smoke Validation Plan

## Goal
Validate the 12 requested Phase 15 watch-mode smoke checks end-to-end via CLI/API and patch issues if any checks fail.

## Steps
1. Verify cold-start behavior (`list`, `stop`, `start`, `status`) and `/health/status` file_watcher payload.
2. Exercise `folders add` with `--watch auto` and `--watch auto --debounce 10`; verify queue/job metadata.
3. Verify `folders list` includes Watch column values (`auto`/`off`).
4. Verify `jobs` table/detail include `Source` and manual default behavior.
5. Verify watcher integration after job completion (`watched_folders` count increases).
6. Verify exclusion patterns in file watcher implementation and tests.
7. Verify backward compatibility for pre-Phase 15 folder JSONL loading defaults.
8. Verify plugin docs include watch/source/file-watcher references.
9. Patch failures, then rerun focused checks and report pass/fail with evidence.
