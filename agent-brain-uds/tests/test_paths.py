"""Tests for ``agent_brain_uds.paths``.

Covers the five resolver branches and the pointer-file long-path fallback
per plan §6.1.1 / §12.3 acceptance #1.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest import mock

import pytest

from agent_brain_uds.errors import SocketPathTooLongError
from agent_brain_uds.paths import (
    MAX_SOCKET_PATH_BYTES,
    POINTER_FILE_NAME,
    SOCKET_FILE_NAME,
    STATE_DIR_NAME,
    fallback_socket_dir,
    resolve_socket_path,
    resolve_state_dir,
    write_pointer_file,
)

# ---------- resolve_state_dir branches ----------


def test_explicit_state_dir_takes_precedence(tmp_path: Path) -> None:
    explicit = tmp_path / "explicit"
    explicit.mkdir()
    assert resolve_state_dir(explicit) == explicit.resolve()


def test_env_var_used_when_no_argument(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_dir = tmp_path / "from_env"
    env_dir.mkdir()
    monkeypatch.setenv("AGENT_BRAIN_STATE_DIR", str(env_dir))
    assert resolve_state_dir() == env_dir.resolve()


def test_cwd_state_dir_used_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    state_dir = project_root / STATE_DIR_NAME
    state_dir.mkdir(parents=True)
    monkeypatch.chdir(project_root)
    monkeypatch.delenv("AGENT_BRAIN_STATE_DIR", raising=False)
    assert resolve_state_dir() == state_dir.resolve()


def test_walks_up_to_find_state_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    state_dir = project_root / STATE_DIR_NAME
    state_dir.mkdir(parents=True)
    nested = project_root / "src" / "sub" / "deep"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("AGENT_BRAIN_STATE_DIR", raising=False)
    assert resolve_state_dir() == state_dir.resolve()


def test_default_when_no_state_dir_anywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "fresh-project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    monkeypatch.delenv("AGENT_BRAIN_STATE_DIR", raising=False)
    expected = project_root / STATE_DIR_NAME
    assert resolve_state_dir() == expected.resolve()
    # And the directory does not need to exist for the resolver to return it.
    assert not expected.exists()


# ---------- resolve_socket_path canonical case ----------


def test_socket_path_is_state_dir_plus_sock_name(short_tmp: Path) -> None:
    # Use short_tmp so the canonical path fits inside sockaddr_un.sun_path —
    # this test asserts the no-fallback case, not the long-path branch.
    # ``.resolve()`` normalizes the macOS ``/var`` → ``/private/var`` symlink,
    # which ``resolve_state_dir`` also performs.
    expected = (short_tmp / SOCKET_FILE_NAME).resolve()
    assert resolve_socket_path(short_tmp).resolve() == expected


# ---------- pointer-file long-path fallback ----------


def test_pointer_file_is_honored_when_present(short_tmp: Path) -> None:
    real_socket = short_tmp / "agent-brain-deadbeef.sock"
    write_pointer_file(short_tmp, real_socket)
    assert (short_tmp / POINTER_FILE_NAME).is_file()
    assert resolve_socket_path(short_tmp) == real_socket


def test_long_state_dir_falls_back_to_private_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Long canonical path uses a 0o700 per-user dir, never shared /tmp (#252)."""
    import os
    import stat

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    os.chmod(runtime, 0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))

    deep = tmp_path
    for _ in range(10):
        deep = deep / ("x" * 32)
    deep.mkdir(parents=True)

    canonical = deep / SOCKET_FILE_NAME
    assert (
        len(str(canonical).encode("utf-8")) >= MAX_SOCKET_PATH_BYTES
    ), "test fixture must produce an over-limit canonical path"

    resolved = resolve_socket_path(deep)
    assert resolved.parent == runtime.resolve()
    assert resolved.name.startswith("agent-brain-")
    assert resolved.name.endswith(".sock")
    parent_mode = stat.S_IMODE(os.lstat(resolved.parent).st_mode)
    assert parent_mode == 0o700
    digest = hashlib.sha256(str(deep.resolve()).encode("utf-8")).hexdigest()[:8]
    assert resolved == runtime / f"agent-brain-{digest}.sock"


def test_fallback_socket_dir_skips_world_writable_tmp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When TMPDIR is 0o755, fall through to ~/.agent-brain/run (#252)."""
    import os
    import stat

    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    shared_tmp = tmp_path / "shared-tmp"
    shared_tmp.mkdir()
    os.chmod(shared_tmp, 0o755)
    monkeypatch.setattr(
        "agent_brain_uds.paths.tempfile.gettempdir", lambda: str(shared_tmp)
    )
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    chosen = fallback_socket_dir()
    assert chosen == fake_home / ".agent-brain" / "run"
    assert chosen.is_dir()
    assert stat.S_IMODE(os.lstat(chosen).st_mode) == 0o700


def test_pointer_file_pointing_to_too_long_path_raises(tmp_path: Path) -> None:
    long_target = "/tmp/" + ("x" * 200) + ".sock"
    write_pointer_file(tmp_path, Path(long_target))
    with pytest.raises(SocketPathTooLongError):
        resolve_socket_path(tmp_path)


def test_write_pointer_file_creates_state_dir(tmp_path: Path) -> None:
    state_dir = tmp_path / "does-not-exist-yet"
    pointer = write_pointer_file(state_dir, Path("/tmp/foo.sock"))
    assert state_dir.is_dir()
    assert pointer.read_text() == "/tmp/foo.sock"


# ---------- guard against impossible /tmp overflow (defensive) ----------


def test_tmp_fallback_overflow_raises(tmp_path: Path) -> None:
    """Even the /tmp fallback can hit the limit if MAX is mocked very low."""
    deep = tmp_path / ("z" * 50)
    deep.mkdir()
    with mock.patch("agent_brain_uds.paths.MAX_SOCKET_PATH_BYTES", 10):
        with pytest.raises(SocketPathTooLongError):
            resolve_socket_path(deep)
