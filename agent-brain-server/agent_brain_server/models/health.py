"""Health status models."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """Server health status response."""

    status: Literal["healthy", "indexing", "degraded", "unhealthy"] = Field(
        ...,
        description="Current server health status",
    )
    message: str | None = Field(
        None,
        description="Additional status message",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of the health check",
    )
    version: str = Field(
        default="2.0.0",
        description="Server version",
    )
    mode: str | None = Field(
        default=None,
        description="Instance mode: 'project' or 'shared'",
    )
    instance_id: str | None = Field(
        default=None,
        description="Unique instance identifier",
    )
    project_id: str | None = Field(
        default=None,
        description="Project identifier (shared mode)",
    )
    active_projects: int | None = Field(
        default=None,
        description="Number of active projects (shared mode)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "message": "Server is running and ready for queries",
                    "timestamp": "2024-12-15T10:30:00Z",
                    "version": "2.0.0",
                }
            ]
        }
    }


class IndexingStatus(BaseModel):
    """Detailed indexing status response."""

    total_documents: int = Field(
        default=0,
        ge=0,
        description="Total number of documents indexed",
    )
    total_chunks: int = Field(
        default=0,
        ge=0,
        description="Total number of chunks in vector store",
    )
    total_doc_chunks: int = Field(
        default=0,
        ge=0,
        description="Number of document chunks",
    )
    total_code_chunks: int = Field(
        default=0,
        ge=0,
        description="Number of code chunks",
    )
    supported_languages: list[str] = Field(
        default_factory=list,
        description="Programming languages that have been indexed",
    )
    indexing_in_progress: bool = Field(
        default=False,
        description="Whether indexing is currently in progress",
    )
    current_job_id: str | None = Field(
        None,
        description="ID of the current indexing job",
    )
    progress_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Progress percentage of current indexing job",
    )
    last_indexed_at: datetime | None = Field(
        None,
        description="Timestamp of last completed indexing operation",
    )
    indexed_folders: list[str] = Field(
        default_factory=list,
        description="List of folders that have been indexed",
    )
    # Graph index status (Feature 113)
    graph_index: dict[str, Any] | None = Field(
        default=None,
        description="Graph index status with entity_count, relationship_count, etc.",
    )
    # Queue status (Feature 115)
    queue_pending: int = Field(
        default=0,
        ge=0,
        description="Number of pending jobs in the queue",
    )
    queue_running: int = Field(
        default=0,
        ge=0,
        description="Number of running jobs (0 or 1)",
    )
    current_job_running_time_ms: int | None = Field(
        None,
        description="Running time of current job in milliseconds",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_documents": 150,
                    "total_chunks": 1200,
                    "total_doc_chunks": 800,
                    "total_code_chunks": 400,
                    "indexing_in_progress": False,
                    "current_job_id": None,
                    "progress_percent": 0.0,
                    "last_indexed_at": "2024-12-15T10:30:00Z",
                    "indexed_folders": ["/path/to/docs"],
                    "supported_languages": ["python", "typescript", "java"],
                    "graph_index": {
                        "enabled": True,
                        "initialized": True,
                        "entity_count": 120,
                        "relationship_count": 250,
                        "store_type": "simple",
                    },
                }
            ]
        }
    }


class ProviderHealth(BaseModel):
    """Health status for a single provider."""

    provider_type: str = Field(description="Type: embedding, summarization, reranker")
    provider_name: str = Field(description="Provider name (e.g., openai, ollama)")
    model: str = Field(description="Model being used")
    status: str = Field(description="Status: healthy, degraded, unavailable")
    message: str | None = Field(default=None, description="Status message")
    dimensions: int | None = Field(
        default=None, description="Embedding dimensions (for embedding providers)"
    )


class ProvidersStatus(BaseModel):
    """Status of all configured providers."""

    config_source: str | None = Field(
        default=None, description="Path to config file if loaded"
    )
    strict_mode: bool = Field(
        default=False, description="Whether strict validation is enabled"
    )
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation error messages"
    )
    providers: list[ProviderHealth] = Field(
        default_factory=list, description="Status of each provider"
    )
    timestamp: datetime = Field(description="Status check timestamp")
