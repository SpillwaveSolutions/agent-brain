"""Phase 5 test: pointer-file fallback safety (plan §8).

``resolve_socket_path()`` honours an ``agent-brain.sock.path`` pointer
file inside the state directory so the server can redirect long-path
sockets to ``/tmp``. The pointer file is itself a privilege boundary —
an adversary who can write the pointer file can redirect every client
to a socket of their choosing.

Defenses (Phase 5):

1. Reject the pointer file outright if it is a symlink (``os.lstat``).
   Pre-fix ``Path.is_file()`` follows symlinks, so a symlink to any
   readable file becomes the pointer contents.
2. Require pointer contents to be an absolute path (``Path.is_absolute``).
3. Reject pointer contents with embedded null bytes.

The downstream ``validate_socket(...)`` call still runs on the resolved
path, so the *worst case* is a verbose rejection — but the goal here is
to fail fast on the obvious attack vectors before they reach the socket
layer.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_brain_uds.errors import SocketPermissionError
from agent_brain_uds.paths import POINTER_FILE_NAME, resolve_socket_path


def test_pointer_file_symlink_rejected(tmp_path: Path) -> None:
    """Symlinked pointer file must be rejected, not silently followed."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    os.chmod(state_dir, 0o700)

    real = tmp_path / "evil-contents.txt"
    real.write_text("/tmp/attacker.sock")

    pointer = state_dir / POINTER_FILE_NAME
    pointer.symlink_to(real)

    with pytest.raises(SocketPermissionError) as excinfo:
        resolve_socket_path(state_dir=state_dir)
    msg = str(excinfo.value).lower()
    assert "symlink" in msg or "pointer" in msg


def test_pointer_file_relative_path_rejected(tmp_path: Path) -> None:
    """Pointer contents must be an absolute path."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    os.chmod(state_dir, 0o700)

    pointer = state_dir / POINTER_FILE_NAME
    pointer.write_text("../../tmp/attacker.sock")

    with pytest.raises(SocketPermissionError) as excinfo:
        resolve_socket_path(state_dir=state_dir)
    assert "absolute" in str(excinfo.value).lower()


def test_pointer_file_with_null_byte_rejected(tmp_path: Path) -> None:
    """Embedded null bytes in pointer contents are rejected."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    os.chmod(state_dir, 0o700)

    pointer = state_dir / POINTER_FILE_NAME
    pointer.write_bytes(b"/tmp/attacker.sock\x00rest")

    with pytest.raises(SocketPermissionError) as excinfo:
        resolve_socket_path(state_dir=state_dir)
    assert (
        "null" in str(excinfo.value).lower() or "invalid" in str(excinfo.value).lower()
    )


def test_pointer_file_valid_absolute_path_accepted(tmp_path: Path) -> None:
    """A well-formed pointer file resolves to its target unchanged."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    os.chmod(state_dir, 0o700)

    target = Path("/tmp/agent-brain-abc12345.sock")
    pointer = state_dir / POINTER_FILE_NAME
    pointer.write_text(str(target))

    resolved = resolve_socket_path(state_dir=state_dir)
    assert resolved == target
