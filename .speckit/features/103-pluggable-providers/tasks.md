# Tasks: Pluggable Model Providers

**Input**: Design documents from `.speckit/features/103-pluggable-providers/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/provider-protocols.md

**Tests**: Tests are REQUIRED per constitution principle III (Test-Alongside). Unit tests for each provider, integration tests for factory.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

All paths relative to `agent-brain-server/`:
- Source: `agent_brain_server/`
- Tests: `tests/`

---

## Phase 1: Setup (Shared Infrastructure) ✅ COMPLETE

**Purpose**: Project initialization, new dependencies, and provider package structure

- [x] T001 Add new dependencies to `agent-brain-server/pyproject.toml`: cohere, google-generativeai, pyyaml
- [x] T002 [P] Create providers package structure in `agent_brain_server/providers/__init__.py`
- [x] T003 [P] Create embedding subpackage in `agent_brain_server/providers/embedding/__init__.py`
- [x] T004 [P] Create summarization subpackage in `agent_brain_server/providers/summarization/__init__.py`
- [x] T005 [P] Create tests directory structure in `tests/unit/providers/`

---

## Phase 2: Foundational (Blocking Prerequisites) ✅ COMPLETE

**Purpose**: Core abstractions and configuration infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Configuration Models (from data-model.md)

- [x] T006 [P] Create `EmbeddingProviderType` enum in `agent_brain_server/providers/base.py`
- [x] T007 [P] Create `SummarizationProviderType` enum in `agent_brain_server/providers/base.py`
- [x] T008 [P] Create `EmbeddingConfig` Pydantic model in `agent_brain_server/config/provider_config.py`
- [x] T009 [P] Create `SummarizationConfig` Pydantic model in `agent_brain_server/config/provider_config.py`
- [x] T010 Create `ProviderSettings` top-level config model in `agent_brain_server/config/provider_config.py`

### Protocol Definitions (from contracts/)

- [x] T011 [P] Create `EmbeddingProvider` Protocol in `agent_brain_server/providers/base.py`
- [x] T012 [P] Create `SummarizationProvider` Protocol in `agent_brain_server/providers/base.py`
- [x] T013 [P] Create `BaseEmbeddingProvider` abstract class in `agent_brain_server/providers/base.py`
- [x] T014 [P] Create `BaseSummarizationProvider` abstract class in `agent_brain_server/providers/base.py`

### Exception Hierarchy

- [x] T015 Create `ProviderError` exception hierarchy in `agent_brain_server/providers/exceptions.py`:
  - `ProviderError` (base)
  - `ConfigurationError`
  - `AuthenticationError`
  - `ProviderNotFoundError`
  - `ProviderMismatchError`
  - `RateLimitError`
  - `ModelNotFoundError`

### Provider Factory

- [x] T016 Create `ProviderRegistry` factory in `agent_brain_server/providers/factory.py` with:
  - `register_embedding_provider()` method
  - `register_summarization_provider()` method
  - `get_embedding_provider()` method
  - `get_summarization_provider()` method
  - `clear_cache()` method for testing

### Unit Tests for Foundation

- [x] T017 [P] Unit test for `EmbeddingConfig` validation in `tests/unit/providers/test_config.py`
- [x] T018 [P] Unit test for `SummarizationConfig` validation in `tests/unit/providers/test_config.py`
- [x] T019 Unit test for `ProviderRegistry` factory in `tests/unit/providers/test_factory.py`

**Checkpoint**: Foundation ready - core abstractions and factory in place ✅

---

## Phase 3: User Story 1 - Switch Embedding Provider (Priority: P1) 🎯 MVP ✅ COMPLETE

**Goal**: Users can switch embedding providers (OpenAI, Ollama, Cohere) via config.yaml

**Independent Test**: Configure Ollama embeddings in config.yaml, start server, verify embeddings work

### Tests for User Story 1

- [x] T020 [P] [US1] Unit test for `OpenAIEmbeddingProvider` in `tests/unit/providers/test_openai_embedding.py`
- [x] T021 [P] [US1] Unit test for `OllamaEmbeddingProvider` in `tests/unit/providers/test_ollama_embedding.py`
- [ ] T022 [P] [US1] Unit test for `CohereEmbeddingProvider` in `tests/unit/providers/test_cohere_embedding.py` (provider implemented, tests pending)

### Implementation for User Story 1

- [x] T023 [P] [US1] Implement `OpenAIEmbeddingProvider` in `agent_brain_server/providers/embedding/openai.py`:
  - Refactor from existing `EmbeddingGenerator` OpenAI code
  - Implement `EmbeddingProvider` protocol
  - Support `embed_text()`, `embed_texts()`, `get_dimensions()`
  - Model dimension mapping for text-embedding-3-large/small, ada-002
- [x] T024 [P] [US1] Implement `OllamaEmbeddingProvider` in `agent_brain_server/providers/embedding/ollama.py`:
  - Use OpenAI-compatible client with custom base_url
  - Support nomic-embed-text, mxbai-embed-large models
  - Implement `EmbeddingProvider` protocol
- [x] T025 [P] [US1] Implement `CohereEmbeddingProvider` in `agent_brain_server/providers/embedding/cohere.py`:
  - Use Cohere SDK async client
  - Support embed-english-v3, embed-multilingual-v3 models
  - Implement `EmbeddingProvider` protocol
- [x] T026 [US1] Register embedding providers in `agent_brain_server/providers/embedding/__init__.py`
- [x] T027 [US1] Add startup logging for embedding provider selection in `agent_brain_server/api/main.py`

**Checkpoint**: User Story 1 complete - embedding providers switchable via config ✅

---

## Phase 4: User Story 2 - Switch Summarization LLM (Priority: P1) 🎯 MVP ✅ COMPLETE

**Goal**: Users can switch summarization providers (Anthropic, OpenAI, Gemini, Grok, Ollama) via config

**Independent Test**: Configure GPT-4o for summarization, index documents, verify summaries generated

### Tests for User Story 2

- [x] T028 [P] [US2] Unit test for `AnthropicSummarizationProvider` in `tests/unit/providers/test_anthropic_summarization.py`
- [ ] T029 [P] [US2] Unit test for `OpenAISummarizationProvider` in `tests/unit/providers/test_openai_summarization.py` (provider implemented, tests pending)
- [ ] T030 [P] [US2] Unit test for `GeminiSummarizationProvider` in `tests/unit/providers/test_gemini_summarization.py` (provider implemented, tests pending)
- [ ] T031 [P] [US2] Unit test for `GrokSummarizationProvider` in `tests/unit/providers/test_grok_summarization.py` (provider implemented, tests pending)
- [ ] T032 [P] [US2] Unit test for `OllamaSummarizationProvider` in `tests/unit/providers/test_ollama_summarization.py` (provider implemented, tests pending)

### Implementation for User Story 2

- [x] T033 [P] [US2] Implement `AnthropicSummarizationProvider` in `agent_brain_server/providers/summarization/anthropic.py`:
  - Refactor from existing `EmbeddingGenerator` Anthropic code
  - Implement `SummarizationProvider` protocol
  - Support `summarize()` and `generate()` methods
- [x] T034 [P] [US2] Implement `OpenAISummarizationProvider` in `agent_brain_server/providers/summarization/openai.py`:
  - Use OpenAI chat completion API
  - Implement `SummarizationProvider` protocol
- [x] T035 [P] [US2] Implement `GeminiSummarizationProvider` in `agent_brain_server/providers/summarization/gemini.py`:
  - Use google-generativeai SDK
  - Implement `SummarizationProvider` protocol
  - Use `generate_content_async()` for async support
- [x] T036 [P] [US2] Implement `GrokSummarizationProvider` in `agent_brain_server/providers/summarization/grok.py`:
  - Use OpenAI client with custom base_url (https://api.x.ai/v1)
  - Implement `SummarizationProvider` protocol
- [x] T037 [P] [US2] Implement `OllamaSummarizationProvider` in `agent_brain_server/providers/summarization/ollama.py`:
  - Use OpenAI-compatible client with local base_url
  - Implement `SummarizationProvider` protocol
- [x] T038 [US2] Register summarization providers in `agent_brain_server/providers/summarization/__init__.py`
- [x] T039 [US2] Add startup logging for summarization provider selection in `agent_brain_server/api/main.py`

**Checkpoint**: User Story 2 complete - summarization providers switchable via config ✅

---

## Phase 5: User Story 3 - Configuration via YAML File (Priority: P1) 🎯 MVP ✅ COMPLETE

**Goal**: Users configure providers via config.yaml without code changes

**Independent Test**: Create config.yaml, start server, verify configured providers are used

### Tests for User Story 3

- [x] T040 [P] [US3] Unit test for YAML config loading in `tests/unit/providers/test_config.py` (combined in test_config.py)
- [x] T041 [P] [US3] Unit test for config validation in `tests/unit/providers/test_config.py` (combined in test_config.py)
- [ ] T042 [US3] Integration test for config loading precedence in `tests/integration/test_provider_config.py`

### Implementation for User Story 3

- [x] T043 [US3] Implement `load_provider_settings()` function in `agent_brain_server/config/provider_config.py`:
  - Load config.yaml from project root
  - Support `DOC_SERVE_CONFIG` env var override
  - Fall back to sensible defaults (OpenAI + Anthropic)
- [x] T044 [US3] Implement config validation with descriptive error messages in `agent_brain_server/config/provider_config.py`
- [x] T045 [US3] Add config file discovery logic (project root, state dir) in `agent_brain_server/config/provider_config.py`
- [x] T046 [US3] Update `settings.py` to integrate with provider configuration in `agent_brain_server/config/settings.py`

**Checkpoint**: User Story 3 complete - YAML configuration fully functional ✅

---

## Phase 6: User Story 4 - Run Completely Offline with Ollama (Priority: P2)

**Goal**: Users can run Agent Brain entirely locally without external API calls

**Independent Test**: Configure Ollama for both, disconnect internet, verify full functionality

### Tests for User Story 4

- [ ] T047 [P] [US4] Unit test for Ollama-only config validation in `tests/unit/providers/test_offline_config.py`
- [ ] T048 [US4] Integration test for offline operation in `tests/integration/test_offline_operation.py`

### Implementation for User Story 4

- [ ] T049 [US4] Add Ollama health check in `agent_brain_server/providers/embedding/ollama.py`
- [ ] T050 [US4] Add Ollama health check in `agent_brain_server/providers/summarization/ollama.py`
- [ ] T051 [US4] Skip API key validation when provider is Ollama in `agent_brain_server/config/provider_config.py`
- [ ] T052 [US4] Add clear error messages when Ollama not running in `agent_brain_server/providers/exceptions.py`

**Checkpoint**: User Story 4 complete - fully offline operation works

---

## Phase 7: User Story 5 - API Key Management via Environment (Priority: P2)

**Goal**: API keys are securely managed via environment variables referenced in config

**Independent Test**: Configure provider with `api_key_env: OPENAI_API_KEY`, verify key read from env

### Tests for User Story 5

- [ ] T053 [P] [US5] Unit test for api_key_env resolution in `tests/unit/providers/test_api_key_resolution.py`
- [ ] T054 [P] [US5] Unit test for missing API key error in `tests/unit/providers/test_api_key_errors.py`
- [ ] T055 [US5] Integration test for secure key handling in `tests/integration/test_api_key_security.py`

### Implementation for User Story 5

- [ ] T056 [US5] Implement `resolve_api_key()` helper in `agent_brain_server/config/provider_config.py`:
  - Read key from environment variable specified in `api_key_env`
  - Raise `AuthenticationError` if not found
  - Skip validation for Ollama (no key needed)
- [ ] T057 [US5] Ensure API keys are never logged in `agent_brain_server/providers/base.py`
- [ ] T058 [US5] Add key masking in error messages in `agent_brain_server/providers/exceptions.py`

**Checkpoint**: User Story 5 complete - secure API key management works

---

## Phase 8: Service Integration (Partially Complete)

**Purpose**: Integrate providers with existing services

### Refactor Existing Code

- [x] T059 Refactor `EmbeddingGenerator` in `agent_brain_server/indexing/embedding.py`:
  - Remove hard-coded OpenAI client initialization
  - Accept `EmbeddingProvider` via dependency injection
  - Accept `SummarizationProvider` via dependency injection
  - Delegate to provider instances
- [ ] T060 Update `IndexingService` in `agent_brain_server/services/indexing_service.py`:
  - Use `ProviderRegistry` to get providers from config
  - Pass providers to `EmbeddingGenerator`
- [ ] T061 Update `QueryService` in `agent_brain_server/services/query_service.py`:
  - Use `ProviderRegistry` for embedding provider
- [x] T062 Update server startup in `agent_brain_server/api/main.py`:
  - Load provider configuration
  - Validate config before starting
  - Log active providers

### Index Metadata for Provider Tracking

- [ ] T063 Create `IndexMetadata` model in `agent_brain_server/models/index_metadata.py`
- [ ] T064 Implement metadata storage/retrieval in `agent_brain_server/storage/metadata_store.py`
- [ ] T065 Add provider mismatch detection on startup in `agent_brain_server/services/indexing_service.py`

### Integration Tests

- [ ] T066 Integration test for provider switching in `tests/integration/test_provider_switching.py`
- [ ] T067 Integration test for index metadata validation in `tests/integration/test_index_metadata.py`

**Checkpoint**: All services integrated with pluggable providers

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and final validation

- [ ] T068 [P] Update quickstart.md with all provider examples in `.speckit/features/103-pluggable-providers/quickstart.md`
- [x] T069 [P] Add config.yaml.example to project root in `config.yaml.example`
- [ ] T070 [P] Update USER_GUIDE.md with provider configuration section in `docs/USER_GUIDE.md`
- [ ] T071 [P] Update DEVELOPERS_GUIDE.md with provider extension guide in `docs/DEVELOPERS_GUIDE.md`
- [ ] T072 Run `task before-push` to validate all tests pass
- [ ] T073 Run quickstart.md validation manually
- [ ] T074 Update constitution Technology Stack section to include pluggable providers in `.speckit/memory/constitution.md`

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ──────────────────────────────────────────────┐
                                                               │
Phase 2 (Foundational) ◄──────────────────────────────────────┘
    │
    ├───► Phase 3 (US1: Embedding Providers) ──────────────────┐
    │                                                           │
    ├───► Phase 4 (US2: Summarization Providers) ──────────────┤
    │                                                           │
    └───► Phase 5 (US3: YAML Configuration) ───────────────────┤
                                                               │
                                                               ▼
    Phase 6 (US4: Offline) ◄───────────────────────────────────┤
                                                               │
    Phase 7 (US5: API Keys) ◄──────────────────────────────────┤
                                                               │
    Phase 8 (Integration) ◄────────────────────────────────────┘
        │
        ▼
    Phase 9 (Polish)
```

### User Story Dependencies

- **US1 (Embedding Providers)**: Depends on Phase 2 (Foundational) - No dependencies on other stories
- **US2 (Summarization Providers)**: Depends on Phase 2 - No dependencies on other stories
- **US3 (YAML Configuration)**: Depends on Phase 2 - Should be done with US1/US2 for full testing
- **US4 (Offline Operation)**: Depends on US1, US2, US3 (needs Ollama providers and config)
- **US5 (API Key Management)**: Depends on Phase 2 - Can run parallel with US1-US4

### Parallel Opportunities

**Phase 1 (Setup):**
```bash
# All can run in parallel:
T002, T003, T004, T005
```

**Phase 2 (Foundational):**
```bash
# Config models in parallel:
T006, T007, T008, T009

# Protocols in parallel:
T011, T012, T013, T014

# Tests in parallel:
T017, T018
```

**Phase 3 (US1 - Embeddings):**
```bash
# All tests in parallel:
T020, T021, T022

# All provider implementations in parallel:
T023, T024, T025
```

**Phase 4 (US2 - Summarization):**
```bash
# All tests in parallel:
T028, T029, T030, T031, T032

# All provider implementations in parallel:
T033, T034, T035, T036, T037
```

**Phase 5 (US3 - Config):**
```bash
# Tests in parallel:
T040, T041
```

---

## Implementation Strategy

### MVP First (User Stories 1-3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: US1 - Embedding Providers
4. Complete Phase 4: US2 - Summarization Providers
5. Complete Phase 5: US3 - YAML Configuration
6. **STOP and VALIDATE**: All core provider functionality works
7. Deploy/demo if ready

**MVP delivers**: Configuration-driven provider switching for both embeddings and summarization

### Full Feature (Add US4-US5)

1. Complete MVP (Phases 1-5)
2. Complete Phase 6: US4 - Offline Operation
3. Complete Phase 7: US5 - API Key Management
4. Complete Phase 8: Service Integration
5. Complete Phase 9: Polish

### Parallel Team Strategy

With 3 developers after Phase 2:

- **Developer A**: US1 (Embedding Providers) → US4 (Offline)
- **Developer B**: US2 (Summarization Providers) → US5 (API Keys)
- **Developer C**: US3 (YAML Config) → Phase 8 Integration

---

## Task Summary

| Phase | Description | Task Count | Status |
|-------|-------------|------------|--------|
| 1 | Setup | 5 | ✅ COMPLETE |
| 2 | Foundational | 14 | ✅ COMPLETE |
| 3 | US1: Embedding Providers | 8 | ✅ COMPLETE (1 test pending) |
| 4 | US2: Summarization Providers | 12 | ✅ COMPLETE (4 tests pending) |
| 5 | US3: YAML Configuration | 7 | ✅ COMPLETE (1 integration test pending) |
| 6 | US4: Offline Operation | 6 | ⏳ NOT STARTED |
| 7 | US5: API Key Management | 6 | ⏳ NOT STARTED |
| 8 | Service Integration | 9 | 🔄 PARTIAL (2/9 done) |
| 9 | Polish | 7 | 🔄 PARTIAL (1/7 done) |
| **Total** | | **74** | **MVP Complete** |

### MVP Status (Phases 1-5): ✅ COMPLETE

All core provider functionality implemented:
- 3 embedding providers (OpenAI, Ollama, Cohere)
- 5 summarization providers (Anthropic, OpenAI, Gemini, Grok, Ollama)
- YAML configuration loading with validation
- EmbeddingGenerator refactored to use provider abstraction
- Server startup logging for active providers
- Quality gate passes (338 tests, all linting/typing checks pass)

### Tasks per User Story

- **US1 (Embedding Providers)**: 8 tasks
- **US2 (Summarization Providers)**: 12 tasks
- **US3 (YAML Configuration)**: 7 tasks
- **US4 (Offline Operation)**: 6 tasks
- **US5 (API Key Management)**: 6 tasks

### Parallel Opportunities

- **Phase 1**: 4 of 5 tasks can run in parallel
- **Phase 2**: 10 of 14 tasks can run in parallel
- **Phase 3**: 6 of 8 tasks can run in parallel
- **Phase 4**: 10 of 12 tasks can run in parallel
- **Phase 5**: 2 of 7 tasks can run in parallel
- **Phase 6**: 1 of 6 tasks can run in parallel
- **Phase 7**: 2 of 6 tasks can run in parallel
- **Phase 9**: 4 of 7 tasks can run in parallel

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing (Test-Alongside principle)
- Commit after each task or logical group
- Run `task before-push` before pushing any changes
- Stop at any checkpoint to validate story independently
