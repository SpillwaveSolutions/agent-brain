# Framework Matrix — Phase 61/62 Python Framework Adapter Tests

This directory contains the **Phase 61/62 Python LLM framework adapter matrix**: a
suite of smoke tests that validate `agent-brain-mcp` as an MCP server against the
five major Python LLM agent frameworks.

## What is this?

Each test connects to a live `agent-brain-mcp` server, calls the `search_documents`
tool, and asserts a non-empty result list. This is a **connectivity/contract proof**
of our MCP server through each framework's adapter — not a test of the framework's
LLM model. No LLM API keys are required.

## Tests are OPT-IN (NOT in `task before-push`)

The framework tests do **NOT** run in `task before-push` or the PR gate. They are
opt-in: driven by an explicit `pytest -m framework framework-matrix/` invocation.
The Taskfile operator target and nightly CI workflow land in **Phase 63** — this
phase ships the harness and tests only.

Never include `framework-matrix/` in any package's `testpaths` or default `addopts`.

## Per-Framework Isolated Venvs

Each framework lives in its own subdirectory with its **own isolated virtual
environment** and **pinned `requirements.txt`**. This isolation prevents transitive
dependency conflicts between the heavy dep trees of LangChain, LlamaIndex, Pydantic
AI, Autogen, and OpenAI Agents SDK.

### Framework Subdirectories

| Directory | Framework | Adapter primitive |
|-----------|-----------|-------------------|
| `openai-agents/` | OpenAI Agents SDK | `MCPServerStdio` + `MCPServerStreamableHttp` |
| `langchain/` | LangChain | `langchain-mcp-adapters` |
| `llama-index/` | LlamaIndex | `llama-index-tools-mcp` |
| `pydantic-ai/` | Pydantic AI | `MCPServerStdio` |
| `autogen/` | Autogen (AG2) | `McpWorkbench` |

Each subdirectory contains:
- `requirements.txt` — pinned SDK + MCP adapter versions
- `.venv/` — isolated virtual environment (created by `bootstrap_venv.sh`)
- `test_<framework>_mcp.py` — the framework smoke test (added per-framework plan)

## Bootstrap a Framework Venv

```bash
# From repo root:
bash framework-matrix/bootstrap_venv.sh openai-agents
bash framework-matrix/bootstrap_venv.sh langchain
bash framework-matrix/bootstrap_venv.sh llama-index
bash framework-matrix/bootstrap_venv.sh pydantic-ai
bash framework-matrix/bootstrap_venv.sh autogen
```

The script enforces **exact pins**: after the initial install it re-runs the
requirements install and verifies it is a no-op (zero `Collecting` / `Successfully
installed` lines). Any pin drift causes an exit-3 error naming the drifted package.

## Run the Framework Tests

```bash
# Run all framework tests (requires bootstrapped venvs + OPENAI_API_KEY):
pytest -m framework framework-matrix/

# Run a single framework:
pytest -m framework framework-matrix/openai-agents/
```

Tests skip gracefully when `OPENAI_API_KEY` is missing or `agent-brain-serve` /
`agent-brain-mcp` are not on PATH.

## Architecture

- `conftest.py` — session-scoped `seeded_mcp_server` fixture (ONE shared
  `agent-brain-serve` with an indexed tiny corpus) + `http_mcp_listener` factory
  fixture for the OpenAI Agents `MCPServerStreamableHttp` leg + framework marker
  auto-tagging + orphan-guard.
- `_harness.py` — shared helpers: `FRAMEWORK_CORPUS`, `SMOKE_QUERY/TOOL/ARGS`,
  `stdio_server_params`, `assert_non_empty_search` (normalizes 5 framework result
  shapes), `assert_no_orphans`.
- `pytest.ini` — registers the `framework` marker; `addopts = -m framework` so a
  bare `pytest framework-matrix/` only runs framework-marked tests.
- `bootstrap_venv.sh` — per-framework venv creator with pin-freshness check.

## Phase Notes

- **Phase 61**: Python framework matrix (this phase) — OpenAI Agents SDK
  (`openai-agents/`), LangChain (`langchain/`), LlamaIndex (`llama-index/`),
  Pydantic AI (`pydantic-ai/`), Autogen (`autogen/`).
- **Phase 62**: TypeScript framework matrix (separate directory, TBD).
- **Phase 63**: Operator Taskfile target + nightly CI workflow.
