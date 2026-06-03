"""JSON-Schema generation for tool input/output models.

The MCP spec requires every tool to advertise an ``inputSchema``
(JSON Schema) and optionally an ``outputSchema``. We generate both
from Pydantic models via ``pydantic.TypeAdapter`` so the schemas stay
in lockstep with the typed payloads.

v1 input/output models are deliberately defined here (small, MCP-facing
shapes) rather than reused from ``agent_brain_server.models`` — the
server models include fields irrelevant to MCP callers (timestamps,
internal IDs) that would clutter the tool schemas.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


def json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a JSON Schema dict for a Pydantic model class."""
    adapter: TypeAdapter[BaseModel] = TypeAdapter(model)
    schema = adapter.json_schema()
    # MCP expects ``additionalProperties: false`` to be explicit on
    # tool input/output schemas so clients can validate before send.
    if isinstance(schema, dict) and schema.get("type") == "object":
        schema.setdefault("additionalProperties", False)
    return schema


# ----------------------------- Tool inputs -----------------------------


class SearchDocumentsInput(BaseModel):
    """Input schema for the ``search_documents`` tool."""

    query: str = Field(description="Natural language or keyword query")
    mode: Literal["semantic", "bm25", "hybrid", "graph", "multi"] = Field(
        default="hybrid", description="Retrieval mode"
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Max results")
    similarity_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Score floor"
    )
    alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Hybrid mix: 0=pure BM25, 1=pure semantic",
    )
    source_types: list[str] | None = Field(default=None)
    languages: list[str] | None = Field(default=None)
    file_paths: list[str] | None = Field(default=None)
    explain: bool = Field(
        default=False, description="Include per-result explanation block"
    )


class QueryCountInput(BaseModel):
    """No arguments."""

    model_config = {"extra": "forbid"}


class IndexFolderInput(BaseModel):
    folder_path: str = Field(description="Absolute or project-relative folder")
    force: bool = Field(default=False, description="Re-index even if unchanged")
    allow_external: bool = Field(
        default=False, description="Allow paths outside the project root"
    )
    include_code: bool = Field(default=True)
    chunk_size: int | None = Field(default=None, ge=1)
    chunk_overlap: int | None = Field(default=None, ge=0)


class GetJobInput(BaseModel):
    job_id: str = Field(description="Job identifier returned by index_folder")


class ListJobsInput(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(
        default=None,
        description="Opaque pagination cursor (base64-encoded offset)",
    )


class CancelJobInput(BaseModel):
    job_id: str = Field(description="Job identifier to cancel")
    confirm: Literal[True] = Field(
        description="Must be true — destructive operation guard (plan §6.2)"
    )


class ServerHealthInput(BaseModel):
    """No arguments."""

    model_config = {"extra": "forbid"}


# ----------------------------- Tool outputs ----------------------------


class JobSummary(BaseModel):
    job_id: str
    status: str
    progress_percent: float | None = None
    message: str | None = None


class SearchResult(BaseModel):
    text: str
    source: str
    score: float
    chunk_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchDocumentsOutput(BaseModel):
    query: str
    mode: str
    total_results: int
    query_time_ms: float | None = None
    results: list[SearchResult]


class QueryCountOutput(BaseModel):
    total_documents: int
    total_chunks: int


class IndexFolderOutput(JobSummary):
    folder_path: str


class GetJobOutput(JobSummary):
    started_at: str | None = None
    completed_at: str | None = None


class ListJobsOutput(BaseModel):
    jobs: list[JobSummary]
    next_cursor: str | None = None


class CancelJobOutput(BaseModel):
    job_id: str
    cancelled: bool
    message: str | None = None


class ServerHealthOutput(BaseModel):
    status: str
    version: str
    message: str | None = None
    mode: str | None = None
    instance_id: str | None = None


# ======================================================================
# Phase 54 — 9 remaining tools
# ----------------------------------------------------------------------
# Inputs and outputs for the nine MCP tools landing in Phase 54:
# ``explain_result``, ``add_documents``, ``inject_documents``,
# ``wait_for_job``, ``list_folders``, ``remove_folder``, ``cache_status``,
# ``clear_cache``, ``list_file_types``. Plans 02/03/04 of Phase 54 wire
# handlers against these contracts. Tool handlers and ``TOOL_REGISTRY``
# entries are NOT added in Plan 01 — only the building blocks.
#
# All field constraints (``ge=``, ``le=``, ``min_length=``,
# ``Literal[...]``) are copied verbatim from the corresponding server
# Pydantic models in ``agent_brain_server.models.{index,folders,job,query}``
# and the FastAPI route signatures in ``api/routers/{index,folders,
# cache,query}.py``. See ``.planning/phases/54-remaining-mcp-tools/
# plans/01-schemas-and-apiclient-SUMMARY.md`` for the side-by-side
# constraint comparison table that locked these values.
# ======================================================================


# ----------------------------- Phase 54 — Inputs -----------------------


class ExplainResultInput(BaseModel):
    """Input schema for ``explain_result`` (TOOL-01).

    The original query + chunk_id is re-executed with ``explain=True``;
    the handler post-filters results for the requested chunk. Constraints
    mirror the search defaults but ``top_k`` is bumped to 50 so the
    target chunk is more likely to appear in the explained pool (CONTEXT
    decision F).
    """

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        description="Original query string that produced the result to explain"
    )
    chunk_id: str = Field(description="chunk_id of the result to explain")
    mode: Literal["semantic", "bm25", "hybrid", "graph", "multi"] = Field(
        default="hybrid",
        description="Retrieval mode (must match the mode used by the original query)",
    )
    top_k: int = Field(
        default=50,
        ge=1,
        le=200,
        description=(
            "Max results to consider for the explanation (bumped from search "
            "default of 10 — needs to be large enough for the target chunk to "
            "appear in the candidate pool)"
        ),
    )
    alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Hybrid mix: 0=pure BM25, 1=pure semantic",
    )


class AddDocumentsInput(BaseModel):
    """Input schema for ``add_documents`` (TOOL-02).

    Wraps ``POST /index/add``. The ``allow_external`` query parameter
    was removed by issue #180; containment is enforced exclusively by
    the server-side ``AGENT_BRAIN_ALLOW_EXTERNAL_PATHS`` setting and is
    therefore NOT exposed here. ``paths`` is plural — the handler (Plan
    02) iterates and submits one ``POST /index/add`` per path.
    """

    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(
        min_length=1,
        description="One or more folder paths to add to the existing index",
    )
    force: bool = Field(
        default=False,
        description="Bypass deduplication and force a new job",
    )


class InjectDocumentsInput(BaseModel):
    """Input schema for ``inject_documents`` (TOOL-03).

    Wraps ``POST /index/`` with ``injector_script`` and/or
    ``folder_metadata_file`` populated. At least one of those two MUST
    be provided (mirrors CLI ``inject`` semantics — CONTEXT decision D).

    The ``allow_external`` query parameter was removed by issue #180 (it
    applied to both ``POST /index/`` and ``POST /index/add``) and is
    therefore NOT exposed here. Server-side containment is enforced by
    ``AGENT_BRAIN_ALLOW_EXTERNAL_PATHS``.

    Injector scripts must be allowlisted server-side (issue #181); a
    403 from the server surfaces as ``McpError(INVALID_PARAMS)`` via
    the existing ``errors.raise_for_status`` pipeline.

    The ``chunk_size`` / ``chunk_overlap`` constraints (``ge=128, le=2048``
    and ``ge=0, le=200``) mirror ``IndexRequest`` 1:1.
    """

    model_config = ConfigDict(extra="forbid")

    folder_path: str = Field(
        min_length=1,
        description="Path to folder containing documents to index with injection",
    )
    injector_script: str | None = Field(
        default=None,
        description=(
            "Path to Python script exporting process_chunk(chunk: dict) -> dict. "
            "Scripts must be allowlisted server-side (issue #181) or the request "
            "fails with INVALID_PARAMS."
        ),
    )
    folder_metadata_file: str | None = Field(
        default=None,
        description="Path to JSON file with static metadata to merge into all chunks",
    )
    dry_run: bool = Field(
        default=False,
        description=(
            "If true, validate injector against sample chunks without enqueueing. "
            "Returns job_id='dry_run' and status='completed' with a validation "
            "report in message."
        ),
    )
    force: bool = Field(
        default=False,
        description="Bypass deduplication and force a new job",
    )
    include_code: bool = Field(
        default=True,
        description="Whether to index source code files alongside documents",
    )
    chunk_size: int | None = Field(
        default=None,
        ge=128,
        le=2048,
        description="Target chunk size in tokens (None = server default of 512)",
    )
    chunk_overlap: int | None = Field(
        default=None,
        ge=0,
        le=200,
        description="Overlap between chunks in tokens (None = server default of 50)",
    )

    @model_validator(mode="after")
    def _require_injector_or_metadata(self) -> InjectDocumentsInput:
        """At least one of ``injector_script`` or ``folder_metadata_file`` MUST
        be provided. Matches CLI ``inject`` command semantics (CONTEXT D).
        """
        if self.injector_script is None and self.folder_metadata_file is None:
            raise ValueError(
                "At least one of injector_script or folder_metadata_file is required"
            )
        return self


class WaitForJobInput(BaseModel):
    """Input schema for ``wait_for_job`` (TOOL-04).

    The only Phase 54 tool that emits MCP ``notifications/progress``;
    handler is async and wired by Plan 04. ``poll_interval_seconds`` is
    upper-bounded at 2.0s so clients cannot accidentally violate the
    MCP spec ≤2s notification cadence (CONTEXT decision E).
    """

    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="Job identifier returned by index_folder/add")
    poll_interval_seconds: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description=(
            "Seconds between GET /index/jobs/{id} polls. Upper bound of 2.0s "
            "enforces MCP spec ≤2s notification cadence."
        ),
    )
    timeout_seconds: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Soft cap. If exceeded, return WaitForJobOutput(status='timeout') "
            "with the last-known job state — do NOT raise."
        ),
    )


class ListFoldersInput(BaseModel):
    """No arguments — wraps ``GET /index/folders/``."""

    model_config = ConfigDict(extra="forbid")


class RemoveFolderInput(BaseModel):
    """Input schema for ``remove_folder`` (TOOL-06).

    Destructive operation — requires ``confirm=True`` (Phase 54
    extension of v1's ``cancel_job`` safety pattern). Wraps
    ``DELETE /index/folders/`` (FolderDeleteRequest body, not query).
    """

    model_config = ConfigDict(extra="forbid")

    folder_path: str = Field(
        min_length=1,
        description="Path to the folder to remove from the index",
    )
    confirm: Literal[True] = Field(
        description=(
            "Must be true — destructive operation guard (Phase 54 extension of "
            "v1 cancel_job pattern)"
        ),
    )


class CacheStatusInput(BaseModel):
    """No arguments — wraps ``GET /index/cache/``."""

    model_config = ConfigDict(extra="forbid")


class ClearCacheInput(BaseModel):
    """Input schema for ``clear_cache`` (TOOL-08).

    Destructive operation — requires ``confirm=True`` (Phase 54
    extension of v1's ``cancel_job`` safety pattern). Wraps
    ``DELETE /index/cache/``.
    """

    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True] = Field(
        description=(
            "Must be true — destructive operation guard (Phase 54 extension of "
            "v1 cancel_job pattern)"
        ),
    )


class ListFileTypesInput(BaseModel):
    """No arguments — returns vendored ``FILE_TYPE_PRESETS`` table."""

    model_config = ConfigDict(extra="forbid")


# ----------------------------- Phase 54 — Outputs ----------------------


class ExplainResultOutput(BaseModel):
    """Output schema for ``explain_result``.

    Combines the matched chunk's identifying fields (text/source/score/
    chunk_id) with the 6-field ``ResultExplanation`` mirror from
    ``agent_brain_server.models.query``. Server-side field types are
    copied 1:1 — note ``fusion`` is ``dict[str, float] | None``,
    ``rerank_movement`` is ``int | None``, ``graph_fallback`` is
    ``bool | None``.
    """

    chunk_id: str
    text: str
    source: str
    score: float
    reason: str
    matched_terms: list[str] | None = None
    fusion: dict[str, float] | None = None
    graph_path: list[str] | None = None
    rerank_movement: int | None = None
    graph_fallback: bool | None = None


class AddDocumentsOutput(BaseModel):
    """Output schema for ``add_documents``.

    Mirrors ``IndexResponse`` from the server — ``add_documents`` is a
    multi-path operation but the MCP-facing tool returns one summary
    record per request (handler aggregates).
    """

    job_id: str
    status: str
    message: str | None = None


class InjectDocumentsOutput(BaseModel):
    """Output schema for ``inject_documents``.

    Mirrors ``IndexResponse``. Dry-run path returns ``job_id='dry_run'``
    and ``status='completed'`` with a validation report in ``message``
    (CONTEXT decision D).
    """

    job_id: str
    status: str
    message: str | None = None


class WaitForJobOutput(BaseModel):
    """Output schema for ``wait_for_job``.

    Extends the v1 ``GetJobOutput`` fields with ``final`` (always True
    when returned) and ``elapsed_seconds`` (wall-clock duration of the
    wait) per CONTEXT decision E.
    """

    job_id: str
    status: str
    progress_percent: float | None = None
    message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    final: bool = True
    elapsed_seconds: float


class FolderInfoMcp(BaseModel):
    """MCP-side mirror of ``agent_brain_server.models.folders.FolderInfo``.

    Field order, types, and defaults copied 1:1 from the server model.
    Kept as an MCP-side projection so the schemas stay independent of
    server model imports per CONTEXT decision A.
    """

    folder_path: str
    chunk_count: int = Field(ge=0)
    last_indexed: str
    watch_mode: str = "off"
    watch_debounce_seconds: int | None = None


class ListFoldersOutput(BaseModel):
    """Output schema for ``list_folders``.

    Mirrors ``FolderListResponse`` (folders list + total count).
    """

    folders: list[FolderInfoMcp] = Field(default_factory=list)
    total: int = Field(ge=0)


class RemoveFolderOutput(BaseModel):
    """Output schema for ``remove_folder``.

    Mirrors ``FolderDeleteResponse`` from the server: ``folder_path``,
    ``chunks_deleted`` (NOT ``chunks_removed`` — name matches server
    1:1), ``message``.
    """

    folder_path: str
    chunks_deleted: int = Field(ge=0)
    message: str


class CacheStatusOutput(BaseModel):
    """Output schema for ``cache_status``.

    Mirrors the ``_cache_status_impl`` return shape in
    ``agent_brain_server/api/routers/cache.py``: session counters
    (hits/misses/hit_rate/mem_entries) merged with disk stats
    (entry_count/size_bytes). Server returns these as a plain dict; we
    type the known keys but leave room for future additions via
    ``extra=allow``.
    """

    model_config = ConfigDict(extra="allow")

    hits: int = Field(ge=0)
    misses: int = Field(ge=0)
    hit_rate: float
    mem_entries: int = Field(ge=0)
    entry_count: int = Field(ge=0)
    size_bytes: int = Field(ge=0)


class ClearCacheOutput(BaseModel):
    """Output schema for ``clear_cache``.

    Mirrors the ``_clear_cache_impl`` return shape: ``count`` (entries
    cleared), ``size_bytes``, ``size_mb`` (size_bytes / 1 MB).
    """

    count: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    size_mb: float


class ListFileTypesOutput(BaseModel):
    """Output schema for ``list_file_types`` (TOOL-09).

    Mirrors ``agent-brain types list --json`` output shape (CONTEXT
    decision H). ``presets`` is the vendored ``FILE_TYPE_PRESETS`` dict;
    ``preset_count`` and ``extension_count`` are convenience fields
    computed from it.
    """

    presets: dict[str, list[str]]
    preset_count: int = Field(ge=0)
    extension_count: int = Field(ge=0)
