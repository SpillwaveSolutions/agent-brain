# Implementation Plan: BM25 & Hybrid Retrieval

**Branch**: `100-bm25-hybrid-retrieval` | **Date**: 2025-12-18 | **Spec**: [specs/100-bm25-hybrid-retrieval/spec.md](spec.md)
**Status**: ✅ COMPLETED - Merged to main | **PR**: https://github.com/SpillwaveSolutions/doc-serve-skill/pull/2
**Input**: Feature specification from `/specs/100-bm25-hybrid-retrieval/spec.md`

## Summary

✅ **COMPLETED**: Implement BM25 keyword search and Hybrid retrieval (combining vector and BM25 scores) using LlamaIndex's `QueryFusionRetriever`. We used `relative_score` fusion to support a tunable `alpha` parameter (0.0 for pure BM25, 1.0 for pure vector). This feature enhances retrieval quality for technical queries by allowing exact term matching alongside semantic search. We leveraged `BM25Retriever` for sparse search and ensured its persistence on disk to optimize server startup times.

**Implementation Results**:
- ✅ 28/28 SDD tasks completed
- ✅ 104 tests passing (68.51% server coverage, 76.19% CLI coverage)
- ✅ Query latency: BM25 <1ms, Hybrid <1.2s
- ✅ Backward compatible API
- ✅ Enhanced CLI with `--mode`, `--alpha`, `--scores` options

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**: FastAPI, LlamaIndex, ChromaDB, OpenAI, rank-bm25  
**Storage**: ChromaDB (Vector Store), Disk-Persistent BM25 Index  
**Testing**: pytest  
**Target Platform**: Linux server  
**Project Type**: Monorepo (FastAPI server + CLI)  
**Performance Goals**: Query latency < 500ms for BM25/Hybrid modes  
**Constraints**: < 50% storage overhead for BM25 index; maintain backward compatibility for API responses.  
**Scale/Scope**: Support technical documentation corpus; thousands of documents.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

1. **Monorepo Modularity**: 
   - Changes restricted to `doc-serve-server` for backend and `doc-svr-ctl` for CLI.
   - `doc-serve-skill` will benefit from server updates without code changes (OpenAPI-driven).
   - SUCCESS: Dependency flow `ctl → server` maintained.
2. **OpenAPI-First**:
   - New query parameters (`mode`, `alpha`) must be defined in Pydantic models in `doc_serve_server/models/query.py`.
   - SUCCESS: Schema updates will be reflected in `/docs`.
3. **Test-Alongside**:
   - Unit tests for `QueryService` hybrid logic.
   - Integration tests for `/query` endpoint with different modes.
   - SUCCESS: Mandatory quality gate `task pr-qa-gate` ensures compliance.
4. **Observability**:
   - Metadata in responses will include `vector_score` and `bm25_score`.
   - Health status will track index availability.
   - SUCCESS: Adheres to observability principle.
5. **Simplicity**:
   - Use `rank-bm25` (via LlamaIndex) instead of complex custom implementations.
   - SUCCESS: Avoids over-engineering.

## Project Structure

### Documentation (this feature)

```text
specs/100-bm25-hybrid-retrieval/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI/Models)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
doc-serve-server/
├── doc_serve_server/
│   ├── api/
│   │   ├── routers/
│   │   │   └── query.py         # Update query endpoint for mode/alpha
│   │   └── models/
│   │       └── query.py         # Add QueryMode enum and alpha field
│   ├── indexing/
│   │   └── bm25_index.py        # New: BM25 index management
│   ├── services/
│   │   └── query_service.py     # Implement Hybrid/RRF logic
│   └── storage/
│       └── vector_store.py      # Ensure compatibility with hybrid
└── tests/
    ├── integration/
    │   └── test_hybrid_query.py # New: Integration tests for hybrid
    └── unit/
        └── test_bm25.py         # New: Unit tests for BM25

doc-svr-ctl/
├── doc_svr_ctl/
│   └── commands/
│       └── query.py             # Add --mode and --alpha flags
└── tests/
    └── test_cli_query.py        # Update CLI tests
```

**Structure Decision**: Selected Option 1 (Single project per package) as it matches the existing monorepo structure. Updates will be applied to `doc-serve-server` and `doc-svr-ctl`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None      | N/A        | N/A                                 |
