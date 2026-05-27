# Plan: Kuzu Graph Store Durability & Self-Heal (Issue #166)

## Context

**Problem:** When the agent-brain server is killed mid-indexing — especially during the `langextract` triplet-extraction phase that writes to the Kuzu graph DB — the on-disk Kuzu catalog at `.agent-brain/data/graph_index/kuzu_db` becomes corrupted. Every subsequent `agent-brain index` job fails immediately inside `_initialize_kuzu_store` with `IndexError: unordered_map::at: key not found` from the pybind11 C++ extension. Only manual recovery (delete `kuzu_db`, restart) works — destroying all previously-extracted triplets, which represent real API spend (`gpt-4o-mini` calls cost real money).

**Why now:** v10.0.4/v10.0.5 closed several Kuzu API-shape bugs (#144, #149, #150, #151) but left the durability gap. The upstream Kuzu issue ([kuzudb#6020](https://github.com/kuzudb/kuzu/issues/6020)) has been open 8+ months with no fix — we can't wait for them.

**Intended outcome:** Agent-brain detects corrupted Kuzu state, self-heals without user intervention, and preserves as many previously-extracted triplets as possible via periodic JSON snapshots. A `kill -9` mid-build becomes a "lose ~60s of work" event instead of a "lose everything" event.

## Scope (User-Confirmed)

1. **Defensive recovery in `_initialize_kuzu_store`** — try/except, rename to `.corrupted-{ts}`, retry on fresh path
2. **Pre-emptive integrity check on server startup** — pay corruption tax once at boot, not on first user job
3. **`agent-brain doctor` check + `--fix`** — graph DB opens cleanly; auto-rename + restore if it doesn't
4. **Periodic JSON snapshots during langextract** — hybrid cadence (every N=25 chunks OR T=60s), kept under `.agent-brain/data/graph_index/snapshots/`, last K=3 retained
5. **Auto-restore from latest snapshot** after corruption recovery (silent + single WARN log line)
6. **CHANGELOG / runbook docs** — explain new behavior and the (now much narrower) sharp edge

**Out of scope** (explicitly deferred): job resume/checkpoint across pipeline phases, ChromaDB/BM25 corruption recovery (those backends don't have this failure mode at present), graceful-shutdown plumbing for `_build_graph` cancellation (separate work — see "Follow-ups").

## Architecture

### Module boundaries

| Concern | Location | New code? |
|---|---|---|
| Defensive Kuzu open + rename-on-fail | `agent-brain-server/agent_brain_server/storage/graph_store.py` | Modify `_initialize_kuzu_store()` |
| Startup integrity check | `agent-brain-server/agent_brain_server/api/main.py` lifespan | New helper call |
| Snapshot writer/reader/rotator | `agent-brain-server/agent_brain_server/storage/graph_snapshot.py` | **New file** |
| Snapshot hook during langextract | `agent-brain-server/agent_brain_server/indexing/graph_index.py` `build_from_documents()` | Add callback inside batch loop |
| Doctor check + `--fix` for graph DB | `agent-brain-cli/agent_brain_cli/diagnostics.py` + `commands/doctor.py` | New check function |
| Tests | `agent-brain-server/tests/storage/test_graph_store_recovery.py` and `test_graph_snapshot.py` | **New files** |

### Reusable existing patterns

- **Self-heal template:** `graph_store.py:230-245` (stale-dir cleanup for #151) — same shape: detect, log loud + actionable, rename (don't delete), retry. Extend with corruption-detection branch.
- **Doctor `--fix` framework:** `agent-brain-cli/agent_brain_cli/commands/doctor.py` already has the safe-idempotent-offline-remediation pattern from v10.0.5. New check plugs into it.
- **Structured user-facing errors:** `RuntimeError` pattern at `graph_store.py:239-245` (names the path, suggests env var) — reuse for snapshot/restore failure modes.
- **Retry with backoff:** `agent-brain-server/agent_brain_server/storage/postgres/connection.py:84-143` — not directly applicable here (Kuzu open is one-shot), but the structured `StorageError` raising style is.

### Snapshot format

JSON file `snapshot-{ISO8601}.json`:

```json
{
  "schema_version": 1,
  "created_at": "2026-05-26T21:05:32Z",
  "kuzu_version": "0.11.3",
  "triplet_count": 1247,
  "source_job_id": "job_170be31f233e",
  "triplets": [
    {"subject": "...", "predicate": "...", "object": "...", "metadata": {...}},
    ...
  ]
}
```

Rotation: keep last 3 by `created_at`, delete older. Atomic write via `tmp + os.replace`.

### Snapshot cadence (hybrid)

Inside `graph_index.build_from_documents()`, between langextract batches:
- Maintain `chunks_since_snapshot` counter and `last_snapshot_ts`
- After each batch: if `chunks_since_snapshot >= 25` OR `now - last_snapshot_ts >= 60s`, take a snapshot of current Kuzu triplets to JSON
- If either threshold is configurable via env (`GRAPH_SNAPSHOT_CHUNKS`, `GRAPH_SNAPSHOT_INTERVAL_SEC`), expose them in `config/settings.py` with sensible defaults

### Recovery flow

```
Server startup or _initialize_kuzu_store called
  ↓
try kuzu.Database(path)
  ↓ raises IndexError / RuntimeError from C++
catch → log WARN with actionable text + path
  ↓
rename kuzu_db → kuzu_db.corrupted-{ts}
rename kuzu_db.wal → kuzu_db.wal.corrupted-{ts} (if exists)
  ↓
retry kuzu.Database(path)  # now fresh
  ↓
look for latest snapshot in snapshots/
  ↓ found?
load triplets, replay into fresh Kuzu DB
log WARN: "Restored N triplets from snapshot {ts} after recovering corrupted kuzu_db"
  ↓ not found?
log INFO: "No snapshot available; starting with empty graph"
  ↓
continue normally
```

If the retry of `kuzu.Database(path)` *also* fails: raise a clear `RuntimeError` with the corrupted-path name and explicit "delete graph_index/ to fully reset" instruction. Don't loop.

## Implementation Steps

> Each step lands as its own commit. Run `task before-push` between commits. The branch must be created before any work begins (see project memory: never work on main).

### Step 0 — Branch setup
- `git checkout -b fix/issue-166-kuzu-resilience`

### Step 1 — Snapshot module
- Create `agent-brain-server/agent_brain_server/storage/graph_snapshot.py` with:
  - `class GraphSnapshotManager` — `__init__(persist_dir)`, `write(triplets, source_job_id)`, `latest()`, `load(path)`, `rotate(keep=3)`
  - `write` uses tmp-file + `os.replace` for atomicity
  - Schema constants and JSON encode/decode helpers
- Unit tests `tests/storage/test_graph_snapshot.py`: write, read-back, rotation (keep=3 of 5), corrupt file ignored gracefully

### Step 2 — Defensive recovery in graph_store
- Modify `_initialize_kuzu_store()` in `agent_brain_server/storage/graph_store.py`:
  - Wrap line 247 `kuzu.Database(...)` in `try / except (IndexError, RuntimeError) as exc`
  - On catch: log WARN with the exact text from the issue, rename `kuzu_db` and `kuzu_db.wal` files (use `Path.rename` to a sibling `.corrupted-{ts}` path; if rename fails, fall back to `shutil.move`)
  - Retry `kuzu.Database(...)`; if THAT raises, re-raise as `RuntimeError` with explicit reset instructions
  - After successful (re-)open, call new `_restore_from_snapshot_if_available()` helper that uses `GraphSnapshotManager` and replays triplets via the new `KuzuPropertyGraphStore` interface
- Tests `tests/storage/test_graph_store_recovery.py`: simulate corrupted DB (write junk bytes to `kuzu_db`), verify rename + fresh open succeeds, verify triplets restored when snapshot present

### Step 3 — Snapshot hook during langextract
- Modify `agent-brain-server/agent_brain_server/indexing/graph_index.py` `build_from_documents()`:
  - Instantiate `GraphSnapshotManager(persist_dir)` once
  - Wrap the existing batch loop with `chunks_since_snapshot` counter and `last_snapshot_ts` timestamp
  - After each batch completion: check thresholds, call `snapshot_mgr.write(...)` + `rotate()` if either crossed
  - Read thresholds from `settings.GRAPH_SNAPSHOT_CHUNKS` (default 25) and `settings.GRAPH_SNAPSHOT_INTERVAL_SEC` (default 60)
- Add the two settings to `agent_brain_server/config/settings.py` with `Field(...)` defaults and env-var binding
- Tests: mock langextract, run `build_from_documents` with 60 chunks, assert ≥2 snapshots written

### Step 4 — Pre-emptive startup check
- In `agent-brain-server/agent_brain_server/api/main.py` lifespan (after lock acquired, before serving):
  - If GraphRAG enabled and `store_type == "kuzu"`: call new `graph_store_manager.preflight_check()` which attempts a read-only open + trivial query, triggering the same corruption-detection-and-recover path as step 2 — but proactively
- Log a clear startup line either way: `"Kuzu graph store preflight: OK"` or `"Kuzu graph store preflight: recovered from corruption (N triplets restored)"`

### Step 5 — Doctor check + `--fix`
- Add to `agent-brain-cli/agent_brain_cli/diagnostics.py` a new check function `check_graph_store_health()`:
  - When GraphRAG enabled, attempt to open `kuzu_db` via the same defensive helper; report OK/WARN/FAIL with `fix:` field
  - `--fix` mode: invoke the rename-and-restore path
- Plug into the existing doctor check registry in `commands/doctor.py`
- Tests: doctor on a fresh project (OK), doctor on a corrupted project (FAIL with fix hint), doctor --fix on corrupted project (FIXED)

### Step 6 — CHANGELOG + runbook
- Add v10.0.6 (or v10.1.0 — defer naming to release skill) CHANGELOG entry under `CHANGELOG.md` describing the fix, the snapshot behavior, the new doctor check, the two new env vars
- Add a short "Graph DB resilience" subsection under `docs/USER_GUIDE.md` (or `docs/DEVELOPERS_GUIDE.md` — whichever has the closest existing content) explaining: snapshots exist, where they live, what `--fix` does

### Step 7 — End-to-end validation
- Run `./scripts/quick_start_guide.sh` to validate full workflow
- Manual repro of issue #166:
  1. Fresh `.agent-brain/`, enable GraphRAG
  2. `agent-brain index <large_folder> --generate-summaries --include-code`
  3. Mid-langextract: `pkill -9 -f agent-brain-serve`
  4. Restart server, re-run `agent-brain index <same_folder>`
  5. Verify: job succeeds, WARN log mentions corruption + snapshot restore, `agent-brain status` shows triplet count near pre-kill value
- Verify `agent-brain doctor` reports OK on the recovered project

### Step 8 — Mandatory validation before push
- `task before-push` — must exit 0 (format, lint, typecheck, tests)
- `task pr-qa-gate` — must exit 0 (full PR gate)
- Only then `git push -u origin fix/issue-166-kuzu-resilience`
- Open PR referencing issue #166; include manual repro evidence in PR body

## Files Modified / Created

| Path | Change |
|---|---|
| `agent-brain-server/agent_brain_server/storage/graph_store.py` | Modify `_initialize_kuzu_store()`; add `preflight_check()` and `_restore_from_snapshot_if_available()` |
| `agent-brain-server/agent_brain_server/storage/graph_snapshot.py` | **NEW** — snapshot writer/reader/rotator |
| `agent-brain-server/agent_brain_server/indexing/graph_index.py` | Add snapshot cadence hook in batch loop |
| `agent-brain-server/agent_brain_server/api/main.py` | Add preflight call in lifespan |
| `agent-brain-server/agent_brain_server/config/settings.py` | Add `GRAPH_SNAPSHOT_CHUNKS`, `GRAPH_SNAPSHOT_INTERVAL_SEC` |
| `agent-brain-server/tests/storage/test_graph_snapshot.py` | **NEW** — unit tests |
| `agent-brain-server/tests/storage/test_graph_store_recovery.py` | **NEW** — corruption recovery tests |
| `agent-brain-cli/agent_brain_cli/diagnostics.py` | Add `check_graph_store_health()` |
| `agent-brain-cli/agent_brain_cli/commands/doctor.py` | Register new check |
| `agent-brain-cli/tests/test_doctor.py` (or existing) | Add cases for graph health + --fix |
| `CHANGELOG.md` | Add v10.0.6 entry |
| `docs/USER_GUIDE.md` (or DEVELOPERS_GUIDE) | Add "Graph DB resilience" section |

## Verification

### Automated
- Unit tests for snapshot module (rotation, atomic write, corrupt-file handling)
- Unit tests for graph_store corruption recovery (synthesize a corrupted file, assert rename + retry succeeds, assert snapshot restore replays triplets)
- Doctor command tests (OK / FAIL / FIXED paths)
- `task before-push` exits 0 with coverage ≥50%
- `task pr-qa-gate` exits 0

### Manual (must-do before merge)
- Run the issue #166 repro on a real machine, confirm self-heal kicks in
- Verify snapshots dir is populated during a long index job and rotation keeps only K=3
- Verify `agent-brain doctor --fix` recovers a deliberately-corrupted Kuzu DB
- Verify the new WARN log line is clear and actionable

### Edge cases to test
- Corrupted DB + no snapshot present → fresh start, no crash, clear INFO log
- Corrupted DB + corrupted snapshot file → rename snapshot, try the next-older, else fresh start
- Snapshot write fails mid-indexing (disk full) → log WARN, continue indexing (don't fail the job)
- Rename of corrupted file fails (file locked) → raise clear RuntimeError with manual-recovery instructions
- Two snapshots with same timestamp (clock collision) → tie-break on filename or use monotonic counter suffix

## Follow-ups (Separate Issues, NOT This PR)

These came up during exploration but are explicitly out of scope:

1. **Graceful drain for `_build_graph`** — currently `asyncio.to_thread(_build_graph)` ignores cancellation tokens. SIGTERM during graph build is still uncatchable mid-batch. File as new issue; needs API design for thread-cancellable extraction.
2. **`task agent-brain:stop` integration** — `agent-brain-server/Taskfile.yml` has no `stop` task. Add one that SIGTERM-then-wait-then-SIGKILL with sensible timeout.
3. **Apply same defensive pattern to ChromaDB/BM25** — both could in principle corrupt under the same conditions; not observed today but worth proactive coverage.
4. **Track upstream [kuzudb/kuzu#6020](https://github.com/kuzudb/kuzu/issues/6020)** — if/when fixed, our defensive code becomes belt-and-suspenders, not load-bearing.

## Risks

- **Snapshot I/O overhead** — JSON-encoding 1000s of triplets every 25 chunks could slow indexing. Mitigation: thresholds are env-configurable; default cadence sized for low overhead; measure during validation and tune if needed.
- **Restored triplets may not match exactly** — replaying triplets into a fresh Kuzu DB may produce slightly different internal IDs. Should not affect query results, but worth verifying with a query-equivalence test.
- **Disk usage from snapshots** — bounded by K=3 rotation. For a 100K-triplet corpus, ~10-30MB each. Acceptable.
- **Concurrent doctor --fix during active indexing** — could race the snapshot writer. Mitigation: doctor --fix should detect running server (via lockfile) and refuse, with clear message.

## Memory / Project Rules Reminders

- Create feature branch first; never work on main
- `task before-push` exits 0 BEFORE every `git push` — no exceptions
- Conventional commits (`fix:`, `feat:`, `test:`, `docs:`)
- After plan approval, also save a copy of this plan to `docs/plans/issue-166-kuzu-resilience.md` (per project CLAUDE.md planning rule)
