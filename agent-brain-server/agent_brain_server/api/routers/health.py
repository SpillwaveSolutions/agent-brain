"""Health check endpoints with non-blocking queue status."""

import logging
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request

from agent_brain_server import __version__
from agent_brain_server.config.provider_config import (
    _find_config_file,
    load_provider_settings,
    validate_provider_config,
)
from agent_brain_server.models import HealthStatus, IndexingStatus
from agent_brain_server.models.health import ProviderHealth, ProvidersStatus
from agent_brain_server.providers.factory import ProviderRegistry
from agent_brain_server.storage import get_effective_backend_type

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/",
    response_model=HealthStatus,
    summary="Health Check",
    description="Returns the current server health status.",
)
async def health_check(request: Request) -> HealthStatus:
    """Check server health status.

    This endpoint never blocks and always returns quickly.

    Returns:
        HealthStatus with current status:
        - healthy: Server is running and ready for queries
        - indexing: Server is currently indexing documents
        - degraded: Server is up but some services are unavailable
        - unhealthy: Server is not operational
    """
    vector_store = getattr(request.app.state, "vector_store", None)
    job_service = getattr(request.app.state, "job_service", None)

    # Determine status using queue service (non-blocking)
    status: Literal["healthy", "indexing", "degraded", "unhealthy"]
    message: str

    # Check queue status (non-blocking)
    is_indexing = False
    current_folder = None
    if job_service:
        try:
            queue_stats = await job_service.get_queue_stats()
            is_indexing = queue_stats.running > 0
            if is_indexing and queue_stats.current_job_id:
                # Get current job details for message
                current_job = await job_service.get_job(queue_stats.current_job_id)
                if current_job:
                    current_folder = current_job.folder_path
        except Exception:
            # Non-blocking: don't fail health check if queue service errors
            pass

    if is_indexing:
        status = "indexing"
        message = f"Indexing in progress: {current_folder or 'unknown'}"
    elif vector_store is None:
        # Non-chroma backend -- check storage_backend directly
        storage_backend = getattr(request.app.state, "storage_backend", None)
        if storage_backend and storage_backend.is_initialized:
            status = "healthy"
            message = "Server is running and ready for queries"
        else:
            status = "degraded"
            message = "Storage backend not initialized"
    elif not vector_store.is_initialized:
        status = "degraded"
        message = "Vector store not initialized"
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
        version=__version__,
        mode=mode,
        instance_id=instance_id,
        project_id=project_id,
        active_projects=active_projects,
    )


@router.get(
    "/status",
    response_model=IndexingStatus,
    summary="Indexing Status",
    description="Returns detailed indexing status information. Never blocks.",
)
async def indexing_status(request: Request) -> IndexingStatus:
    """Get detailed indexing status.

    This endpoint never blocks and always returns quickly, even during indexing.

    Returns:
        IndexingStatus with:
        - total_documents: Number of documents indexed
        - total_chunks: Number of chunks in vector store
        - indexing_in_progress: Boolean indicating active indexing
        - queue_pending: Number of pending jobs
        - queue_running: Number of running jobs (0 or 1)
        - current_job_running_time_ms: How long current job has been running
        - last_indexed_at: Timestamp of last indexing operation
        - indexed_folders: List of folders that have been indexed
    """
    indexing_service = request.app.state.indexing_service
    vector_store = getattr(request.app.state, "vector_store", None)
    job_service = getattr(request.app.state, "job_service", None)

    # Get vector store count (non-blocking read)
    try:
        if vector_store is not None and vector_store.is_initialized:
            total_chunks = await vector_store.get_count()
        else:
            storage_backend = getattr(request.app.state, "storage_backend", None)
            if storage_backend and storage_backend.is_initialized:
                total_chunks = await storage_backend.get_count()
            else:
                total_chunks = 0
    except Exception:
        total_chunks = 0

    # Get queue status (non-blocking)
    queue_pending = 0
    queue_running = 0
    current_job_id = None
    current_job_running_time_ms = None
    progress_percent = 0.0

    if job_service:
        try:
            queue_stats = await job_service.get_queue_stats()
            queue_pending = queue_stats.pending
            queue_running = queue_stats.running
            current_job_id = queue_stats.current_job_id
            current_job_running_time_ms = queue_stats.current_job_running_time_ms

            # Get progress from current job
            if current_job_id:
                current_job = await job_service.get_job(current_job_id)
                if current_job and current_job.progress:
                    progress_percent = current_job.progress.percent_complete
        except Exception:
            # Non-blocking: don't fail status if queue service errors
            pass

    # Get indexing service status for historical data
    # This is read-only and non-blocking
    service_status = await indexing_service.get_status()

    # Override graph index status when on non-chroma backend
    backend_type = get_effective_backend_type()
    graph_index_info = service_status.get("graph_index")
    if backend_type != "chroma" and graph_index_info is not None:
        reason_msg = (
            f"Graph queries require ChromaDB backend (current: {backend_type})"
        )
        graph_index_info = {
            "enabled": False,
            "initialized": False,
            "entity_count": 0,
            "relationship_count": 0,
            "store_type": "unavailable",
            "reason": reason_msg,
        }
        service_status["graph_index"] = graph_index_info

    return IndexingStatus(
        total_documents=service_status.get("total_documents", 0),
        total_chunks=total_chunks,
        total_doc_chunks=service_status.get("total_doc_chunks", 0),
        total_code_chunks=service_status.get("total_code_chunks", 0),
        indexing_in_progress=queue_running > 0,
        current_job_id=current_job_id,
        progress_percent=progress_percent,
        last_indexed_at=(
            datetime.fromisoformat(service_status["completed_at"])
            if service_status.get("completed_at")
            else None
        ),
        indexed_folders=service_status.get("indexed_folders", []),
        supported_languages=service_status.get("supported_languages", []),
        graph_index=service_status.get("graph_index"),
        # Queue status (Feature 115)
        queue_pending=queue_pending,
        queue_running=queue_running,
        current_job_running_time_ms=current_job_running_time_ms,
    )


@router.get(
    "/providers",
    response_model=ProvidersStatus,
    summary="Provider Status",
    description="Returns status of all configured providers with health checks.",
)
async def providers_status(request: Request) -> ProvidersStatus:
    """Get detailed status of all configured providers.

    Returns:
        ProvidersStatus with configuration source, validation errors,
        and health status of each provider.
    """
    # Get config source
    config_file = _find_config_file()
    config_source = str(config_file) if config_file else None

    # Get strict mode from app state
    strict_mode = getattr(request.app.state, "strict_mode", False)

    # Load settings and validate
    settings = load_provider_settings()
    validation_errors = validate_provider_config(settings)
    error_messages = [str(e) for e in validation_errors]

    providers: list[ProviderHealth] = []

    # Check embedding provider
    try:
        embedding_provider = ProviderRegistry.get_embedding_provider(settings.embedding)
        embedding_status = "healthy"
        embedding_message = None
        embedding_dimensions = embedding_provider.get_dimensions()
    except Exception as e:
        embedding_status = "unavailable"
        embedding_message = str(e)
        embedding_dimensions = None

    providers.append(
        ProviderHealth(
            provider_type="embedding",
            provider_name=str(settings.embedding.provider),
            model=settings.embedding.model,
            status=embedding_status,
            message=embedding_message,
            dimensions=embedding_dimensions,
        )
    )

    # Check summarization provider
    try:
        _ = ProviderRegistry.get_summarization_provider(settings.summarization)
        summarization_status = "healthy"
        summarization_message = None
    except Exception as e:
        summarization_status = "unavailable"
        summarization_message = str(e)

    providers.append(
        ProviderHealth(
            provider_type="summarization",
            provider_name=str(settings.summarization.provider),
            model=settings.summarization.model,
            status=summarization_status,
            message=summarization_message,
        )
    )

    # Check reranker provider if reranking is enabled
    from agent_brain_server.config import settings as app_settings

    if app_settings.ENABLE_RERANKING:
        try:
            _ = ProviderRegistry.get_reranker_provider(settings.reranker)
            reranker_status = "healthy"
            reranker_message = None
        except Exception as e:
            reranker_status = "unavailable"
            reranker_message = str(e)

        providers.append(
            ProviderHealth(
                provider_type="reranker",
                provider_name=str(settings.reranker.provider),
                model=settings.reranker.model,
                status=reranker_status,
                message=reranker_message,
            )
        )

    return ProvidersStatus(
        config_source=config_source,
        strict_mode=strict_mode,
        validation_errors=error_messages,
        providers=providers,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/postgres",
    summary="PostgreSQL Health",
    description=(
        "Returns PostgreSQL connection pool metrics and database info. "
        "Only available when storage backend is 'postgres'."
    ),
)
async def postgres_health(request: Request) -> dict[str, Any]:
    """Check PostgreSQL backend health and pool metrics.

    Returns pool status (pool_size, checked_in, checked_out, overflow)
    and database connection info when the backend is PostgreSQL.

    Returns:
        Dictionary with pool metrics and database info.

    Raises:
        HTTPException: If backend is not postgres (400).
    """
    backend_type = get_effective_backend_type()
    if backend_type != "postgres":
        raise HTTPException(
            status_code=400,
            detail=(
                "PostgreSQL health endpoint only available when "
                "storage backend is 'postgres'"
            ),
        )

    try:
        backend = request.app.state.storage_backend
        pool_metrics = await backend.connection_manager.get_pool_status()

        # Try a test query for database version
        from sqlalchemy import text as sa_text

        db_info: dict[str, Any] = {}
        try:
            async with backend.connection_manager.engine.connect() as conn:
                result = await conn.execute(sa_text("SELECT version()"))
                row = result.fetchone()
                if row:
                    db_info["version"] = row[0]
        except Exception:
            db_info["version"] = "unavailable"

        db_info["host"] = backend.config.host
        db_info["port"] = backend.config.port
        db_info["database"] = backend.config.database

        return {
            "status": "healthy",
            "backend": "postgres",
            "pool": pool_metrics,
            "database": db_info,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("PostgreSQL health check failed: %s", e)
        return {
            "status": "unhealthy",
            "backend": "postgres",
            "error": str(e),
        }
