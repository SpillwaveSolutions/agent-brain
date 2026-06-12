/**
 * FRAME-06: Mastra @mastra/mcp smoke test.
 *
 * Connects to agent-brain-mcp over stdio via MCPClient, lists tools, calls
 * search_documents with SMOKE_ARGS, and asserts a non-empty result list.
 *
 * Keyless: no OPENAI/ANTHROPIC key required by the MCP tool call itself.
 * OPENAI_API_KEY is only needed by agent-brain-serve to seed the corpus;
 * if missing, globalSetup skips seeding and this test skips gracefully.
 *
 * Resolved API shape (ctx7 / @mastra/mcp 1.9.1):
 *   - new MCPClient({ id, servers: { name: { command, args, env } } })
 *   - await client.listToolsets() → Record<serverName, Record<toolName, Tool>>
 *   - await tool.execute?.({ ...args }, {}) → unknown result envelope
 *   - await client.disconnect() — teardown
 *
 * Canonical sources:
 *   - framework-matrix/openai-agents/test_openai_agents_smoke.py
 *   - .planning/phases/62-typescript-framework-adapter-matrix/62-CONTEXT.md (FRAME-06)
 */

import { beforeAll, afterAll, it, expect } from "vitest";
import { MCPClient } from "@mastra/mcp";

import {
  SMOKE_TOOL,
  SMOKE_ARGS,
  assertNonEmptySearch,
} from "../src/corpus.js";
import { stdioServerParams, prerequisitesAvailable } from "../src/harness.js";
import { stage } from "../src/fingerprint.js";

const SERVER_NAME = "agentBrain";

let client: MCPClient | null = null;
let skipReason: string | null = null;

beforeAll(async () => {
  // Check global handoff from globalSetup — set once per pnpm test run.
  const stateDir = process.env["AB_FWM_STATE_DIR"];
  if (!stateDir) {
    skipReason =
      "AB_FWM_STATE_DIR not set — globalSetup did not seed the server " +
      "(OPENAI_API_KEY or binaries missing). Skipping FRAME-06 Mastra test.";
    return;
  }

  const { ok, reason } = prerequisitesAvailable();
  if (!ok) {
    skipReason = reason;
    return;
  }

  const { command, args, env } = stdioServerParams(stateDir);

  // connect stage: construct MCPClient with stdio server entry and connect.
  client = await stage("mastra", "connect",() => {
    return new MCPClient({
      id: "frame-06-mastra-smoke",
      servers: {
        [SERVER_NAME]: { command, args, env },
      },
    });
  });
});

afterAll(async () => {
  if (client !== null) {
    await stage("mastra", "disconnect",async () => {
      await client!.disconnect();
      client = null;
    });
  }
});

it("FRAME-06: Mastra MCPClient connects, lists tools, calls search_documents, asserts non-empty", async () => {
  if (skipReason !== null) {
    // Graceful skip — prerequisites absent or server not seeded.
    console.log(`[mastra] SKIPPED: ${skipReason}`);
    return;
  }

  expect(client).not.toBeNull();

  // list-tools stage: fetch toolsets (grouped by server, not namespaced).
  const toolsets = await stage("mastra", "list-tools",async () => {
    const ts = await client!.listToolsets();
    const serverTools = ts[SERVER_NAME];
    if (!serverTools) {
      throw new Error(
        `Server "${SERVER_NAME}" not found in toolsets. Available: ${Object.keys(ts).join(", ")}`,
      );
    }
    if (!(SMOKE_TOOL in serverTools)) {
      throw new Error(
        `"${SMOKE_TOOL}" not found. Available tools: ${Object.keys(serverTools).join(", ")}`,
      );
    }
    return ts;
  });

  // call stage: invoke search_documents via tool.execute.
  // NOTE: MCP tools from listToolsets() use a CoreTool-compatible execute
  // signature. The second argument (invocation options) is optional in
  // practice — the underlying MCP dispatch only requires the tool arguments.
  // We cast to avoid importing @mastra/core internals in a smoke test.
  const result = await stage("mastra", "call",async () => {
    const serverTools = toolsets[SERVER_NAME]!;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const tool = serverTools[SMOKE_TOOL] as unknown as { execute?: (args: unknown, opts: unknown) => Promise<unknown> };
    return await tool.execute?.(SMOKE_ARGS, {});
  });

  // assert stage: validate non-empty result via shared 5-shape normalizer.
  stage("mastra", "assert", () => assertNonEmptySearch(result));
});
