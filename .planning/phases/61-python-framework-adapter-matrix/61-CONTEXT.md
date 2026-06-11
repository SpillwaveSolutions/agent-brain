# Phase 61: Python framework adapter matrix - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate `agent-brain-mcp` as an MCP server against the **5 Python LLM agent
frameworks** — OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Autogen
(AG2) — via smoke tests. Each test connects to the MCP server, calls the
`search_documents` tool, and asserts a non-empty result list. OpenAI Agents SDK
additionally connects via BOTH `MCPServerStdio` AND `MCPServerStreamableHttp`.
SDK versions are pinned to control churn. A new `framework-matrix/` directory is
created by this phase (does not exist yet).

Out of scope: TypeScript frameworks (Phase 62), the operator-facing task target
+ nightly CI workflow + `docs/INTEGRATIONS.md` (Phase 63), v9.6 runtime parity,
and any wizard/install-experience work.

</domain>

<decisions>
## Implementation Decisions

### Dependency isolation — per-framework venvs
- Each of the 5 frameworks gets its **own isolated virtual environment** with its
  own pinned requirements, NOT a single shared `framework-matrix/requirements.txt`.
- Rationale: LangChain, LlamaIndex, Pydantic AI, Autogen, and OpenAI Agents SDK
  have heavy, frequently-conflicting transitive dep trees (pydantic, httpx,
  openai version skew). A single resolved env is fragile and lets one framework's
  churn break the entire matrix. Per-framework venvs isolate the blast radius.
- Each venv pins its SDK + the relevant MCP adapter with a comment noting the
  source URL and pin date. Running a framework's suite must produce **no** `pip
  install` upgrade messages (success criterion #3).
- Layout: `framework-matrix/<framework>/` per framework, each with its own
  requirements/pin file and smoke test. Planner decides exact dir/file names and
  whether to drive venv creation via a Taskfile target or a bootstrap script.

### CI gating — opt-in + nightly advisory (NOT in before-push)
- The framework matrix does **NOT** run in `task before-push` or the PR gate.
- It runs via an **opt-in Taskfile target** (operator-invoked) plus a **nightly
  advisory CI workflow** (the actual task target + workflow land in Phase 63;
  Phase 61 just must not wire itself into the gating path).
- Rationale: 5 external SDKs churn independently; gating PRs on them couples our
  green build to upstream release breakage and network availability. Mirrors the
  Phase 60 stress-test opt-in precedent (`task mcp:stress:orphan-test`, never in
  before-push).

### Test depth — MCP-adapter layer only, keyless (no LLM agent loop)
- Each smoke test drives the framework's **MCP client primitive** to connect →
  list tools → call `search_documents` → assert non-empty results. It does NOT
  run a full `agent.run()` LLM loop.
- Therefore the tests need **no LLM API keys** and run **offline** (the only live
  dependency is the spawned `agent-brain-serve` + `agent-brain-mcp` against a
  local fixture corpus). This is what makes the nightly CI workflow feasible
  without secrets.
- Rationale: the success criteria is a connectivity/contract proof of OUR MCP
  server through each framework's adapter — not a test of the framework's model.
  A full agent loop would be flaky, non-deterministic, key-gated, and would
  mostly exercise the LLM, not `agent-brain-mcp`.
- Per-framework adapter primitives (from REQUIREMENTS.md FRAME-01..05):
  - **FRAME-01** OpenAI Agents SDK — `MCPServerStdio` AND `MCPServerStreamableHttp`
  - **FRAME-02** LangChain — `langchain-mcp-adapters`
  - **FRAME-03** LlamaIndex — `llama-index-tools-mcp`
  - **FRAME-04** Pydantic AI — `MCPServerStdio`
  - **FRAME-05** Autogen / AG2 — `McpWorkbench`

### Subprocess hygiene — inherit the Phase 60 contract
- Every test reaches the MCP server through the hygienic stdio path established
  in Phase 60 (`McpStdioBackend._hygienic_stdio_client` / `close()` —
  SIGTERM→SIGKILL escalation, no orphans). For frameworks that own their own
  stdio spawn (e.g. OpenAI Agents `MCPServerStdio`), the test must still
  guarantee deterministic tear-down so zero orphan subprocesses survive between
  frameworks (success criterion #4: each test <30s in isolation).

### Claude's Discretion
- Exact `framework-matrix/` directory + file naming and venv-bootstrap mechanism
  (Taskfile target vs script).
- Whether to share one `agent-brain-serve` + corpus fixture across all 5 framework
  tests (reusing the Phase-4/e2e `tiny_corpus` harness) or spawn per-framework.
- Pin-freshness check mechanism (how "no pip upgrade messages" is asserted).
- HTTP-transport spin-up reuse for the OpenAI Agents `MCPServerStreamableHttp` leg.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope & requirements
- `.planning/ROADMAP.md` § "Phase 61: Python framework adapter matrix" — goal, success criteria, depends-on
- `.planning/REQUIREMENTS.md` — FRAME-01 through FRAME-05 (per-framework adapter + library)

### MCP v3 design
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` — v3 design doc (CLI-via-MCP + framework matrix scope)
- `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` — v3 roadmap doc (framework matrix positioning)

### Subprocess hygiene contract (Phase 60 — MUST inherit)
- `agent-brain-mcp/agent_brain_mcp/client.py` — `McpStdioBackend._hygienic_stdio_client`, `close()` (per-call spawn + SIGTERM→SIGKILL, orphan registration)
- `.planning/phases/60-subprocess-hygiene-1000-invocation-orphan-test/` — hygiene contract plans/summaries
- `agent-brain-mcp/tests/stress/test_orphan_subprocess.py` — orphan-free assertion pattern (psutil children delta)

### Existing test harness to mirror
- `agent-brain-mcp/tests/e2e/conftest.py` — spawns real `agent-brain-serve` against a fixture corpus, connects via MCP SDK over stdio; `short_state_dir` fixture (AF_UNIX-safe /tmp path)
- `agent-brain-mcp/tests/e2e/fixtures/tiny_corpus/` — minimal indexable corpus
- `agent-brain-mcp/tests/e2e/test_e2e_index_and_query.py` — index-then-query e2e reference
- `agent-brain-mcp/agent_brain_mcp/tools/search.py` — `search_documents` tool (the integration target)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `McpStdioBackend` (`agent-brain-mcp/agent_brain_mcp/client.py`): the hygienic
  stdio entry point — framework tests that don't own their spawn should route
  through it; those that do (OpenAI Agents `MCPServerStdio`) must replicate its
  tear-down guarantee.
- `tests/e2e/conftest.py` `short_state_dir` + `tiny_corpus` fixtures: a ready
  pattern for spinning a local server + indexed corpus the framework adapters can
  query for non-empty results.
- HTTP transport (`McpHttpBackend` / `agent-brain-mcp --transport http`,
  loopback-only) for the OpenAI Agents `MCPServerStreamableHttp` leg.

### Established Patterns
- Opt-in heavy tests live behind a dedicated Taskfile target and pytest marker,
  never in `before-push` (Phase 60 `stress` marker precedent).
- Loopback-only, no-silent-fallback transport discipline (Phases 57-59).

### Integration Points
- New top-level `framework-matrix/` directory (created this phase).
- Integration target is the live `search_documents` MCP tool over stdio (+ HTTP
  for FRAME-01).

</code_context>

<specifics>
## Specific Ideas

- Smoke = connectivity/contract proof: connect → call `search_documents` → assert
  non-empty list. Nothing deeper. Keep each test <30s and orphan-free.
- "No pip upgrade messages" is an explicit acceptance signal that pins are
  exact and the venv is pre-resolved.

</specifics>

<deferred>
## Deferred Ideas

- **v9.6.0 Runtime Parity fold-in — DECLINED (kept deferred).** Headless
  execution verification for external agent CLIs stays its own parked track, NOT
  folded into v10.3. Scope now reduced to **Codex + OpenCode only** (Gemini CLI
  is end-of-life — see below). Phase 56 explicitly parked this decision for this
  discuss-phase; decision recorded: keep deferred.
- **Drop Gemini CLI runtime support (separate cleanup task, not Phase 61).**
  Gemini CLI is EOL. Remove the `gemini` runtime from `agent-brain install-agent`
  and scrub Gemini from plugin/skill/docs. Own small task/phase — tracked, not in
  this phase.
- **Setup-experience audit (own phase, not Phase 61).** The config wizard
  (`agent-brain-cli/agent_brain_cli/commands/config.py`) and `install-agent`
  predate the MCP transport + API-key auth flow (~2 mcp/auth references in the
  wizard). Audit + update for: seamless MCP transport config, API-key auth setup,
  and the upgrade migration path. NOTE: **OAuth is NOT shipped** — it is MCP v4 /
  #188 / v10.4 (only a `v4 (OAUTH-01)` placeholder in `http.py`); the shipped
  auth is API-key/RFC-6750 Bearer. Backwards-compat for the auth change exists
  (v1 `X-API-Key`/`AGENT_BRAIN_API_KEY` honored through a deprecation window;
  `config_migrate.py`/`migration.py` infra present); the one breaking edge is a
  **non-loopback** bind now refusing to boot without `API_KEY` or
  `INSECURE_NO_AUTH=true`.

</deferred>

---

*Phase: 61-python-framework-adapter-matrix*
*Context gathered: 2026-06-11*
