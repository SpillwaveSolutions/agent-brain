# Tasks: C# Code Indexing

**Input**: Design documents from `.speckit/features/110-csharp-code-indexing/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, quickstart.md

**Tests**: Per Constitution III (Test-Alongside), test tasks are included. Tests MUST be written during implementation in the same PR/commit.

**Organization**: All three user stories touch the same 2 source files, so tasks are organized as a single implementation phase with story labels for traceability.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Verify environment and tree-sitter C# grammar availability

- [ ] T001 Verify `tree-sitter-language-pack` includes the `c_sharp` grammar — run `python -c "from tree_sitter_language_pack import get_language; get_language('c_sharp')"` in `doc-serve-server/`
- [ ] T002 Create a sample C# test fixture file at `doc-serve-server/tests/fixtures/sample.cs` containing a class with methods, properties, interfaces, enums, XML doc comments, and a namespace declaration for use in unit tests

---

## Phase 2: User Story 1 — Index C# Source Files (Priority: P1) + User Story 2 — Extract C# Symbol Metadata (Priority: P2) + User Story 3 — Content-Based Detection (Priority: P3) 🎯 MVP

**Goal**: Full C# indexing with AST-aware chunking, symbol metadata extraction, XML doc comment extraction, and content-based language detection. All three stories are combined because they modify the same two files.

**Independent Test**: Index a directory containing C# source files. Verify `.cs` files are loaded, parsed into AST-aware chunks at class/method boundaries, stored with correct language and symbol metadata, and queryable by method name or `language=csharp` filter.

### Tests (Constitution III: Test-Alongside)

- [ ] T003 [P] [US1] Write unit tests for C# file extension detection in `doc-serve-server/tests/unit/test_document_loader.py` — test that `.cs` and `.csx` are recognized as `csharp`, test `is_supported_language("csharp")` returns True
- [ ] T004 [P] [US2] Write unit tests for C# AST parsing and symbol extraction in `doc-serve-server/tests/unit/test_chunking.py` — test that `CodeChunker` with language `csharp` produces chunks at class/method boundaries, test symbol metadata extraction (name, kind, parameters, return type, line numbers) for classes, methods, interfaces, properties, enums, structs
- [ ] T005 [P] [US2] Write unit test for C# XML doc comment extraction in `doc-serve-server/tests/unit/test_chunking.py` — test that `/// <summary>` comments are extracted as docstring metadata on the corresponding chunk
- [ ] T006 [P] [US3] Write unit tests for C# content-based detection in `doc-serve-server/tests/unit/test_document_loader.py` — test that content containing `using System;`, namespace declarations, property accessors, and attributes is detected as `csharp`
- [ ] T007 [P] [US1] Write integration test for C# indexing end-to-end in `doc-serve-server/tests/unit/test_chunking.py` — test that a sample `.cs` file is loaded, chunked with AST awareness, and produces chunks with correct `language=csharp` metadata

### Implementation

- [ ] T008 [P] [US1] Add `.cs` and `.csx` to `EXTENSION_TO_LANGUAGE` dictionary in `doc-serve-server/doc_serve_server/indexing/document_loader.py` — map both extensions to `"csharp"`
- [ ] T009 [P] [US1] Add `.cs` and `.csx` to `CODE_EXTENSIONS` set in `doc-serve-server/doc_serve_server/indexing/document_loader.py`
- [ ] T010 [P] [US3] Add C# content-detection patterns to `CONTENT_PATTERNS` dictionary in `doc-serve-server/doc_serve_server/indexing/document_loader.py` — key: `"csharp"`, patterns: `using\s+System`, `namespace\s+\w+`, `\{\s*get\s*;\s*(set\s*;)?\s*\}`, `\[[\w]+(\(.*\))?\]`, `public\s+(class|interface|struct|record|enum)\s+\w+`
- [ ] T011 [US1] Add `"csharp": "c_sharp"` to the language mapping dictionary in `_setup_language()` method in `doc-serve-server/doc_serve_server/indexing/chunking.py`
- [ ] T012 [US2] Add C# AST query patterns to `_get_symbols()` method in `doc-serve-server/doc_serve_server/indexing/chunking.py` — add a `csharp` case querying for: `class_declaration`, `method_declaration`, `constructor_declaration`, `interface_declaration`, `property_declaration`, `enum_declaration`, `struct_declaration`, `record_declaration`, `namespace_declaration`. Extract symbol name from the `name` field of each node.
- [ ] T013 [US2] Add XML doc comment extraction for C# in `_get_symbols()` or `_extract_docstring()` in `doc-serve-server/doc_serve_server/indexing/chunking.py` — detect `///` comment nodes preceding declarations, extract text content, strip XML tags for plain text, store as `docstring` metadata on the chunk

### Verification

- [ ] T014 Run all unit tests: `cd doc-serve-server && poetry run pytest tests/unit/test_document_loader.py tests/unit/test_chunking.py -v`
- [ ] T015 Run full test suite: `cd doc-serve-server && poetry run pytest`
- [ ] T016 Run `task before-push` from repository root to verify formatting, linting, type checking, and all tests pass

**Checkpoint**: C# code indexing is fully functional. All `.cs` and `.csx` files are recognized, parsed with AST-aware chunking, and searchable with correct metadata. Content-based detection works for ambiguous files.

---

## Phase 3: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final verification

- [ ] T017 [P] Run quickstart.md verification checklist — confirm all 7 items pass
- [ ] T018 [P] Update `.speckit/features/110-csharp-code-indexing/spec.md` status from "Draft" to "Implemented"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — verify grammar availability first
- **Implementation (Phase 2)**: Depends on Setup — all three user stories in one phase
- **Polish (Phase 3)**: Depends on Phase 2 completion

### User Story Dependencies

All three stories are implemented together in Phase 2 because they modify the same files:

- **US1 (P1)**: Extension mapping + parser setup → enables file loading and AST chunking
- **US2 (P2)**: Symbol extraction + doc comments → depends on parser from US1
- **US3 (P3)**: Content patterns → independent of US1/US2 (different dict in same file)

### Within Phase 2

- Tests (T003-T007) can all run in parallel
- T008, T009, T010 can run in parallel (different dicts in same file, but independent additions)
- T011 must complete before T012-T013 (parser setup before symbol queries)
- T014-T016 run sequentially after all implementation tasks

### Parallel Opportunities

**Phase 1**: T001 and T002 can run in parallel
**Phase 2 Tests**: T003, T004, T005, T006, T007 can all run in parallel (5 tasks)
**Phase 2 Impl**: T008, T009, T010 can run in parallel (extension + content patterns)

---

## Parallel Example: Phase 2

```bash
# Launch all tests in parallel (write first, expect failures):
Task: "T003 [P] [US1] Unit tests for C# extension detection"
Task: "T004 [P] [US2] Unit tests for C# AST parsing"
Task: "T005 [P] [US2] Unit tests for XML doc comment extraction"
Task: "T006 [P] [US3] Unit tests for content-based detection"
Task: "T007 [P] [US1] Integration test for C# indexing"

# Launch parallel implementation for document_loader.py:
Task: "T008 [P] [US1] Add .cs/.csx to EXTENSION_TO_LANGUAGE"
Task: "T009 [P] [US1] Add .cs/.csx to CODE_EXTENSIONS"
Task: "T010 [P] [US3] Add C# content patterns"

# Sequential implementation for chunking.py:
Task: "T011 [US1] Add csharp→c_sharp parser mapping"
Task: "T012 [US2] Add C# AST query patterns"
Task: "T013 [US2] Add XML doc comment extraction"
```

---

## Implementation Strategy

### MVP (All Stories — Single Phase)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: All user stories (T003-T016)
3. Complete Phase 3: Polish (T017-T018)
4. **VALIDATE**: Run quickstart.md checklist

This feature is small enough (~100 lines of new code across 2 files) to implement and ship in a single pass.

---

## Notes

- All three user stories combined into one phase because they modify the same 2 source files
- [P] tasks = different files or independent additions, no dependencies
- [USn] label maps task to specific user story for traceability
- Test tasks included per Constitution III (Test-Alongside)
- No API changes needed (FR-009) — no contracts/ directory generated
- No data-model.md needed — no new entities, just configuration additions
