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
    WaitForJobInput,
    WaitForJobOutput,
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
from .wait import handle_wait_for_job

# ``ToolHandler`` is intentionally typed as ``Any`` because each concrete
# handler narrows the arg/return to its specific input/output models
# (Callable is contravariant in arg types — strict mypy rejects the
# narrower signatures otherwise). Runtime dispatch in server.py uses the
# input_model on the ToolSpec to validate arguments before invocation.
ToolHandler = Any


class ToolSpec:
    """A registered MCP tool.

    Phase 54 Plan 04: ``emits_progress`` was added to discriminate v1's
    sync handlers (default ``False`` — invoked via ``asyncio.to_thread``
    in :func:`server.call_tool`) from the new async progress-emitting
    handler signature ``async (client, args, *, notify) -> output``. Only
    ``wait_for_job`` currently sets ``emits_progress=True``; every other
    Phase 54 + v1 tool keeps the default and the legacy dispatch path.
    """

    __slots__ = (
        "name",
        "description",
        "handler",
        "input_model",
        "output_model",
        "annotations",
        "emits_progress",
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
        emits_progress: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        self.handler = handler
        self.input_model = input_model
        self.output_model = output_model
        self.annotations = annotations or {}
        self.emits_progress = emits_progress


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
    # ---------------------------------------------------------------------
    # Phase 54 Plan 04 — the progress-emitting tool (TOOL-04). The only
    # ``emits_progress=True`` entry in the registry; the only async
    # handler. ``server.call_tool`` branches on ``emits_progress`` and
    # invokes ``handle_wait_for_job(api, args, notify=notify)`` instead
    # of the legacy ``asyncio.to_thread`` path. Per CONTEXT decision E.
    # ---------------------------------------------------------------------
    "wait_for_job": ToolSpec(
        name="wait_for_job",
        description=(
            "Block until a job reaches a terminal status (succeeded, failed, "
            "cancelled, or dry_run). Emits notifications/progress at least "
            "every 2 seconds (1s default cadence) while the job runs. "
            "Cancelling this MCP request via notifications/cancelled will "
            "also cancel the underlying indexing job server-side."
        ),
        handler=handle_wait_for_job,
        input_model=WaitForJobInput,
        output_model=WaitForJobOutput,
        annotations={"readOnlyHint": True},
        emits_progress=True,
    ),
}

# ---------------------------------------------------------------------------
# Per-tool scope single source of truth (OAUTH-06 SC#4)
#
# Each TOOL_REGISTRY key maps to exactly ONE of the 4 locked OAuth scopes.
# This map + the import-time guard below close design Risk 4 ("a tool added
# without a scope silently gets admin access via the is-authenticated check"):
# the server refuses to start if any registry key lacks a scope entry.
#
# Scope assignment (design doc §"Scope-to-Tool Mapping", locked 2026-06-14):
#   agent-brain:read      — read-only queries and status tools
#   agent-brain:index     — indexing / mutation tools
#   agent-brain:admin     — destructive / admin tools
#   (agent-brain:subscribe is for subscription channels; not a call_tool scope)
#
# Notes on two tools absent from the design table:
#   server_health  → agent-brain:read  (matches get_corpus_status in the table;
#                    naming resolved: registry key wins over table label)
#   query_count    → agent-brain:read  (read-only document count)
# ---------------------------------------------------------------------------

TOOL_SCOPE_REQUIREMENTS: dict[str, str] = {
    # agent-brain:read — read-only tools
    "search_documents": "agent-brain:read",
    "explain_result": "agent-brain:read",
    "server_health": "agent-brain:read",  # design table calls this get_corpus_status
    "query_count": "agent-brain:read",  # not named in design table — read
    "cache_status": "agent-brain:read",
    "list_folders": "agent-brain:read",
    "list_file_types": "agent-brain:read",
    "list_jobs": "agent-brain:read",
    "get_job": "agent-brain:read",
    # agent-brain:index — index/mutation tools
    "index_folder": "agent-brain:index",
    "add_documents": "agent-brain:index",
    "inject_documents": "agent-brain:index",
    "wait_for_job": "agent-brain:index",
    # agent-brain:admin — destructive/admin tools
    "cancel_job": "agent-brain:admin",
    "remove_folder": "agent-brain:admin",
    "clear_cache": "agent-brain:admin",
}

# Import VALID_SCOPES for the drift guard.  Uses a local frozenset literal as
# the canonical set to avoid a circular-import if oauth.scopes ever imports
# from tools.  A test asserts that this literal matches VALID_SCOPES exactly.
_VALID_SCOPES_LOCAL: frozenset[str] = frozenset(
    {
        "agent-brain:read",
        "agent-brain:index",
        "agent-brain:admin",
        "agent-brain:subscribe",
    }
)


def _scope_drift(
    registry: set[str],
    scoped: set[str],
    scope_map: dict[str, str],
    valid_scopes: frozenset[str],
) -> tuple[set[str], set[str], dict[str, str]]:
    """Return the three diff sets used by the drift guard.

    Extracted as a pure helper so tests can call it without monkeypatching the
    module-level guard (which fires once at import time).

    Args:
        registry: The set of tool names in TOOL_REGISTRY.
        scoped: The set of keys in TOOL_SCOPE_REQUIREMENTS.
        scope_map: The full scope map (for bad-value checking).
        valid_scopes: The frozenset of accepted scope strings.

    Returns:
        A 3-tuple (unassigned, unknown, bad_values) where:
          - unassigned: registry tools that lack a scope entry.
          - unknown: scope entries with no matching registry tool.
          - bad_values: mapping of tool name → invalid scope string.
    """
    unassigned = registry - scoped
    unknown = scoped - registry
    bad_values: dict[str, str] = {
        name: scope for name, scope in scope_map.items() if scope not in valid_scopes
    }
    return unassigned, unknown, bad_values


def _assert_every_tool_has_scope() -> None:
    """Raise RuntimeError if TOOL_SCOPE_REQUIREMENTS is out of sync with TOOL_REGISTRY.

    Called once at module import time.  The server refuses to start (import
    fails) if any registered tool lacks a scope assignment, any scope entry has
    no matching tool, or any scope value is not in the 4-value locked set.

    This mirrors the ``_assert_matrix_covers_registry()`` guard in
    ``tests/contract/_tool_matrix.py`` — same fail-fast philosophy, but lives
    in production code so it fires on server startup, not just during test runs.

    Raises:
        RuntimeError: Naming the unassigned tool(s), orphan scope entries, or
            invalid scope values detected at import time.
    """
    unassigned, unknown, bad_values = _scope_drift(
        set(TOOL_REGISTRY.keys()),
        set(TOOL_SCOPE_REQUIREMENTS.keys()),
        TOOL_SCOPE_REQUIREMENTS,
        _VALID_SCOPES_LOCAL,
    )
    if unassigned or unknown or bad_values:
        raise RuntimeError(
            "TOOL_SCOPE_REQUIREMENTS is out of sync with TOOL_REGISTRY.\n"
            f"  tools missing a scope assignment: {sorted(unassigned)}\n"
            f"  scope entries with no matching tool: {sorted(unknown)}\n"
            f"  entries with an invalid scope value: {bad_values}"
        )


_assert_every_tool_has_scope()

__all__ = [
    "TOOL_REGISTRY",
    "TOOL_SCOPE_REQUIREMENTS",
    "ToolSpec",
    "ToolHandler",
    "file_types",
]
