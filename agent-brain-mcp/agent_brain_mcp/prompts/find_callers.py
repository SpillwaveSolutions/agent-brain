"""find-callers — graph-walk for who calls a symbol."""

from __future__ import annotations

from typing import Any

from .types import PromptArgumentSpec, PromptSpec


def _render(args: dict[str, Any]) -> list[dict[str, Any]]:
    symbol = args["symbol"]
    language = args.get("language")
    lang_hint = f" in {language}" if language else ""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": (
                    f"Use the search_documents tool with mode=graph and "
                    f'relationship_types=["calls"] to find all callers of '
                    f"the symbol `{symbol}`{lang_hint}. Report each caller "
                    "with its source path, line range, and the surrounding "
                    "context. Group results by file."
                ),
            },
        }
    ]


find_callers = PromptSpec(
    name="find-callers",
    description="Find every function that calls a given symbol (graph-walk).",
    arguments=[
        PromptArgumentSpec(
            name="symbol",
            description="The function or method name to find callers of.",
            required=True,
        ),
        PromptArgumentSpec(
            name="language",
            description="Optional: restrict to a language (python, ts, etc).",
            required=False,
        ),
    ],
    render=_render,
)
