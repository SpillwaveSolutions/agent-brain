"""Config migration engine for Agent Brain YAML config files.

Provides versioned migration steps that upgrade deprecated config keys to the
current schema, and a diff utility to preview changes before applying them.
"""

from __future__ import annotations

import copy
import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

# ---------------------------------------------------------------------------
# MigrationResult dataclass
# ---------------------------------------------------------------------------


@dataclass
class MigrationResult:
    """Result of running migration steps against a config dict.

    Attributes:
        original: Deep copy of the original config dict before migration.
        migrated: Config dict after all migration steps have been applied.
        changes: Human-readable descriptions of each change applied.
        already_current: True when no migration steps produced any changes.
    """

    original: dict[str, Any]
    migrated: dict[str, Any]
    changes: list[str]
    already_current: bool


# ---------------------------------------------------------------------------
# Migration functions
# ---------------------------------------------------------------------------


def _migrate_use_llm_extraction(
    config: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Migrate graphrag.use_llm_extraction -> graphrag.doc_extractor.

    Phase 34 decision: `use_llm_extraction` (bool) was renamed to
    `doc_extractor` (str: "langextract" | "none").

    Args:
        config: Config dict (will NOT be mutated; a deep copy is made).

    Returns:
        Tuple of (updated config dict, list of change descriptions).
    """
    changes: list[str] = []
    config = copy.deepcopy(config)
    graphrag = config.get("graphrag", {})

    if "use_llm_extraction" in graphrag:
        old_val = graphrag.pop("use_llm_extraction")
        if old_val:
            graphrag["doc_extractor"] = "langextract"
            changes.append(
                "graphrag.use_llm_extraction=True -> graphrag.doc_extractor=langextract"
            )
        else:
            changes.append(
                "graphrag.use_llm_extraction=False -> removed"
                " (default: no doc extraction)"
            )
        config["graphrag"] = graphrag

    return config, changes


# ---------------------------------------------------------------------------
# MIGRATIONS list — applied in order by migrate_config
# ---------------------------------------------------------------------------

MigrationFn = Callable[[dict[str, Any]], tuple[dict[str, Any], list[str]]]

MIGRATIONS: list[MigrationFn] = [
    _migrate_use_llm_extraction,
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def migrate_config(config: dict[str, Any]) -> MigrationResult:
    """Apply all migration steps to a config dict.

    Does NOT read or write any files. Mutations are applied to a deep copy,
    so the original dict is never modified.

    Args:
        config: Parsed YAML config dictionary.

    Returns:
        :class:`MigrationResult` describing the changes (or lack thereof).
    """
    original = copy.deepcopy(config)
    current = copy.deepcopy(config)
    all_changes: list[str] = []

    for migration_fn in MIGRATIONS:
        current, changes = migration_fn(current)
        all_changes.extend(changes)

    return MigrationResult(
        original=original,
        migrated=current,
        changes=all_changes,
        already_current=len(all_changes) == 0,
    )


def migrate_config_file(path: Path) -> MigrationResult:
    """Apply all migrations to a YAML config file and write results to disk.

    Reads the YAML from *path*, calls :func:`migrate_config`, and if any
    changes were made, writes the migrated dict back to *path* using
    ``yaml.safe_dump`` with ``default_flow_style=False, sort_keys=False``.

    Args:
        path: Path to the YAML config file.

    Returns:
        :class:`MigrationResult` describing the changes (or lack thereof).

    Raises:
        OSError: If the file cannot be read or written.
        yaml.YAMLError: If the YAML cannot be parsed.
    """
    yaml_text = path.read_text(encoding="utf-8")
    config: dict[str, Any] = yaml.safe_load(yaml_text) or {}

    result = migrate_config(config)

    if not result.already_current:
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(
                result.migrated, fh, default_flow_style=False, sort_keys=False
            )

    return result


def diff_config(config: dict[str, Any]) -> str:
    """Return a unified diff of what :func:`migrate_config` would change.

    Args:
        config: Parsed YAML config dictionary.

    Returns:
        Unified diff string (empty if no changes needed).
    """
    result = migrate_config(config)
    if result.already_current:
        return ""

    original_yaml = yaml.safe_dump(result.original, default_flow_style=False)
    migrated_yaml = yaml.safe_dump(result.migrated, default_flow_style=False)

    diff_lines = list(
        difflib.unified_diff(
            original_yaml.splitlines(keepends=True),
            migrated_yaml.splitlines(keepends=True),
            fromfile="config.yaml (current)",
            tofile="config.yaml (migrated)",
        )
    )

    return "".join(diff_lines)


def diff_config_file(path: Path) -> str:
    """Return a unified diff of what migrating *path* would change.

    Args:
        path: Path to the YAML config file.

    Returns:
        Unified diff string (empty if no changes needed).

    Raises:
        OSError: If the file cannot be read.
        yaml.YAMLError: If the YAML cannot be parsed.
    """
    yaml_text = path.read_text(encoding="utf-8")
    config: dict[str, Any] = yaml.safe_load(yaml_text) or {}
    return diff_config(config)
