"""Common types for prompt definitions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class PromptArgumentSpec:
    __slots__ = ("name", "description", "required")

    def __init__(
        self,
        *,
        name: str,
        description: str,
        required: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        self.required = required


PromptRenderer = Callable[[dict[str, Any]], list[dict[str, Any]]]


class PromptSpec:
    """A registered MCP prompt template."""

    __slots__ = ("name", "description", "arguments", "render")

    def __init__(
        self,
        *,
        name: str,
        description: str,
        arguments: list[PromptArgumentSpec],
        render: PromptRenderer,
    ) -> None:
        self.name = name
        self.description = description
        self.arguments = arguments
        self.render = render

    def required_arg_names(self) -> set[str]:
        return {a.name for a in self.arguments if a.required}

    def validate(self, args: dict[str, Any]) -> None:
        missing = self.required_arg_names() - set(args.keys())
        if missing:
            raise ValueError(
                f"Prompt {self.name!r} missing required arguments: "
                f"{sorted(missing)}"
            )
