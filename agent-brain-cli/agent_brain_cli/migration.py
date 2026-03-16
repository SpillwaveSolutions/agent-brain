"""Migration utilities for Agent Brain state directory.

Handles auto-migration from the legacy `.claude/agent-brain` state directory
to the new runtime-neutral `.agent-brain` directory.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

LEGACY_STATE_DIR_NAME = ".claude/agent-brain"
NEW_STATE_DIR_NAME = ".agent-brain"


def detect_legacy_state_dir(project_root: Path) -> Path | None:
    """Check if a legacy `.claude/agent-brain` state directory exists.

    Args:
        project_root: The resolved project root path.

    Returns:
        Path to the legacy state dir if it exists, None otherwise.
    """
    legacy = project_root / LEGACY_STATE_DIR_NAME
    if legacy.is_dir():
        return legacy
    return None


def detect_new_state_dir(project_root: Path) -> Path | None:
    """Check if the new `.agent-brain` state directory exists.

    Args:
        project_root: The resolved project root path.

    Returns:
        Path to the new state dir if it exists, None otherwise.
    """
    new = project_root / NEW_STATE_DIR_NAME
    if new.is_dir():
        return new
    return None


def migrate_state_dir(project_root: Path) -> Path:
    """Auto-migrate from legacy to new state directory if needed.

    Migration rules:
    - If `.agent-brain/` exists: use it (already migrated)
    - If only `.claude/agent-brain/` exists: move it to `.agent-brain/`
    - If neither exists: return the new path (caller will create it)

    Args:
        project_root: The resolved project root path.

    Returns:
        Path to the state directory to use.
    """
    new_dir = project_root / NEW_STATE_DIR_NAME
    legacy_dir = project_root / LEGACY_STATE_DIR_NAME

    # Already using new layout
    if new_dir.is_dir():
        return new_dir

    # Legacy exists, migrate
    if legacy_dir.is_dir():
        logger.info(
            "Migrating state directory from %s to %s",
            legacy_dir,
            new_dir,
        )
        try:
            shutil.move(str(legacy_dir), str(new_dir))
            logger.info("Migration complete: %s -> %s", legacy_dir, new_dir)

            # Clean up empty .claude/ parent if it's now empty
            claude_dir = project_root / ".claude"
            if claude_dir.is_dir() and not any(claude_dir.iterdir()):
                # Don't remove .claude/ — it may be used by Claude Code itself
                pass

        except OSError as exc:
            logger.warning(
                "Failed to migrate state directory: %s. "
                "Falling back to legacy path.",
                exc,
            )
            return legacy_dir

    return new_dir


def resolve_state_dir_with_fallback(project_root: Path) -> Path:
    """Resolve state directory, checking new path first, legacy second.

    Unlike `migrate_state_dir`, this does NOT move files. It just finds
    whichever state directory currently exists.

    Args:
        project_root: The resolved project root path.

    Returns:
        Path to the existing state directory, or the new path if neither exists.
    """
    new_dir = project_root / NEW_STATE_DIR_NAME
    if new_dir.is_dir():
        return new_dir

    legacy_dir = project_root / LEGACY_STATE_DIR_NAME
    if legacy_dir.is_dir():
        return legacy_dir

    # Neither exists — default to new
    return new_dir
