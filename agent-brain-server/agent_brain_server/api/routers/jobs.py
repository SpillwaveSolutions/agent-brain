"""Job management endpoints for indexing job queue."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from agent_brain_server.job_queue.job_service import JobQueueService
from agent_brain_server.models.job import JobDetailResponse, JobListResponse

router = APIRouter()


@router.get(
    "/",
    response_model=JobListResponse,
    summary="List Jobs",
    description="List all indexing jobs with pagination.",
)
async def list_jobs(
    request: Request,
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of jobs to return"
    ),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
) -> JobListResponse:
    """List all jobs with pagination.

    Returns a paginated list of jobs with summary information and queue statistics.

    Args:
        request: FastAPI request for accessing app state.
        limit: Maximum number of jobs to return (1-100, default 50).
        offset: Number of jobs to skip for pagination (default 0).

    Returns:
        JobListResponse with list of job summaries and queue statistics.
    """
    job_service: JobQueueService = request.app.state.job_service
    return await job_service.list_jobs(limit=limit, offset=offset)


@router.get(
    "/{job_id}",
    response_model=JobDetailResponse,
    summary="Get Job Details",
    description="Get detailed information about a specific job.",
)
async def get_job(job_id: str, request: Request) -> JobDetailResponse:
    """Get details for a specific job.

    Returns full job information including progress, timestamps, and results.

    Args:
        job_id: The unique job identifier.
        request: FastAPI request for accessing app state.

    Returns:
        JobDetailResponse with full job details.

    Raises:
        404: Job not found.
    """
    job_service: JobQueueService = request.app.state.job_service
    job = await job_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return job


@router.delete(
    "/{job_id}",
    summary="Cancel Job",
    description="Cancel a pending or running job.",
)
async def cancel_job(job_id: str, request: Request) -> dict[str, Any]:
    """Cancel a job.

    Cancellation behavior depends on job status:
    - PENDING jobs are cancelled immediately
    - RUNNING jobs have cancel_requested flag set; worker will stop at next checkpoint
    - Completed/Failed/Cancelled jobs return 409 Conflict

    Args:
        job_id: The unique job identifier.
        request: FastAPI request for accessing app state.

    Returns:
        Dictionary with cancellation status and message.

    Raises:
        404: Job not found.
        409: Job cannot be cancelled (already completed, failed, or cancelled).
    """
    job_service: JobQueueService = request.app.state.job_service

    try:
        result = await job_service.cancel_job(job_id)
        return result
    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
