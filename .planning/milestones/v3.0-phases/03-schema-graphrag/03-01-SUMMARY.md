---
phase: 03-schema-graphrag
plan: 01
subsystem: graph
tags: [graphrag, pydantic, literal-types, schema, entity-types, relationship-predicates, llamaindex]

# Dependency graph
requires:
  - phase: 113-graphrag-integration
    provides: Graph index infrastructure (GraphTriple, extractors, store)
provides:
  - EntityType, CodeEntityType, DocEntityType, InfraEntityType Literal type definitions (17 entity types)
  - RelationshipType Literal type definitions (8 relationship predicates)
  - normalize_entity_type() helper with acronym preservation (README, APIDoc, PRD)
  - Schema-aware LLM extraction prompts with entity type categories
  - AST symbol type normalization in CodeMetadataExtractor
affects: [03-02, schema-based-queries, type-filtered-retrieval, graph-analysis]

# Tech tracking
tech-stack:
  added: [typing.Literal, get_args]
  patterns: [Pydantic Literal enums for schema, case-insensitive normalization with explicit mapping, schema-guided LLM prompts]

key-files:
  created: []
  modified:
    - agent-brain-server/agent_brain_server/models/graph.py
    - agent-brain-server/agent_brain_server/models/__init__.py
    - agent-brain-server/agent_brain_server/indexing/graph_extractors.py
    - agent-brain-server/tests/unit/test_graph_models.py
    - agent-brain-server/tests/unit/test_graph_extractors.py

key-decisions:
  - "Use Literal type hints instead of Enum classes for entity types (better for LLM prompts, less verbose)"
  - "Preserve acronyms (README, APIDoc, PRD) via explicit mapping table instead of .capitalize()"
  - "Keep GraphTriple subject_type/object_type as str | None (not EntityType | None) for backward compatibility"
  - "Log unknown types but don't reject (permissive, not strict) to avoid breaking extraction"
  - "Organize entity types by category (Code, Documentation, Infrastructure) in LLM prompt for clarity"

patterns-established:
  - "Pattern 1: Schema types defined as Literal, runtime constants extracted via get_args()"
  - "Pattern 2: Normalization helper functions for case-insensitive schema matching"
  - "Pattern 3: Schema-guided LLM prompts with organized entity type lists"
  - "Pattern 4: AST metadata normalization using SYMBOL_TYPE_MAPPING dict"

# Metrics
duration: 7min
completed: 2026-02-10
---

# Phase 3 Plan 1: Schema-Based GraphRAG Foundation Summary

**Domain-specific entity type schema (17 types: Code, Documentation, Infrastructure) and relationship predicates (8 types) with case-insensitive normalization and schema-guided LLM extraction**

## Performance

- **Duration:** 7 minutes
- **Started:** 2026-02-10T18:10:39Z
- **Completed:** 2026-02-10T18:17:16Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Defined complete entity type schema with 17 types organized in 3 categories (Code: 7, Documentation: 6, Infrastructure: 4)
- Defined 8 relationship predicates (calls, extends, implements, references, depends_on, imports, contains, defined_in)
- Implemented case-insensitive normalization with acronym preservation (README, APIDoc, PRD)
- Updated LLM extraction prompt to include full schema vocabulary organized by category
- Integrated schema normalization into CodeMetadataExtractor for AST symbol types
- Added 19 comprehensive tests (13 for schema types, 6 for schema-aware extraction)
- All 494 tests pass with 70% coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: Define entity type schema and relationship predicates** - `35f0aab` (feat)
   - Added EntityType, CodeEntityType, DocEntityType, InfraEntityType Literal types
   - Added RelationshipType Literal with 8 predicates
   - Added normalize_entity_type() helper with explicit mapping for acronyms
   - Exported all new types from models/__init__.py

2. **Task 2: Update extractors to use schema vocabulary** - `db97e64` (feat)
   - Updated LLMEntityExtractor._build_extraction_prompt() with organized entity type lists
   - Updated LLMEntityExtractor._parse_triplets() to normalize types and predicates
   - Updated CodeMetadataExtractor to use normalize_entity_type() for all symbol_type fields
   - Added debug logging for unknown types (permissive, not strict)

3. **Task 3: Add tests for schema types and schema-aware extraction** - `0cd5aed` (test)
   - Added TestEntityTypeSchema class with 13 tests in test_graph_models.py
   - Added 6 schema-aware extraction tests in test_graph_extractors.py
   - Verified backward compatibility, acronym preservation, case-insensitivity

## Files Created/Modified

- `agent-brain-server/agent_brain_server/models/graph.py` - Added 17 entity types, 8 relationship types, normalization helpers
- `agent-brain-server/agent_brain_server/models/__init__.py` - Exported all schema types and helpers
- `agent-brain-server/agent_brain_server/indexing/graph_extractors.py` - Schema-aware extraction with normalization
- `agent-brain-server/tests/unit/test_graph_models.py` - Added TestEntityTypeSchema class (13 tests)
- `agent-brain-server/tests/unit/test_graph_extractors.py` - Added 6 schema-aware extraction tests

## Decisions Made

**1. Literal types instead of Enum classes**
- Rationale: Less verbose, better for LLM prompt templates, easier to iterate over with get_args()

**2. Acronym preservation via explicit mapping**
- Rationale: .capitalize() breaks "readme" → "Readme" instead of "README". Explicit table ensures correct casing for APIDoc, PRD, etc.

**3. Backward compatibility: GraphTriple types remain str | None**
- Rationale: Existing untyped triplets with subject_type=None or custom types like "Framework" must continue to work. Schema is guidance, not constraint.

**4. Permissive extraction: unknown types logged but not rejected**
- Rationale: LLMs may suggest valid but unlisted types. Logging enables schema evolution without breaking extraction.

**5. Category-organized entity types in LLM prompt**
- Rationale: Grouping by Code/Documentation/Infrastructure improves LLM accuracy vs. flat list.

## Deviations from Plan

None - plan executed exactly as written. All verification steps passed, no blocking issues encountered.

## Issues Encountered

None - implementation followed plan precisely. All tests passed on first run after formatting/linting fixes.

## User Setup Required

None - no external service configuration required. Schema is internal to the application.

## Next Phase Readiness

**Ready for Plan 03-02 (schema-aware features):**
- Entity type schema fully defined and tested
- LLM extraction using schema vocabulary
- AST metadata normalization complete
- Backward compatibility verified
- All tests passing (494 tests, 70% coverage)

**Blockers:** None

**Enables:**
- Type-filtered graph queries (e.g., find only Class and Function entities)
- Schema-aware graph analysis and visualization
- Improved LLM extraction accuracy via structured prompts
- Foundation for future schema extensions (e.g., custom domain types)

---

## Self-Check: PASSED

All files created/modified exist:
- FOUND: agent-brain-server/agent_brain_server/models/graph.py
- FOUND: agent-brain-server/agent_brain_server/models/__init__.py
- FOUND: agent-brain-server/agent_brain_server/indexing/graph_extractors.py

All commits exist:
- FOUND: 35f0aab (Task 1)
- FOUND: db97e64 (Task 2)
- FOUND: 0cd5aed (Task 3)

---
*Phase: 03-schema-graphrag*
*Completed: 2026-02-10*
