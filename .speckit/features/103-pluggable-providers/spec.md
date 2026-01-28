# Feature Specification: Pluggable Model Providers

**Feature Branch**: `103-pluggable-providers`
**Created**: 2025-12-18
**Status**: Draft
**Input**: Product Roadmap Phase 5

## User Scenarios & Testing

### User Story 1 - Switch Embedding Provider (Priority: P1)

A user wants to use a different embedding model provider than the default OpenAI to reduce costs or use local models.

**Why this priority**: Core capability for provider flexibility. Many users want Ollama for local/offline operation.

**Independent Test**: Configure Ollama embeddings in config.yaml, index documents, verify embeddings work.

**Acceptance Scenarios**:

1. **Given** config.yaml with `embedding.provider: ollama`, **When** server starts, **Then** it uses Ollama for embeddings
2. **Given** config.yaml with `embedding.provider: openai`, **When** server starts, **Then** it uses OpenAI (current default)
3. **Given** config.yaml with `embedding.provider: cohere`, **When** server starts, **Then** it uses Cohere embeddings
4. **Given** invalid provider specified, **When** server starts, **Then** it fails with descriptive error message

---

### User Story 2 - Switch Summarization LLM (Priority: P1)

A user wants to use a different LLM for summarization/extraction than the default Claude Haiku.

**Why this priority**: Summarization is used for context injection. Users may prefer different models for cost or quality.

**Independent Test**: Configure GPT-4o for summarization, index documents, verify summaries are generated.

**Acceptance Scenarios**:

1. **Given** config with `summarization.provider: openai`, **When** indexing, **Then** GPT-4o generates summaries
2. **Given** config with `summarization.provider: ollama`, **When** indexing, **Then** local Llama model generates summaries
3. **Given** config with `summarization.provider: gemini`, **When** indexing, **Then** Gemini generates summaries
4. **Given** config with `summarization.provider: grok`, **When** indexing, **Then** Grok generates summaries via OpenAI-compatible endpoint

---

### User Story 3 - Configuration via YAML File (Priority: P1)

Users configure providers via a simple YAML configuration file without code changes.

**Why this priority**: Configuration-driven is the goal. No code changes should be required.

**Independent Test**: Create config.yaml, start server, verify configured providers are used.

**Acceptance Scenarios**:

1. **Given** config.yaml in project root, **When** server starts, **Then** it loads and applies configuration
2. **Given** config.yaml with all settings, **When** validated, **Then** all required fields are present
3. **Given** environment variable `DOC_SERVE_CONFIG`, **When** set, **Then** server loads config from that path
4. **Given** no config.yaml exists, **When** server starts, **Then** it uses sensible defaults (current behavior)

---

### User Story 4 - Run Completely Offline with Ollama (Priority: P2)

A user wants to run doc-serve entirely locally without any external API calls for privacy reasons.

**Why this priority**: Key value proposition for privacy-conscious users. Enables air-gapped operation.

**Independent Test**: Configure Ollama for both embeddings and summarization, disconnect from internet, verify full functionality.

**Acceptance Scenarios**:

1. **Given** Ollama configured for embeddings and summarization, **When** offline, **Then** indexing works
2. **Given** Ollama configured, **When** querying, **Then** no external API calls are made
3. **Given** Ollama models downloaded, **When** first query after restart, **Then** response time < 5 seconds
4. **Given** local-only configuration, **When** API keys not set, **Then** server starts without errors

---

### User Story 5 - API Key Management via Environment (Priority: P2)

API keys for providers are managed securely via environment variables referenced in config.

**Why this priority**: Security best practice. Keys should not be in config files.

**Independent Test**: Configure provider with `api_key_env: OPENAI_API_KEY`, verify key is read from environment.

**Acceptance Scenarios**:

1. **Given** config with `params.api_key_env: OPENAI_API_KEY`, **When** server starts, **Then** it reads key from environment
2. **Given** environment variable not set, **When** server starts with that provider, **Then** it fails with clear error
3. **Given** multiple providers configured, **When** each has different key env vars, **Then** all are read correctly
4. **Given** Ollama provider (no key needed), **When** configured, **Then** no API key validation occurs

---

### Edge Cases

- What happens when switching providers with existing index? (Re-indexing required, warn user)
- How does system handle model not found in provider? (Descriptive error with available models)
- What happens when provider API is temporarily unavailable? (Retry with backoff, fail gracefully)
- How does system handle embedding dimension mismatch? (Error during indexing, not silently corrupt index)
- What happens when mixing providers across restarts? (Detect mismatch, require re-index)

## Requirements

### Functional Requirements

- **FR-001**: System MUST support configuration via `config.yaml` file
- **FR-002**: System MUST support OpenAI, Ollama, and Cohere embedding providers
- **FR-003**: System MUST support Anthropic, OpenAI, Gemini, Grok, and Ollama summarization providers
- **FR-004**: Configuration MUST NOT require code changes to switch providers
- **FR-005**: API keys MUST be read from environment variables, not stored in config
- **FR-006**: System MUST validate provider configuration on startup
- **FR-007**: System MUST detect embedding dimension mismatches and prevent index corruption
- **FR-008**: System MUST log which providers are in use on startup
- **FR-009**: System MUST support Ollama for completely offline operation
- **FR-010**: Provider switch with existing index MUST require explicit re-indexing

### Supported Providers

**Embeddings:**
| Provider | Models | Authentication |
|----------|--------|----------------|
| OpenAI | text-embedding-3-small/large, ada-002 | API key |
| Ollama | nomic-embed-text, bge, mxbai-embed-large | None (local) |
| Cohere | embed-english-v3, embed-multilingual-v3 | API key |

**Note:** Grok and Gemini do NOT provide public embedding APIs.

**Summarization/LLM:**
| Provider | Models | Authentication |
|----------|--------|----------------|
| Anthropic | Claude Haiku, Sonnet, Opus | API key |
| OpenAI | GPT-4o, GPT-4o-mini, GPT-3.5 | API key |
| Gemini | gemini-1.5-flash, gemini-1.5-pro | API key |
| Grok | grok-beta | API key (OpenAI-compatible) |
| Ollama | llama3, mistral, qwen | None (local) |

### Key Entities

- **ProviderConfig**: Configuration for embedding or summarization provider
- **EmbeddingProvider**: Abstract interface for embedding generation
- **SummarizationProvider**: Abstract interface for text summarization
- **ConfigLoader**: Reads and validates config.yaml
- **ProviderFactory**: Creates provider instances from configuration

## Success Criteria

### Measurable Outcomes

- **SC-001**: Switching providers requires only config.yaml change, no code changes
- **SC-002**: Ollama enables fully offline operation for both embeddings and summarization
- **SC-003**: All Phase 1-4 functionality remains working with any supported provider
- **SC-004**: Provider configuration is validated on startup with clear error messages
- **SC-005**: API keys are never logged or exposed in error messages
- **SC-006**: Documentation includes setup guides for each supported provider
