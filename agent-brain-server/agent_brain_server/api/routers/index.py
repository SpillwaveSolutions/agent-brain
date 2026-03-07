"""Indexing endpoints for document processing with job queue support."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from agent_brain_server.config import settings
from agent_brain_server.models import IndexRequest, IndexResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Maximum queue length for backpressure
MAX_QUEUE_LENGTH = settings.AGENT_BRAIN_MAX_QUEUE


async def _handle_dry_run(
    request: Request,
    request_body: IndexRequest,
    folder_path: Path,
) -> IndexResponse:
    """Handle dry_run mode: validate injector against sample chunks without enqueueing.

    Loads up to 3 files from the folder, chunks them, applies the injector,
    and returns a report without creating a job.

    Args:
        request: FastAPI request for accessing app state.
        request_body: IndexRequest with injection config.
        folder_path: Resolved folder path.

    Returns:
        IndexResponse with dry_run report as message.
    """
    from agent_brain_server.services.content_injector import ContentInjector

    indexing_service = request.app.state.indexing_service
    document_loader = indexing_service.document_loader
    chunker = indexing_service.chunker

    # Build injector (may be None if no injection configured)
    injector: ContentInjector | None = None
    if request_body.injector_script or request_body.folder_metadata_file:
        try:
            injector = ContentInjector.build(
                script_path=request_body.injector_script,
                metadata_path=request_body.folder_metadata_file,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to load injector: {exc}",
            ) from exc

    # Load a sample of documents (limit to first 3 files)
    try:
        documents = await document_loader.load_files(
            str(folder_path),
            recursive=request_body.recursive,
            include_code=request_body.include_code,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load sample documents: {exc}",
        ) from exc

    sample_docs = documents[:3]

    # Chunk sample documents
    try:
        sample_chunks = await chunker.chunk_documents(sample_docs)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to chunk sample documents: {exc}",
        ) from exc

    # Limit to 10 chunks for the report
    sample_chunks = sample_chunks[:10]

    # Apply injector and collect results
    injected_keys: set[str] = set()
    enriched_count = 0

    if injector is not None:
        known_keys: set[str] = {
            "chunk_id",
            "source",
            "file_name",
            "chunk_index",
            "total_chunks",
            "source_type",
            "created_at",
            "language",
            "heading_path",
            "section_title",
            "content_type",
            "symbol_name",
            "symbol_kind",
            "start_line",
            "end_line",
            "section_summary",
            "prev_section_summary",
            "docstring",
            "parameters",
            "return_type",
            "decorators",
            "imports",
        }
        for chunk in sample_chunks:
            original_dict: dict[str, Any] = chunk.metadata.to_dict()
            enriched_dict = injector.apply(original_dict)
            new_keys = {k for k in enriched_dict if k not in known_keys}
            if new_keys:
                injected_keys.update(new_keys)
                enriched_count += 1

    report = (
        f"Dry-run complete: sampled {len(sample_docs)} files, "
        f"{len(sample_chunks)} chunks. "
        f"Injection enriched {enriched_count}/{len(sample_chunks)} chunks "
        f"with keys: {sorted(injected_keys) if injected_keys else 'none'}."
    )

    return IndexResponse(
        job_id="dry_run",
        status="completed",
        message=report,
    )


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

    # Validate include_types presets early (before enqueueing)
    if request_body.include_types is not None:
        from agent_brain_server.services.file_type_presets import resolve_file_types

        try:
            resolve_file_types(request_body.include_types)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

    # Validate injector script path if provided (INJECT-04)
    if request_body.injector_script is not None:
        script_path = Path(request_body.injector_script).expanduser().resolve()
        if not script_path.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Injector script not found: {request_body.injector_script}",
            )
        if script_path.suffix != ".py":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Injector script must be a .py file",
            )

    # Validate folder metadata file path if provided (INJECT-04)
    if request_body.folder_metadata_file is not None:
        meta_path = Path(request_body.folder_metadata_file).expanduser().resolve()
        if not meta_path.exists():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Metadata file not found: {request_body.folder_metadata_file}"
                ),
            )

    # Handle dry_run mode (INJECT-02): validate injector without enqueueing
    if request_body.dry_run:
        return await _handle_dry_run(request, request_body, folder_path)

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
            include_types=request_body.include_types,
            exclude_patterns=request_body.exclude_patterns,
            generate_summaries=request_body.generate_summaries,
            force=request_body.force,
            injector_script=request_body.injector_script,
            folder_metadata_file=request_body.folder_metadata_file,
            watch_mode=request_body.watch_mode,
            watch_debounce_seconds=request_body.watch_debounce_seconds,
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

    # Validate include_types presets early (before enqueueing)
    if request_body.include_types is not None:
        from agent_brain_server.services.file_type_presets import resolve_file_types

        try:
            resolve_file_types(request_body.include_types)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

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
            include_types=request_body.include_types,
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
