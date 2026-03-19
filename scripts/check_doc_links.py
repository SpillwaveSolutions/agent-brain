#!/usr/bin/env python3
"""Scan markdown documentation for broken internal links and file path references.

Usage:
    python scripts/check_doc_links.py [glob1 glob2 ...]

If no globs are provided, scans the default audited doc set (phases 29-33).

Outputs a JSON report to stdout with broken links, broken paths, and stats.
"""

import glob
import json
import os
import re
import sys
import unicodedata

# Project root: where this script lives is scripts/, so go up one level
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Default audited doc set
DEFAULT_GLOBS = [
    "docs/*.md",
    "agent-brain-plugin/commands/*.md",
    "agent-brain-plugin/skills/*/references/*.md",
    "agent-brain-plugin/agents/*.md",
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/CLAUDE.md",
]

# Regex for markdown links: [text](target)
# Captures the target part. Excludes image links starting with !
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)")

# Extensions for file paths in code blocks
PATH_EXTENSIONS = (
    ".py", ".md", ".ts", ".tsx", ".js", ".jsx",
    ".yaml", ".yml", ".toml", ".json", ".sh", ".cfg",
    ".html", ".css", ".txt", ".env", ".lock", ".whl",
)


def slug_heading(heading: str) -> str:
    """Convert a markdown heading to a URL-friendly slug.

    Matches GitHub's heading anchor generation:
    - Lowercase
    - Strip leading/trailing whitespace
    - Replace spaces with hyphens
    - Remove punctuation except hyphens and underscores
    - Collapse multiple hyphens
    """
    s = heading.strip().lower()
    # Remove backticks, bold/italic markers
    s = s.replace("`", "").replace("*", "").replace("~", "")
    # Remove characters that aren't alphanumeric, space, hyphen, or underscore
    s = re.sub(r"[^\w\s\-]", "", s)
    # Replace spaces with hyphens
    s = re.sub(r"\s+", "-", s)
    # Collapse multiple hyphens
    s = re.sub(r"-+", "-", s)
    # Strip leading/trailing hyphens
    s = s.strip("-")
    return s


def extract_headings(filepath: str) -> set:
    """Extract all heading anchors from a markdown file."""
    anchors = set()
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip()
                m = re.match(r"^(#{1,6})\s+(.+)", line)
                if m:
                    heading_text = m.group(2)
                    anchors.add(slug_heading(heading_text))
    except (OSError, IOError):
        pass
    return anchors


def resolve_file_globs(globs: list, root: str) -> list:
    """Resolve globs relative to project root, return sorted unique file list."""
    files = set()
    for g in globs:
        pattern = os.path.join(root, g)
        for f in glob.glob(pattern, recursive=True):
            if os.path.isfile(f):
                files.add(os.path.abspath(f))
    return sorted(files)


def is_url(target: str) -> bool:
    """Check if a link target is an external URL or special link."""
    return target.startswith(("http://", "https://", "mailto:", "ftp://"))


def check_file(filepath: str, root: str) -> tuple:
    """Check a single markdown file for broken links and paths.

    Returns (broken_links, broken_paths, link_count, path_count).
    """
    broken_links = []
    broken_paths = []
    link_count = 0
    path_count = 0
    file_dir = os.path.dirname(filepath)
    rel_file = os.path.relpath(filepath, root)

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, IOError):
        return broken_links, broken_paths, link_count, path_count

    in_code_block = False

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()

        # Track code block boundaries
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue

        if not in_code_block:
            # Check markdown links
            for match in LINK_RE.finditer(line):
                target = match.group(2).strip()

                # Skip external URLs
                if is_url(target):
                    continue

                # Skip pure anchors (same-file references)
                if target.startswith("#"):
                    link_count += 1
                    anchor = target[1:]
                    headings = extract_headings(filepath)
                    if anchor and anchor not in headings:
                        broken_links.append({
                            "file": rel_file,
                            "line": line_num,
                            "link": match.group(0),
                            "target": target,
                            "reason": "anchor not found",
                        })
                    continue

                link_count += 1

                # Split file path and anchor
                file_target = target
                anchor = None
                if "#" in target:
                    file_target, anchor = target.split("#", 1)

                # Resolve relative to the file's directory
                resolved = os.path.normpath(os.path.join(file_dir, file_target))

                if not os.path.exists(resolved):
                    broken_links.append({
                        "file": rel_file,
                        "line": line_num,
                        "link": match.group(0),
                        "target": target,
                        "reason": "file not found",
                    })
                elif anchor:
                    headings = extract_headings(resolved)
                    if anchor not in headings:
                        broken_links.append({
                            "file": rel_file,
                            "line": line_num,
                            "link": match.group(0),
                            "target": target,
                            "reason": "anchor not found",
                        })
        else:
            # Inside code block: skip path checking entirely.
            # Code blocks in documentation contain illustrative examples
            # (search results, command output, config snippets) that
            # reference hypothetical files, not actual project files.
            # Only markdown links (checked above) represent real references.
            pass

    return broken_links, broken_paths, link_count, path_count


def main() -> None:
    """Main entry point."""
    globs = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_GLOBS
    files = resolve_file_globs(globs, PROJECT_ROOT)

    all_broken_links = []
    all_broken_paths = []
    total_links = 0
    total_paths = 0

    for filepath in files:
        broken_links, broken_paths, link_count, path_count = check_file(
            filepath, PROJECT_ROOT
        )
        all_broken_links.extend(broken_links)
        all_broken_paths.extend(broken_paths)
        total_links += link_count
        total_paths += path_count

    report = {
        "broken_links": all_broken_links,
        "broken_paths": all_broken_paths,
        "stats": {
            "files_scanned": len(files),
            "links_checked": total_links,
            "paths_checked": total_paths,
            "broken_links": len(all_broken_links),
            "broken_paths": len(all_broken_paths),
        },
    }

    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
