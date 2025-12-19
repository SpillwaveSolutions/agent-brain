"""Indexing request, response, and state models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CodeChunkStrategy(str, Enum):
    """Strategy for chunking code files."""

    AST_AWARE = "ast_aware"  # Use LlamaIndex CodeSplitter for AST boundaries
    TEXT_BASED = "text_based"  # Use regular text chunking


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

    # Code indexing options
    include_code: bool = Field(
        default=False,
        description="Whether to index source code files alongside documents",
    )
    supported_languages: Optional[list[str]] = Field(
        default=None,
        description="Programming languages to index (defaults to all supported)",
        examples=[["python", "typescript"], ["java", "kotlin"]],
    )
    code_chunk_strategy: CodeChunkStrategy = Field(
        default=CodeChunkStrategy.AST_AWARE,
        description="Strategy for chunking code files",
    )
    generate_summaries: bool = Field(
        default=False,
        description="Generate LLM summaries for code chunks to improve semantic search",
    )

    # File filtering options
    include_patterns: Optional[list[str]] = Field(
        default=None,
        description="Additional file patterns to include (supports wildcards)",
        examples=[["*.md", "*.py"], ["docs/**/*.md", "src/**/*.py"]],
    )
    exclude_patterns: Optional[list[str]] = Field(
        default=None,
        description="Additional file patterns to exclude (supports wildcards)",
        examples=[["*.log", "__pycache__/**"], ["node_modules/**", "*.tmp"]],
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "folder_path": "/path/to/documents",
                    "chunk_size": 512,
                    "chunk_overlap": 50,
                    "recursive": True,
                },
                {
                    "folder_path": "/path/to/project",
                    "chunk_size": 512,
                    "chunk_overlap": 50,
                    "recursive": True,
                    "include_code": True,
                    "supported_languages": ["python", "typescript", "javascript"],
                    "code_chunk_strategy": "ast_aware",
                    "include_patterns": ["docs/**/*.md", "src/**/*.py", "src/**/*.ts"],
                    "exclude_patterns": ["node_modules/**", "__pycache__/**", "*.log"],
                },
                {
                    "folder_path": "/path/to/codebase",
                    "include_code": True,
                    "supported_languages": ["java", "kotlin"],
                    "code_chunk_strategy": "ast_aware",
                },
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
