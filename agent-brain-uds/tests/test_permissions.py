"""Tests for ``agent_brain_uds.permissions``.

Phase 1 ships the happy-path checks. The full adversarial matrix
(symlink hijack, cross-UID, pointer-file attack) is Phase 5 (plan §13).

All tests that bind a real socket use the ``short_tmp`` fixture instead of
``tmp_path`` — pytest's tmp_path on macOS exceeds the ``sockaddr_un.sun_path``
limit (104 bytes).
"""

from __future__ import annotations

import os
import socket
import stat
from pathlib import Path
from unittest import mock

import pytest

from agent_brain_uds.errors import SocketNotFoundError, SocketPermissionError
from agent_brain_uds.permissions import validate_socket


def _make_socket(state_dir: Path, *, mode: int = 0o600) -> Path:
    """Create a real listening UDS socket inside ``state_dir`` at mode ``mode``.

    Returns the socket path. Caller is responsible for closing the socket
    via the returned ``Path``'s parent fixture cleanup.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(state_dir, 0o700)
    sock_path = state_dir / "agent-brain.sock"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(sock_path))
    os.chmod(sock_path, mode)
    return sock_path


def test_validate_socket_happy_path(short_tmp: Path) -> None:
    sock_path = _make_socket(short_tmp)
    validate_socket(sock_path)  # must not raise


def test_missing_socket_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(SocketNotFoundError) as excinfo:
        validate_socket(tmp_path / "does-not-exist.sock")
    assert excinfo.value.socket_path is not None
    assert excinfo.value.remediation is not None


def test_non_socket_file_rejected(tmp_path: Path) -> None:
    os.chmod(tmp_path, 0o700)
    regular_file = tmp_path / "not-a-socket"
    regular_file.write_text("hello")
    os.chmod(regular_file, 0o600)
    with pytest.raises(SocketPermissionError) as excinfo:
        validate_socket(regular_file)
    assert "not a socket file" in str(excinfo.value)


def test_symlink_rejected(short_tmp: Path) -> None:
    real_dir = short_tmp / "real"
    real_dir.mkdir()
    sock_path = _make_socket(real_dir)

    link_dir = short_tmp / "link"
    link_dir.mkdir()
    os.chmod(link_dir, 0o700)
    link = link_dir / "agent-brain.sock"
    link.symlink_to(sock_path)

    with pytest.raises(SocketPermissionError) as excinfo:
        validate_socket(link)
    assert "symlink" in str(excinfo.value).lower()


def test_world_readable_socket_rejected(short_tmp: Path) -> None:
    sock_path = _make_socket(short_tmp, mode=0o666)
    with pytest.raises(SocketPermissionError) as excinfo:
        validate_socket(sock_path)
    assert "group or world bits" in str(excinfo.value)


def test_group_readable_socket_rejected(short_tmp: Path) -> None:
    sock_path = _make_socket(short_tmp, mode=0o640)
    with pytest.raises(SocketPermissionError):
        validate_socket(sock_path)


def test_loose_parent_dir_rejected(short_tmp: Path) -> None:
    sock_path = _make_socket(short_tmp, mode=0o600)
    os.chmod(short_tmp, 0o755)  # too permissive on the parent
    with pytest.raises(SocketPermissionError) as excinfo:
        validate_socket(sock_path)
    assert "parent directory mode" in str(excinfo.value)


def test_cross_uid_socket_rejected(short_tmp: Path) -> None:
    sock_path = _make_socket(short_tmp)
    real_lstat = os.lstat
    foreign_uid = os.getuid() + 1

    def fake_lstat(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
    ) -> os.stat_result:
        st = real_lstat(path)
        if Path(os.fsdecode(path)) == sock_path:
            # Synthesize a stat_result with a different st_uid.
            return os.stat_result(
                (
                    st.st_mode,
                    st.st_ino,
                    st.st_dev,
                    st.st_nlink,
                    foreign_uid,
                    st.st_gid,
                    st.st_size,
                    st.st_atime,
                    st.st_mtime,
                    st.st_ctime,
                )
            )
        return st

    with mock.patch("agent_brain_uds.permissions.os.lstat", side_effect=fake_lstat):
        with pytest.raises(SocketPermissionError) as excinfo:
            validate_socket(sock_path)
    assert "owned by uid" in str(excinfo.value)


def test_error_carries_remediation_and_path(short_tmp: Path) -> None:
    sock_path = _make_socket(short_tmp, mode=0o666)
    with pytest.raises(SocketPermissionError) as excinfo:
        validate_socket(sock_path)
    assert excinfo.value.socket_path == sock_path
    assert excinfo.value.remediation is not None
    # Validate __str__ surfaces remediation, since CLI/MCP print it directly.
    rendered = str(excinfo.value)
    assert excinfo.value.remediation in rendered


# Sanity reference to FORBIDDEN_SOCKET_BITS so it stays exported.
def test_forbidden_bits_is_subset_of_group_world() -> None:
    from agent_brain_uds.permissions import FORBIDDEN_SOCKET_BITS

    assert FORBIDDEN_SOCKET_BITS & stat.S_IRWXU == 0
    assert (
        FORBIDDEN_SOCKET_BITS & (stat.S_IRWXG | stat.S_IRWXO) == FORBIDDEN_SOCKET_BITS
    )
