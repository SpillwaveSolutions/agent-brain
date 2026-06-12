# Agent Brain MCP — Integrations

`agent-brain-mcp` is an MCP server that exposes semantic codebase and
documentation search to any MCP-compatible LLM framework or editor.
The connect snippets in this page **mirror the smoke tests** in
`framework-matrix/` so they are known-good against the pinned SDK versions.

## Opt-in test matrix

`task mcp:framework-matrix` runs all 7 framework smoke tests
(5 Python + 2 TypeScript) sequentially, with per-framework venv
bootstrap and teardown.

**Important constraints:**

- **Slow + opt-in** — the matrix is gated on the `FRAMEWORK_MATRIX=1`
  environment variable or the `--force` flag. When the gate is unset the
  command prints an opt-in message and exits 0 without running any test.
- **NOT part of `task before-push`** — the matrix is excluded from the
  default QA gate to avoid adding 5–10 minutes to every local push cycle.
- **Nightly CI** — the matrix runs as an advisory (non-blocking) CI job
  on a scheduled nightly workflow. A failure there signals SDK drift, not
  a broken commit.

Run manually:

```bash
# Run the full 7-framework matrix (slow — boots per-framework venvs)
FRAMEWORK_MATRIX=1 task mcp:framework-matrix

# Force-run even if the gate env var is unset
task mcp:framework-matrix -- --force
```

---

## OpenAI Agents

**Requirement:** FRAME-01 | **Transport:** stdio + streamable HTTP

### Install

```bash
pip install openai-agents==0.17.5 mcp==1.27.2
```

Pin reference: `framework-matrix/openai-agents/requirements.txt`

### Server command

**stdio** (adapter spawns `agent-brain-mcp` as a subprocess):

```python
command = "agent-brain-mcp"
args    = ["--backend", "uds", "--state-dir", "<project>/.agent-brain"]
env     = {"PATH": ..., "HOME": ..., "AGENT_BRAIN_STATE_DIR": ..., "OPENAI_API_KEY": ...}
```

**streamable HTTP** (start the HTTP listener first):

```bash
agent-brain mcp start   # starts agent-brain-mcp --transport http on a loopback port
                        # writes mcp.runtime.json with the URL
agent-brain mcp stop    # teardown
```

### Transport

Both `MCPServerStdio` (stdio subprocess) and `MCPServerStreamableHttp`
(loopback HTTP) are smoke-tested for this framework.

### Capabilities

Primary tool: `search_documents({"query": "authenticate user login"})` — semantic
search over indexed codebases and docs.
\+ 15 more tools, 5 resources + 4 URI schemes (`chunk://`, `graph-entity://`,
`job://`, `file://`), 6 prompts — see [docs/USER_GUIDE.md](USER_GUIDE.md).

### Connect snippet (mirrors `framework-matrix/openai-agents/test_openai_agents_smoke.py`)

```python
import asyncio
from agents.mcp import MCPServerStdio, MCPServerStreamableHttp

# --- stdio transport ---
async def connect_stdio(state_dir: str) -> None:
    server = MCPServerStdio(
        name="agent-brain-mcp-stdio",
        params={
            "command": "agent-brain-mcp",
            "args": ["--backend", "uds", "--state-dir", f"{state_dir}/.agent-brain"],
            "env": {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": "/home/user",
                "AGENT_BRAIN_STATE_DIR": f"{state_dir}/.agent-brain",
                "OPENAI_API_KEY": "sk-...",
            },
        },
    )
    async with server:
        tools = await server.list_tools()
        assert any(t.name == "search_documents" for t in tools)
        result = await server.call_tool("search_documents", {"query": "authenticate user login"})
        print(result)

# --- streamable HTTP transport ---
async def connect_http(mcp_url: str) -> None:
    # Start the server first: `agent-brain mcp start`
    # URL is written to mcp.runtime.json, e.g. http://127.0.0.1:PORT/mcp
    server = MCPServerStreamableHttp(
        name="agent-brain-mcp-http",
        params={"url": mcp_url},
    )
    async with server:
        tools = await server.list_tools()
        assert any(t.name == "search_documents" for t in tools)
        result = await server.call_tool("search_documents", {"query": "authenticate user login"})
        print(result)

asyncio.run(connect_stdio("/path/to/project"))
```

---

## LangChain

**Requirement:** FRAME-02 | **Transport:** stdio

### Install

```bash
pip install langchain-mcp-adapters==0.3.0 langchain-core==1.4.6 mcp==1.27.2
```

Pin reference: `framework-matrix/langchain/requirements.txt`

### Server command

The adapter spawns `agent-brain-mcp` as a subprocess via `MultiServerMCPClient`
with `transport="stdio"`. No separate server start needed.

### Transport

stdio (`MultiServerMCPClient` with `transport="stdio"`).

### Capabilities

Primary tool: `search_documents({"query": "authenticate user login"})`.
\+ 15 more tools, 5 resources + 4 URI schemes, 6 prompts — see [docs/USER_GUIDE.md](USER_GUIDE.md).

### Connect snippet (mirrors `framework-matrix/langchain/test_langchain_smoke.py`)

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient

async def connect(state_dir: str) -> None:
    async with MultiServerMCPClient(
        {
            "agent-brain": {
                "command": "agent-brain-mcp",
                "args": ["--backend", "uds", "--state-dir", f"{state_dir}/.agent-brain"],
                "transport": "stdio",
                "env": {
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "HOME": "/home/user",
                    "AGENT_BRAIN_STATE_DIR": f"{state_dir}/.agent-brain",
                    "OPENAI_API_KEY": "sk-...",
                },
            }
        }
    ) as client:
        tools = await client.get_tools()
        search_tool = next(t for t in tools if t.name == "search_documents")
        # Invoke directly — no LLM agent loop required (keyless)
        result = await search_tool.ainvoke({"query": "authenticate user login"})
        print(result)

asyncio.run(connect("/path/to/project"))
```

---

## LlamaIndex

**Requirement:** FRAME-03 | **Transport:** stdio

### Install

```bash
pip install llama-index-tools-mcp==0.4.8 llama-index-core==0.14.22 mcp==1.27.2
```

Pin reference: `framework-matrix/llama-index/requirements.txt`

### Server command

The adapter spawns `agent-brain-mcp` as a subprocess via `BasicMCPClient`.
No separate server start needed.

### Transport

stdio (`BasicMCPClient` with `command`, `args`, `env`).

### Capabilities

Primary tool: `search_documents({"query": "authenticate user login"})`.
\+ 15 more tools, 5 resources + 4 URI schemes, 6 prompts — see [docs/USER_GUIDE.md](USER_GUIDE.md).

### Connect snippet (mirrors `framework-matrix/llama-index/test_llama_index_smoke.py`)

```python
import asyncio
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec

async def connect(state_dir: str) -> None:
    mcp_client = BasicMCPClient(
        "agent-brain-mcp",
        args=["--backend", "uds", "--state-dir", f"{state_dir}/.agent-brain"],
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/home/user",
            "AGENT_BRAIN_STATE_DIR": f"{state_dir}/.agent-brain",
            "OPENAI_API_KEY": "sk-...",
        },
    )
    tool_spec = McpToolSpec(client=mcp_client)
    tools = await tool_spec.to_tool_list_async()

    search_tool = next(
        t for t in tools if t.metadata.name == "search_documents"
    )
    # Call directly — no LLM loop required (keyless)
    result = await search_tool.acall(**{"query": "authenticate user login"})
    print(result)

asyncio.run(connect("/path/to/project"))
```

---

## Pydantic AI

**Requirement:** FRAME-04 | **Transport:** stdio

### Install

```bash
pip install pydantic-ai==1.107.0 mcp==1.9.4 anyio==4.9.0
```

Pin reference: `framework-matrix/pydantic-ai/requirements.txt`

### Server command

The adapter spawns `agent-brain-mcp` as a subprocess via `MCPServerStdio`.
No separate server start needed.

### Transport

stdio (`pydantic_ai.mcp.MCPServerStdio`).

### Capabilities

Primary tool: `search_documents({"query": "authenticate user login"})`.
\+ 15 more tools, 5 resources + 4 URI schemes, 6 prompts — see [docs/USER_GUIDE.md](USER_GUIDE.md).

### Connect snippet (mirrors `framework-matrix/pydantic-ai/test_pydantic_ai_smoke.py`)

```python
import asyncio
from pydantic_ai.mcp import MCPServerStdio

async def connect(state_dir: str) -> None:
    server = MCPServerStdio(
        "agent-brain-mcp",
        args=["--backend", "uds", "--state-dir", f"{state_dir}/.agent-brain"],
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/home/user",
            "AGENT_BRAIN_STATE_DIR": f"{state_dir}/.agent-brain",
            "OPENAI_API_KEY": "sk-...",
        },
    )
    async with server:
        tools = await server.list_tools()
        assert any(t.name == "search_documents" for t in tools)
        result = await server.call_tool("search_documents", {"query": "authenticate user login"})
        print(result)

asyncio.run(connect("/path/to/project"))
```

---

## Autogen

**Requirement:** FRAME-05 | **Transport:** stdio

**Package note:** `McpWorkbench` ships in `autogen-ext[mcp]` (Microsoft's
`autogen-ext` package), NOT in the AG2 fork (`pyautogen`). Import from
`autogen_ext.tools.mcp`.

### Install

```bash
pip install "autogen-ext[mcp]==0.7.5" autogen-core==0.7.5 mcp==1.9.4 anyio==4.9.0
```

Pin reference: `framework-matrix/autogen/requirements.txt`

### Server command

The adapter spawns `agent-brain-mcp` as a subprocess via `McpWorkbench` +
`StdioServerParams`. No separate server start needed.

### Transport

stdio (`McpWorkbench` with `StdioServerParams`).

### Capabilities

Primary tool: `search_documents({"query": "authenticate user login"})`.
\+ 15 more tools, 5 resources + 4 URI schemes, 6 prompts — see [docs/USER_GUIDE.md](USER_GUIDE.md).

### Connect snippet (mirrors `framework-matrix/autogen/test_autogen_smoke.py`)

```python
import asyncio
from autogen_ext.tools.mcp import McpWorkbench, StdioServerParams

async def connect(state_dir: str) -> None:
    params = StdioServerParams(
        command="agent-brain-mcp",
        args=["--backend", "uds", "--state-dir", f"{state_dir}/.agent-brain"],
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/home/user",
            "AGENT_BRAIN_STATE_DIR": f"{state_dir}/.agent-brain",
            "OPENAI_API_KEY": "sk-...",
        },
    )
    async with McpWorkbench(server_params=params) as wb:
        tools = await wb.list_tools()
        assert any(t.name == "search_documents" for t in tools)
        result = await wb.call_tool("search_documents", {"query": "authenticate user login"})
        print(result)

asyncio.run(connect("/path/to/project"))
```

---

## Mastra

**Requirement:** FRAME-06 | **Transport:** stdio

### Install

```bash
npm install @mastra/mcp@1.9.1 @modelcontextprotocol/sdk@1.29.0
# or with pnpm
pnpm add @mastra/mcp@1.9.1 @modelcontextprotocol/sdk@1.29.0
```

Pin reference: `framework-matrix/ts/package.json` + `framework-matrix/ts/PINS.md`

### Server command

The adapter spawns `agent-brain-mcp` as a subprocess via `MCPClient` with a
stdio server entry. No separate server start needed.

### Transport

stdio (`MCPClient` with `{ command, args, env }` server config).

### Capabilities

Primary tool: `search_documents({"query": "authenticate user login"})`.
\+ 15 more tools, 5 resources + 4 URI schemes, 6 prompts — see [docs/USER_GUIDE.md](USER_GUIDE.md).

### Connect snippet (mirrors `framework-matrix/ts/test/mastra.test.ts`)

```typescript
import { MCPClient } from "@mastra/mcp";

async function connect(stateDir: string): Promise<void> {
  const client = new MCPClient({
    id: "agent-brain-smoke",
    servers: {
      agentBrain: {
        command: "agent-brain-mcp",
        args: ["--backend", "uds", "--state-dir", `${stateDir}/.agent-brain`],
        env: {
          PATH: process.env.PATH ?? "",
          HOME: process.env.HOME ?? "",
          AGENT_BRAIN_STATE_DIR: `${stateDir}/.agent-brain`,
          OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
        },
      },
    },
  });

  // listToolsets() returns tools grouped by server name (not namespaced)
  const toolsets = await client.listToolsets();
  const serverTools = toolsets["agentBrain"];
  console.log("Available tools:", Object.keys(serverTools));

  // Call search_documents
  const tool = serverTools["search_documents"] as unknown as {
    execute?: (args: unknown, opts: unknown) => Promise<unknown>;
  };
  const result = await tool.execute?.({ query: "authenticate user login" }, {});
  console.log(result);

  await client.disconnect();
}

connect("/path/to/project");
```

**Note on `listToolsets()` vs `listTools()`:** Use `listToolsets()` — it
returns tools grouped by server name without namespacing. `listTools()` would
return tools namespaced as `serverName_toolName`.

---

## Vercel AI SDK

**Requirement:** FRAME-07 | **Transport:** stdio

### Install

```bash
npm install @ai-sdk/mcp@1.0.48 @modelcontextprotocol/sdk@1.29.0 zod@4.4.3
# or with pnpm
pnpm add @ai-sdk/mcp@1.0.48 @modelcontextprotocol/sdk@1.29.0 zod@4.4.3
```

Pin reference: `framework-matrix/ts/package.json` + `framework-matrix/ts/PINS.md`

### Server command

The adapter connects via `StdioClientTransport` from the MCP SDK, which
spawns `agent-brain-mcp` as a subprocess. No separate server start needed.

### Transport

stdio (`StdioClientTransport` from `@modelcontextprotocol/sdk/client/stdio.js`).

### Capabilities

Primary tool: `search_documents({"query": "authenticate user login"})`.
\+ 15 more tools, 5 resources + 4 URI schemes, 6 prompts — see [docs/USER_GUIDE.md](USER_GUIDE.md).

### Connect snippet (mirrors `framework-matrix/ts/test/vercel-ai-sdk.test.ts`)

```typescript
import { experimental_createMCPClient } from "@ai-sdk/mcp";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

async function connect(stateDir: string): Promise<void> {
  const transport = new StdioClientTransport({
    command: "agent-brain-mcp",
    args: ["--backend", "uds", "--state-dir", `${stateDir}/.agent-brain`],
    env: {
      PATH: process.env.PATH ?? "",
      HOME: process.env.HOME ?? "",
      AGENT_BRAIN_STATE_DIR: `${stateDir}/.agent-brain`,
      OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? "",
    },
  });

  // createMCPClient is the stable API; experimental_createMCPClient is an alias
  const client = await experimental_createMCPClient({ transport });

  // client.tools() returns McpToolSet (Record<toolName, McpToolBase>)
  const toolMap = await client.tools();
  console.log("Available tools:", Object.keys(toolMap));

  // Call search_documents
  const tool = toolMap["search_documents"] as unknown as {
    execute: (args: unknown, opts: unknown) => Promise<unknown>;
  };
  const result = await tool.execute({ query: "authenticate user login" }, {});
  console.log(result);

  await client.close();
}

connect("/path/to/project");
```

**Package note:** Import `createMCPClient` / `experimental_createMCPClient`
from `@ai-sdk/mcp`, NOT from the `ai` package. The `ai` package is not
required and is not installed in the matrix venv.

---

## SDK Pinning

The framework matrix pins every SDK version to control churn. Before running
the matrix or developing against a specific framework, align your environment
to these pin files.

### Python frameworks

Each Python framework has its own isolated venv and `requirements.txt`:

| Framework | Pin file | Key package |
|-----------|----------|-------------|
| OpenAI Agents | `framework-matrix/openai-agents/requirements.txt` | `openai-agents==0.17.5` |
| LangChain | `framework-matrix/langchain/requirements.txt` | `langchain-mcp-adapters==0.3.0` |
| LlamaIndex | `framework-matrix/llama-index/requirements.txt` | `llama-index-tools-mcp==0.4.8` |
| Pydantic AI | `framework-matrix/pydantic-ai/requirements.txt` | `pydantic-ai==1.107.0` |
| Autogen | `framework-matrix/autogen/requirements.txt` | `autogen-ext[mcp]==0.7.5` |

Bootstrap a framework venv:

```bash
bash framework-matrix/bootstrap_venv.sh openai-agents  # or langchain, llama-index, pydantic-ai, autogen
```

`bootstrap_venv.sh` exits with code 3 on pin drift (installed versions do not
match `requirements.txt`), so CI catches version mismatches immediately.

### TypeScript frameworks

| File | Purpose |
|------|---------|
| `framework-matrix/ts/package.json` | Exact pins (no `^` or `~` ranges) — install with `pnpm install --frozen-lockfile` |
| `framework-matrix/ts/PINS.md` | Pin manifest with package name, version, source URL, and pin date for every dependency |

Key TS pins: `@mastra/mcp@1.9.1`, `@ai-sdk/mcp@1.0.48`,
`@modelcontextprotocol/sdk@1.29.0`.

Install:

```bash
cd framework-matrix/ts
pnpm install --frozen-lockfile  # enforces exact pins
```

---

## Config Recipes

> **Config-only — NOT smoke-tested in v10.3**
>
> The 5 editor integrations below are configuration recipes only. Framework
> adapter drift is too fast to maintain reliable smoke tests for editor plugins
> alongside the 7 SDK-level tests above. Promoting any of these to a real
> smoke test is a future-milestone decision. Each recipe wires `agent-brain-mcp`
> as a stdio MCP server using the current config format for that editor.

### Goose

[Goose](https://github.com/block/goose) (Block's AI coding agent) reads MCP
server configuration from `~/.config/goose/config.yaml`.

> **Note (config-only, not smoke-tested in v10.3):** Confirm against
> [Goose MCP docs](https://block.github.io/goose/docs/getting-started/using-extensions)
> for the latest config schema.

```yaml
# ~/.config/goose/config.yaml
extensions:
  agent-brain:
    type: stdio
    cmd: agent-brain-mcp
    args:
      - "--backend"
      - "uds"
      - "--state-dir"
      - "/path/to/project/.agent-brain"
    envs:
      AGENT_BRAIN_STATE_DIR: "/path/to/project/.agent-brain"
      OPENAI_API_KEY: "sk-..."
    timeout: 30
    enabled: true
```

### Continue.dev

[Continue.dev](https://continue.dev) reads MCP server configuration from
`~/.continue/config.yaml` (or `config.json` for older versions).

> **Note (config-only, not smoke-tested in v10.3):** Confirm against
> [Continue MCP docs](https://docs.continue.dev/customize/model-providers/more/mcp)
> for the latest config schema.

```yaml
# ~/.continue/config.yaml
mcpServers:
  - name: agent-brain
    command: agent-brain-mcp
    args:
      - "--backend"
      - "uds"
      - "--state-dir"
      - "/path/to/project/.agent-brain"
    env:
      AGENT_BRAIN_STATE_DIR: "/path/to/project/.agent-brain"
      OPENAI_API_KEY: "sk-..."
```

Alternatively in `config.json` format:

```json
{
  "mcpServers": [
    {
      "name": "agent-brain",
      "command": "agent-brain-mcp",
      "args": [
        "--backend", "uds",
        "--state-dir", "/path/to/project/.agent-brain"
      ],
      "env": {
        "AGENT_BRAIN_STATE_DIR": "/path/to/project/.agent-brain",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  ]
}
```

### Cline

[Cline](https://github.com/cline/cline) (VS Code extension) reads MCP server
configuration from its settings file, typically stored at:
`~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

> **Note (config-only, not smoke-tested in v10.3):** Confirm against
> [Cline MCP docs](https://github.com/cline/cline/blob/main/docs/mcp.md)
> for the latest config schema.

```json
{
  "mcpServers": {
    "agent-brain-mcp": {
      "command": "agent-brain-mcp",
      "args": [
        "--backend", "uds",
        "--state-dir", "/path/to/project/.agent-brain"
      ],
      "env": {
        "AGENT_BRAIN_STATE_DIR": "/path/to/project/.agent-brain",
        "OPENAI_API_KEY": "sk-..."
      },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### Cursor

[Cursor](https://cursor.sh) reads MCP server configuration from
`~/.cursor/mcp.json` (global) or `.cursor/mcp.json` in your project root
(project-scoped).

> **Note (config-only, not smoke-tested in v10.3):** Confirm against
> [Cursor MCP docs](https://docs.cursor.com/context/model-context-protocol)
> for the latest config schema.

```json
{
  "mcpServers": {
    "agent-brain-mcp": {
      "command": "agent-brain-mcp",
      "args": [
        "--backend", "uds",
        "--state-dir", "/path/to/project/.agent-brain"
      ],
      "env": {
        "AGENT_BRAIN_STATE_DIR": "/path/to/project/.agent-brain",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

### Cody

[Cody](https://sourcegraph.com/cody) (Sourcegraph's AI coding assistant) reads
MCP server configuration from the VS Code extension settings via
`sourcegraph.cody.mcpServers` in your VS Code `settings.json`, or from the
Cody configuration file.

> **Note (config-only, not smoke-tested in v10.3):** Confirm against
> [Cody MCP docs](https://sourcegraph.com/docs/cody/capabilities/agentic-chat)
> for the latest config schema, as the format may have changed since this
> recipe was authored.

```json
{
  "sourcegraph.cody.mcpServers": {
    "agent-brain-mcp": {
      "command": "agent-brain-mcp",
      "args": [
        "--backend", "uds",
        "--state-dir", "/path/to/project/.agent-brain"
      ],
      "env": {
        "AGENT_BRAIN_STATE_DIR": "/path/to/project/.agent-brain",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```
