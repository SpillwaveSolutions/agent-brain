---
phase: 54
plan: "01"
subsystem: agent-brain-mcp
tags:
  - mcp
  - schemas
  - contracts
  - phase-foundation
dependency_graph:
  requires:
    - 53-PLAN.md (MCP package was previously stable)
  provides:
    - 18 Pydantic schemas (9 input + 9 output) for Phase 54 tools
    - 5 ApiClient methods backing the 9 tool handlers
    - Vendored FILE_TYPE_PRESETS table for list_file_types tool
  affects:
    - 54-02 (read-only tools — consumes ExplainResultInput/Output, ListFoldersInput/Output, CacheStatusInput/Output, ListFileTypesInput/Output and the corresponding ApiClient methods)
    - 54-03 (mutating tools — consumes AddDocumentsInput/Output, InjectDocumentsInput/Output, RemoveFolderInput/Output, ClearCacheInput/Output and the matching ApiClient methods)
    - 54-04 (wait_for_job — consumes WaitForJobInput/Output)
tech_stack:
  added: []
  patterns:
    - "Pydantic v2 ConfigDict(extra='forbid') + json_schema() helper for MCP-spec additionalProperties: false"
    - "@model_validator(mode='after') for cross-field validation (InjectDocumentsInput requires injector_script OR folder_metadata_file)"
    - "confirm: Literal[True] guard on destructive ops (extended Phase 54 pattern from v1 CancelJobInput)"
    - "Vendored FILE_TYPE_PRESETS instead of cross-package import (preserves import-linter contracts)"
key_files:
  created:
    - agent-brain-mcp/agent_brain_mcp/tools/file_types.py
    - agent-brain-mcp/tests/test_schemas_phase54.py
    - agent-brain-mcp/tests/test_client_phase54.py
    - agent-brain-mcp/tests/test_file_types_presets.py
  modified:
    - agent-brain-mcp/agent_brain_mcp/schemas.py
    - agent-brain-mcp/agent_brain_mcp/client.py
    - agent-brain-mcp/agent_brain_mcp/tools/__init__.py
decisions:
  - "Omit allow_external from BOTH AddDocumentsInput AND InjectDocumentsInput (Rule 1 deviation from plan/CONTEXT D — issue #180 removed it from BOTH POST /index/add and POST /index/; exposing it MCP-side would create a silent no-op + constraint mismatch)"
  - "Use chunks_deleted (not chunks_removed) on RemoveFolderOutput — mirrors FolderDeleteResponse 1:1, NOT the plan's suggested chunks_removed/documents_removed pair (Rule 1 — server has no documents_removed; planning shorthand mis-matched the wire shape)"
  - "ExplainResultOutput.fusion is dict[str, float] | None and rerank_movement is int | None — NOT dict[str, Any]/dict[str, Any]/bool as the plan summary said (Rule 1 — server ResultExplanation lines 153-208 declare these types; constraint-1:1 principle overrides plan paraphrasing)"
  - "CacheStatusOutput uses ConfigDict(extra='allow') so future server-side additions to the cache-status payload don't break MCP clients (output models — server expansion is forward-compatible by default)"
  - "FILE_TYPE_PRESETS vendored verbatim from agent-brain-cli/agent_brain_cli/commands/types.py — Phase 55 VAL-01 contract test cited in module docstring is the drift detection mechanism"
metrics:
  duration_minutes: 17
  completed_date: 2026-06-03
  tests_added: 92
  tests_before: 308
  tests_after: 400
  commits: 5
  files_changed: 7
  lines_added_approx: 1230
---

# Phase 54 Plan 01: Schemas + ApiClient + FILE_TYPE_PRESETS Summary

**One-liner:** Locked the contracts (18 Pydantic schemas + 5 ApiClient methods + vendored FILE_TYPE_PRESETS table) that Phase 54 Plans 02/03/04 will use to wire the 9 remaining MCP tool handlers against the existing FastAPI routes.

## Scope Recap

Plan 01 is the foundation plan for Phase 54: it ships the interface layer
that the next three plans consume.  No tool handlers were registered, no
`TOOL_REGISTRY` entries were added, no `server.py` was touched.  Plans 02
(read-only tools), 03 (mutating tools), and 04 (`wait_for_job`) all
`from agent_brain_mcp.schemas import …` and `client.<new method>(…)`
using exactly the symbols this plan locks.

## Server↔MCP Constraint Comparison Table

Every constraint on every input model was copied **verbatim** from a
specific line in either an `agent_brain_server.models.*` Pydantic model
or a FastAPI route signature in `agent_brain_server.api.routers.*`.  The
side-by-side comparison reviewers requested:

### `ExplainResultInput` ↔ `QueryRequest` + `ResultExplanation`

| MCP field                | Server source                                                 | Constraint match                            |
| ------------------------ | ------------------------------------------------------------- | ------------------------------------------- |
| `query: str`             | `QueryRequest.query` (models/query.py)                        | required, non-empty handled server-side     |
| `chunk_id: str`          | (MCP-side post-filter — no direct server param)               | required                                    |
| `mode: Literal[5]`       | `QueryRequest.mode` Literal["semantic","bm25","hybrid","graph","multi"] | 1:1, same default `"hybrid"`         |
| `top_k: int = 50, ge=1, le=200` | `QueryRequest.top_k = 10, ge=1, le=100` (MCP override per CONTEXT F) | **Intentional divergence**: 50 default + le=200 so the chunk_id is more likely to appear in the explained pool |
| `alpha: float = 0.5, ge=0.0, le=1.0` | `QueryRequest.alpha = 0.5, ge=0.0, le=1.0`             | 1:1                                         |

### `AddDocumentsInput` ↔ `POST /index/add`

| MCP field                | Server source                                                       | Constraint match                                    |
| ------------------------ | ------------------------------------------------------------------- | --------------------------------------------------- |
| `paths: list[str], min_length=1` | `IndexRequest.folder_path: str, min_length=1` (per-call iteration MCP-side) | List form for MCP convenience; min_length=1 mirrors |
| `force: bool = False`    | `add_documents` query `force: bool = Query(False)`                   | 1:1                                                 |
| (omitted) `allow_external` | Removed from server route by issue #180                           | **Intentionally absent** — preventing silent drift  |

### `InjectDocumentsInput` ↔ `POST /index/` (with injector fields)

| MCP field                                    | Server source                                                | Constraint match                                |
| -------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------- |
| `folder_path: str, min_length=1`             | `IndexRequest.folder_path: str, min_length=1`                | 1:1                                             |
| `injector_script: str \| None`               | `IndexRequest.injector_script: str \| None`                  | 1:1                                             |
| `folder_metadata_file: str \| None`          | `IndexRequest.folder_metadata_file: str \| None`             | 1:1                                             |
| `@model_validator: at least one of those two`| CLI inject command lines 138-141                              | New MCP-side enforcement (CONTEXT D)            |
| `dry_run: bool = False`                      | `IndexRequest.dry_run: bool = False`                         | 1:1                                             |
| `force: bool = False`                        | `index_documents` query `force: bool = Query(False)`         | 1:1                                             |
| `include_code: bool = True`                  | `IndexRequest.include_code: bool = False` (MCP default flip)  | **Intentional default flip**: CLI inject default + plan §4 step 4 (MCP injection users want code by default) |
| `chunk_size: int \| None = None, ge=128, le=2048` | `IndexRequest.chunk_size: int = 512, ge=128, le=2048`    | bounds 1:1; default-None means "use server's 512" |
| `chunk_overlap: int \| None = None, ge=0, le=200` | `IndexRequest.chunk_overlap: int = 50, ge=0, le=200`     | bounds 1:1; default-None means "use server's 50"   |
| (omitted) `allow_external`                   | Removed from server route by issue #180                       | **Intentionally absent** — see Deviation §1     |

### `WaitForJobInput` ↔ `GET /index/jobs/{id}` polling loop

| MCP field                                            | Source                                                      | Constraint match                                |
| ---------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------- |
| `job_id: str`                                        | path param on `GET /index/jobs/{id}`                         | 1:1                                             |
| `poll_interval_seconds: float = 1.0, ge=0.5, le=2.0` | MCP spec ≤ 2.0s cadence (no server constraint)              | MCP-spec enforced (CONTEXT E)                    |
| `timeout_seconds: int \| None = None, ge=1`          | Client-side soft cap (no server constraint)                 | MCP-side only                                    |

### `RemoveFolderInput` ↔ `FolderDeleteRequest`

| MCP field                        | Server source                                              | Constraint match                                        |
| -------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------- |
| `folder_path: str, min_length=1` | `FolderDeleteRequest.folder_path: str, min_length=1`       | 1:1                                                     |
| `confirm: Literal[True]`         | (Greenfield — extension of v1 `CancelJobInput.confirm`)    | Phase 54 destructive-op pattern                          |

### `ClearCacheInput` ↔ `DELETE /index/cache/`

| MCP field                | Server source                                              | Constraint match                                        |
| ------------------------ | ---------------------------------------------------------- | ------------------------------------------------------- |
| `confirm: Literal[True]` | (Greenfield — extension of v1 `CancelJobInput.confirm`)    | Phase 54 destructive-op pattern                          |

### Empty-input models (`ListFoldersInput`, `CacheStatusInput`, `ListFileTypesInput`)

All three carry `model_config = ConfigDict(extra="forbid")` so any
caller smuggling fields will hit a `ValidationError` at Pydantic-construction
AND the JSON Schema advertised over the wire shows `additionalProperties:
false` to MCP-client pre-validators.

### Output model field shapes (server source 1:1)

| MCP output model                   | Server source                                                 | Notes                                                                       |
| ---------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------- |
| `ExplainResultOutput` (10 fields)  | `QueryResult` text/source/score + `ResultExplanation` (6)     | `fusion`=`dict[str,float]\|None`, `rerank_movement`=`int\|None`, `graph_fallback`=`bool\|None` — exact 1:1 |
| `AddDocumentsOutput`/`InjectDocumentsOutput` | `IndexResponse` (job_id, status, message)           | 1:1                                                                          |
| `WaitForJobOutput`                 | `GetJobOutput` (v1) + `final: bool = True, elapsed_seconds: float` | Extension per CONTEXT E                                                       |
| `FolderInfoMcp`                    | `agent_brain_server.models.folders.FolderInfo`                | 5-field 1:1 mirror                                                            |
| `ListFoldersOutput`                | `FolderListResponse`                                          | 1:1 (folders list + total)                                                    |
| `RemoveFolderOutput`               | `FolderDeleteResponse`                                        | **Uses `chunks_deleted` (NOT `chunks_removed`)** — server-name 1:1            |
| `CacheStatusOutput`                | `_cache_status_impl` return dict                              | 6 typed keys + `extra="allow"` for forward compat                             |
| `ClearCacheOutput`                 | `_clear_cache_impl` return dict                               | count + size_bytes + size_mb 1:1                                              |
| `ListFileTypesOutput`              | `agent-brain types list --json`                              | presets + preset_count + extension_count per CONTEXT H                        |

## New ApiClient Methods

| Method                                                  | Route                       | Notes                                                          |
| ------------------------------------------------------- | --------------------------- | -------------------------------------------------------------- |
| `add_documents(body, *, force=False) -> dict`           | `POST /index/add?force=…`   | No `allow_external` query param (#180)                          |
| `inject_documents(body, *, force=False) -> dict`        | `POST /index/?force=…`      | Same endpoint as v1 `index_folder`; differentiator is the body  |
| `cache_status() -> dict`                                | `GET /index/cache/`         | 503 → `McpError` via existing `raise_for_status`                |
| `clear_cache() -> dict`                                 | `DELETE /index/cache/`      | Unconditional — MCP-handler `confirm: Literal[True]` is the gate |
| `delete_folder(body) -> dict`                           | `DELETE /index/folders/`    | `FolderDeleteRequest` is a **body**, not query                  |

All 5 reuse the existing `_request → raise_for_status` pipeline. No new
error mapping (CONTEXT decision G).

## Vendored Table

`agent_brain_mcp/tools/file_types.py` carries `FILE_TYPE_PRESETS: dict[str, list[str]]` — 16 presets vendored verbatim from `agent-brain-cli/agent_brain_cli/commands/types.py` (lines 19-61 of that file, as of commit `51dd48f`). The module docstring cites the source and names Phase 55 VAL-01 as the parity-contract test. No import of `agent_brain_cli` from MCP (forbidden by import-linter).

`tools/__init__.py` adds `from . import file_types` and includes `file_types` in `__all__`. `TOOL_REGISTRY` is UNCHANGED (still 7 v1 tools); `server.py` is UNCHANGED.

## Deviations from Plan

### Auto-fixed Issues (Rule 1 — bug-class)

**1. [Rule 1 — Bug] Removed `allow_external` from `InjectDocumentsInput`**

- **Found during:** Task 1 (schemas drafting)
- **Issue:** Plan §4 step 4 and CONTEXT decision D list `allow_external: bool = False` on `InjectDocumentsInput`. However, the server-side `POST /index/` route (which `inject_documents` wraps) does NOT accept an `allow_external` query parameter (only `force` and `rebuild_graph`). Issue #180 removed `allow_external` from both `POST /index/add` AND `POST /index/`; the only remaining containment control is the server-side `AGENT_BRAIN_ALLOW_EXTERNAL_PATHS` setting. Exposing it MCP-side would create a silent no-op + violate the "every field constraint matches server 1:1" principle.
- **Fix:** `allow_external` omitted from `InjectDocumentsInput`; constraint matches the server route 1:1. Added defensive test `test_no_allow_external_field` to lock it.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/schemas.py`, `agent-brain-mcp/tests/test_schemas_phase54.py`
- **Commit:** `bcf9fc3` (schemas), `b95fa0b` (test pin)

**2. [Rule 1 — Bug] `RemoveFolderOutput` uses `chunks_deleted`, NOT `chunks_removed` / `documents_removed`**

- **Found during:** Task 1 (schemas drafting)
- **Issue:** Plan §5 step 5 lists `chunks_removed: int` and `documents_removed: int` for `RemoveFolderOutput`. But the server-side `FolderDeleteResponse` (models/folders.py:101-122) uses `chunks_deleted: int` and has NO `documents_removed` field; the server returns `folder_path`, `chunks_deleted`, `message`. The plan's field names were paraphrasing the server shape and would create a silent rename + a phantom field.
- **Fix:** `RemoveFolderOutput` uses `folder_path: str`, `chunks_deleted: int = Field(ge=0)`, `message: str` — exact 1:1 mirror of `FolderDeleteResponse`. Added `test_uses_chunks_deleted_not_chunks_removed` to lock the field name.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/schemas.py`, `agent-brain-mcp/tests/test_schemas_phase54.py`
- **Commit:** `bcf9fc3` (schemas), `b95fa0b` (test pin)

**3. [Rule 1 — Bug] `ExplainResultOutput.fusion / rerank_movement / graph_fallback` types match server, not plan paraphrase**

- **Found during:** Task 1 (schemas drafting)
- **Issue:** Plan §5 step 5 paraphrases the `ResultExplanation` fields as `fusion: dict[str, Any] | None`, `rerank_movement: dict[str, Any] | None`, `graph_fallback: bool`. The actual server-side declarations (models/query.py:177-208) are `fusion: dict[str, float] | None`, `rerank_movement: int | None`, `graph_fallback: bool | None`. The plan's looser types would either drop information (`int` reranked to `dict`) or block legitimate None values (`bool` vs `bool | None`).
- **Fix:** Types copied 1:1 from server `ResultExplanation`. The `test_round_trip_full` test exercises a realistic fusion dict and asserts the key roundtrips.
- **Files modified:** `agent-brain-mcp/agent_brain_mcp/schemas.py`, `agent-brain-mcp/tests/test_schemas_phase54.py`
- **Commit:** `bcf9fc3` (schemas), `b95fa0b` (test pin)

### Auto-fixed Issues (Rule 3 — blocking, build/lint)

**4. [Rule 3 — Blocking] Black reformatted 5 files + Ruff flagged 2 issues**

- **Found during:** Quality gate (after Task 4)
- **Issue:** Black wanted to reformat (a) the docstring continuation and parenthesized multi-arg calls in schemas.py, (b) the `from . import (file_types,)` wrap in tools/__init__.py, (c) line-wrapping in all three new test modules. Ruff additionally flagged `UP037` (quoted forward-reference annotation in the model_validator) and `F401` on the noqa-tagged `file_types` import.
- **Fix:** Ran `poetry run black agent_brain_mcp tests` (reformatted 5 files); dropped quotes around `InjectDocumentsInput` return annotation (already a string under `from __future__ import annotations`); collapsed the import back to single-line `from . import file_types` AND added `file_types` to `__all__` so the unused-import warning naturally resolves AND the module becomes part of the package's public namespace (which it is — Plan 02 will import it).
- **Files modified:** schemas.py, tools/__init__.py, all three test modules
- **Commit:** `e5e7e6e` (chore — formatting + lint)

### Auto-fixed Issues (Rule 2 — missing critical functionality)

**5. [Rule 2 — Tests] Added 13 ApiClient tests covering 5 new methods**

- **Found during:** Task 4
- **Issue:** Repo doesn't have a pre-existing `tests/test_client.py` to mirror — the v1 client coverage is interleaved with tool tests via `MockTransport`. Without a dedicated client test module, the 5 new methods would only be exercised transitively by Plan 02's handler tests (which won't land for days). That's a constraint-drift gap.
- **Fix:** Wrote `tests/test_client_phase54.py` with 13 tests — each new method gets URL/verb/body/query-param assertions via a capturing MockTransport; the `allow_external`-immunity test triple-checks that defense-in-depth holds even if a caller smuggles the field into the body; error-path smoke proves 404/409 surface as `McpError`.
- **Files modified:** `agent-brain-mcp/tests/test_client_phase54.py` (new)
- **Commit:** `b95fa0b`

## Authentication Gates

None. This is pure schema/contract work; no network calls outside the
fully-stubbed `MockTransport` in the test layer.

## Quality Gate Results

| Gate                                                       | Result               |
| ---------------------------------------------------------- | -------------------- |
| `poetry run black --check agent_brain_mcp tests`           | exit 0 (77 files clean) |
| `poetry run ruff check agent_brain_mcp tests`              | exit 0 ("All checks passed") |
| `poetry run mypy agent_brain_mcp`                          | exit 0 ("Success: no issues found in 31 source files") |
| `poetry run pytest -q` (MCP package)                       | **400 passed**, 46 deselected, 2 warnings, 7s (was 308 → +92) |
| `task check:layering`                                      | exit 0 (3/3 contracts kept) |
| `task before-push` (repo root)                             | exit 0 (1269 + 416 = 1685 passed across server+CLI; coverage ≥ 80% gate honored) |

## Commit Trail

| Commit  | Type      | Description                                                                |
| ------- | --------- | -------------------------------------------------------------------------- |
| `bcf9fc3` | feat    | Add 18 Phase 54 schemas (9 input + 9 output) to schemas.py                 |
| `8d52cc4` | feat    | Add 5 ApiClient methods backing Phase 54 tool handlers                     |
| `f3e7920` | feat    | Vendor FILE_TYPE_PRESETS for list_file_types tool                          |
| `b95fa0b` | test    | Pin Phase 54 schemas, ApiClient methods, and FILE_TYPE_PRESETS              |
| `e5e7e6e` | chore   | Black reformat + ruff fixes for Phase 54 contracts                          |

## Locked Public Surface (consumed by Plans 02-04)

```python
from agent_brain_mcp.schemas import (
    # 9 input models
    ExplainResultInput, AddDocumentsInput, InjectDocumentsInput,
    WaitForJobInput, ListFoldersInput, RemoveFolderInput,
    CacheStatusInput, ClearCacheInput, ListFileTypesInput,
    # 9 output models
    ExplainResultOutput, AddDocumentsOutput, InjectDocumentsOutput,
    WaitForJobOutput, ListFoldersOutput, RemoveFolderOutput,
    CacheStatusOutput, ClearCacheOutput, ListFileTypesOutput,
    # Support model
    FolderInfoMcp,
)
from agent_brain_mcp.client import ApiClient
# new methods: add_documents, inject_documents, cache_status, clear_cache, delete_folder
from agent_brain_mcp.tools.file_types import FILE_TYPE_PRESETS
```

These names + signatures + constraints are LOCKED.  Plans 02/03/04 may
extend models with new optional fields, but renames or constraint
changes require an explicit follow-up review.

## Self-Check: PASSED

All 7 declared files exist on disk; all 5 declared commits resolve via
`git log`. Tested at completion (2026-06-03T18:22Z).

---
*Plan 01 of Phase 54 — duration 17 minutes, 5 commits, +92 tests*
