"""Shared pytest fixtures for agent-brain-uds tests."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def short_tmp() -> Generator[Path, None, None]:
    """A tempdir guaranteed short enough for AF_UNIX paths on macOS.

    Pytest's built-in ``tmp_path`` resolves to ``/private/var/folders/.../
    pytest-of-USER/pytest-N/test_NAME0`` on macOS, which routinely exceeds the
    104-byte ``sockaddr_un.sun_path`` limit when a ``agent-brain.sock`` segment
    is appended. Tests that bind a real socket (or assert on the canonical
    socket path, not the long-path fallback) must use this fixture instead.

    Returns a path under ``/tmp/abuds-<random>`` and removes it on teardown.
    """
    base = Path(tempfile.mkdtemp(prefix="abuds-"))
    try:
        yield base
    finally:
        shutil.rmtree(base, ignore_errors=True)
