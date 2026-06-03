"""Runtime state management for Agent Brain instances."""

import json
import logging
import os
import secrets
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def generate_api_key() -> str:
    """Generate a fresh API key for bearer-token auth (Issue #179).

    Returns:
        A URL-safe 32-byte token (~43 chars). Shared between the server (which
        verifies it) and the CLI (which sends it as ``Authorization: Bearer``).
    """
    return secrets.token_urlsafe(32)


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
    # Bearer-token auth (Issue #179). Generated on `agent-brain init` or backfilled
    # on first authenticated server start; the file is written mode 600 because
    # this field is a secret. None only in --insecure mode.
    api_key: str | None = None
    # Shared mode fields
    project_id: str | None = None
    active_projects: list[str] | None = None
    # UDS transport (plan §4.3 — present when --uds, None otherwise)
    socket_path: str | None = None


def write_runtime(state_dir: Path, state: RuntimeState) -> None:
    """Write runtime state to state directory.

    Args:
        state_dir: Path to the state directory.
        state: Runtime state to write.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    runtime_path = state_dir / "runtime.json"
    runtime_path.write_text(state.model_dump_json(indent=2))
    # runtime.json holds the API key (Issue #179) — keep it owner-only.
    try:
        runtime_path.chmod(0o600)
    except OSError as e:  # e.g. exotic filesystems without POSIX perms
        logger.warning(f"Could not set mode 600 on {runtime_path}: {e}")
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
