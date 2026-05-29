"""``query_count`` + ``server_health`` tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import (
    QueryCountInput,
    QueryCountOutput,
    ServerHealthInput,
    ServerHealthOutput,
)

if TYPE_CHECKING:
    from ..client import ApiClient


def handle_query_count(client: ApiClient, args: QueryCountInput) -> QueryCountOutput:
    raw = client.query_count()
    return QueryCountOutput(
        total_documents=int(raw.get("total_documents", 0)),
        total_chunks=int(raw.get("total_chunks", 0)),
    )


def handle_server_health(
    client: ApiClient, args: ServerHealthInput
) -> ServerHealthOutput:
    raw = client.server_health()
    return ServerHealthOutput(
        status=str(raw.get("status", "unknown")),
        version=str(raw.get("version", "unknown")),
        message=raw.get("message"),
        mode=raw.get("mode"),
        instance_id=raw.get("instance_id"),
    )
