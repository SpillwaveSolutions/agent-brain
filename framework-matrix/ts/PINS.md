# Dependency Pins — framework-matrix/ts

All dependencies are exact-pinned (no `^` or `~` ranges) following the Phase 61
`requirements.txt`-discipline precedent. Each entry records: package, version,
source URL, and pin date.

## devDependencies

| Package | Version | Source URL | Notes |
|---------|---------|-----------|-------|
| `typescript` | `6.0.3` | https://www.npmjs.com/package/typescript/v/6.0.3 | pinned: 2026-06-11 |
| `vitest` | `4.1.8` | https://www.npmjs.com/package/vitest/v/4.1.8 | pinned: 2026-06-11 |
| `@types/node` | `25.9.3` | https://www.npmjs.com/package/@types/node/v/25.9.3 | pinned: 2026-06-11 |

## dependencies

| Package | Version | Source URL | Notes |
|---------|---------|-----------|-------|
| `@mastra/mcp` | `1.9.1` | https://www.npmjs.com/package/@mastra/mcp/v/1.9.1 | pinned: 2026-06-11; Mastra MCP client (FRAME-06) |
| `@ai-sdk/mcp` | `1.0.48` | https://www.npmjs.com/package/@ai-sdk/mcp/v/1.0.48 | pinned: 2026-06-11; Vercel AI SDK MCP client — exports `createMCPClient` + `Experimental_StdioMCPTransport` (FRAME-07) |
| `@modelcontextprotocol/sdk` | `1.29.0` | https://www.npmjs.com/package/@modelcontextprotocol/sdk/v/1.29.0 | pinned: 2026-06-11; MCP SDK (transport base for both adapters) |
| `zod` | `4.4.3` | https://www.npmjs.com/package/zod/v/4.4.3 | pinned: 2026-06-11; peer dep of @ai-sdk/mcp |

## Resolution Method

All versions resolved on 2026-06-11 via `npm view <pkg> version` (latest at resolution time).

## AI SDK Note

The plan referenced `experimental_createMCPClient` from the `ai` package, which was the
pre-v1.0 beta name. The current stable API (`@ai-sdk/mcp@1.0.48`) exports `createMCPClient`
(stable, no `experimental_` prefix) from `@ai-sdk/mcp`, and `Experimental_StdioMCPTransport`
from `@ai-sdk/mcp/mcp-stdio`. Plan 62-02 will use the stable `createMCPClient` export.
