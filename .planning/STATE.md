# Agent Brain — Project State

**Last Updated:** 2026-02-10
**Current Phase:** Phase 3 — Schema-Based GraphRAG (Feature 122)
**Status:** IN PROGRESS

## Current Position

Phase: 3 of 4 (Schema-Based GraphRAG)
Plan: 1 of 2 in current phase
Status: Plan 03-01 complete
Last activity: 2026-02-10 - Completed 03-01-PLAN.md (Schema Foundation)

Progress: ██████░░░░ 60%

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-07)

**Core value:** Developers can semantically search their entire codebase and documentation through a single, fast, local-first API
**Current focus:** Phase 3 — Schema-Based GraphRAG

## Progress

```
Roadmap Progress: ██████░░░░ 60%
```

| Phase | Status | Plans | Progress |
|-------|--------|-------|----------|
| 1 — Two-Stage Reranking | ● Complete | 7/7 | 100% |
| 2 — Pluggable Providers | ● Complete | 4/4 | 100% |
| 3 — Schema GraphRAG | ◐ In Progress | 1/2 | 50% |
| 4 — Provider Testing | ○ Pending | 0/0 | 0% |

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

### Phase 3: Schema-Based GraphRAG (IN PROGRESS)

- Plan 03-01 complete: Schema Foundation
  - 17 entity types (Code, Documentation, Infrastructure)
  - 8 relationship predicates
  - Case-insensitive normalization with acronym preservation
  - Schema-guided LLM extraction prompts
  - 19 new tests, all 494 tests passing (70% coverage)
- See: `.planning/phases/03-schema-graphrag/`

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

## Session Continuity

Last session: 2026-02-10
Stopped at: Completed 03-01-PLAN.md (Schema Foundation)
Resume file: None

## Next Action

```
/gsd:execute-phase 3
```

Continue Phase 3 with Plan 03-02 (schema-aware features).

---
*State updated: 2026-02-10*
