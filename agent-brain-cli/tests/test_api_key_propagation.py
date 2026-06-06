"""Tests for X-API-Key propagation through CLI client + transport (Issue #179).

Covers three independent surfaces:

1. ``DocServeClient(api_key=...)`` — header set on the underlying httpx.Client.
2. ``DocServeClient.from_httpx(client, api_key=...)`` — header injected into
   a pre-built UDS client.
3. ``resolve_api_key`` — env > runtime.json > None precedence chain.
4. ``open_backend(ctx)`` — end-to-end: env-provided key reaches the client's
   default headers.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from pathlib import Path

import click
import httpx
import pytest

from agent_brain_cli.client.api_client import DocServeClient
from agent_brain_cli.config import resolve_api_key


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


# ---------------------------------------------------------------------------
# DocServeClient header injection
# ---------------------------------------------------------------------------


class TestDocServeClientHeader:
    def test_api_key_added_to_httpx_default_headers(self) -> None:
        client = DocServeClient(base_url="http://test", api_key="secret-token")
        try:
            assert client._client.headers["X-API-Key"] == "secret-token"
        finally:
            client.close()

    def test_no_header_when_api_key_omitted(self) -> None:
        client = DocServeClient(base_url="http://test")
        try:
            assert "X-API-Key" not in client._client.headers
        finally:
            client.close()

    def test_empty_string_api_key_treated_as_no_auth(self) -> None:
        """Truthy check prevents an empty string from setting an empty header."""
        client = DocServeClient(base_url="http://test", api_key="")
        try:
            assert "X-API-Key" not in client._client.headers
        finally:
            client.close()


class TestFromHttpxHeaderInjection:
    def test_api_key_injected_onto_existing_httpx_client(self) -> None:
        inner = httpx.Client(base_url="http://uds-target")
        wrapper = DocServeClient.from_httpx(inner, api_key="uds-secret")
        try:
            assert inner.headers["X-API-Key"] == "uds-secret"
            # The wrapper hands ownership to the inner client
            assert wrapper._client is inner
        finally:
            wrapper.close()

    def test_no_header_when_api_key_omitted(self) -> None:
        inner = httpx.Client(base_url="http://uds-target")
        wrapper = DocServeClient.from_httpx(inner)
        try:
            assert "X-API-Key" not in inner.headers
        finally:
            wrapper.close()


# ---------------------------------------------------------------------------
# resolve_api_key precedence
# ---------------------------------------------------------------------------


class TestResolveApiKeyPrecedence:
    def test_env_var_wins(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", "env-key")
        (tmp_path / "runtime.json").write_text(json.dumps({"api_key": "file-key"}))

        assert resolve_api_key(tmp_path) == "env-key"

    def test_runtime_json_used_when_env_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        (tmp_path / "runtime.json").write_text(json.dumps({"api_key": "file-key"}))

        assert resolve_api_key(tmp_path) == "file-key"

    def test_returns_none_when_no_source_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        # No runtime.json
        assert resolve_api_key(tmp_path) is None

    def test_returns_none_when_runtime_json_omits_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        (tmp_path / "runtime.json").write_text(json.dumps({"base_url": "x"}))

        assert resolve_api_key(tmp_path) is None

    def test_corrupt_runtime_json_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        (tmp_path / "runtime.json").write_text("{not valid json")

        assert resolve_api_key(tmp_path) is None


# ---------------------------------------------------------------------------
# End-to-end through open_backend
# ---------------------------------------------------------------------------


class TestOpenBackendEndToEnd:
    def test_env_api_key_reaches_http_client(self, clean_env: None) -> None:
        from agent_brain_cli.client.transport import open_backend

        os.environ["AGENT_BRAIN_API_KEY"] = "e2e-secret"
        cmd = click.Command("test")
        ctx = click.Context(cmd)
        ctx.obj = {
            "transport_hint": "http",
            "base_url_override": "http://127.0.0.1:9001",
        }
        client = open_backend(ctx)
        try:
            assert client._client.headers["X-API-Key"] == "e2e-secret"
        finally:
            client.close()
