"""Prompt registry — 6 v1 templates per plan §6.6.

Each prompt is a parameterized message sequence the MCP server returns
from ``prompts/get``; the client model then executes the implied tool
plan.

Argument validation: ``arguments`` declared as a Pydantic model so
missing required values get rejected with a clear message before the
handler runs.
"""

from .audit_indexed_folders import audit_indexed_folders
from .compare_search_modes import compare_search_modes
from .explain_architecture import explain_architecture
from .find_callers import find_callers
from .find_implementation import find_implementation
from .onboard_to_codebase import onboard_to_codebase
from .types import PromptArgumentSpec, PromptSpec

PROMPT_REGISTRY: dict[str, PromptSpec] = {
    "find-callers": find_callers,
    "find-implementation": find_implementation,
    "explain-architecture": explain_architecture,
    "compare-search-modes": compare_search_modes,
    "onboard-to-codebase": onboard_to_codebase,
    "audit-indexed-folders": audit_indexed_folders,
}

__all__ = [
    "PROMPT_REGISTRY",
    "PromptArgumentSpec",
    "PromptSpec",
]
