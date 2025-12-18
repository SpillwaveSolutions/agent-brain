"""Health status models."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    """Server health status response."""

    status: Literal["healthy", "indexing", "degraded", "unhealthy"] = Field(
        ...,
        description="Current server health status",
    )
    message: Optional[str] = Field(
        None,
        description="Additional status message",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of the health check",
    )
    version: str = Field(
        default="1.0.0",
        description="Server version",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "message": "Server is running and ready for queries",
                    "timestamp": "2024-12-15T10:30:00Z",
                    "version": "1.0.0",
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
    indexing_in_progress: bool = Field(
        default=False,
        description="Whether indexing is currently in progress",
    )
    current_job_id: Optional[str] = Field(
        None,
        description="ID of the current indexing job",
    )
    progress_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Progress percentage of current indexing job",
    )
    last_indexed_at: Optional[datetime] = Field(
        None,
        description="Timestamp of last completed indexing operation",
    )
    indexed_folders: list[str] = Field(
        default_factory=list,
        description="List of folders that have been indexed",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_documents": 150,
                    "total_chunks": 1200,
                    "indexing_in_progress": False,
                    "current_job_id": None,
                    "progress_percent": 0.0,
                    "last_indexed_at": "2024-12-15T10:30:00Z",
                    "indexed_folders": ["/path/to/docs"],
                }
            ]
        }
    }
