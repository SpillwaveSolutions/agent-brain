# Implementation Plan: C# Code Indexing

**Branch**: `110-csharp-code-indexing` | **Date**: 2026-01-27 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `.speckit/features/110-csharp-code-indexing/spec.md`

## Summary

Add C# as the 11th supported language in doc-serve's code indexing pipeline. This is a slot-in addition following the established pattern from 10 existing languages: add file extension mappings, tree-sitter parser setup, AST query patterns for symbol extraction, and content-based detection patterns. No new dependencies, no API changes, no architectural modifications.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: tree-sitter-language-pack (existing, includes `c_sharp` grammar), LlamaIndex CodeSplitter (existing)
**Storage**: ChromaDB (existing vector store), disk-based BM25 index (existing)
**Testing**: pytest (with async support)
**Target Platform**: macOS/Linux local development
**Project Type**: Monorepo (doc-serve-server, doc-svr-ctl, doc-serve-skill)
**Performance Goals**: C# indexing performance on par with existing languages (~100 files/sec)
**Constraints**: No new external dependencies; no API changes
**Scale/Scope**: Standard C# projects (1-10k files)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Monorepo Modularity — PASS

- All changes are within `doc-serve-server` (the server package)
- No changes to `doc-svr-ctl` or `doc-serve-skill`
- No cross-package dependency changes

### II. OpenAPI-First — PASS (No API Changes)

- FR-009 explicitly requires no API changes
- Existing `/index` and `/query` endpoints work unchanged
- The `language=csharp` filter uses the existing `language` query parameter

### III. Test-Alongside — PASS

- Unit tests for C# language detection, AST parsing, and symbol extraction
- Integration tests for end-to-end C# indexing and querying
- Tests follow existing patterns from other language test files

### IV. Observability — PASS

- C# chunks counted in existing `code_chunks` metric (FR-008)
- Existing structured logging covers C# files through the standard pipeline
- No new observability requirements

### V. Simplicity — PASS

- ~100 lines of new code (well under 500-line threshold)
- 0 new dependencies
- 3 files modified (document_loader.py, chunking.py, and tests)
- Follows exact pattern of existing languages — no new abstractions

## Project Structure

### Documentation (this feature)

```text
.speckit/features/110-csharp-code-indexing/
├── plan.md              # This file
├── research.md          # Phase 0 output (6 decisions)
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
doc-serve-server/
├── doc_serve_server/
│   ├── indexing/
│   │   ├── document_loader.py   # MODIFIED: add .cs/.csx extensions, csharp content patterns
│   │   └── chunking.py          # MODIFIED: add c_sharp parser setup, C# AST query patterns
│   └── ...
└── tests/
    └── unit/
        ├── test_document_loader.py  # MODIFIED: add C# extension and content detection tests
        └── test_chunking.py         # MODIFIED: add C# AST parsing and symbol extraction tests
```

**Structure Decision**: Monorepo structure preserved. Only 2 source files modified, plus their existing test files. No new modules or packages created.

## Implementation Phases

### Phase 1: C# Language Support (US1 + US2 + US3 — All Stories)

**Goal**: Full C# indexing with AST-aware chunking, symbol metadata extraction, and content detection.

This feature is small enough to implement in a single phase. All three user stories touch the same two files and are tightly coupled.

1. Add `.cs` and `.csx` to `EXTENSION_TO_LANGUAGE` dict in `document_loader.py`
2. Add `.cs` and `.csx` to `CODE_EXTENSIONS` set in `document_loader.py`
3. Add `csharp` content-detection patterns to `CONTENT_PATTERNS` dict in `document_loader.py`
4. Add `"c_sharp": "c_sharp"` mapping to `_setup_language()` in `chunking.py`
5. Add C# AST query patterns to `_get_symbols()` in `chunking.py` — query for class_declaration, method_declaration, constructor_declaration, interface_declaration, property_declaration, enum_declaration, struct_declaration, record_declaration
6. Add XML doc comment extraction logic for C# `///` comments in `chunking.py`
7. Write unit tests for all new code
8. Run `task before-push` to verify all quality gates

**Files Modified**: `document_loader.py`, `chunking.py`, `test_document_loader.py`, `test_chunking.py`

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Grammar source | `tree-sitter-language-pack` `c_sharp` | Already a dependency; no new package needed |
| File extensions | `.cs`, `.csx` | Standard C# source and script extensions |
| Tree-sitter ID | `c_sharp` | Language pack naming convention |
| Symbol types | 9 node types (class, method, constructor, interface, property, enum, struct, record, namespace) | Covers all common C# declarations |
| Doc comments | Extract `///` comment text | Equivalent to Python docstrings and Java Javadoc |
| Content patterns | 5 regex patterns (using System, namespace, property accessors, attributes, type declarations) | Disambiguates C# from Java |

See [research.md](research.md) for full decision records with alternatives considered.
