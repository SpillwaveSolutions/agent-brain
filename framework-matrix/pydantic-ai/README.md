# FRAME-04: Pydantic AI — MCPServerStdio Smoke Test

Tests `pydantic_ai.mcp.MCPServerStdio` connecting to `agent-brain-mcp` over stdio, listing tools, and calling `search_documents` against the seeded corpus.

## Bootstrap

```bash
sh framework-matrix/bootstrap_venv.sh pydantic-ai
```

## Run

```bash
framework-matrix/pydantic-ai/.venv/bin/pytest framework-matrix/pydantic-ai/ -m framework -v
```
