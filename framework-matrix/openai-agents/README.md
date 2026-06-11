# openai-agents — FRAME-01 Framework Smoke Tests

Tests `agent-brain-mcp` via the OpenAI Agents SDK MCP adapter over **both** transports:
`MCPServerStdio` (stdio) and `MCPServerStreamableHttp` (streamable HTTP). No LLM API key required.

## Bootstrap

```bash
sh framework-matrix/bootstrap_venv.sh openai-agents
```

## Run

```bash
framework-matrix/openai-agents/.venv/bin/pytest framework-matrix/openai-agents/ -m framework
```

Tests skip gracefully when `OPENAI_API_KEY` is missing or `agent-brain-serve`/`agent-brain-mcp` are not on PATH.
