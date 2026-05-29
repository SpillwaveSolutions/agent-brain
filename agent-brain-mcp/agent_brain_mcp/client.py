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
