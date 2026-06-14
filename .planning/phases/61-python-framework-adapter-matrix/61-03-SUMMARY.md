---
phase: 61-python-framework-adapter-matrix
plan: 03
subsystem: testing
tags: [pytest, mcp, framework-matrix, langchain, langchain-mcp-adapters, llama-index, llama-index-tools-mcp, stdio, MultiServerMCPClient, BasicMCPClient, McpToolSpec]

# Dependency graph
requires:
  - phase: 61-python-framework-adapter-matrix/61-01
    provides: "framework-matrix/ harness skeleton: seeded_mcp_server, stdio_server_params, assert_non_empty_search, bootstrap_venv.sh, framework pytest marker"

provides:
  - "framework-matrix/langchain/ — FRAME-02 LangChain smoke test via langchain-mcp-adapters==0.3.0 MultiServerMCPClient stdio"
  - "framework-matrix/llama-index/ — FRAME-03 LlamaIndex smoke test via llama-index-tools-mcp==0.4.8 BasicMCPClient + McpToolSpec stdio"
  - "Both SDKs pinned with source URL + pin-date comments in isolated per-framework requirements files"
  - "Both tests: @pytest.mark.framework, keyless, <30s, orphan-free, skip gracefully without OPENAI_API_KEY"

affects:
  - 61-04 (pydantic-ai + autogen tests — same harness shape)
  - 63-xx (operator task target + nightly CI workflow — consumes all framework-matrix dirs)

# Tech tracking
tech-stack:
  added:
    - "langchain-mcp-adapters==0.3.0 (MultiServerMCPClient stdio transport)"
    - "langchain-core==1.4.6 (minimal dep for langchain-mcp-adapters; no model/agent extras)"
    - "llama-index-tools-mcp==0.4.8 (BasicMCPClient + McpToolSpec stdio transport)"
    - "llama-index-core==0.14.22 (minimal dep for llama-index-tools-mcp; no LLM/embedding extras)"
  patterns:
    - "MultiServerMCPClient async context manager: async with MultiServerMCPClient({'agent-brain': {'command': ..., 'args': ..., 'transport': 'stdio', 'env': ...}}) as client: tools = await client.get_tools()"
    - "LangChain direct tool invocation: search_tool.ainvoke(SMOKE_ARGS) — no LLM loop required (BaseTool.ainvoke is LLM-independent)"
    - "LlamaIndex stdio: BasicMCPClient(command, args=args, env=env) + McpToolSpec + to_tool_list_async() + tool.acall(**SMOKE_ARGS)"
    - "LlamaIndex tool name matching: exact match on t.metadata.name == SMOKE_TOOL; substring fallback if adapter prefixes names"

key-files:
  created:
    - "framework-matrix/langchain/requirements.txt"
    - "framework-matrix/langchain/test_langchain_smoke.py"
    - "framework-matrix/langchain/README.md"
    - "framework-matrix/llama-index/requirements.txt"
    - "framework-matrix/llama-index/test_llama_index_smoke.py"
    - "framework-matrix/llama-index/README.md"
  modified: []

key-decisions:
  - "LangChain adapter: MultiServerMCPClient (newer API) preferred over load_mcp_tools(session) pattern — single async context manager, no manual ClientSession management"
  - "LangChain invocation: tool.ainvoke(SMOKE_ARGS) called directly on BaseTool — works without LLM, fully keyless"
  - "LlamaIndex adapter: BasicMCPClient(command, args, env) positional first arg + named kwargs — consistent with PyPI docs stdio example"
  - "LlamaIndex tool name fallback: exact match on t.metadata.name first; substring fallback to handle any adapter name-prefix behavior"
  - "Both requirements.txt files: only minimal MCP-adapter-layer deps pinned; zero LLM/model/embedding provider extras"

patterns-established:
  - "Keyless direct-tool-invocation pattern: both adapters support calling MCP tools without any LLM/model configured — BaseTool.ainvoke (LangChain) and FunctionTool.acall (LlamaIndex) are adapter-layer only"
  - "Per-framework sys.path injection: test file inserts framework-matrix/ parent onto sys.path so _harness imports work inside isolated venvs"

requirements-completed: [FRAME-02, FRAME-03]

# Metrics
duration: 6min
completed: 2026-06-11
---

# Phase 61 Plan 03: LangChain + LlamaIndex Adapter Smoke Tests Summary

**langchain-mcp-adapters==0.3.0 MultiServerMCPClient stdio + llama-index-tools-mcp==0.4.8 BasicMCPClient/McpToolSpec smoke tests against agent-brain-mcp, both keyless direct-tool-invocation, isolated pinned venvs**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-06-11T21:45:48Z
- **Completed:** 2026-06-11T21:51:58Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 6 created, 0 modified

## Accomplishments

- Created `framework-matrix/langchain/` with pinned requirements (langchain-mcp-adapters==0.3.0, langchain-core==1.4.6, mcp==1.27.2, typing-extensions==4.15.0) and `test_langchain_smoke.py` using `MultiServerMCPClient` async context manager + `BaseTool.ainvoke(SMOKE_ARGS)` — no LLM agent loop (keyless)
- Created `framework-matrix/llama-index/` with pinned requirements (llama-index-tools-mcp==0.4.8, llama-index-core==0.14.22, mcp==1.27.2, pydantic==2.13.4) and `test_llama_index_smoke.py` using `BasicMCPClient(command, args, env)` + `McpToolSpec` + `to_tool_list_async()` + `FunctionTool.acall(**SMOKE_ARGS)` — no LLM loop (keyless)
- Both tests: `@pytest.mark.framework`, consume `seeded_mcp_server` fixture, skip gracefully without `OPENAI_API_KEY`, designed for <30s, orphan-free
- `task before-push` still passes: 544 passed, 111 deselected — framework tests remain opt-in, not collected by before-push

## Task Commits

1. **Task 1: FRAME-02 LangChain - pin langchain-mcp-adapters + stdio smoke test** - `23c9987` (feat)
2. **Task 2: FRAME-03 LlamaIndex - pin llama-index-tools-mcp + stdio smoke test** - `a7887a9` (feat)

## Files Created/Modified

- `framework-matrix/langchain/requirements.txt` - Pins langchain-mcp-adapters==0.3.0 + minimal deps; source URL + pin-date comments; no LLM extras
- `framework-matrix/langchain/test_langchain_smoke.py` - FRAME-02 smoke test: MultiServerMCPClient stdio -> get_tools -> ainvoke -> assert_non_empty_search
- `framework-matrix/langchain/README.md` - FRAME-02 description + bootstrap/run commands
- `framework-matrix/llama-index/requirements.txt` - Pins llama-index-tools-mcp==0.4.8 + minimal deps; source URL + pin-date comments; no LLM extras
- `framework-matrix/llama-index/test_llama_index_smoke.py` - FRAME-03 smoke test: BasicMCPClient + McpToolSpec + to_tool_list_async -> acall -> assert_non_empty_search
- `framework-matrix/llama-index/README.md` - FRAME-03 description + bootstrap/run commands

## Decisions Made

- **LangChain: MultiServerMCPClient async context manager** (newer API): single `async with MultiServerMCPClient({...}) as client:` block manages stdio connection lifecycle. This is cleaner than the older `load_mcp_tools(session)` pattern which requires manual `stdio_client` + `ClientSession` management.
- **LangChain invocation keyless**: `BaseTool.ainvoke(args_dict)` is callable without any LLM configured — confirmed by ctx7 docs. The test exercises the MCP adapter contract, not LangChain's agent loop.
- **LlamaIndex positional first arg**: `BasicMCPClient(command, args=args, env=env)` matches the PyPI README pattern `local_client = BasicMCPClient("python", args=["server.py"])`. The first positional arg is `command_or_url`.
- **LlamaIndex tool name fallback**: Exact match on `t.metadata.name == SMOKE_TOOL` first; substring fallback (`SMOKE_TOOL in t.metadata.name`) handles any future adapter name-prefix behavior transparently.
- **No provider extras in any requirements.txt**: Zero `langchain-openai`, `langchain-anthropic`, `llama-index-llms-*`, `llama-index-embeddings-*` packages — tests are keyless by design.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None. Both verification check suites passed on first attempt. `task before-push` exits 0 (544 passed, framework tests not collected).

## User Setup Required

None — no external service configuration required. Both tests skip gracefully when `OPENAI_API_KEY` or required binaries (`agent-brain-serve`, `agent-brain-mcp`) are absent.

## Next Phase Readiness

- All 4 per-framework tests (FRAME-02 LangChain + FRAME-03 LlamaIndex now complete; FRAME-01 OpenAI Agents in 61-02; FRAME-04 Pydantic AI + FRAME-05 Autogen in 61-04) share the same harness
- Phase 63 operator Taskfile target + nightly CI workflow can consume `framework-matrix/langchain/` and `framework-matrix/llama-index/` without additional scaffolding
- `sh framework-matrix/bootstrap_venv.sh langchain` creates the isolated venv; `framework-matrix/langchain/.venv/bin/pytest framework-matrix/langchain/ -m framework` runs the test

---
*Phase: 61-python-framework-adapter-matrix*
*Completed: 2026-06-11*
