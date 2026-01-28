# Research: C# Code Indexing

**Feature**: 110-csharp-code-indexing
**Date**: 2026-01-27

## Decision 1: Tree-Sitter C# Grammar Availability

**Decision**: Use `c_sharp` grammar from `tree-sitter-language-pack`.

**Rationale**: The `tree-sitter-language-pack` package (v0.7.3, already a project dependency) includes `c_sharp` as a supported language. No new dependency is required.

**Alternatives Considered**:
- **Standalone `tree-sitter-c-sharp` package**: Rejected. Would add a new dependency when the existing language pack already provides it.
- **Text-only chunking (no AST)**: Rejected. Would provide inferior results compared to all other supported languages.

---

## Decision 2: C# File Extensions

**Decision**: Map `.cs` and `.csx` to the `csharp` language identifier.

**Rationale**: `.cs` is the standard C# source file extension. `.csx` is the C# script extension used by dotnet-script and Visual Studio. Both contain valid C# syntax parseable by the same grammar.

**Alternatives Considered**:
- **`.cs` only**: Rejected. `.csx` files are common in scripting scenarios and contain the same syntax.
- **Include `.cshtml`/`.razor`**: Rejected. These are markup+code hybrids requiring a different parser (out of scope per spec).

---

## Decision 3: Tree-Sitter Language Identifier

**Decision**: Map the `csharp` language name to tree-sitter identifier `c_sharp`.

**Rationale**: The tree-sitter-language-pack uses `c_sharp` (with underscore) as the grammar identifier for C#. This follows the tree-sitter naming convention where special characters in language names are replaced with underscores.

---

## Decision 4: AST Query Patterns for C# Symbols

**Decision**: Query for these C# node types: `class_declaration`, `method_declaration`, `constructor_declaration`, `interface_declaration`, `property_declaration`, `enum_declaration`, `struct_declaration`, `record_declaration`, `namespace_declaration`.

**Rationale**: These are the primary top-level declaration types in C# that correspond to meaningful code boundaries. The pattern follows the same approach used for Java (classes + methods) and TypeScript (classes + functions + interfaces) but extended for C#-specific constructs (properties, structs, records).

**Alternatives Considered**:
- **Minimal set (class + method only)**: Rejected. Would miss interfaces, properties, enums, structs, and records — all common C# constructs.
- **Exhaustive set (include delegates, events, indexers, operators)**: Rejected for MVP. These can be added later if needed.

---

## Decision 5: XML Documentation Comment Extraction

**Decision**: Extract `/// <summary>`, `/// <param>`, and `/// <returns>` XML doc comments by querying for `comment` nodes immediately preceding declarations.

**Rationale**: C# uses XML documentation comments (triple-slash `///`) as its standard documentation format, analogous to Python docstrings and Java Javadoc. The tree-sitter C# grammar represents these as `comment` nodes. Extracting them provides the same docstring metadata that other languages already support.

**Alternatives Considered**:
- **Skip doc comment extraction**: Rejected. Would make C# the only language without docstring support, reducing search quality.
- **Parse XML structure within comments**: Rejected for MVP. Extracting raw text is sufficient; structured XML parsing can be added later.

---

## Decision 6: Content-Based Detection Patterns

**Decision**: Use these regex patterns for C# content detection:
- `using\s+System` (C#-specific using directive)
- `namespace\s+\w+(\.\w+)*\s*[{;]` (namespace with optional file-scoped syntax)
- `\{\s*get\s*;\s*(set\s*;)?\s*\}` (property accessor pattern)
- `\[[\w]+(\(.*\))?\]` (attribute syntax)
- `public\s+(class|interface|struct|record|enum)\s+\w+` (type declarations)

**Rationale**: These patterns distinguish C# from Java (which shares class/interface syntax). The `using System`, property accessors, and attribute syntax are uniquely C#.

**Alternatives Considered**:
- **No content detection**: Rejected. Other languages have content patterns; omitting for C# would be inconsistent.
- **Keyword-only detection**: Rejected. Many C# keywords overlap with Java; structural patterns are more reliable.
