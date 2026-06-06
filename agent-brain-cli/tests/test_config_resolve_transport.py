"""Phase 3 TDD: ``agent_brain_cli.config.resolve_transport``.

Maps to plan §12.3 acceptance #6 (``--transport auto`` picks UDS when the
socket validates, HTTP otherwise; clear error when neither is reachable).

The function is the *pure* resolver — returns a ``("http"|"uds", target)``
tuple. The live ``httpx.Client`` construction lives in
``agent_brain_cli.client.transport.open_backend`` (see test_transport_selector).

RED until Phase 3 ships ``resolve_transport()`` next to ``get_server_url()``
in ``agent_brain_cli/config.py``.
"""

from __future__ import annotations

import os
import socket
import stat
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """Strip all AGENT_BRAIN_* env vars for the duration of one test."""
    keys = [k for k in os.environ if k.startswith("AGENT_BRAIN_")]
    saved = {k: os.environ.pop(k) for k in keys}
    try:
        yield
    finally:
        for k in keys:
            os.environ.pop(k, None)
        os.environ.update(saved)


@pytest.fixture
def short_state_dir() -> Generator[Path, None, None]:
    """A short /tmp-rooted state dir suitable for an AF_UNIX socket."""
    base = Path(tempfile.mkdtemp(prefix="absrv-tx-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        import shutil

        shutil.rmtree(base, ignore_errors=True)


def _bind_real_socket(socket_path: Path) -> socket.socket:
    """Bind a real AF_UNIX socket so ``validate_socket`` will accept it."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(socket_path))
    os.chmod(socket_path, 0o600)
    # Tighten parent dir too — validate_socket checks it
    os.chmod(socket_path.parent, 0o700)
    return s


class TestResolveTransportExplicit:
    """``transport_hint`` argument wins over env / auto-detection."""

    def test_explicit_http_returns_http(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        from agent_brain_cli.config import resolve_transport

        transport, target = resolve_transport(
            transport_hint="http", base_url_override="http://127.0.0.1:9999"
        )
        assert transport == "http"
        assert target == "http://127.0.0.1:9999"

    def test_explicit_uds_returns_uds(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        from agent_brain_cli.config import resolve_transport

        socket_path = short_state_dir / "agent-brain.sock"
        s = _bind_real_socket(socket_path)
        try:
            transport, target = resolve_transport(
                transport_hint="uds", socket_path_override=socket_path
            )
            assert transport == "uds"
            assert target == str(socket_path)
        finally:
            s.close()

    def test_explicit_uds_with_missing_socket_raises(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        """Plan §12.3 #7 — `--transport uds` without socket should
        fail loudly, not silently fall back to HTTP."""
        from agent_brain_uds import SocketNotFoundError

        from agent_brain_cli.config import resolve_transport

        with pytest.raises((SocketNotFoundError, FileNotFoundError, OSError)):
            resolve_transport(
                transport_hint="uds",
                socket_path_override=short_state_dir / "does-not-exist.sock",
            )


class TestResolveTransportEnv:
    """``AGENT_BRAIN_TRANSPORT`` env var read when ``transport_hint`` is None."""

    def test_env_http_overrides_default(self, clean_env: None) -> None:
        from agent_brain_cli.config import resolve_transport

        os.environ["AGENT_BRAIN_TRANSPORT"] = "http"
        os.environ["AGENT_BRAIN_URL"] = "http://127.0.0.1:8123"
        transport, target = resolve_transport()
        assert transport == "http"
        assert target == "http://127.0.0.1:8123"

    def test_env_uds_picks_uds(self, clean_env: None, short_state_dir: Path) -> None:
        from agent_brain_cli.config import resolve_transport

        socket_path = short_state_dir / "agent-brain.sock"
        s = _bind_real_socket(socket_path)
        try:
            os.environ["AGENT_BRAIN_TRANSPORT"] = "uds"
            os.environ["AGENT_BRAIN_UDS_PATH"] = str(socket_path)
            transport, target = resolve_transport()
            assert transport == "uds"
            assert target == str(socket_path)
        finally:
            s.close()


class TestResolveTransportAuto:
    """``auto`` mode tries UDS first, falls back to HTTP."""

    def test_auto_picks_uds_when_socket_validates(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        """Plan §12.3 #6 (first half)."""
        from agent_brain_cli.config import resolve_transport

        socket_path = short_state_dir / "agent-brain.sock"
        s = _bind_real_socket(socket_path)
        try:
            transport, target = resolve_transport(
                transport_hint="auto", socket_path_override=socket_path
            )
            assert transport == "uds"
            assert target == str(socket_path)
        finally:
            s.close()

    def test_auto_falls_back_to_http_when_socket_missing(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        """Plan §12.3 #6 (second half)."""
        from agent_brain_cli.config import resolve_transport

        transport, target = resolve_transport(
            transport_hint="auto",
            socket_path_override=short_state_dir / "missing.sock",
            base_url_override="http://127.0.0.1:8000",
        )
        assert transport == "http"
        assert target == "http://127.0.0.1:8000"

    def test_auto_default_is_auto(self, clean_env: None, short_state_dir: Path) -> None:
        """No env, no hint → behaves as ``auto``."""
        from agent_brain_cli.config import resolve_transport

        with patch(
            "agent_brain_cli.config.get_server_url",
            return_value="http://127.0.0.1:8000",
        ):
            transport, target = resolve_transport(
                socket_path_override=short_state_dir / "missing.sock"
            )
            assert transport == "http"
            assert target == "http://127.0.0.1:8000"


class TestResolveTransportPermissions:
    """``auto`` mode must reject sockets that fail permission checks
    rather than treating them as valid UDS targets."""

    def test_auto_skips_world_readable_socket(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        from agent_brain_cli.config import resolve_transport

        socket_path = short_state_dir / "agent-brain.sock"
        s = _bind_real_socket(socket_path)
        # Make it world-readable to fail the permission check.
        os.chmod(socket_path, 0o644)
        # Sanity check the chmod stuck.
        assert stat.S_IMODE(os.stat(socket_path).st_mode) == 0o644
        try:
            transport, target = resolve_transport(
                transport_hint="auto",
                socket_path_override=socket_path,
                base_url_override="http://127.0.0.1:8000",
            )
            # Auto must fall back; loose-perm socket is NOT a valid UDS.
            assert transport == "http"
            assert target == "http://127.0.0.1:8000"
        finally:
            s.close()
