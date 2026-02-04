# Changelog

All notable changes to Agent Brain will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
