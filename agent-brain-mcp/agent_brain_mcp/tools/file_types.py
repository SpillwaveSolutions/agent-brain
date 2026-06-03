"""File type presets — vendored from agent-brain-cli for the list_file_types MCP tool.

Phase 54 Plan 02 ADDS :func:`handle_list_file_types` — the tool handler
that wraps the vendored dict in :class:`ListFileTypesOutput`. NO HTTP
roundtrip (CONTEXT decision H — the dict is pure static data).

This dict MUST stay in sync with agent-brain-cli/agent_brain_cli/commands/types.py
FILE_TYPE_PRESETS. Phase 55 (VAL-01) contract test asserts equality across the two
copies. If a preset changes in one, change it in both, or convert to a server-side
GET /index/types endpoint (deferred per .planning/phases/54-remaining-mcp-tools/
54-CONTEXT.md).

Source of truth for now: agent-brain-cli/agent_brain_cli/commands/types.py lines
19-90 (FILE_TYPE_PRESETS). The CLI itself notes that file matches
agent_brain_server/services/file_type_presets.py — there is no single canonical
copy on the server side, only the resolver and the same dict embedded in the CLI.

Drift detection:
    - Phase 55 ships ``tests/test_file_type_presets_parity.py`` (parameterized
      across all keys + values) that imports both this module and the CLI module
      and asserts ``MCP_PRESETS == CLI_PRESETS``. CI fails if they diverge.
    - Until Phase 55 lands, the smoke test in this repo
      (``tests/test_file_types_presets.py``) at minimum guarantees this copy is
      importable and structurally non-empty.

Layering note: this module imports ONLY stdlib types (no ``agent_brain_cli``
import). The MCP -> CLI dependency direction is forbidden by the import-linter
contracts; a copy is the explicit price of decoupling. If the source ever
becomes config-driven, the right fix is a ``GET /index/types`` server endpoint
that both CLI and MCP read at runtime — that work is deferred per Phase 54
CONTEXT decision H.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..schemas import ListFileTypesInput, ListFileTypesOutput

if TYPE_CHECKING:
    from ..client import ApiClient

# Vendored verbatim from agent-brain-cli/agent_brain_cli/commands/types.py
# lines 19-61 as of commit 51dd48f (Phase 53 verification merge, 2026-06-03).
FILE_TYPE_PRESETS: dict[str, list[str]] = {
    "python": ["*.py", "*.pyi", "*.pyw"],
    "javascript": ["*.js", "*.jsx", "*.mjs", "*.cjs"],
    "typescript": ["*.ts", "*.tsx"],
    "go": ["*.go"],
    "rust": ["*.rs"],
    "java": ["*.java"],
    "csharp": ["*.cs"],
    "pascal": ["*.pas", "*.pp", "*.lpr", "*.dpr", "*.dpk"],
    "object-pascal": ["*.pas", "*.pp", "*.lpr", "*.dpr", "*.dpk"],
    "c": ["*.c", "*.h"],
    "cpp": ["*.cpp", "*.hpp", "*.cc", "*.hh"],
    "web": ["*.html", "*.css", "*.scss", "*.jsx", "*.tsx"],
    "docs": ["*.md", "*.txt", "*.rst", "*.pdf"],
    "text": ["*.md", "*.txt", "*.rst"],
    "pdf": ["*.pdf"],
    "code": [
        "*.py",
        "*.pyi",
        "*.pyw",
        "*.js",
        "*.jsx",
        "*.mjs",
        "*.cjs",
        "*.ts",
        "*.tsx",
        "*.go",
        "*.rs",
        "*.java",
        "*.cs",
        "*.pas",
        "*.pp",
        "*.lpr",
        "*.dpr",
        "*.dpk",
        "*.c",
        "*.h",
        "*.cpp",
        "*.hpp",
        "*.cc",
        "*.hh",
    ],
}


def handle_list_file_types(
    client: ApiClient,  # noqa: ARG001 — uniform ToolSpec handler signature
    args: ListFileTypesInput,  # noqa: ARG001 — empty input, kept for uniformity
) -> ListFileTypesOutput:
    """Return the vendored ``FILE_TYPE_PRESETS`` table (TOOL-09).

    No HTTP roundtrip — the presets dict is pure static data (CONTEXT
    decision H). The ``client`` parameter is unused but kept for
    ToolSpec signature uniformity (every handler is ``(client, args)``
    so the dispatch path in :mod:`server` can stay branch-free).

    Args:
        client: Authenticated ``ApiClient`` (unused).
        args: Empty input model (unused).

    Returns:
        :class:`ListFileTypesOutput` with a *defensive copy* of
        :data:`FILE_TYPE_PRESETS` plus ``preset_count`` and
        ``extension_count`` convenience fields. The defensive copy
        protects callers from mutating the module-level dict in place.
    """
    presets = {name: list(patterns) for name, patterns in FILE_TYPE_PRESETS.items()}
    return ListFileTypesOutput(
        presets=presets,
        preset_count=len(presets),
        extension_count=sum(len(v) for v in presets.values()),
    )


__all__ = ["FILE_TYPE_PRESETS", "handle_list_file_types"]
