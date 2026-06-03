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
    AddDocumentsInput,
    AddDocumentsOutput,
    CacheStatusInput,
    CacheStatusOutput,
    CancelJobInput,
    CancelJobOutput,
    ClearCacheInput,
    ClearCacheOutput,
    ExplainResultInput,
    ExplainResultOutput,
    GetJobInput,
    GetJobOutput,
    IndexFolderInput,
    IndexFolderOutput,
    InjectDocumentsInput,
    InjectDocumentsOutput,
    ListFileTypesInput,
    ListFileTypesOutput,
    ListFoldersInput,
    ListFoldersOutput,
    ListJobsInput,
    ListJobsOutput,
    QueryCountInput,
    QueryCountOutput,
    RemoveFolderInput,
    RemoveFolderOutput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    ServerHealthInput,
    ServerHealthOutput,
)
from . import file_types  # Phase 54 Plan 01; consumed by handlers in Plan 02+
from .cache import handle_cache_status, handle_clear_cache
from .explain import handle_explain_result
from .file_types import handle_list_file_types
from .folders import handle_list_folders, handle_remove_folder
from .index import handle_add_documents, handle_index_folder
from .inject import handle_inject_documents
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
    # ---------------------------------------------------------------------
    # Phase 54 Plan 02 — 4 read-only tools (TOOL-01 / TOOL-05 / TOOL-07 /
    # TOOL-09). All four are flagged ``readOnlyHint: True``. ``explain_result``
    # additionally carries ``openWorldHint: True`` because it triggers a
    # search-pipeline re-execution against the live corpus.
    # ---------------------------------------------------------------------
    "explain_result": ToolSpec(
        name="explain_result",
        description=(
            "Get provenance and scoring breakdown for a specific result chunk. "
            "Re-executes the original query with explain=true; not suitable for "
            "high-frequency calls. Use search_documents(..., explain=true) "
            "directly for known-bulk explanation needs."
        ),
        handler=handle_explain_result,
        input_model=ExplainResultInput,
        output_model=ExplainResultOutput,
        annotations={"readOnlyHint": True, "openWorldHint": True},
    ),
    "list_folders": ToolSpec(
        name="list_folders",
        description=(
            "List all indexed folders with chunk counts and last-indexed metadata."
        ),
        handler=handle_list_folders,
        input_model=ListFoldersInput,
        output_model=ListFoldersOutput,
        annotations={"readOnlyHint": True},
    ),
    "cache_status": ToolSpec(
        name="cache_status",
        description="Show embedding cache statistics (hit rate, size, entries).",
        handler=handle_cache_status,
        input_model=CacheStatusInput,
        output_model=CacheStatusOutput,
        annotations={"readOnlyHint": True},
    ),
    "list_file_types": ToolSpec(
        name="list_file_types",
        description=(
            "List available file type presets and their associated glob patterns."
        ),
        handler=handle_list_file_types,
        input_model=ListFileTypesInput,
        output_model=ListFileTypesOutput,
        annotations={"readOnlyHint": True},
    ),
    # ---------------------------------------------------------------------
    # Phase 54 Plan 03 — 4 mutating tools (TOOL-02 / TOOL-03 / TOOL-06 /
    # TOOL-08). ``add_documents`` and ``inject_documents`` are
    # job-spawning index operations (``openWorldHint: True``);
    # ``remove_folder`` and ``clear_cache`` are destructive
    # (``destructiveHint: True``) and Pydantic-gated via
    # ``confirm: Literal[True]``. Phase 54 CONTEXT decisions B + D + G.
    # ---------------------------------------------------------------------
    "add_documents": ToolSpec(
        name="add_documents",
        description=(
            "Index a list of document paths into the existing corpus. Returns "
            "a job_id the caller can poll with wait_for_job or get_job. "
            "Server-side path containment is enforced by the "
            "AGENT_BRAIN_ALLOW_EXTERNAL_PATHS setting (see issue #180 — there "
            "is no client-side allow_external knob)."
        ),
        handler=handle_add_documents,
        input_model=AddDocumentsInput,
        output_model=AddDocumentsOutput,
        annotations={"openWorldHint": True, "destructiveHint": False},
    ),
    "inject_documents": ToolSpec(
        name="inject_documents",
        description=(
            "Index a folder with content injection (custom enrichment script "
            "and/or folder-level metadata JSON). Returns a job_id the caller "
            "can poll with wait_for_job or get_job. At least one of "
            "injector_script or folder_metadata_file is required. Injector "
            "scripts must be hash-allowlisted server-side (see issue #181). "
            "Unallowlisted scripts will fail with INVALID_PARAMS. Set "
            "dry_run=true to validate without enqueueing — returns "
            "job_id='dry_run' with a validation report in message."
        ),
        handler=handle_inject_documents,
        input_model=InjectDocumentsInput,
        output_model=InjectDocumentsOutput,
        annotations={"openWorldHint": True, "destructiveHint": False},
    ),
    "remove_folder": ToolSpec(
        name="remove_folder",
        description=(
            "Remove all indexed chunks for a folder. Requires confirm=true. "
            "Removing a folder while an indexing job is active for it will "
            "fail with a BackendConflict error (HTTP 409 surfaced as "
            "MCP code -32000) — cancel the job first."
        ),
        handler=handle_remove_folder,
        input_model=RemoveFolderInput,
        output_model=RemoveFolderOutput,
        annotations={"destructiveHint": True},
    ),
    "clear_cache": ToolSpec(
        name="clear_cache",
        description=(
            "Clear the embedding cache. Requires confirm=true. Cannot be undone."
        ),
        handler=handle_clear_cache,
        input_model=ClearCacheInput,
        output_model=ClearCacheOutput,
        annotations={"destructiveHint": True},
    ),
}

__all__ = ["TOOL_REGISTRY", "ToolSpec", "ToolHandler", "file_types"]
