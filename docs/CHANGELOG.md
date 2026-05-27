---
last_validated: 2026-05-26
---

# Changelog

All notable changes to Agent Brain will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [10.0.6] - 2026-05-26

### Fixed

- **Kuzu graph store now self-heals from kill-mid-write corruption.** When the server was killed (SIGKILL or even SIGTERM) during the `langextract` triplet phase, the on-disk Kuzu catalog at `.agent-brain/data/graph_index/kuzu_db` could enter a state where `kuzu.Database(path)` raises `IndexError: unordered_map::at: key not found` from the pybind11 C++ constructor — every subsequent `agent-brain index` job then failed instantly inside `_initialize_kuzu_store` with no actionable recovery hint. Manual `rm kuzu_db` worked but destroyed all previously-extracted triplets (real `gpt-4o-mini` API spend). `_initialize_kuzu_store` in `agent_brain_server/storage/graph_store.py` now wraps `kuzu.Database()` in defensive `try/except (IndexError, RuntimeError)`. On catch it logs a loud actionable WARN, quarantines `kuzu_db` (and `kuzu_db.wal`) to `.corrupted-<ts>` sibling files (never deletes — forensic preservation), then retries on the now-empty path. A second failure raises a structured `RuntimeError` with explicit reset instructions. The lifespan in `agent_brain_server/api/main.py` calls a new `preflight_check()` at startup so corruption is detected once at boot rather than on the first user-facing indexing job. Same shape as the existing `#151` stale-directory self-heal pattern. Cross-reference: upstream [kuzudb/kuzu#6020](https://github.com/kuzudb/kuzu/issues/6020) tracks the catalog-load fragility on a different code path. Closes #166.

### Added

- **Triplet snapshots during langextract** (`agent_brain_server/storage/graph_snapshot.py` + hook in `agent_brain_server/indexing/graph_index.py`). `build_from_documents` now writes JSON triplet snapshots to `<graph_index>/snapshots/snapshot-<ISO8601>.json` on a hybrid cadence — whenever either `GRAPH_SNAPSHOT_CHUNKS` chunks (default 25) OR `GRAPH_SNAPSHOT_INTERVAL_SEC` seconds (default 60) have elapsed — plus a final tail snapshot at end-of-build. Rotation keeps the `GRAPH_SNAPSHOT_KEEP` most recent (default 3). Writes are atomic (`tmp + os.fsync + os.replace`). When the corruption-recovery path detects a quarantined Kuzu DB, it walks newest-to-oldest snapshots (skipping any that themselves got corrupted) and replays the triplets into the fresh database — silently restoring previously-extracted work with a single WARN log line. Snapshot write failure is non-fatal (a disk-full `OSError` logs WARN and indexing continues; the snapshot is a safety net, not a critical path). New env-var settings: `GRAPH_SNAPSHOT_CHUNKS`, `GRAPH_SNAPSHOT_INTERVAL_SEC`, `GRAPH_SNAPSHOT_KEEP`.
- **`agent-brain doctor` now checks Kuzu DB health** (`agent_brain_cli/agent_brain_cli/diagnostics.py`). When GraphRAG is enabled with `store_type: kuzu`, the new `graph_store_health` check briefly opens `kuzu_db` in-process and reports OK / FAIL with an actionable fix hint. `agent-brain doctor --fix` extends to recover a corrupted Kuzu DB offline: refuses to run while a `server.lock` exists (avoids racing the live server), quarantines `kuzu_db` + `kuzu_db.wal` to `.corrupted-<ts>` siblings, and replays the newest valid triplet snapshot into a fresh DB. The CLI peeks at `config.yaml` directly for the `graphrag` block since `AgentBrainConfig` doesn't model graphrag (server concern). Closes the remaining graph DB durability gap from `#146`.

### Internal

- Server-side snapshot manager (`GraphSnapshotManager`) is deliberately backend-agnostic — operates on plain `SnapshotTriplet` dataclasses, never imports Kuzu directly. Same module could later snapshot SimplePropertyGraphStore. Loads sort snapshots by mtime (with filename tie-break) rather than filename alone — collision-suffixed names like `snapshot-T-001.json` sort *before* `snapshot-T.json` lexically, the wrong direction for "newest first". Test coverage: 36 new unit tests across `tests/unit/storage/test_graph_snapshot.py` (write/list/load/rotate lifecycle, corruption handling), `tests/unit/storage/test_graph_store_recovery.py` (defensive recovery state machine with a mocked Kuzu), and `tests/unit/test_graph_index_snapshot.py` (hybrid-cadence hook). Five new doctor tests in `agent-brain-cli/tests/test_resolver_and_doctor.py`.

---

## [10.0.5] - 2026-05-26

### Fixed

- **Graph search with Anthropic summarization now works out of the box.** When `graphrag.enabled: true` and `summarization.provider: anthropic`, `LangExtractExtractor` silently produced zero triplets per chunk because Claude model ids (`claude-haiku-4-5-…`, etc.) are not in `langextract`'s provider registry — the per-chunk WARNING that should have surfaced the failure used `logger.warning(..., extra={"error": ...})`, which the default formatter does not render. Three layers of fix in `agent_brain_server/indexing/graph_extractors.py`: (a) when `summarization.provider` is anthropic / claude and no explicit `graphrag.langextract_{provider,model}` override is configured, the extractor auto-routes to `openai/gpt-4o-mini` with a clear INFO log; (b) startup-time validation now calls `langextract.providers.router.resolve(model_id)` and raises a `ConfigurationError` naming the YAML keys to set when the resolved model would be rejected; (c) the per-chunk WARNING now interpolates the underlying error text via `%s` so it shows in any default-formatted log. Also fixed two latent bugs surfaced by the new validation: `_resolve_model_id`'s ollama default (`ollama/llama3.1:8b`) was always rejected by langextract — switched to the bare `llama3.1:8b` form; and `self.model` no longer inherits `summarization.model` when the caller passed an explicit `provider=` (the cross-wiring made `LangExtractExtractor(provider="ollama")` resolve to a Claude model in the wild). `langextract_provider` and `langextract_model` are now documented in `agent-brain-plugin/skills/configuring-agent-brain/SKILL.md` and `docs/GRAPHRAG_GUIDE.md`. Closes #149.
- `agent-brain jobs <job_id>` no longer crashes with `TypeError: unsupported format string passed to dict.__format__` when the server returns a structured `JobProgress` payload (the default since the job-queue rework — `progress` is a dict with `percent_complete`, `files_processed`, `files_total`, `chunks_created`, `current_file`). The CLI assumed a float and used `f"{progress:.1f}%"` unconditionally on `jobs.py:33,34,126,129`. `_format_progress` was rewritten to dispatch on type — extracts `percent_complete` from the structured dict, falls back to a `key=value` pretty-print for unknown dicts, keeps the legacy float path, and coerces unknown types to `str(...)` rather than raising. The detail view (`_create_job_detail_panel`) now centralizes formatting through the same helper so list view and detail view never diverge. New regression suite in `agent-brain-cli/tests/test_jobs_progress.py` pins each input shape, including the exact failing payload from the issue. Closes #150.
- Kuzu graph-store initialization now self-heals when a stale empty `kuzu_db/` directory is left over from a v10.0.2 upgrade. Pre-v10.0.4 created `kuzu_db/` as a directory; v10.0.4's `#144` fix expects either no path or a kuzu single-file database there, so the upgrade path raised `RuntimeError: Database path cannot be a directory: …/kuzu_db` on the first indexing job. `_initialize_kuzu_store` in `agent_brain_server/storage/graph_store.py` now `rmdir()`s an empty stale dir before opening (only succeeds on empty dirs — safe), and raises a clearer `RuntimeError` that names the directory + suggests `GRAPH_INDEX_PATH` if the leftover is non-empty (never silently deletes user data). Two regression tests in `tests/integration/test_kuzu_graph_e2e.py` pin both paths. Closes #151.

### Added

- `agent-brain doctor` gained the `--fix` flag for safe, idempotent, offline remediations: appends `.agent-brain/` to `.gitignore` (creating it if missing) and creates a stub state dir + `config.json` when the project is uninitialized. The doctor report re-runs after fixing so the printed table reflects the new state. Network calls, API keys, and user code are explicitly off-limits — those still require manual action. Closes part of #146.
- `agent-brain doctor` now reports the installed `agent-brain-cli` version as its own check (catches broken installs at the top of the report instead of letting the user discover them later), and explains *which* rule selected the project root (`.agent-brain/` match, git top-level, `.claude/` marker, etc.) on monorepos. When the server is reachable, the server check additionally pulls `/health/status` and surfaces a one-line indexing summary (state + chunk count). When `graphrag.enabled: true`, doctor checks that `langextract` is importable and hints at the `[graphrag]` extra if not. Closes #146.

### Internal

- `resolve_project_root` in `agent_brain_cli/config.py` now has a sibling `resolve_project_root_with_strategy()` that returns `(root, strategy_label)` — the strategy is a stable identifier (`agent_brain_dir`, `git_root`, `pyproject`, etc.) for use by `agent-brain doctor`. The original signature is unchanged and now delegates to the new function.
- Confirmed via codebase audit that issue #147 (auto-suggest doctor on connection failures) was already implemented end-to-end in v10.0.4: all five commands (`status`, `query`, `jobs`, `index`, `reset`) import `doctor_hint_message` from `agent_brain_cli.diagnostics` and print it on `ConnectionError`, and the helper already distinguishes "no runtime.json found" from "server unreachable." Closed with evidence; no code change in this release.

---

## [10.0.4] - 2026-05-26

### Fixed

- **Graph search with Kuzu now works.** The `--mode graph` retrieval path had been silently broken since the `llama-index-graph-stores-kuzu` package bumped to `>=0.9.0`, which renamed the `KuzuGraphStore` constructor parameters and removed the legacy positional signature Agent Brain was passing. Indexing in graph mode raised `TypeError: __init__() got an unexpected keyword argument` and the server fell back to vector-only retrieval without surfacing the failure. The constructor call in `agent_brain_server/storage/graph_store.py` has been migrated to the new keyword-only API (`db_path=`, plus optional `node_table_name`/`rel_table_name`), the optional dependency pin in `agent-brain-server/pyproject.toml` has been raised to `^0.9.0`, and an integration test exercises a full graph-mode index + query cycle so the regression cannot reoccur. Closes #144.
- `exclude_patterns` now uses gitignore-style glob semantics via the `pathspec` library instead of naive substring matching. Previously a pattern like `**/node_modules/**` matched only paths that literally contained the string `**/node_modules/**`, so users had to enumerate every level (`node_modules/**`, `*/node_modules/**`, ...) to get the same effect they get from `.gitignore`. The matcher in `agent_brain_server/indexing/document_loader.py` was rewritten to compile patterns through `pathspec.PathSpec.from_lines("gitwildmatch", ...)`, which gives the same precedence and wildcard rules as Git. `pathspec` is now a required dependency. Existing simple patterns (`*.log`, `__pycache__`) continue to work unchanged. Closes #142.
- BM25 indexing no longer crashes when a folder produces zero indexable chunks (e.g., a directory of only binary files, or a folder where every file is filtered out by `exclude_patterns`). `BM25Retriever.from_defaults([])` raises `ValueError: docstore must contain at least one node` in `llama-index-retrievers-bm25`, which propagated as a 500 from `/index` and aborted the whole queued job. `agent_brain_server/services/indexing_service.py` now short-circuits before constructing the retriever, logs a `WARNING` with the folder path, marks the job `completed` with `indexed_count=0`, and returns. The vector store path was already a no-op in this case, so behavior is now consistent across backends. Closes #143.

### Internal

- Removed a duplicate `resolve_project_root()` definition in `agent_brain_cli/commands/stop.py` that shadowed the shared implementation in `agent_brain_cli.utils.project`. The shadow had drifted: it silently returned `Path.cwd()` when no `.agent-brain/` marker was found, whereas the canonical version walks up the tree and raises a clear error. Behavior of `agent-brain stop` outside an initialized project is now consistent with `start`/`status`/`list`. Closes #131.

## [10.0.3] - 2026-05-26

### Fixed

- Multi-page PDF indexing silently lost data because `chunk_id` was derived from only `(source, idx)`. Every page reset `idx` to 0, so chunks collided and ChromaDB's upsert kept only the last page (a 128-page PDF was indexed as only a handful of chunks, all from later pages). The collisions were masked by a last-occurrence-wins dedupe in `vector_store.py` with only a server-log warning. Fix: `DocumentLoader` now preserves the per-part identifier PyMuPDFReader sets in `metadata["source"]` as `page_label`, and both `chunking.py` and the `CodeChunker` mix `page_label` into the id_seed when present (using `#` as a URL-fragment-style separator so filenames like `foo.pdf_3` cannot collide with `foo.pdf#3_0`). Non-PDF sources without `page_label` keep the legacy `f"{source}_{idx}"` seed, so already-indexed corpora are unaffected. Includes new regression suite `tests/unit/test_chunk_id_uniqueness.py` covering disjoint IDs across pages, legacy-formula backwards compat, and stability across re-indexing. Closes #141.

## [10.0.2] - 2026-05-25

### Fixed

- Release automation now refuses to proceed if `docs/CHANGELOG.md` is missing an entry for the new version. Previously the release agent silently shipped without updating the CHANGELOG, requiring a post-release docs catchup commit each time (see PR #139 for v10.0.1). The new pre-release check (Check #6 in `.claude/agents/release_agent.md`, Check #5 in `.claude/commands/ag-brain-release.md`) computes the target version from the bump type and greps `docs/CHANGELOG.md` for a matching `## [X.Y.Z]` heading. On failure it aborts with a clear instruction to add the section and commit before re-running. Same root cause as #135 (release agent's documented contract diverging from automation) — now resolved structurally. Closes #138.

### Internal

- This v10.0.2 CHANGELOG entry self-demonstrates the new check: the release that ships it is the first release to actually run the check, and it will validate its own existence in `docs/CHANGELOG.md` before proceeding.

## [10.0.1] - 2026-05-25

### Fixed

- `scripts/quick_start_guide.sh` was silently broken since v9.0.0 — line 68 still invoked the legacy `doc-serve` binary (renamed to `agent-brain-serve` in v9.0.0) and the script's exported `DOC_SERVE_URL` env var was no longer read by the modern CLI. The script is cited as a mandatory pre-release gate in `.claude/CLAUDE.md`, so the gate had been effectively bypassed for the entire v9.x line. Replaced the binary call, updated three echo banners from "Doc-Serve" to "Agent Brain", and renamed `DOC_SERVE_URL` to `AGENT_BRAIN_URL`. Closes #134.
- Release automation now bumps `agent-brain-plugin/.claude-plugin/plugin.json` in lockstep with `pyproject.toml` and `__init__.py` files. The release agent's documented contract required the plugin manifest to match (line 119) but its actual step list only enumerated 4 files, requiring a manual catchup commit each release (see `4997007` for v10.0.0). Both `.claude/agents/release_agent.md` and `.claude/commands/ag-brain-release.md` now list 5 files. The v10.0.1 release commit (`fc8f9bb`) is the first to bump `plugin.json` automatically. Closes #135.

### Internal

- Identified `.claude/commands/ag-brain-release.md` as the runtime source of truth for the release slash command — its "Task" section is what the skill follows, not the duplicate file list in the agent definition. PR #137 was needed because PR #136 only updated the agent file.

## [10.0.0] - 2026-05-25

### Breaking

- `cohere` is now an optional extra. Install with `pip install 'agent-brain-rag[cohere]'` to use the Cohere provider. Without the extra, selecting cohere raises a clear `ImportError` with install hint. Closes #122, #125.

### Added

- `agent-brain doctor` CLI command — checks Python version, project init, provider config, required API keys, optional deps (`cohere`/`langextract`), `.gitignore` hygiene, and server reachability. Supports `--json` and exits non-zero on critical failures.
- Connect-time hints — when `status`, `query`, `jobs`, `index`, `reset` hit `ConnectionError`, they now print a context-sensitive tip pointing at `agent-brain doctor` or the missing `runtime.json`.
- Plugin delegation — `ab-setup-check.sh` now calls `agent-brain doctor --json` when the CLI is installed.

### Fixed

- File watcher infinite re-index loop — `.agent-brain/` and `.claude/` added to `AgentBrainWatchFilter`'s ignore_dirs. Closes #123.
- Monorepo project-root resolver — CLI/server walked past nested `.agent-brain/` to the git root in mono-repos, so `status` always queried port 8000. Unified four duplicate project-root resolvers; check for a local state dir before consulting git. Closes #124, #128.
- `graphrag:` YAML section was silently ignored — added `GraphRAGConfig` Pydantic model + `get_graphrag_config()` accessor that merges YAML over env-var defaults. Graph index dir resolved under `{state_dir}/data/graph_index` instead of CWD. Closes #126.
- `langextract` 1.x migration — `extract_relations` removed from the public API; migrated `LangExtractExtractor` to `lx.extract()` with a prompt + few-shot examples, kept a legacy fallback path, stopped swallowing `AttributeError` as "not installed." Closes #129.
- `tiktoken` rejected `<|endoftext|>` literals in indexed text — added `ALLOW_SPECIAL_TOKENS_IN_TEXT` (on by default) and a `_safe_token_count` helper used by every `encode()` call in chunking. Closes #114.

### Performance

- Prune excluded dirs during traversal instead of after walking them — significantly faster indexing on large trees with deep ignore patterns. Closes #127.

### Internal

- Test-isolation fix — `isolate_provider_settings` autouse fixture now honors `AGENT_BRAIN_CONFIG` env-var overrides while still blocking home/XDG/walk-up YAML lookups. Unblocked CI on the pgvector contract/integration/load test suites that had been erroring with `column cannot have more than 2000 dimensions for hnsw index`.
- CI — `provider-e2e.yml` workflow now installs the `[cohere]` extra so the cohere matrix step works after the cohere-is-optional change.

---

## [9.6.0] - 2026-04-03

### Added

- Repo-owned runtime parity harness workspaces under `e2e_workdir/`
- Shared shell helpers for E2E workspace lifecycle, reporting, and runtime install verification
- Structured runtime parity failure payloads with remediation guidance
- OpenCode global scope mutation regression coverage

### Changed

- Runtime parity plumbing now uses runtime-specific `<runtime>-runtime/` directories with `cleanup/` and `logs/`
- E2E runtime documentation now describes the verification contract: structure check, install JSON validation, then dry JSON probe

### Fixed

- Prevented runtime parity installs from silently targeting forbidden global runtime paths
- Fixed workspace cleanup so only disposable runtime `project/` trees are removed on success

---

## [3.0.0] - 2026-02-03

### Added

**Server-Side Job Queue:**
- JobQueueStore with JSONL persistence and file locking
- JobWorker background processor with timeout handling
- JobQueueService with deduplication and backpressure
- New endpoints: GET /index/jobs/, GET /index/jobs/{id}, DELETE /index/jobs/{id}

**CLI Jobs Command:**
- `agent-brain jobs` - List all jobs in queue
- `agent-brain jobs --watch` - Watch queue with live Rich table updates
- `agent-brain jobs JOB_ID` - Show detailed job information
- `agent-brain jobs JOB_ID --cancel` - Cancel a pending or running job

**Runtime Autodiscovery:**
- CLI config module reads runtime.json for automatic server URL discovery
- Foreground mode now writes runtime.json before exec
- Config resolution order: AGENT_BRAIN_URL > runtime.json > config.yaml > default:8000

**Integration Testing:**
- Local integration check script: `scripts/local_integration_check.sh`
- Validates runtime.json creation, job completion, and query functionality
- Added `task local-integration` to Taskfile

### Changed

**Breaking API Changes:**
- POST /index now returns 202 Accepted with job_id (was blocking)
- POST /index/add now returns 202 Accepted with job_id
- Response includes queue_position, queue_length, dedupe_hit

**Version Bump:**
- Major version increment from 2.0.0 to 3.0.0 due to API contract change

### Fixed

- BM25 top_k capping for small corpus
- Runtime.json race condition in foreground mode
- Jobs endpoint trailing slash consistency
- locking.py no longer incorrectly deletes runtime.json

### Removed

- `--daemon` flag (server backgrounds by default)

### Runtime.json Expectations

Both foreground and background modes write runtime.json before the server starts:

```json
{
  "base_url": "http://127.0.0.1:49321",
  "port": 49321,
  "bind_host": "127.0.0.1",
  "pid": 12345,
  "started_at": "2026-02-03T10:00:00Z",
  "foreground": false
}
```

Location: `.claude/agent-brain/runtime.json`

### CLI Resolution Order

The CLI resolves server URL in this priority:
1. `AGENT_BRAIN_URL` environment variable
2. `.claude/agent-brain/runtime.json` (searches cwd upward)
3. `config.yaml` (if contains URL)
4. Default: `http://127.0.0.1:8000`

### Migration Notes

**For API Clients:**

If your code waits for indexing completion synchronously, update to poll the job status:

```python
# Before (v2.x)
response = requests.post(f"{url}/index", json={"folder_path": "/docs"})
# Blocking - returns when done

# After (v3.x)
response = requests.post(f"{url}/index", json={"folder_path": "/docs"})
job_id = response.json()["job_id"]

# Poll for completion
while True:
    status = requests.get(f"{url}/index/jobs/{job_id}").json()
    if status["status"] in ["done", "failed", "cancelled"]:
        break
    time.sleep(2)
```

**For CLI Users:**

No changes required. The `agent-brain index` command works as before but now returns immediately with a job ID. Use `agent-brain jobs --watch` to monitor progress.

---

## [2.0.0] - 2026-01-15

### Added

- GraphRAG integration with knowledge graph search
- Pluggable provider system (OpenAI, Ollama, Cohere, Anthropic, Gemini, Grok)
- Multi-instance support with per-project servers
- AST-aware code chunking for 10+ languages

### Changed

- Renamed from doc-serve to agent-brain
- Default embedding model changed to text-embedding-3-large

### Fixed

- BM25 index persistence across restarts
- Memory leak in large document indexing

---

## [1.2.0] - 2026-01-01

### Added

- Hybrid search mode combining BM25 and vector search
- Alpha parameter for tuning hybrid balance
- Code summarization with LLM

### Changed

- Improved chunk overlap handling
- Better error messages for missing API keys

---

## [1.1.0] - 2025-12-15

### Added

- BM25 keyword search
- Source type filtering (doc/code)
- Language filtering for code queries

### Fixed

- Unicode handling in document parsing
- Path normalization on Windows

---

## [1.0.0] - 2025-12-01

### Added

- Initial release
- Vector-based semantic search
- Document indexing with ChromaDB
- CLI tool with query and index commands
- FastAPI REST API
- Claude Code plugin integration
