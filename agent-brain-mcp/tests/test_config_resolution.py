"""Phase 4 test: backend client resolution (plan §7)."""

from __future__ import annotations

import os
import socket
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from agent_brain_mcp.config import (
    DEFAULT_HTTP_BASE_URL,
    open_backend_client,
)


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
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
    base = Path(tempfile.mkdtemp(prefix="absrv-mcp-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        import shutil

        shutil.rmtree(base, ignore_errors=True)


class TestExplicitBackend:
    def test_http_returns_http(self, clean_env: None) -> None:
        transport, client = open_backend_client(
            backend="http", backend_url="http://127.0.0.1:9000"
        )
        try:
            assert transport == "http"
            assert str(client.base_url).startswith("http://127.0.0.1:9000")
        finally:
            client.close()

    def test_uds_with_real_socket(self, clean_env: None, short_state_dir: Path) -> None:
        socket_path = short_state_dir / "agent-brain.sock"
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        os.chmod(short_state_dir, 0o700)
        try:
            transport, client = open_backend_client(
                backend="uds", socket_path=socket_path
            )
            try:
                assert transport == "uds"
            finally:
                client.close()
        finally:
            s.close()


class TestAutoBackend:
    def test_auto_falls_back_to_http_without_socket(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        transport, client = open_backend_client(
            backend="auto",
            socket_path=short_state_dir / "no-such.sock",
            backend_url="http://127.0.0.1:8000",
        )
        try:
            assert transport == "http"
        finally:
            client.close()

    def test_auto_picks_uds_when_validates(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        socket_path = short_state_dir / "agent-brain.sock"
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        os.chmod(short_state_dir, 0o700)
        try:
            transport, client = open_backend_client(
                backend="auto", socket_path=socket_path
            )
            try:
                assert transport == "uds"
            finally:
                client.close()
        finally:
            s.close()


class TestHttpUrlResolution:
    def test_default_url(self, clean_env: None, short_state_dir: Path) -> None:
        transport, client = open_backend_client(
            backend="http",
            socket_path=short_state_dir / "x.sock",
        )
        try:
            assert str(client.base_url).startswith(DEFAULT_HTTP_BASE_URL)
        finally:
            client.close()

    def test_env_url(self, clean_env: None) -> None:
        os.environ["AGENT_BRAIN_URL"] = "http://127.0.0.1:9555"
        transport, client = open_backend_client(backend="http")
        try:
            assert "9555" in str(client.base_url)
        finally:
            client.close()
