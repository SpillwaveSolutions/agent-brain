"""Tool registry — maps tool name to handler + schemas + annotations.

The registry is the single source of truth that ``server.py`` reads
when responding to MCP ``tools/list`` and ``tools/call``. Each entry:

    (handler, input_model, output_model, annotations)

where ``handler(client: ApiClient, args: input_model) -> output_model``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from ..schemas import (
    CancelJobInput,
    CancelJobOutput,
    GetJobInput,
    GetJobOutput,
    IndexFolderInput,
    IndexFolderOutput,
    ListJobsInput,
    ListJobsOutput,
    QueryCountInput,
    QueryCountOutput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    ServerHealthInput,
    ServerHealthOutput,
)
from . import file_types  # Phase 54 Plan 01; consumed by handlers in Plan 02+
from .index import handle_index_folder
from .jobs import handle_cancel_job, handle_get_job, handle_list_jobs
from .meta import handle_query_count, handle_server_health
from .search import handle_search_documents

# ``ToolHandler`` is intentionally typed as ``Any`` because each concrete
# handler narrows the arg/return to its specific input/output models
# (Callable is contravariant in arg types — strict mypy rejects the
# narrower signatures otherwise). Runtime dispatch in server.py uses the
# input_model on the ToolSpec to validate arguments before invocation.
ToolHandler = Any


class ToolSpec:
    """A registered MCP tool."""

    __slots__ = (
        "name",
        "description",
        "handler",
        "input_model",
        "output_model",
        "annotations",
    )

    def __init__(
        self,
        *,
        name: str,
        description: str,
        handler: ToolHandler,
        input_model: type[BaseModel],
        output_model: type[BaseModel],
        annotations: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.handler = handler
        self.input_model = input_model
        self.output_model = output_model
        self.annotations = annotations or {}


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_documents": ToolSpec(
        name="search_documents",
        description=(
            "Search indexed documents using semantic, BM25, hybrid, graph, "
            "or multi-stage retrieval. Returns ranked chunks with source "
            "paths and similarity scores."
        ),
        handler=handle_search_documents,
        input_model=SearchDocumentsInput,
        output_model=SearchDocumentsOutput,
        annotations={"readOnlyHint": True, "openWorldHint": True},
    ),
    "query_count": ToolSpec(
        name="query_count",
        description="Return total documents and chunks currently indexed.",
        handler=handle_query_count,
        input_model=QueryCountInput,
        output_model=QueryCountOutput,
        annotations={"readOnlyHint": True},
    ),
    "index_folder": ToolSpec(
        name="index_folder",
        description=(
            "Queue a folder for indexing. Returns a job_id the caller can "
            "poll with get_job. Honors include_code, chunk_size, "
            "chunk_overlap, force, and allow_external."
        ),
        handler=handle_index_folder,
        input_model=IndexFolderInput,
        output_model=IndexFolderOutput,
        annotations={"destructiveHint": False, "openWorldHint": True},
    ),
    "get_job": ToolSpec(
        name="get_job",
        description="Look up the current state of a specific indexing job.",
        handler=handle_get_job,
        input_model=GetJobInput,
        output_model=GetJobOutput,
        annotations={"readOnlyHint": True},
    ),
    "list_jobs": ToolSpec(
        name="list_jobs",
        description=(
            "List jobs in the queue with cursor-based pagination "
            "(opaque base64-offset cursor)."
        ),
        handler=handle_list_jobs,
        input_model=ListJobsInput,
        output_model=ListJobsOutput,
        annotations={"readOnlyHint": True},
    ),
    "cancel_job": ToolSpec(
        name="cancel_job",
        description=(
            "Cancel a job. Requires confirm:true in the input as a "
            "destructive-operation guard."
        ),
        handler=handle_cancel_job,
        input_model=CancelJobInput,
        output_model=CancelJobOutput,
        annotations={"destructiveHint": True},
    ),
    "server_health": ToolSpec(
        name="server_health",
        description=(
            "Return Agent Brain server health, version, and mode. Used by "
            "MCP startup to verify backend reachability and version compat."
        ),
        handler=handle_server_health,
        input_model=ServerHealthInput,
        output_model=ServerHealthOutput,
        annotations={"readOnlyHint": True},
    ),
}

__all__ = ["TOOL_REGISTRY", "ToolSpec", "ToolHandler", "file_types"]
