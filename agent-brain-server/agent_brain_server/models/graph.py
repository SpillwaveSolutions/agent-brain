"""Models for GraphRAG feature (Feature 113).

Defines Pydantic models for graph entities, relationships, and status.
All models are configured with frozen=True for immutability.
"""

from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

# Entity Type Schema (SCHEMA-01, SCHEMA-02, SCHEMA-03)

# Code entity types
CodeEntityType = Literal[
    "Package",  # Top-level package
    "Module",  # Python module, JS file
    "Class",  # Class definition
    "Method",  # Class method
    "Function",  # Standalone function
    "Interface",  # Interface/Protocol
    "Enum",  # Enumeration type
]

# Documentation entity types
DocEntityType = Literal[
    "DesignDoc",  # Design documents
    "UserDoc",  # User documentation
    "PRD",  # Product requirements
    "Runbook",  # Operational runbooks
    "README",  # README files
    "APIDoc",  # API documentation
]

# Infrastructure entity types
InfraEntityType = Literal[
    "Service",  # Microservice
    "Endpoint",  # API endpoint
    "Database",  # Database
    "ConfigFile",  # Configuration file
]

# Combined entity type (all 17 types)
EntityType = Literal[
    # Code (7 types)
    "Package",
    "Module",
    "Class",
    "Method",
    "Function",
    "Interface",
    "Enum",
    # Documentation (6 types)
    "DesignDoc",
    "UserDoc",
    "PRD",
    "Runbook",
    "README",
    "APIDoc",
    # Infrastructure (4 types)
    "Service",
    "Endpoint",
    "Database",
    "ConfigFile",
]

# Relationship types (8 predicates)
RelationshipType = Literal[
    "calls",  # Function/method invocation
    "extends",  # Class inheritance
    "implements",  # Interface implementation
    "references",  # Documentation references code
    "depends_on",  # Package/module dependency
    "imports",  # Import statement
    "contains",  # Containment relationship
    "defined_in",  # Symbol defined in module
]

# Runtime constants for validation and iteration
ENTITY_TYPES: list[str] = list(get_args(EntityType))
RELATIONSHIP_TYPES: list[str] = list(get_args(RelationshipType))
CODE_ENTITY_TYPES: list[str] = list(get_args(CodeEntityType))
DOC_ENTITY_TYPES: list[str] = list(get_args(DocEntityType))
INFRA_ENTITY_TYPES: list[str] = list(get_args(InfraEntityType))

# AST symbol type mapping to schema entity types
SYMBOL_TYPE_MAPPING: dict[str, str] = {
    "package": "Package",
    "module": "Module",
    "class": "Class",
    "method": "Method",
    "function": "Function",
    "interface": "Interface",
    "enum": "Enum",
}

# Comprehensive case-insensitive mapping for ALL entity types.
# .capitalize() breaks acronyms like README and APIDoc, so we use
# an explicit lookup table built from get_args(EntityType).
ENTITY_TYPE_NORMALIZE: dict[str, str] = {t.lower(): t for t in ENTITY_TYPES}
# Also merge SYMBOL_TYPE_MAPPING for AST symbol types
ENTITY_TYPE_NORMALIZE.update(SYMBOL_TYPE_MAPPING)


def normalize_entity_type(raw_type: str | None) -> str | None:
    """Normalize a raw entity type string to schema EntityType.

    Uses explicit mapping to preserve acronyms (README, APIDoc, PRD).
    Returns None if input is None, returns original string if no mapping found.

    Args:
        raw_type: Raw entity type string (may be lowercase, mixed case, etc.)

    Returns:
        Normalized entity type from schema, or original if not found, or None.

    Examples:
        >>> normalize_entity_type("function")
        "Function"
        >>> normalize_entity_type("CLASS")
        "Class"
        >>> normalize_entity_type("readme")
        "README"
        >>> normalize_entity_type("apidoc")
        "APIDoc"
        >>> normalize_entity_type(None)
        None
        >>> normalize_entity_type("CustomType")
        "CustomType"
    """
    if raw_type is None:
        return None
    # Exact match first (already correct case)
    if raw_type in ENTITY_TYPES:
        return raw_type
    # Case-insensitive lookup via explicit mapping
    mapped = ENTITY_TYPE_NORMALIZE.get(raw_type.lower())
    if mapped:
        return mapped
    return raw_type  # Fallback: keep original for flexibility


class GraphTriple(BaseModel):
    """Represents a subject-predicate-object triple in the knowledge graph.

    Triples are the fundamental unit of knowledge representation in GraphRAG.
    They capture relationships between entities extracted from documents.

    Attributes:
        subject: The subject entity (e.g., "FastAPI").
        subject_type: Optional type classification (e.g., "Framework").
        predicate: The relationship type (e.g., "uses").
        object: The object entity (e.g., "Pydantic").
        object_type: Optional type classification (e.g., "Library").
        source_chunk_id: Optional ID of the source document chunk.
    """

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "subject": "FastAPI",
                    "subject_type": "Framework",
                    "predicate": "uses",
                    "object": "Pydantic",
                    "object_type": "Library",
                    "source_chunk_id": "chunk_abc123",
                },
                {
                    "subject": "UserController",
                    "subject_type": "Class",
                    "predicate": "calls",
                    "object": "authenticate_user",
                    "object_type": "Function",
                    "source_chunk_id": "chunk_def456",
                },
            ]
        },
    )

    subject: str = Field(
        ...,
        min_length=1,
        description="Subject entity in the triple",
    )
    subject_type: str | None = Field(
        default=None,
        description="Type classification for subject entity",
    )
    predicate: str = Field(
        ...,
        min_length=1,
        description="Relationship type connecting subject to object",
    )
    object: str = Field(
        ...,
        min_length=1,
        description="Object entity in the triple",
    )
    object_type: str | None = Field(
        default=None,
        description="Type classification for object entity",
    )
    source_chunk_id: str | None = Field(
        default=None,
        description="ID of the source document chunk",
    )


class GraphEntity(BaseModel):
    """Represents an entity node in the knowledge graph.

    Entities are the nodes in the graph, representing concepts,
    code elements, or other named items extracted from documents.

    Attributes:
        name: Unique name/identifier of the entity.
        entity_type: Classification type (e.g., "Class", "Function", "Concept").
        description: Optional description of the entity.
        source_chunk_ids: List of source chunk IDs where entity appears.
        properties: Additional metadata properties.
    """

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "VectorStoreManager",
                    "entity_type": "Class",
                    "description": "Manages Chroma vector store operations",
                    "source_chunk_ids": ["chunk_001", "chunk_002"],
                    "properties": {"module": "storage.vector_store"},
                },
            ]
        },
    )

    name: str = Field(
        ...,
        min_length=1,
        description="Unique name/identifier of the entity",
    )
    entity_type: str | None = Field(
        default=None,
        description="Classification type for the entity",
    )
    description: str | None = Field(
        default=None,
        description="Description of the entity",
    )
    source_chunk_ids: list[str] = Field(
        default_factory=list,
        description="List of source chunk IDs where entity appears",
    )
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Additional metadata properties",
    )


class GraphIndexStatus(BaseModel):
    """Status of the graph index.

    Provides information about the graph index state,
    including whether it's enabled, initialized, and statistics.

    Attributes:
        enabled: Whether graph indexing is enabled.
        initialized: Whether the graph store is initialized.
        entity_count: Number of entities in the graph.
        relationship_count: Number of relationships in the graph.
        last_updated: Timestamp of last graph update.
        store_type: Type of graph store backend.
    """

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "enabled": True,
                    "initialized": True,
                    "entity_count": 150,
                    "relationship_count": 320,
                    "last_updated": "2024-12-15T10:30:00Z",
                    "store_type": "simple",
                },
                {
                    "enabled": False,
                    "initialized": False,
                    "entity_count": 0,
                    "relationship_count": 0,
                    "last_updated": None,
                    "store_type": "simple",
                },
            ]
        },
    )

    enabled: bool = Field(
        default=False,
        description="Whether graph indexing is enabled",
    )
    initialized: bool = Field(
        default=False,
        description="Whether the graph store is initialized",
    )
    entity_count: int = Field(
        default=0,
        ge=0,
        description="Number of entities in the graph",
    )
    relationship_count: int = Field(
        default=0,
        ge=0,
        description="Number of relationships in the graph",
    )
    last_updated: datetime | None = Field(
        default=None,
        description="Timestamp of last graph update",
    )
    store_type: str = Field(
        default="simple",
        description="Type of graph store backend (simple or kuzu)",
    )
    counts_stale: bool = Field(
        default=False,
        description=(
            "True when the entity/relationship counts are from a cached "
            "last-known value (kuzu unreachable at query time). "
            "False on a successful live COUNT(*) or on non-kuzu backends. "
            "GSTAB-03 / Phase 64 Plan 02."
        ),
    )


class GraphQueryContext(BaseModel):
    """Context information from graph-based retrieval.

    Contains additional context extracted from the knowledge graph
    during query processing.

    Attributes:
        related_entities: List of related entity names.
        relationship_paths: List of relationship paths as strings.
        subgraph_triplets: Relevant triplets from the graph.
        graph_score: Score from graph-based retrieval.
    """

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "related_entities": ["FastAPI", "Pydantic", "Uvicorn"],
                    "relationship_paths": [
                        "FastAPI -> uses -> Pydantic",
                        "FastAPI -> runs_on -> Uvicorn",
                    ],
                    "subgraph_triplets": [
                        {
                            "subject": "FastAPI",
                            "predicate": "uses",
                            "object": "Pydantic",
                        },
                    ],
                    "graph_score": 0.85,
                },
            ]
        },
    )

    related_entities: list[str] = Field(
        default_factory=list,
        description="List of related entity names",
    )
    relationship_paths: list[str] = Field(
        default_factory=list,
        description="Relationship paths as formatted strings",
    )
    subgraph_triplets: list[GraphTriple] = Field(
        default_factory=list,
        description="Relevant triplets from the graph",
    )
    graph_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Score from graph-based retrieval",
    )


# -----------------------------------------------------------------------------
# GraphEntityRecord v2 — backs GET /graph/entity/{type}/{id}
#
# Locked by Phase 50 design doc §2.4 (docs/plans/2026-06-02-mcp-v2-subscriptions.md).
# These are deliberately distinct from the legacy ``GraphEntity`` /
# ``GraphTriple`` extraction models above:
#
#   - ``GraphEntity`` (above) describes an entity extracted from documents
#     during indexing — its primary key is ``name`` and it carries
#     ``source_chunk_ids`` for traceability.
#   - ``GraphEntityRecordNode`` (below) describes an entity as exposed via
#     the public HTTP endpoint — its primary key is ``(type, id)`` and it
#     carries a free-form ``properties`` dict matching the wire shape.
#
# The two will eventually converge; keeping them separate now avoids
# rewriting existing extraction code in this plan.
# -----------------------------------------------------------------------------


class GraphEntityRecordNode(BaseModel):
    """Entity node payload for ``GET /graph/entity/{type}/{id}``.

    Wire shape locked in Phase 50 design doc §2.4. Used for both the
    target entity and its 1-hop neighbors.
    """

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "type": "Function",
                    "id": "authenticate_user",
                    "properties": {
                        "module": "auth.handlers",
                        "language": "python",
                    },
                }
            ]
        },
    )

    type: str = Field(
        ...,
        min_length=1,
        description=(
            "Entity type — one of the 17 SCHEMA-01 types when canonical, "
            "but accepted as opaque on the wire so existing data with "
            "non-canonical labels still serializes."
        ),
    )
    id: str = Field(
        ...,
        min_length=1,
        description="Stable opaque entity id (entity name in current backends).",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form entity properties carried by the backend.",
    )


class GraphEntityRecordNeighbor(BaseModel):
    """A single 1-hop neighbor of the target entity.

    Direction is implied by the containing list (``neighbors.incoming`` vs
    ``neighbors.outgoing``); the predicate names the relationship.
    """

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "type": "Class",
                    "id": "AuthService",
                    "predicate": "calls",
                    "properties": {"source_chunk_id": "chunk_42"},
                }
            ]
        },
    )

    type: str = Field(
        ...,
        min_length=1,
        description="Neighbor entity type (SCHEMA-01 vocabulary when canonical).",
    )
    id: str = Field(
        ...,
        min_length=1,
        description="Neighbor entity id.",
    )
    predicate: str = Field(
        ...,
        min_length=1,
        description="Relationship predicate (SCHEMA-03 vocabulary when canonical).",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form relationship properties (e.g. source_chunk_id).",
    )


class GraphEntityRecordNeighbors(BaseModel):
    """Container for the 1-hop neighborhood of the target entity.

    Empty arrays are returned as ``[]`` — never ``None`` — so MCP clients
    can iterate without null-checks. v2 caps at 1-hop; multi-hop traversal
    is a v3 concern (see design doc §2.4).
    """

    model_config = ConfigDict(frozen=True)

    incoming: list[GraphEntityRecordNeighbor] = Field(
        default_factory=list,
        description="Neighbors with edges pointing at the target entity.",
    )
    outgoing: list[GraphEntityRecordNeighbor] = Field(
        default_factory=list,
        description="Neighbors that the target entity points at.",
    )


class GraphEntityRecord(BaseModel):
    """Response model for ``GET /graph/entity/{entity_type}/{entity_id}``.

    Shape locked by Phase 50 design doc §2.4. Phase 51 wires this through
    the MCP ``graph-entity://<type>/<id>`` resource scheme (URI-02) — both
    paths must serialize this exact shape so an MCP client and a direct
    HTTP consumer see the same wire format.
    """

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "entity": {
                        "type": "Function",
                        "id": "authenticate_user",
                        "properties": {"module": "auth.handlers"},
                    },
                    "neighbors": {
                        "incoming": [
                            {
                                "type": "Class",
                                "id": "AuthController",
                                "predicate": "calls",
                                "properties": {},
                            }
                        ],
                        "outgoing": [
                            {
                                "type": "Function",
                                "id": "verify_password",
                                "predicate": "calls",
                                "properties": {},
                            }
                        ],
                    },
                }
            ]
        },
    )

    entity: GraphEntityRecordNode = Field(
        ...,
        description="The requested entity's type, id, and properties.",
    )
    neighbors: GraphEntityRecordNeighbors = Field(
        default_factory=GraphEntityRecordNeighbors,
        description="1-hop neighbors split by direction. Empty lists, never None.",
    )
