"""Health check endpoints."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Request

from doc_serve_server.models import HealthStatus, IndexingStatus

router = APIRouter()


@router.get(
    "/",
    response_model=HealthStatus,
    summary="Health Check",
    description="Returns the current server health status.",
)
async def health_check(request: Request) -> HealthStatus:
    """Check server health status.

    Returns:
        HealthStatus with current status:
        - healthy: Server is running and ready for queries
        - indexing: Server is currently indexing documents
        - degraded: Server is up but some services are unavailable
        - unhealthy: Server is not operational
    """
    indexing_service = request.app.state.indexing_service
    vector_store = request.app.state.vector_store

    # Determine status
    status: Literal["healthy", "indexing", "degraded", "unhealthy"]
    if indexing_service.is_indexing:
        status = "indexing"
        message = f"Indexing in progress: {indexing_service.state.folder_path}"
    elif not vector_store.is_initialized:
        status = "degraded"
        message = "Vector store not initialized"
    elif indexing_service.state.error:
        status = "degraded"
        message = f"Last indexing failed: {indexing_service.state.error}"
    else:
        status = "healthy"
        message = "Server is running and ready for queries"

    # Multi-instance metadata
    mode = getattr(request.app.state, "mode", "project")
    instance_id = getattr(request.app.state, "instance_id", None)
    project_id = getattr(request.app.state, "project_id", None)
    active_projects = getattr(request.app.state, "active_projects", None)

    return HealthStatus(
        status=status,
        message=message,
        timestamp=datetime.now(timezone.utc),
        version="1.1.0",
        mode=mode,
        instance_id=instance_id,
        project_id=project_id,
        active_projects=active_projects,
    )


@router.get(
    "/status",
    response_model=IndexingStatus,
    summary="Indexing Status",
    description="Returns detailed indexing status information.",
)
async def indexing_status(request: Request) -> IndexingStatus:
    """Get detailed indexing status.

    Returns:
        IndexingStatus with:
        - total_documents: Number of documents indexed
        - total_chunks: Number of chunks in vector store
        - indexing_in_progress: Boolean indicating active indexing
        - last_indexed_at: Timestamp of last indexing operation
        - indexed_folders: List of folders that have been indexed
    """
    indexing_service = request.app.state.indexing_service
    status = await indexing_service.get_status()

    return IndexingStatus(
        total_documents=status["total_documents"],
        total_chunks=status["total_chunks"],
        total_doc_chunks=status.get("total_doc_chunks", 0),
        total_code_chunks=status.get("total_code_chunks", 0),
        indexing_in_progress=status["is_indexing"],
        current_job_id=status["current_job_id"],
        progress_percent=status["progress_percent"],
        last_indexed_at=(
            datetime.fromisoformat(status["completed_at"])
            if status["completed_at"]
            else None
        ),
        indexed_folders=status["indexed_folders"],
        supported_languages=status.get("supported_languages", []),
    )
