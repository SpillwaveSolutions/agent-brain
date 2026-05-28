"""Socket path resolution for agent-brain-uds.

Mirrors the state-directory lookup in ``agent_brain_server.runtime`` /
``agent_brain_server.storage_paths`` so client and server agree on where
the socket lives. Handles the platform sockaddr_un length limit by
falling back to a short ``/tmp`` path and writing a pointer file inside
the state directory.

See docs/plans/2026-05-28-mcp-uds-transport-design.md §6.1.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .errors import SocketPathTooLongError

#: Default state-directory name. Mirrors ``STATE_DIR_NAME`` in the server.
STATE_DIR_NAME = ".agent-brain"

#: Default socket file name inside the state directory.
SOCKET_FILE_NAME = "agent-brain.sock"

#: Pointer-file name written alongside the canonical socket location when
#: the canonical path exceeds the platform limit. Contains the real
#: (short) socket path, one line, UTF-8.
POINTER_FILE_NAME = "agent-brain.sock.path"

#: Conservative sockaddr_un limit. macOS/BSD cap is 104 bytes; Linux is 108.
#: We use the smaller value so paths work on every supported platform.
MAX_SOCKET_PATH_BYTES = 104


def _short_fallback_path(state_dir: Path) -> Path:
    """Return a short ``/tmp`` socket path derived from the state-dir hash.

    The hash makes the fallback deterministic per project, so concurrent
    instances in different projects do not collide.
    """
    digest = hashlib.sha256(str(state_dir.resolve()).encode("utf-8")).hexdigest()[:8]
    return Path("/tmp") / f"agent-brain-{digest}.sock"


def resolve_state_dir(state_dir: Path | None = None) -> Path:
    """Resolve the state directory using the same precedence as the server.

    Order:

    1. Explicit ``state_dir`` argument.
    2. ``AGENT_BRAIN_STATE_DIR`` environment variable.
    3. ``<cwd>/.agent-brain/`` if it exists.
    4. Walk up from ``cwd`` looking for ``.agent-brain/``.
    5. Fall back to ``<cwd>/.agent-brain/`` (does not need to exist —
       the server creates it).

    Returns:
        The resolved state-directory path (not guaranteed to exist).
    """
    if state_dir is not None:
        return state_dir.resolve()

    env_dir = os.environ.get("AGENT_BRAIN_STATE_DIR")
    if env_dir:
        return Path(env_dir).resolve()

    cwd = Path.cwd().resolve()
    candidate = cwd / STATE_DIR_NAME
    if candidate.is_dir():
        return candidate

    # Walk upward looking for an existing .agent-brain/ directory.
    for parent in cwd.parents:
        candidate = parent / STATE_DIR_NAME
        if candidate.is_dir():
            return candidate

    # Default: a (possibly non-existent) .agent-brain/ in the current dir.
    return cwd / STATE_DIR_NAME


def resolve_socket_path(state_dir: Path | None = None) -> Path:
    """Resolve the UDS socket path for the given state directory.

    Reads a pointer file first if present (long-path fallback), then
    falls back to ``<state_dir>/agent-brain.sock``. If even the canonical
    path is too long for the platform, returns the short ``/tmp`` fallback
    (the server is responsible for writing the pointer file when it binds).

    Raises:
        SocketPathTooLongError: when even the ``/tmp`` fallback exceeds
            the platform limit (essentially impossible, but guarded for
            completeness).
    """
    resolved_state_dir = resolve_state_dir(state_dir)

    # If a previous server run dropped a pointer file, honor it.
    pointer = resolved_state_dir / POINTER_FILE_NAME
    if pointer.is_file():
        target = Path(pointer.read_text().strip())
        if len(str(target).encode("utf-8")) >= MAX_SOCKET_PATH_BYTES:
            raise SocketPathTooLongError(
                "Pointer-file target exceeds platform socket-path limit.",
                socket_path=target,
                remediation=(
                    "Delete the pointer file and re-bind the server with "
                    "AGENT_BRAIN_UDS_PATH set to a path under 104 bytes."
                ),
            )
        return target

    canonical = resolved_state_dir / SOCKET_FILE_NAME
    if len(str(canonical).encode("utf-8")) < MAX_SOCKET_PATH_BYTES:
        return canonical

    # Canonical path is too long; use the short fallback.
    fallback = _short_fallback_path(resolved_state_dir)
    if len(str(fallback).encode("utf-8")) >= MAX_SOCKET_PATH_BYTES:
        raise SocketPathTooLongError(
            "Both canonical and /tmp fallback paths exceed platform limit.",
            socket_path=fallback,
            remediation=("Set AGENT_BRAIN_UDS_PATH to a path shorter than 104 bytes."),
        )
    return fallback


def write_pointer_file(state_dir: Path, real_socket_path: Path) -> Path:
    """Write the pointer file used by long-path fallback.

    Called by the server when binding to a ``/tmp`` fallback socket so
    later clients can discover the real socket without recomputing.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    pointer = state_dir / POINTER_FILE_NAME
    pointer.write_text(str(real_socket_path))
    return pointer
