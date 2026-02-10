# Agent Brain — Project State

**Last Updated:** 2026-02-10
**Current Phase:** Phase 4 — Provider Integration Testing
**Status:** IN PROGRESS

## Current Position

Phase: 4 of 4 (Provider Integration Testing)
Plan: 1 of ? in current phase
Status: Plan 04-01 complete (6/6 must-haves)
Last activity: 2026-02-10 - Completed 04-01-PLAN.md

Progress: ██████████ 100%

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-07)

**Core value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API
**Current focus:** Phase 4 — Provider Integration Testing

## Progress

```
Roadmap Progress: ████████░░ 80%
```

| Phase | Status | Plans | Progress |
|-------|--------|-------|----------|
| 1 — Two-Stage Reranking | ● Complete | 7/7 | 100% |
| 2 — Pluggable Providers | ● Complete | 4/4 | 100% |
| 3 — Schema GraphRAG | ● Complete | 2/2 | 100% |
| 4 — Provider Testing | ◐ In Progress | 1/? | ?% |

## Completed Phases

### Phase 1: Two-Stage Reranking (COMPLETE)

- 7 plans executed across 4 waves
- SentenceTransformerRerankerProvider + OllamaRerankerProvider
- 55 new tests, all 453 tests passing
- See: `.planning/phases/01-two-stage-reranking/`

### Phase 2: Pluggable Providers (COMPLETE)

- 4 plans executed across 2 waves
- Dimension mismatch prevention (PROV-07)
- Strict startup validation with severity levels (PROV-06)
- Provider switching E2E tests + config CLI (PROV-03)
- Ollama offline E2E tests (PROV-04)
- 20+ new tests, verification passed (23/23 must-haves)
- See: `.planning/phases/02-pluggable-providers/`

### Phase 3: Schema-Based GraphRAG (COMPLETE)

- Plan 03-01 complete: Schema Foundation
  - 17 entity types (Code, Documentation, Infrastructure)
  - 8 relationship predicates
  - Case-insensitive normalization with acronym preservation
  - Schema-guided LLM extraction prompts
  - 19 new tests, all 494 tests passing (70% coverage)
- Plan 03-02 complete: Type Filtering for Graph Queries
  - GraphIndexManager.query_by_type() with entity_types/relationship_types filtering
  - QueryRequest entity_types and relationship_types filter fields
  - Subject_type and object_type fields in graph query results
  - 11 new tests, all 505 tests passing (70% coverage)
- See: `.planning/phases/03-schema-graphrag/`

### Phase 4: Provider Integration Testing (IN PROGRESS)

- Plan 04-01 complete: Per-Provider E2E Test Suites
  - 5 provider test files (OpenAI, Anthropic, Cohere, Ollama, Health)
  - 42 new tests with graceful API key skipping
  - Config-level tests pass without API keys
  - Health endpoint tests validate structured provider status
  - Duration: 367s (6.1 minutes)
- See: `.planning/phases/04-provider-integration-testing/`

## Key Decisions

- **Embedding Metadata Storage**: Store provider/model/dimensions in ChromaDB collection metadata
- **Validation Strategy**: Dual-layer — startup (warning) + indexing (error unless force=True)
- **Strict Mode**: Opt-in via --strict flag or AGENT_BRAIN_STRICT_MODE env var
- **Config CLI**: `agent-brain config show/path` for debugging provider configuration
- **Test Fixtures**: YAML config fixtures for different provider combinations
- **Entity Type Schema**: Use Literal types (not Enum) for entity types — better for LLM prompts, less verbose
- **Acronym Preservation**: Explicit mapping table for README, APIDoc, PRD (not .capitalize())
- **Schema Enforcement**: Permissive (log unknown types, don't reject) to enable schema evolution
- **Backward Compatibility**: GraphTriple types remain str | None to preserve existing untyped triplets
- **Type Filtering Strategy**: Over-fetch (3x top_k) then post-filter for type-filtered queries to ensure enough results
- **Cohere Provider Testing**: Cohere requires API key at instantiation (unlike Ollama), so provider instantiation tests need check_cohere_key fixture
- **Health Endpoint Testing**: Use minimal FastAPI app with custom lifespan to avoid ChromaDB initialization in tests

## Session Continuity

Last session: 2026-02-10
Stopped at: Completed 04-01-PLAN.md (Per-Provider E2E Test Suites)
Resume file: None

## Next Action

Continue Phase 4 execution with next plan, or verify phase completion.

Phase 4 Plan 01 complete. Provider E2E tests established.

---
*State updated: 2026-02-10*
