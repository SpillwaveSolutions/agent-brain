---
roadmap: mcp-v3
status: planned
source_design: docs/plans/2026-05-28-mcp-uds-transport-design.md
milestone: MCP v3 (CLI-via-MCP + frameworks)
---

# MCP v3 — CLI speaks MCP + framework integration matrix

> Issue body for `gh issue create --body-file docs/roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md`.
> See plan `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v3 row) and §15.2.

## Context

v1 shipped CLI HTTP/UDS. v2 added MCP subscriptions / deferred resources / Streamable HTTP. v3 makes the CLI a reference MCP client and validates the MCP server against the major LLM agent frameworks.

## Scope

### CLI-via-MCP

- New `McpStdioBackend` and `McpHttpBackend` in `agent_brain_mcp/client.py` satisfying the same shape `DocServeClient` exposes.
- CLI gains `--transport mcp` and `--mcp-transport stdio|http`.
- CLI gains `agent-brain prompt <name>` for `prompts/get` expansion.
- CLI gains `agent-brain resources list` and `agent-brain resources read <uri>`.
- CLI auto-discovers a running MCP HTTP server via new `<state_dir>/mcp.runtime.json`.
- New CLI helper `agent-brain mcp start` that runs `agent-brain-mcp --transport http` and writes `mcp.runtime.json`.

### Framework integration matrix

Adapter smoke tests against each:

- **OpenAI Agents SDK** (Python) — `MCPServerStdio` / `MCPServerStreamableHttp`
- **LangChain** — `langchain-mcp-adapters`
- **LlamaIndex** — `llama-index-tools-mcp`
- **Pydantic AI** — `MCPServerStdio`
- **Mastra** (TypeScript) — `@mastra/mcp`
- **Vercel AI SDK** (TypeScript) — `experimental_createMCPClient`
- **Autogen / AG2** — `McpWorkbench`
- Optional config recipes only: Goose, Continue.dev, Cline, Cursor, Cody

### New tooling

- New `task mcp:framework-matrix` (slow, opt-in, nightly CI).
- New `docs/INTEGRATIONS.md` — one short page per framework with copy-pasteable config.

## Prerequisites

- v2 shipped (resources + prompts are what makes CLI-via-MCP interesting).
- v2 packages folded into root QA gate.

## Definition of done

- Own design doc filed.
- `agent-brain --transport mcp query "X"` produces byte-identical results to `--transport uds` (modulo timing).
- All 6 Python frameworks pass `search_documents` smoke against the MCP server.
- `docs/INTEGRATIONS.md` shipped.
- MCP stdio subprocess hygiene verified: pinned cwd, sanitized env (allowlist), SIGTERM/SIGKILL escalation, no orphans confirmed by a 1000-invocation `pgrep` test.

## Design doc

Surgical v3 design — locks BackendClient Protocol, backend class boundaries, runtime discovery model, and sync-facade decision. Reviewers challenge the wire shape here BEFORE any MCP-layer code lands (v2 Phase 50 precedent).

- [`docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md`](../../plans/2026-06-05-mcp-v3-cli-via-mcp.md) — v3 design doc (filed 2026-06-05, Plan 56-01)

## Source design

`docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 (v3 row), §15.2.
