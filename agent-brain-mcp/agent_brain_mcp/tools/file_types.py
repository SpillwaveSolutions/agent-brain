"""File type presets — vendored from agent-brain-cli for the list_file_types MCP tool.

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


__all__ = ["FILE_TYPE_PRESETS"]
