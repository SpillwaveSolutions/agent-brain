"""``search_documents`` tool — POST /query/."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import SearchDocumentsInput, SearchDocumentsOutput, SearchResult

if TYPE_CHECKING:
    from ..client import ApiClient


def handle_search_documents(
    client: ApiClient, args: SearchDocumentsInput
) -> SearchDocumentsOutput:
    """Forward to the server's /query/ endpoint, parse the response."""
    body = args.model_dump(exclude_none=True)
    raw = client.query(body)
    results = [
        SearchResult(
            text=r.get("text", ""),
            source=r.get("source", ""),
            score=float(r.get("score", 0.0)),
            chunk_id=r.get("chunk_id", ""),
            metadata=r.get("metadata") or {},
        )
        for r in raw.get("results", [])
    ]
    return SearchDocumentsOutput(
        query=raw.get("query", args.query),
        mode=raw.get("mode", args.mode),
        total_results=int(raw.get("total_results", len(results))),
        query_time_ms=raw.get("query_time_ms"),
        results=results,
    )
