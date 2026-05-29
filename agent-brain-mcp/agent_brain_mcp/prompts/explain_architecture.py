"""explain-architecture — summarize a folder's architecture."""

from __future__ import annotations

from typing import Any

from .types import PromptArgumentSpec, PromptSpec


def _render(args: dict[str, Any]) -> list[dict[str, Any]]:
    folder = args["folder"]
    depth = args.get("depth", 2)
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"Explain the architecture of `{folder}` at depth "
                    f"{depth}. Plan:\n"
                    "1. Call search_documents with mode=multi and "
                    f"file_paths=[`{folder}`/**] to pull READMEs, "
                    "entrypoints, and high-level docs.\n"
                    "2. Then call search_documents with mode=graph for the "
                    "top entrypoint symbols to surface the relationship "
                    f"graph (depth={depth}).\n"
                    "Summarize: what does this code do, what are the major "
                    "components, how do they interact?"
                ),
            },
        }
    ]


explain_architecture = PromptSpec(
    name="explain-architecture",
    description=(
        "Multi-stage retrieval restricted to a folder, then graph walk to "
        "produce an architectural summary."
    ),
    arguments=[
        PromptArgumentSpec(
            name="folder",
            description="Folder (relative to project root) to explain.",
            required=True,
        ),
        PromptArgumentSpec(
            name="depth",
            description="Graph walk depth (default: 2).",
            required=False,
        ),
    ],
    render=_render,
)
