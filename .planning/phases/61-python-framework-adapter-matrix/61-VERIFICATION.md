---
phase: 61-python-framework-adapter-matrix
verified: 2026-06-11T00:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Phase 61: Python Framework Adapter Matrix Verification Report

**Phase Goal:** Validate the MCP server against the 5 Python LLM agent frameworks via smoke tests that each connect, call `search_documents`, and assert non-empty results. SDK versions pinned to control churn.
**Verified:** 2026-06-11
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | OpenAI Agents SDK connects via BOTH `MCPServerStdio` AND `MCPServerStreamableHttp`, calls `search_documents`, asserts non-empty result | VERIFIED | `openai-agents/test_openai_agents_smoke.py`: two async tests; imports `from agents.mcp import MCPServerStdio` and `MCPServerStreamableHttp`; both call `server.call_tool(SMOKE_TOOL, SMOKE_ARGS)` + `assert_non_empty_search(result)`; streamable-http test calls `http_mcp_listener()` with parens (factory pattern confirmed) |
| 2 | LangChain, LlamaIndex, Pydantic AI, and Autogen each have a smoke test connecting to `agent-brain-mcp`, calling `search_documents`, asserting non-empty | VERIFIED | All 4 test files parse cleanly, import their respective framework adapters (`MultiServerMCPClient`, `BasicMCPClient`/`McpToolSpec`, `pydantic_ai.mcp.MCPServerStdio`, `McpWorkbench`/`StdioServerParams`), surface `search_documents`, invoke it, and run `assert_non_empty_search` |
| 3 | `framework-matrix/` per-framework `requirements.txt` pins every SDK version with a `# source:` URL and `pinned: YYYY-MM-DD` comment; bootstrap enforces no-op re-install | VERIFIED | All 5 `requirements.txt` files use `==` pins (not ranges); every pinned line carries `# source: https://pypi.org/project/<pkg>/  pinned: 2026-06-11`; `bootstrap_venv.sh` re-runs pip install and greps for `^Collecting` and `^Successfully installed` to enforce no-op, exiting 3 on drift |
| 4 | Tests are opt-in (`@pytest.mark.framework`, excluded from `task before-push`); teardown wired SIGTERM→SIGKILL; orphan-guard in conftest.py | VERIFIED | `pytest.ini` registers `framework:` marker with `addopts = -m framework`; no package `pyproject.toml` or `Taskfile.yml` references `framework-matrix`; `conftest.py` uses `SIGTERM`→`proc.wait(grace)`→`proc.kill()` (SIGKILL) for both `seeded_mcp_server` and `http_mcp_listener` teardown — SIGINT is intentionally absent; `_orphan_guard` session-autouse fixture calls `assert_no_orphans` |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `framework-matrix/conftest.py` | Session-scoped `seeded_mcp_server` + `http_mcp_listener` factory + auto-marker hook + orphan guard | VERIFIED | 490 lines (min 120); real `agent-brain-serve` spawn with `start_seeded_server`; `http_mcp_listener` factory yields callable; `pytest_collection_modifyitems` auto-tags; `_orphan_guard` autouse; SIGTERM→SIGKILL throughout; no cross-package imports |
| `framework-matrix/_harness.py` | `FRAMEWORK_CORPUS`, `SMOKE_QUERY`, `SMOKE_TOOL`, `SMOKE_ARGS`, `stdio_server_params`, `assert_non_empty_search` (5 shapes), `assert_no_orphans` | VERIFIED | 395 lines (min 60); all exports present; corpus has 4 files with literal `authenticate` in content; `_count()` dispatches all 5 framework result shapes (structuredContent, content-list, str, list, ToolResult.result); all shapes pass unit test |
| `framework-matrix/bootstrap_venv.sh` | Venv creation + exact-pin freshness check | VERIFIED | 120 lines (min 30); executable; `git rev-parse --show-toplevel` fallback; pin-freshness re-install with `^Collecting` and `^Successfully installed` detection; exit 3 on drift |
| `framework-matrix/pytest.ini` | `framework:` marker + `addopts = -m framework` | VERIFIED | `framework:` marker description references `before-push`; `addopts = -m framework` present; `asyncio_mode = auto` set |
| `framework-matrix/openai-agents/requirements.txt` | `openai-agents==` exact pin with source+date | VERIFIED | `openai-agents==0.17.5` + `mcp==1.27.2`; source URL + `pinned: 2026-06-11` on each line |
| `framework-matrix/openai-agents/test_openai_agents_smoke.py` | Two tests — stdio + streamable-http legs | VERIFIED | 135 lines (min 70); `test_stdio_search_returns_results` + `test_streamable_http_search_returns_results`; `http_mcp_listener()` called with parens on line 121 |
| `framework-matrix/langchain/requirements.txt` | `langchain-mcp-adapters==` exact pin | VERIFIED | `langchain-mcp-adapters==0.3.0`; source+date on each line |
| `framework-matrix/langchain/test_langchain_smoke.py` | One framework test with non-empty assert | VERIFIED | 84 lines (min 40); `MultiServerMCPClient`; `search_documents` in tool list; `ainvoke` + `assert_non_empty_search` |
| `framework-matrix/llama-index/requirements.txt` | `llama-index-tools-mcp==` exact pin | VERIFIED | `llama-index-tools-mcp==0.4.8`; source+date on each line |
| `framework-matrix/llama-index/test_llama_index_smoke.py` | One framework test with non-empty assert | VERIFIED | 85 lines (min 40); `BasicMCPClient` + `McpToolSpec`; `to_tool_list_async()`; `acall(**SMOKE_ARGS)` + `assert_non_empty_search` |
| `framework-matrix/pydantic-ai/requirements.txt` | `pydantic-ai==` exact pin | VERIFIED | `pydantic-ai==1.107.0` (exact `==`, not a range); source+date |
| `framework-matrix/pydantic-ai/test_pydantic_ai_smoke.py` | One framework test with non-empty assert | VERIFIED | 76 lines (min 40); `pydantic_ai.mcp.MCPServerStdio`; `list_tools()` + `call_tool` + `assert_non_empty_search` |
| `framework-matrix/autogen/requirements.txt` | `autogen-ext[mcp]==` exact pin | VERIFIED | `autogen-ext[mcp]==0.7.5` + `autogen-core==0.7.5`; source+date; README notes Microsoft fork vs AG2 fork |
| `framework-matrix/autogen/test_autogen_smoke.py` | One framework test with non-empty assert | VERIFIED | 85 lines (min 40); `McpWorkbench` + `StdioServerParams` from `autogen_ext.tools.mcp`; `list_tools()` + `call_tool` + `assert_non_empty_search` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `conftest.py` | `agent-brain-serve` binary | `Popen(["agent-brain-serve"])` + UDS env + poll `/health/status` | WIRED | Lines 215–272; exact mirror of `_corpus.py:start_seeded_server` pattern |
| `conftest.py` | `agent-brain-mcp --transport http` | `_start_http_listener()` Popen + GET `/healthz` poll | WIRED | Lines 326–402; `"--transport", "http"` arg at line 351; `/healthz` polled at line 369 |
| `openai-agents/test_openai_agents_smoke.py` | `MCPServerStdio` + `MCPServerStreamableHttp` | `async with server:` → `list_tools()` → `call_tool` → `assert_non_empty_search` | WIRED | Both transports import and use directly; `http_mcp_listener()` called with parens (line 121) to start real binary |
| `openai-agents/test_openai_agents_smoke.py` | `conftest.py:seeded_mcp_server` + `http_mcp_listener` | Fixture injection | WIRED | `seeded_mcp_server: Path` arg in stdio test; `http_mcp_listener: Callable[[], str]` in HTTP test |
| `langchain/test_langchain_smoke.py` | `langchain_mcp_adapters.client.MultiServerMCPClient` | `async with client:` → `get_tools()` → `ainvoke` | WIRED | Import + context manager + tool invocation + `assert_non_empty_search` |
| `llama-index/test_llama_index_smoke.py` | `llama_index.tools.mcp.BasicMCPClient` + `McpToolSpec` | `to_tool_list_async()` → `acall(**SMOKE_ARGS)` | WIRED | Import + tool-list fetch + direct call + `assert_non_empty_search` |
| `pydantic-ai/test_pydantic_ai_smoke.py` | `pydantic_ai.mcp.MCPServerStdio` | `async with server:` → `list_tools()` → `call_tool` | WIRED | Import + context manager + `assert_non_empty_search` |
| `autogen/test_autogen_smoke.py` | `autogen_ext.tools.mcp.McpWorkbench` + `StdioServerParams` | `async with McpWorkbench(server_params=params) as wb:` → `list_tools()` → `call_tool` | WIRED | Import + context manager + `assert_non_empty_search` |
| `conftest.py` teardown | SIGTERM→SIGKILL | `proc.send_signal(signal.SIGTERM)` → `proc.wait(grace)` → `proc.kill()` on `TimeoutExpired` | WIRED | Pattern present for both `start_seeded_server` (lines 266–270) and `_stop_http_listener` (lines 413–419); SIGINT absent |
| `conftest.py:_orphan_guard` | `_harness.assert_no_orphans` | Session-autouse fixture snapshots child PIDs at start, calls `assert_no_orphans` at teardown | WIRED | Lines 279–289; `baseline = _children_pids(self_pid)` → `yield` → `assert_no_orphans(self_pid, baseline)` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FRAME-01 | 61-01, 61-02 | OpenAI Agents SDK — `MCPServerStdio` + `MCPServerStreamableHttp` | SATISFIED | Two test functions; both transport imports present; HTTP leg starts real binary via `http_mcp_listener()` factory |
| FRAME-02 | 61-03 | LangChain adapter smoke test via `langchain-mcp-adapters` | SATISFIED | `test_langchain_smoke.py` uses `MultiServerMCPClient`; `langchain-mcp-adapters==0.3.0` pinned |
| FRAME-03 | 61-03 | LlamaIndex adapter smoke test via `llama-index-tools-mcp` | SATISFIED | `test_llama_index_smoke.py` uses `BasicMCPClient` + `McpToolSpec`; `llama-index-tools-mcp==0.4.8` pinned |
| FRAME-04 | 61-04 | Pydantic AI adapter smoke test via `MCPServerStdio` | SATISFIED | `test_pydantic_ai_smoke.py` uses `pydantic_ai.mcp.MCPServerStdio`; `pydantic-ai==1.107.0` exact-pinned |
| FRAME-05 | 61-04 | Autogen / AG2 adapter smoke test via `McpWorkbench` | SATISFIED | `test_autogen_smoke.py` uses `autogen_ext.tools.mcp.McpWorkbench`; `autogen-ext[mcp]==0.7.5` pinned; README clarifies Microsoft vs AG2 fork |

All 5 requirement IDs from plan frontmatter (`FRAME-01..05`) are accounted for. REQUIREMENTS.md marks all 5 as `Complete | Phase 61`. No orphaned requirements found.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `_harness.py` | 97 | `return []` | Info | This is the `search()` function body inside the `query_service.py` string value of `FRAMEWORK_CORPUS` — it is corpus text, not implementation code. Not a stub. |

No blockers. No warnings. The `return []` is inside a Python source code string used as corpus content for seeding the test index — it is intentional and correct.

### Human Verification Required

The following items cannot be verified programmatically (no venvs are installed for framework SDKs):

#### 1. OpenAI Agents MCPServerStdio live execution

**Test:** `sh framework-matrix/bootstrap_venv.sh openai-agents` then run `framework-matrix/openai-agents/.venv/bin/pytest framework-matrix/openai-agents/ -m framework -v` with `OPENAI_API_KEY` set.
**Expected:** Both `test_stdio_search_returns_results` and `test_streamable_http_search_returns_results` pass in <30s each with no orphan subprocesses.
**Why human:** Cannot install framework venvs during automated verification; test requires a live OpenAI API key and running binaries.

#### 2. LangChain live execution

**Test:** `sh framework-matrix/bootstrap_venv.sh langchain` then `framework-matrix/langchain/.venv/bin/pytest framework-matrix/langchain/ -m framework -v` with `OPENAI_API_KEY` set.
**Expected:** `test_langchain_search_returns_results` passes in <30s with >=1 result.
**Why human:** Same venv + API key constraint.

#### 3. LlamaIndex live execution

**Test:** `sh framework-matrix/bootstrap_venv.sh llama-index` then `framework-matrix/llama-index/.venv/bin/pytest framework-matrix/llama-index/ -m framework -v` with `OPENAI_API_KEY` set.
**Expected:** `test_llama_index_search_returns_results` passes in <30s.
**Why human:** Same constraint.

#### 4. Pydantic AI live execution

**Test:** `sh framework-matrix/bootstrap_venv.sh pydantic-ai` then `framework-matrix/pydantic-ai/.venv/bin/pytest framework-matrix/pydantic-ai/ -m framework -v` with `OPENAI_API_KEY` set.
**Expected:** `test_pydantic_ai_search_returns_results` passes in <30s.
**Why human:** Same constraint.

#### 5. Autogen/AG2 live execution

**Test:** `sh framework-matrix/bootstrap_venv.sh autogen` then `framework-matrix/autogen/.venv/bin/pytest framework-matrix/autogen/ -m framework -v` with `OPENAI_API_KEY` set.
**Expected:** `test_autogen_search_returns_results` passes in <30s.
**Why human:** Same constraint.

#### 6. Bootstrap pin-freshness enforcement

**Test:** For each framework, run `bootstrap_venv.sh` twice and verify the second run exits 0 with no `Collecting` or `Successfully installed` lines in the log.
**Expected:** Exit code 0, log contains only `Requirement already satisfied` lines.
**Why human:** Requires actual pip install into real venvs.

#### 7. `task before-push` framework test exclusion confirmation

**Test:** Confirm that `task before-push` from repo root (544 passed, 111 deselected) does not collect any tests from `framework-matrix/`.
**Expected:** Framework tests do not appear in the before-push run output.
**Why human:** Already confirmed by orchestrator (544 passed, 111 deselected); documented here for completeness.

---

## Summary

All automated checks pass. The phase deliverables are complete and substantive:

- **Harness skeleton (Plan 61-01):** `conftest.py` (490 lines) provides a real session-scoped `seeded_mcp_server` that actually spawns `agent-brain-serve`, seeds the corpus, and polls until indexed — it is not a stub. The `http_mcp_listener` factory starts the real `agent-brain-mcp --transport http` binary and polls `/healthz`. SIGTERM→SIGKILL teardown is correctly wired throughout (SIGINT absent). The `_orphan_guard` session-autouse fixture is wired to `assert_no_orphans`. `_harness.py` exports all required symbols and correctly normalizes all 5 framework result shapes (confirmed by unit test).

- **FRAME-01 OpenAI Agents (Plan 61-02):** Two test functions covering both transports. The streamable-HTTP leg calls `http_mcp_listener()` with parens (line 121), proving the factory pattern is used correctly. Both tests wire through to `assert_non_empty_search`.

- **FRAME-02..05 (Plans 61-03, 61-04):** Each framework has a single substantive test (40–85 lines) using its native MCP adapter, correctly consuming `seeded_mcp_server` and running `assert_non_empty_search`. All `requirements.txt` files use exact `==` pins (no ranges) with `# source:` URL and `pinned: 2026-06-11` comments on every line.

- **Opt-in isolation:** `pytest.ini` with `addopts = -m framework` and no reference to `framework-matrix/` in any package `pyproject.toml` or `Taskfile.yml` ensures the suite is entirely absent from `task before-push`. This was independently confirmed by the orchestrator (544 passed, 111 deselected).

- **Requirements:** All 5 FRAME-01..05 IDs from plan frontmatter are implemented. REQUIREMENTS.md marks all 5 as `Complete | Phase 61`. No orphaned requirements.

The phase goal is achieved at the code/structure level. Live execution verification (which requires installed framework venvs and an OpenAI API key) is deferred to human verification per the stated context.

---

_Verified: 2026-06-11_
_Verifier: Claude (gsd-verifier)_
