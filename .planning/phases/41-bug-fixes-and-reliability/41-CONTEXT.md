# Phase 41: Bug Fixes & Reliability — Context

**Gathered:** 2026-03-23
**Status:** Ready for planning
**Source:** Code investigation + conversation history + STATE.md pending todos

<domain>
## Phase Boundary

Fix 4 known defects that affect daily use. These were identified during prior milestone work and logged as pending todos. Two are already partially or fully addressed in existing code — verification needed.

**What this phase delivers:**
1. BUGFIX-01: Start timeout default already 120s — verify and close, or fix if not working
2. BUGFIX-02: Ensure chroma_db/bm25_index/cache dirs never resolve from CWD when state_dir is available
3. BUGFIX-03: ChromaDB telemetry suppression already implemented — verify effective and close
4. BUGFIX-04: Gemini provider already migrated to google-genai — verify no remnants and close

**What this phase does NOT deliver:**
- No new features
- No CLI commands
- No API changes
</domain>

<decisions>
## Implementation Decisions

### BUGFIX-01: Start Timeout (120s)
- **Status: Likely already fixed.** `start.py:197-200` shows `--timeout` default is already 120.
- Verify the default works end-to-end. If it does, write a test confirming the default and close.
- If there's a code path that ignores the timeout flag, fix it.

### BUGFIX-02: State-Dir Path Resolution
- **Status: Partially fixed.** `main.py:289-299` shows three fallback tiers:
  1. `storage_paths` dict (from `resolve_storage_paths`) — correct
  2. `state_dir` with hardcoded subpaths — correct
  3. `settings.CHROMA_PERSIST_DIR` / `settings.BM25_INDEX_PATH` — **BUG: resolves from CWD**
- The third tier is reached when both `storage_paths` and `state_dir` are None.
- Fix: `main.py:247-251` tries `resolve_state_dir(Path.cwd())` — ensure this always populates `state_dir` so tier 3 is never reached.
- Also check: `GRAPH_INDEX_PATH: str = "./graph_index"` in settings.py:65 — same CWD-relative pattern.
- Also check: `embedding_cache` dir resolution path.
- The `settings.py` defaults (`./chroma_db`, `./bm25_index`, `./graph_index`) should be treated as legacy fallbacks, never used in normal operation.

### BUGFIX-03: ChromaDB Telemetry Suppression
- **Status: Already implemented.** `main.py:165-168` sets `ANONYMIZED_TELEMETRY=False` and adjusts logger levels.
- Also `vector_store.py:101` passes `anonymized_telemetry=False` to ChromaDB client.
- Verify: Run server, check no PostHog errors in output. If clean, write a test and close.
- If errors persist despite suppression, investigate whether the issue is a version-specific ChromaDB bug.

### BUGFIX-04: Gemini Provider Migration
- **Status: Already done.** `gemini.py` imports `google.genai` (not `google-generativeai`). `pyproject.toml` has `google-genai = "^1.0.0"` with no reference to the deprecated package.
- Verify: grep for any remaining `google-generativeai` or `google.generativeai` references. If none, close.

### Validation Approach
- For already-fixed bugs: write regression tests confirming the fix, then close
- For BUGFIX-02: fix the code path, add tests for state-dir resolution
- Run `task before-push` — all 1272+ tests must pass

### Claude's Discretion
- Exact test structure and naming
- Whether to consolidate BUGFIX-03 and BUGFIX-04 tests into existing test files vs new files
- How to test BUGFIX-02 (mock vs integration)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bug Fix Locations
- `agent-brain-cli/agent_brain_cli/commands/start.py` — Start timeout logic (BUGFIX-01), line 197-200 (--timeout default), line 432-436 (wait loop)
- `agent-brain-server/agent_brain_server/api/main.py` — Lifespan with path resolution (BUGFIX-02), lines 247-299; telemetry suppression (BUGFIX-03), lines 165-168
- `agent-brain-server/agent_brain_server/config/settings.py` — CWD-relative defaults: CHROMA_PERSIST_DIR (line 32), BM25_INDEX_PATH (line 33), GRAPH_INDEX_PATH (line 65)
- `agent-brain-server/agent_brain_server/storage_paths.py` — Correct state-dir resolution (full file)
- `agent-brain-server/agent_brain_server/providers/summarization/gemini.py` — Already migrated to google-genai (BUGFIX-04)
- `agent-brain-server/agent_brain_server/storage/vector_store.py:101` — anonymized_telemetry=False (BUGFIX-03)

### Existing Tests
- `agent-brain-server/tests/unit/test_storage_paths.py` — Storage path resolution tests
- `agent-brain-cli/tests/test_cli.py` — CLI command tests including start
</canonical_refs>

<specifics>
## Specific Ideas

- BUGFIX-02 is the only real code change. The others need verification + regression tests.
- For BUGFIX-02, the fix should ensure `state_dir` is always populated in the lifespan. If `resolve_state_dir(Path.cwd())` fails or returns None, use a sensible fallback (e.g., `.agent-brain/` in CWD).
- Consider adding a startup log line that reports resolved storage paths so users can verify the server is using the right directories.
</specifics>

<deferred>
## Deferred Ideas

None — all 4 bugs should be addressed in this phase.
</deferred>

---

*Phase: 41-bug-fixes-and-reliability*
*Context gathered: 2026-03-23 via code investigation*
