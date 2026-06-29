---
last_validated: 2026-05-30
---

# Agent Brain MCP Server Guide

Complete reference for `agent-brain-mcp` — the Model Context Protocol server that exposes your indexed Agent Brain corpus to MCP-aware clients (Claude Desktop, Cursor, Windsurf, Claude Agent SDK, LangChain DeepAgents, and any other MCP host).

## Table of Contents

- [What it is](#what-it-is)
- [MCP server vs. plugin — which should I use?](#mcp-server-vs-plugin--which-should-i-use)
- [Features at a glance](#features-at-a-glance)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Universal stdio config](#universal-stdio-config)
  - [Claude Desktop](#claude-desktop)
  - [Cursor / Windsurf / generic MCP IDE](#cursor--windsurf--generic-mcp-ide)
  - [Claude Agent SDK (Python)](#claude-agent-sdk-python)
  - [LangChain DeepAgents (and other LangGraph agents)](#langchain-deepagents-and-other-langgraph-agents)
  - [Other agent frameworks (preview)](#other-agent-frameworks-preview)
- [MCP transport axes (v10.2+)](#mcp-transport-axes-v102)
- [CLI flags and environment variables](#cli-flags-and-environment-variables)
- [Tool reference (16 tools)](#tool-reference-16-tools)
- [Resource reference (5 resources)](#resource-reference-5-resources)
- [Prompt reference (6 prompts)](#prompt-reference-6-prompts)
- [End-to-end worked examples](#end-to-end-worked-examples)
- [Error handling](#error-handling)
- [Cancellation](#cancellation)
- [Troubleshooting](#troubleshooting)
- [What's not in v1, and what's coming](#whats-not-in-v1-and-whats-coming)
- [Related docs](#related-docs)

---

## What it is

`agent-brain-mcp` is a small Python process that speaks the [Model Context Protocol](https://modelcontextprotocol.io/) over stdio to an LLM client and talks to your local Agent Brain backend (the FastAPI server shipped by `agent-brain-rag`) over a Unix Domain Socket or HTTP. It is **a thin protocol adapter**, not a re-implementation — every tool call maps to a single REST endpoint on the backend.

- **PyPI distribution:** `agent-brain-ag-mcp`
- **Console script:** `agent-brain-mcp`
- **Transport (to the LLM client):** stdio (default) or Streamable HTTP (`--transport http`)
- **Transport (to the backend):** UDS (preferred) or HTTP, selectable with `--backend {auto|uds|http}`
- **Surface (v10.4):** **16 tools**, 5 read-only resources, 6 prompts
- **Auth (v10.4):** OAuth 2.1 on the HTTP listen transport, **off by default** — see [Authentication](#authentication)
- **Quick start:** for a copy-paste walkthrough see the **[MCP Quickstart](./MCP_QUICKSTART.md)**

> **Register it for Claude Code in one command:** `agent-brain install-agent --agent claude --with-mcp`
> writes the `.mcp.json` entry for you (see [Register automatically](#register-automatically-claude-code)).

If you want slash commands inside Claude Code, OpenCode, Gemini CLI, or Codex, use the [plugin](./PLUGIN_GUIDE.md) instead. If your LLM client speaks MCP natively (Claude Desktop, Cursor, an agent SDK), use this server.

---

## MCP server vs. plugin — which should I use?

You can run both at the same time against the same backend — they don't conflict. Use whichever matches your host.

| Question | Plugin | MCP server |
|---|---|---|
| Where does it run? | Inside Claude Code / OpenCode / Gemini CLI / Codex | Inside Claude Desktop, Cursor, Windsurf, an agent SDK process |
| How does the user call it? | `/agent-brain-search "…"` slash commands (30 of them) | The host model picks tools, reads resources, or expands prompts as part of normal tool use |
| What's installed? | Markdown files + a few shell commands; shells out to the `agent-brain` CLI | A Python process started by the host as a subprocess |
| Best for | Interactive sessions where humans drive search via slash commands | Agentic / autonomous workflows where the model itself orchestrates retrieval |
| Backend required? | Yes (`agent-brain start`) | Yes (`agent-brain start`) |
| Multi-runtime? | Yes — Claude Code, OpenCode, Gemini CLI, Codex, generic skill runtime | Yes — any MCP-aware host |

**Rule of thumb:** if your client has a `mcpServers` config block, use the MCP server. If it has a `plugins` config block and you're a Claude Code / OpenCode / Gemini user, use the plugin.

---

## Features at a glance

- **All 5 retrieval modes** — `semantic`, `bm25`, `hybrid`, `graph`, `multi` — selected by the `mode` parameter on a single `search_documents` tool. No mode-specific tools to remember.
- **Structured tool output** — every tool advertises an `outputSchema` and returns a typed `structuredContent` block alongside the human-readable summary, so model clients that consume MCP structured output get typed data.
- **Corpus state as resources** — read backend config, status, health, providers, and indexed folders via `corpus://...` URIs without a tool call (i.e. without an LLM round-trip).
- **Opinionated multi-step prompts** — six parameterized templates (`find-callers`, `find-implementation`, `explain-architecture`, `compare-search-modes`, `onboard-to-codebase`, `audit-indexed-folders`) that chain tool calls into useful end-to-end flows.
- **One-command registration** — `install-agent --agent claude --with-mcp` writes/merges the `.mcp.json` entry (idempotent, dry-run aware) instead of hand-editing JSON.
- **OAuth 2.1 for remote servers (v10.4)** — run Agent Brain remotely behind OAuth on the HTTP transport, with per-tool scopes (`agent-brain:read|index|admin|subscribe`) and default-deny on the mutating tools. Off by default; local/loopback needs no auth.
- **UDS-or-HTTP backend transport** — `--backend auto` prefers UDS for lower latency and falls back to HTTP transparently.
- **Version-compat startup check** — the server calls `GET /health/` once at startup and refuses to start if the backend reports a version below the pinned `MIN_BACKEND_VERSION`. Prevents wire drift.
- **Structured JSON-RPC errors** — HTTP failures map to MCP error codes including custom `-32000…-32003` codes for `BackendConflict`, `BackendUnavailable`, `ServiceIndexing`, and `BackendTimeout`. Every error carries `data.httpStatus` and `data.cause`.
- **Responsive cancellation** — `notifications/cancelled` unblocks the MCP-side handler within ~1 second even while a slow backend request is in flight.

---

## Installation

The MCP server is published as `agent-brain-ag-mcp` on PyPI. The PyPI distribution name is unusual (the original `agent-brain-mcp` name was taken on PyPI), but the installed **console script** is `agent-brain-mcp`.

```bash
pip install agent-brain-ag-mcp
# verify
agent-brain-mcp --help
```

You also need a running Agent Brain backend. The MCP server is a proxy — it does not index anything itself.

```bash
# install the backend + CLI
pip install agent-brain-rag agent-brain-cli

# in your project root
agent-brain init                  # creates .agent-brain/
agent-brain start                 # starts the FastAPI server
agent-brain index ./docs          # index something
```

For multi-instance / shared deployments, see [`docs/USER_GUIDE.md`](./USER_GUIDE.md#multi-project-support).

---

## Configuration

### Register automatically (Claude Code)

The fastest path — let the CLI write the registration for you while installing the plugin:

```bash
# Install the plugin AND register the agent-brain MCP server for Claude Code
agent-brain install-agent --agent claude --with-mcp

# Preview without writing
agent-brain install-agent --agent claude --with-mcp --dry-run

# Register with client-side OAuth (for a remote, OAuth-protected server)
agent-brain install-agent --agent claude --with-mcp --mcp-auth oauth
```

This writes/merges an `agent-brain` entry into the runtime's MCP config, **preserving any other
servers and keys**, pins an absolute `AGENT_BRAIN_STATE_DIR`, and is **idempotent** (re-running
reports `unchanged`). Flags: `--with-mcp`, `--mcp-backend {auto,uds,http}`,
`--mcp-auth {none,oauth}`. Auto-registration targets **Claude Code** (`.mcp.json` / `~/.claude.json`,
`mcpServers` schema) and **OpenCode** (`--agent opencode` → project-root `opencode.json` /
`~/.config/opencode/opencode.json`, `mcp` schema with a single `command` array + `environment`).
For Gemini / Codex it prints a note and skips — register manually with the JSON below (tracked as
[#225](https://github.com/SpillwaveSolutions/agent-brain/issues/225)–[#226](https://github.com/SpillwaveSolutions/agent-brain/issues/226)).

### Universal stdio config

Every MCP host launches the server the same way — a subprocess with a `command`, optional `args`, and an `env` dictionary. The hosts only differ in *where* you put that object.

```json
{
  "command": "agent-brain-mcp",
  "args": ["--backend", "auto"],
  "env": {
    "AGENT_BRAIN_STATE_DIR": "/abs/path/to/your-project/.agent-brain"
  }
}
```

- `command` must resolve on the host's `PATH`. If the host can't find it, use the absolute path printed by `which agent-brain-mcp`.
- `args` accept any flag from [CLI flags](#cli-flags-and-environment-variables).
- `env` should usually pin `AGENT_BRAIN_STATE_DIR` to the project's `.agent-brain` directory so the MCP server can locate the running backend's UDS socket and `runtime.json`. Without it, the server falls back to `$CWD/.agent-brain`, which the host's CWD may not match.

### Claude Desktop

Add to `claude_desktop_config.json` (location varies by OS — `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "agent-brain": {
      "command": "agent-brain-mcp",
      "args": ["--backend", "auto"],
      "env": {
        "AGENT_BRAIN_STATE_DIR": "/Users/me/work/myproject/.agent-brain"
      }
    }
  }
}
```

Restart Claude Desktop. The 16 tools, 5 resources, and 6 prompts will appear in the tool/resource pickers.

### Cursor / Windsurf / generic MCP IDE

Most MCP-aware IDEs accept the same `mcpServers` shape — Cursor uses `~/.cursor/mcp.json`, Windsurf uses its in-app settings, others vary. Drop the universal stdio object in:

```json
{
  "mcpServers": {
    "agent-brain": {
      "command": "agent-brain-mcp",
      "args": ["--backend", "auto"],
      "env": {
        "AGENT_BRAIN_STATE_DIR": "/abs/path/to/.agent-brain"
      }
    }
  }
}
```

If your IDE asks for a "name" or "label", use `agent-brain` — tools and resources are namespaced by it in the host (e.g. `mcp__agent-brain__search_documents` in some hosts).

### Claude Agent SDK (Python)

The [`claude-agent-sdk-python`](https://github.com/anthropics/claude-agent-sdk-python) registers external MCP servers through `ClaudeAgentOptions.mcp_servers`:

```python
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

options = ClaudeAgentOptions(
    mcp_servers={
        "agent-brain": {
            "type": "stdio",
            "command": "agent-brain-mcp",
            "args": ["--backend", "auto"],
            "env": {
                "AGENT_BRAIN_STATE_DIR": "/abs/path/to/.agent-brain",
            },
        },
    },
    # Pre-approve Agent Brain tools so the SDK does not prompt
    # for permission on each call. Names are namespaced by server.
    allowed_tools=[
        "mcp__agent-brain__search_documents",
        "mcp__agent-brain__query_count",
        "mcp__agent-brain__server_health",
    ],
)

async with ClaudeSDKClient(options=options) as client:
    await client.query("Find every caller of `compute_embeddings`.")
    async for msg in client.receive_response():
        print(msg)
```

Tool names in `allowed_tools` follow the SDK's `mcp__<server-name>__<tool-name>` namespacing convention. Omit destructive tools (`cancel_job`) from `allowed_tools` if you want the SDK to ask for permission each time.

### LangChain DeepAgents (and other LangGraph agents)

DeepAgents builds on LangGraph, and the canonical way to load MCP tools into a LangGraph agent is the official [`langchain-mcp-adapters`](https://github.com/langchain-ai/langchain-mcp-adapters) package. The same pattern works for any LangChain agent that accepts a `tools=` list.

```bash
pip install deepagents langchain-mcp-adapters
```

```python
from deepagents import create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        "agent-brain": {
            "command": "agent-brain-mcp",
            "args": ["--backend", "auto"],
            "transport": "stdio",
            "env": {
                "AGENT_BRAIN_STATE_DIR": "/abs/path/to/.agent-brain",
            },
        },
    }
)

tools = await client.get_tools()
agent = create_deep_agent(tools=tools, model="anthropic:claude-opus-4-7")

result = await agent.ainvoke(
    {"messages": [("user", "Where is `IndexingService.process_folder` implemented?")]}
)
```

The `MultiServerMCPClient` starts `agent-brain-mcp` as a stdio subprocess and exposes each MCP tool as a LangChain `Tool`. `client.get_tools()` returns the full set — pass them through to `create_deep_agent`, `create_agent`, `create_react_agent`, or your own LangGraph node.

If you'd rather use DeepAgents' built-in MCP loader (the `.mcp.json` file under your project root), put the universal stdio object there with `"type": "stdio"` and DeepAgents will pick it up at launch.

### Other agent frameworks (preview)

First-party adapters for OpenAI Agents SDK, LlamaIndex, Pydantic AI, Mastra, Vercel AI SDK, and Autogen are tracked in [v3 of the MCP roadmap](./roadmaps/mcp/v3-cli-via-mcp-and-frameworks.md). In the meantime, any framework that can spawn an MCP stdio subprocess (i.e. anyone using the official `mcp` Python or TypeScript SDK as a client) can connect today — the universal stdio config above is all you need.

---

## MCP transport axes (v10.2+)

Agent Brain's MCP integration has **two orthogonal transport axes**. Conflating them is the most common operator mistake — and it matters because authentication is scoped to one axis only.

```
┌─────────────┐  listen transport   ┌──────────────────┐  backend transport  ┌────────────────────┐
│ MCP client  │ ──────────────────▶ │ agent-brain-mcp  │ ──────────────────▶ │ agent-brain-serve  │
│ (Claude     │  --transport        │ (MCP server)     │  --backend          │ (FastAPI / UDS)    │
│  Desktop,   │  {stdio, http}      │                  │  {auto, uds, http}  │                    │
│  SDK, IDE)  │                     │                  │                     │                    │
└─────────────┘                     └──────────────────┘                     └────────────────────┘
       ▲                                                                                ▲
       │                                                                                │
       │      OAuth 2.1 on the listen axis                          X-API-Key on the
       │      (shipped v10.4 — OFF by default)                      backend axis (#179)
       │                                                                                │
       └──────────────────────────── deliberately distinct axes ────────────────────────┘
```

The two axes are independent:

- **`--transport` (listen axis)** — how MCP clients reach `agent-brain-mcp`. Either an OS pipe (`stdio`) or a Streamable HTTP listener (`http`).
- **`--backend` (backend axis)** — how `agent-brain-mcp` reaches `agent-brain-serve`. Either a Unix domain socket (`uds`) or a localhost HTTP client (`http`), with `auto` trying UDS first.

### Authentication

**Local/loopback needs no auth.** For `stdio` and loopback HTTP, leave the defaults — the server
runs as a child of a trusted local client (subprocess hygiene covers stdio).

**OAuth 2.1 on the listen axis shipped in v10.4** (closes [#188](https://github.com/SpillwaveSolutions/agent-brain/issues/188)) for running Agent Brain remotely. It is **off by default** and opt-in via env vars:

| Variable | Side | Values | Notes |
|----------|------|--------|-------|
| `AGENT_BRAIN_AUTH` | server | `none` (default) / `basic` / `oauth` | Server-side auth mode on the HTTP listen transport |
| `AGENT_BRAIN_OAUTH_RESOURCE` | server | absolute URI (scheme, no fragment) | Required **only** in `oauth` mode (RFC 8707 resource id); invalid value → exit 2 at startup |
| `AGENT_BRAIN_MCP_AUTH` | client | unset (off) / `oauth` | Opts the MCP client into the OAuth dance (browser flow + token cache) |

Highlights:

- Co-located AS/RS (single binary, RS256 JWT) **and** split AS/RS (external IdP — Keycloak/Auth0/Cognito via JWKS / introspection).
- Discovery: Protected Resource Metadata (RFC 9728) + Authorization Server Metadata (RFC 8414); PKCE **S256-only**.
- **Per-tool scopes** — `agent-brain:read | index | admin | subscribe` — enforced server-side with **default-deny** on the mutating tools; an under-scoped call gets HTTP 403 `insufficient_scope`.
- Resource Indicators (RFC 8707) + confused-deputy prevention: the client OAuth token never reaches the MCP→backend leg, which keeps using `X-API-Key`.
- Client tokens persist at `<state_dir>/mcp-oauth-tokens.json` (chmod `0o600`) and refresh silently.

The optional **`X-API-Key` middleware on `agent-brain-serve`** (issue [#179](https://github.com/SpillwaveSolutions/agent-brain/issues/179)) is a separate **backend-axis** concern from the listen-axis OAuth above — they protect different hops.

### Local trust model

`127.0.0.1` binding alone does **not** protect against malicious local processes — any process running as the same user can reach the MCP HTTP port and drive tools (including `cancel_job`, which is annotated `destructiveHint: true`). Do **not** run `agent-brain-mcp --transport http` on a shared / multi-user host without external sandboxing.

### Picking a listen transport

| Situation                                              | Use this listen transport |
| ------------------------------------------------------ | ------------------------- |
| Claude Desktop / Claude Code / generic MCP CLI clients | `stdio` (default)         |
| IDE plugins or framework adapters that prefer HTTP/SSE | `http`                    |
| CI smoke tests driving the official MCP Python SDK     | `http`                    |
| Remote / shared host exposed beyond `127.0.0.1`        | `http` **behind a gateway with `AGENT_BRAIN_AUTH=oauth`** (v10.4) |

The backend axis is unchanged from v10.1 — `--backend auto` keeps working in both cases.

---

## CLI flags and environment variables

`agent-brain-mcp` exposes six flags split across the two transport axes.

### Backend axis (unchanged from v10.1)

| Flag | Env var | Default | Description |
|---|---|---|---|
| `--backend {auto,uds,http}` | `AGENT_BRAIN_MCP_BACKEND` | `auto` | Backend transport. `auto` tries UDS first and falls back to HTTP. |
| `--backend-url <url>` | `AGENT_BRAIN_MCP_BACKEND_URL` then `AGENT_BRAIN_URL` | `http://127.0.0.1:8000` | Explicit HTTP base URL. Only consulted when transport resolves to HTTP. |
| `--state-dir <path>` | `AGENT_BRAIN_STATE_DIR` | `$CWD/.agent-brain` if it exists | Locates the UDS socket and `runtime.json` for the running backend. |

### Listen axis (new in v10.2)

| Flag | Env var | Default | Description |
|---|---|---|---|
| `--transport {stdio,http}` | *(reserved: `AGENT_BRAIN_MCP_TRANSPORT` is NOT honored in v10.2 — see Phase 53 D-02)* | `stdio` | Listen transport. `stdio` keeps existing Claude Desktop / Code configs working; `http` mounts a Streamable HTTP listener at `/mcp` plus `/healthz`. |
| `--host <ip-or-name>` | — | `127.0.0.1` | Bind host for `--transport http`. Only `127.0.0.1`, `localhost`, and `::1` are accepted (loopback whitelist). Ignored when `--transport stdio`. |
| `--port <int>` | — | `8765` | TCP port for `--transport http`. Ignored when `--transport stdio`. |

### Auth axis (v10.4, off by default)

| Env var | Side | Default | Description |
|---|---|---|---|
| `AGENT_BRAIN_AUTH` | server | `none` | `none` / `basic` / `oauth` — enables OAuth 2.1 on the HTTP listen transport |
| `AGENT_BRAIN_OAUTH_RESOURCE` | server | — | Required in `oauth` mode: absolute resource URI (scheme, no fragment) |
| `AGENT_BRAIN_OAUTH_ISSUER` | server | — | Optional external Authorization Server issuer (split AS/RS) |
| `AGENT_BRAIN_MCP_AUTH` | client | unset | Set to `oauth` to opt the MCP client into the OAuth dance |

### Resolution precedence

**Backend axis** (top wins):

- Transport: `--backend` → `AGENT_BRAIN_MCP_BACKEND` → `"auto"`.
- HTTP URL: `--backend-url` → `AGENT_BRAIN_MCP_BACKEND_URL` → `AGENT_BRAIN_URL` → `<state-dir>/runtime.json::base_url` → `http://127.0.0.1:8000`.
- UDS path: `AGENT_BRAIN_UDS_PATH` → `<state-dir>/runtime.json::socket_path` → backend's conventional path under `<state-dir>/`.

**Listen axis:**

- `--transport` is the only knob. `AGENT_BRAIN_MCP_TRANSPORT` is reserved-but-not-honored in v10.2 — explicit opt-in only.
- `--host` is rejected at startup if not in `{127.0.0.1, localhost, ::1}`.
- `--port` collisions exit with code **2** (distinct from the default exit code 1 used for validation errors), so shell pipelines can route on `$?` without parsing stderr.

**Tip:** when running multiple Agent Brain projects from the same workstation, give each MCP entry its own `AGENT_BRAIN_STATE_DIR` and use a distinct host label (`agent-brain-app`, `agent-brain-docs`, …) so the model can address them separately. If you also need parallel HTTP listeners, give each one a distinct `--port`.

---

## Tool reference (16 tools)

Every tool returns both a human-readable `content` block and a typed `structuredContent` payload validated against its `outputSchema`. REST endpoint columns refer to the FastAPI backend the MCP server proxies to — see [`API_REFERENCE.md`](./API_REFERENCE.md) for full backend schemas.

The 7 core tools are documented in detail below; the 9 added in v10.2–v10.3 are summarized in
[Additional tools](#additional-tools-v102v103). Each tool's required OAuth scope (enforced only
when `AGENT_BRAIN_AUTH=oauth`) is listed in [Tool scopes](#tool-scopes).

### `search_documents` (readOnly, openWorld)

Search indexed documents using semantic, BM25, hybrid, graph, or multi-stage retrieval. **The single entry point for all retrieval modes.**

**Wraps:** `POST /query/`

**Input:**

| Field | Type | Default | Constraints |
|---|---|---|---|
| `query` | string | — | required |
| `mode` | enum | `"hybrid"` | one of `semantic`, `bm25`, `hybrid`, `graph`, `multi` |
| `top_k` | int | `10` | 1–100 |
| `similarity_threshold` | float | `0.0` | 0.0–1.0 (score floor) |
| `alpha` | float | `0.5` | 0.0–1.0 (hybrid mix: 0 = pure BM25, 1 = pure semantic) |
| `source_types` | string[] | null | filter by source type |
| `languages` | string[] | null | filter by language |
| `file_paths` | string[] | null | restrict to file-path globs |
| `explain` | bool | `false` | include per-result explanation block |

**Output:** `{query, mode, total_results, query_time_ms, results: [{text, source, score, chunk_id, metadata}]}`

**Use when:** you need the model to find chunks. Default `mode: hybrid` for general questions; `bm25` for exact symbols; `graph` for relationships ("who calls X?"); `multi` for the "throw the kitchen sink at it" question.

**Example call (MCP JSON-RPC):**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search_documents",
    "arguments": {
      "query": "session timeout handling",
      "mode": "hybrid",
      "top_k": 5,
      "alpha": 0.6,
      "explain": true
    }
  }
}
```

### `query_count` (readOnly)

Return total documents and chunks currently indexed.

**Wraps:** `GET /query/count`

**Input:** none.

**Output:** `{total_documents: int, total_chunks: int}`

**Use when:** the model is sanity-checking that the corpus is non-empty before searching.

### `index_folder` (openWorld)

Queue a folder for indexing. Returns a `job_id` the caller polls with `get_job`.

**Wraps:** `POST /index/?force=&allow_external=`

**Input:**

| Field | Type | Default | Constraints |
|---|---|---|---|
| `folder_path` | string | — | absolute or project-relative |
| `force` | bool | `false` | re-index even if unchanged |
| `allow_external` | bool | `false` | allow paths outside the project root |
| `include_code` | bool | `true` | apply AST-aware code ingestion |
| `chunk_size` | int? | null | optional override (≥ 1) |
| `chunk_overlap` | int? | null | optional override (≥ 0) |

**Output:** `{job_id, status, message?, folder_path, progress_percent?}`

**Use when:** the model needs to add new content to the corpus mid-conversation. Indexing is async; pair with `get_job`.

### `get_job` (readOnly)

Look up the current state of an indexing job.

**Wraps:** `GET /index/jobs/{job_id}`

**Input:** `{job_id: string}`

**Output:** `{job_id, status, progress_percent?, message?, started_at?, completed_at?}`

**Use when:** polling a job to completion. (v2 will add `wait_for_job` with server-side progress notifications — see roadmap.)

### `list_jobs` (readOnly)

List jobs in the queue with cursor-based pagination.

**Wraps:** `GET /index/jobs/?limit=&offset=`

**Input:**

| Field | Type | Default | Constraints |
|---|---|---|---|
| `limit` | int | `20` | 1–100 |
| `cursor` | string? | null | opaque base64-encoded offset from previous response |

**Output:** `{jobs: [JobSummary], next_cursor?}`

**Use when:** the model needs to enumerate background work — e.g. "find any stuck indexing jobs from yesterday".

### `cancel_job` (destructive)

Cancel an indexing job. **Requires a `confirm: true` argument as a destructive-operation guard** (enforced by the JSON Schema — calls without it fail validation).

**Wraps:** `DELETE /index/jobs/{job_id}`

**Input:** `{job_id: string, confirm: true}`

**Output:** `{job_id, cancelled: bool, message?}`

**Use when:** stopping a runaway re-index. Host clients typically prompt the user before allowing destructive tools — keep this tool out of any `allowed_tools` auto-approve list unless you trust the caller.

### `server_health` (readOnly)

Return Agent Brain server health, version, and mode.

**Wraps:** `GET /health/`

**Input:** none.

**Output:** `{status, version, message?, mode?, instance_id?}`

**Use when:** the model wants a quick liveness check (also called at MCP startup for the version-compat gate).

---

### Additional tools (v10.2–v10.3)

These 9 tools complete the 16-tool surface. Each returns the same `content` + typed
`structuredContent` shape; see `agent_brain_mcp/schemas.py` and [`API_REFERENCE.md`](./API_REFERENCE.md)
for full field-level schemas.

| Tool | Annotation | Wraps | Purpose |
|---|---|---|---|
| `explain_result` | readOnly | `POST /query/explain` | Explain why a result matched (score breakdown across modes) |
| `add_documents` | openWorld | `POST /index/add` | Add specific documents to the index without a full folder scan |
| `inject_documents` | openWorld | `POST /index/inject` | Index with a content-enrichment script (`--script`) |
| `wait_for_job` | openWorld | polls `GET /jobs/{id}` | Block until a job completes, emitting progress notifications |
| `list_folders` | readOnly | `GET /index/folders` | List indexed folders with chunk counts |
| `remove_folder` | destructive | `DELETE /index/folders` | Remove all chunks for a folder (requires `confirm: true`) |
| `cache_status` | readOnly | `GET /cache/status` | Embedding-cache statistics (hit rate, size) |
| `clear_cache` | destructive | `POST /cache/clear` | Clear cached embeddings (requires `confirm: true`) |
| `list_file_types` | readOnly | `GET /types` | List file-type presets and extensions |

### Tool scopes

When `AGENT_BRAIN_AUTH=oauth`, each tool requires the scope below (default-deny: a token without
the scope gets HTTP 403 `insufficient_scope`). With the default `AGENT_BRAIN_AUTH=none`, scopes are
not enforced.

| Scope | Tools |
|---|---|
| `agent-brain:read` | `search_documents`, `explain_result`, `query_count`, `server_health`, `cache_status`, `list_folders`, `list_file_types`, `list_jobs`, `get_job` |
| `agent-brain:index` | `index_folder`, `add_documents`, `inject_documents`, `wait_for_job` |
| `agent-brain:admin` | `cancel_job`, `remove_folder`, `clear_cache` |
| `agent-brain:subscribe` | resource subscriptions (`corpus://`, `job://`) |

---

## Resource reference (5 resources)

Resources are *read-on-demand only* in v1 — `resources/subscribe` lands in v2. All resources return JSON (`mime_type: application/json`) and mirror a backend `/health/*` or `/index/*` endpoint.

| URI | Mirrors | What's inside |
|---|---|---|
| `corpus://config` | `GET /health/config` | Storage backend, enabled stores (vector/BM25/graph), embedding model, reranker config, file-watcher status. |
| `corpus://status` | `GET /health/status` | Indexed document counts, in-progress jobs, queue depth, graph-index size, embedding + query cache hit rates. |
| `corpus://health` | `GET /health/` | Server status, message, version, mode (project/shared), instance_id, project_id. |
| `corpus://providers` | `GET /health/providers` | Active embedding / summarization / reranker provider per type with healthy / degraded / unavailable state and validation errors. |
| `corpus://folders` | `GET /index/folders/` | Array of indexed folders with `chunk_count`, `last_indexed`, `watch_mode`, and `watch_debounce_seconds`. |

**Use resources when** the model needs corpus *state* (what's indexed, what mode is configured, is the watcher running) rather than corpus *content*. Resource reads are an HTTP `GET` against the backend with no LLM round-trip — cheaper than calling a tool to fetch the same info.

**Example read (MCP JSON-RPC):**

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "resources/read",
  "params": { "uri": "corpus://folders" }
}
```

Response (truncated):

```json
{
  "contents": [
    {
      "uri": "corpus://folders",
      "mimeType": "application/json",
      "text": "{\"folders\":[{\"folder_path\":\"/Users/me/app/docs\",\"chunk_count\":1284,\"last_indexed\":\"2026-05-29T10:14:32Z\",\"watch_mode\":\"poll\",\"watch_debounce_seconds\":2}]}"
    }
  ]
}
```

---

## Prompt reference (6 prompts)

Prompts are parameterized message sequences the MCP server returns from `prompts/get`. The host model then executes the implied tool plan. They are pure templates — no backend call happens inside `prompts/get` itself; the model still issues the tool calls.

### `find-callers`

Find every function that calls a given symbol (graph-walk).

| Argument | Required | Description |
|---|---|---|
| `symbol` | yes | The function or method name to find callers of. |
| `language` | no | Optional language restriction (`python`, `ts`, …). |

**Implied tool plan:** `search_documents(mode=graph, relationship_types=["calls"], query=<symbol>)`, group results by file.

**Use when:** the user asks "where is `X` called from?" and you want a callsite-by-file report.

### `find-implementation`

Two-step BM25 + graph walk to surface a feature's primary implementation site and its tests.

| Argument | Required | Description |
|---|---|---|
| `feature` | yes | The feature, concept, or symbol to locate. |

**Implied tool plan:**
1. `search_documents(mode=bm25, query=<feature>)` for exact symbol matches.
2. `search_documents(mode=graph, …)` on the top match to walk to tests + helpers.

**Use when:** "show me where the X feature lives, plus its tests".

### `explain-architecture`

Multi-stage retrieval restricted to a folder, then a graph walk to produce an architectural summary.

| Argument | Required | Description |
|---|---|---|
| `folder` | yes | Folder (relative to project root) to explain. |
| `depth` | no (default `2`) | Graph walk depth. |

**Implied tool plan:**
1. `search_documents(mode=multi, file_paths=[<folder>/**])` to pull READMEs, entrypoints, high-level docs.
2. `search_documents(mode=graph)` on the top entrypoint symbols at `depth=<depth>`.

**Use when:** onboarding to or reviewing a specific subdirectory.

### `compare-search-modes`

Run the same query under BM25, hybrid, and multi modes and present the three result sets side-by-side.

| Argument | Required | Description |
|---|---|---|
| `query` | yes | The query to compare. |

**Implied tool plan:** three `search_documents` calls with different `mode` values; side-by-side report.

**Use when:** tuning retrieval — figuring out which mode answers a given question best.

### `onboard-to-codebase`

Build a "where to start" briefing by reading config + folders resources and surfacing top entrypoints.

| Argument | Required | Description |
|---|---|---|
| `area` | no | Optional folder or topic to scope the briefing. |

**Implied tool plan:**
1. `resources/read corpus://config` for backend setup.
2. `resources/read corpus://status` for index size and state.
3. `resources/read corpus://folders` for what's indexed.
4. `search_documents(mode=multi, …)` for top entrypoints.

**Use when:** new contributors arrive and you want a one-shot "read these files, in this order" briefing.

### `audit-indexed-folders`

Read `corpus://folders`, identify stale (>7 days) and unwatched folders, and suggest `index_folder` calls.

| Argument | Required | Description |
|---|---|---|
| (none) | — | — |

**Implied tool plan:** `resources/read corpus://folders`; categorize; suggest re-index commands.

**Use when:** doing periodic corpus hygiene.

---

## End-to-end worked examples

### 1. Index a folder and poll the job to completion

```jsonc
// 1. Queue the index
→ {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{
    "name":"index_folder",
    "arguments":{"folder_path":"./docs","include_code":false}
  }}

← {"jsonrpc":"2.0","id":1,"result":{
    "content":[{"type":"text","text":"Queued indexing of ./docs (job_id=ix-abc123)"}],
    "structuredContent":{
      "job_id":"ix-abc123","status":"queued",
      "folder_path":"./docs","progress_percent":0.0
    }
  }}

// 2. Poll until completed (host loops, e.g. every 2-5s)
→ {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{
    "name":"get_job","arguments":{"job_id":"ix-abc123"}
  }}

← {"jsonrpc":"2.0","id":2,"result":{
    "structuredContent":{
      "job_id":"ix-abc123","status":"completed",
      "progress_percent":100.0,
      "started_at":"2026-05-30T10:00:01Z",
      "completed_at":"2026-05-30T10:01:47Z"
    }
  }}
```

v1 has no `wait_for_job` — the host (or model) drives the poll loop. v2 will add server-side progress notifications.

### 2. Search and interpret results using a resource

```jsonc
// 1. Run a hybrid search with explanations on
→ tools/call search_documents { "query":"jwt refresh", "mode":"hybrid", "alpha":0.6, "explain":true }

// 2. Read corpus://config to understand what model + reranker produced those scores
→ resources/read corpus://config
← { "contents":[{"text":"{\"embedding_model\":\"text-embedding-3-large\",\"reranker\":{\"enabled\":true,\"model\":\"cohere-rerank-3\"},\"storage_backend\":\"chroma\"}"}] }
```

Reading `corpus://config` after a search lets the model contextualize the result list ("scores look low because reranker is disabled", "BM25 ignored because the bm25 store is off") without an extra tool call.

### 3. Onboard to a new codebase with the `onboard-to-codebase` prompt

```jsonc
// 1. Host asks the server to expand the prompt with arguments
→ {"jsonrpc":"2.0","id":1,"method":"prompts/get","params":{
    "name":"onboard-to-codebase","arguments":{"area":"auth"}
  }}

← {"jsonrpc":"2.0","id":1,"result":{
    "messages":[{"role":"user","content":{"type":"text","text":"Produce an onboarding briefing for this codebase focused on `auth`. Plan: 1. Read corpus://config ... 2. Read corpus://status ... 3. Read corpus://folders ... 4. Call search_documents (mode=multi) for the top entrypoints in `auth` ..."}}]
  }}

// 2. Host feeds those messages to the model, which then issues the
//    implied resources/read + tools/call sequence on its own.
```

The prompt itself doesn't call tools — it returns the script the model should execute. This is the MCP equivalent of a runbook.

---

## Error handling

HTTP backend errors are mapped to MCP JSON-RPC error codes per a fixed table. Every error carries `data.httpStatus` and `data.cause` so clients can distinguish transport-level failures from backend-rejected requests.

| HTTP | MCP code | Name | Notes |
|---|---|---|---|
| 400 / 404 / 422 | `-32602` | `InvalidParams` | Pydantic validation detail echoed in `data.cause`. |
| 409 | `-32000` | `BackendConflict` | Custom Agent Brain code. |
| 500 | `-32603` | `InternalError` | Standard JSON-RPC. |
| 502 | `-32001` | `BackendUnavailable` | Custom — UDS missing or HTTP unreachable. |
| 503 | `-32002` | `ServiceIndexing` | Custom — indexing in progress, retry later. |
| 504 | `-32003` | `BackendTimeout` | Custom — wraps `httpx.TimeoutException`. |

Transport-level errors (connection refused, read timeout) surface as the same custom codes (`-32001`, `-32003`), so MCP clients can tell "backend down" from "backend rejected my request" with one check.

**Version-compat startup check.** The server calls `GET /health/` once at startup and refuses to start if the backend reports a `version` below the pinned floor (`MIN_BACKEND_VERSION` in `agent_brain_mcp/server.py`). If this fires, upgrade the backend (`pip install -U agent-brain-rag agent-brain-cli`) and restart it. The pin is intentional — it prevents the MCP wire from drifting from the server it talks to.

---

## Cancellation

MCP `notifications/cancelled` propagates. Every tool and resource handler runs in `asyncio.to_thread` so the asyncio event loop stays responsive while a sync `httpx` call is in flight. Cancelling a tool call returns control to the MCP client within ~1 second; the underlying OS-level request may still complete in the background (Python can't portably kill threads), but the MCP-side handler unblocks cleanly. v1 has no long-running tools (no `wait_for_job` — that's v2), so this is a fast-path guarantee.

---

## Troubleshooting

**"Server fails to start with version-floor error."** The backend is older than `MIN_BACKEND_VERSION`. Upgrade both:

```bash
pip install -U agent-brain-rag agent-brain-cli agent-brain-ag-mcp
agent-brain stop && agent-brain start
```

**"Connection refused" / "Backend Unavailable (-32001)".** The backend isn't running, or the MCP server resolved the wrong state directory. Check:

```bash
agent-brain status                       # is the backend up?
agent-brain-mcp --backend http --backend-url http://127.0.0.1:8000   # bypass UDS to isolate
echo $AGENT_BRAIN_STATE_DIR              # does it match the project that ran `agent-brain start`?
```

**"Backend Timeout (-32003)" on long indexing jobs.** Expected for large folders — `index_folder` is async and returns immediately, but `get_job` calls use the backend's default timeout. Poll less aggressively or raise the backend timeout. (v2's `wait_for_job` will push progress notifications.)

**"Tool not found" or tools missing in the host.** The host probably hasn't picked up the new `mcpServers` entry. Restart Claude Desktop / your IDE after editing the config. In Claude Agent SDK, confirm `allowed_tools` uses the `mcp__<server-name>__<tool-name>` shape (e.g. `mcp__agent-brain__search_documents`).

**"agent-brain-mcp: command not found"** in the host. The host launches the subprocess with its own PATH, which may not include your user `bin`. Use the absolute path:

```bash
which agent-brain-mcp   # paste the result into "command"
```

**Multiple projects bleeding into each other.** Each MCP host entry must pin its own `AGENT_BRAIN_STATE_DIR` env var. Don't rely on `$CWD/.agent-brain` — the host's CWD is rarely your project root.

---

## Roadmap status (v1–v4 shipped)

The full MCP roadmap is complete as of **v10.4**:

- ✅ **v2** — resource subscriptions (`resources/subscribe`), Streamable HTTP transport, the
  `chunk://` / `graph-entity://` schemes, and the 9 additional tools.
- ✅ **v3** — CLI-via-MCP (`agent-brain --transport mcp`) and the agent-framework adapter matrix.
- ✅ **v4** — OAuth 2.1 for remote Agent Brain instances (see [Authentication](#authentication)).

What's next (not yet shipped):

- Multi-runtime `--with-mcp` auto-registration: OpenCode ✅ ([#224](https://github.com/SpillwaveSolutions/agent-brain/issues/224)); Gemini / Codex next — [#225](https://github.com/SpillwaveSolutions/agent-brain/issues/225)–[#226](https://github.com/SpillwaveSolutions/agent-brain/issues/226).
- Enterprise hardening + cloud deployment — [#219](https://github.com/SpillwaveSolutions/agent-brain/issues/219) and follow-ups #200–#205.

See [`docs/roadmaps/mcp/`](./roadmaps/mcp/) for the original per-version scope and
[`docs/plans/backlog-survey.md`](./plans/backlog-survey.md) for the current backlog.

---

## Related docs

- [Plugin Guide](./PLUGIN_GUIDE.md) — the slash-command companion for Claude Code / OpenCode / Gemini CLI / Codex.
- [User Guide](./USER_GUIDE.md) — backend setup, indexing, retrieval modes, multi-instance architecture.
- [API Reference](./API_REFERENCE.md) — FastAPI backend schemas (every MCP tool wraps one of these).
- [Configuration](./CONFIGURATION.md) — provider configuration (embedding, summarization, reranker).
- [GraphRAG Guide](./GRAPHRAG_GUIDE.md) — context for `mode: graph` searches.
- [MCP + UDS design doc](./plans/2026-05-28-mcp-uds-transport-design.md) — internal design (UDS bind strategy, package layering, future work).
- [MCP meta-roadmap](./roadmaps/mcp/) — v1 shipped, v2/v3/v4 planned scope.
