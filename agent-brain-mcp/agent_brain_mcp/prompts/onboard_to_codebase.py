"""onboard-to-codebase — produce a 'where to start' briefing."""

from __future__ import annotations

from typing import Any

from .types import PromptArgumentSpec, PromptSpec


def _render(args: dict[str, Any]) -> list[dict[str, Any]]:
    area = args.get("area")
    area_hint = f" focused on `{area}`" if area else ""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"Produce an onboarding briefing for this codebase"
                    f"{area_hint}. Plan:\n"
                    "1. Read corpus://config to learn what storage backend, "
                    "embedding model, and graph extractor are active.\n"
                    "2. Read corpus://status for index size and current "
                    "indexing state.\n"
                    "3. Read corpus://folders to see what is indexed.\n"
                    "4. Call search_documents (mode=multi) for the top "
                    "entrypoints and key abstractions"
                    + (f" in `{area}`" if area else "")
                    + ".\n"
                    "Briefing should cover: the directory layout, the "
                    "primary modules to read first, the build/test "
                    "commands, and any open questions a new contributor "
                    "would have."
                ),
            },
        }
    ]


onboard_to_codebase = PromptSpec(
    name="onboard-to-codebase",
    description=(
        "Build a 'where to start' briefing by reading config + folders "
        "resources and surfacing top entrypoints."
    ),
    arguments=[
        PromptArgumentSpec(
            name="area",
            description="Optional: scope onboarding to a folder or topic.",
            required=False,
        ),
    ],
    render=_render,
)
