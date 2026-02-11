"""Indexing endpoints for document processing with job queue support."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, status

from agent_brain_server.config import settings
from agent_brain_server.models import IndexRequest, IndexResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum queue length for backpressure
MAX_QUEUE_LENGTH = settings.AGENT_BRAIN_MAX_QUEUE


@router.post(
    "/",
    response_model=IndexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Index Documents",
    description="Enqueue a job to index documents from a folder.",
)
async def index_documents(
    request_body: IndexRequest,
    request: Request,
    force: bool = Query(False, description="Bypass deduplication and force a new job"),
    allow_external: bool = Query(
        False, description="Allow paths outside the project directory"
    ),
    rebuild_graph: bool = Query(
        False,
        description="Rebuild only the graph index without re-indexing documents "
        "(requires ENABLE_GRAPH_INDEX=true)",
    ),
) -> IndexResponse:
    """Enqueue an indexing job for documents from the specified folder.

    This endpoint accepts the request and returns immediately with a job ID.
    The job is processed asynchronously by a background worker.
    Use the /index/jobs/{job_id} endpoint to monitor progress.

    If rebuild_graph=true, only rebuilds the graph index from existing chunks
    without re-indexing documents (requires ENABLE_GRAPH_INDEX=true).

    Args:
        request_body: IndexRequest with folder_path and optional configuration.
        request: FastAPI request for accessing app state.
        force: If True, bypass deduplication and create a new job.
        allow_external: If True, allow indexing paths outside the project.
        rebuild_graph: If True, only rebuild graph index from existing chunks.

    Returns:
        IndexResponse with job_id and status.

    Raises:
        400: Invalid folder path or path outside project (without allow_external)
        400: rebuild_graph=true but GraphRAG not enabled
        429: Queue is full (backpressure)
    """
    # Handle rebuild_graph parameter - rebuild graph index only
    if rebuild_graph:
        logger.info("Received rebuild_graph request")
        if not settings.ENABLE_GRAPH_INDEX:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot rebuild graph: ENABLE_GRAPH_INDEX is not enabled. "
                "Set ENABLE_GRAPH_INDEX=true to use GraphRAG features.",
            )

        # Get indexing service and rebuild graph from existing chunks
        indexing_service = request.app.state.indexing_service
        try:
            graph_manager = indexing_service.graph_index_manager

            # Get existing chunks from vector store
            vector_store = indexing_service.vector_store
            if not vector_store.is_initialized:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No documents indexed. Index documents first before "
                    "rebuilding the graph.",
                )

            # Clear existing graph and rebuild
            graph_manager.clear()
            graph_manager.graph_store.initialize()

            # Get all documents from BM25 index (has the text content)
            bm25_manager = indexing_service.bm25_manager
            if bm25_manager._index is not None:
                nodes = bm25_manager._index.nodes
                triplet_count = graph_manager.build_from_documents(nodes)
                logger.info(f"Graph index rebuilt with {triplet_count} triplets")

                return IndexResponse(
                    job_id="rebuild_graph",
                    status="completed",
                    message=f"Graph index rebuilt successfully with {triplet_count} "
                    "triplets",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No documents indexed. Index documents first before "
                    "rebuilding the graph.",
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to rebuild graph index: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to rebuild graph index: {str(e)}",
            ) from e

    # Validate folder path
    folder_path = Path(request_body.folder_path).expanduser().resolve()

    if not folder_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Folder not found: {request_body.folder_path}",
        )

    if not folder_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {request_body.folder_path}",
        )

    if not os.access(folder_path, os.R_OK):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot read folder: {request_body.folder_path}",
        )

    # Get job service from app state
    job_service = request.app.state.job_service

    # Backpressure check (pending + running to prevent overflow)
    stats = await job_service.get_queue_stats()
    active_jobs = stats.pending + stats.running
    if active_jobs >= MAX_QUEUE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Queue full ({stats.pending} pending, {stats.running} running). "
            "Try again later.",
        )

    # Enqueue the job
    try:
        # Update request with resolved path
        resolved_request = IndexRequest(
            folder_path=str(folder_path),
            chunk_size=request_body.chunk_size,
            chunk_overlap=request_body.chunk_overlap,
            recursive=request_body.recursive,
            include_code=request_body.include_code,
            supported_languages=request_body.supported_languages,
            code_chunk_strategy=request_body.code_chunk_strategy,
            include_patterns=request_body.include_patterns,
            exclude_patterns=request_body.exclude_patterns,
            generate_summaries=request_body.generate_summaries,
            force=request_body.force,
        )

        result = await job_service.enqueue_job(
            request=resolved_request,
            operation="index",
            force=force,
            allow_external=allow_external,
        )
    except ValueError as e:
        # Path validation error (outside project)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue indexing job: {str(e)}",
        ) from e

    # Build response message
    if result.dedupe_hit:
        message = (
            f"Duplicate detected - existing job {result.job_id} is {result.status}"
        )
    else:
        message = f"Job queued for {request_body.folder_path}"

    return IndexResponse(
        job_id=result.job_id,
        status=result.status,
        message=message,
    )


@router.post(
    "/add",
    response_model=IndexResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Add Documents",
    description="Enqueue a job to add documents from another folder.",
)
async def add_documents(
    request_body: IndexRequest,
    request: Request,
    force: bool = Query(False, description="Bypass deduplication and force a new job"),
    allow_external: bool = Query(
        False, description="Allow paths outside the project directory"
    ),
) -> IndexResponse:
    """Enqueue a job to add documents from a new folder to the existing index.

    This is similar to the index endpoint but adds to the existing
    vector store instead of replacing it.

    Args:
        request_body: IndexRequest with folder_path and optional configuration.
        request: FastAPI request for accessing app state.
        force: If True, bypass deduplication and create a new job.
        allow_external: If True, allow indexing paths outside the project.

    Returns:
        IndexResponse with job_id and status.
    """
    # Same validation as index_documents
    folder_path = Path(request_body.folder_path).expanduser().resolve()

    if not folder_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Folder not found: {request_body.folder_path}",
        )

    if not folder_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {request_body.folder_path}",
        )

    # Get job service from app state
    job_service = request.app.state.job_service

    # Backpressure check (pending + running to prevent overflow)
    stats = await job_service.get_queue_stats()
    active_jobs = stats.pending + stats.running
    if active_jobs >= MAX_QUEUE_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Queue full ({stats.pending} pending, {stats.running} running). "
            "Try again later.",
        )

    try:
        resolved_request = IndexRequest(
            folder_path=str(folder_path),
            chunk_size=request_body.chunk_size,
            chunk_overlap=request_body.chunk_overlap,
            recursive=request_body.recursive,
            include_code=request_body.include_code,
            supported_languages=request_body.supported_languages,
            code_chunk_strategy=request_body.code_chunk_strategy,
            include_patterns=request_body.include_patterns,
            exclude_patterns=request_body.exclude_patterns,
            force=request_body.force,
        )

        result = await job_service.enqueue_job(
            request=resolved_request,
            operation="add",
            force=force,
            allow_external=allow_external,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue add job: {str(e)}",
        ) from e

    # Build response message
    if result.dedupe_hit:
        message = (
            f"Duplicate detected - existing job {result.job_id} is {result.status}"
        )
    else:
        message = f"Job queued to add documents from {request_body.folder_path}"

    return IndexResponse(
        job_id=result.job_id,
        status=result.status,
        message=message,
    )


@router.delete(
    "/",
    response_model=IndexResponse,
    summary="Reset Index",
    description="Delete all indexed documents and reset the vector store.",
)
async def reset_index(request: Request) -> IndexResponse:
    """Reset the index by deleting all stored documents.

    Warning: This permanently removes all indexed content.
    Cannot be performed while jobs are running.

    Args:
        request: FastAPI request for accessing app state.

    Returns:
        IndexResponse confirming the reset.

    Raises:
        409: Jobs in progress
    """
    job_service = request.app.state.job_service
    indexing_service = request.app.state.indexing_service

    # Check if any jobs are running
    stats = await job_service.get_queue_stats()
    if stats.running > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reset while indexing jobs are in progress.",
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
