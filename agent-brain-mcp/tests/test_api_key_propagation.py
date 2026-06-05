"""Tests for X-API-Key propagation through the MCP backend client (Issue #179).

Covers the precedence chain in ``_resolve_api_key`` and verifies the
resolved key reaches the httpx.Client default headers for both HTTP and
UDS transports.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from agent_brain_mcp.config import (
    _resolve_api_key,
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
    base = Path(tempfile.mkdtemp(prefix="absrv-mcp-auth-"))
    os.chmod(base, 0o700)
    try:
        yield base
    finally:
        import shutil

        shutil.rmtree(base, ignore_errors=True)


class TestResolveApiKeyPrecedence:
    def test_mcp_specific_env_wins(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        os.environ["AGENT_BRAIN_MCP_API_KEY"] = "mcp-env-key"
        os.environ["AGENT_BRAIN_API_KEY"] = "shared-env-key"
        (short_state_dir / "runtime.json").write_text(
            json.dumps({"api_key": "runtime-key"})
        )
        (short_state_dir / "config.json").write_text(
            json.dumps({"api_key": "config-key"})
        )

        assert _resolve_api_key(short_state_dir) == "mcp-env-key"

    def test_shared_env_used_when_mcp_specific_absent(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        os.environ["AGENT_BRAIN_API_KEY"] = "shared-env-key"
        (short_state_dir / "runtime.json").write_text(
            json.dumps({"api_key": "runtime-key"})
        )

        assert _resolve_api_key(short_state_dir) == "shared-env-key"

    def test_runtime_json_used_when_no_env(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        (short_state_dir / "runtime.json").write_text(
            json.dumps({"api_key": "runtime-key"})
        )
        (short_state_dir / "config.json").write_text(
            json.dumps({"api_key": "config-key"})
        )

        assert _resolve_api_key(short_state_dir) == "runtime-key"

    def test_config_json_fallback_when_runtime_absent(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        (short_state_dir / "config.json").write_text(
            json.dumps({"api_key": "config-key"})
        )

        assert _resolve_api_key(short_state_dir) == "config-key"

    def test_returns_none_when_no_source(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        assert _resolve_api_key(short_state_dir) is None


class TestHttpClientHeaderInjection:
    def test_api_key_added_to_http_client_default_headers(
        self, clean_env: None
    ) -> None:
        os.environ["AGENT_BRAIN_API_KEY"] = "http-test-key"

        transport, client = open_backend_client(
            backend="http", backend_url="http://127.0.0.1:9000"
        )
        try:
            assert transport == "http"
            assert client.headers["X-API-Key"] == "http-test-key"
        finally:
            client.close()

    def test_no_header_when_no_key_resolved(self, clean_env: None) -> None:
        transport, client = open_backend_client(
            backend="http", backend_url="http://127.0.0.1:9000"
        )
        try:
            assert "X-API-Key" not in client.headers
        finally:
            client.close()


class TestUdsClientHeaderInjection:
    def test_api_key_added_to_uds_client_default_headers(
        self, clean_env: None, short_state_dir: Path
    ) -> None:
        socket_path = short_state_dir / "agent-brain.sock"
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        os.chmod(short_state_dir, 0o700)

        os.environ["AGENT_BRAIN_API_KEY"] = "uds-test-key"

        try:
            transport, client = open_backend_client(
                backend="uds", socket_path=socket_path
            )
            try:
                assert transport == "uds"
                assert client.headers["X-API-Key"] == "uds-test-key"
            finally:
                client.close()
        finally:
            s.close()
