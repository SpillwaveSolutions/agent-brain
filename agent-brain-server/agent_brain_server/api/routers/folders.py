"""Folder management API router.

Provides endpoints for listing indexed folders and removing folders
from the index. Delegates to FolderManager for folder state and
the storage backend for chunk deletion.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status

from agent_brain_server.models.folders import (
    FolderDeleteRequest,
    FolderDeleteResponse,
    FolderInfo,
    FolderListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/",
    response_model=FolderListResponse,
    summary="List Indexed Folders",
    description="List all folders that have been indexed with chunk counts.",
)
async def list_folders(request: Request) -> FolderListResponse:
    """List all indexed folders with chunk counts and last indexed timestamps.

    Returns folder records tracked by FolderManager, sorted by path.

    Args:
        request: FastAPI request for accessing app state.

    Returns:
        FolderListResponse with sorted folder list and total count.
    """
    folder_manager = request.app.state.folder_manager
    records = await folder_manager.list_folders()

    folders = [
        FolderInfo(
            folder_path=record.folder_path,
            chunk_count=record.chunk_count,
            last_indexed=record.last_indexed,
        )
        for record in records
    ]

    return FolderListResponse(folders=folders, total=len(folders))


@router.delete(
    "/",
    response_model=FolderDeleteResponse,
    summary="Remove Indexed Folder",
    description=(
        "Remove a folder from the index, deleting all its chunks from the vector "
        "store. Returns 409 if an active indexing job is running for this folder."
    ),
)
async def remove_folder(
    request_body: FolderDeleteRequest,
    request: Request,
) -> FolderDeleteResponse:
    """Remove a folder from the index and delete all its chunks.

    Normalizes the folder path before lookup. Checks for active indexing
    jobs first (FOLD-07) to prevent removing a folder while it is being
    indexed. Deletes chunks by IDs if available, otherwise falls back to
    metadata-based deletion.

    Args:
        request_body: FolderDeleteRequest with the folder path to remove.
        request: FastAPI request for accessing app state.

    Returns:
        FolderDeleteResponse with folder path, chunks deleted, and message.

    Raises:
        HTTPException 409: Active indexing job running for this folder.
        HTTPException 404: Folder not found in the index.
        HTTPException 500: Internal error during chunk deletion.
    """
    folder_manager = request.app.state.folder_manager
    job_service = request.app.state.job_service
    storage_backend = request.app.state.storage_backend

    # Normalize the folder path to absolute canonical form
    normalized_path = str(Path(request_body.folder_path).resolve())

    # FOLD-07: Check for active indexing jobs for this folder using the store
    stats = await job_service.get_queue_stats()
    if stats.running > 0:
        # Use store.get_running_job() for efficient single-job check
        running_job = await job_service.store.get_running_job()
        if running_job is not None:
            running_folder = str(Path(running_job.folder_path).resolve())
            if running_folder == normalized_path:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Cannot remove folder while indexing job is active "
                        f"for this path: {normalized_path}"
                    ),
                )

    # Look up the folder record in FolderManager
    record = await folder_manager.get_folder(normalized_path)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder not found in index: {normalized_path}",
        )

    # Delete chunks from storage backend
    chunks_deleted = 0
    try:
        if record.chunk_ids:
            # Delete by chunk IDs (preferred — targeted, no accidental over-deletion)
            chunks_deleted = await storage_backend.delete_by_ids(record.chunk_ids)
            logger.info(
                f"Deleted {chunks_deleted} chunks by IDs for folder: {normalized_path}"
            )
        else:
            # Fallback: delete by metadata source path prefix
            chunks_deleted = await storage_backend.delete_by_metadata(
                where={"source": normalized_path}
            )
            logger.info(
                f"Deleted {chunks_deleted} chunks by metadata for folder: "
                f"{normalized_path}"
            )
    except Exception as e:
        logger.error(f"Failed to delete chunks for folder {normalized_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete chunks: {str(e)}",
        ) from e

    # Remove folder record from FolderManager
    await folder_manager.remove_folder(normalized_path)

    return FolderDeleteResponse(
        folder_path=normalized_path,
        chunks_deleted=chunks_deleted,
        message=(f"Successfully removed {chunks_deleted} chunks for {normalized_path}"),
    )
