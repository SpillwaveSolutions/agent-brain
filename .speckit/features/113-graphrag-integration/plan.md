# Implementation Plan: GraphRAG Integration

**Branch**: `113-graphrag-integration` | **Date**: 2026-01-30 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `.speckit/features/113-graphrag-integration/spec.md`

## Summary

Add optional GraphRAG capabilities to doc-serve using LlamaIndex's PropertyGraphIndex with SimplePropertyGraphStore (default) and Kuzu (optional) backends. This extends the existing hybrid retrieval system with two new query modes: GRAPH (graph-only traversal) and MULTI (vector + BM25 + graph fusion using RRF). The feature is disabled by default and can be enabled via `ENABLE_GRAPH_INDEX=true`.

## Technical Context

**Language/Version**: Python 3.10+ (existing: ^3.10 in pyproject.toml)
**Primary Dependencies**: FastAPI, LlamaIndex (llama-index-core ^0.14.0), ChromaDB, langextract (new), llama-index-graph-stores-kuzu (optional)
**Storage**: ChromaDB (vector), disk-based BM25 index (existing), SimplePropertyGraphStore/Kuzu (new graph storage)
**Testing**: pytest with async support (existing pattern)
**Target Platform**: Linux/macOS server, local development
**Project Type**: Monorepo (doc-serve-server, doc-svr-ctl, doc-serve-skill)
**Performance Goals**: Graph queries < 2s for 10k documents; no latency impact when disabled
**Constraints**: GraphRAG disabled by default; optional dependencies only installed when needed
**Scale/Scope**: Up to 10,000 documents with graph index; configurable triplet limits

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Monorepo Modularity | ✅ PASS | Changes confined to doc-serve-server; CLI updates extend existing patterns |
| II. OpenAPI-First | ✅ PASS | New query modes added to existing QueryMode enum; contracts defined in contracts/ |
| III. Test-Alongside | ✅ PASS | Unit, integration, and contract tests required for each component |
| IV. Observability | ✅ PASS | Graph status in /health/status; structured logging for graph operations |
| V. Simplicity | ⚠️ MONITOR | 2 new optional dependencies; ~800 LOC estimated; documented in Complexity Tracking |

## Project Structure

### Documentation (this feature)

```text
.speckit/features/113-graphrag-integration/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── query-modes.yaml # OpenAPI additions
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
doc-serve-server/
├── doc_serve_server/
│   ├── config/
│   │   └── settings.py           # MODIFY: Add graph settings
│   ├── storage/
│   │   ├── vector_store.py       # EXISTING
│   │   └── graph_store.py        # NEW: Graph store manager
│   ├── indexing/
│   │   ├── graph_index.py        # NEW: Graph index manager
│   │   └── graph_extractors.py   # NEW: Entity extraction (LLM + AST)
│   ├── models/
│   │   └── query.py              # MODIFY: Add GRAPH, MULTI modes
│   ├── services/
│   │   ├── query_service.py      # MODIFY: Add graph/multi query execution
│   │   └── indexing_service.py   # MODIFY: Build graph during indexing
│   ├── api/routers/
│   │   ├── query.py              # MODIFY: Support new modes
│   │   └── index.py              # MODIFY: Graph rebuild endpoint
│   └── storage_paths.py          # MODIFY: Add graph_index dir
└── tests/
    ├── unit/
    │   ├── test_graph_store.py       # NEW
    │   ├── test_graph_extractors.py  # NEW
    │   └── test_graph_index.py       # NEW
    ├── integration/
    │   └── test_graph_query.py       # NEW
    └── contract/
        └── test_query_modes.py       # NEW

doc-svr-ctl/
├── doc_svr_ctl/
│   └── commands/
│       └── query.py              # MODIFY: Add --mode graph, --mode multi
└── tests/
    └── test_query_command.py     # MODIFY: Test new modes
```

**Structure Decision**: Follows existing monorepo pattern. New graph components mirror vector_store.py and bm25_index.py patterns. All changes are additive or extend existing interfaces.

## Complexity Tracking

| Aspect | Evaluation | Justification |
|--------|------------|---------------|
| New Dependencies | 2 optional | langextract for LLM extraction; kuzu for production graph store. Both optional based on config. |
| Lines of Code | ~800 estimated | graph_store.py (~150), graph_index.py (~200), graph_extractors.py (~200), query modifications (~150), tests (~100+) |
| Pattern Compliance | Factory pattern | Follows existing VectorStoreManager singleton pattern |

**Constitution V (Simplicity) Justification**: The feature adds complexity but follows existing patterns and is entirely optional. Users who don't enable GraphRAG experience zero overhead or changes. The 2 optional dependencies are well-maintained (langextract by Google, Kuzu by active community) and only installed when the feature is used.
