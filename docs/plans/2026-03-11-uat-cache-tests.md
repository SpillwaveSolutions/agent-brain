# UAT Cache Tests Plan

## Goal
Run UAT tests 3-13 for the embedding cache feature and report pass/fail with concrete evidence.

## Steps
1. Inspect local project state, config resolution, and available CLI/server entrypoints.
2. Start a local Agent Brain instance in this workspace using an isolated state directory if needed.
3. Execute cache-focused UAT scenarios for restart persistence, status output, clear flows, status/health exposure, help text, and compatibility checks.
4. Capture results, note any blockers caused by local environment or external provider availability, and summarize outcomes by test number.
