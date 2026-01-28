# Implementation Plan: Phase 1 - Core Server

**Branch**: `001-phase1-core-server` | **Date**: 2025-12-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/001-phase1-core-server/spec.md`
**Status**: Implemented

## Summary

Phase 1 delivers the core Doc-Serve REST API server with document indexing via
LlamaIndex + Chroma, semantic search via OpenAI embeddings, and health monitoring
endpoints for skill/CLI integration.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: FastAPI, LlamaIndex, Chroma, OpenAI, Pydantic
**Storage**: Chroma (local vector store)
**Testing**: pytest with pytest-asyncio
**Target Platform**: Local server (macOS/Linux)
**Project Type**: Monorepo with multiple packages
**Performance Goals**: Query response < 2s, health check < 100ms
**Constraints**: Local-first, no external database required
**Scale/Scope**: Single user, thousands of documents

## Constitution Check

*GATE: Verified against Doc-Serve Constitution v1.0.0*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Monorepo Modularity | PASS | doc-serve-server is independently testable |
| II. OpenAPI-First | PASS | /docs and /openapi.json exposed |
| III. Test-Alongside | PARTIAL | Structure exists, tests needed |
| IV. Observability | PASS | /health, /health/status, structured logging |
| V. Simplicity | PASS | Standard dependencies, no over-engineering |

## Project Structure

### Documentation (this feature)

```text
specs/001-phase1-core-server/
├── spec.md              # Feature specification
├── plan.md              # This file
└── tasks.md             # Task breakdown (if needed)
```

### Source Code (implemented)

```text
doc-serve-server/
├── pyproject.toml          # Poetry dependencies
├── src/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py         # FastAPI app entry point
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── health.py   # GET /health, GET /health/status
│   │       ├── index.py    # POST /index, POST /index/add, DELETE /index
│   │       └── query.py    # POST /query, GET /query/count
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py     # Pydantic settings from env
│   ├── models/
│   │   ├── __init__.py
│   │   ├── health.py       # HealthStatus, IndexingStatus
│   │   ├── index.py        # IndexRequest, IndexResponse, IndexingState
│   │   └── query.py        # QueryRequest, QueryResponse, QueryResult
│   ├── services/
│   │   ├── __init__.py
│   │   ├── indexing_service.py  # Document indexing orchestration
│   │   └── query_service.py     # Semantic search execution
│   ├── indexing/
│   │   ├── __init__.py
│   │   ├── document_loader.py   # File loading
│   │   ├── chunking.py          # Text chunking
│   │   └── embedding.py         # OpenAI embedding generation
│   └── storage/
│       ├── __init__.py
│       └── vector_store.py      # Chroma integration
└── tests/
    └── (tests to be added)
```

**Structure Decision**: Monorepo with doc-serve-server as primary package.
Service layer pattern with clear separation: routers → services → storage.

## API Endpoints (Implemented)

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| GET | `/` | Root info (redirects to docs) | Implemented |
| GET | `/docs` | OpenAPI Swagger UI | Implemented |
| GET | `/openapi.json` | OpenAPI spec | Implemented |
| GET | `/health` | Health check | Implemented |
| GET | `/health/status` | Detailed indexing status | Implemented |
| POST | `/index` | Index documents from folder | Implemented |
| POST | `/index/add` | Add documents to existing index | Implemented |
| DELETE | `/index` | Reset/clear index | Implemented |
| POST | `/query` | Semantic search | Implemented |
| GET | `/query/count` | Document count | Implemented |

## Complexity Tracking

No complexity violations. Implementation follows standard patterns with
well-maintained dependencies.

## What Remains for Phase 1 Completion

1. **Tests**: Unit and integration tests for all endpoints
2. **doc-svr-ctl**: CLI tool implementation (scaffolded but empty)
3. **doc-serve-skill**: Claude skill implementation (scaffolded but empty)

## Phase 2 Preview (from README)

Phase 2 will add:
- BM25 keyword search alongside vector search
- Hybrid retrieval with reciprocal rank fusion
- Query mode selection (vector, bm25, hybrid)
