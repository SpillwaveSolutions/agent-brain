"""Job-related tools: ``get_job``, ``list_jobs``, ``cancel_job``."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from ..schemas import (
    CancelJobInput,
    CancelJobOutput,
    GetJobInput,
    GetJobOutput,
    JobSummary,
    ListJobsInput,
    ListJobsOutput,
)

if TYPE_CHECKING:
    from ..client import ApiClient


def _decode_cursor(cursor: str | None) -> int:
    """Translate an opaque base64-encoded cursor to a numeric offset."""
    if cursor is None:
        return 0
    try:
        return int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii"))
    except Exception:
        # Bad cursor → start from the beginning rather than blow up the call.
        return 0


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")


def handle_get_job(client: ApiClient, args: GetJobInput) -> GetJobOutput:
    raw = client.get_job(args.job_id)
    return GetJobOutput(
        job_id=str(raw.get("job_id", args.job_id)),
        status=str(raw.get("status", "unknown")),
        progress_percent=raw.get("progress_percent"),
        message=raw.get("message"),
        started_at=raw.get("started_at"),
        completed_at=raw.get("completed_at"),
    )


def handle_list_jobs(client: ApiClient, args: ListJobsInput) -> ListJobsOutput:
    offset = _decode_cursor(args.cursor)
    raw = client.list_jobs(limit=args.limit, offset=offset)
    jobs_data = raw.get("jobs") or raw.get("data") or []
    jobs = [
        JobSummary(
            job_id=str(j.get("job_id", "")),
            status=str(j.get("status", "unknown")),
            progress_percent=j.get("progress_percent"),
            message=j.get("message"),
        )
        for j in jobs_data
    ]
    # If the server returned exactly ``limit`` items, assume more exist
    # and produce a cursor; otherwise this is the last page.
    next_cursor = (
        _encode_cursor(offset + len(jobs)) if len(jobs) == args.limit else None
    )
    return ListJobsOutput(jobs=jobs, next_cursor=next_cursor)


def handle_cancel_job(client: ApiClient, args: CancelJobInput) -> CancelJobOutput:
    # confirm:True is enforced by the Literal[True] in the input model —
    # Pydantic raises ValidationError before we reach the handler.
    raw = client.cancel_job(args.job_id)
    return CancelJobOutput(
        job_id=args.job_id,
        cancelled=bool(raw.get("cancelled", True)),
        message=raw.get("message"),
    )
