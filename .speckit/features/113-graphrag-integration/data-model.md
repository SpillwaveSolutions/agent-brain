# Data Model: GraphRAG Integration

**Feature**: 113-graphrag-integration
**Date**: 2026-01-30

## Entity Definitions

### 1. GraphEntity

Represents an extracted entity (concept, object, or code element) in the knowledge graph.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| id | string | Unique entity identifier | UUID format |
| name | string | Entity display name | Non-empty, max 255 chars |
| entity_type | string | Category (e.g., "CLASS", "FUNCTION", "CONCEPT") | Enum or freeform |
| properties | dict | Additional attributes | JSON-serializable |
| source_chunk_id | string | Reference to source chunk | FK to chunk |

### 2. GraphRelationship

Represents a typed connection between two entities.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| id | string | Unique relationship identifier | UUID format |
| source_id | string | Source entity ID | FK to GraphEntity |
| target_id | string | Target entity ID | FK to GraphEntity |
| relationship_type | string | Type (e.g., "imports", "contains", "references") | Non-empty |
| properties | dict | Additional attributes | JSON-serializable |
| weight | float | Relationship strength | 0.0-1.0, default 1.0 |

### 3. GraphTriple

Convenience structure for entity extraction output.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| subject | string | Subject entity name | Non-empty |
| subject_type | string | Subject entity type | Optional |
| predicate | string | Relationship type | Non-empty |
| object | string | Object entity name | Non-empty |
| object_type | string | Object entity type | Optional |
| source_chunk_id | string | Originating chunk | FK to chunk |

### 4. GraphQueryResult

Extended query result including graph-specific information.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| text | string | Chunk text content | Inherited from QueryResult |
| source | string | Source file path | Inherited |
| score | float | Combined/primary score | Inherited |
| vector_score | float? | Vector similarity score | Optional |
| bm25_score | float? | BM25 relevance score | Optional |
| graph_score | float? | Graph traversal score | NEW: Optional |
| related_entities | list[string] | Connected entity names | NEW: For graph results |
| relationship_path | list[string] | Traversal path from query | NEW: For graph results |
| chunk_id | string | Unique chunk ID | Inherited |

### 5. GraphIndexStatus

Status information for the graph index.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| enabled | bool | Whether GraphRAG is enabled | Config-driven |
| initialized | bool | Whether graph store is ready | Runtime state |
| entity_count | int | Number of entities in graph | >= 0 |
| relationship_count | int | Number of relationships | >= 0 |
| last_updated | datetime? | Last index update time | Optional |
| store_type | string | "simple" or "kuzu" | Config-driven |

---

## Configuration Entities

### 6. GraphSettings (extends Settings)

New configuration fields for GraphRAG feature.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| ENABLE_GRAPH_INDEX | bool | False | Master enable/disable switch |
| GRAPH_STORE_TYPE | str | "simple" | Graph storage backend |
| GRAPH_INDEX_PATH | str | "./graph_index" | Persistence directory |
| GRAPH_EXTRACTION_MODEL | str | "claude-haiku-4-5" | LLM for extraction |
| GRAPH_MAX_TRIPLETS_PER_CHUNK | int | 10 | Limit triplets per chunk |
| GRAPH_USE_CODE_METADATA | bool | True | Extract from AST |
| GRAPH_USE_LLM_EXTRACTION | bool | True | Use LLM for docs |
| GRAPH_TRAVERSAL_DEPTH | int | 2 | Default query depth |
| GRAPH_RRF_K | int | 60 | RRF constant |

---

## Enum Extensions

### QueryMode (extended)

```python
class QueryMode(str, Enum):
    VECTOR = "vector"      # Existing
    BM25 = "bm25"          # Existing
    HYBRID = "hybrid"      # Existing
    GRAPH = "graph"        # NEW: Graph-only traversal
    MULTI = "multi"        # NEW: Vector + BM25 + Graph fusion
```

---

## Relationships

```
┌─────────────────┐     ┌────────────────────┐     ┌─────────────────┐
│   GraphEntity   │────<│ GraphRelationship  │>────│   GraphEntity   │
│                 │     │                    │     │                 │
│ - id            │     │ - id               │     │ (same structure)│
│ - name          │     │ - source_id (FK)   │     │                 │
│ - entity_type   │     │ - target_id (FK)   │     │                 │
│ - properties    │     │ - relationship_type│     │                 │
│ - source_chunk  │     │ - properties       │     │                 │
└─────────────────┘     │ - weight           │     └─────────────────┘
         │              └────────────────────┘
         │
         ▼
┌─────────────────┐
│   TextChunk     │
│   (existing)    │
│                 │
│ - chunk_id      │
│ - text          │
│ - metadata      │
└─────────────────┘
```

---

## State Transitions

### Graph Index States

```
┌──────────────────┐
│    DISABLED      │ ◄── ENABLE_GRAPH_INDEX=false
└────────┬─────────┘
         │ ENABLE_GRAPH_INDEX=true
         ▼
┌──────────────────┐
│  UNINITIALIZED   │ ◄── No graph_index/ directory
└────────┬─────────┘
         │ First document indexed
         ▼
┌──────────────────┐
│    BUILDING      │ ◄── During indexing operation
└────────┬─────────┘
         │ Indexing complete
         ▼
┌──────────────────┐
│      READY       │ ◄── Graph queries available
└────────┬─────────┘
         │ Index corruption/rebuild
         ▼
┌──────────────────┐
│    REBUILDING    │ ◄── Rebuild in progress
└──────────────────┘
```

---

## Validation Rules

1. **GraphEntity.name**: Must be non-empty, max 255 characters
2. **GraphRelationship**: source_id and target_id must reference existing entities
3. **GraphTriple.predicate**: Must be non-empty, recommended lowercase with underscores
4. **GRAPH_MAX_TRIPLETS_PER_CHUNK**: Must be >= 1 and <= 100
5. **GRAPH_TRAVERSAL_DEPTH**: Must be >= 1 and <= 5
6. **QueryMode.GRAPH/MULTI**: Requires ENABLE_GRAPH_INDEX=true
