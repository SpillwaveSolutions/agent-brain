# Plan 02: 16-tool parameterized contract tests + resource templates assertion (VAL-01)

**Phase:** 55 — Validation, contract tests & QA gate integration
**Requirements covered:** VAL-01
**Depends on:** Plan 01 (consumes `mcp_stdio_session` fixture + `_DEFAULT_RESPONSES`)
**Parallel-safe with:** Plan 03 (different test files, both consume Plan 01)
**Status:** Not started

## Goal

Land the parameterized contract test suite that drives all 16 MCP tools
(7 from v1 + 9 from v2) through the official MCP SDK client over stdio,
asserting `inputSchema` validation, `outputSchema` validation (when declared),
`content[0]` is `TextContent`, and `structuredContent` matches the declared
shape. Add a resources-side contract test that asserts
`resources/templates/list` advertises all four v2 URI schemes (`chunk://`,
`graph-entity://`, `job://`, `file://`) and that `resources/read` returns
well-formed payloads for each. Layer 1 (in-process) coverage of the same 16
tools is also extended via the existing `tests/test_each_tool.py` parametrize
matrix.

## Acceptance Criteria

- [ ] `agent-brain-mcp/tests/contract/test_tools_contract.py` parametrizes a `(tool_name, sample_arguments, expected_shape)` matrix with **16 happy-path entries** (one per tool) and **16 negative-arg entries** (one per tool, exercising the input-schema rejection path). Each happy-path entry asserts:
  - Tool is listed in `tools/list`.
  - `inputSchema` validates `sample_arguments` (use `jsonschema.validate`).
  - `tools/call` returns `result.content[0]` of type `TextContent`.
  - `result.structuredContent` is a dict and validates against `outputSchema` when declared.
- [ ] Each negative-arg entry asserts `tools/call` returns an MCP error code matching §6.3 of the v1 design doc (typically `-32602 InvalidParams`).
- [ ] `agent-brain-mcp/tests/contract/test_resources_contract.py` asserts:
  - `resources/templates/list` returns exactly four templates with uriTemplate prefixes `chunk://`, `graph-entity://`, `job://`, `file://`.
  - `resources/list` returns at least the v1 five static resources (`corpus://config|status|health|providers|folders`).
  - `resources/read` against one URI per template (using fake-backed test data) returns a well-formed `contents[0]` payload with the URI echoed back.
- [ ] `agent-brain-mcp/tests/test_each_tool.py` parametrize matrix is extended from 7 → 16 entries — Layer 1 tests cover the same 16 tools via the in-process `fake_httpx_client`.
- [ ] `task mcp:test` runs the Layer 1 suite green in <30s.
- [ ] `task mcp:contract` runs Plans 01 + 02 contract suites green in <60s.
- [ ] `task mcp:pr-qa-gate` passes with `--cov-fail-under=80` after both Layer 1 and Layer 2 test additions.

## Files to Touch

| File | Action | Notes |
|------|--------|-------|
| `agent-brain-mcp/tests/contract/test_tools_contract.py` | create | Parametrized 16-tool happy-path + 16-tool negative-arg matrix over stdio session |
| `agent-brain-mcp/tests/contract/test_resources_contract.py` | create | `resources/list`, `resources/templates/list`, `resources/read` happy-path assertions |
| `agent-brain-mcp/tests/contract/_tool_matrix.py` | create | Single source of truth for the 16-tool matrix (`TOOLS: list[ToolCase]`) — imported by both `test_tools_contract.py` (Layer 2) and `test_each_tool.py` (Layer 1) |
| `agent-brain-mcp/tests/test_each_tool.py` | modify | Replace hardcoded 7-tool list with `from tests.contract._tool_matrix import TOOLS` and parametrize over all 16 |
| `agent-brain-mcp/tests/conftest.py` | modify | If `_DEFAULT_RESPONSES` is missing any path that a new tool's happy-path test hits, extend it (should be covered by Plan 01 but verify) |

## Implementation Steps

1. Read `agent-brain-mcp/tests/test_each_tool.py` lines 30-60 to confirm the existing parametrize idiom and `_call_tool` helper signatures — copy them verbatim into the Layer 2 test.
2. Read Phase 54's tool schemas (from `54-CONTEXT.md` or the tool source files) to build the 16-entry matrix. Each `ToolCase` needs:
   - `name: str` (e.g. `"explain_result"`)
   - `sample_arguments: dict` (a valid invocation per the tool's `inputSchema`)
   - `negative_arguments: dict` (invalid — missing required field or wrong type)
   - `expected_structured_keys: list[str]` (keys that must appear in `structuredContent`)
   - `expected_error_code: int` (default `-32602` for invalid params)
3. Write `tests/contract/_tool_matrix.py`:
   ```python
   from dataclasses import dataclass
   @dataclass(frozen=True)
   class ToolCase:
       name: str
       sample_arguments: dict
       negative_arguments: dict
       expected_structured_keys: tuple[str, ...]
       expected_error_code: int = -32602
   TOOLS: list[ToolCase] = [
       # v1 (7): search_documents, query_count, server_health, index_folder, get_job, list_jobs, cancel_job
       ToolCase(name="search_documents", sample_arguments={"query": "x", "limit": 5}, ...),
       # ... 6 more v1 entries
       # v2 (9): explain_result, add_documents, inject_documents, wait_for_job, list_folders, remove_folder, cache_status, clear_cache, list_file_types
       ToolCase(name="explain_result", sample_arguments={"result_id": "fixture-id"}, ...),
       # ... 8 more v2 entries
   ]
   ```
4. Write `tests/contract/test_tools_contract.py`:
   - `@pytest.mark.contract @pytest.mark.asyncio @pytest.mark.parametrize("case", TOOLS, ids=lambda c: c.name)`
   - `async def test_tool_happy_path(mcp_stdio_session, case): ...` — initialize, list_tools, find `case.name`, `jsonschema.validate(case.sample_arguments, tool.inputSchema)`, call_tool, assert content shape + `structuredContent` keys.
   - `async def test_tool_negative_args(mcp_stdio_session, case): ...` — call_tool with `case.negative_arguments`, assert an error result with `case.expected_error_code`.
5. Write `tests/contract/test_resources_contract.py`:
   - `test_resources_templates_list` — `await session.list_resource_templates()`, assert four entries with the expected URI prefixes.
   - `test_resources_list_includes_v1_static` — assert `corpus://{config,status,health,providers,folders}` all present.
   - `test_resources_read_chunk` / `test_resources_read_graph_entity` / `test_resources_read_job` / `test_resources_read_file` — one each, against a fake-backed URI from `_DEFAULT_RESPONSES`. Assert `contents[0].uri` matches input and `contents[0].mimeType == "application/json"`.
6. Refactor `tests/test_each_tool.py` to import `TOOLS` from `tests.contract._tool_matrix` and parametrize over all 16. Delete the old hardcoded 7-tool list. Layer 1 assertions stay in-process — they just assert `_call_tool(...)` returns a dict with `case.expected_structured_keys`.
7. Run `task mcp:test` to confirm Layer 1 still green after the extension.
8. Run `task mcp:contract` to confirm Layer 2 green.
9. Run `task mcp:pr-qa-gate` to confirm coverage stays ≥80%.

## Verification

- `cd agent-brain-mcp && task test` → 16-tool Layer 1 matrix passes (was 7); coverage stable.
- `cd agent-brain-mcp && task contract` → 32 contract assertions (16 happy + 16 negative) plus 7 resource assertions all pass.
- `cd agent-brain-mcp && task pr-qa-gate` → exits 0 with `--cov-fail-under=80`.
- `cd agent-brain-mcp && poetry run pytest tests/contract/test_tools_contract.py::test_tool_happy_path -v` reports 16 tests, all passing.
- Manual: `agent-brain-mcp < scripts/mcp-smoke.jsonl | jq '.result.tools | length'` returns `16` (was 7) — proves the tool registry was extended to 16 by Phase 54 and that Phase 55 binds to that count.

## Risk Notes

- **Tool registry drift**: if Phase 54 ships with fewer than 9 new tools or renames any, this plan's 16-entry matrix breaks. The matrix lives in `_tool_matrix.py` as a single source of truth — update there and both layers re-run cleanly. Cross-check tool names against `agent_brain_mcp/tools/__init__.py::TOOL_REGISTRY` before locking the matrix.
- **`outputSchema` may not be declared on every tool**: skip the `outputSchema` validation conditionally when `tool.outputSchema is None`; the `expected_structured_keys` check still runs.
- **Negative-arg expectations**: some tools may not reject the negative input as cleanly as expected (e.g., `inject_documents` with a missing script path might 404 at the backend rather than 400 at the schema). Document any tool whose error code differs from `-32602` in the matrix's `expected_error_code` field.
- **Test ID collisions**: the `ids=lambda c: c.name` parametrize key produces clean test IDs but may collide with existing `test_each_tool.py::test_tool[search_documents]` if the same matrix runs Layer 1. Use distinct test function names or distinct module-level matrices if pytest collects both under one node ID.
- **Coverage delta**: extending tests should *raise* coverage, but if the negative-arg paths exercise error branches not previously covered (e.g., in `agent_brain_mcp/errors.py`), coverage may shift. If `--cov-fail-under=80` fails by <2pp, narrow the cause; if >2pp, file as a follow-up — do not gate Plan 02 on Phase 50–54 coverage debt.

---
*Plan 02 of Phase 55*
