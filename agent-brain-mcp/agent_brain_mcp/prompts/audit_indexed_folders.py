"""audit-indexed-folders — flag stale/unwatched folders."""

from __future__ import annotations

from typing import Any

from .types import PromptSpec


def _render(args: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    "Audit the indexed-folders state of Agent Brain. Plan:\n"
                    "1. Read corpus://folders.\n"
                    "2. Flag any folder where `last_indexed` is more than 7 "
                    "days old (stale).\n"
                    '3. Flag any folder where `watch_mode == "off"` '
                    "(not auto-reindexed on file changes).\n"
                    "4. For each flagged folder, suggest the appropriate "
                    "index_folder call (with force=true for stale, with "
                    "watch_mode=auto for unwatched). Report as a numbered "
                    "todo list."
                ),
            },
        }
    ]


audit_indexed_folders = PromptSpec(
    name="audit-indexed-folders",
    description=(
        "Read corpus://folders, surface stale (>7d) and unwatched folders, "
        "suggest index_folder calls."
    ),
    arguments=[],
    render=_render,
)
