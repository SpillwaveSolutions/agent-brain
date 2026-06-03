"""ApiClient — thin httpx wrapper used by MCP tool/resource handlers.

Wraps an already-constructed ``httpx.Client`` (HTTP or UDS) and exposes
one method per Agent Brain endpoint that v1 exercises. Each method
calls the underlying client, applies :func:`errors.raise_for_status`
on non-2xx, and returns parsed JSON.

Plan §4.2: this client does NOT depend on ``agent_brain_cli`` — keeps
the MCP process free of Click / Rich. ~80 LOC bound.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

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
