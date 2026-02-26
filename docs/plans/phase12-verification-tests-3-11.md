# Phase 12 Verification Plan (Tests 3-11)

1. Initialize project state in repo root (`agent-brain init`) if missing.
2. Start local Agent Brain server and confirm health/status.
3. Create/use a small sample folder for deterministic indexing checks.
4. Run folder lifecycle checks:
   - `folders list` (CLI)
   - `/index/folders/` (API)
   - restart persistence check
   - `folders remove` (CLI + API)
   - `folders add` alias behavior
5. Run include filter behavior checks:
   - `--include-type` + `--include-patterns` union
   - unknown preset error messaging
6. Run `task before-push` and record outcome (or blockers).

Notes:
- If indexing cannot complete due missing provider credentials/local model access, continue verifying command wiring and error surfaces, and report environment-limited failures explicitly.
