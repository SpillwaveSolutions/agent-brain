#!/usr/bin/env python3
"""Validate YAML frontmatter in Markdown files.

Scans .md files in given directories for YAML frontmatter blocks (between ---
delimiters) and reports any parse errors. Exits with code 1 if errors found.

Usage:
    python scripts/lint_yaml_frontmatter.py [dir ...]
    python scripts/lint_yaml_frontmatter.py agent-brain-plugin/
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def extract_frontmatter(text: str) -> str | None:
    """Return the YAML block between the first pair of --- delimiters, or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = next(
        (i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if end is None:
        return None
    return "\n".join(lines[1:end])


def lint_directory(base: Path) -> list[tuple[Path, str]]:
    """Return list of (file, error_message) for any files with invalid frontmatter."""
    errors: list[tuple[Path, str]] = []
    for md_file in sorted(base.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        frontmatter = extract_frontmatter(content)
        if frontmatter is None:
            continue
        try:
            yaml.safe_load(frontmatter)
        except yaml.YAMLError as exc:
            errors.append((md_file, str(exc)))
    return errors


def main() -> int:
    dirs = [Path(d) for d in sys.argv[1:]] if len(sys.argv) > 1 else [Path(".")]

    all_errors: list[tuple[Path, str]] = []
    for d in dirs:
        if not d.is_dir():
            print(f"WARNING: {d} is not a directory, skipping", file=sys.stderr)
            continue
        all_errors.extend(lint_directory(d))

    if all_errors:
        print(f"YAML frontmatter lint FAILED — {len(all_errors)} error(s):\n")
        for path, msg in all_errors:
            print(f"  {path}:\n    {msg}\n")
        return 1

    scanned = sum(
        sum(1 for _ in Path(d).rglob("*.md")) for d in dirs if Path(d).is_dir()
    )
    print(f"YAML frontmatter OK — {scanned} file(s) scanned, 0 errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
