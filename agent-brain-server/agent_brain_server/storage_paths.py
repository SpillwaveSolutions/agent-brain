"""State directory and storage path resolution."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_DIR_NAME = ".claude/agent-brain"

SUBDIRECTORIES = [
    "data",
    "data/chroma_db",
    "data/bm25_index",
    "data/llamaindex",
    "data/graph_index",
    "logs",
    "manifests",
]


def resolve_state_dir(project_root: Path) -> Path:
    """Resolve the state directory for a project.

    Returns <project_root>/.claude/agent-brain/

    Args:
        project_root: Resolved project root path.

    Returns:
        Path to the state directory.
    """
    state_dir = project_root.resolve() / STATE_DIR_NAME
    return state_dir


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
    }

    # Create directories
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    return paths


def resolve_shared_project_dir(project_id: str) -> Path:
    """Resolve per-project storage under shared daemon.

    Args:
        project_id: Unique project identifier.

    Returns:
        Path to shared project data directory.
    """
    shared_dir = Path.home() / ".agent-brain" / "projects" / project_id / "data"
    shared_dir.mkdir(parents=True, exist_ok=True)
    return shared_dir
