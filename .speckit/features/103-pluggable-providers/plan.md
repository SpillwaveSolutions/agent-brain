# Implementation Plan: Pluggable Model Providers

**Branch**: `103-pluggable-providers` | **Date**: 2026-02-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `.speckit/features/103-pluggable-providers/spec.md`

## Summary

Implement configuration-driven model provider selection using LlamaIndex abstractions, enabling users to switch between OpenAI, Ollama, Cohere (embeddings) and Anthropic, OpenAI, Gemini, Grok, Ollama (summarization) providers without code changes. The implementation uses Protocol-based abstractions with a Factory pattern for provider instantiation, supporting YAML configuration and secure API key management via environment variables.

## Technical Context

**Language/Version**: Python 3.10+ (existing: ^3.10 in pyproject.toml)
**Primary Dependencies**: FastAPI, LlamaIndex, Pydantic, httpx (async HTTP), anthropic, openai, google-generativeai (new)
**Storage**: ChromaDB (vector), disk-based BM25 index (existing)
**Testing**: pytest with pytest-asyncio, pytest-mock
**Target Platform**: Linux/macOS server, local development
**Project Type**: Monorepo with agent-brain-server as primary package
**Performance Goals**: Embedding latency <500ms for single text, <5s for 100-text batch
**Constraints**: Must maintain backward compatibility with existing configs, no breaking API changes
**Scale/Scope**: Support 3 embedding providers, 5 summarization providers, config validation on startup

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence/Notes |
|-----------|--------|----------------|
| **I. Monorepo Modularity** | ✅ PASS | Provider abstraction lives in agent-brain-server; CLI/skill remain unchanged |
| **II. OpenAPI-First** | ✅ PASS | No API changes required; providers are internal implementation detail |
| **III. Test-Alongside** | ✅ PASS | Plan includes unit tests per provider, integration tests for factory |
| **IV. Observability** | ✅ PASS | Startup logging of provider selection; metrics for embedding latency |
| **V. Simplicity** | ✅ PASS | Protocol + Factory is minimal abstraction; 3 new dependencies only |

**Technology Stack Compliance**:
- FastAPI: ✅ Unchanged
- LlamaIndex: ✅ Using existing abstractions where available
- ChromaDB: ✅ Unchanged (embeddings are provider-agnostic)
- Embeddings: ⚠️ Adding Ollama, Cohere alongside OpenAI (constitution amendment needed)
- Summarization: ⚠️ Adding OpenAI, Gemini, Grok, Ollama alongside Anthropic (constitution amendment needed)

**Constitution Amendment Required**: Technology Stack section needs update to reflect pluggable providers as approved design pattern.

## Project Structure

### Documentation (this feature)

```text
.speckit/features/103-pluggable-providers/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (internal contracts)
│   └── provider-protocols.md
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
agent-brain-server/
├── agent_brain_server/
│   ├── config/
│   │   ├── settings.py          # Extended with provider settings
│   │   └── provider_config.py   # NEW: YAML config loader for providers
│   ├── providers/               # NEW: Provider abstractions
│   │   ├── __init__.py
│   │   ├── base.py              # Protocol definitions
│   │   ├── factory.py           # Provider factory
│   │   ├── embedding/           # Embedding providers
│   │   │   ├── __init__.py
│   │   │   ├── openai.py
│   │   │   ├── ollama.py
│   │   │   └── cohere.py
│   │   └── summarization/       # Summarization providers
│   │       ├── __init__.py
│   │       ├── anthropic.py
│   │       ├── openai.py
│   │       ├── gemini.py
│   │       ├── grok.py
│   │       └── ollama.py
│   ├── indexing/
│   │   └── embedding.py         # Refactored to use provider abstraction
│   └── services/
│       └── indexing_service.py  # Updated to use factory
└── tests/
    ├── unit/
    │   └── providers/           # NEW: Provider unit tests
    │       ├── test_factory.py
    │       ├── test_openai_embedding.py
    │       ├── test_ollama_embedding.py
    │       └── ...
    └── integration/
        └── test_provider_switching.py  # NEW: Integration tests
```

**Structure Decision**: Extends existing monorepo structure with new `providers/` package. Maintains clean separation between embedding and summarization providers, enabling independent testing and future additions.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New `providers/` package (6+ files) | Each provider has distinct authentication, client initialization, and error handling | Single file would exceed 500 LOC and violate SRP |
| Protocol + Factory pattern | Enables runtime provider selection without conditionals throughout codebase | Direct if/else would require changes to indexing_service, query_service, embedding.py |
| 3 new dependencies (google-generativeai, cohere, ollama) | Required for provider support | Using raw HTTP would lose SDK features (retries, validation, async) |

## Phase 0: Research Summary

See [research.md](./research.md) for full details.

### Key Decisions

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Protocol-based abstraction | Type-safe, IDE-friendly, minimal overhead | ABC (more verbose), duck typing (less safe) |
| YAML config over JSON | Human-readable, supports comments | JSON (harder to maintain), TOML (less familiar) |
| Factory with registry | Extensible, testable, single point of instantiation | Service locator (hidden dependencies), DI container (overkill) |
| Separate embedding/summarization | Different interfaces, independent scaling | Combined interface (violates SRP) |

### Provider-Specific Notes

**Embeddings:**
- OpenAI: Existing implementation, refactor to Protocol
- Ollama: Uses OpenAI-compatible API, simple HTTP client
- Cohere: SDK available, async support

**Summarization:**
- Anthropic: Existing implementation, refactor to Protocol
- OpenAI: Chat completion API, async SDK
- Gemini: google-generativeai SDK, async support via asyncio
- Grok: OpenAI-compatible endpoint, reuse OpenAI client
- Ollama: OpenAI-compatible chat API

## Phase 1: Design Artifacts

### Data Model

See [data-model.md](./data-model.md) for entity definitions.

Key entities:
- `ProviderType` (enum): openai, ollama, cohere, anthropic, gemini, grok
- `EmbeddingConfig`: provider, model, api_key_env, params
- `SummarizationConfig`: provider, model, api_key_env, params
- `ProviderSettings`: embedding, summarization (top-level YAML structure)

### Contracts

See [contracts/provider-protocols.md](./contracts/provider-protocols.md) for Protocol definitions.

Key protocols:
- `EmbeddingProvider`: embed_text, embed_texts, get_dimensions
- `SummarizationProvider`: summarize
- `ProviderFactory`: get_embedding_provider, get_summarization_provider

### Quickstart

See [quickstart.md](./quickstart.md) for user-facing configuration examples.

## Implementation Phases

### Phase 2: Tasks (Generated by /speckit.tasks)

Tasks will be generated covering:
1. Create provider Protocols and base classes
2. Implement embedding providers (OpenAI refactor, Ollama, Cohere)
3. Implement summarization providers (Anthropic refactor, OpenAI, Gemini, Grok, Ollama)
4. Create ProviderFactory with registry
5. Add YAML configuration loading
6. Refactor EmbeddingGenerator to use providers
7. Update settings.py with provider configuration
8. Write unit tests for each provider
9. Write integration tests for provider switching
10. Update documentation

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Provider API changes | Medium | Medium | Pin SDK versions, integration tests |
| Embedding dimension mismatch | Medium | High | Validate on startup, error on mismatch |
| Ollama not running locally | High | Low | Clear error message, health check |
| API key misconfiguration | Medium | Medium | Startup validation, descriptive errors |

## Dependencies

**New Python packages:**
- `cohere` - Cohere SDK
- `google-generativeai` - Gemini SDK
- `ollama` - Ollama Python client (optional, can use httpx)

**Optional:**
- `llama-index-embeddings-ollama` - LlamaIndex Ollama integration
- `llama-index-embeddings-cohere` - LlamaIndex Cohere integration

## Success Metrics

- [ ] All 10 acceptance scenarios from spec pass
- [ ] Provider switch requires only config.yaml change
- [ ] Offline operation works with Ollama
- [ ] No decrease in test coverage
- [ ] Startup logs show active providers
- [ ] API keys never logged
