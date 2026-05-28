"""Socket permission validation for agent-brain-uds.

Filesystem permissions are the auth model for local UDS: a socket file
that is mode 0600 owned by the current user is reachable only by that
user. We enforce that explicitly on connect so a symlink-hijack or a
world-readable socket fails loud instead of leaking traffic.

Adversarial test coverage lands in Phase 5 (plan §13). Phase 1 ships
the happy-path and basic rejection logic that those tests build on.

See docs/plans/2026-05-28-mcp-uds-transport-design.md §6.5 / §8.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .errors import SocketNotFoundError, SocketPermissionError

#: Mode bits we refuse to accept on the socket file (group + world rwx).
FORBIDDEN_SOCKET_BITS = stat.S_IRWXG | stat.S_IRWXO  # 0o077

#: Mode we require on the parent directory of the socket file.
REQUIRED_PARENT_DIR_MODE = 0o700


def validate_socket(path: Path) -> None:
    """Validate that a UDS socket file is safe for the current user to connect.

    Checks (in order):

    1. The path is not a symlink (``os.lstat``).
    2. The path exists.
    3. The path is a socket file (``S_ISSOCK``).
    4. The path is owned by the current UID.
    5. The path has no group or world permission bits set.
    6. The parent directory is mode ``0700``.

    Raises:
        SocketNotFoundError: when the path does not exist.
        SocketPermissionError: when any safety check fails.
    """
    # Use lstat to detect symlinks without following them. A symlink at
    # the socket path is a classic privilege-escalation hook.
    try:
        st = os.lstat(path)
    except FileNotFoundError as exc:
        raise SocketNotFoundError(
            f"No socket file at {path}.",
            socket_path=path,
            remediation=(
                "Start the server with `agent-brain start --uds`, or set "
                "AGENT_BRAIN_UDS_PATH to point at an existing socket."
            ),
        ) from exc

    if stat.S_ISLNK(st.st_mode):
        raise SocketPermissionError(
            "Refusing to connect: socket path is a symlink.",
            socket_path=path,
            remediation=(
                "Inspect the symlink target; if expected, delete the symlink "
                "and re-bind the server, which will create a real socket file."
            ),
        )

    if not stat.S_ISSOCK(st.st_mode):
        raise SocketPermissionError(
            "Refusing to connect: path exists but is not a socket file.",
            socket_path=path,
            remediation=(
                "Delete or move the path and re-bind the server to recreate "
                "the socket cleanly."
            ),
        )

    current_uid = os.getuid()
    if st.st_uid != current_uid:
        raise SocketPermissionError(
            f"Refusing to connect: socket owned by uid {st.st_uid}, "
            f"current uid is {current_uid}.",
            socket_path=path,
            remediation=(
                "Confirm you started the server as the current user, or "
                "use sudo -u to run as the socket owner."
            ),
        )

    if st.st_mode & FORBIDDEN_SOCKET_BITS:
        raise SocketPermissionError(
            f"Refusing to connect: socket mode {stat.S_IMODE(st.st_mode):#o} "
            "includes group or world bits.",
            socket_path=path,
            remediation=(
                "Re-bind the server (the bind helper chmod 0600s the socket); "
                "or chmod 600 the existing socket if the server is trustworthy."
            ),
        )

    parent_st = os.lstat(path.parent)
    parent_mode = stat.S_IMODE(parent_st.st_mode)
    if parent_mode != REQUIRED_PARENT_DIR_MODE:
        raise SocketPermissionError(
            f"Refusing to connect: parent directory mode is {parent_mode:#o}, "
            f"expected {REQUIRED_PARENT_DIR_MODE:#o}.",
            socket_path=path,
            remediation=(f"chmod 700 {path.parent} and re-bind the server."),
        )
