# Plan: Agent Brain MCP Server User Guide

## Context

The MCP server (`agent-brain-mcp`, PyPI distribution `agent-brain-ag-mcp`) shipped in v10.1.0 (Phase 4 of the MCP/UDS rollout) and currently has only ~90 lines of user-facing documentation embedded in `docs/USER_GUIDE.md` (lines 1021–1110) plus a 37-line `agent-brain-mcp/README.md`. The MCP roadmap meta-doc (`docs/roadmaps/mcp/README.md`) and the design doc (`docs/plans/2026-05-28-mcp-uds-transport-design.md`) are internal-facing.

A symmetric `docs/PLUGIN_GUIDE.md` already exists for the slash-command plugin. The MCP server has no equivalent dedicated user guide — users arriving via PyPI, Claude Desktop, Cursor, or an MCP-capable agent framework have no single doc that answers "what is this, how do I configure it, what verbs does it expose, when do I use it instead of the plugin?".

This plan creates `docs/MCP_USER_GUIDE.md` as a comprehensive standalone guide, then trims the existing USER_GUIDE.md MCP section to a short cross-link so we don't fork content. The package README gets a minor pointer update.

The guide must answer (from the user's request):
1. What verbs (tools) are available
2. How to configure (per client)
3. When to use MCP vs the plugin
4. How to use the MCP server end-to-end
5. What features it provides

## Approach

Single canonical user guide at `docs/MCP_USER_GUIDE.md`, modeled on the structure of `docs/PLUGIN_GUIDE.md`, with reference tables drawn from the existing USER_GUIDE.md MCP section as the spine. Worked examples and the MCP-vs-plugin decision matrix are new material. No source code changes — documentation only.

### Outline of `docs/MCP_USER_GUIDE.md`

1. **What is the MCP server?** — One-paragraph definition: thin MCP/stdio adapter over the existing FastAPI backend; 7 tools + 5 resources + 6 prompts; ships as PyPI package `agent-brain-ag-mcp`; console script `agent-brain-mcp`.
2. **MCP vs the plugin — when to use which** — Decision matrix. Plugin = Claude Code/OpenCode/Gemini CLI slash-commands (CLI-shell pattern). MCP = Claude Desktop, Cursor, Windsurf, Claude Agent SDK, LangChain DeepAgents, and any MCP-aware agent framework. Both target the same backend; you can run both side-by-side.
3. **Features at a glance** — Bullet list: 5 retrieval modes via `mode` param, structured-output tool responses (`outputSchema`-typed), corpus state resources (no LLM call needed to read config/status/folders/health/providers), opinionated multi-step prompts, UDS-or-HTTP backend transport, version-compat startup check, JSON-RPC error mapping with custom `-32000..-32003` codes.
4. **Installation** — `pip install agent-brain-ag-mcp` (resolves console script `agent-brain-mcp`). Note: requires a running `agent-brain-server` (install with `pip install agent-brain-rag agent-brain-cli`, then `agent-brain init && agent-brain start`).
5. **Configuration** — One subsection per client, each showing the stdio config and explaining the env vars:
   - **Claude Desktop** — `claude_desktop_config.json` snippet with `command`, `args`, `env` (location varies by OS).
   - **Cursor / Windsurf / generic IDE** — Generic stdio JSON snippet usable in any MCP-aware editor.
   - **Claude Agent SDK** — Anthropic's `claude-agent-sdk` Python/TS snippet: register `agent-brain-mcp` as an `mcpServers` entry when constructing an Agent, call tools through the SDK's tool-use interface.
   - **LangChain DeepAgents** — Snippet using LangChain's MCP client adapter (`langchain-mcp-adapters` or DeepAgent's MCP loader) to load tools from the `agent-brain-mcp` stdio process and pass them to a DeepAgent.
   - **(Preview)** — One short paragraph: v3 roadmap covers first-party adapters for OpenAI Agents SDK, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, Autogen. Link to `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md`.
6. **CLI flags + environment variables** — Table of all flags from `agent_brain_mcp/cli.py` (`--backend`, `--backend-url`, `--state-dir`) and env vars from `agent_brain_mcp/config.py` (`AGENT_BRAIN_MCP_BACKEND`, `AGENT_BRAIN_MCP_BACKEND_URL`, `AGENT_BRAIN_URL`, `AGENT_BRAIN_UDS_PATH`, `AGENT_BRAIN_STATE_DIR`), with precedence rules.
7. **Tool reference (7 tools)** — Expand the existing 7-row table from USER_GUIDE.md into one subsection per tool. For each: purpose, input schema (full field list with types, defaults, constraints — pulled from `agent_brain_mcp/schemas.py`), output schema, REST endpoint it wraps, MCP annotations (readOnly / destructive / openWorld), example call (inline-rendered as MCP JSON-RPC), and a one-line "use when" hint.
8. **Resource reference (5 resources)** — One row per `corpus://` URI: what's inside, when to read it, JSON shape (link to mirrored REST endpoint for full schema), and a worked example showing the MCP `resources/read` request and a representative response payload.
9. **Prompt reference (6 prompts)** — One subsection per prompt: arguments, the tool/resource sequence the prompt orchestrates, a worked example showing the rendered prompt messages and what the model is asked to do, and a "use when" hint.
10. **End-to-end worked examples** — Three short narratives, each ~15-20 lines, with tool-call JSON:
    - **Index a folder and poll the job** — `index_folder` → loop on `get_job` until `status: completed`.
    - **Search and explain results** — `search_documents` with `mode: hybrid`, `explain: true`, then read `corpus://config` to interpret the scoring.
    - **Onboard to a new codebase** — Invoke the `onboard-to-codebase` prompt; show how it reads `corpus://config`, `corpus://folders`, and runs a multi-mode search under the hood.
11. **Error handling** — Reuse the existing HTTP→MCP error mapping table; add a paragraph on the version-compat startup check (server refuses to start if backend `version` is below `MIN_BACKEND_VERSION`) and what to do when that fires.
12. **Cancellation** — Reuse the existing cancellation paragraph (one paragraph: `notifications/cancelled` propagates, handlers wake within ~1s).
13. **Troubleshooting** — Specific failure modes:
    - "Server fails to start with version-floor error" → upgrade `agent-brain-rag`/`agent-brain-server` to match `MIN_BACKEND_VERSION`.
    - "Connection refused" → backend not running; run `agent-brain start`.
    - "Backend Unavailable (-32001)" → UDS socket missing or backend died; switch to `--backend http` to bypass UDS.
    - "Backend Timeout (-32003)" on long indexing jobs → expected for big folders; use `get_job` to poll (v2 will add `wait_for_job`).
    - "Tool not found" in client → confirm the client picked up the new `mcpServers` entry (restart the client after config change).
14. **What's not in v1, what's coming** — Reuse the existing "deferred" list from USER_GUIDE.md and link `docs/roadmaps/mcp/v2-…`, `v3-…`, `v4-…` for the per-version scope.
15. **Related docs** — Cross-links to `PLUGIN_GUIDE.md`, `USER_GUIDE.md`, `API_REFERENCE.md`, `CONFIGURATION.md`, and the design/roadmap docs.

### Files to modify

| File | Change |
|---|---|
| `docs/MCP_USER_GUIDE.md` | **Create** new file (the outline above; estimated 600–800 lines including JSON examples). |
| `docs/USER_GUIDE.md` (lines 1021–1110) | **Replace** the existing "Using Agent Brain via MCP" section with a ~15-line summary that links to `MCP_USER_GUIDE.md`. Keep the Claude Desktop snippet inline so casual readers still see one config example without leaving the page. |
| `agent-brain-mcp/README.md` | **Minor edit**: update the "Status" line (which still says "Phase 0 scaffold (10.0.7)" even though v1 shipped in 10.1.0) and add a "Full guide" pointer to `docs/MCP_USER_GUIDE.md`. Keep the quick config snippet for PyPI/GitHub package-page viewers. |
| `docs/plans/2026-05-30-mcp-user-guide.md` | **Create** a copy of this plan in the repo's plans directory (per `CLAUDE.md`: "after any planning step, save the plan to `docs/plans/<name>.md` before doing work"). |

### Sources to draw from (existing material to reuse, not re-derive)

- **Tool/resource/prompt tables** — Already correct in `docs/USER_GUIDE.md` lines 1043–1078; expand with schema detail.
- **Error mapping table** — `docs/USER_GUIDE.md` lines 1082–1093 (verbatim).
- **Cancellation paragraph** — `docs/USER_GUIDE.md` line 1097 (verbatim).
- **Input/output schemas** — Read from `agent-brain-mcp/agent_brain_mcp/schemas.py` lines 35–158 (every model is annotated; copy field-by-field).
- **CLI flags** — `agent-brain-mcp/agent_brain_mcp/cli.py` lines 1–56.
- **Env-var resolution chain** — `agent-brain-mcp/agent_brain_mcp/config.py` lines 1–155.
- **Tool→REST mapping** — `agent-brain-mcp/agent_brain_mcp/client.py` lines 1–125 (one method per tool).
- **Prompt orchestration logic** — `agent-brain-mcp/agent_brain_mcp/prompts/*.py` (each file is one prompt and is self-contained; the tool sequence it asks the model to follow is in the messages it returns).
- **Plugin install + commands** (for the "MCP vs plugin" section) — `agent-brain-plugin/README.md` and `agent-brain-cli/agent_brain_cli/commands/`.
- **v2/v3/v4 deferred items** — `docs/roadmaps/mcp/v{2,3,4}-*.md`.

### Sources to fetch fresh (not in training data)

- **Claude Agent SDK MCP server registration** — Use `ctx7` to resolve and pull docs for `claude-agent-sdk` (Anthropic's Python/TS SDK). The exact `mcpServers` API on Agent construction may have changed.
- **LangChain DeepAgents MCP loader** — Use `ctx7` to resolve `deepagents` (or `langchain-mcp-adapters`) and pull the current MCP-tool-loading snippet.

The fetched snippets go straight into §5 (Configuration). Don't paraphrase APIs from memory.

## Verification

Documentation-only change, no code execution needed for correctness. Verify by:

1. **Render check** — Preview `docs/MCP_USER_GUIDE.md` in a Markdown viewer (or `gh` web view after push) and confirm every code block, table, and cross-link renders cleanly.
2. **Link check** — All internal cross-links (`./PLUGIN_GUIDE.md`, `./USER_GUIDE.md`, `./API_REFERENCE.md`, `./roadmaps/mcp/*.md`, `../agent-brain-mcp/agent_brain_mcp/*.py`) resolve to real files. Run `grep -oE '\]\([^)]+\)' docs/MCP_USER_GUIDE.md | sort -u` and spot-check each path with `ls`.
3. **Tool/resource/prompt parity** — Diff the new tool table against the registry in `agent-brain-mcp/agent_brain_mcp/tools/__init__.py` lines 76–150, resources against `resources/corpus.py` lines 62–108, and prompts against `prompts/__init__.py` lines 20–27. Counts must match (7 / 5 / 6) and names must be byte-exact.
4. **Schema parity** — Spot-check 2–3 tool input schemas in the guide against the matching Pydantic models in `agent_brain_mcp/schemas.py`. Default values and constraints (e.g. `top_k: int = 10 (1-100)`) must match the model definitions.
5. **Worked-example smoke test** — Run the two non-destructive worked examples against a live local backend to confirm the JSON-RPC requests are valid:
   ```bash
   agent-brain start          # ensure backend is up
   agent-brain-mcp --backend auto < tests/example-list-tools.jsonl
   ```
   Where `example-list-tools.jsonl` contains the `tools/list`, `resources/list`, and `prompts/list` requests from the guide. (The repo's `agent-brain-mcp/tests/test_tools_list.py` already covers this — borrow its harness pattern for an ad-hoc check.)
6. **Lint/format** — Run `task before-push` from the repo root before pushing (per `CLAUDE.md`'s mandatory rule). Even though no Python changes, the task may include doc linting (e.g. markdownlint, link checkers) that must pass.
7. **Plan-of-record** — After completion, copy this plan to `docs/plans/2026-05-30-mcp-user-guide.md` so the repo retains the planning artifact (per project convention).
