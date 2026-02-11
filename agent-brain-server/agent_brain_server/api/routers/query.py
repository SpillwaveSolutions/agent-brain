"""Query endpoints for semantic search."""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from agent_brain_server.models import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=QueryResponse,
    summary="Query Documents",
    description="Perform semantic, keyword, or hybrid search on indexed documents.",
)
async def query_documents(
    request_body: QueryRequest, request: Request
) -> QueryResponse:
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

    return response


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
