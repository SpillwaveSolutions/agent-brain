---
created: 2026-02-25T18:45:24.065Z
title: Fix include_types pipeline plumbing
area: api
files:
  - agent-brain-server/agent_brain_server/models/job.py:42-70
  - agent-brain-server/agent_brain_server/job_queue/job_service.py:167-182
  - agent-brain-server/agent_brain_server/job_queue/job_worker.py:211-221
  - agent-brain-server/agent_brain_server/services/indexing_service.py:267-289
  - agent-brain-server/agent_brain_server/indexing/document_loader.py:481-533
  - agent-brain-server/agent_brain_server/api/routers/index.py:155-178
---

## Problem

The include_types feature (file type presets like `python`, `docs`) is partially implemented across 4 hops in the indexing pipeline. Preset resolution logic exists and is correct in `indexing_service.py`, but data never reaches it due to 3 independent breakpoints:

1. **JobRecord model missing `include_types` field** (`job.py:42-70`): The Pydantic model has `include_patterns` and `exclude_patterns` but no `include_types`. When `job_service.py:167-182` constructs a JobRecord from IndexRequest, `include_types` is silently dropped.

2. **job_worker doesn't pass include_types** (`job_worker.py:211-221`): The worker reconstructs an IndexRequest from JobRecord fields but never includes `include_types`, even if the field existed on JobRecord.

3. **effective_include_patterns computed but discarded** (`indexing_service.py:267-289`): The code correctly resolves presets into `effective_include_patterns` (lines 268-283), then calls `document_loader.load_files()` with only `(abs_folder_path, recursive, include_code)` — the patterns are never passed. DocumentLoader.load_files() (`document_loader.py:481-533`) has no `include_patterns` parameter.

Additionally, unknown preset names (e.g., `--include-type bogus`) are never validated at the API level. Since include_types is dropped before reaching the pipeline, `resolve_file_types()` (which raises ValueError for unknowns) is never called.

Diagnosed during Phase 12 UAT — Tests 9 and 10 (both severity: major).

## Solution

Five files need changes to complete the pipeline:

1. Add `include_types: list[str] | None = None` field to `JobRecord` in `job.py`
2. Store `include_types` when creating JobRecord in `job_service.py` enqueue_job
3. Pass `include_types` when reconstructing IndexRequest in `job_worker.py`
4. Add `include_patterns` parameter to `DocumentLoader.load_files()` and apply glob filtering via `required_exts` translation or post-filter
5. Pass `effective_include_patterns` to `load_files()` in `indexing_service.py` instead of discarding them
6. Add early validation in `index.py` API router: call `resolve_file_types()` before enqueueing, raise HTTP 400 on ValueError
