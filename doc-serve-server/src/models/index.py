"""Indexing request, response, and state models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IndexingStatusEnum(str, Enum):
    """Enumeration of indexing status values."""

    IDLE = "idle"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


class IndexRequest(BaseModel):
    """Request model for indexing documents."""

    folder_path: str = Field(
        ...,
        min_length=1,
        description="Path to folder containing documents to index",
    )
    chunk_size: int = Field(
        default=512,
        ge=128,
        le=2048,
        description="Target chunk size in tokens",
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0,
        le=200,
        description="Overlap between chunks in tokens",
    )
    recursive: bool = Field(
        default=True,
        description="Whether to scan folder recursively",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "folder_path": "/path/to/documents",
                    "chunk_size": 512,
                    "chunk_overlap": 50,
                    "recursive": True,
                }
            ]
        }
    }


class IndexResponse(BaseModel):
    """Response model for indexing operations."""

    job_id: str = Field(..., description="Unique identifier for the indexing job")
    status: str = Field(..., description="Current status of the indexing job")
    message: Optional[str] = Field(None, description="Additional status message")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "job_id": "job_abc123",
                    "status": "started",
                    "message": "Indexing started for /path/to/documents",
                }
            ]
        }
    }


class IndexingState(BaseModel):
    """Internal state model for tracking indexing progress."""

    current_job_id: Optional[str] = Field(None, description="Current job ID")
    status: IndexingStatusEnum = Field(
        default=IndexingStatusEnum.IDLE,
        description="Current indexing status",
    )
    is_indexing: bool = Field(default=False, description="Whether indexing is active")
    folder_path: Optional[str] = Field(None, description="Folder being indexed")
    total_documents: int = Field(default=0, description="Total documents found")
    processed_documents: int = Field(default=0, description="Documents processed")
    total_chunks: int = Field(default=0, description="Total chunks created")
    started_at: Optional[datetime] = Field(None, description="When indexing started")
    completed_at: Optional[datetime] = Field(
        None, description="When indexing completed"
    )
    error: Optional[str] = Field(None, description="Error message if failed")

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_documents == 0:
            return 0.0
        return (self.processed_documents / self.total_documents) * 100
