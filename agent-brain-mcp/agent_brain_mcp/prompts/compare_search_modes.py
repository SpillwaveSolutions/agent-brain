"""compare-search-modes — same query across BM25/hybrid/multi."""

from __future__ import annotations

from typing import Any

from .types import PromptArgumentSpec, PromptSpec


def _render(args: dict[str, Any]) -> list[dict[str, Any]]:
    query = args["query"]
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"Run the query `{query}` against Agent Brain in three "
                    "modes and present the results side-by-side so I can "
                    "see which mode fits this question:\n"
                    f"1. search_documents(query=`{query}`, mode=bm25)\n"
                    f"2. search_documents(query=`{query}`, mode=hybrid)\n"
                    f"3. search_documents(query=`{query}`, mode=multi)\n"
                    "For each mode, report top 5 results with score and "
                    "source path. Then briefly call out which mode "
                    "produced the most useful ranking for this query."
                ),
            },
        }
    ]


compare_search_modes = PromptSpec(
    name="compare-search-modes",
    description=(
        "Run the same query under BM25, hybrid, and multi modes; "
        "present results side-by-side."
    ),
    arguments=[
        PromptArgumentSpec(
            name="query",
            description="The query to run across all three modes.",
            required=True,
        ),
    ],
    render=_render,
)
