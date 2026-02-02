# Research: Pluggable Model Providers

**Feature**: 103-pluggable-providers
**Date**: 2026-02-01
**Status**: Complete

## Research Tasks

### 1. Current Architecture Analysis

**Question**: How are embeddings and summarization currently implemented?

**Findings**:

The current implementation in `agent-brain-server/agent_brain_server/indexing/embedding.py` uses:

1. **Embeddings**: Hard-coded to OpenAI's `AsyncOpenAI` client
   - Initialized in `EmbeddingGenerator.__init__()` (line 43-45)
   - Uses `settings.OPENAI_API_KEY` and `settings.EMBEDDING_MODEL`
   - Model dimensions hard-coded in dictionary (line 170-175)

2. **Summarization**: Hard-coded to Anthropic's `AsyncAnthropic` client
   - Initialized in same class (line 48-50)
   - Uses `settings.ANTHROPIC_API_KEY` and `settings.CLAUDE_MODEL`
   - Fixed prompt template for code summarization

3. **Singleton Pattern**: Global `_embedding_generator` with `get_embedding_generator()`
   - Makes provider swapping difficult at runtime
   - No abstract interface for mocking in tests

**Decision**: Refactor to Protocol-based design with Factory pattern.
**Rationale**: Enables runtime provider selection, improves testability, follows existing DI patterns in services.
**Alternatives Rejected**:
- ABC base class: More verbose, requires inheritance
- Direct if/else switching: Would require changes throughout codebase

---

### 2. LlamaIndex Provider Integration

**Question**: What LlamaIndex abstractions exist for our target providers?

**Findings**:

LlamaIndex provides embedding integrations via separate packages:

| Provider | Package | Async Support | Notes |
|----------|---------|---------------|-------|
| OpenAI | `llama-index-embeddings-openai` | ✅ Yes | Already installed |
| Ollama | `llama-index-embeddings-ollama` | ✅ Yes | OpenAI-compatible API |
| Cohere | `llama-index-embeddings-cohere` | ✅ Yes | Requires `cohere` SDK |
| Bedrock | `llama-index-embeddings-bedrock` | ✅ Yes | Future: Phase 7 |

LlamaIndex LLM integrations for summarization:

| Provider | Package | Async Support | Notes |
|----------|---------|---------------|-------|
| Anthropic | `llama-index-llms-anthropic` | ✅ Yes | Available but not used currently |
| OpenAI | `llama-index-llms-openai` | ✅ Yes | Already installed |
| Gemini | `llama-index-llms-gemini` | ⚠️ Partial | Requires wrapper |
| Ollama | `llama-index-llms-ollama` | ✅ Yes | OpenAI-compatible |

**Decision**: Use native SDK clients instead of LlamaIndex LLM wrappers.
**Rationale**:
- Direct control over prompts and parameters
- Simpler error handling
- Fewer dependencies
- Current implementation already uses native clients
**Alternatives Rejected**: LlamaIndex LLM wrappers (less control, extra abstraction layer)

---

### 3. Provider Authentication Patterns

**Question**: How do each provider handle authentication?

**Findings**:

| Provider | Auth Method | Environment Variable | SDK Support |
|----------|-------------|---------------------|-------------|
| OpenAI | API Key | `OPENAI_API_KEY` | Native |
| Anthropic | API Key | `ANTHROPIC_API_KEY` | Native |
| Cohere | API Key | `COHERE_API_KEY` | Native |
| Gemini | API Key | `GOOGLE_API_KEY` | Native |
| Grok | API Key | `GROK_API_KEY` | OpenAI-compatible |
| Ollama | None | N/A | Local HTTP |

**Decision**: Use `api_key_env` field in config to reference environment variable names.
**Rationale**:
- Keeps secrets out of config files
- Follows existing pattern in settings.py
- Supports different keys for different providers
**Alternatives Rejected**:
- Direct API keys in config (security risk)
- Single environment variable (inflexible)

---

### 4. Embedding Dimension Handling

**Question**: How to handle different embedding dimensions across providers?

**Findings**:

| Provider | Model | Dimensions |
|----------|-------|------------|
| OpenAI | text-embedding-3-large | 3072 |
| OpenAI | text-embedding-3-small | 1536 |
| OpenAI | text-embedding-ada-002 | 1536 |
| Ollama | nomic-embed-text | 768 |
| Ollama | mxbai-embed-large | 1024 |
| Cohere | embed-english-v3 | 1024 |
| Cohere | embed-multilingual-v3 | 1024 |

**Critical Issue**: ChromaDB collections are created with fixed dimensions. Switching providers with different dimensions requires re-indexing.

**Decision**:
1. Store embedding provider/model in index metadata
2. Validate on startup: if provider/model changed, require explicit re-index
3. Provide `get_dimensions()` method on EmbeddingProvider protocol

**Rationale**: Prevents silent index corruption.
**Alternatives Rejected**: Auto-reindex (too slow, could be destructive)

---

### 5. Ollama Integration Patterns

**Question**: Best practices for Ollama integration?

**Findings**:

Ollama provides an OpenAI-compatible API:
- Base URL: `http://localhost:11434/v1`
- Embedding endpoint: `/embeddings`
- Chat endpoint: `/chat/completions`

Two integration approaches:

1. **Native Ollama client** (`ollama` package):
   ```python
   import ollama
   response = await ollama.embeddings(model="nomic-embed-text", prompt="text")
   ```

2. **OpenAI client with custom base_url**:
   ```python
   client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
   response = await client.embeddings.create(model="nomic-embed-text", input="text")
   ```

**Decision**: Use OpenAI client with custom base_url.
**Rationale**:
- Reuse existing OpenAI provider code
- Consistent async patterns
- Fewer dependencies
**Alternatives Rejected**: Native ollama package (different API, new dependency)

---

### 6. Grok Integration

**Question**: How to integrate Grok (xAI)?

**Findings**:

Grok uses an OpenAI-compatible API:
- Base URL: `https://api.x.ai/v1`
- API Key: Required via `x-api-key` header
- Models: `grok-4`, `grok-4-fast`

**Decision**: Reuse OpenAI provider with custom base_url and header.
**Rationale**: Minimal code, proven pattern.
**Alternatives Rejected**: Separate implementation (unnecessary duplication)

---

### 7. Gemini Integration

**Question**: How to integrate Google Gemini?

**Findings**:

Gemini SDK (`google-generativeai`):
```python
import google.generativeai as genai
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-3-flash")
response = await model.generate_content_async("prompt")
```

Key considerations:
- Async support via `generate_content_async()`
- No embedding API (Gemini doesn't provide embeddings)
- Only usable for summarization, not embeddings

**Decision**: Gemini for summarization only; use Vertex AI (Phase 8) for embeddings.
**Rationale**: Gemini API doesn't expose embeddings.
**Alternatives Rejected**: None (technical limitation)

---

### 8. Configuration File Format

**Question**: What format should config.yaml use?

**Findings**:

Proposed structure:

```yaml
# config.yaml
embedding:
  provider: openai  # openai | ollama | cohere
  model: text-embedding-3-large
  api_key_env: OPENAI_API_KEY
  params:
    batch_size: 100

summarization:
  provider: anthropic  # anthropic | openai | gemini | grok | ollama
  model: claude-haiku-4-5-20251001
  api_key_env: ANTHROPIC_API_KEY
  params:
    max_tokens: 300
    temperature: 0.1
```

Config loading precedence:
1. Environment variables (highest)
2. config.yaml in project root
3. Default values (lowest)

**Decision**: YAML with nested provider config.
**Rationale**: Human-readable, supports comments, familiar to developers.
**Alternatives Rejected**:
- JSON (no comments, harder to read)
- TOML (less familiar)
- Flat environment variables (complex nesting)

---

### 9. Error Handling Strategy

**Question**: How to handle provider-specific errors?

**Findings**:

Common error scenarios:
1. API key missing/invalid → Startup failure with clear message
2. Model not found → Startup failure with available models
3. Rate limit → Retry with exponential backoff
4. Network timeout → Retry, then fail with context
5. Ollama not running → Clear error with troubleshooting steps

**Decision**: Wrap provider-specific exceptions in common `ProviderError` hierarchy.
**Rationale**: Consistent error handling across providers.
**Alternatives Rejected**: Pass-through exceptions (inconsistent, hard to handle)

---

### 10. Testing Strategy

**Question**: How to test providers without hitting real APIs?

**Findings**:

Testing approaches:
1. **Unit tests**: Mock SDK clients at method level
2. **Integration tests**: Use pytest fixtures with mock servers
3. **Contract tests**: Record/replay with VCR.py or similar
4. **Ollama tests**: Use local Ollama instance in CI (optional)

**Decision**: Mock SDK clients for unit tests; optional integration tests with real providers.
**Rationale**: Fast CI, optional manual validation.
**Alternatives Rejected**:
- VCR.py (complex setup, cassette management)
- Always-real API calls (slow, expensive, flaky)

---

## Summary of Key Decisions

| Area | Decision | Impact |
|------|----------|--------|
| Architecture | Protocol + Factory pattern | Extensible, testable |
| Config format | YAML with nested providers | Human-readable |
| LlamaIndex | Native SDKs, not LLM wrappers | Direct control |
| Ollama | OpenAI-compatible client | Code reuse |
| Grok | OpenAI-compatible client | Code reuse |
| Gemini | Summarization only | API limitation |
| Dimensions | Validate on startup | Prevent corruption |
| Auth | api_key_env references | Secure |
| Errors | Common ProviderError | Consistent |
| Testing | Mock SDKs | Fast CI |

## Open Questions Resolved

- ✅ How to handle dimension mismatches? → Validate on startup, require re-index
- ✅ Should we use LlamaIndex wrappers? → No, use native SDKs
- ✅ How to support Ollama offline? → OpenAI-compatible client with local URL
- ✅ Can Gemini do embeddings? → No, summarization only
- ✅ How to test without API keys? → Mock SDK clients
