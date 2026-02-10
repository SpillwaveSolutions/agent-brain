"""Query request and response models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..indexing.document_loader import LanguageDetector


class QueryMode(str, Enum):
    """Retrieval modes."""

    VECTOR = "vector"
    BM25 = "bm25"
    HYBRID = "hybrid"
    GRAPH = "graph"  # Graph-only retrieval (Feature 113)
    MULTI = "multi"  # Multi-retrieval: vector + BM25 + graph with RRF (Feature 113)


class QueryRequest(BaseModel):
    """Request model for document queries."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The search query text",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of results to return",
    )
    similarity_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0-1)",
    )
    mode: QueryMode = Field(
        default=QueryMode.HYBRID,
        description="Retrieval mode (vector, bm25, hybrid, graph, multi)",
    )
    alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for hybrid search (1.0 = pure vector, 0.0 = pure bm25)",
    )

    # Content filtering
    source_types: list[str] | None = Field(
        default=None,
        description="Filter by source types: 'doc', 'code', 'test'",
        examples=[["doc"], ["code"], ["doc", "code"]],
    )
    languages: list[str] | None = Field(
        default=None,
        description="Filter by programming languages for code files",
        examples=[["python"], ["typescript", "javascript"], ["java", "kotlin"]],
    )
    file_paths: list[str] | None = Field(
        default=None,
        description="Filter by specific file paths (supports wildcards)",
        examples=[["docs/*.md"], ["src/**/*.py"]],
    )

    # Graph entity type filtering (Feature 122 - Schema GraphRAG)
    entity_types: list[str] | None = Field(
        default=None,
        description=(
            "Filter graph results by entity types "
            "(e.g., ['Class', 'Function']). "
            "Only applies to graph and multi query modes."
        ),
        examples=[["Class", "Function"], ["Package", "Module"]],
    )
    relationship_types: list[str] | None = Field(
        default=None,
        description=(
            "Filter graph results by relationship types "
            "(e.g., ['calls', 'extends']). "
            "Only applies to graph and multi query modes."
        ),
        examples=[["calls", "extends"], ["imports", "contains"]],
    )

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, v: list[str] | None) -> list[str] | None:
        """Validate that provided languages are supported."""
        if v is None:
            return v

        detector = LanguageDetector()
        supported_languages = detector.get_supported_languages()

        invalid_languages = [lang for lang in v if lang not in supported_languages]
        if invalid_languages:
            raise ValueError(
                f"Unsupported languages: {invalid_languages}. "
                f"Supported languages: {supported_languages}"
            )

        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "How do I configure authentication?",
                    "top_k": 5,
                    "similarity_threshold": 0.3,
                    "mode": "hybrid",
                    "alpha": 0.5,
                },
                {
                    "query": "implement user authentication",
                    "top_k": 10,
                    "source_types": ["code"],
                    "languages": ["python", "typescript"],
                },
                {
                    "query": "API endpoints",
                    "top_k": 5,
                    "source_types": ["doc", "code"],
                    "file_paths": ["docs/api/*.md", "src/**/*.py"],
                },
            ]
        }
    }


class QueryResult(BaseModel):
    """Single query result with source and score."""

    text: str = Field(..., description="The chunk text content")
    source: str = Field(..., description="Source file path")
    score: float = Field(..., description="Primary score (rank or similarity)")
    vector_score: float | None = Field(
        default=None, description="Score from vector search"
    )
    bm25_score: float | None = Field(default=None, description="Score from BM25 search")
    chunk_id: str = Field(..., description="Unique chunk identifier")

    # Content type information
    source_type: str = Field(
        default="doc", description="Type of content: 'doc', 'code', or 'test'"
    )
    language: str | None = Field(
        default=None, description="Programming language for code files"
    )

    # GraphRAG fields (Feature 113)
    graph_score: float | None = Field(
        default=None, description="Score from graph-based retrieval"
    )
    related_entities: list[str] | None = Field(
        default=None, description="Related entities from knowledge graph"
    )
    relationship_path: list[str] | None = Field(
        default=None, description="Relationship paths in the graph"
    )

    # Reranking fields (Feature 123)
    rerank_score: float | None = Field(
        default=None, description="Score from reranking stage (if enabled)"
    )
    original_rank: int | None = Field(
        default=None, description="Position before reranking (1-indexed)"
    )

    # Additional metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class QueryResponse(BaseModel):
    """Response model for document queries."""

    results: list[QueryResult] = Field(
        default_factory=list,
        description="List of matching document chunks",
    )
    query_time_ms: float = Field(
        ...,
        ge=0,
        description="Query execution time in milliseconds",
    )
    total_results: int = Field(
        default=0,
        ge=0,
        description="Total number of results found",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {
                            "text": "Authentication is configured via...",
                            "source": "docs/auth.md",
                            "score": 0.92,
                            "vector_score": 0.92,
                            "bm25_score": 0.85,
                            "chunk_id": "chunk_abc123",
                            "source_type": "doc",
                            "language": "markdown",
                            "metadata": {"chunk_index": 0},
                        },
                        {
                            "text": "def authenticate_user(username, password):",
                            "source": "src/auth.py",
                            "score": 0.88,
                            "vector_score": 0.88,
                            "bm25_score": 0.82,
                            "chunk_id": "chunk_def456",
                            "source_type": "code",
                            "language": "python",
                            "metadata": {"symbol_name": "authenticate_user"},
                        },
                    ],
                    "query_time_ms": 125.5,
                    "total_results": 2,
                }
            ]
        }
    }
