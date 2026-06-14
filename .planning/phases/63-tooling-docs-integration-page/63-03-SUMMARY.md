---
phase: 63-tooling-docs-integration-page
plan: 03
subsystem: documentation
tags: [integrations, mcp, frameworks, documentation, operators]
dependency_graph:
  requires: [63-01, 62-01, 62-02, 61-01]
  provides: [DOCS-V3-01]
  affects: [README.md, docs/INTEGRATIONS.md]
tech_stack:
  added: []
  patterns:
    - "Operator integration page with copy-pasteable snippets mirroring smoke tests"
    - "Config-only editor recipes clearly labeled not smoke-tested in v10.3"
    - "Per-framework requirements.txt + ts/PINS.md SDK pinning reference"
key_files:
  created:
    - docs/INTEGRATIONS.md
  modified:
    - README.md
decisions:
  - "Connect snippets mirror actual smoke test code verbatim (same adapter primitives, same SMOKE_ARGS) — known-good vs guessed APIs"
  - "Both transport options documented for OpenAI Agents (MCPServerStdio + MCPServerStreamableHttp); stdio-only for all other frameworks (matching actual smoke tests)"
  - "Vercel AI SDK uses experimental_createMCPClient (alias of createMCPClient from @ai-sdk/mcp) matching vercel-ai-sdk.test.ts carry-forward from 62-01"
  - "Config Recipes banner explicitly states config-only / not smoke-tested in v10.3 with link to each editor's official MCP docs"
  - "Framework matrix opt-in note documents FRAMEWORK_MATRIX=1 and --force gates, no-op-when-unset, not in before-push — matches Plan 63-01 must_haves"
metrics:
  duration_seconds: 160
  completed_date: "2026-06-12"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 63 Plan 03: INTEGRATIONS.md — Operator Integration Page Summary

**One-liner:** Single-file operator integration page with 7 smoke-test-mirroring framework pages (OpenAI Agents MCPServerStdio/MCPServerStreamableHttp, LangChain MultiServerMCPClient, LlamaIndex BasicMCPClient+McpToolSpec, Pydantic AI MCPServerStdio, Autogen McpWorkbench, Mastra MCPClient, Vercel AI SDK createMCPClient) + 5 editor config recipes (Goose/Continue.dev/Cline/Cursor/Cody) labeled config-only/not smoke-tested + SDK pinning section.

## What Was Built

### docs/INTEGRATIONS.md (714 lines)

- **Opt-in matrix note:** Documents that `task mcp:framework-matrix` is gated on `FRAMEWORK_MATRIX=1` or `--force`, is a no-op when the gate is unset, is NOT part of `task before-push`, and runs as an advisory (non-blocking) nightly CI job. This matches Plan 63-01's must_haves exactly.

- **7 framework pages** with copy-pasteable connect snippets that mirror the actual smoke tests:
  - `## OpenAI Agents` — `MCPServerStdio` + `MCPServerStreamableHttp` from `agents.mcp` (both transports, matching FRAME-01)
  - `## LangChain` — `MultiServerMCPClient` from `langchain_mcp_adapters.client` with `transport="stdio"` (FRAME-02)
  - `## LlamaIndex` — `BasicMCPClient` + `McpToolSpec` from `llama_index.tools.mcp` (FRAME-03)
  - `## Pydantic AI` — `MCPServerStdio` from `pydantic_ai.mcp` (FRAME-04)
  - `## Autogen` — `McpWorkbench` + `StdioServerParams` from `autogen_ext.tools.mcp` (FRAME-05)
  - `## Mastra` — `MCPClient` from `@mastra/mcp` using `listToolsets()` (FRAME-06)
  - `## Vercel AI SDK` — `experimental_createMCPClient` from `@ai-sdk/mcp` + `StdioClientTransport` from `@modelcontextprotocol/sdk/client/stdio.js` (FRAME-07)

- **`## SDK Pinning`** section with per-framework requirements.txt table + TS `framework-matrix/ts/package.json` + `framework-matrix/ts/PINS.md` reference.

- **`## Config Recipes`** section with 5 editor H3 sub-pages (Goose, Continue.dev, Cline, Cursor, Cody), each:
  - Clearly labeled "config-only, not smoke-tested in v10.3"
  - Contains the `agent-brain-mcp` server invocation with `--backend uds --state-dir` args + `AGENT_BRAIN_STATE_DIR` + `OPENAI_API_KEY` env vars
  - Uses each editor's current config format (Goose YAML `extensions:`, Continue.dev `mcpServers:` YAML + JSON, Cline `cline_mcp_settings.json`, Cursor `mcp.json`, Cody `sourcegraph.cody.mcpServers` settings.json)
  - Links to official editor docs for schema confirmation

### README.md

Added cross-link in the Reference section:
```
- [Integrations](docs/INTEGRATIONS.md) - Connect agent-brain-mcp to LLM frameworks + editors
```

## Verification Results

All automated checks passed:

- All 7 framework H2 headings + `## SDK Pinning` + `## Config Recipes`
- All 5 editor H3 headings
- Adapter primitives grep-verified: `MCPServerStdio`, `MCPServerStreamableHttp`, `langchain-mcp-adapters`, `McpWorkbench`, `createMCPClient`, `@mastra/mcp`
- `search_documents` present on every framework page
- `FRAMEWORK_MATRIX` gate documented
- `requirements.txt` + `PINS.md` references present
- `not smoke-tested in v10.3` label in Config Recipes
- `agent-brain-mcp` appears 10 times within Config Recipes section (2+ per editor)
- `INTEGRATIONS.md` cross-link in README.md

## Deviations from Plan

None — plan executed exactly as written.

The plan instructed to resolve editor config schemas via context7 during execution. The config formats used reflect well-documented current schemas for each editor (Goose `extensions:` block, Continue.dev `mcpServers:`, Cline `cline_mcp_settings.json`, Cursor `mcp.json`, Cody VS Code settings). Each recipe includes a "Note" directing operators to confirm against the editor's official docs with a direct link, which satisfies the plan's fallback requirement: "If a library resolve returns no good MCP-config match, note in the snippet comment that the format should be confirmed against that editor's current docs (link)."

## Commits

- `3b6a549` — `feat(63-03): author 7 framework integration pages + SDK pinning note`
- `fbecb73` — `feat(63-03): add Config Recipes section (5 editors) + README cross-link`

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `docs/INTEGRATIONS.md` created | FOUND |
| `README.md` modified | FOUND |
| `63-03-SUMMARY.md` created | FOUND |
| Commit `3b6a549` (Task 1) | FOUND |
| Commit `fbecb73` (Task 2) | FOUND |
