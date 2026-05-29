"""find-implementation — locate where a feature is implemented."""

from __future__ import annotations

from typing import Any

from .types import PromptArgumentSpec, PromptSpec


def _render(args: dict[str, Any]) -> list[dict[str, Any]]:
    feature = args["feature"]
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"Find where the feature `{feature}` is implemented. "
                    "Two-step plan:\n"
                    f"1. Call search_documents with mode=bm25 and "
                    f"query=`{feature}` to find exact symbol matches.\n"
                    "2. For the top match, call search_documents with "
                    "mode=graph to walk to related tests and helpers.\n"
                    "Report the primary implementation file, the test file, "
                    "and any direct dependencies."
                ),
            },
        }
    ]


find_implementation = PromptSpec(
    name="find-implementation",
    description=(
        "Two-step BM25 + graph walk to surface a feature's primary "
        "implementation site and its tests."
    ),
    arguments=[
        PromptArgumentSpec(
            name="feature",
            description="The feature, concept, or symbol to locate.",
            required=True,
        ),
    ],
    render=_render,
)
