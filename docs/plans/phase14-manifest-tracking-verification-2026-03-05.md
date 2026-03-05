# Phase 14 Manifest Tracking & Chunk Eviction Verification Plan (2026-03-05)

## Goal
Verify the 7 Phase 14 checkpoints and report pass/fail with concrete evidence.

## Steps
1. Confirm mapping from checkpoints to existing automated tests and runtime behaviors.
2. Run targeted server test modules for manifest tracker, chunk eviction service, indexing manifest behavior, and state path manifests directory creation.
3. Run/validate CLI presentation behavior for job detail eviction summary.
4. If CLI coverage is missing in tests, execute a minimal end-to-end run (server + CLI index/jobs/query) in isolated temp state and data dirs.
5. Collect outcomes and map each of the 7 checkpoints to pass/fail/skip with brief rationale.
