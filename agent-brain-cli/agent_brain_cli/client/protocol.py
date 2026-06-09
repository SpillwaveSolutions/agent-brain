"""BackendClient — the structural Protocol every CLI backend satisfies.

The shape lives in code so:

1. mypy strict verifies callers can swap DocServeClient (HTTP/UDS) for
   McpStdioBackend / McpHttpBackend (v3, Phase 56 Plan 03) without
   editing a single Click command in :mod:`agent_brain_cli.commands`.
2. Tests can assert ``isinstance(backend, BackendClient)`` at runtime
   via :pep:`544`'s ``@runtime_checkable`` decorator.

Surface mirrors :class:`agent_brain_cli.client.api_client.DocServeClient`
verbatim — 12 public methods + 3 context-manager methods. The decision
to keep the Protocol sync-only (no async variant) is committed in the
v3 design doc at ``docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md`` §3.2.
A future ``AsyncBackendClient`` is deferred to v10.4+ per the design
doc's §6.
"""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    # TYPE_CHECKING import avoids a runtime cycle once Phase 56 Plan 03
    # backends start importing the Protocol from this module.
    from .api_client import (
        FolderInfo,
        HealthStatus,
        IndexingStatus,
        IndexResponse,
        QueryResponse,
    )


@runtime_checkable
class BackendClient(Protocol):
    """Structural contract for CLI-side backends.

    DocServeClient satisfies this Protocol without inheritance.
    McpStdioBackend + McpHttpBackend (Plan 56-03) will declare it
    explicitly via ``class McpStdioBackend(BackendClient): ...`` so
    mypy emits a clean error if a method ever drifts.

    All methods are synchronous. The v3 backends wrap async MCP SDK
    calls via ``asyncio.run(...)`` or a persistent ``_loop`` attribute
    — see the design doc §3.2. From the caller's perspective the
    facade is identical to DocServeClient's.
    """

    # --- Context manager surface ---------------------------------------

    def __enter__(self) -> BackendClient: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    def close(self) -> None: ...

    # --- Health + status ----------------------------------------------

    def health(self) -> HealthStatus: ...

    def status(self) -> IndexingStatus: ...

    # --- Query (maps to MCP `search_documents` tool for v3 backends) ---

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: float = 0.7,
        mode: str = "hybrid",
        alpha: float = 0.5,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
        file_paths: list[str] | None = None,
        explain: bool = False,
    ) -> QueryResponse: ...

    # --- Indexing -----------------------------------------------------

    def index(
        self,
        folder_path: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        recursive: bool = True,
        include_code: bool = False,
        supported_languages: list[str] | None = None,
        code_chunk_strategy: str = "ast_aware",
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
        include_types: list[str] | None = None,
        generate_summaries: bool = False,
        force: bool = False,
        injector_script: str | None = None,
        folder_metadata_file: str | None = None,
        dry_run: bool = False,
        watch_mode: str | None = None,
        watch_debounce_seconds: int | None = None,
    ) -> IndexResponse: ...

    # --- Folder management --------------------------------------------

    def list_folders(self) -> list[FolderInfo]: ...

    def delete_folder(self, folder_path: str) -> dict[str, Any]: ...

    def reset(self) -> IndexResponse: ...

    # --- Job queue ----------------------------------------------------

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]: ...

    def get_job(self, job_id: str) -> dict[str, Any]: ...

    def cancel_job(self, job_id: str) -> dict[str, Any]: ...

    # --- Embedding cache ----------------------------------------------

    def cache_status(self) -> dict[str, Any]: ...

    def clear_cache(self) -> dict[str, Any]: ...


@runtime_checkable
class McpBackend(Protocol):
    """Structural contract for MCP-only CLI backends (Phase 59).

    Exposes the ``prompts/get`` + ``prompts/list`` +
    ``resources/list`` + ``resources/templates/list`` +
    ``resources/read`` MCP surface that the v3 ``agent-brain prompt``
    and ``agent-brain resources *`` commands speak. Intentionally
    SEPARATE from :class:`BackendClient` — DocServeClient (UDS/HTTP)
    does NOT satisfy this Protocol because those transports do not
    speak MCP prompts/resources. The negative-case pinning test in
    ``agent-brain-mcp/tests/test_mcp_backend_protocol_skeleton.py``
    (``test_doc_serve_client_does_not_satisfy_mcp_backend``) makes the
    architectural boundary explicit and lasting.

    All methods are synchronous (sync-facade Pattern A confirmed by
    Plan 57-02; see design doc §3.2). The v3 MCP backends wrap async
    MCP SDK calls via ``asyncio.run(...)`` per call — from the
    caller's perspective the facade is identical to
    :class:`BackendClient`'s.

    Return shapes are deliberately ``dict[str, Any]`` /
    ``list[dict[str, Any]]`` (NOT typed dataclasses) — the MCP wire
    payloads for ``prompts/get`` and ``resources/read`` differ enough
    that the Phase 59 Plan 02 / Plan 03 command layer handles per-
    method coercion (mirrors the existing
    :func:`api_client._unwrap_payload` shape). Phase 60+ may revisit.
    """

    def get_prompt(
        self, name: str, arguments: dict[str, str] | None = None
    ) -> dict[str, Any]: ...

    def list_prompts(self) -> list[dict[str, Any]]: ...

    def list_resources(self) -> list[dict[str, Any]]: ...

    def list_resource_templates(self) -> list[dict[str, Any]]: ...

    def read_resource(self, uri: str) -> dict[str, Any]: ...


__all__: list[str] = ["BackendClient", "McpBackend"]
