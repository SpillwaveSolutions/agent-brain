"""File type preset resolution for indexed folder filtering.

This module provides preset names mapped to glob patterns, allowing callers
to specify named groups of file types (e.g., "python", "docs") instead of
listing individual glob patterns.
"""

from __future__ import annotations

# Canonical preset definitions mapping preset names to glob patterns.
# Each entry maps a short name to the list of glob patterns it covers.
FILE_TYPE_PRESETS: dict[str, list[str]] = {
    "python": ["*.py", "*.pyi", "*.pyw"],
    "javascript": ["*.js", "*.jsx", "*.mjs", "*.cjs"],
    "typescript": ["*.ts", "*.tsx"],
    "go": ["*.go"],
    "rust": ["*.rs"],
    "java": ["*.java"],
    "csharp": ["*.cs"],
    "c": ["*.c", "*.h"],
    "cpp": ["*.cpp", "*.hpp", "*.cc", "*.hh"],
    "web": ["*.html", "*.css", "*.scss", "*.jsx", "*.tsx"],
    "docs": ["*.md", "*.txt", "*.rst", "*.pdf"],
    "text": ["*.md", "*.txt", "*.rst"],
    "pdf": ["*.pdf"],
    # "code" is the union of all programming language presets
    "code": [
        # python
        "*.py",
        "*.pyi",
        "*.pyw",
        # javascript
        "*.js",
        "*.jsx",
        "*.mjs",
        "*.cjs",
        # typescript
        "*.ts",
        "*.tsx",
        # go
        "*.go",
        # rust
        "*.rs",
        # java
        "*.java",
        # csharp
        "*.cs",
        # c
        "*.c",
        "*.h",
        # cpp
        "*.cpp",
        "*.hpp",
        "*.cc",
        "*.hh",
    ],
}


def resolve_file_types(preset_names: list[str]) -> list[str]:
    """Resolve preset names to a deduplicated list of glob patterns.

    Takes one or more preset names and returns the combined, deduplicated
    set of glob patterns they represent.

    Args:
        preset_names: List of preset names to resolve. Each name must
            exist in FILE_TYPE_PRESETS.

    Returns:
        Deduplicated list of glob patterns, preserving order of first
        occurrence across all resolved presets.

    Raises:
        ValueError: If any preset name is not found in FILE_TYPE_PRESETS.
            The error message lists all valid preset names.

    Examples:
        >>> resolve_file_types(["python"])
        ['*.py', '*.pyi', '*.pyw']
        >>> resolve_file_types(["python", "docs"])  # deduplicated
        ['*.py', '*.pyi', '*.pyw', '*.md', '*.txt', '*.rst', '*.pdf']
    """
    valid_presets = sorted(FILE_TYPE_PRESETS.keys())

    # Validate all preset names before resolving
    for name in preset_names:
        if name not in FILE_TYPE_PRESETS:
            raise ValueError(
                f"Unknown file type preset '{name}'. " f"Valid presets: {valid_presets}"
            )

    # Resolve all patterns, maintaining insertion order + deduplication
    seen: set[str] = set()
    patterns: list[str] = []

    for name in preset_names:
        for pattern in FILE_TYPE_PRESETS[name]:
            if pattern not in seen:
                seen.add(pattern)
                patterns.append(pattern)

    return patterns


def list_presets() -> dict[str, list[str]]:
    """Return a copy of all available file type presets.

    Returns:
        Dictionary mapping preset names to their glob pattern lists.
        This is a shallow copy — safe to inspect but do not mutate
        the inner lists.
    """
    return dict(FILE_TYPE_PRESETS)
