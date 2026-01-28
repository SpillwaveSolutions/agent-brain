# Feature Specification: C# Code Indexing

**Feature Branch**: `110-csharp-code-indexing`
**Created**: 2026-01-27
**Status**: Draft
**Input**: User description: "Add C# to the indexing of source code"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Index C# Source Files (Priority: P1)

As a developer working on a C# project (or a polyglot repository containing C# code), I want doc-serve to recognize, parse, and index `.cs` files so that I can search my C# codebase using semantic and keyword queries just like I can with Python, TypeScript, Java, and other already-supported languages.

**Why this priority**: This is the core capability. Without C# file recognition and AST-aware parsing, no other C# indexing feature can work. This delivers immediate value to any user with C# code in their project.

**Independent Test**: Index a directory containing C# source files with classes, methods, interfaces, and enums. Verify that all `.cs` files are loaded, parsed into AST-aware chunks at function/class boundaries, and stored with correct language metadata. Query for a known C# method name and confirm it returns relevant results.

**Acceptance Scenarios**:

1. **Given** a directory containing `.cs` files, **When** the user indexes the directory with `include_code=true`, **Then** all `.cs` files are loaded and identified as C# source code.
2. **Given** a C# file with classes, methods, and properties, **When** the file is chunked, **Then** chunks are split at class and method boundaries using AST-aware parsing, preserving method signatures and class declarations.
3. **Given** indexed C# code, **When** the user queries for a method name or class name, **Then** the system returns relevant C# code chunks with correct metadata (language, symbol name, symbol kind, line numbers).
4. **Given** indexed C# code, **When** the user filters queries by `language=csharp`, **Then** only C# code chunks are returned.

---

### User Story 2 - Extract C# Symbol Metadata (Priority: P2)

As a developer, I want doc-serve to extract rich metadata from C# code (namespaces, classes, interfaces, methods, properties, XML doc comments) so that search results include meaningful context about each code chunk.

**Why this priority**: Rich metadata improves search quality and makes results more useful. Without it, C# code is still indexable (US1) but results lack the contextual information that makes code search valuable.

**Independent Test**: Index a C# file containing a class with XML documentation comments, methods with parameters and return types, properties, and an interface. Verify that extracted metadata includes symbol names, kinds (class, method, interface, property), parameter lists, return types, and doc comments.

**Acceptance Scenarios**:

1. **Given** a C# method with parameters and a return type, **When** the code is chunked, **Then** the chunk metadata includes the method name, parameter names and types, and return type.
2. **Given** a C# class with XML documentation comments (`/// <summary>`), **When** the code is chunked, **Then** the doc comment text is extracted and stored as the chunk's docstring metadata.
3. **Given** a C# file with interfaces, enums, structs, and records, **When** the code is chunked, **Then** each symbol is identified with the correct kind (interface, enum, struct, record, class).
4. **Given** a C# file with namespace declarations, **When** the code is chunked, **Then** the namespace is included in the chunk metadata.

---

### User Story 3 - Content-Based C# Detection (Priority: P3)

As a developer, I want doc-serve to detect C# code even when file extensions are ambiguous or missing, so that the system correctly identifies and parses C# content in edge cases.

**Why this priority**: This is a robustness improvement. Most C# files use `.cs` extensions, so this is a secondary concern. Content-based detection provides a fallback for unusual project structures.

**Independent Test**: Present a file without a `.cs` extension but containing C# syntax (using directives, namespace declarations, class definitions). Verify the system detects it as C# via content pattern matching.

**Acceptance Scenarios**:

1. **Given** a file with C# syntax but no `.cs` extension, **When** the system attempts language detection, **Then** content-based pattern matching identifies it as C# by recognizing C#-specific patterns (e.g., `using System;`, `namespace`, `[Attribute]`, C# property syntax).
2. **Given** a file that could be either C# or Java (similar syntax), **When** the system attempts language detection, **Then** C#-specific patterns (e.g., `using` directives with semicolons, `var` keyword, property syntax with `{ get; set; }`) are used to disambiguate.

---

### Edge Cases

- What happens when a `.cs` file contains syntax errors? The system MUST fall back to text-based chunking and log a warning, consistent with how other languages handle parse failures.
- What happens when a C# file uses advanced syntax features (records, pattern matching, top-level statements, file-scoped namespaces)? The system MUST handle these without crashing; incomplete parsing is acceptable as long as the file is still indexed.
- What happens when a `.cs` file is a C# script (`.csx`)? The `.csx` extension MUST also be recognized as C# source code.
- What happens when a C# file is very large (>10,000 lines)? The system MUST chunk it without running out of memory, consistent with existing large-file handling for other languages.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST recognize `.cs` and `.csx` file extensions as C# source code during document loading.
- **FR-002**: System MUST parse C# files using a tree-sitter C# parser for AST-aware chunking at function, method, class, interface, struct, record, and enum boundaries.
- **FR-003**: System MUST extract symbol metadata from C# code: symbol name, symbol kind (class, method, interface, property, enum, struct, record), start/end line numbers, parameters, and return type.
- **FR-004**: System MUST extract XML documentation comments (`/// <summary>`, `/// <param>`, `/// <returns>`) and store them as docstring metadata on the corresponding chunk.
- **FR-005**: System MUST support filtering indexed results by `language=csharp` in query requests.
- **FR-006**: System MUST fall back to text-based chunking when C# AST parsing fails (syntax errors, unsupported constructs), consistent with existing fallback behavior for other languages.
- **FR-007**: System MUST include C# content-detection patterns (e.g., `using System;`, `namespace`, property accessors, attributes) for language identification when file extensions are unavailable.
- **FR-008**: System MUST count C# chunks in the `code_chunks` metric alongside other supported languages.
- **FR-009**: System MUST support C# files within the existing indexing pipeline without changes to the indexing API (no new endpoints or parameters required).

### Key Entities

- **C# Language Mapping**: Maps the `.cs` and `.csx` file extensions to the `csharp` language identifier, and maps the `csharp` identifier to the tree-sitter `c_sharp` grammar.
- **C# AST Query**: Tree-sitter query patterns for extracting C# symbols (class_declaration, method_declaration, interface_declaration, property_declaration, enum_declaration, struct_declaration, record_declaration).
- **C# Content Pattern**: Regular expression patterns that identify C# source code by content analysis (using directives, namespace syntax, property accessors, attributes).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can index a C# project and query for any public method or class by name, receiving relevant results with correct metadata, within the same latency as other supported languages.
- **SC-002**: C# code chunks include symbol metadata (name, kind, parameters, return type, line numbers) for at least 90% of top-level declarations (classes, methods, interfaces, enums).
- **SC-003**: XML documentation comments are extracted and included in chunk metadata for at least 90% of documented symbols.
- **SC-004**: C# files with syntax errors are still indexed (via text-based fallback) rather than silently skipped, ensuring no data loss.
- **SC-005**: Adding C# support requires no changes to the indexing or query API — existing API consumers work without modification.

## Assumptions

- The `tree-sitter-language-pack` dependency already includes the C# grammar (`tree_sitter_languages` package provides `c_sharp`). If not available, an alternative tree-sitter C# parser package will be added.
- C# code follows standard conventions (`.cs` extension, UTF-8 encoding). Unusual encodings or obfuscated code are not targeted.
- The feature adds C# alongside existing languages — no existing language support is modified or removed.
- C# script files (`.csx`) are treated identically to regular C# files for parsing purposes.

## Out of Scope

- Razor files (`.cshtml`, `.razor`) — these are markup+code hybrids requiring a different parser
- XAML files (`.xaml`) — UI markup, not source code
- C# project files (`.csproj`, `.sln`) — build configuration, not source code
- NuGet package analysis or dependency resolution
- Cross-language reference resolution (e.g., C# calling Python via interop)
