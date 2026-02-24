"""Pydantic models for folder management API.

This module defines request/response models used by the folder management
router to expose indexed folder tracking over the REST API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FolderInfo(BaseModel):
    """Information about a single indexed folder.

    Attributes:
        folder_path: Canonical absolute path to the indexed folder.
        chunk_count: Number of document chunks indexed from this folder.
        last_indexed: ISO 8601 UTC timestamp of the last indexing run.
    """

    folder_path: str = Field(
        ...,
        description="Canonical absolute path to the indexed folder",
    )
    chunk_count: int = Field(
        ...,
        description="Number of indexed chunks from this folder",
        ge=0,
    )
    last_indexed: str = Field(
        ...,
        description="ISO 8601 UTC timestamp of last indexing",
    )


class FolderListResponse(BaseModel):
    """Response model listing all indexed folders.

    Attributes:
        folders: List of FolderInfo objects sorted by folder_path.
        total: Total number of indexed folders.
    """

    folders: list[FolderInfo] = Field(
        default_factory=list,
        description="Indexed folders sorted by path",
    )
    total: int = Field(
        ...,
        description="Total number of indexed folders",
        ge=0,
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "folders": [
                        {
                            "folder_path": "/home/user/project/docs",
                            "chunk_count": 42,
                            "last_indexed": "2026-02-24T01:00:00+00:00",
                        },
                        {
                            "folder_path": "/home/user/project/src",
                            "chunk_count": 128,
                            "last_indexed": "2026-02-24T00:30:00+00:00",
                        },
                    ],
                    "total": 2,
                }
            ]
        }
    }


class FolderDeleteRequest(BaseModel):
    """Request model for removing an indexed folder.

    Attributes:
        folder_path: Path to the folder whose index should be deleted.
    """

    folder_path: str = Field(
        ...,
        min_length=1,
        description="Path to the folder to remove from the index",
    )


class FolderDeleteResponse(BaseModel):
    """Response model confirming folder removal from the index.

    Attributes:
        folder_path: Canonical path of the removed folder.
        chunks_deleted: Number of chunks removed from the vector store.
        message: Human-readable confirmation message.
    """

    folder_path: str = Field(
        ...,
        description="Canonical path of the removed folder",
    )
    chunks_deleted: int = Field(
        ...,
        description="Number of chunks removed from the vector store",
        ge=0,
    )
    message: str = Field(
        ...,
        description="Human-readable confirmation",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "folder_path": "/home/user/project/docs",
                    "chunks_deleted": 42,
                    "message": "Successfully removed 42 chunks for "
                    "/home/user/project/docs",
                }
            ]
        }
    }
