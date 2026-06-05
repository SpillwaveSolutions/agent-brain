"""Runtime state management for Agent Brain instances."""

import json
import logging
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RuntimeState(BaseModel):
    """Runtime state for an Agent Brain instance."""

    schema_version: str = "1.0"
    mode: str = "project"  # "project" or "shared"
    project_root: str = ""
    instance_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    base_url: str = ""
    bind_host: str = "127.0.0.1"
    port: int = 0
    pid: int = 0
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # Shared mode fields
    project_id: str | None = None
    active_projects: list[str] | None = None
    # UDS transport (plan §4.3 — present when --uds, None otherwise)
    socket_path: str | None = None
    # API key for X-API-Key auth (Issue #179). Optional — None means the
    # server is running without auth (only safe on loopback). CLI and MCP
    # clients read this field to authenticate their requests; the file is
    # chmod'd to 0o600 by write_runtime so the secret stays user-only.
    api_key: str | None = None


def write_runtime(state_dir: Path, state: RuntimeState) -> None:
    """Write runtime state to state directory.

    The file is chmod'd to 0o600 (owner read/write only) because it may
    contain an ``api_key`` secret. The chmod is best-effort — on
    filesystems that don't support POSIX mode bits (e.g., FAT) the write
    still succeeds but the mode flag has no effect.

    Args:
        state_dir: Path to the state directory.
        state: Runtime state to write.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    runtime_path = state_dir / "runtime.json"
    runtime_path.write_text(state.model_dump_json(indent=2))
    try:
        runtime_path.chmod(0o600)
    except OSError as exc:
        logger.warning("Failed to chmod runtime.json to 0o600: %s", exc)
    logger.info(f"Runtime state written to {runtime_path}")


def read_runtime(state_dir: Path) -> RuntimeState | None:
    """Read runtime state from state directory.

    Args:
        state_dir: Path to the state directory.

    Returns:
        RuntimeState if file exists and is valid, None otherwise.
    """
    runtime_path = state_dir / "runtime.json"
    if not runtime_path.exists():
        return None
    try:
        data = json.loads(runtime_path.read_text())
        return RuntimeState(**data)
    except Exception as e:
        logger.warning(f"Failed to read runtime state: {e}")
        return None


def delete_runtime(state_dir: Path) -> None:
    """Delete runtime state file.

    Args:
        state_dir: Path to the state directory.
    """
    runtime_path = state_dir / "runtime.json"
    if runtime_path.exists():
        runtime_path.unlink()
        logger.info(f"Runtime state deleted: {runtime_path}")


def validate_runtime(state: RuntimeState) -> bool:
    """Validate that the runtime state is still valid.

    Checks:
    1. PID is still alive
    2. Health endpoint responds

    Args:
        state: Runtime state to validate.

    Returns:
        True if the instance is still running, False otherwise.
    """
    # Check PID
    if state.pid:
        try:
            os.kill(state.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            pass  # Process exists but we can't signal it

    # Check health endpoint
    if state.base_url:
        try:
            req = urllib.request.Request(f"{state.base_url}/health/", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return bool(resp.status == 200)
        except Exception:
            return False

    return False
