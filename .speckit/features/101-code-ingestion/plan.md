# Implementation Plan: Source Code Ingestion & Unified Corpus

**Branch**: `101-code-ingestion` | **Date**: 2025-12-19 | **Spec**: [specs/101-code-ingestion/spec.md](specs/101-code-ingestion/spec.md)
**Input**: Feature specification from `/specs/101-code-ingestion/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Enable indexing and searching of source code files alongside documentation to create a unified corpus. Implementation uses AST-aware parsing with language-specific chunking strategies, natural language summaries for code chunks, and hybrid search capabilities across both documentation and code.

Technical approach: Extend existing indexing pipeline with CodeSplitter for AST-aware chunking, SummaryExtractor for code descriptions, and unified storage with metadata filtering by language and source type.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.10+
**Primary Dependencies**: LlamaIndex (CodeSplitter, SummaryExtractor), tree-sitter (AST parsing), OpenAI/Anthropic (embeddings/summaries)
**Storage**: ChromaDB vector store (existing)
**Testing**: pytest with coverage
**Target Platform**: Linux/macOS server
**Project Type**: Web application (FastAPI server)
**Performance Goals**: Indexing time increases < 3x compared to doc-only NEEDS CLARIFICATION
**Constraints**: Memory usage for large codebases NEEDS CLARIFICATION, preserve existing API contracts
**Scale/Scope**: Support for monorepo-scale codebases (100k+ LOC) NEEDS CLARIFICATION

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Status: PASS** - All core principles satisfied

- **Monorepo Modularity**: ✅ Adds functionality to server package only
- **OpenAPI-First**: ✅ Will extend existing API spec with new parameters (include_code, source_type, language)
- **Test-Alongside**: ✅ Tests will be implemented alongside features
- **Observability**: ✅ Health endpoints will be extended to track code_chunks count
- **Simplicity**: ✅ Complexity justified by core value proposition (unified doc+code search)

**API Changes Required**: Extend `/index` and `/query` endpoints in OpenAPI spec

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
doc-serve-server/
├── doc_serve_server/
│   ├── indexing/           # EXTENDED: Add code parsing capabilities
│   │   ├── code_parser.py         # NEW: AST-aware code parsing
│   │   ├── code_splitter.py       # NEW: Language-aware chunking
│   │   └── summary_extractor.py   # NEW: Code summarization
│   ├── models/             # EXTENDED: Add code-related models
│   │   ├── code.py                # NEW: CodeChunk, CodeMetadata models
│   │   └── query.py               # EXTENDED: Add language/source filters
│   ├── services/           # EXTENDED: Add code indexing services
│   │   ├── code_indexing_service.py # NEW: Code indexing orchestration
│   │   └── query_service.py        # EXTENDED: Unified doc+code search
│   └── storage/            # EXTENDED: Code chunk storage
│       └── vector_store.py         # EXTENDED: Multi-source collection support
├── tests/
│   ├── integration/
│   │   ├── test_code_indexing.py  # NEW: Code indexing tests
│   │   └── test_unified_search.py # NEW: Cross-reference search tests
│   └── unit/
│       ├── test_code_parser.py    # NEW: Parser unit tests
│       └── test_code_splitter.py  # NEW: Splitter unit tests
```

**Structure Decision**: Extends existing server package structure. Code parsing added to indexing/, models to models/, services to services/. No new packages required - maintains monorepo modularity principle.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| ~1000+ lines of new code | AST-aware parsing enables logical code chunking and cross-reference search | Regex-based parsing would lose semantic understanding of code structure and fail to chunk at function/class boundaries |
| Multi-language support (Python, TS/JS) | Core requirement for unified corpus across tech stacks | Single-language support would limit the unified search value proposition |
| LLM-powered summarization | Improves semantic search retrieval for code queries | Keyword-only search would miss conceptual matches between natural language questions and code implementations |
