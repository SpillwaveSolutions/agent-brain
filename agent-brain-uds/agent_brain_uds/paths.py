"""Socket path resolution for agent-brain-uds.

Mirrors the state-directory lookup in ``agent_brain_server.runtime`` /
``agent_brain_server.storage_paths`` so client and server agree on where
the socket lives. Handles the platform sockaddr_un length limit by
falling back to a short per-user path and writing a pointer file inside
the state directory.

See docs/plans/2026-05-28-mcp-uds-transport-design.md §6.1.
"""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
from pathlib import Path

from .errors import SocketPathTooLongError, SocketPermissionError

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


def fallback_socket_dir() -> Path:
    """Return a per-user 0o700 directory for long-path UDS fallbacks.

    ``/tmp`` is mode 0o755 (or 0o1777) on every supported OS, so the
    client-side parent-dir check refuses it and ``chmod 700 /tmp`` is
    not actionable. Issue #252.

    Order:

    1. ``$XDG_RUNTIME_DIR`` when set (Linux, already 0o700).
    2. ``tempfile.gettempdir()`` when its mode is 0o700 (macOS ``$TMPDIR``
       is ``/var/folders/.../T``, per-user, short).
    3. ``~/.agent-brain/run/``, created with mode 0o700.
    """
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        candidate = Path(xdg)
        if candidate.is_dir():
            return candidate

    tmp = Path(tempfile.gettempdir())
    try:
        if tmp.is_dir() and stat.S_IMODE(os.lstat(tmp).st_mode) == 0o700:
            return tmp
    except OSError:
        pass

    run_dir = Path.home() / ".agent-brain" / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(run_dir, 0o700)
    except OSError:
        pass
    return run_dir


def _short_fallback_path(state_dir: Path) -> Path:
    """Return a short fallback socket path derived from the state-dir hash.

    The hash makes the fallback deterministic per project, so concurrent
    instances in different projects do not collide. Parent directory is
    always a per-user private dir (issue #252), never shared ``/tmp``.
    """
    digest = hashlib.sha256(str(state_dir.resolve()).encode("utf-8")).hexdigest()[:8]
    return fallback_socket_dir() / f"agent-brain-{digest}.sock"


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
    path is too long for the platform, returns the short per-user fallback
    (the server is responsible for writing the pointer file when it binds).

    Raises:
        SocketPathTooLongError: when even the per-user fallback exceeds
            the platform limit (essentially impossible, but guarded for
            completeness).
    """
    resolved_state_dir = resolve_state_dir(state_dir)

    # If a previous server run dropped a pointer file, honor it — but
    # validate it first (plan §8). The pointer file is a privilege
    # boundary: whoever writes it controls every client's destination.
    pointer = resolved_state_dir / POINTER_FILE_NAME
    target = _read_pointer_file(pointer)
    if target is not None:
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
            "Both canonical and per-user fallback paths exceed platform limit.",
            socket_path=fallback,
            remediation=("Set AGENT_BRAIN_UDS_PATH to a path shorter than 104 bytes."),
        )
    return fallback


def _read_pointer_file(pointer: Path) -> Path | None:
    """Return the validated socket path from ``pointer`` or ``None``.

    Defenses (plan §8 — Phase 5):

    * ``os.lstat`` instead of ``Path.is_file`` so a symlink at the
      pointer path is detected, not silently followed.
    * Pointer must be a regular file; symlinks / sockets / fifos / dirs
      are rejected outright.
    * Pointer contents must be an absolute path with no embedded null
      bytes.

    ``validate_socket(...)`` still runs on the returned path before any
    connection, so this is defense-in-depth — the goal is to fail fast
    on obviously attacker-controlled inputs rather than to substitute
    for the socket-level checks.
    """
    try:
        pst = os.lstat(pointer)
    except FileNotFoundError:
        return None

    if stat.S_ISLNK(pst.st_mode):
        raise SocketPermissionError(
            "Refusing to follow symlinked pointer file.",
            socket_path=pointer,
            remediation=(
                f"Delete {pointer} (it is a symlink) and re-bind the "
                "server, which will write a real pointer file."
            ),
        )
    if not stat.S_ISREG(pst.st_mode):
        raise SocketPermissionError(
            "Pointer file is not a regular file.",
            socket_path=pointer,
            remediation=f"Delete {pointer} and re-bind the server.",
        )

    raw = pointer.read_bytes()
    if b"\x00" in raw:
        raise SocketPermissionError(
            "Pointer file contains an embedded null byte; refusing to parse.",
            socket_path=pointer,
            remediation=f"Delete {pointer} and re-bind the server.",
        )

    target_str = raw.decode("utf-8", errors="strict").strip()
    target = Path(target_str)
    if not target.is_absolute():
        raise SocketPermissionError(
            f"Pointer-file target {target_str!r} is not an absolute path.",
            socket_path=target,
            remediation=(
                f"Delete {pointer} and re-bind the server (or set "
                "AGENT_BRAIN_UDS_PATH to an absolute path under 104 bytes)."
            ),
        )
    return target


def write_pointer_file(state_dir: Path, real_socket_path: Path) -> Path:
    """Write the pointer file used by long-path fallback.

    Called by the server when binding to a short fallback socket so
    later clients can discover the real socket without recomputing.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    pointer = state_dir / POINTER_FILE_NAME
    pointer.write_text(str(real_socket_path))
    return pointer
