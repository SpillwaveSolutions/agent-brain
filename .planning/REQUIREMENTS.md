# Requirements: Agent Brain v10.3 — MCP v3 (CLI-via-MCP + Framework Matrix)

**Defined:** 2026-06-05
**Core Value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API that understands code structure and relationships
**Milestone source:** Issue [#187](https://github.com/SpillwaveSolutions/agent-brain/issues/187) · Spec `docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md` · Master design `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v3 row), §15.2
**Prereqs (already shipped):** v10.2 — Streamable HTTP transport (`agent-brain-mcp --transport http`), 16-tool MCP surface, resource subscriptions, 4 URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`), root QA gate integration.

## v1 Requirements (this milestone)

Requirements for v10.3. Each maps to a roadmap phase.

### Design

- [x] **DESIGN-V3-01**: v3 design doc filed at `docs/plans/2026-06-<dd>-mcp-v3-cli-via-mcp.md` covering CLI backend abstraction, runtime discovery, and framework matrix scope before MCP-layer code lands.

### CLI-via-MCP Backend Clients

- [x] **CLI-MCP-01**: New `McpStdioBackend` in `agent_brain_mcp/client.py` (or `agent_brain_cli/client/mcp_backend.py`) satisfying the same shape `DocServeClient` exposes today (query, list_folders, etc.) — caller cannot distinguish via the interface.
- [x] **CLI-MCP-02**: New `McpHttpBackend` parallel to `McpStdioBackend` but driving `streamablehttp_client` against a live `agent-brain-mcp --transport http` listener.
- [x] **CLI-MCP-03**: `agent-brain --transport mcp` selector + `--mcp-transport stdio|http` sub-selector wired into the CLI; explicit selection, no silent fallback (mirrors v10.2 HTTP-03).
- [x] **CLI-MCP-04**: `agent-brain --transport mcp query "X"` returns byte-identical results to `--transport uds` for the same backend state (modulo timestamps/elapsed) — the v3 DoD anchor.

### CLI Surface for Prompts + Resources

- [x] **CLI-MCP-05**: `agent-brain prompt <name>` command that calls MCP `prompts/get` and prints the expanded prompt content (all 6 v1 prompts: `audit_indexed_folders`, `compare_search_modes`, `explain_architecture`, `find_callers`, `find_implementation`, `onboard_to_codebase`).
- [x] **CLI-MCP-06**: `agent-brain resources list` enumerates the 5 static URIs + 4 templated URI schemes (`chunk://`, `graph-entity://`, `job://`, `file://`).
- [x] **CLI-MCP-07**: `agent-brain resources read <uri>` calls MCP `resources/read` and prints content; respects `file://` sandbox; correct content-type handling for binary blobs vs JSON.

### Runtime Discovery & Helper

- [x] **CLI-MCP-08**: `<state_dir>/mcp.runtime.json` written by `agent-brain mcp start`, read by CLI when `--transport mcp --mcp-transport http` is set without an explicit `--mcp-url`. Schema matches `runtime.json` style (host, port, pid, started_at, transport).
- [x] **CLI-MCP-09**: `agent-brain mcp start` helper that launches `agent-brain-mcp --transport http` as a background process with loopback bind, port auto-allocation, and `mcp.runtime.json` write on listener-ready (uses the same psutil socket-bind verification path as v10.2 HTTP-02).
- [x] **CLI-MCP-10**: `agent-brain mcp stop` companion command that reads `mcp.runtime.json`, sends SIGTERM, escalates to SIGKILL after grace period, removes `mcp.runtime.json` on clean exit.

### Subprocess Hygiene

- [x] **MCPHYG-01**: MCP stdio subprocess hygiene — pinned cwd (no `cwd=None` inheritance), env sanitized to allowlist (drop `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`/etc. unless explicitly forwarded), SIGTERM → SIGKILL escalation with configurable grace period.
- [x] **MCPHYG-02**: 1000-invocation no-orphan pgrep test — drive `McpStdioBackend` through 1000 query→close cycles in a tight loop, assert `pgrep -f agent-brain-mcp` returns no surviving PIDs after each tear-down. Gated behind `task mcp:stress:orphan-test` (opt-in, slow).

### Framework Adapter Matrix

Python frameworks (smoke tests in `agent-brain-cli/tests/framework_matrix/` or new `framework-matrix/` top-level dir):

- [x] **FRAME-01**: OpenAI Agents SDK adapter smoke test — `MCPServerStdio` + `MCPServerStreamableHttp` connect to `agent-brain-mcp`, call `search_documents`, assert non-empty results.
- [x] **FRAME-02**: LangChain adapter smoke test via `langchain-mcp-adapters`.
- [x] **FRAME-03**: LlamaIndex adapter smoke test via `llama-index-tools-mcp`.
- [ ] **FRAME-04**: Pydantic AI adapter smoke test via `MCPServerStdio`.
- [ ] **FRAME-05**: Autogen / AG2 adapter smoke test via `McpWorkbench`.

TypeScript frameworks (separate test harness, likely under `framework-matrix/ts/`):

- [ ] **FRAME-06**: Mastra adapter smoke test via `@mastra/mcp`.
- [ ] **FRAME-07**: Vercel AI SDK adapter smoke test via `experimental_createMCPClient`.

### Tooling + Docs

- [ ] **TOOLING-V3-01**: `task mcp:framework-matrix` Taskfile target — slow, opt-in, gated behind a `FRAMEWORK_MATRIX=1` env or explicit `--force` flag. Runs all 7 framework smoke tests sequentially with per-framework setup/teardown.
- [ ] **TOOLING-V3-02**: Nightly CI workflow (`.github/workflows/framework-matrix.yml`) running `task mcp:framework-matrix` against `main`; failure does NOT block PRs (advisory only — framework drift is expected).
- [ ] **DOCS-V3-01**: `docs/INTEGRATIONS.md` — one short page per framework with copy-pasteable config (server command, transport, capabilities). Includes the 5 optional-config-only frameworks (Goose, Continue.dev, Cline, Cursor, Cody) as a separate "config recipes" section without smoke tests.

## v2 Requirements (deferred to future milestone)

Deferred capabilities tracked but not in current scope.

### Optional Framework Recipes (config-only, no smoke test in v10.3)

- **FRAME-OPT-01..05**: Recipe-only entries for Goose, Continue.dev, Cline, Cursor, Cody. Live in `docs/INTEGRATIONS.md` as text-only configs in v10.3 (covered by DOCS-V3-01); reach smoke-test parity in a future milestone if/when adoption justifies it.

### Held for v10.4 (OAuth 2.1, issue #188)

- **OAUTH-01..N**: OAuth 2.1 for the Streamable HTTP transport (PRM, DCR, Resource Indicators, optional DPoP). Strictly depends on v10.3's `McpHttpBackend`.

### Optional v9.6.0 Runtime Parity Phases (open scope question)

- **RUNTIME-PARITY-47/48/49**: Headless project-local install + execution verification for Codex / OpenCode / Gemini. Deferred from v9.6.0 with explicit "re-evaluate during MCP v3" note. **Decision lives in `/gsd:discuss-phase`**: fold into v10.3 as a parallel track (framework matrix already exercises external CLIs) OR defer to v10.4+.

## Out of Scope

Explicit exclusions to prevent scope creep.

| Feature | Reason |
|---------|--------|
| OAuth 2.1 for HTTP transport | v10.4 territory (#188); v10.3 stays loopback-only |
| MCP sampling / completion | Advanced LLM-in-the-server pattern; not required for tool/resource/subscription completeness |
| MCP plugin auto-registration | Requires manifest design; deferred |
| Smoke tests for the 5 optional config-only frameworks (Goose, Continue, Cline, Cursor, Cody) | Editor-side integrations vary too quickly; docs-only in v10.3 |
| Multi-tenant MCP HTTP server | Local-first philosophy — one instance per project |
| Web UI for MCP debugging | CLI-first philosophy — `agent-brain mcp` subcommands cover the surface |
| Renaming `agent-brain` CLI commands to match MCP tool names | Backwards-compat for v1/v2 CLI users; `--transport mcp` is additive, not a rename |

## Traceability

Which phases cover which requirements. Filled by roadmap creation 2026-06-05.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DESIGN-V3-01 | Phase 56 | Complete |
| CLI-MCP-01 | Phase 56 | Complete |
| CLI-MCP-02 | Phase 56 | Complete |
| CLI-MCP-03 | Phase 57 | Complete (selector + dispatcher + 3 §3.5 cases in Plan 57-01; query() wiring + CLI-MCP-04 DoD anchor in Plan 57-02; remaining 10 BackendClient methods + verbatim reset() on both backends in Plan 57-03) |
| CLI-MCP-04 | Phase 57 | Complete |
| CLI-MCP-05 | Phase 59 | Complete |
| CLI-MCP-06 | Phase 59 | Complete |
| CLI-MCP-07 | Phase 59 | Complete |
| CLI-MCP-08 | Phase 58 | Complete (Plan 58-01 helpers + Plan 58-02 start writes runtime + Plan 58-03 McpHttpBackend.__init__ + resolve_mcp_transport discovery end-to-end) |
| CLI-MCP-09 | Phase 58 | Complete |
| CLI-MCP-10 | Phase 58 | Complete |
| MCPHYG-01 | Phase 60 | Complete |
| MCPHYG-02 | Phase 60 | Complete |
| FRAME-01 | Phase 61 | Complete |
| FRAME-02 | Phase 61 | Complete |
| FRAME-03 | Phase 61 | Complete |
| FRAME-04 | Phase 61 | Pending |
| FRAME-05 | Phase 61 | Pending |
| FRAME-06 | Phase 62 | Pending |
| FRAME-07 | Phase 62 | Pending |
| TOOLING-V3-01 | Phase 63 | Pending |
| TOOLING-V3-02 | Phase 63 | Pending |
| DOCS-V3-01 | Phase 63 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23 (Phases 56-63)
- Unmapped: 0

---
*Requirements defined: 2026-06-05*
*Last updated: 2026-06-05 — Traceability updated by roadmapper. 23/23 mapped across Phases 56-63 (Phase 56: 3 / Phase 57: 2 / Phase 58: 3 / Phase 59: 3 / Phase 60: 2 / Phase 61: 5 / Phase 62: 2 / Phase 63: 3). No orphans, no duplicates.*
