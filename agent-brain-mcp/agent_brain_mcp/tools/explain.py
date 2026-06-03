"""``explain_result`` tool — provenance/scoring breakdown for a chunk (TOOL-01).

Phase 54 CONTEXT decision F: there is NO ``GET /query/explain`` server
endpoint. The handler re-issues the *original* query with
``explain=True`` and post-filters the returned results for the
requested ``chunk_id``. If the chunk isn't in the top-``top_k`` pool,
we raise :class:`McpError(INVALID_PARAMS)` with a message that nudges
the caller toward a higher ``top_k`` or a closer query.

The re-execution cost is real (an extra query roundtrip per call); the
tool description WARNS against high-frequency use and points callers
at ``search_documents(..., explain=true)`` for bulk explanation needs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mcp import McpError
from mcp.types import ErrorData

from ..errors import INVALID_PARAMS
from ..schemas import ExplainResultInput, ExplainResultOutput

if TYPE_CHECKING:
    from ..client import ApiClient


def handle_explain_result(
    client: ApiClient, args: ExplainResultInput
) -> ExplainResultOutput:
    """Re-execute the query with ``explain=True`` and filter for ``chunk_id``.

    Args:
        client: Authenticated ``ApiClient`` wired to ``agent-brain-serve``.
        args: Validated :class:`ExplainResultInput` — the original query
            text, mode, top_k, alpha, and the target ``chunk_id``.

    Returns:
        :class:`ExplainResultOutput` populated from the matching result's
        identifying fields (``chunk_id`` / ``text`` / ``source`` / ``score``)
        merged with its ``explanation`` sub-dict (``reason`` /
        ``matched_terms`` / ``fusion`` / ``graph_path`` / ``rerank_movement``
        / ``graph_fallback``).

    Raises:
        McpError: ``INVALID_PARAMS`` if the chunk is not present in the
            top-``top_k`` results for this query/mode. The error data
            carries ``chunk_id`` and ``top_k`` so MCP clients can surface
            a targeted hint to the user.
    """
    body: dict[str, Any] = {
        "query": args.query,
        "mode": args.mode,
        "top_k": args.top_k,
        "alpha": args.alpha,
        "explain": True,
    }
    response = client.query(body)
    for result in response.get("results", []):
        if result.get("chunk_id") == args.chunk_id:
            explanation = result.get("explanation") or {}
            return ExplainResultOutput(
                chunk_id=str(result.get("chunk_id", args.chunk_id)),
                text=str(result.get("text", "")),
                source=str(result.get("source", "")),
                score=float(result.get("score", 0.0)),
                reason=str(explanation.get("reason", "")),
                matched_terms=explanation.get("matched_terms"),
                fusion=explanation.get("fusion"),
                graph_path=explanation.get("graph_path"),
                rerank_movement=explanation.get("rerank_movement"),
                graph_fallback=explanation.get("graph_fallback"),
            )
    raise McpError(
        ErrorData(
            code=INVALID_PARAMS,
            message=(
                f"Chunk {args.chunk_id} not present in top-{args.top_k} "
                "results for this query/mode. Re-issue with a higher top_k "
                "or a closer query."
            ),
            data={"chunk_id": args.chunk_id, "top_k": args.top_k},
        )
    )
