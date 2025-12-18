"""Query request and response models."""

from typing import Any

from pydantic import BaseModel, Field


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
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score (0-1)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "How do I configure authentication?",
                    "top_k": 5,
                    "similarity_threshold": 0.7,
                }
            ]
        }
    }


class QueryResult(BaseModel):
    """Single query result with source and score."""

    text: str = Field(..., description="The chunk text content")
    source: str = Field(..., description="Source file path")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0-1)")
    chunk_id: str = Field(..., description="Unique chunk identifier")
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
                            "chunk_id": "chunk_abc123",
                            "metadata": {"chunk_index": 0},
                        }
                    ],
                    "query_time_ms": 125.5,
                    "total_results": 1,
                }
            ]
        }
    }
