"""XDG Base Directory path resolution and legacy migration helpers.

This module is the single source of truth for all XDG directory resolution
in the Agent Brain CLI. Every other module should import from here.

XDG Base Directory specification:
  Config: $XDG_CONFIG_HOME/agent-brain  (default: ~/.config/agent-brain)
  State:  $XDG_STATE_HOME/agent-brain   (default: ~/.local/state/agent-brain)
  Data:   $XDG_DATA_HOME/agent-brain    (default: ~/.local/share/agent-brain)

Legacy path: ~/.agent-brain (pre-XDG, deprecated)
"""

import logging
import os
import shutil
from pathlib import Path

import click

logger = logging.getLogger(__name__)

# Legacy directory — deprecated, replaced by XDG paths
LEGACY_DIR: Path = Path.home() / ".agent-brain"


def get_xdg_config_dir() -> Path:
    """Return XDG config directory for Agent Brain.

    Returns:
        $XDG_CONFIG_HOME/agent-brain if XDG_CONFIG_HOME is set,
        otherwise ~/.config/agent-brain.
    """
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / "agent-brain"
    return Path.home() / ".config" / "agent-brain"


def get_xdg_state_dir() -> Path:
    """Return XDG state directory for Agent Brain.

    Returns:
        $XDG_STATE_HOME/agent-brain if XDG_STATE_HOME is set,
        otherwise ~/.local/state/agent-brain.
    """
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return Path(xdg_state_home) / "agent-brain"
    return Path.home() / ".local" / "state" / "agent-brain"


def get_registry_path() -> Path:
    """Return path to the global registry.json file.

    Prefers XDG state dir over legacy path. Falls back to legacy if
    registry.json exists only there. Returns XDG path as default write
    target when neither exists.

    Returns:
        Path to registry.json (may not exist yet).
    """
    xdg_registry = get_xdg_state_dir() / "registry.json"
    if xdg_registry.exists():
        return xdg_registry

    # Legacy fallback — use Path.home() dynamically so tests can mock it
    legacy_registry = Path.home() / ".agent-brain" / "registry.json"
    if legacy_registry.exists():
        return legacy_registry

    # Default write target: XDG state dir
    return xdg_registry


def migrate_legacy_paths(*, silent: bool = False) -> bool:
    """Migrate ~/.agent-brain to XDG directories.

    Copies config.yaml to XDG config dir and registry.json to XDG state
    dir, then removes the legacy ~/.agent-brain directory.

    This migration is non-blocking — errors are caught and logged.
    Migration is skipped if either XDG directory already exists (idempotent).

    Args:
        silent: If True, suppress output to stderr.

    Returns:
        True if migration succeeded, False otherwise.
    """
    # Use Path.home() dynamically so tests can mock it
    legacy_dir = Path.home() / ".agent-brain"

    # Skip if legacy dir doesn't exist
    if not legacy_dir.exists():
        return False

    xdg_config = get_xdg_config_dir()
    xdg_state = get_xdg_state_dir()

    # Skip if either XDG dir already exists (already migrated)
    if xdg_config.exists() or xdg_state.exists():
        return False

    try:
        # Create XDG directories
        xdg_config.mkdir(parents=True, exist_ok=True)
        xdg_state.mkdir(parents=True, exist_ok=True)

        # Copy config files to XDG config dir
        for config_name in ("config.yaml", "agent-brain.yaml"):
            src = legacy_dir / config_name
            if src.exists():
                shutil.copy2(src, xdg_config / config_name)

        # Copy state files to XDG state dir
        for state_name in ("registry.json",):
            src = legacy_dir / state_name
            if src.exists():
                shutil.copy2(src, xdg_state / state_name)

        # Remove legacy directory
        shutil.rmtree(legacy_dir)

        if not silent:
            click.echo(
                f"Migrated Agent Brain config from {legacy_dir} to XDG directories:\n"
                f"  Config: {xdg_config}\n"
                f"  State:  {xdg_state}",
                err=True,
            )

        return True

    except (PermissionError, OSError) as e:
        logger.warning("Failed to migrate legacy Agent Brain config: %s", e)
        if not silent:
            click.echo(
                f"Warning: Could not migrate {legacy_dir} to XDG directories: {e}",
                err=True,
            )
        return False
