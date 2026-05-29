"""The 5 ``corpus://`` resources per plan §6.5.

These are *read-on-demand* only — no subscriptions in v1.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..client import ApiClient

ResourceHandler = Callable[["ApiClient"], dict[str, Any]]


class ResourceSpec:
    __slots__ = ("uri", "name", "description", "handler", "mime_type")

    def __init__(
        self,
        *,
        uri: str,
        name: str,
        description: str,
        handler: ResourceHandler,
        mime_type: str = "application/json",
    ) -> None:
        self.uri = uri
        self.name = name
        self.description = description
        self.handler = handler
        self.mime_type = mime_type


def _read_config(client: ApiClient) -> dict[str, Any]:
    return client.server_config()


def _read_status(client: ApiClient) -> dict[str, Any]:
    return client.server_status()


def _read_health(client: ApiClient) -> dict[str, Any]:
    return client.server_health()


def _read_providers(client: ApiClient) -> dict[str, Any]:
    return client.server_providers()


def _read_folders(client: ApiClient) -> dict[str, Any]:
    data = client.list_folders()
    # The server returns either a list (older) or {"folders": [...]} (newer).
    if isinstance(data, dict) and "folders" in data:
        return data
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return {"folders": data["data"]}
    return {"folders": []}


RESOURCE_REGISTRY: dict[str, ResourceSpec] = {
    "corpus://config": ResourceSpec(
        uri="corpus://config",
        name="Agent Brain configuration",
        description=(
            "Active storage backend, enabled stores (vector/bm25/graph), "
            "embedding model, reranker config, file-watcher status."
        ),
        handler=_read_config,
    ),
    "corpus://status": ResourceSpec(
        uri="corpus://status",
        name="Agent Brain indexing status",
        description=(
            "Indexed document counts, in-progress jobs, queue depth, "
            "graph-index size, embedding + query cache hit rates."
        ),
        handler=_read_status,
    ),
    "corpus://health": ResourceSpec(
        uri="corpus://health",
        name="Agent Brain server health",
        description=(
            "Server status, message, version, mode (project/shared), "
            "instance_id, project_id."
        ),
        handler=_read_health,
    ),
    "corpus://providers": ResourceSpec(
        uri="corpus://providers",
        name="Agent Brain provider status",
        description=(
            "Active embedding/summarization/reranker provider per type, "
            "with healthy/degraded/unavailable state and validation errors."
        ),
        handler=_read_providers,
    ),
    "corpus://folders": ResourceSpec(
        uri="corpus://folders",
        name="Agent Brain indexed folders",
        description=(
            "Array of indexed folders with chunk_count, last_indexed, "
            "watch_mode, and watch_debounce_seconds."
        ),
        handler=_read_folders,
    ),
}
