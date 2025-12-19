"""Indexing endpoints for document processing."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from doc_serve_server.models import IndexRequest, IndexResponse
from doc_serve_server.services import get_indexing_service

router = APIRouter()


@router.post(
    "/",
    response_model=IndexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Index Documents",
    description="Start indexing documents from a folder.",
)
async def index_documents(request: IndexRequest) -> IndexResponse:
    """
    Start indexing documents from the specified folder.

    This endpoint initiates a background indexing job and returns immediately.
    Use the /health/status endpoint to monitor progress.

    Args:
        request: IndexRequest with folder_path and optional configuration.

    Returns:
        IndexResponse with job_id and status.

    Raises:
        400: Invalid folder path
        409: Indexing already in progress
    """
    # Validate folder path
    folder_path = Path(request.folder_path).expanduser().resolve()

    if not folder_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Folder not found: {request.folder_path}",
        )

    if not folder_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {request.folder_path}",
        )

    if not os.access(folder_path, os.R_OK):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot read folder: {request.folder_path}",
        )

    # Get indexing service
    indexing_service = get_indexing_service()

    # Check if already indexing
    if indexing_service.is_indexing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Indexing already in progress. Please wait for completion.",
        )

    # Start indexing
    try:
        # Update request with resolved path
        resolved_request = IndexRequest(
            folder_path=str(folder_path),
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            recursive=request.recursive,
            include_code=request.include_code,
            supported_languages=request.supported_languages,
            code_chunk_strategy=request.code_chunk_strategy,
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
            generate_summaries=request.generate_summaries,
        )
        job_id = await indexing_service.start_indexing(resolved_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start indexing: {str(e)}",
        ) from e

    return IndexResponse(
        job_id=job_id,
        status="started",
        message=f"Indexing started for {request.folder_path}",
    )


@router.post(
    "/add",
    response_model=IndexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add Documents",
    description="Add documents from another folder to the existing index.",
)
async def add_documents(request: IndexRequest) -> IndexResponse:
    """
    Add documents from a new folder to the existing index.

    This is similar to the index endpoint but adds to the existing
    vector store instead of replacing it.

    Args:
        request: IndexRequest with folder_path and optional configuration.

    Returns:
        IndexResponse with job_id and status.
    """
    # Same validation as index_documents
    folder_path = Path(request.folder_path).expanduser().resolve()

    if not folder_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Folder not found: {request.folder_path}",
        )

    if not folder_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {request.folder_path}",
        )

    indexing_service = get_indexing_service()

    if indexing_service.is_indexing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Indexing already in progress. Please wait for completion.",
        )

    try:
        resolved_request = IndexRequest(
            folder_path=str(folder_path),
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            recursive=request.recursive,
            include_code=request.include_code,
            supported_languages=request.supported_languages,
            code_chunk_strategy=request.code_chunk_strategy,
            include_patterns=request.include_patterns,
            exclude_patterns=request.exclude_patterns,
        )
        job_id = await indexing_service.start_indexing(resolved_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add documents: {str(e)}",
        ) from e

    return IndexResponse(
        job_id=job_id,
        status="started",
        message=f"Adding documents from {request.folder_path}",
    )


@router.delete(
    "/",
    response_model=IndexResponse,
    summary="Reset Index",
    description="Delete all indexed documents and reset the vector store.",
)
async def reset_index() -> IndexResponse:
    """
    Reset the index by deleting all stored documents.

    Warning: This permanently removes all indexed content.

    Returns:
        IndexResponse confirming the reset.

    Raises:
        409: Indexing in progress
    """
    indexing_service = get_indexing_service()

    if indexing_service.is_indexing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reset while indexing is in progress.",
        )

    try:
        await indexing_service.reset()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset index: {str(e)}",
        ) from e

    return IndexResponse(
        job_id="reset",
        status="completed",
        message="Index has been reset successfully",
    )
