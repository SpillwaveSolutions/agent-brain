---
roadmap: mcp-meta
status: shipped (v1) / planned (v2–v4)
source_design: docs/plans/2026-05-28-mcp-uds-transport-design.md
---

# MCP roadmap

> Meta-issue body for `gh issue create --body-file docs/roadmaps/mcp/README.md` (the title is "MCP roadmap meta-issue (v2 / v3 / v4 tracking)").
> See plan `docs/plans/2026-05-28-mcp-uds-transport-design.md` §11 and §15.4.

## Source design

`docs/plans/2026-05-28-mcp-uds-transport-design.md`

## v1 (this release — 10.1.0)

Shipped per the plan above. UDS transport + 7-tool / 5-resource / 6-prompt stdio MCP server + CLI HTTP/UDS dual transport.

## Roadmap

- [ ] **MCP v2** — Resource subscriptions + the 2 deferred URI schemes + Streamable HTTP + 9 remaining tools. Body: [v2-subscriptions-and-resources.md](v2-subscriptions-and-resources.md).
- [ ] **MCP v3** — CLI-via-MCP + framework integration matrix (OpenAI Agents SDK, LangChain, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, Autogen). Body: [v3-cli-via-mcp-and-frameworks.md](v3-cli-via-mcp-and-frameworks.md).
- [ ] **MCP v4** — OAuth 2.1 for remote Agent Brain instances (Protected Resource Metadata, Dynamic Client Registration, Resource Indicators, DPoP optional). Body: [v4-oauth-for-remote.md](v4-oauth-for-remote.md).

Each phase requires its own design doc before implementation lands. Phase order is hard:

- **v3 depends on v2's HTTP transport.** No `McpHttpBackend` in v3 without Streamable HTTP in v2.
- **v4 depends on v3's `McpHttpBackend`.** OAuth lives on the HTTP transport; stdio is local-trust by definition.

## How to file these issues

The three roadmap bodies (`v2-*.md`, `v3-*.md`, `v4-*.md`) and this meta-body are formatted to be passed directly to `gh issue create --body-file`. Suggested titles + labels are in plan §15.

When filing, link the meta-issue back to the three sub-issues using the issue numbers GitHub assigns (e.g., update the checkbox lines above to `- [ ] #123 MCP v2 — …`).
