---
status: complete
phase: 03-schema-graphrag
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md]
started: 2026-02-10T18:40:00Z
updated: 2026-02-10T19:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Entity type schema completeness
expected: Total: 17 entity types across 3 categories (7 Code, 6 Doc, 4 Infra).
result: pass

### 2. Relationship predicates completeness
expected: 8 predicates: calls, extends, implements, references, depends_on, imports, contains, defined_in.
result: pass

### 3. Entity type normalization with acronym preservation
expected: Function, Class, README, APIDoc, PRD, None, SomeCustomType — acronyms preserved, unknown types passed through.
result: pass

### 4. Backward compatibility — untyped GraphTriple
expected: t1.subject_type=None and t2.subject_type=Framework. Non-schema types still accepted.
result: pass

### 5. LLM extraction prompt includes schema vocabulary
expected: Prompt contains entity types from all 3 categories plus relationship predicates (all True).
result: pass

### 6. CodeMetadataExtractor normalizes AST symbol types
expected: subject_type=Function (normalized from lowercase 'function'). Requires ENABLE_GRAPH_INDEX=true.
result: pass
note: Test command needed ENABLE_GRAPH_INDEX=true env var — code correctly respects setting. With env var set, subject_type=Function as expected. Unit tests cover this with proper mocks.

### 7. QueryRequest accepts entity_types and relationship_types
expected: Defaults None/None, with values ['Class', 'Function']/['calls'].
result: pass

### 8. GraphIndexManager has query_by_type method
expected: Parameters: self, query_text, entity_types, relationship_types, top_k, traversal_depth.
result: pass

### 9. All tests pass with coverage
expected: All 505+ tests pass with no failures or errors.
result: pass
note: 505 tests passed, 70% coverage, 12 deprecation warnings (google.api_core, chromadb) — non-blocking.

### 10. Type checking passes
expected: mypy Success: no issues found.
result: pass
note: Success: no issues found in 56 source files.

### 11. Models __init__.py exports schema types
expected: "All exports available" — no import errors.
result: pass

## Summary

total: 11
passed: 11
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
