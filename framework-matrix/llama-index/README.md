# FRAME-03: LlamaIndex — llama-index-tools-mcp smoke test

Connects to `agent-brain-mcp` over stdio via `BasicMCPClient` + `McpToolSpec`,
surfaces `search_documents` as a LlamaIndex `FunctionTool`, calls it directly
(no LLM loop), and asserts a non-empty result against the seeded corpus.

**Bootstrap and run:**

```sh
sh framework-matrix/bootstrap_venv.sh llama-index
framework-matrix/llama-index/.venv/bin/pytest framework-matrix/llama-index/ -m framework -v
```
