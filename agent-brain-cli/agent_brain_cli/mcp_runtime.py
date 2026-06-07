"""MCP runtime + lock helpers for agent-brain mcp start/stop commands (Phase 58).

Schema reference: docs/plans/2026-06-05-mcp-v3-cli-via-mcp.md §2.4 (lines 176-188).
All five mcp.runtime.json fields (host, port, pid, started_at, transport) are
mandatory and load-bearing — adding/renaming requires a design-doc amendment.

This module is the FOUNDATION for Phase 58:

- Plan 58-02 (``agent-brain mcp start``) uses :func:`acquire_lock`,
  :func:`write_mcp_runtime`, and :func:`is_listening` to spawn the MCP
  subprocess + write the runtime file AFTER psutil verifies the kernel
  bound the requested loopback port.
- Plan 58-03 (``agent-brain mcp stop`` + ``McpHttpBackend.__init__``
  discovery) uses :func:`read_mcp_runtime`, :func:`delete_mcp_runtime`,
  and :func:`release_lock` to terminate the subprocess + clean up the
  runtime + lock files, AND reads the discovery file inside the HTTP
  backend constructor when ``--mcp-url`` is omitted.

File permissions (``0o600``) follow the issue #179 API-key-bearing-file
convention — the runtime file embeds the spawned-subprocess pid, and
the lock file embeds the parent-CLI pid; neither is sensitive on its
own, but matching the convention keeps file-permission audits one-line.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# --- Public constants (load-bearing across Phase 58 commands + Phase 58-03
# McpHttpBackend discovery integration). DO NOT rename. ----------------------
MCP_RUNTIME_FILE = "mcp.runtime.json"
MCP_LOCK_FILE = "agent-brain-mcp.lock"

# Default port + start-timeout exposed at module level so Plan 58-02's
# Click command (``agent-brain mcp start``) AND Plan 58-03's discovery
# integration can share a single source of truth. Phase 58 CONTEXT
# decision: ``8765`` (preferred default port) + ``10`` seconds (psutil
# bind-verification timeout; MCP doesn't load ML deps, so 10s is plenty
# faster than the server's 120s).
MCP_DEFAULT_PORT = 8765
MCP_DEFAULT_START_TIMEOUT = 10.0

# File permissions match the issue #179 API-key-bearing-file convention.
_RUNTIME_FILE_MODE = 0o600
_LOCK_FILE_MODE = 0o600


class LockAcquisitionError(RuntimeError):
    """Raised by :func:`acquire_lock` when an alive MCP instance already holds the lock.

    The verbatim wording ``"agent-brain mcp already running on port {port}
    (pid {pid}); run 'agent-brain mcp stop' first"`` is pinned by
    :mod:`tests/test_mcp_runtime.py` so Plan 58-02 can grep for it without
    knowing about this module.
    """


def read_mcp_runtime(state_dir: Path) -> dict[str, Any] | None:
    """Return parsed mcp.runtime.json or None if missing/malformed.

    Mirrors :func:`agent_brain_cli.commands.start.read_runtime` — never
    raises on a malformed/missing file (callers treat the absence as
    "MCP not running" rather than an error to surface).
    """
    runtime_path = state_dir / MCP_RUNTIME_FILE
    if not runtime_path.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(runtime_path.read_text())
        return data
    except (OSError, json.JSONDecodeError):
        return None


def write_mcp_runtime(state_dir: Path, data: dict[str, Any]) -> None:
    """Write mcp.runtime.json with 0o600 perms (issue #179 convention).

    Caller is responsible for the schema shape — this helper does NOT
    validate ``{host, port, pid, started_at, transport}`` presence (Plan
    58-02 owns that). It only writes bytes + chmods. Creates the parent
    state_dir if missing.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    runtime_path = state_dir / MCP_RUNTIME_FILE
    runtime_path.write_text(json.dumps(data, indent=2))
    os.chmod(runtime_path, _RUNTIME_FILE_MODE)


def delete_mcp_runtime(state_dir: Path) -> None:
    """Idempotent delete of mcp.runtime.json.

    Missing file → no-op. Permission errors are swallowed (mirrors
    :func:`agent_brain_cli.commands.start.cleanup_stale`).
    """
    runtime_path = state_dir / MCP_RUNTIME_FILE
    if runtime_path.exists():
        try:
            runtime_path.unlink()
        except OSError:
            pass


def _is_pid_alive(pid: int) -> bool:
    """psutil-backed liveness check (handles NoSuchProcess + AccessDenied)."""
    try:
        # ``psutil.pid_exists`` is typed as ``Any`` under
        # ``ignore_missing_imports = true``; cast to ``bool`` for mypy strict.
        return bool(psutil.pid_exists(pid))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def acquire_lock(state_dir: Path) -> Path:
    """Acquire the MCP lock file with stale-pid reclamation.

    Uses ``os.open(path, O_CREAT | O_EXCL | O_WRONLY, 0o600)`` for atomic
    creation. On collision with an alive holder, raises
    :class:`LockAcquisitionError` with the verbatim
    ``"agent-brain mcp already running on port {port} (pid {pid}); run
    'agent-brain mcp stop' first"`` wording. The port is read from
    ``mcp.runtime.json`` when present (best-effort diagnostic — defaults
    to ``"?"`` if the runtime file was already cleaned up but the lock
    file lingers).

    On collision with a DEAD holder (psutil reports pid gone), the lock
    file + any stale runtime file are reclaimed and acquisition is
    retried once. A second collision after reclamation raises
    :class:`LockAcquisitionError` with a generic "failed to reclaim"
    message — operators remove the lock file manually in that case.

    Returns the absolute :class:`Path` of the acquired lock file.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / MCP_LOCK_FILE

    for attempt in range(2):
        try:
            fd = os.open(
                str(lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                _LOCK_FILE_MODE,
            )
            try:
                os.write(fd, str(os.getpid()).encode())
            finally:
                os.close(fd)
            return lock_path
        except FileExistsError:
            # Inspect the holder. Prefer mcp.runtime.json's pid (the
            # spawned subprocess) over the lock file's pid (the parent
            # CLI process) — the subprocess is what stop() will signal.
            runtime = read_mcp_runtime(state_dir)
            holder_pid: int | None = None
            holder_port: int | str = "?"
            if runtime is not None:
                holder_pid = runtime.get("pid")
                holder_port = runtime.get("port", "?")
            if holder_pid is None:
                try:
                    holder_pid = int(lock_path.read_text().strip())
                except (OSError, ValueError):
                    holder_pid = None
            if holder_pid is not None and _is_pid_alive(holder_pid):
                raise LockAcquisitionError(
                    f"agent-brain mcp already running on port {holder_port} "
                    f"(pid {holder_pid}); run 'agent-brain mcp stop' first"
                ) from None
            # Stale — reclaim and retry once.
            if attempt == 0:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                delete_mcp_runtime(state_dir)
                continue
            # Defensive: should not reach here after a clean reclaim.
            raise LockAcquisitionError(
                "failed to reclaim stale agent-brain-mcp.lock; "
                "remove manually and retry"
            ) from None

    # Mypy: ensure return on all paths (the for-loop returns or raises).
    raise LockAcquisitionError("acquire_lock: unreachable")


def release_lock(state_dir: Path) -> None:
    """Idempotent delete of the MCP lock file.

    Missing file → no-op. Permission errors are swallowed (mirrors
    :func:`delete_mcp_runtime`).
    """
    lock_path = state_dir / MCP_LOCK_FILE
    if lock_path.exists():
        try:
            lock_path.unlink()
        except OSError:
            pass


def is_listening(
    pid: int,
    host: str,
    port: int,
    timeout: float = MCP_DEFAULT_START_TIMEOUT,
    poll_interval: float = 0.1,
) -> bool:
    """Poll psutil until ``pid`` owns a LISTEN socket on ``(host, port)``.

    Clones the canonical kernel-bind verification pattern from
    ``agent-brain-mcp/tests/test_http_loopback.py`` (lines 48-67) — proves
    the OS kernel agrees the port is bound to ``host`` by the right pid.
    Returns ``True`` on success, ``False`` if timeout expires without a
    match (or if the process disappears / access is denied / pid was
    never alive).

    All error modes return ``False`` rather than raising — callers
    (Plan 58-02's ``agent-brain mcp start``) treat a False return as
    "subprocess failed to come up; surface stderr log + exit non-zero".

    Args:
        pid: Process id of the spawned ``agent-brain-mcp`` subprocess.
        host: Expected loopback bind IP (Phase 58 always ``"127.0.0.1"``).
        port: Expected TCP port.
        timeout: Max wall-clock seconds to poll. ``0.0`` means a single
            check with no sleep.
        poll_interval: Sleep between polls. Default 100ms.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        try:
            # Chained form is grep-pinned by Plan 58-01 acceptance criteria
            # (the literal substring proves the kernel-bind verifier mirrors
            # agent-brain-mcp/tests/test_http_loopback.py lines 48-67).
            connections = psutil.Process(pid).net_connections(kind="inet")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            logger.debug("is_listening: psutil could not inspect pid=%d (%s)", pid, exc)
            return False
        for conn in connections:
            if conn.status != psutil.CONN_LISTEN:
                continue
            laddr = conn.laddr
            if (
                getattr(laddr, "ip", None) == host
                and getattr(laddr, "port", None) == port
            ):
                return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval)


__all__ = [
    "LockAcquisitionError",
    "MCP_DEFAULT_PORT",
    "MCP_DEFAULT_START_TIMEOUT",
    "MCP_LOCK_FILE",
    "MCP_RUNTIME_FILE",
    "acquire_lock",
    "delete_mcp_runtime",
    "is_listening",
    "read_mcp_runtime",
    "release_lock",
    "write_mcp_runtime",
]
