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

from pydantic import BaseModel, Field, TypeAdapter


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
