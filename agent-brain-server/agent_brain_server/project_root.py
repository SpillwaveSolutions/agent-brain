"""Project root resolution for per-project Agent Brain instances."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def resolve_project_root(start_path: Path | None = None) -> Path:
    """Resolve the canonical project root directory.

    Resolution order:
    1. Git repository root (git rev-parse --show-toplevel)
    2. Walk up looking for .claude/ directory
    3. Walk up looking for pyproject.toml
    4. Fall back to cwd

    Always resolves symlinks for canonical paths.

    Args:
        start_path: Starting path for resolution. Defaults to cwd.

    Returns:
        Resolved project root path.
    """
    start = (start_path or Path.cwd()).resolve()

    # Try git root first
    git_root = _resolve_git_root(start)
    if git_root:
        return git_root

    # Walk up looking for markers
    marker_root = _walk_up_for_marker(start)
    if marker_root:
        return marker_root

    return start


def _resolve_git_root(start: Path) -> Path | None:
    """Resolve git repository root with timeout.

    Args:
        start: Directory to start searching from.

    Returns:
        Git root path or None if not in a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(start),
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _walk_up_for_marker(start: Path) -> Path | None:
    """Walk up directories looking for project markers.

    Looks for .claude/ directory or pyproject.toml file.

    Args:
        start: Directory to start walking from.

    Returns:
        Directory containing a marker, or None.
    """
    current = start
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        if (current / "pyproject.toml").is_file():
            return current
        current = current.parent
    return None
