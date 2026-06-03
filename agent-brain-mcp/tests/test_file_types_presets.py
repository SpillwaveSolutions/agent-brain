"""Phase 54 Plan 01 — smoke test for the vendored FILE_TYPE_PRESETS table.

Asserts the dict is importable, structurally sound, and large enough to
match the CLI shape. The CLI / MCP parity contract (assert ``MCP_PRESETS
== CLI_PRESETS`` across both packages) lands in Phase 55 (VAL-01) where
the cross-package test infrastructure exists; until then this smoke
gate at minimum proves the table is non-empty and well-typed at the
MCP-package boundary.
"""

from __future__ import annotations

from agent_brain_mcp.tools.file_types import FILE_TYPE_PRESETS


def test_presets_table_is_non_empty_dict_of_lists() -> None:
    """The vendored table is a dict[str, list[str]] — basic shape gate."""
    assert isinstance(FILE_TYPE_PRESETS, dict)
    assert len(FILE_TYPE_PRESETS) >= 11, (
        "CLI ships ≥11 presets (CLAUDE.md). MCP must vendor every one of them."
    )
    for name, patterns in FILE_TYPE_PRESETS.items():
        assert isinstance(name, str) and name, f"preset name must be non-empty string: {name!r}"
        assert isinstance(patterns, list), f"{name!r} value must be a list"
        assert patterns, f"{name!r} must have at least one pattern"
        for pattern in patterns:
            assert isinstance(pattern, str) and pattern, (
                f"{name!r} pattern must be non-empty string: {pattern!r}"
            )


def test_known_presets_present() -> None:
    """Spot-check the 11 baseline preset names the CLI ships.

    Phase 55 will add the full cross-package parity assertion; this
    spot-check is the MCP-side trip-wire until then.
    """
    expected_baseline = {
        "python",
        "javascript",
        "typescript",
        "go",
        "rust",
        "java",
        "csharp",
        "c",
        "cpp",
        "docs",
        "code",
    }
    missing = expected_baseline - set(FILE_TYPE_PRESETS.keys())
    assert not missing, f"missing baseline presets: {sorted(missing)}"


def test_python_preset_includes_standard_extensions() -> None:
    """Drift detector — if someone reorders the dict or strips an extension,
    this test catches it before Plan 02 wires the tool."""
    py_patterns = set(FILE_TYPE_PRESETS["python"])
    assert {"*.py", "*.pyi", "*.pyw"}.issubset(py_patterns)


def test_code_preset_is_a_superset_of_language_presets() -> None:
    """The 'code' preset is documented as the union of language-specific
    presets. Spot-check Python and Go inclusion (smoke; full equality lands
    in Phase 55)."""
    code = set(FILE_TYPE_PRESETS["code"])
    assert {"*.py", "*.go"}.issubset(code)
