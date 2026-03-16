"""State directory and storage path resolution."""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_DIR_NAME = ".agent-brain"
LEGACY_STATE_DIR_NAME = ".claude/agent-brain"

SUBDIRECTORIES = [
    "data",
    "data/chroma_db",
    "data/bm25_index",
    "data/llamaindex",
    "data/graph_index",
    "logs",
    "manifests",
    "embedding_cache",  # Phase 16: persistent embedding cache
]


def resolve_state_dir(project_root: Path) -> Path:
    """Resolve the state directory for a project.

    Checks for `.agent-brain/` first, then falls back to the legacy
    `.claude/agent-brain/` path for backward compatibility. If neither
    exists, returns the new `.agent-brain/` path.

    Args:
        project_root: Resolved project root path.

    Returns:
        Path to the state directory.
    """
    resolved = project_root.resolve()
    new_dir = resolved / STATE_DIR_NAME
    if new_dir.is_dir():
        return new_dir

    legacy_dir = resolved / LEGACY_STATE_DIR_NAME
    if legacy_dir.is_dir():
        return legacy_dir

    return new_dir


def resolve_storage_paths(state_dir: Path) -> dict[str, Path]:
    """Resolve all storage paths relative to state directory.

    Creates directories if they don't exist.

    Args:
        state_dir: Path to the state directory.

    Returns:
        Dictionary mapping storage names to paths.
    """
    paths: dict[str, Path] = {
        "state_dir": state_dir,
        "data": state_dir / "data",
        "chroma_db": state_dir / "data" / "chroma_db",
        "bm25_index": state_dir / "data" / "bm25_index",
        "llamaindex": state_dir / "data" / "llamaindex",
        "graph_index": state_dir / "data" / "graph_index",
        "logs": state_dir / "logs",
        "manifests": state_dir / "manifests",
        "embedding_cache": state_dir / "embedding_cache",  # Phase 16
    }

    # Create directories
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    return paths


def resolve_shared_project_dir(project_id: str) -> Path:
    """Resolve per-project storage under shared daemon.

    Checks AGENT_BRAIN_SHARED_DIR env var first, then XDG_DATA_HOME/agent-brain,
    falling back to ~/.local/share/agent-brain.

    Args:
        project_id: Unique project identifier.

    Returns:
        Path to shared project data directory.
    """
    base_env = os.environ.get("AGENT_BRAIN_SHARED_DIR")
    if base_env:
        shared_dir = Path(base_env) / "projects" / project_id / "data"
    else:
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            shared_dir = (
                Path(xdg_data_home) / "agent-brain" / "projects" / project_id / "data"
            )
        else:
            shared_dir = (
                Path.home()
                / ".local"
                / "share"
                / "agent-brain"
                / "projects"
                / project_id
                / "data"
            )
    shared_dir.mkdir(parents=True, exist_ok=True)
    return shared_dir
