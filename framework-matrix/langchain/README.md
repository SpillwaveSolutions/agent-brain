# FRAME-02: LangChain — langchain-mcp-adapters smoke test

Connects to `agent-brain-mcp` over stdio via `MultiServerMCPClient`, surfaces
`search_documents` as a LangChain `BaseTool`, invokes it directly (no LLM loop),
and asserts a non-empty result against the seeded corpus.

**Bootstrap and run:**

```sh
sh framework-matrix/bootstrap_venv.sh langchain
framework-matrix/langchain/.venv/bin/pytest framework-matrix/langchain/ -m framework -v
```
