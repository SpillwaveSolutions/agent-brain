"""Query endpoints for semantic search."""

from fastapi import APIRouter, HTTPException, status

from ...models import QueryRequest, QueryResponse
from ...services import get_indexing_service, get_query_service

router = APIRouter()


@router.post(
    "/",
    response_model=QueryResponse,
    summary="Query Documents",
    description="Perform semantic search on indexed documents.",
)
async def query_documents(request: QueryRequest) -> QueryResponse:
    """
    Execute a semantic search query on indexed documents.

    Args:
        request: QueryRequest containing:
            - query: The search query text
            - top_k: Number of results to return (default: 5)
            - similarity_threshold: Minimum similarity score (default: 0.7)

    Returns:
        QueryResponse containing:
            - results: List of matching chunks with sources and scores
            - query_time_ms: Query execution time in milliseconds
            - total_results: Total number of results found

    Raises:
        400: Invalid query (empty or too long)
        503: Index not ready (indexing in progress or not initialized)
    """
    query_service = get_query_service()
    indexing_service = get_indexing_service()

    # Validate query
    query = request.query.strip()
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

    # Execute query
    try:
        response = await query_service.execute_query(request)
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
async def get_document_count() -> dict[str, int | bool]:
    """
    Get the total number of indexed document chunks.

    Returns:
        Dictionary with count of indexed chunks.
    """
    query_service = get_query_service()

    count = await query_service.get_document_count()

    return {
        "total_chunks": count,
        "ready": query_service.is_ready(),
    }
