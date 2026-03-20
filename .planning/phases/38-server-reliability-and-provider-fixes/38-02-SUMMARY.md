---
phase: 38-server-reliability-and-provider-fixes
plan: 02
subsystem: api
tags: [ollama, retry, embeddings, timeout, reranker]

requires:
  - phase: 38-server-reliability-and-provider-fixes
    provides: state-dir and telemetry startup reliability improvements from plan 01
provides:
  - Retryable Ollama embedding calls with bounded exponential backoff and error classification
  - Safer Ollama defaults (batch_size 10, max_retries 3, optional request_delay_ms)
  - Longer CLI start health-check timeout for first-time sentence-transformers model initialization
affects: [indexing-jobs, provider-reliability, cli-startup]

tech-stack:
  added: []
  patterns:
    - per-request retry loops in provider methods with shared retryability classifier
    - provider-level configurable request pacing via request_delay_ms

key-files:
  created: []
  modified:
    - agent-brain-server/agent_brain_server/providers/embedding/ollama.py
    - agent-brain-server/tests/unit/providers/test_ollama_embedding.py
    - agent-brain-cli/agent_brain_cli/commands/start.py

key-decisions:
  - "Use explicit immediate-fail paths for refused connections and retry only transient transport errors."
  - "Set Ollama default embedding batch size to 10 while preserving explicit user overrides."
  - "Increase CLI startup timeout default to 120 seconds to absorb first-run reranker model download latency."

patterns-established:
  - "Retry classification helper: _is_retryable_error() centralizes transient failure rules for Ollama embedding calls."

requirements-completed: []

duration: 6 min
completed: 2026-03-20
---

# Phase 38 Plan 02: Ollama resilience and startup timeout summary

**Ollama embedding now retries transient pipe/protocol failures with 1s/2s/4s backoff and safer defaults, and CLI startup timeout now allows sentence-transformers first-run initialization.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-20T00:57:04Z
- **Completed:** 2026-03-20T01:03:17Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added robust retry/error-classification logic to Ollama embedding provider for both `_embed_batch` and `embed_text`.
- Added a focused retry test suite (12 cases) covering retryability, backoff sequence, no-retry paths, and delay semantics.
- Increased `agent-brain start` timeout default from 30s to 120s to prevent false startup failure on first model download.

## Task Commits

Each task was committed atomically:

1. **Task 1 (TDD RED): Add failing Ollama retry tests** - `8e84380` (test)
2. **Task 1 (TDD GREEN): Implement Ollama retry/delay/defaults** - `3f55279` (feat)
3. **Task 2: Increase CLI startup timeout default** - `987662d` (fix)

## Files Created/Modified
- `agent-brain-server/tests/unit/providers/test_ollama_embedding.py` - Added `TestOllamaRetryLogic` with retry, backoff, delay, and classification coverage.
- `agent-brain-server/agent_brain_server/providers/embedding/ollama.py` - Added `_is_retryable_error`, retry loops, backoff, and new defaults (`batch_size=10`, `max_retries=3`, `request_delay_ms=0`).
- `agent-brain-cli/agent_brain_cli/commands/start.py` - Raised `--timeout` default and help text to 120 seconds.

## Decisions Made
- Kept connection-refused failures as immediate `OllamaConnectionError` paths and separated them from retryable transport errors.
- Applied identical retry/backoff logic to single-text and batch embedding code paths for behavioral consistency.
- Left reranker provider implementation unchanged and addressed startup behavior in CLI timeout only.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 38-02 deliverables are complete and verification checks pass.
- Ready for `38-03-PLAN.md`.

---
*Phase: 38-server-reliability-and-provider-fixes*
*Completed: 2026-03-20*

## Self-Check: PASSED
