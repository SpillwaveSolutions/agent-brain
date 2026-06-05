# Plan 01: Phase 54 foundation — schemas + ApiClient methods

**Phase:** 54 — 9 remaining MCP tools
**Requirements covered:** Foundation for TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08, TOOL-09 (no requirement is directly closed by this plan; all 9 land in Plans 02–04 which import from here)
**Depends on:** none — first plan
**Parallel-safe with:** none (Plans 02, 03, 04 all import from this plan's outputs)
**Status:** Not started

## Goal

Land the contracts the four other Phase 54 plans build against. This plan adds the 9 input/output Pydantic models to `agent_brain_mcp/schemas.py`, the 5 new `ApiClient` methods to `agent_brain_mcp/client.py`, and the vendored `FILE_TYPE_PRESETS` table to `agent_brain_mcp/tools/file_types.py`. No tool handlers, no `TOOL_REGISTRY` mutations, no `server.py` changes — purely the building blocks. Plans 02/03/04 then wire handlers against these contracts.

This is the "interface-first" ordering required by interface-first task ordering — downstream plans receive the contracts rather than scavenging for them.

## Acceptance Criteria

- [ ] `schemas.py` exports 18 new symbols (9 input + 9 output models, named `<ToolName>Input` / `<ToolName>Output` in PascalCase):
  - `ExplainResultInput` / `ExplainResultOutput`
  - `AddDocumentsInput` / `AddDocumentsOutput`
  - `InjectDocumentsInput` / `InjectDocumentsOutput`
  - `WaitForJobInput` / `WaitForJobOutput`
  - `ListFoldersInput` / `ListFoldersOutput`
  - `RemoveFolderInput` / `RemoveFolderOutput`
  - `CacheStatusInput` / `CacheStatusOutput`
  - `ClearCacheInput` / `ClearCacheOutput`
  - `ListFileTypesInput` / `ListFileTypesOutput`
- [ ] Every input model passes the existing `json_schema()` helper and the resulting schema contains `"additionalProperties": false` (assertion in tests).
- [ ] Every model's field constraints (`ge=`, `le=`, `min_length=`, `max_length=`, `Literal[...]`) match the corresponding FastAPI route Pydantic model 1:1 (verified by side-by-side diff in PR description, plus a parameterized test in `tests/test_schema_constraints.py` that asserts each constraint).
- [ ] `client.py` exports 5 new `ApiClient` methods, each typed and returning the parsed response body (raw dict — handlers cast into output models):
  - `add_documents(self, body: dict, *, force: bool = False) -> dict`
  - `inject_documents(self, body: dict, *, force: bool = False) -> dict` (note: same `POST /index/` endpoint as v1 `index_folder`; this method just always sets `injector_script` and/or `folder_metadata_file` in body — see decision D in CONTEXT)
  - `cache_status(self) -> dict`
  - `clear_cache(self) -> dict`
  - `delete_folder(self, body: dict) -> dict`
- [ ] No method named `query_with_explain` — `explain_result` handler reuses existing `query(body)` with `explain=True` set on the body.
- [ ] `tools/file_types.py` exists and exports `FILE_TYPE_PRESETS: dict[str, list[str]]` vendored verbatim from `agent-brain-cli/agent_brain_cli/commands/types.py` (lines 19-90). A leading comment cites the source and Phase 55's parity contract test.
- [ ] `TOOL_REGISTRY` is unchanged. `server.py` is unchanged. `__all__` exports in `tools/__init__.py` and `tools/file_types.py` are added defensively but no registry mutation.
- [ ] Unit tests in `tests/test_schemas_phase54.py` cover: (a) each model round-trips with valid input, (b) each model rejects an additional unknown field, (c) each input's JSON Schema has `additionalProperties: false`, (d) constraint values match the documented values from CONTEXT decisions B/D/E/F/H.
- [ ] Unit tests in `tests/test_client_phase54.py` cover the 5 new methods against a `respx`-mocked httpx transport (existing v1 test pattern in `tests/test_client.py`).
- [ ] `task mcp:test` passes from `agent-brain-mcp/`.
- [ ] `task mcp:pr-qa-gate` passes from `agent-brain-mcp/` (Black, Ruff, mypy strict, pytest).
- [ ] `task check:layering` passes from repo root (import-linter contracts unchanged).
- [ ] `task before-push` passes from repo root.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/agent_brain_mcp/schemas.py` | modify | Append 9 input + 9 output Pydantic models. Match v1's existing style — hand-written, minimal projections, `additionalProperties: false` via `json_schema()`. Add module-level section header `# Phase 54 — 9 remaining tools`. |
| `agent-brain-mcp/agent_brain_mcp/client.py` | modify | Append 5 new methods after the existing 8. Each is a 3-5 line `_request()` wrapper. Match v1 style (lines 80-125). |
| `agent-brain-mcp/agent_brain_mcp/tools/file_types.py` | create | New module. Vendor `FILE_TYPE_PRESETS` from CLI verbatim. Add module docstring citing source + Phase 55 parity contract. |
| `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` | modify | Defensive: add `from . import file_types` so the module is reachable. Do NOT add to `TOOL_REGISTRY` (that's Plan 02). |
| `agent-brain-mcp/tests/test_schemas_phase54.py` | create | New test module — 9 model round-trips × 2 (valid + extra-field-rejection) + JSON Schema additionalProperties assertion × 9 + constraint assertions. |
| `agent-brain-mcp/tests/test_client_phase54.py` | create | New test module — 5 new ApiClient methods, respx-mocked. |
| `agent-brain-mcp/tests/test_file_types_presets.py` | create | Smoke test: imports `FILE_TYPE_PRESETS` from MCP module and asserts it's a non-empty `dict[str, list[str]]` with at least 11 presets (matches the CLI count documented in CLAUDE.md). Phase 55's cross-package parity test is separate. |

## Implementation Steps

1. Open `agent-brain-mcp/agent_brain_mcp/schemas.py` and read the v1 model conventions (header comment block lines 1-25, `IndexFolderInput` and `IndexFolderOutput` as canonical examples).
2. Open `agent-brain-server/agent_brain_server/api/routers/index.py`, `routers/folders.py`, `routers/cache.py`, `routers/query.py` and note the Pydantic models on each route for the 9 tools we'll wrap. Build a side-by-side constraint table in your PR description.
3. Open `agent-brain-server/agent_brain_server/models/query.py:ResultExplanation` (lines 153-208) — `ExplainResultOutput` mirrors its 6 fields verbatim (`reason`, `matched_terms`, `fusion`, `graph_path`, `rerank_movement`, `graph_fallback`).
4. Add the 9 input models. Per CONTEXT decisions:
   - `ExplainResultInput`: `query: str`, `chunk_id: str`, `mode: Literal["semantic","bm25","hybrid","graph","multi"] = "hybrid"`, `top_k: int = 50` (`ge=1, le=200`), `alpha: float = 0.5`. (Decision F.)
   - `AddDocumentsInput`: `paths: list[str]` (`min_length=1`), `force: bool = False`. **Do NOT include `allow_external`** — it was removed from the server route in issue #180 (CONTEXT `<specifics>`).
   - `InjectDocumentsInput`: `folder_path: str`, `injector_script: str | None = None`, `folder_metadata_file: str | None = None`, `dry_run: bool = False`, `force: bool = False`, `allow_external: bool = False`, `include_code: bool = True`, `chunk_size: int | None = None`, `chunk_overlap: int | None = None`. Add a Pydantic root validator requiring at least one of `injector_script` / `folder_metadata_file`. (Decision D.)
   - `WaitForJobInput`: `job_id: str`, `poll_interval_seconds: float = 1.0` (`ge=0.5, le=2.0` — server-enforced upper bound to honor the ≤2s spec requirement), `timeout_seconds: int | None = None` (`ge=1`). (Decision E.)
   - `ListFoldersInput`: empty model (no parameters).
   - `RemoveFolderInput`: `folder_path: str`, `confirm: Literal[True]` (Greenfield pattern — destructive op deserves the confirm guard, matches `CancelJobInput`).
   - `CacheStatusInput`: empty model.
   - `ClearCacheInput`: `confirm: Literal[True]` (Greenfield pattern — same rationale as `RemoveFolderInput`).
   - `ListFileTypesInput`: empty model.
5. Add the 9 output models. Per CONTEXT:
   - `ExplainResultOutput`: `chunk_id: str`, `text: str`, `source: str`, `score: float`, plus 6 fields mirroring `ResultExplanation` (`reason: str`, `matched_terms: list[str]`, `fusion: dict[str, Any] | None`, `graph_path: list[str] | None`, `rerank_movement: dict[str, Any] | None`, `graph_fallback: bool`).
   - `AddDocumentsOutput`: `job_id: str`, `status: str`. Match `index_folder`'s output shape.
   - `InjectDocumentsOutput`: `job_id: str`, `status: str`, `message: str | None = None`. Note dry-run path returns `job_id="dry_run"`, `status="completed"` (Decision D).
   - `WaitForJobOutput`: extend `GetJobOutput` fields (`job_id`, `status`, `progress_percent`, `message`, `started_at`, `completed_at`) plus `final: bool = True`, `elapsed_seconds: float`. (Decision E.)
   - `ListFoldersOutput`: `folders: list[FolderInfoMcp]` where `FolderInfoMcp` mirrors `agent_brain_server.models.folders.FolderInfo` (`folder_path`, `chunk_count`, `last_indexed`, `watch_mode`, `watch_debounce_seconds`).
   - `RemoveFolderOutput`: `folder_path: str`, `chunks_removed: int`, `documents_removed: int` (mirror `FolderDeleteResponse`).
   - `CacheStatusOutput`: mirror server's cache status response (whatever `GET /index/cache/` returns — read `routers/cache.py` for the canonical shape).
   - `ClearCacheOutput`: `cleared: bool`, `message: str` (or whatever `DELETE /index/cache/` returns).
   - `ListFileTypesOutput`: `presets: dict[str, list[str]]`, `preset_count: int`, `extension_count: int`. (Decision H — matches `agent-brain types list --json` shape.)
6. Open `agent-brain-mcp/agent_brain_mcp/client.py` and append 5 new methods after the existing 8. Each follows the pattern at lines 94-125 — call `self._request(...)`, return parsed JSON. Routes per CONTEXT decision C:
   - `add_documents(body, *, force)` → `POST /index/add?force=<bool>`
   - `inject_documents(body, *, force)` → `POST /index/?force=<bool>` (note: `body` must contain `folder_path` and at least one of `injector_script` / `folder_metadata_file`; this is the same endpoint as `index_folder` — the differentiator is the request body)
   - `cache_status()` → `GET /index/cache/`
   - `clear_cache()` → `DELETE /index/cache/`
   - `delete_folder(body)` → `DELETE /index/folders/` (note: `FolderDeleteRequest` is request **body**, not query/path — see §2 of v1 design doc)
7. Create `agent-brain-mcp/agent_brain_mcp/tools/file_types.py`. Vendor `FILE_TYPE_PRESETS` verbatim from `agent-brain-cli/agent_brain_cli/commands/types.py` (lines 19-90). Module docstring:
   ```
   """File type presets — vendored from agent-brain-cli for the list_file_types MCP tool.

   This dict MUST stay in sync with agent-brain-cli/agent_brain_cli/commands/types.py
   FILE_TYPE_PRESETS. Phase 55 (VAL-01) contract test asserts equality across the two
   copies. If a preset changes in one, change it in both, or convert to a server-side
   GET /index/types endpoint (deferred per .planning/phases/54-remaining-mcp-tools/54-CONTEXT.md).
   """
   ```
8. Add `from . import file_types` to `tools/__init__.py` so the module is import-visible.
9. Write `tests/test_schemas_phase54.py`. For each of the 9 input models, assert:
   - A minimal valid construction succeeds.
   - Passing an extra field raises `pydantic.ValidationError` (proves `additionalProperties: false`).
   - The JSON Schema returned by `json_schema(<Model>)` contains `"additionalProperties": false`.
   - Each numeric constraint matches the value listed in the implementation step (e.g., `WaitForJobInput.poll_interval_seconds` has `ge=0.5` and `le=2.0`).
   For each of the 9 output models, assert a round-trip with a representative dict.
10. Write `tests/test_client_phase54.py` using `respx` (the v1 client test pattern). For each new method, mock the route and assert (a) correct URL, (b) correct HTTP verb, (c) correct query/body, (d) returned dict matches mocked response.
11. Write `tests/test_file_types_presets.py` — import `FILE_TYPE_PRESETS`, assert `len(...) >= 11` and `all(isinstance(v, list) and v for v in FILE_TYPE_PRESETS.values())`.
12. Run `task mcp:test` from `agent-brain-mcp/`. Fix any failures.
13. Run `task mcp:pr-qa-gate` from `agent-brain-mcp/`. Fix any Black / Ruff / mypy issues.
14. Run `task check:layering` from repo root. The new `tools/file_types.py` module imports only stdlib — should be fine. Confirm.
15. Run `task before-push` from repo root. Must exit 0. **No exceptions per CLAUDE.md.**

## Verification

```bash
# Run new tests directly
cd agent-brain-mcp && poetry run pytest tests/test_schemas_phase54.py tests/test_client_phase54.py tests/test_file_types_presets.py -v

# Full package test + quality gate
cd agent-brain-mcp && task test
cd agent-brain-mcp && task pr-qa-gate

# Layering invariants still hold
cd /Users/richardhightower/clients/spillwave/src/agent-brain && task check:layering

# Root quality gate (MANDATORY per CLAUDE.md)
cd /Users/richardhightower/clients/spillwave/src/agent-brain && task before-push

# Smoke check: every new schema has additionalProperties: false
cd agent-brain-mcp && poetry run python -c "
from agent_brain_mcp.schemas import (
    json_schema, ExplainResultInput, AddDocumentsInput, InjectDocumentsInput,
    WaitForJobInput, ListFoldersInput, RemoveFolderInput,
    CacheStatusInput, ClearCacheInput, ListFileTypesInput,
)
for m in [ExplainResultInput, AddDocumentsInput, InjectDocumentsInput,
          WaitForJobInput, ListFoldersInput, RemoveFolderInput,
          CacheStatusInput, ClearCacheInput, ListFileTypesInput]:
    s = json_schema(m)
    assert s.get('additionalProperties') is False, m.__name__
    print(f'{m.__name__}: OK')
"

# Smoke check: FILE_TYPE_PRESETS importable and non-empty
cd agent-brain-mcp && poetry run python -c "
from agent_brain_mcp.tools.file_types import FILE_TYPE_PRESETS
assert len(FILE_TYPE_PRESETS) >= 11
print(f'FILE_TYPE_PRESETS: {len(FILE_TYPE_PRESETS)} presets OK')
"
```

## Risk Notes

- **Schema constraint drift** — the bedrock risk for this whole phase. Walk the server routes line-by-line and copy constraints verbatim; do NOT rely on memory or "what feels right". The PR description must include a side-by-side comparison table (server field → MCP field, constraint → constraint).
- **`InjectDocumentsInput` root validator** — Pydantic v2 syntax differs from v1. Use `@model_validator(mode="after")` not `@root_validator`. Check the v1 codebase for an existing example before writing it (v1 `IndexFolderInput` doesn't have one, so this is genuinely new).
- **`Literal[True]` confirm pattern on `clear_cache` / `remove_folder`** — this is a Phase 54 extension of v1's `cancel_job` safety pattern. Mention it in the PR description so reviewers know it's intentional, not copy-paste from `cancel_job`.
- **Vendoring `FILE_TYPE_PRESETS`** — second copy creates drift risk. The module docstring + Phase 55 contract test are the safety net. Do NOT try to refactor CLI to expose the dict — that creates a CLI → MCP dependency direction the import-linter contracts forbid.
- **`additionalProperties: false`** — the `json_schema()` helper sets this automatically, but if a test fails on a model it usually means the model is missing `model_config = ConfigDict(extra="forbid")` (which is what makes Pydantic refuse extra fields at runtime). The two-way enforcement (Pydantic at runtime, JSON Schema at MCP-client-prevalidation) requires both.

---
*Plan 01 of Phase 54*
