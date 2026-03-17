#!/usr/bin/env python3
"""Add last_validated frontmatter metadata to audited documentation files.

Usage:
    python scripts/add_audit_metadata.py [--date YYYY-MM-DD] [--dry-run]

Adds or updates `last_validated: YYYY-MM-DD` in YAML frontmatter for every
audited documentation file. Files without existing frontmatter get a new
frontmatter block prepended.
"""

import argparse
import glob
import os
import re
import sys
from datetime import date

# Project root: where this script lives is scripts/, so go up one level
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Same audited doc set as check_doc_links.py
DEFAULT_GLOBS = [
    "docs/*.md",
    "agent-brain-plugin/commands/*.md",
    "agent-brain-plugin/skills/*/references/*.md",
    "agent-brain-plugin/agents/*.md",
]

STANDALONE_FILES = [
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/CLAUDE.md",
]

# Frontmatter boundary pattern
FRONTMATTER_RE = re.compile(r"^---\s*\n", re.MULTILINE)


def resolve_files(root: str) -> list:
    """Resolve all audited doc files, excluding plans/ and design/."""
    files = set()
    for g in DEFAULT_GLOBS:
        pattern = os.path.join(root, g)
        for f in glob.glob(pattern, recursive=True):
            if os.path.isfile(f):
                files.add(os.path.abspath(f))
    for f in STANDALONE_FILES:
        full = os.path.join(root, f)
        if os.path.isfile(full):
            files.add(os.path.abspath(full))
    # Exclude out-of-scope directories
    files = {
        f
        for f in files
        if "/plans/" not in f and "/design/" not in f
    }
    return sorted(files)


def has_frontmatter(content: str) -> bool:
    """Check if content starts with YAML frontmatter (---\\n)."""
    return content.startswith("---\n") or content.startswith("---\r\n")


def update_frontmatter(content: str, audit_date: str) -> tuple:
    """Update or add last_validated in existing frontmatter.

    Returns (new_content, action) where action is 'updated', 'added', or 'current'.
    """
    if not has_frontmatter(content):
        # No frontmatter - prepend new block
        new_content = f"---\nlast_validated: {audit_date}\n---\n\n{content}"
        return new_content, "new_frontmatter"

    # Find the closing --- of frontmatter
    # First --- is at position 0, find the second one
    lines = content.split("\n")
    closing_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            closing_idx = i
            break

    if closing_idx is None:
        # Malformed frontmatter (no closing ---), treat as no frontmatter
        new_content = f"---\nlast_validated: {audit_date}\n---\n\n{content}"
        return new_content, "new_frontmatter"

    # Extract frontmatter lines (between opening and closing ---)
    fm_lines = lines[1:closing_idx]

    # Check if last_validated already exists
    found = False
    for j, line in enumerate(fm_lines):
        if line.startswith("last_validated:"):
            current_val = line.split(":", 1)[1].strip().strip('"').strip("'")
            if current_val == audit_date:
                return content, "current"
            fm_lines[j] = f"last_validated: {audit_date}"
            found = True
            break

    if not found:
        # Add as last field before closing ---
        fm_lines.append(f"last_validated: {audit_date}")

    # Reconstruct content
    new_lines = ["---"] + fm_lines + lines[closing_idx:]
    new_content = "\n".join(new_lines)
    return new_content, "updated" if found else "added"


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Add last_validated frontmatter to audited docs"
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Audit date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing files",
    )
    args = parser.parse_args()

    # Validate date format
    try:
        date.fromisoformat(args.date)
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
        sys.exit(1)

    audit_date = args.date
    files = resolve_files(PROJECT_ROOT)

    updated = 0
    added = 0
    new_fm = 0
    current = 0
    errors = 0

    for filepath in files:
        rel = os.path.relpath(filepath, PROJECT_ROOT)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, IOError) as e:
            print(f"  ERROR reading {rel}: {e}", file=sys.stderr)
            errors += 1
            continue

        new_content, action = update_frontmatter(content, audit_date)

        if action == "current":
            current += 1
            if args.dry_run:
                print(f"  SKIP (current): {rel}")
            continue

        if action == "updated":
            updated += 1
            label = "UPDATE"
        elif action == "added":
            added += 1
            label = "ADD FIELD"
        else:  # new_frontmatter
            new_fm += 1
            label = "NEW FRONTMATTER"

        if args.dry_run:
            print(f"  {label}: {rel}")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"  {label}: {rel}")

    # Summary
    total = updated + added + new_fm
    mode = " (dry-run)" if args.dry_run else ""
    print(f"\nSummary{mode}:")
    print(f"  Files processed: {len(files)}")
    print(f"  Updated existing last_validated: {updated}")
    print(f"  Added last_validated to frontmatter: {added}")
    print(f"  Added new frontmatter block: {new_fm}")
    print(f"  Already current: {current}")
    print(f"  Total modified: {total}")
    if errors:
        print(f"  Errors: {errors}")


if __name__ == "__main__":
    main()
