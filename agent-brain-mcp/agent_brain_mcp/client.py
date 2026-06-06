"""ApiClient — thin httpx wrapper used by MCP tool/resource handlers.

Wraps an already-constructed ``httpx.Client`` (HTTP or UDS) and exposes
one method per Agent Brain endpoint that v1 exercises. Each method
calls the underlying client, applies :func:`errors.raise_for_status`
on non-2xx, and returns parsed JSON.

Plan §4.2: this client does NOT depend on ``agent_brain_cli`` — keeps
the MCP process free of Click / Rich. ~80 LOC bound.
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import TYPE_CHECKING, Any

import httpx

from . import errors


class ApiClient:
    """Synchronous Agent Brain HTTP client over a provided httpx.Client.

    The transport (UDS or TCP) is selected by the caller via
    :func:`agent_brain_mcp.config.open_backend_client`.
    """

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", path, json=json)

    def _delete(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("DELETE", path, json=json)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, json=json, params=params)
        except httpx.TimeoutException as e:
            errors.raise_backend_timeout(e)
            raise  # unreachable; satisfies type checker
        except (httpx.ConnectError, httpx.NetworkError) as e:
            errors.raise_backend_unavailable(e)
            raise

        errors.raise_for_status(response)
        if not response.content:
            return {}
        result: Any = response.json()
        if isinstance(result, dict):
            return result
        return {"data": result}

    # --- Tool-backing methods ---

    def server_health(self) -> dict[str, Any]:
        return self._get("/health/")

    def server_status(self) -> dict[str, Any]:
        return self._get("/health/status")

    def server_config(self) -> dict[str, Any]:
        return self._get("/health/config")

    def server_providers(self) -> dict[str, Any]:
        return self._get("/health/providers")

    def query(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post("/query/", json=body)

    def query_count(self) -> dict[str, Any]:
        return self._get("/query/count")

    def index_folder(
        self,
        body: dict[str, Any],
        *,
        force: bool = False,
        allow_external: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if force:
            params["force"] = "true"
        if allow_external:
            params["allow_external"] = "true"
        return self._request("POST", "/index/", json=body, params=params or None)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._get(f"/index/jobs/{job_id}")

    def list_jobs(self, *, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        return self._get("/index/jobs/", params={"limit": limit, "offset": offset})

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._delete(f"/index/jobs/{job_id}")

    def list_folders(self) -> dict[str, Any]:
        return self._get("/index/folders/")

    def get_chunk(self, chunk_id: str) -> dict[str, Any]:
        """GET /query/chunk/{chunk_id} — chunk content + metadata, no embedding.

        Backs the MCP ``chunk://<chunk_id>`` URI scheme (URI-01, Phase 51).
        The server-side response shape is :class:`ChunkRecord` (Phase 50
        Plan 02). Error mapping is the existing pipeline: 404 →
        ``INVALID_PARAMS`` via :func:`errors.raise_for_status`.
        """
        return self._get(f"/query/chunk/{chunk_id}")

    def get_graph_entity(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        """GET /graph/entity/{entity_type}/{entity_id} — entity + 1-hop neighbors.

        Backs the MCP ``graph-entity://<type>/<id>`` URI scheme (URI-02,
        Phase 51). The server-side response shape is
        :class:`GraphEntityRecord` (Phase 50 Plan 03). Error mapping is
        the existing pipeline: 404 → ``INVALID_PARAMS``, 503 →
        ``SERVICE_INDEXING`` (covers both ``graphrag_disabled`` and the
        ``kuzu_unavailable`` #178 fallback).

        Entity ids may contain ``/`` characters (Phase 50 decision B —
        the server's route uses a path-style ``{entity_id}`` segment).
        Callers MUST not pre-encode the id; httpx URL-quotes it once
        which is what the FastAPI route expects.
        """
        return self._get(f"/graph/entity/{entity_type}/{entity_id}")

    # --- Phase 54: tool-backing methods for the remaining 9 tools ---

    def add_documents(
        self,
        body: dict[str, Any],
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """POST /index/add — add documents from another folder to the index.

        Backs the ``add_documents`` MCP tool (TOOL-02, Phase 54). The
        ``allow_external`` query parameter was removed by issue #180;
        containment is enforced exclusively by the server-side
        ``AGENT_BRAIN_ALLOW_EXTERNAL_PATHS`` setting.
        """
        params: dict[str, Any] = {}
        if force:
            params["force"] = "true"
        return self._request("POST", "/index/add", json=body, params=params or None)

    def inject_documents(
        self,
        body: dict[str, Any],
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        """POST /index/ — index a folder with injector_script/folder_metadata_file.

        Same endpoint as :meth:`index_folder`; the differentiator is
        that ``body`` MUST include at least one of ``injector_script``
        or ``folder_metadata_file`` (CONTEXT decision D — the MCP
        handler raises ``INVALID_PARAMS`` before this method is called
        if both are missing). Backs the ``inject_documents`` MCP tool
        (TOOL-03, Phase 54).

        Unallowlisted scripts (issue #181) surface as 403 → structured
        ``McpError(INVALID_PARAMS)`` via ``errors.raise_for_status``.
        """
        params: dict[str, Any] = {}
        if force:
            params["force"] = "true"
        return self._request("POST", "/index/", json=body, params=params or None)

    def cache_status(self) -> dict[str, Any]:
        """GET /index/cache/ — embedding cache hit/miss + disk statistics.

        Backs the ``cache_status`` MCP tool (TOOL-07, Phase 54). Returns
        503 → ``McpError`` via the standard pipeline when the cache
        service is not initialised.
        """
        return self._get("/index/cache/")

    def clear_cache(self) -> dict[str, Any]:
        """DELETE /index/cache/ — clear all cached embeddings.

        Backs the ``clear_cache`` MCP tool (TOOL-08, Phase 54). The MCP
        handler's ``confirm: Literal[True]`` guard ensures this method
        is only reachable after explicit destructive-op acknowledgement.
        Returns 503 → ``McpError`` when the cache service is not
        initialised.
        """
        return self._delete("/index/cache/")

    def delete_folder(self, body: dict[str, Any]) -> dict[str, Any]:
        """DELETE /index/folders/ — remove a folder from the index.

        ``FolderDeleteRequest`` is a request *body*, not a query/path
        param — see folders router source. Backs the ``remove_folder``
        MCP tool (TOOL-06, Phase 54). 409 (active job for this folder,
        FOLD-07) surfaces as ``McpError(INVALID_PARAMS)`` via the
        existing pipeline.
        """
        return self._delete("/index/folders/", json=body)


# =============================================================================
# v3 CLI-via-MCP backends (Phase 56 Plan 03 — skeletons; wired in Phase 57+)
# =============================================================================
#
# These two classes structurally satisfy the BackendClient Protocol declared
# at agent_brain_cli/client/protocol.py (Plan 56-02). They expose the same
# 12-public-method + ctx-mgr surface as agent_brain_cli.client.DocServeClient
# so a CLI command coded against DocServeClient can be transparently
# rerouted through an MCP transport in Phase 57.
#
# Method bodies (except __init__, __enter__, __exit__, close) raise
# NotImplementedError with the literal message "Wired in Phase 57+". The
# message is load-bearing — Phase 57's transport selector tests grep for it
# to confirm "I got the skeleton, not a stale stub left behind by a botched
# refactor." See ROADMAP Phase 56 success criteria #5.
#
# Both classes inherit MIN_BACKEND_VERSION = "10.2.0" verbatim from
# agent_brain_mcp.server. Bump to "10.3.0" at v3 release per design doc §3.4.
#
# IMPORTANT: this block deliberately does NOT re-import the deferred-
# annotations future. The module-header import already covers this file.
# Python forbids those imports anywhere except the file header —
# re-importing here (even with an alias) is a SyntaxError.
# =============================================================================

if TYPE_CHECKING:
    from agent_brain_cli.client.api_client import (
        FolderInfo,
        HealthStatus,
        IndexingStatus,
        IndexResponse,
        QueryResponse,
    )


_PHASE_57_NOT_WIRED = "Wired in Phase 57+"

# Verbatim NotImplementedError wording for `reset()` on both backends
# (Phase 57 CONTEXT.md §decisions — DO NOT paraphrase). Duplicated as a
# string literal in each backend's `reset()` body so a grep for the
# message returns exactly 2 hits.
_RESET_NOT_SUPPORTED = (
    "--transport mcp does not support reset; use --transport uds "
    "or http (no reset_index MCP tool in v2; v3 Phase 57+ open "
    "decision per design doc §4 risks)"
)


def _coerce_query_response(payload: dict[str, Any]) -> QueryResponse:
    """Translate a ``search_documents`` MCP tool payload into ``QueryResponse``.

    The MCP tool's structuredContent has the same shape as the
    ``agent-brain-server`` ``POST /query/`` response, so we delegate to
    ``api_client._parse_query_result`` for each result entry.

    Late-imports the agent_brain_cli dataclasses to avoid a module-load
    cycle with agent_brain_cli (the CLI's BackendClient Protocol uses
    forward string references to these dataclasses for the same
    reason).
    """
    # Late import — avoids a top-level dep on agent_brain_cli for
    # consumers of agent_brain_mcp.client that never touch the v3
    # backends (e.g. the v1 ApiClient code path).
    from agent_brain_cli.client import api_client as _api_client

    results = [_api_client._parse_query_result(r) for r in payload.get("results", [])]
    return _api_client.QueryResponse(
        results=results,
        query_time_ms=float(payload.get("query_time_ms", 0.0)),
        total_results=int(payload.get("total_results", len(results))),
    )


def _coerce_health_status(payload: dict[str, Any]) -> HealthStatus:
    """Translate a ``server_health`` MCP tool payload into ``HealthStatus``.

    Mirrors ``DocServeClient.health()``'s parse logic so both transports
    produce identical dataclass shapes. Late-imports the dataclass per
    the same module-load cycle rationale as ``_coerce_query_response``.
    """
    from agent_brain_cli.client import api_client as _api_client

    return _api_client.HealthStatus(
        status=payload.get("status", ""),
        message=payload.get("message"),
        version=payload.get("version", "unknown"),
        timestamp=payload.get("timestamp", ""),
    )


def _coerce_indexing_status(payload: dict[str, Any]) -> IndexingStatus:
    """Translate a ``corpus://status`` MCP resource body into ``IndexingStatus``.

    Mirrors ``DocServeClient.status()``'s parse logic.
    """
    from agent_brain_cli.client import api_client as _api_client

    return _api_client.IndexingStatus(
        total_documents=int(payload.get("total_documents", 0)),
        total_chunks=int(payload.get("total_chunks", 0)),
        indexing_in_progress=bool(payload.get("indexing_in_progress", False)),
        current_job_id=payload.get("current_job_id"),
        progress_percent=float(payload.get("progress_percent", 0.0)),
        last_indexed_at=payload.get("last_indexed_at"),
        indexed_folders=list(payload.get("indexed_folders", [])),
        file_watcher=payload.get("file_watcher"),
        embedding_cache=payload.get("embedding_cache"),
    )


def _coerce_folder_info_list(payload: dict[str, Any]) -> list[FolderInfo]:
    """Translate a ``corpus://folders`` MCP resource body into ``list[FolderInfo]``.

    Mirrors ``DocServeClient.list_folders()``'s parse logic.
    """
    from agent_brain_cli.client import api_client as _api_client

    return [
        _api_client.FolderInfo(
            folder_path=f["folder_path"],
            chunk_count=int(f.get("chunk_count", 0)),
            last_indexed=f.get("last_indexed", ""),
            watch_mode=f.get("watch_mode", "off"),
            watch_debounce_seconds=f.get("watch_debounce_seconds"),
        )
        for f in payload.get("folders", [])
    ]


def _coerce_index_response(payload: dict[str, Any]) -> IndexResponse:
    """Translate an ``index_folder`` / ``inject_documents`` MCP tool payload
    into ``IndexResponse``.

    Mirrors ``DocServeClient.index()``'s parse logic.
    """
    from agent_brain_cli.client import api_client as _api_client

    return _api_client.IndexResponse(
        job_id=payload.get("job_id", ""),
        status=payload.get("status", ""),
        message=payload.get("message"),
    )


def _unwrap_payload(result: Any) -> dict[str, Any]:
    """Extract a dict payload from an MCP tool result.

    Prefer ``structuredContent`` (the SDK's typed channel). Fall back to
    parsing ``content[0].text`` as JSON when ``structuredContent`` is
    None (the SDK behavior when the tool's output_schema is not
    declared).
    """
    if result.structuredContent is not None:
        payload = result.structuredContent
        assert isinstance(payload, dict)
        return payload
    import json as _json

    text = result.content[0].text
    parsed = _json.loads(text)
    assert isinstance(parsed, dict)
    return parsed


def _unwrap_resource_body(result: Any) -> dict[str, Any]:
    """Extract a dict payload from an MCP read_resource result.

    ``result.contents[0].text`` is a JSON string for the corpus:// and
    job:// schemes (Plan 51).
    """
    import json as _json

    text = result.contents[0].text
    parsed = _json.loads(text)
    assert isinstance(parsed, dict)
    return parsed


class McpStdioBackend:
    """CLI-side backend that talks to agent-brain-mcp over stdio.

    Skeleton implementation. Constructor records configuration; method
    bodies raise NotImplementedError until Phase 57 wires the MCP SDK
    subprocess + tool-call dispatch.

    Structurally satisfies the BackendClient Protocol at
    agent_brain_cli.client.protocol.BackendClient (Plan 56-02). Verified
    by tests/test_cli_backends_skeleton.py via isinstance() at runtime
    and by mypy strict structural conformance.

    Args:
        command: Path or shell command to launch agent-brain-mcp. Phase 57
            normalizes to a list[str] for subprocess.Popen; the skeleton
            stores it verbatim.
        cwd: Working directory for the subprocess. Default None means
            "let Phase 57 decide" — the design doc and Phase 60 (subprocess
            hygiene) pin this to an explicit value before any orphan
            test ships. None is permitted in v3 skeleton ONLY.
        env: Subprocess env dict. None means "inherit current env" in the
            skeleton; Phase 60 replaces with an allowlist.

    Phase 57+ will wire:
        - Async event loop management (sync facade with asyncio.run or
          persistent _loop per design doc §3.2).
        - MCP SDK ClientSession + stdio_client lifecycle.
        - Method ↔ MCP tool mapping per design doc §2.3 table.
    """

    def __init__(
        self,
        command: str | list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.env = env
        self._closed = False

    def __enter__(self) -> McpStdioBackend:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Tear down the MCP subprocess. Idempotent.

        Skeleton: marks the instance closed; Phase 57 implements SIGTERM
        ->SIGKILL escalation per design doc §4.5 (Phase 60 hygiene).
        """
        self._closed = True

    # --- Shared helpers (Pattern A — asyncio.run per call) ---

    def _stdio_params(self) -> Any:
        """Build StdioServerParameters from ``self.command`` / cwd / env.

        Shared by every async helper so the subprocess spec stays
        consistent across all 11 wired methods.
        """
        from mcp.client.stdio import StdioServerParameters

        if isinstance(self.command, str):
            command_str = self.command
            extra_args: list[str] = []
        else:
            command_str = self.command[0]
            extra_args = list(self.command[1:])
        return StdioServerParameters(
            command=command_str,
            args=[*extra_args, "--transport", "stdio"],
            cwd=self.cwd,
            env=self.env,
        )

    # --- BackendClient surface (12 methods) ---

    def health(self) -> HealthStatus:
        return asyncio.run(self._async_health())

    async def _async_health(self) -> HealthStatus:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("server_health", {})
        return _coerce_health_status(_unwrap_payload(result))

    def status(self) -> IndexingStatus:
        return asyncio.run(self._async_status())

    async def _async_status(self) -> IndexingStatus:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        from pydantic import AnyUrl

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.read_resource(AnyUrl("corpus://status"))
        return _coerce_indexing_status(_unwrap_resource_body(result))

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
    ) -> QueryResponse:
        return asyncio.run(
            self._async_query(
                query_text=query_text,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                mode=mode,
                alpha=alpha,
                source_types=source_types,
                languages=languages,
                file_paths=file_paths,
                explain=explain,
            )
        )

    async def _async_query(
        self,
        *,
        query_text: str,
        top_k: int,
        similarity_threshold: float,
        mode: str,
        alpha: float,
        source_types: list[str] | None,
        languages: list[str] | None,
        file_paths: list[str] | None,
        explain: bool,
    ) -> QueryResponse:
        """Async helper for :meth:`query` (Pattern A sync facade — Phase
        57 CONTEXT decision).

        Each call spawns a fresh ``agent-brain-mcp --transport stdio``
        subprocess via the MCP SDK's ``stdio_client``, opens a
        ``ClientSession``, calls the ``search_documents`` tool, then
        tears the subprocess down. Phase 60 owns the persistent-
        subprocess hygiene refinement; Phase 57 ships the simplest
        correct code path.
        """
        # Late import — keeps the MCP SDK dep contained to the wire
        # path; consumers of the McpStdioBackend constructor that
        # never call query() do not pay the import cost.
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        tool_args: dict[str, Any] = {
            "query": query_text,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "mode": mode,
            "alpha": alpha,
            "explain": explain,
        }
        if source_types is not None:
            tool_args["source_types"] = source_types
        if languages is not None:
            tool_args["languages"] = languages
        if file_paths is not None:
            tool_args["file_paths"] = file_paths

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("search_documents", tool_args)

        return _coerce_query_response(_unwrap_payload(result))

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
    ) -> IndexResponse:
        body: dict[str, Any] = {
            "folder_path": folder_path,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "recursive": recursive,
            "include_code": include_code,
            "code_chunk_strategy": code_chunk_strategy,
            "generate_summaries": generate_summaries,
            "force": force,
            "dry_run": dry_run,
        }
        if supported_languages is not None:
            body["supported_languages"] = supported_languages
        if include_patterns is not None:
            body["include_patterns"] = include_patterns
        if exclude_patterns is not None:
            body["exclude_patterns"] = exclude_patterns
        if include_types is not None:
            body["include_types"] = include_types
        if folder_metadata_file is not None:
            body["folder_metadata_file"] = folder_metadata_file
        if watch_mode is not None:
            body["watch_mode"] = watch_mode
        if watch_debounce_seconds is not None:
            body["watch_debounce_seconds"] = watch_debounce_seconds
        if injector_script is not None:
            body["injector_script"] = injector_script
            tool_name = "inject_documents"
        else:
            tool_name = "index_folder"
        return asyncio.run(self._async_index(tool_name=tool_name, body=body))

    async def _async_index(
        self, *, tool_name: str, body: dict[str, Any]
    ) -> IndexResponse:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, body)
        return _coerce_index_response(_unwrap_payload(result))

    def list_folders(self) -> list[FolderInfo]:
        return asyncio.run(self._async_list_folders())

    async def _async_list_folders(self) -> list[FolderInfo]:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        from pydantic import AnyUrl

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.read_resource(AnyUrl("corpus://folders"))
        return _coerce_folder_info_list(_unwrap_resource_body(result))

    def delete_folder(self, folder_path: str) -> dict[str, Any]:
        return asyncio.run(self._async_delete_folder(folder_path))

    async def _async_delete_folder(self, folder_path: str) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "remove_folder", {"folder_path": folder_path}
                )
        return _unwrap_payload(result)

    def reset(self) -> IndexResponse:
        # Design doc §4-risks: reset() has no MCP tool equivalent in v2.
        # Phase 57+ open decision per CONTEXT.md §decisions — explicit
        # NotImplementedError pointer rather than a silent fallback or a
        # not-yet-existing tool call.
        raise NotImplementedError(
            "--transport mcp does not support reset; use --transport uds "
            "or http (no reset_index MCP tool in v2; v3 Phase 57+ open "
            "decision per design doc §4 risks)"
        )

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        return asyncio.run(self._async_list_jobs(limit))

    async def _async_list_jobs(self, limit: int) -> list[dict[str, Any]]:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("list_jobs", {"limit": limit})
        payload = _unwrap_payload(result)
        jobs = payload.get("jobs", [])
        assert isinstance(jobs, list)
        return jobs

    def get_job(self, job_id: str) -> dict[str, Any]:
        return asyncio.run(self._async_get_job(job_id))

    async def _async_get_job(self, job_id: str) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client
        from pydantic import AnyUrl

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.read_resource(AnyUrl(f"job://{job_id}"))
        return _unwrap_resource_body(result)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return asyncio.run(self._async_cancel_job(job_id))

    async def _async_cancel_job(self, job_id: str) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("cancel_job", {"job_id": job_id})
        return _unwrap_payload(result)

    def cache_status(self) -> dict[str, Any]:
        return asyncio.run(self._async_cache_status())

    async def _async_cache_status(self) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("cache_status", {})
        return _unwrap_payload(result)

    def clear_cache(self) -> dict[str, Any]:
        return asyncio.run(self._async_clear_cache())

    async def _async_clear_cache(self) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        # confirm=True is REQUIRED by the clear_cache tool's
        # Pydantic schema (Phase 54 Plan 03 destructive-op guard).
        # CONTEXT.md Claude's-discretion note: pass-through for parity
        # with --transport uds; no CLI-side confirmation prompt.
        async with stdio_client(self._stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("clear_cache", {"confirm": True})
        return _unwrap_payload(result)


class McpHttpBackend:
    """CLI-side backend that talks to agent-brain-mcp over Streamable HTTP.

    Skeleton implementation. Constructor records configuration; method
    bodies raise NotImplementedError until Phase 57 wires the MCP SDK
    streamablehttp_client + tool-call dispatch.

    Structurally satisfies the BackendClient Protocol at
    agent_brain_cli.client.protocol.BackendClient (Plan 56-02).

    Args:
        url: Full HTTP URL of the MCP listener including the mount path,
            e.g. "http://127.0.0.1:9999/mcp" (the v2 default mount path
            is /mcp per agent_brain_mcp.http.MCP_MOUNT_PATH). Loopback
            only — design doc §1.3 explicitly defers public-bind auth to
            v10.4 (#188).
        timeout: Per-request timeout in seconds. Default 30.0 matches
            DocServeClient's default.

    Phase 57+ will wire:
        - mcp.client.streamable_http.streamablehttp_client async context
          manager + ClientSession lifecycle.
        - Async event loop facade per design doc §3.2.
        - Method ↔ MCP tool mapping per design doc §2.3 table.
    """

    def __init__(self, url: str, *, timeout: float = 30.0) -> None:
        self.url = url
        self.timeout = timeout
        self._closed = False

    def __enter__(self) -> McpHttpBackend:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._closed = True

    def health(self) -> HealthStatus:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

    def status(self) -> IndexingStatus:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

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
    ) -> QueryResponse:
        return asyncio.run(
            self._async_query(
                query_text=query_text,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                mode=mode,
                alpha=alpha,
                source_types=source_types,
                languages=languages,
                file_paths=file_paths,
                explain=explain,
            )
        )

    async def _async_query(
        self,
        *,
        query_text: str,
        top_k: int,
        similarity_threshold: float,
        mode: str,
        alpha: float,
        source_types: list[str] | None,
        languages: list[str] | None,
        file_paths: list[str] | None,
        explain: bool,
    ) -> QueryResponse:
        """Async helper for :meth:`query` (Pattern A sync facade — Phase
        57 CONTEXT decision).

        Each call opens a fresh ``streamablehttp_client`` against
        ``self.url``, opens a ``ClientSession``, calls the
        ``search_documents`` tool, then tears down. Phase 60 owns the
        persistent-connection hygiene refinement; Phase 57 ships the
        simplest correct code path. Mirrors :meth:`McpStdioBackend.
        _async_query` exactly except for the transport call.
        """
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        tool_args: dict[str, Any] = {
            "query": query_text,
            "top_k": top_k,
            "similarity_threshold": similarity_threshold,
            "mode": mode,
            "alpha": alpha,
            "explain": explain,
        }
        if source_types is not None:
            tool_args["source_types"] = source_types
        if languages is not None:
            tool_args["languages"] = languages
        if file_paths is not None:
            tool_args["file_paths"] = file_paths

        # The SDK's streamablehttp_client yields (read, write,
        # session_id_factory) in mcp 1.12.x; use *_ to absorb any
        # future trailing tuple elements per the Phase 53
        # test_transport_selection.py precedent (lines 67-71).
        async with streamablehttp_client(self.url) as (read, write, *_):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("search_documents", tool_args)

        if result.structuredContent is None:
            import json as _json

            payload = _json.loads(result.content[0].text)  # type: ignore[union-attr]
        else:
            payload = result.structuredContent

        return _coerce_query_response(payload)

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
    ) -> IndexResponse:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

    def list_folders(self) -> list[FolderInfo]:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

    def delete_folder(self, folder_path: str) -> dict[str, Any]:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

    def reset(self) -> IndexResponse:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

    def get_job(self, job_id: str) -> dict[str, Any]:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

    def cache_status(self) -> dict[str, Any]:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)

    def clear_cache(self) -> dict[str, Any]:
        raise NotImplementedError(_PHASE_57_NOT_WIRED)


__all__: list[str] = ["ApiClient", "McpStdioBackend", "McpHttpBackend"]
