# Feature Specification: Source Code Ingestion & Unified Corpus

**Feature Branch**: `101-code-ingestion`
**Created**: 2025-12-18
**Status**: Draft
**Input**: Product Roadmap Phase 3

## User Scenarios & Testing

### User Story 1 - Index Source Code from Folder (Priority: P1)

A developer wants to index their project's source code alongside documentation to create a unified searchable corpus.

**Why this priority**: Core capability for the code ingestion phase. Without this, no code search is possible.

**Independent Test**: POST to `/index` with `include_code=true` and verify code files appear in the index.

**Acceptance Scenarios**:

1. **Given** a folder with Python files, **When** I POST to `/index` with `include_code=true`, **Then** Python files are parsed and indexed
2. **Given** a folder with TypeScript files, **When** I index with code enabled, **Then** TS/TSX files are parsed and indexed
3. **Given** a folder with JavaScript files, **When** I index with code enabled, **Then** JS/JSX files are parsed and indexed
4. **Given** a mixed folder with docs and code, **When** I index with code enabled, **Then** both docs and code appear in the unified index
5. **Given** indexing complete, **When** I check `/health/status`, **Then** I see counts for both document_chunks and code_chunks

---

### User Story 2 - Cross-Reference Search (Priority: P1) ✅ IMPLEMENTED

A user wants to search and find related code and documentation together from a unified corpus.

**Why this priority**: The key value proposition of code ingestion - unified search across docs and implementation.

**Independent Test**: Query for a concept and verify results include both documentation and code examples.

**Acceptance Scenarios**:

1. **Given** docs and code indexed, **When** I query "authentication handler", **Then** results include both doc sections and code implementing authentication
2. **Given** unified corpus, **When** I query for a function name, **Then** I see the function definition AND documentation about it
3. **Given** hybrid search enabled, **When** I query for exact code patterns, **Then** BM25 finds exact matches while vector finds conceptually related code
4. **Given** code-only query, **When** I POST with `source_types=['code']`, **Then** only code results are returned
5. **Given** language-specific query, **When** I POST with `languages=['python']`, **Then** only Python code results are returned
6. **Given** combined filters, **When** I POST with `source_types=['code']` and `languages=['python']`, **Then** only Python code is searched

---

### User Story 3 - Language-Specific Filtering (Priority: P2)

A user wants to filter search results by programming language to narrow down code results.

**Why this priority**: Multi-language projects need language-specific searches. Common in monorepos.

**Independent Test**: Query with `language=python` and verify only Python code results are returned.

**Acceptance Scenarios**:

1. **Given** Python and TypeScript indexed, **When** I query with `language=python`, **Then** only Python code results appear
2. **Given** multiple languages indexed, **When** I query with `language=typescript`, **Then** only TS/TSX results appear
3. **Given** invalid language parameter, **When** I POST query, **Then** I receive 400 error listing valid languages
4. **Given** docs and code indexed, **When** I query with `language=python` and `source_type=code`, **Then** only Python code is searched

---

### User Story 4 - Code Summaries via SummaryExtractor (Priority: P2)

Code chunks automatically receive natural language descriptions to improve semantic search retrieval.

**Why this priority**: Code alone may not match semantic queries. Summaries bridge the gap between natural language questions and code.

**Independent Test**: Index code and verify chunks have summary metadata attached.

**Acceptance Scenarios**:

1. **Given** a Python function, **When** indexed, **Then** the chunk includes a natural language summary of what the function does
2. **Given** a TypeScript class, **When** indexed, **Then** the chunk includes a summary describing the class purpose
3. **Given** code with existing docstrings, **When** indexed, **Then** the summary incorporates docstring content
4. **Given** LLM summarization disabled, **When** indexing, **Then** summaries are generated from available comments/docstrings only

---

### User Story 5 - AST-Aware Chunking (Priority: P3)

Code is chunked at logical boundaries (functions, classes, modules) rather than arbitrary character limits.

**Why this priority**: Maintains code context integrity. A function split across chunks loses meaning.

**Independent Test**: Index code and verify chunks align with function/class boundaries.

**Acceptance Scenarios**:

1. **Given** a Python file with multiple functions, **When** indexed, **Then** each function is a separate chunk
2. **Given** a large function exceeding chunk limit, **When** indexed, **Then** it is split at logical points (try/except blocks, loops)
3. **Given** a class definition, **When** indexed, **Then** class docstring and method signatures are preserved together
4. **Given** import statements, **When** indexed, **Then** they are attached to the first relevant code chunk

---

### User Story 7 - Config-Driven Language Support (Priority: P3 - Future Enhancement)

A developer wants to add support for new programming languages without modifying code - just configuration changes.

**Why this priority**: Enables support for 160+ languages via tree-sitter-language-pack without code changes.

**Independent Test**: Edit languages.yaml config and verify new language is automatically supported.

**Acceptance Scenarios**:

1. **Given** languages.yaml config, **When** I add a new language entry, **Then** it's automatically supported without code changes
2. **Given** language presets, **When** I select "comprehensive" preset, **Then** programming + web + infrastructure languages are enabled
3. **Given** per-language excludes, **When** I configure test file patterns, **Then** test files are automatically excluded
4. **Given** environment overrides, **When** I set ENABLED_LANGUAGES=ruby, **Then** Ruby support is enabled
5. **Given** user custom config, **When** I provide custom languages.yaml, **Then** it overrides defaults

---

### User Story 6 - Corpus for Book/Tutorial Generation (Priority: P1)

A technical writer wants to create a searchable corpus from SDK source code and documentation for writing tutorials.

**Why this priority**: This is a key use case driving the entire phase. Enables AI-assisted technical writing.

**Independent Test**: Index AWS CDK source + docs, query for patterns, verify comprehensive results.

**Acceptance Scenarios**:

1. **Given** AWS CDK docs and source indexed, **When** I query "S3 bucket with versioning", **Then** I get docs explaining the feature AND code examples
2. **Given** Claude SDK indexed, **When** I query "streaming response handling", **Then** I get API docs AND implementation code
3. **Given** comprehensive corpus, **When** Claude skill queries, **Then** it can cite specific files and line numbers
4. **Given** book being written, **When** author queries concepts, **Then** they receive authoritative source material

---

### Edge Cases

- What happens when a code file has syntax errors? (Best-effort parsing, log warning, skip unparseable sections)
- How does system handle binary files in code folders? (Skip with warning, only process text-based code)
- What happens with generated code (e.g., .d.ts, .pyc)? (Skip by default, configurable inclusion)
- How does system handle very large code files? (Multi-chunk with preserved context)
- What happens with unsupported languages? (Skip with warning, log language detection failure)

## Requirements

### Functional Requirements

- **FR-001**: System MUST parse Python source files (.py) with AST awareness
- **FR-002**: System MUST parse TypeScript/JavaScript files (.ts, .tsx, .js, .jsx)
- **FR-003**: System MUST extract docstrings, comments, and type hints as metadata
- **FR-004**: System MUST chunk code at function/class boundaries via CodeSplitter
- **FR-005**: System MUST generate natural language summaries for code chunks (SummaryExtractor)
- **FR-006**: System MUST support `include_code` parameter on `/index` endpoint
- **FR-007**: System MUST support `source_type` filter (doc | code | all) on `/query`
- **FR-008**: System MUST support `language` filter on `/query` for code results
- **FR-009**: System MUST track separate counts for document_chunks and code_chunks
- **FR-010**: System MUST preserve code metadata (file_path, language, line_numbers) in responses
- **FR-011**: CLI MUST support `--include-code` and `--languages` flags for index command

### Key Entities

- **CodeChunk**: Code segment with language, line numbers, summary, and embeddings
- **CodeSplitter**: LlamaIndex splitter for language-aware chunking
- **SummaryExtractor**: Generates natural language descriptions for code
- **LanguageType**: Enum with python, typescript, javascript, jsx values
- **SourceType**: Enum with doc, code, all values for filtering
- **CodeMetadata**: file_path, language, start_line, end_line, function_name, class_name

## Success Criteria

### Measurable Outcomes

- **SC-001**: Python files are correctly parsed and chunked at function boundaries
- **SC-002**: TypeScript/JavaScript files are correctly parsed and chunked
- **SC-003**: Cross-reference queries return relevant results from both docs and code
- **SC-004**: Code summaries improve retrieval quality for semantic queries
- **SC-005**: Indexing time increases < 3x compared to doc-only for equivalent file counts
- **SC-006**: All Phase 1 and Phase 2 functionality remains working
