# Implementation Plan: Code Ingestion

**Branch**: `101-code-ingestion` | **Date**: 2025-12-18 | **Spec**: [specs/101-code-ingestion/spec.md](spec.md)
**Input**: Feature specification from `/specs/101-code-ingestion/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement source code ingestion and indexing in Doc-Serve (Phase 3) to create a unified searchable corpus combining documentation and source code. Use LlamaIndex's CodeSplitter for AST-aware chunking with tree-sitter, add SummaryExtractor for natural language descriptions, and extend the current vector/BM25 search architecture to support cross-referencing between docs and code.

**Key Components:**
- CodeSplitter for AST-aware chunking (Python, TypeScript, JavaScript)
- SummaryExtractor for code descriptions via LLM
- Unified ChromaDB collection with rich metadata filtering
- Extended API with source_type and language filtering
- CLI enhancements for code indexing and filtering

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: LlamaIndex (CodeSplitter, SummaryExtractor), tree-sitter parsers, ChromaDB
**Storage**: ChromaDB (unified vector store), Disk-based BM25 index
**Testing**: pytest with integration tests for code indexing pipeline
**Target Platform**: Linux server (same as current Doc-Serve deployment)
**Project Type**: Monorepo (extend existing doc-serve-server package)
**Performance Goals**: Code indexing < 2x document indexing time, query latency < 500ms
**Constraints**: < 50% storage overhead for BM25 index, maintain backward compatibility, support 10k+ LOC
**Scale/Scope**: Multi-language codebases (Python, TypeScript, JavaScript), unified docs+code search

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

1. **Monorepo Modularity**:
   - Changes restricted to `doc-serve-server` package for core functionality
   - `doc-serve-skill` and `doc-svr-ctl` benefit from server enhancements without code changes
   - Dependency flow `ctl/skill → server` maintained
   - **SUCCESS**: No cross-package changes required

2. **OpenAPI-First**:
   - New `/index` parameters (`include_code`, `languages`, `exclude_patterns`) and `/query` filters (`source_type`, `language`) will be added to Pydantic models
   - Schema changes will be reflected in `/docs` endpoint automatically
   - **SUCCESS**: Extends existing API without breaking changes

3. **Test-Alongside**:
   - Unit tests for CodeSplitter integration and metadata extraction
   - Integration tests for full code indexing pipeline
   - Contract tests for new API parameters
   - **SUCCESS**: All tests will be included in implementation PR

4. **Observability**:
   - Health endpoints will track code chunk counts alongside document chunks
   - New metadata fields (language, symbol_name, etc.) will be logged
   - Query performance metrics will include code search timing
   - **SUCCESS**: Maintains observability principles

5. **Simplicity**:
   - Uses LlamaIndex CodeSplitter instead of custom AST parsing
   - Leverages existing ChromaDB filtering for source_type/language queries
   - Builds on existing vector/BM25 search infrastructure
   - **SUCCESS**: Minimal new abstractions, extends existing patterns

## Project Structure

### Documentation (this feature)

```text
specs/101-code-ingestion/
├── plan.md              # This file (/speckit.plan command output)
├── spec.md              # User stories and acceptance criteria
├── research.md          # Technical research and decisions (Phase 0)
├── data-model.md        # Entity relationships and schemas (Phase 1)
├── quickstart.md        # Usage examples and setup (Phase 1)
├── contracts/           # API specifications (Phase 1)
└── tasks.md             # Implementation tasks (Phase 2 - /speckit.tasks)
```

### Source Code (extends existing monorepo structure)

```text
doc-serve-server/
├── doc_serve_server/
│   ├── indexing/           # EXTENDED: CodeChunker, code loading
│   │   ├── document_loader.py    # Add load_code_files()
│   │   ├── chunking.py           # Add CodeChunker class
│   │   └── embedding.py          # SummaryExtractor integration
│   ├── models/             # EXTENDED: Code metadata schemas
│   │   └── query.py              # Add source_type, language filters
│   ├── services/           # EXTENDED: Code indexing pipeline
│   │   └── indexing_service.py   # Add code indexing support
│   └── api/routers/        # EXTENDED: New API parameters
│       └── query.py              # Add filtering endpoints
├── tests/                 # EXTENDED: Code indexing tests
│   ├── unit/                    # CodeChunker, metadata extraction
│   └── integration/             # Full code indexing pipeline
└── pyproject.toml         # EXTENDED: tree-sitter dependencies

doc-svr-ctl/               # EXTENDED: CLI code support
└── doc_svr_ctl/commands/
    ├── index.py                 # --include-code, --languages flags
    └── query.py                 # --source-type, --language filters
```

**Structure Decision**: Extends existing monorepo packages rather than creating new ones. Code ingestion is a server-side feature that enhances the core indexing/querying capabilities, so it belongs in `doc-serve-server`. CLI enhancements are additive features in `doc-svr-ctl`. This maintains the constitution's monorepo modularity principle.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
