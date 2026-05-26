---
last_validated: 2026-05-25
---

# Changelog

All notable changes to Agent Brain will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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
