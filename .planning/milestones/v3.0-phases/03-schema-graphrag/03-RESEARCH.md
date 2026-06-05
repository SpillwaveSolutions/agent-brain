# Phase 3: Schema-Based GraphRAG - Research

**Researched:** 2026-02-10
**Domain:** Knowledge Graph Schema Design, LlamaIndex Property Graphs, Pydantic Entity Modeling
**Confidence:** HIGH

## Summary

Schema-Based GraphRAG enhances the existing graph index (Feature 113) by adding domain-specific entity types and relationship predicates. This phase is about **schema definition and enforcement**, not building a graph from scratch. The codebase already has working graph infrastructure (extractors, store, index manager) that uses generic string types. This phase adds structured enums and validation to improve LLM extraction accuracy and enable type-filtered queries.

**Key Findings:**
1. LlamaIndex SchemaLLMPathExtractor supports Pydantic-style entity type schemas with validation
2. Existing graph infrastructure uses `subject_type` and `object_type` as optional strings — perfect for schema enhancement
3. Project follows Pydantic enum pattern (see `provider_config.py` ValidationSeverity, ProviderType enums)
4. Entity type schema should use `Literal` type hints for LLM extraction, enums for validation

**Primary recommendation:** Use Pydantic `Literal` enums for entity types and predicates, add schema validation to existing extractors, implement type filtering in graph queries without breaking existing graph functionality.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pydantic | ^2.0 (existing) | Model validation, enum-based schemas | Already used project-wide, excellent enum support |
| LlamaIndex | ^0.14.0 (existing) | SchemaLLMPathExtractor for entity extraction | Official property graph schema support |
| typing.Literal | stdlib | Type hints for entity/relationship enums | Python 3.10+ standard, integrates with Pydantic |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| anthropic | existing | LLM extraction with schema prompts | Already used for LLMEntityExtractor |
| SimplePropertyGraphStore | existing (LlamaIndex) | Graph storage backend | Already initialized, supports typed entities |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic Literal | String constants | Literal provides type safety + IDE autocomplete |
| Enum classes | StrEnum | Enum is more verbose, Literal better for LLM prompt templates |
| SchemaLLMPathExtractor | Custom validation | SchemaLLMPathExtractor is official LlamaIndex pattern |

**Installation:**
```bash
# No new dependencies - using existing stack
# Pydantic ^2.0, LlamaIndex ^0.14.0, anthropic already installed
```

## Architecture Patterns

### Recommended Project Structure
```
agent_brain_server/
├── models/
│   └── graph.py              # Add entity type enums here
├── indexing/
│   └── graph_extractors.py   # Add schema validation to extractors
├── storage/
│   └── graph_store.py         # No changes needed
└── services/
    └── query_service.py       # Add type filtering support
```

### Pattern 1: Pydantic Literal Entity Schema
**What:** Use `Literal` type hints for entity types, validated via Pydantic models
**When to use:** Defining strict entity type vocabularies for LLM extraction
**Example:**
```python
# Source: LlamaIndex docs + existing provider_config.py pattern
from typing import Literal
from pydantic import BaseModel, Field

# Code entity types
CodeEntityType = Literal[
    "Package", "Module", "Class", "Method", "Function",
    "Interface", "Enum"
]

# Documentation entity types
DocEntityType = Literal[
    "DesignDoc", "UserDoc", "PRD", "Runbook", "README", "APIDoc"
]

# Combined entity types
EntityType = Literal[
    # Code
    "Package", "Module", "Class", "Method", "Function", "Interface", "Enum",
    # Documentation
    "DesignDoc", "UserDoc", "PRD", "Runbook", "README", "APIDoc",
    # Infrastructure
    "Service", "Endpoint", "Database", "ConfigFile"
]

# Relationship predicates
RelationshipType = Literal[
    "calls", "extends", "implements", "references",
    "depends_on", "imports", "contains", "defined_in"
]

class GraphTriple(BaseModel):
    subject: str = Field(..., min_length=1)
    subject_type: EntityType | None = None  # Now typed!
    predicate: RelationshipType | str  # Typed predicates + fallback
    object: str = Field(..., min_length=1)
    object_type: EntityType | None = None
    source_chunk_id: str | None = None
```

### Pattern 2: Schema-Guided LLM Extraction
**What:** Pass entity/relationship schema to LLM via prompt templates
**When to use:** LLMEntityExtractor should use schema vocabulary
**Example:**
```python
# Source: LlamaIndex SchemaLLMPathExtractor pattern
def _build_extraction_prompt(self, text: str, max_triplets: int) -> str:
    """Build schema-aware extraction prompt."""
    return f"""Extract key entity relationships from the following text.
Return up to {max_triplets} triplets in the format:
SUBJECT | SUBJECT_TYPE | PREDICATE | OBJECT | OBJECT_TYPE

Valid SUBJECT_TYPE / OBJECT_TYPE (use these exact values):
- Code: Package, Module, Class, Method, Function, Interface, Enum
- Documentation: DesignDoc, UserDoc, PRD, Runbook, README, APIDoc
- Infrastructure: Service, Endpoint, Database, ConfigFile

Valid PREDICATE (relationship types):
- calls, extends, implements, references, depends_on
- imports, contains, defined_in

Rules:
- Use exact type names from the lists above
- PREDICATE must be from the valid list
- One triplet per line
- Only output triplets, no explanations

Text:
{text}

Triplets:"""
```

### Pattern 3: Type Filtering in Graph Queries
**What:** Filter graph results by entity type
**When to use:** Query API should support filtering by entity types
**Example:**
```python
# New method in GraphIndexManager
def query_by_type(
    self,
    query_text: str,
    entity_types: list[str] | None = None,
    relationship_types: list[str] | None = None,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Query graph filtered by entity/relationship types.

    Args:
        query_text: Natural language query
        entity_types: Filter to these entity types (e.g., ["Class", "Function"])
        relationship_types: Filter to these predicates (e.g., ["calls", "extends"])
        top_k: Maximum results

    Returns:
        Filtered graph query results
    """
    results = self.query(query_text, top_k=top_k * 2)  # Fetch extra for filtering

    if entity_types:
        results = [
            r for r in results
            if r.get("subject_type") in entity_types
            or r.get("object_type") in entity_types
        ]

    if relationship_types:
        results = [r for r in results if r.get("predicate") in relationship_types]

    return results[:top_k]
```

### Pattern 4: Backward Compatibility
**What:** Entity types are optional — existing untyped triplets still work
**When to use:** Migration strategy for existing graph data
**Example:**
```python
# GraphTriple model supports both typed and untyped
GraphTriple(subject="FastAPI", predicate="uses", object="Pydantic")  # Valid
GraphTriple(
    subject="FastAPI",
    subject_type="Framework",  # Optional type
    predicate="uses",
    object="Pydantic",
    object_type="Library"
)  # Also valid

# Validation is permissive - unknown types log warning but don't fail
```

### Anti-Patterns to Avoid
- **Hard-coding entity types in extractors:** Use schema constants, not strings like `"class"` vs `"Class"`
- **Breaking existing graph data:** Entity types MUST be optional to preserve backward compatibility
- **Over-constraining LLM extraction:** Allow `str` fallback for predicates when LLM suggests valid but unlisted relationships
- **Ignoring metadata extraction:** CodeMetadataExtractor should set entity types from AST (e.g., `symbol_type="function"` → `subject_type="Function"`)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Entity type validation | Custom string validation | Pydantic `Literal` types | Type safety, IDE autocomplete, auto-validation |
| Schema-guided extraction | Custom prompt templates | LlamaIndex SchemaLLMPathExtractor pattern | Official LlamaIndex approach, proven effective |
| Entity type enums | Scattered string constants | Centralized Pydantic Literal definitions | Single source of truth, refactor-safe |
| Type filtering queries | Manual list comprehension | Dedicated `query_by_type()` method | Reusable, testable, API-friendly |

**Key insight:** LlamaIndex already solved schema-based extraction. Don't reinvent — adapt their patterns to our existing extractors.

## Common Pitfalls

### Pitfall 1: Breaking Existing Graph Data
**What goes wrong:** Adding strict entity type validation breaks existing graph triplets with `subject_type=None`
**Why it happens:** Changing `subject_type: str | None` to `subject_type: EntityType` makes None invalid
**How to avoid:** Keep entity types optional with union type: `subject_type: EntityType | None = None`
**Warning signs:** Tests fail with "None is not a valid EntityType"

### Pitfall 2: LLM Hallucinating Invalid Types
**What goes wrong:** LLM returns `"Service"` when schema only defines code types
**Why it happens:** LLM doesn't strictly follow prompt constraints
**How to avoid:** Parse LLM output permissively — log unknown types, store as-is, don't fail extraction
**Warning signs:** Extraction yields zero triplets because all are rejected

### Pitfall 3: Case Sensitivity Mismatch
**What goes wrong:** LLM returns `"class"` but schema defines `"Class"`
**Why it happens:** Inconsistent prompt examples
**How to avoid:**
- Use PascalCase consistently in schema and prompts
- Normalize case during parsing: `subject_type = subject_type.capitalize() if subject_type else None`
**Warning signs:** Valid extractions rejected due to case differences

### Pitfall 4: Over-Constraining Predicates
**What goes wrong:** Requiring all predicates match schema list prevents discovering new relationship types
**Why it happens:** Using strict `Literal` without fallback
**How to avoid:** Allow `predicate: RelationshipType | str` — track unknown predicates for schema evolution
**Warning signs:** Extraction misses valid relationships because predicate not in list

### Pitfall 5: Schema-Code Metadata Disconnect
**What goes wrong:** CodeMetadataExtractor uses lowercase `"function"` but schema defines `"Function"`
**Why it happens:** AST metadata uses different naming convention than schema
**How to avoid:** Add normalization layer in `extract_from_metadata()`:
```python
SYMBOL_TYPE_MAPPING = {
    "function": "Function",
    "method": "Method",
    "class": "Class",
    # ...
}
subject_type = SYMBOL_TYPE_MAPPING.get(metadata["symbol_type"], metadata["symbol_type"])
```
**Warning signs:** Code entities all have null types despite metadata being present

## Code Examples

Verified patterns from LlamaIndex docs and existing codebase:

### Example 1: Entity Type Schema Definition
```python
# Source: models/graph.py (new enums)
from typing import Literal

# Entity type schema - centralized definitions
CodeEntityType = Literal[
    "Package",    # Top-level package
    "Module",     # Python module, JS file
    "Class",      # Class definition
    "Method",     # Class method
    "Function",   # Standalone function
    "Interface",  # Interface/Protocol
    "Enum",       # Enumeration type
]

DocEntityType = Literal[
    "DesignDoc",  # Design documents
    "UserDoc",    # User documentation
    "PRD",        # Product requirements
    "Runbook",    # Operational runbooks
    "README",     # README files
    "APIDoc",     # API documentation
]

InfraEntityType = Literal[
    "Service",    # Microservice
    "Endpoint",   # API endpoint
    "Database",   # Database
    "ConfigFile", # Configuration file
]

# Combined entity type (all categories)
EntityType = Literal[
    # Code
    "Package", "Module", "Class", "Method", "Function", "Interface", "Enum",
    # Documentation
    "DesignDoc", "UserDoc", "PRD", "Runbook", "README", "APIDoc",
    # Infrastructure
    "Service", "Endpoint", "Database", "ConfigFile",
]

# Relationship types
RelationshipType = Literal[
    "calls",      # Function/method invocation
    "extends",    # Class inheritance
    "implements", # Interface implementation
    "references", # Documentation references code
    "depends_on", # Package/module dependency
    "imports",    # Import statement
    "contains",   # Containment relationship
    "defined_in", # Symbol defined in module
]
```

### Example 2: Schema-Aware Extraction Prompt
```python
# Source: indexing/graph_extractors.py LLMEntityExtractor
def _build_extraction_prompt(self, text: str, max_triplets: int) -> str:
    """Build schema-aware extraction prompt with entity types."""
    return f"""Extract key entity relationships from the following text.
Return up to {max_triplets} triplets in the format:
SUBJECT | SUBJECT_TYPE | PREDICATE | OBJECT | OBJECT_TYPE

Valid entity types (SUBJECT_TYPE / OBJECT_TYPE):
Code: Package, Module, Class, Method, Function, Interface, Enum
Documentation: DesignDoc, UserDoc, PRD, Runbook, README, APIDoc
Infrastructure: Service, Endpoint, Database, ConfigFile

Valid relationships (PREDICATE):
calls, extends, implements, references, depends_on, imports, contains, defined_in

Rules:
- Use exact type/predicate names from lists above
- Prefer specific types (Method over Function for class methods)
- One triplet per line
- Only output triplets, no explanations

Text:
{text}

Triplets:"""
```

### Example 3: Type-Aware Metadata Extraction
```python
# Source: indexing/graph_extractors.py CodeMetadataExtractor
class CodeMetadataExtractor:
    # Symbol type mapping from AST to schema
    SYMBOL_TYPE_MAPPING = {
        "package": "Package",
        "module": "Module",
        "class": "Class",
        "method": "Method",
        "function": "Function",
        "interface": "Interface",
        "enum": "Enum",
    }

    def extract_from_metadata(
        self,
        metadata: dict[str, Any],
        source_chunk_id: str | None = None,
    ) -> list[GraphTriple]:
        """Extract typed relationships from code metadata."""
        triplets: list[GraphTriple] = []

        symbol_name = metadata.get("symbol_name")
        raw_symbol_type = metadata.get("symbol_type", "")

        # Normalize symbol type to schema entity type
        symbol_type = self.SYMBOL_TYPE_MAPPING.get(
            raw_symbol_type.lower(),
            raw_symbol_type  # Fallback to original
        )

        # ... rest of extraction logic ...

        triplet = GraphTriple(
            subject=parent_symbol,
            subject_type="Class",  # Typed!
            predicate="contains",
            object=symbol_name,
            object_type=symbol_type,  # Normalized type
            source_chunk_id=source_chunk_id,
        )
        triplets.append(triplet)

        return triplets
```

### Example 4: Type-Filtered Graph Query
```python
# Source: services/query_service.py (new feature)
from agent_brain_server.models.graph import EntityType, RelationshipType

class QueryService:
    def query_graph_by_type(
        self,
        query_text: str,
        entity_types: list[EntityType] | None = None,
        relationship_types: list[RelationshipType] | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Query graph with entity/relationship type filters.

        Example:
            # Find only Class and Function entities
            results = service.query_graph_by_type(
                "user authentication",
                entity_types=["Class", "Function"]
            )

            # Find only 'calls' and 'extends' relationships
            results = service.query_graph_by_type(
                "AuthService",
                relationship_types=["calls", "extends"]
            )
        """
        # Fetch more results for filtering
        raw_results = self.graph_index.query(
            query_text,
            top_k=top_k * 3  # Over-fetch before filtering
        )

        filtered = raw_results

        # Filter by entity types
        if entity_types:
            filtered = [
                r for r in filtered
                if (r.get("subject_type") in entity_types
                    or r.get("object_type") in entity_types)
            ]

        # Filter by relationship types
        if relationship_types:
            filtered = [
                r for r in filtered
                if r.get("predicate") in relationship_types
            ]

        return filtered[:top_k]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Generic string types | Schema-enforced Literal types | LlamaIndex 0.9+ (2024) | Better LLM extraction accuracy |
| Unstructured graph extraction | SchemaLLMPathExtractor with validation | LlamaIndex 0.10+ (2024) | Consistent entity types |
| Free-form predicates | Predefined relationship vocabulary | GraphRAG best practices (2025) | Queryable, structured graphs |
| Type-agnostic queries | Type-filtered retrieval | Neo4j/FalkorDB patterns (2025) | Precise code analysis |

**Deprecated/outdated:**
- **String-only entity types:** Modern GraphRAG uses typed schemas (Literal, enums)
- **LLM-only extraction without schema:** Leads to inconsistent entity types, poor query precision
- **Hard-coded entity lists in prompts:** Use centralized schema definitions

## Open Questions

1. **Should we support custom entity types?**
   - What we know: Current schema is code/doc-focused
   - What's unclear: Users may want domain-specific types (e.g., "DatabaseTable", "APIRoute")
   - Recommendation: Start with fixed schema, add extensibility in Phase 4 if needed

2. **How to migrate existing graph data?**
   - What we know: Existing triplets have `subject_type=None`
   - What's unclear: Should we backfill types via LLM analysis?
   - Recommendation: Make types optional (backward compatible), consider migration script in future

3. **Should predicate filtering be strict or permissive?**
   - What we know: LLMs may suggest valid but unlisted predicates
   - What's unclear: Reject unknown predicates or allow with warning?
   - Recommendation: Allow `str` fallback, log unknown predicates for schema evolution

4. **How granular should entity types be?**
   - What we know: "Function" vs "Method" distinction is useful
   - What's unclear: Should we distinguish "AsyncFunction", "GeneratorFunction"?
   - Recommendation: Start with coarse types (Function, Method), refine based on usage

## Sources

### Primary (HIGH confidence)
- [LlamaIndex Property Graph Advanced](https://developers.llamaindex.ai/python/examples/property_graph/property_graph_advanced/) - SchemaLLMPathExtractor patterns
- [LlamaIndex Property Graph Index Guide](https://developers.llamaindex.ai/python/framework/module_guides/indexing/lpg_index_guide/) - Entity extraction best practices
- [Pydantic Enums Documentation](https://docs.pydantic.dev/2.0/usage/types/enums/) - Enum validation patterns
- Existing codebase: `provider_config.py` (enum patterns), `graph_extractors.py` (extraction logic), `models/graph.py` (GraphTriple model)

### Secondary (MEDIUM confidence)
- [Code Graph Analysis - FalkorDB](https://www.falkordb.com/blog/code-graph/) - Code entity types (Class, Function, Method)
- [Codebase Knowledge Graph - Neo4j](https://neo4j.com/blog/developer/codebase-knowledge-graph/) - Relationship predicates (calls, extends, implements)
- [GraphRAG 2026 Guide - Meilisearch](https://www.meilisearch.com/blog/graph-rag) - Entity schema design patterns

### Tertiary (LOW confidence)
- [GraphRAG Knowledge Graphs 2026 - Fluree](https://flur.ee/fluree-blog/graphrag-knowledge-graphs-making-your-data-ai-ready-for-2026/) - Industry trends, no specific implementation details

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Pydantic and LlamaIndex already in use, official docs confirm patterns
- Architecture: HIGH - Existing codebase provides clear patterns (provider_config enums, graph models)
- Pitfalls: MEDIUM - Based on LlamaIndex docs + inference from existing code structure
- Code examples: HIGH - Adapted from official LlamaIndex docs + existing codebase patterns

**Research date:** 2026-02-10
**Valid until:** 60 days (stable schema design patterns, but LlamaIndex may add features)

**Dependencies on existing phases:**
- Phase 1 (Two-Stage Reranking): No dependency
- Phase 2 (Pluggable Providers): Pattern reference (enum usage in provider_config.py)
- Feature 113 (GraphRAG Integration): CRITICAL dependency — this phase enhances existing graph infrastructure

**Key risks:**
- Existing graph data has untyped entities — migration strategy needed
- LLM extraction quality depends on prompt clarity — iterative refinement likely needed
- Over-constraining predicates may miss valid relationships — balance strictness vs flexibility
