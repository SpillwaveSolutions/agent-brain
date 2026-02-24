"""Pydantic models for request/response handling."""

from .folders import (
    FolderDeleteRequest,
    FolderDeleteResponse,
    FolderInfo,
    FolderListResponse,
)
from .graph import (
    CODE_ENTITY_TYPES,
    DOC_ENTITY_TYPES,
    ENTITY_TYPE_NORMALIZE,
    ENTITY_TYPES,
    INFRA_ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    SYMBOL_TYPE_MAPPING,
    CodeEntityType,
    DocEntityType,
    EntityType,
    GraphEntity,
    GraphIndexStatus,
    GraphQueryContext,
    GraphTriple,
    InfraEntityType,
    RelationshipType,
    normalize_entity_type,
)
from .health import HealthStatus, IndexingStatus
from .index import IndexingState, IndexingStatusEnum, IndexRequest, IndexResponse
from .job import (
    JobDetailResponse,
    JobEnqueueResponse,
    JobListResponse,
    JobProgress,
    JobRecord,
    JobStatus,
    JobSummary,
    QueueStats,
)
from .query import QueryMode, QueryRequest, QueryResponse, QueryResult

__all__ = [
    # Folder management models (Feature 12)
    "FolderInfo",
    "FolderListResponse",
    "FolderDeleteRequest",
    "FolderDeleteResponse",
    # Query models
    "QueryMode",
    "QueryRequest",
    "QueryResponse",
    "QueryResult",
    # Index models
    "IndexRequest",
    "IndexResponse",
    "IndexingState",
    "IndexingStatusEnum",
    # Health models
    "HealthStatus",
    "IndexingStatus",
    # Graph models (Feature 113)
    "GraphTriple",
    "GraphEntity",
    "GraphIndexStatus",
    "GraphQueryContext",
    # Graph schema types (Feature 122 - Phase 3)
    "EntityType",
    "CodeEntityType",
    "DocEntityType",
    "InfraEntityType",
    "RelationshipType",
    "ENTITY_TYPES",
    "RELATIONSHIP_TYPES",
    "CODE_ENTITY_TYPES",
    "DOC_ENTITY_TYPES",
    "INFRA_ENTITY_TYPES",
    "SYMBOL_TYPE_MAPPING",
    "ENTITY_TYPE_NORMALIZE",
    "normalize_entity_type",
    # Job queue models (Feature 115)
    "JobStatus",
    "JobProgress",
    "JobRecord",
    "JobEnqueueResponse",
    "JobListResponse",
    "JobSummary",
    "JobDetailResponse",
    "QueueStats",
]
