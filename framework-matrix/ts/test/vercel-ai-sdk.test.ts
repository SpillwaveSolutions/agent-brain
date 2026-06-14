/**
 * FRAME-07: Vercel AI SDK @ai-sdk/mcp smoke test.
 *
 * Connects to agent-brain-mcp over stdio via createMCPClient (stable API;
 * also exported as experimental_createMCPClient for backward compatibility),
 * lists tools, calls search_documents with SMOKE_ARGS, and asserts a non-empty
 * result list.
 *
 * Keyless: no OPENAI/ANTHROPIC key required by the MCP tool call itself.
 * OPENAI_API_KEY is only needed by agent-brain-serve to seed the corpus;
 * if missing, globalSetup skips seeding and this test skips gracefully.
 *
 * Package deviation (62-01 carry-forward): The stable API is `createMCPClient`
 * from `@ai-sdk/mcp` (1.0.48). It is also exported as `experimental_createMCPClient`
 * from the same package for backward compat. The `ai` package is NOT installed.
 * We import `experimental_createMCPClient` from `@ai-sdk/mcp` to satisfy both
 * the requirement name and the correct package path.
 *
 * Resolved API shape (ctx7 / @ai-sdk/mcp 1.0.48):
 *   - transport: new StdioClientTransport({ command, args, env }) from
 *       @modelcontextprotocol/sdk/client/stdio.js
 *   - client = await createMCPClient({ transport }) — async factory
 *   - await client.tools() → McpToolSet (Record<toolName, McpToolBase>)
 *   - tool.execute(args, opts) — call via cast (smoke test, no LLM context)
 *   - await client.close() — teardown
 *
 * Canonical sources:
 *   - framework-matrix/openai-agents/test_openai_agents_smoke.py
 *   - .planning/phases/62-typescript-framework-adapter-matrix/62-CONTEXT.md (FRAME-07)
 *   - .planning/phases/62-typescript-framework-adapter-matrix/62-01-SUMMARY.md (deviation)
 */

import { beforeAll, afterAll, it, expect } from "vitest";
import {
  experimental_createMCPClient,
  type MCPClient,
} from "@ai-sdk/mcp";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

import {
  SMOKE_TOOL,
  SMOKE_ARGS,
  assertNonEmptySearch,
} from "../src/corpus.js";
import { stdioServerParams, prerequisitesAvailable } from "../src/harness.js";
import { stage } from "../src/fingerprint.js";

let client: MCPClient | null = null;
let skipReason: string | null = null;

beforeAll(async () => {
  // Check global handoff from globalSetup — set once per pnpm test run.
  const stateDir = process.env["AB_FWM_STATE_DIR"];
  if (!stateDir) {
    skipReason =
      "AB_FWM_STATE_DIR not set — globalSetup did not seed the server " +
      "(OPENAI_API_KEY or binaries missing). Skipping FRAME-07 Vercel AI SDK test.";
    return;
  }

  const { ok, reason } = prerequisitesAvailable();
  if (!ok) {
    skipReason = reason;
    return;
  }

  const { command, args, env } = stdioServerParams(stateDir);

  // connect stage: build StdioClientTransport + experimental_createMCPClient.
  client = await stage("vercel-ai-sdk", "connect", async () => {
    const transport = new StdioClientTransport({ command, args, env });
    return await experimental_createMCPClient({ transport });
  });
});

afterAll(async () => {
  if (client !== null) {
    await stage("vercel-ai-sdk", "disconnect", async () => {
      await client!.close();
      client = null;
    });
  }
});

it("FRAME-07: Vercel AI SDK createMCPClient connects, lists tools, calls search_documents, asserts non-empty", async () => {
  if (skipReason !== null) {
    // Graceful skip — prerequisites absent or server not seeded.
    console.log(`[vercel-ai-sdk] SKIPPED: ${skipReason}`);
    return;
  }

  expect(client).not.toBeNull();

  // list-tools stage: fetch tools from the MCP client.
  const toolMap = await stage("vercel-ai-sdk", "list-tools", async () => {
    const tools = await client!.tools();
    if (!(SMOKE_TOOL in tools)) {
      throw new Error(
        `"${SMOKE_TOOL}" not found. Available tools: ${Object.keys(tools).join(", ")}`,
      );
    }
    return tools;
  });

  // call stage: invoke search_documents via tool.execute.
  // NOTE: McpToolBase.execute takes (input, ToolExecutionOptions). In a smoke
  // test context we only need the MCP call, not the full LLM context.
  // Cast to bypass the strict ToolExecutionOptions requirement.
  const result = await stage("vercel-ai-sdk", "call", async () => {
    const tool = toolMap[SMOKE_TOOL] as unknown as {
      execute: (args: unknown, opts: unknown) => Promise<unknown>;
    };
    return await tool.execute(SMOKE_ARGS, {});
  });

  // assert stage: validate non-empty result via shared 5-shape normalizer.
  stage("vercel-ai-sdk", "assert", () => assertNonEmptySearch(result));
});
