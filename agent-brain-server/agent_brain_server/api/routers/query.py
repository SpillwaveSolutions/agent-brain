"""Query endpoints for semantic search."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from agent_brain_server.api.security import verify_api_key
from agent_brain_server.models import ChunkRecord, QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post(
    "/",
    response_model=QueryResponse,
    summary="Query Documents",
    description="Perform semantic, keyword, or hybrid search on indexed documents.",
)
async def query_documents(request_body: QueryRequest, request: Request) -> JSONResponse:
    """Execute a search query on indexed documents.

    Args:
        request_body: QueryRequest containing query parameters.
        request: FastAPI request for accessing app state.

    Returns:
        QueryResponse with ranked results and timing.

    Raises:
        400: Invalid query (empty or too long)
        409: Embedding provider mismatch (re-index required)
        503: Index not ready (indexing in progress or not initialized)
    """
    from agent_brain_server.services import QueryService
    from agent_brain_server.services.indexing_service import IndexingService

    query_service: QueryService = request.app.state.query_service
    indexing_service: IndexingService = request.app.state.indexing_service

    # Validate query
    query = request_body.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty",
        )

    # Check if service is ready
    if not query_service.is_ready():
        if indexing_service.is_indexing:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Index not ready. Indexing is in progress.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Index not ready. Please index documents first.",
            )

    # Check for embedding provider mismatch (PROV-07 query-time guard)
    embedding_warning = getattr(request.app.state, "embedding_warning", None)
    if embedding_warning:
        # Check if it's a dimension mismatch (critical) vs provider/model only
        if "d)" in embedding_warning:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Embedding mismatch: {embedding_warning} "
                    "Re-index with --force to resolve."
                ),
            )

    # Execute query
    try:
        response = await query_service.execute_query(request_body)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}",
        ) from e

    # Issue #159: when explain=false (default), omit `explanation` per result
    # so the wire format is byte-identical to historical responses. When
    # explain=true, dump normally — `null` values inside ResultExplanation are
    # explicit signals (e.g., matched_terms=null means no BM25 contribution)
    # and are intentionally preserved.
    if not request_body.explain:
        payload = response.model_dump(exclude={"results": {"__all__": {"explanation"}}})
    else:
        payload = response.model_dump()
    return JSONResponse(content=payload)


@router.get(
    "/chunk/{chunk_id}",
    response_model=ChunkRecord,
    summary="Get Chunk by ID",
    description=(
        "O(1) lookup of a single chunk by its primary-key chunk_id. "
        "Returns the chunk's content plus full metadata per the v2 "
        "design doc §2.3 (ChunkRecord shape). Embeddings are NOT "
        "included — fetch them via POST /query/ if needed. Returns 404 "
        "with a structured error body when the chunk does not exist."
    ),
    responses={
        404: {
            "description": "Chunk not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "error": "chunk_not_found",
                            "chunk_id": "missing-id",
                        }
                    }
                }
            },
        }
    },
)
async def get_chunk_by_id(chunk_id: str, request: Request) -> ChunkRecord:
    """Look up a single chunk by primary key.

    Backs the future MCP ``chunk://<chunk_id>`` URI scheme (URI-01,
    Phase 51). No authentication required (matches v1 stance; auth is
    v4 work, separately tracked under #179).

    Args:
        chunk_id: The unique chunk identifier (primary key).
        request: FastAPI request for accessing the storage backend on
            ``app.state``.

    Returns:
        :class:`ChunkRecord` with the chunk's content and metadata. The
        ``embedding`` field is intentionally absent from the response
        payload per the v2 design doc.

    Raises:
        404: Structured ``{"error": "chunk_not_found", "chunk_id": "..."}``
            when no chunk with the supplied ID exists.
        500: When the underlying storage backend fails. The error
            message is surfaced as ``detail``.
    """
    from agent_brain_server.storage.protocol import (
        StorageBackendProtocol,
        StorageError,
    )

    storage: StorageBackendProtocol = request.app.state.storage_backend

    try:
        record = await storage.get_chunk_by_id(chunk_id)
    except StorageError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chunk lookup failed: {e.message}",
        ) from e

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "chunk_not_found", "chunk_id": chunk_id},
        )

    return record


@router.get(
    "/count",
    summary="Document Count",
    description="Get the total number of indexed document chunks.",
)
async def get_document_count(request: Request) -> dict[str, int | bool]:
    """Get the total number of indexed document chunks.

    Args:
        request: FastAPI request for accessing app state.

    Returns:
        Dictionary with count of indexed chunks.
    """
    query_service = request.app.state.query_service

    count = await query_service.get_document_count()

    return {
        "total_chunks": count,
        "ready": query_service.is_ready(),
    }
