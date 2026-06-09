# Phase 61: Python framework adapter matrix - Context

**Gathered:** 2026-06-09
**Status:** Ready for planning
**Mode:** Auto (user requested "go into auto mode and pick the best options" — recommended defaults selected per gray area, logged below)

<domain>
## Phase Boundary

Validate `agent-brain-mcp` against the 5 Python LLM agent frameworks listed in `.planning/REQUIREMENTS.md` (FRAME-01..05) via smoke tests that each connect to a fresh `agent-brain-mcp` subprocess, call the `search_documents` MCP tool, and assert a non-empty result list. SDK versions are pinned in `framework-matrix/requirements.txt` to control churn. Every test goes through `McpStdioBackend` so it inherits Phase 60's subprocess hygiene contract automatically.

**Inherited from Phase 60 (NOT re-decided):**
- Pinned `cwd` on every spawned subprocess
- Env allowlist (`PATH`, `HOME`, `USER`, `LANG`, `LC_ALL`, `TERM` + `AGENT_BRAIN_API_KEY`); never auto-forward `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`
- SIGTERM → SIGKILL escalation with 5.0s grace
- `psutil`-based orphan detection patterns available if needed

**Out of scope (NOT in this phase):**
- TypeScript frameworks (Phase 62: Mastra + Vercel AI SDK — FRAME-06, FRAME-07)
- `task mcp:framework-matrix` Taskfile target + `docs/INTEGRATIONS.md` + nightly CI workflow (Phase 63: TOOLING-V3-01, TOOLING-V3-02, DOCS-V3-01)
- v9.6.0 Runtime Parity Phases 47-49 (headless Codex/OpenCode/Gemini execution verification) — stays parked, see decision below
- Per-framework end-to-end agent workflows — smoke tests only call `search_documents`, NOT multi-turn agent reasoning
- Issue #199 v2 API auth hardening (orthogonal — separate feature branch)

</domain>

<decisions>
## Implementation Decisions

### Harness layout + dep strategy

- **Test location:** `agent-brain-mcp/tests/framework/<framework>/test_smoke.py` — one subdir per framework, keeps the test runner unified (single `pytest` invocation, single coverage report). Mirrors the existing `tests/contract/`, `tests/e2e/`, `tests/stress/` subdir pattern.
- **SDK version pinning file:** `framework-matrix/requirements.txt` at the repo root — exactly the path named in Phase 61 SC #3. Every framework SDK line carries a comment with the source URL (PyPI page) and pin date. Single file (NOT per-framework venvs) — defer per-framework isolation until dep conflicts actually surface.
- **Poetry extra:** Single `framework-matrix` extra on `agent-brain-mcp` (`poetry install -E framework-matrix`). One command gets you the whole matrix. Per-framework extras (`[langchain]`, `[llamaindex]`, etc.) are a maintenance burden — avoided.
- **Why this shape:** the roadmap explicitly allows "single requirements.txt OR per-framework venvs" — we pick the single-file lighter form. If/when a dep conflict surfaces (e.g., LangChain pinning `pydantic <2` while Pydantic-AI requires `>=2`), we revisit and split.

### Skip-on-missing + CI gating

- **Skip mechanism:** `@pytest.mark.framework_matrix` + module-level `try/except ImportError`. If `openai-agents` (or any framework SDK) isn't installed in the active venv, the entire test module is skipped — canonical pytest pattern for optional-dep tests.
- **Marker registration:** add `framework_matrix` to `[tool.pytest.ini_options].markers` in `agent-brain-mcp/pyproject.toml`.
- **Taskfile target:** new `task mcp:framework-matrix` runs `pytest -m framework_matrix` (mirrors Phase 60's `task mcp:stress:orphan-test` shape).
- **NOT in `task before-push`:** matrix is opt-in, slow (5 frameworks × subprocess spawn × SDK init), and SDK-availability-dependent. Same posture as Phase 60's stress test.
- **CI integration:** nightly-advisory workflow only (per v3 design doc §4.6 — `task mcp:framework-matrix` is "slow, opt-in, nightly CI"). Phase 63 owns the workflow file; Phase 61 just produces the tests.

### Seed corpus for search_documents

- **Mechanism:** session-scoped pytest fixture (`framework_mcp_session`) in `agent-brain-mcp/tests/framework/conftest.py`. Fixture:
  1. Spawns `agent-brain-mcp` via `McpStdioBackend` in a temporary state dir
  2. Calls the `add_documents` MCP tool with a canned text snippet (~200 words about a fictional system) so search has deterministic data
  3. Yields the backend to each framework's smoke test
  4. Teardown drops the temp state dir
- **Canned snippet content:** small, structured text where `search_documents` for a known phrase reliably returns ≥1 chunk. Picks a sentinel phrase (e.g., "agent-brain ingests documentation") that every framework smoke test queries.
- **Why this shape:** pre-indexed fixture artifacts would require maintenance + git-storage of vector DB state — fragile. Reusing `agent-brain-server/tests/` corpora crosses package boundaries. Inline `add_documents` keeps each test self-contained, fits the <30s SC, and exercises the real MCP tool surface as a bonus.
- **Cross-test isolation:** each framework smoke test gets its own session-scoped fixture invocation (NOT shared across frameworks), so a flake in one doesn't taint another. Slight cost in setup time, but framework SDK init dominates anyway.

### v9.6.0 Runtime Parity fold-in

- **Decision: KEEP PARKED.** Do NOT fold v9.6.0 Phases 47-49 (headless Codex/OpenCode/Gemini execution verification) into Phase 61.
- **Rationale:** the "external CLI exercising" overlap noted in v3 design doc §4.6 is shallow. Phase 61 smoke tests use **client SDK libraries** that speak MCP (Python imports + tool calls). v9.6 Phases 47-49 need **headless CLI subprocess invocation** with stdout assertion — different test mechanism, different failure modes, different deps. Folding would expand Phase 61 from "5 smoke tests against client SDKs" to "5 SDK tests + 3 headless-CLI verifications" and obscure both efforts.
- **Implication:** v9.6 stays parked for a focused post-v10.3 phase. The unpark decision belongs in a future `/gsd:discuss-phase` for whichever milestone picks it up.

### FRAME-01 special case (OpenAI Agents SDK — dual transport)

- **Two transport arms:** SC #1 explicitly requires FRAME-01 to test BOTH `MCPServerStdio` AND `MCPServerStreamableHttp`. The other 4 frameworks are stdio-only.
- **HTTP arm prerequisites:** `agent-brain-mcp --transport http` listener must already be running (Phase 53 work). The HTTP arm spawns `agent-brain-mcp start` via `subprocess.Popen` in the fixture, hits the loopback HTTP listener, asserts non-empty results, then `mcp stop` teardown.
- **Pattern reference:** existing tests in `agent-brain-mcp/tests/test_mcp_backend_prompts_wire.py` already use `streamablehttp_client` patches — the FRAME-01 HTTP arm uses the real listener, not patches.

### Plan structure

- **6 plans total** — 1 shared scaffolding + 5 framework smokes:
  - **61-01** — Shared fixture (`framework_mcp_session`) + corpus seed helper + `framework_matrix` pytest marker registration + Taskfile `mcp:framework-matrix` target + `framework-matrix/requirements.txt` skeleton + poetry extra
  - **61-02** — FRAME-01: OpenAI Agents SDK (stdio + HTTP — both transports)
  - **61-03** — FRAME-02: LangChain (`langchain-mcp-adapters`)
  - **61-04** — FRAME-03: LlamaIndex (`llama-index-tools-mcp`)
  - **61-05** — FRAME-04: Pydantic AI (`MCPServerStdio`)
  - **61-06** — FRAME-05: Autogen / AG2 (`McpWorkbench`)
- **Why 6 plans not 5:** shared fixture deserves its own atomic commit (won't be broken by framework SDK churn). After 61-01 lands, frameworks 02-06 can be implemented in parallel waves with no plan-to-plan coupling.

### Claude's Discretion

- Exact wording of the canned 200-word text corpus (subject just needs to be searchable with a deterministic sentinel phrase)
- Plan-to-plan execution order beyond "61-01 first" — Plans 02-06 can interleave
- Whether to add a sixth `framework_matrix_quick` marker for fast-subset runs (skip if no need surfaces in plan-phase)
- Test naming (e.g., `test_smoke.py` vs `test_<framework>_smoke.py`) — pick whichever flows cleaner during plan-phase

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner) MUST read these before planning or implementing.**

### v3 design + scope
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §1.2 — framework matrix list (the canonical 7 frameworks; Phase 61 owns the 5 Python ones)
- `docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md` §4.6 — Phase 61-62 scope deferral ("framework matrix gets its own lighter scoping doc when Phase 61 starts" — THIS file fulfills that promise)
- `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` — full v3 milestone roadmap (Phase 61 carries the framework matrix bar)

### Roadmap + requirements
- `.planning/ROADMAP.md` — Phase 61 entry with 4 SCs (specifically: SC #3 names `framework-matrix/requirements.txt` for pinning; SC #4 caps each test at <30s)
- `.planning/REQUIREMENTS.md` — FRAME-01..05 lines naming the 5 frameworks and the adapter class per framework

### Hygiene contract inherited
- `.planning/phases/60-subprocess-hygiene-1000-invocation-orphan-test/60-CONTEXT.md` — env allowlist, cwd policy, SIGTERM→SIGKILL escalation, `psutil` orphan detection. Phase 61 inherits all of these via `McpStdioBackend`.

### Pattern references
- `agent-brain-mcp/tests/test_mcp_backend_prompts_wire.py` — existing `streamablehttp_client` test patches (pattern for FRAME-01's HTTP arm, though FRAME-01 uses real listener not patches)
- `agent-brain-mcp/Taskfile.yml` — `mcp:stress:orphan-test` target (template for new `mcp:framework-matrix` target)
- `agent-brain-mcp/tests/stress/` directory + `pytest.mark.stress` registration in `pyproject.toml` (template for `framework_matrix` marker + `tests/framework/` subdir)

### v9.6.0 (referenced but explicitly NOT in scope)
- Wherever v9.6.0 Phases 47-49 are tracked — parked, see `<decisions>` "v9.6.0 Runtime Parity fold-in" above

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`McpStdioBackend`** (`agent-brain-mcp/agent_brain_mcp/`) — the canonical subprocess spawner for all framework tests. Inherits Phase 60's hygiene contract. Every framework's stdio smoke test wraps `McpStdioBackend` so subprocess lifecycle stays correct without any per-framework hygiene code.
- **`streamablehttp_client` test patterns** (`agent-brain-mcp/tests/test_mcp_backend_prompts_wire.py:23, 170, 364`) — shape reference for FRAME-01's HTTP arm (real listener, not patches).
- **`add_documents` MCP tool** — existing tool from v10.2 Phase 54. Used in the shared fixture to seed corpus.
- **`search_documents` MCP tool** — existing tool from v10.1 Phase 53/55. The single tool exercised by every framework smoke test.

### Established Patterns
- **Opt-in slow tests via marker + Taskfile target:** Phase 60's `pytest.mark.stress` + `task mcp:stress:orphan-test` + NOT in `task before-push`. Phase 61 mirrors this exactly with `pytest.mark.framework_matrix` + `task mcp:framework-matrix`.
- **Subdir-per-test-category under `agent-brain-mcp/tests/`:** existing `contract/`, `e2e/`, `stress/`, `subscriptions/`. Adding `framework/<framework>/` follows the convention.
- **Session-scoped fixtures for MCP subprocess + seeded state:** common pattern across MCP tests; new shared fixture follows the same shape.

### Integration Points
- **`agent-brain-mcp/Taskfile.yml`** — add new target `mcp:framework-matrix`
- **`agent-brain-mcp/pyproject.toml`** — register `framework_matrix` marker; add `framework-matrix` poetry extra
- **`framework-matrix/requirements.txt`** (new file at repo root) — pinned SDK versions per Phase 61 SC #3
- **`agent-brain-mcp/tests/framework/conftest.py`** (new) — shared `framework_mcp_session` fixture
- **`agent-brain-mcp/tests/framework/<framework>/`** (5 new subdirs) — one `test_smoke.py` per framework

</code_context>

<specifics>
## Specific Ideas

- **Phase 60's stress-test pattern is the explicit template.** When planner agents draft 61-01, they should literally lift the marker registration + Taskfile target shape from `agent-brain-mcp/tests/stress/` + the existing `mcp:stress:orphan-test` Taskfile entry and rename `stress` → `framework_matrix`.
- **The canned corpus snippet is small but deterministic.** Pick a sentinel phrase that every smoke test queries — e.g., "agent-brain provides semantic search across documentation." Each framework's test calls `search_documents(query="semantic search", top_k=3)` and asserts `len(results) > 0`. The exact corpus body can be 200 words of context around that sentinel.
- **FRAME-01 needs the running HTTP listener.** Its fixture is `agent-brain mcp start --transport http --port=<random>` via `McpStdioBackend`-spawned helper; teardown is `agent-brain mcp stop`. The stdio arm uses the regular `McpStdioBackend` flow.

</specifics>

<deferred>
## Deferred Ideas

- **v9.6.0 Runtime Parity Phases 47-49** — headless Codex/OpenCode/Gemini execution verification. Stays parked per decision above; pick up in a post-v10.3 phase when there's appetite for the headless-CLI test infrastructure.
- **Per-framework venvs** — kept as a fallback option if dep conflicts surface after 61-02 lands. Default is single `framework-matrix/requirements.txt`.
- **`framework_matrix_quick` marker for fast subset runs** — only add if Phase 63's tooling work surfaces a need.
- **End-to-end agent workflow tests** (multi-turn reasoning, tool chaining) — explicit non-goal for smoke tests. Could be a future phase if the framework matrix's value proposition expands beyond "they can attach and call one tool."
- **TypeScript frameworks (FRAME-06 Mastra, FRAME-07 Vercel AI SDK)** — Phase 62 scope.
- **`docs/INTEGRATIONS.md` + nightly CI workflow** — Phase 63 scope.

</deferred>

---

*Phase: 61-python-framework-adapter-matrix*
*Context gathered: 2026-06-09*
