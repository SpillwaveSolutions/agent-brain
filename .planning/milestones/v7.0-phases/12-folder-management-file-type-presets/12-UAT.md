---
status: complete
phase: 12-folder-management-file-type-presets
source: [12-01-SUMMARY.md, 12-02-SUMMARY.md, 12-03-SUMMARY.md]
started: 2026-02-25T12:00:00Z
updated: 2026-02-25T18:00:00Z
---

## Current Test

[testing complete — all gaps resolved 2026-02-25]

## Tests

### 1. List File Type Presets
expected: Run `agent-brain types list` — shows table with preset names and their glob extensions
result: pass

### 2. Index with File Type Presets
expected: Run `agent-brain index /path --include-type python,docs` — queues indexing job with preset filtering
result: issue
reported: "accepted the command/options, but it did not queue a job because the CLI could not connect to the local server (http://127.0.0.1:8000 → Connection refused). No job ID was shown."
severity: minor
note: Expected behavior when server not running. CLI correctly accepted --include-type flag. Once server was started on 8123, indexing worked.

### 3. List Indexed Folders via CLI
expected: After indexing, `agent-brain folders list` shows Rich table with Folder Path, Chunks, Last Indexed
result: pass

### 4. List Indexed Folders via API
expected: GET /index/folders/ returns JSON array with folder metadata
result: issue
reported: "API returns an object wrapper, not a raw array: {\"folders\":[...],\"total\":1} from GET /index/folders/"
severity: minor

### 5. Folders Persist Across Server Restart
expected: Stop and restart server, folders list still shows previously indexed folders
result: pass

### 6. Remove Folder via CLI
expected: `agent-brain folders remove /path` prompts confirmation, deletes chunks, shows count
result: pass

### 7. Remove Folder via API
expected: DELETE /index/folders/ removes chunks, returns 404 if not found, 409 if active job
result: pass
note: Success and 404 cases verified. 409 case not reproduced (job completed too fast to catch window).

### 8. Add Folder via CLI
expected: `agent-brain folders add /path` works as alias for index, queues job
result: pass

### 9. Include-Type Combined with Include Pattern
expected: `--include-type python --include-patterns "*.toml"` indexes union of both pattern sets
result: issue
reported: "--include-type python --include-patterns '*.toml' queued but job failed with No files found; expected union behavior did not occur"
severity: major

### 10. Unknown Preset Error
expected: `--include-type bogus` returns clear error listing valid preset names
result: issue
reported: "--include-type bogus did not return a clear error; it queued a job and completed successfully, so invalid preset was effectively ignored"
severity: major

### 11. Unit Tests Pass
expected: `task before-push` passes — all server and CLI tests pass
result: issue
reported: "CLI side failed: 1 failed, 120 passed. Failure was test_config.py:142 because get_server_url() returned http://127.0.0.1:8123 (from local runtime state) instead of expected default http://127.0.0.1:8000"
severity: minor

## Summary

total: 11
passed: 11
issues: 0
pending: 0
skipped: 0

## Gaps (all resolved)

- truth: "include_types combined with include_patterns produces union of both pattern sets"
  status: resolved
  reason: "User reported: --include-type python --include-patterns '*.toml' queued but job failed with No files found; expected union behavior did not occur"
  severity: major
  test: 9
  root_cause: |
    Three separate defects combine to cause this failure:

    1. JobRecord model is missing the include_types field.
       File: agent-brain-server/agent_brain_server/models/job.py (lines 55-70)
       The JobRecord Pydantic model stores include_patterns and exclude_patterns but has
       no include_types field. When job_service.py creates a JobRecord from the IndexRequest
       (lines 167-182 of job_service.py), include_types is silently dropped — Pydantic
       ignores unknown fields on construction.

    2. job_worker.py does not pass include_types when rebuilding IndexRequest from JobRecord.
       File: agent-brain-server/agent_brain_server/job_queue/job_worker.py (lines 211-221)
       The worker reconstructs an IndexRequest from JobRecord fields before calling
       _run_indexing_pipeline(). Even if JobRecord had the field, include_types is not
       included in this reconstruction. The resulting IndexRequest always has include_types=None.

    3. effective_include_patterns is computed but never passed to DocumentLoader.
       File: agent-brain-server/agent_brain_server/services/indexing_service.py (lines 267-288)
       The code resolves include_types into effective_include_patterns (lines 268-283) and
       logs the resolved patterns, but then calls document_loader.load_files() (line 285)
       with only (abs_folder_path, recursive, include_code). The effective_include_patterns
       variable is computed and immediately discarded. DocumentLoader.load_files() has no
       parameter for include_patterns, so the filtering never reaches the file scanner.

    Root: The include_types filtering pipeline was partially implemented (preset resolution
    in indexing_service.py exists and is correct) but the plumbing was never completed:
    JobRecord lacks the field, the worker drops it, and DocumentLoader cannot accept
    include_patterns as input.
  artifacts:
    - agent-brain-server/agent_brain_server/models/job.py
    - agent-brain-server/agent_brain_server/job_queue/job_service.py
    - agent-brain-server/agent_brain_server/job_queue/job_worker.py
    - agent-brain-server/agent_brain_server/services/indexing_service.py
    - agent-brain-server/agent_brain_server/indexing/document_loader.py
  missing:
    - JobRecord.include_types field (list[str] | None, default None)
    - job_service.py enqueue_job must store include_types in JobRecord
    - job_worker.py must pass include_types when reconstructing IndexRequest
    - DocumentLoader.load_files() must accept include_patterns parameter and apply glob
      filtering when building the effective extension set (or pass patterns to
      SimpleDirectoryReader via required_exts translation)
    - indexing_service._run_indexing_pipeline() must pass effective_include_patterns
      to DocumentLoader instead of discarding them
  debug_session: ""

- truth: "Unknown preset names raise clear error with list of valid presets"
  status: resolved
  reason: "User reported: --include-type bogus did not return a clear error; it queued a job and completed successfully, so invalid preset was effectively ignored"
  severity: major
  test: 10
  root_cause: |
    The include_types field is silently dropped when the IndexRequest is stored as a
    JobRecord (see Test 9 root cause — JobRecord has no include_types field).

    Because include_types never reaches the job worker or indexing service with a real
    value, resolve_file_types() is never called during job execution. The ValueError
    that resolve_file_types() raises for unknown presets (file_type_presets.py lines 87-91)
    is therefore never triggered.

    The API endpoint (index.py) and the job_service.enqueue_job() do not call
    resolve_file_types() at enqueue time either — validation is deferred entirely to
    indexing_service._run_indexing_pipeline(). Since include_types is dropped before
    reaching the pipeline, the bogus preset name is never validated, and the job runs
    as if no type filter was specified.

    The fix requires two changes:
    (a) Validate include_types at enqueue time in the API router (index.py) before
        creating the job, so unknown presets return an immediate HTTP 400 error.
    (b) Fix the JobRecord / job_worker plumbing described in Test 9 so that valid
        presets actually reach the document loading step.
  artifacts:
    - agent-brain-server/agent_brain_server/models/job.py
    - agent-brain-server/agent_brain_server/job_queue/job_service.py
    - agent-brain-server/agent_brain_server/job_queue/job_worker.py
    - agent-brain-server/agent_brain_server/services/file_type_presets.py
    - agent-brain-server/agent_brain_server/services/indexing_service.py
    - agent-brain-server/agent_brain_server/api/routers/index.py
  missing:
    - Early validation of include_types in index.py API router: call resolve_file_types()
      before enqueueing and raise HTTP 400 if ValueError is raised, so clients get an
      immediate error rather than a silently-completed job
    - All the same plumbing fixes needed for Test 9 (JobRecord field, worker pass-through,
      DocumentLoader filtering)
  debug_session: ""

- truth: "GET /index/folders/ returns JSON array with folder metadata"
  status: resolved
  reason: "User reported: API returns object wrapper {folders:[...],total:1} not raw array"
  severity: minor
  test: 4
  root_cause: |
    Design choice, not a code bug. The implementation intentionally returns a
    FolderListResponse wrapper object with two fields:
      { "folders": [...], "total": 1 }

    This is defined in:
      agent-brain-server/agent_brain_server/models/folders.py (FolderListResponse, lines 36-74)
      agent-brain-server/agent_brain_server/api/routers/folders.py (list_folders, line 29)

    The original FOLD-02 requirement text says "returning JSON array with folder metadata"
    which is ambiguous — it may have meant "returning JSON containing an array" rather than
    "returning a bare JSON array". The FolderListResponse design is consistent with all
    other list endpoints in the codebase (e.g., JobListResponse), follows REST best
    practices (envelope allows adding pagination metadata without breaking clients), and
    was explicitly planned in 12-01-PLAN.md and 12-02-PLAN.md.

    Resolution: The requirement wording is imprecise. The implementation is correct.
    FOLD-02 requirement text should be updated to read "returning JSON object with a
    folders array and total count" to match the implemented design. No code change needed.
  artifacts:
    - agent-brain-server/agent_brain_server/models/folders.py
    - agent-brain-server/agent_brain_server/api/routers/folders.py
    - .planning/REQUIREMENTS.md (FOLD-02 wording)
  missing:
    - REQUIREMENTS.md FOLD-02 should be updated to say "returning JSON object with folders
      array and total count field" instead of "returning JSON array with folder metadata"
  debug_session: ""

- truth: "task before-push passes with all changes"
  status: resolved
  reason: "User reported: CLI test_config.py:142 failed because get_server_url() returned http://127.0.0.1:8123 from local runtime state instead of expected default http://127.0.0.1:8000"
  severity: minor
  test: 11
  root_cause: |
    Test environment issue, not a production code bug. The test at line 140 of
    agent-brain-cli/tests/test_config.py patches os.environ to be empty but does NOT
    mock the filesystem calls inside get_server_url().

    get_server_url() resolution order (config.py lines 314-352):
      1. AGENT_BRAIN_URL env var (correctly cleared by patch.dict)
      2. runtime.json in the state directory (NOT mocked)
      3. config file
      4. default http://127.0.0.1:8000

    get_server_url() calls get_state_dir() which calls _find_project_root() which uses
    git rev-parse to find the repo root. From within the repo, this resolves to the
    actual project root. It then checks for a runtime.json at
    {project_root}/.claude/agent-brain/runtime.json.

    During manual testing the server was started on port 8123. Starting the server
    writes a runtime.json with "base_url": "http://127.0.0.1:8123". This file persists
    on disk after the test session ends. When the test suite runs, get_server_url()
    finds the stale runtime.json and returns the port-8123 URL instead of the default.

    The test isolation is incomplete: the test mocks the environment but not the
    filesystem state that get_server_url() also consults. The test needs to mock
    either get_state_dir() or the runtime.json file path so that no real filesystem
    state can leak in.

    This is reproducible only when a stale runtime.json exists from a previous manual
    test run. It will not fail on a clean CI machine or after deleting
    {project_root}/.claude/agent-brain/runtime.json.
  artifacts:
    - agent-brain-cli/tests/test_config.py (TestGetServerUrl.test_default_url, line 140)
    - agent-brain-cli/agent_brain_cli/config.py (get_server_url, lines 314-352)
  missing:
    - test_default_url should mock get_state_dir() (or _find_project_root()) to return a
      tmp_path so that no real runtime.json can be found during the test
    - Alternatively, mock the open() call or runtime_file.exists() check so the test
      is fully isolated from filesystem state
  debug_session: ""

## Connection Refused (Test 2) — Not a Gap

Test 2 observed "Connection refused" because the server was not running. This is expected
behavior. The CLI handles ConnectionError gracefully in
agent-brain-cli/agent_brain_cli/commands/index.py (lines 180-187): it prints a formatted
error message and exits with code 1. No traceback is shown. No code change needed.
