# FRAME-05: Autogen/AG2 — McpWorkbench Smoke Test

Tests `autogen_ext.tools.mcp.McpWorkbench` (from **autogen-ext**, Microsoft's fork) connecting to `agent-brain-mcp` over stdio, listing tools, and calling `search_documents` against the seeded corpus.

**Distribution note**: `McpWorkbench` ships in `autogen-ext[mcp]` — NOT the AG2 fork (`ag2-agentchat`) or `pyautogen`. The fork split renamed packages; `autogen-ext` (Microsoft) is the correct distribution.

## Bootstrap

```bash
sh framework-matrix/bootstrap_venv.sh autogen
```

## Run

```bash
framework-matrix/autogen/.venv/bin/pytest framework-matrix/autogen/ -m framework -v
```
