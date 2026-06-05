---
phase: 12-folder-management-file-type-presets
plan: 01
subsystem: services
tags: [folder-management, jsonl, atomicwrite, file-type-presets, pydantic, chromadb, postgres, storage-protocol]

requires: []

provides:
  - FolderManager service with JSONL persistence and asyncio.Lock atomic writes
  - FolderRecord dataclass for tracking indexed folders with chunk IDs
  - FILE_TYPE_PRESETS dict with 14 named presets mapped to glob patterns
  - resolve_file_types() function for preset resolution with deduplication
  - FolderInfo, FolderListResponse, FolderDeleteRequest, FolderDeleteResponse Pydantic models
  - StorageBackendProtocol.delete_by_metadata() method on both backends

affects:
  - 12-02 (folder API router depends on FolderManager + folder models + delete_by_metadata)
  - 12-03 (CLI folder commands depend on folder models from API)

tech-stack:
  added: []
  patterns:
    - "Atomic JSONL writes via temp-file + Path.replace() rename"
    - "asyncio.Lock + asyncio.to_thread for async-safe sync I/O"
    - "Two-step ChromaDB delete: query IDs first, guard empty list, then delete by IDs"
    - "JSONB containment DELETE...RETURNING for count-in-one-query PostgreSQL deletes"

key-files:
  created:
    - agent-brain-server/agent_brain_server/services/folder_manager.py
    - agent-brain-server/agent_brain_server/services/file_type_presets.py
    - agent-brain-server/agent_brain_server/models/folders.py
    - agent-brain-server/tests/test_folder_manager.py
    - agent-brain-server/tests/test_file_type_presets.py
  modified:
    - agent-brain-server/agent_brain_server/services/__init__.py
    - agent-brain-server/agent_brain_server/models/__init__.py
    - agent-brain-server/agent_brain_server/storage/protocol.py
    - agent-brain-server/agent_brain_server/storage/chroma/backend.py
    - agent-brain-server/agent_brain_server/storage/postgres/backend.py
    - agent-brain-server/agent_brain_server/storage/vector_store.py
    - agent-brain-server/tests/unit/storage/test_protocol.py

key-decisions:
  - "Atomic JSONL writes via temp + replace (Path.replace is POSIX atomic) — safe for concurrent processes"
  - "asyncio.Lock wraps all cache mutations — single-threaded async safety without thread-pool contention"
  - "Two-step ChromaDB delete (get IDs then delete by IDs) — avoids collection wipe bug on empty ids=[]"
  - "DELETE...RETURNING for PostgreSQL — gets deleted count without extra SELECT round-trip"
  - "14 presets covers all common file types; 'code' is union of all language presets for convenience"
  - "resolve_file_types() validates all names before resolving — fails fast with all valid presets listed"

patterns-established:
  - "JSONL persistence pattern: atomic write via temp-file rename, load on initialize"
  - "File type preset resolution: validate-all-first then expand-and-deduplicate"
  - "Protocol extension: add method to Protocol + implement in both backends + update mock in test"

duration: 35min
completed: 2026-02-24
---

# Phase 12 Plan 01: Server Foundation for Folder Management Summary

**FolderManager (JSONL+asyncio.Lock), 14-preset FileTypePresetResolver, Pydantic folder models, and StorageBackendProtocol.delete_by_metadata on ChromaDB + PostgreSQL backends**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-02-24T01:07:17Z
- **Completed:** 2026-02-24T01:42:00Z
- **Tasks:** 3/3
- **Files modified:** 11 total (5 created, 6 modified)

## Accomplishments

- FolderManager with atomic JSONL persistence, asyncio.Lock safety, and Path.resolve() normalization (13 tests)
- FileTypePresetResolver with 14 presets and deduplication (26 tests)
- Pydantic folder models (FolderInfo, FolderListResponse, FolderDeleteRequest, FolderDeleteResponse) with schema examples
- StorageBackendProtocol extended with delete_by_metadata; both ChromaDB and PostgreSQL backends implement it
- VectorStoreManager.delete_by_where with critical empty-ID guard to prevent collection wipe
- All 725 existing + new tests pass; mypy strict, ruff, and black all clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Create FolderManager service with JSONL persistence** - `4af5b34` (feat)
2. **Task 2: Create FileTypePresetResolver and Pydantic folder models** - `8865872` (feat)
3. **Task 3: Extend StorageBackendProtocol + both backends with delete_by_metadata** - `ffd25ab` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified

- `agent-brain-server/agent_brain_server/services/folder_manager.py` - FolderManager + FolderRecord with JSONL persistence
- `agent-brain-server/agent_brain_server/services/file_type_presets.py` - FILE_TYPE_PRESETS + resolve_file_types + list_presets
- `agent-brain-server/agent_brain_server/models/folders.py` - FolderInfo, FolderListResponse, FolderDeleteRequest, FolderDeleteResponse
- `agent-brain-server/agent_brain_server/services/__init__.py` - added file_type_presets exports
- `agent-brain-server/agent_brain_server/models/__init__.py` - added folder model exports
- `agent-brain-server/agent_brain_server/storage/protocol.py` - added delete_by_metadata to StorageBackendProtocol
- `agent-brain-server/agent_brain_server/storage/chroma/backend.py` - ChromaBackend.delete_by_metadata
- `agent-brain-server/agent_brain_server/storage/postgres/backend.py` - PostgresBackend.delete_by_metadata
- `agent-brain-server/agent_brain_server/storage/vector_store.py` - VectorStoreManager.delete_by_where with empty-ID guard
- `agent-brain-server/tests/test_folder_manager.py` - 13 tests for FolderManager
- `agent-brain-server/tests/test_file_type_presets.py` - 26 tests for file_type_presets
- `agent-brain-server/tests/unit/storage/test_protocol.py` - updated MockCompleteBackend to implement delete_by_metadata

## Decisions Made

- **Atomic JSONL writes via temp + replace**: `Path.replace()` is POSIX-atomic, safe even if process crashes mid-write
- **asyncio.Lock wraps all cache mutations**: single-threaded async safety, no thread-pool contention
- **Two-step ChromaDB delete**: query IDs first (`.get(where=..., include=[])`), guard against empty list, then delete by IDs — avoids the critical ChromaDB bug where `delete(ids=[])` wipes the entire collection
- **DELETE...RETURNING for PostgreSQL**: gets deleted count in a single round-trip without extra SELECT COUNT
- **14 presets**: python, javascript, typescript, go, rust, java, csharp, c, cpp, web, docs, code, text, pdf — "code" is the union of all language presets
- **resolve_file_types() validate-all-first**: raises ValueError with all names before any resolution — better error message than validating one-at-a-time

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_get_folder_normalizes_path using relative path that can't work**
- **Found during:** Task 1 (FolderManager tests)
- **Issue:** Test used `get_folder("test_folder")` (relative) to look up a folder added as `/tmp/.../test_folder`. Since `Path.resolve()` resolves relative to CWD (not tmp_path), this lookup always returns None.
- **Fix:** Changed test to use `str(tmp_path) + "/./test_folder"` — an absolute path with redundant `./` that Path.resolve() normalizes to the canonical path
- **Files modified:** `tests/test_folder_manager.py`
- **Verification:** 13/13 tests pass including fixed test
- **Committed in:** `4af5b34` (Task 1 commit)

**2. [Rule 2 - Missing Critical] Updated MockCompleteBackend in test_protocol.py**
- **Found during:** Task 3 (running full test suite after adding delete_by_metadata to protocol)
- **Issue:** `MockCompleteBackend` in `test_protocol.py` didn't implement the new `delete_by_metadata` method, causing `isinstance(mock, StorageBackendProtocol)` to return False (protocol runtime_checkable check)
- **Fix:** Added `async def delete_by_metadata(self, where: dict[str, any]) -> int: return 0` to the mock
- **Files modified:** `tests/unit/storage/test_protocol.py`
- **Verification:** All 725 tests pass
- **Committed in:** `ffd25ab` (Task 3 commit)

**3. [Rule 1 - Bug] Fixed ruff linting errors in folder_manager.py**
- **Found during:** Final quality check (Task 3)
- **Issue:** Unused `typing.Any` import, unnecessary `"r"` open mode parameter, missing blank line after imports
- **Fix:** Removed unused import, removed redundant mode parameter, added blank line
- **Files modified:** `agent_brain_server/services/folder_manager.py`
- **Verification:** `ruff check` and `black --check` both pass
- **Committed in:** `ffd25ab` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 2 missing critical)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02 (folder API router) can proceed: FolderManager, folder Pydantic models, and delete_by_metadata are all implemented
- Plan 03 (CLI folder commands) can proceed after Plan 02 ships the API endpoints
- ChromaDB delete_by_metadata uses source metadata field — callers should use chunk_ids from FolderRecord for precise targeted deletion (avoids needing $contains substring matching)

---
*Phase: 12-folder-management-file-type-presets*
*Completed: 2026-02-24*

## Self-Check: PASSED

**Files verified:**
- FOUND: agent-brain-server/agent_brain_server/services/folder_manager.py
- FOUND: agent-brain-server/agent_brain_server/services/file_type_presets.py
- FOUND: agent-brain-server/agent_brain_server/models/folders.py
- FOUND: agent-brain-server/tests/test_folder_manager.py
- FOUND: agent-brain-server/tests/test_file_type_presets.py
- FOUND: .planning/phases/12-folder-management-file-type-presets/12-01-SUMMARY.md

**Commits verified:**
- FOUND: 4af5b34 (Task 1 - FolderManager)
- FOUND: 8865872 (Task 2 - FileTypePresets + folder models)
- FOUND: ffd25ab (Task 3 - delete_by_metadata on both backends)
