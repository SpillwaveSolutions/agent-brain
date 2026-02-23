# Configuration Guide

## Environment Variables

### Required
- `OPENAI_API_KEY` — OpenAI API key for generating embeddings
- `ANTHROPIC_API_KEY` — Anthropic API key for code summarization

### Optional
- `EMBEDDING_MODEL` — Embedding model (default: text-embedding-3-large)
- `CLAUDE_MODEL` — Summarization model (default: claude-haiku-4-5-20251001)
- `API_HOST` — Server bind address (default: 127.0.0.1)
- `API_PORT` — Server port (default: 8000)

## Multi-Instance Support

Agent Brain supports running multiple instances for different projects.
Each instance uses a separate state directory and port.

Use `agent-brain init` to initialize a project directory, then
`agent-brain start` to launch the instance with auto-allocated port.

## Provider Configuration

Embedding providers: OpenAI, Cohere, HuggingFace (local).
Summarization providers: Anthropic Claude, OpenAI GPT.
