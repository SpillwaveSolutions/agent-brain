"""Tests for Bearer-token propagation through CLI client + transport.

Issues #179 + #199 (199-04 swap from X-API-Key to Authorization: Bearer).

Covers four independent surfaces:

1. ``DocServeClient(api_key=...)`` — ``Authorization: Bearer`` header set on
   the underlying httpx.Client (199-04 swap from ``X-API-Key``).
2. ``DocServeClient.from_httpx(client, api_key=...)`` — same header injected
   into a pre-built UDS client.
3. ``resolve_api_key`` — env (API_KEY > AGENT_BRAIN_API_KEY w/ deprecation
   log) > runtime.json > config.json > None precedence chain.
4. ``open_backend(ctx)`` — end-to-end: env-provided key reaches the client's
   default headers as a Bearer token.
"""

from __future__ import annotations

import json
import logging
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
    """Strip every Agent Brain auth env var and the canonical ``API_KEY``."""
    candidates = {
        k for k in os.environ if k.startswith("AGENT_BRAIN_") or k == "API_KEY"
    }
    saved = {k: os.environ.pop(k) for k in candidates}
    try:
        yield
    finally:
        for k in candidates:
            os.environ.pop(k, None)
        os.environ.update(saved)


@pytest.fixture(autouse=True)
def reset_legacy_warn_flag() -> Generator[None, None, None]:
    """The deprecation warning fires once per process via a function attribute.
    Reset it around each test so we can re-assert the warning is emitted."""
    if hasattr(resolve_api_key, "_legacy_env_warned"):
        delattr(resolve_api_key, "_legacy_env_warned")
    yield
    if hasattr(resolve_api_key, "_legacy_env_warned"):
        delattr(resolve_api_key, "_legacy_env_warned")


# ---------------------------------------------------------------------------
# DocServeClient header injection
# ---------------------------------------------------------------------------


class TestDocServeClientHeader:
    def test_bearer_header_added_to_httpx_default_headers(self) -> None:
        client = DocServeClient(base_url="http://test", api_key="secret-token")
        try:
            assert client._client.headers["Authorization"] == "Bearer secret-token"
            # X-API-Key MUST NOT be sent — server still accepts it but the
            # CLI side has moved to Bearer entirely.
            assert "X-API-Key" not in client._client.headers
        finally:
            client.close()

    def test_no_auth_header_when_api_key_omitted(self) -> None:
        client = DocServeClient(base_url="http://test")
        try:
            assert "Authorization" not in client._client.headers
            assert "X-API-Key" not in client._client.headers
        finally:
            client.close()

    def test_empty_string_api_key_treated_as_no_auth(self) -> None:
        """Truthy check prevents an empty string from sending a malformed
        ``Authorization: Bearer `` header (note trailing space)."""
        client = DocServeClient(base_url="http://test", api_key="")
        try:
            assert "Authorization" not in client._client.headers
        finally:
            client.close()


class TestFromHttpxHeaderInjection:
    def test_bearer_header_injected_onto_existing_httpx_client(self) -> None:
        inner = httpx.Client(base_url="http://uds-target")
        wrapper = DocServeClient.from_httpx(inner, api_key="uds-secret")
        try:
            assert inner.headers["Authorization"] == "Bearer uds-secret"
            assert "X-API-Key" not in inner.headers
            # The wrapper hands ownership to the inner client
            assert wrapper._client is inner
        finally:
            wrapper.close()

    def test_no_header_when_api_key_omitted(self) -> None:
        inner = httpx.Client(base_url="http://uds-target")
        wrapper = DocServeClient.from_httpx(inner)
        try:
            assert "Authorization" not in inner.headers
        finally:
            wrapper.close()


# ---------------------------------------------------------------------------
# resolve_api_key precedence
# ---------------------------------------------------------------------------


class TestResolveApiKeyPrecedence:
    def test_api_key_env_var_wins(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """API_KEY is the canonical v2 env var — beats every other source."""
        monkeypatch.setenv("API_KEY", "v2-env-key")
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", "legacy-env-key")
        (tmp_path / "runtime.json").write_text(json.dumps({"api_key": "file-key"}))

        assert resolve_api_key(tmp_path) == "v2-env-key"

    def test_legacy_env_var_wins_when_api_key_unset(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """AGENT_BRAIN_API_KEY still works but logs a one-time deprecation warning."""
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", "legacy-env-key")
        (tmp_path / "runtime.json").write_text(json.dumps({"api_key": "file-key"}))

        with caplog.at_level(logging.WARNING, logger="agent_brain_cli.config"):
            assert resolve_api_key(tmp_path) == "legacy-env-key"

        assert any(
            "AGENT_BRAIN_API_KEY environment variable is deprecated" in record.message
            for record in caplog.records
        )

    def test_legacy_deprecation_warning_fires_once_per_process(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Long-running CLI sessions should see the warning once, not on every call."""
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.setenv("AGENT_BRAIN_API_KEY", "legacy-key")

        with caplog.at_level(logging.WARNING, logger="agent_brain_cli.config"):
            resolve_api_key(tmp_path)
            resolve_api_key(tmp_path)
            resolve_api_key(tmp_path)

        warnings = [
            r
            for r in caplog.records
            if "AGENT_BRAIN_API_KEY environment variable is deprecated" in r.message
        ]
        assert len(warnings) == 1

    def test_runtime_json_used_when_env_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        (tmp_path / "runtime.json").write_text(json.dumps({"api_key": "file-key"}))

        assert resolve_api_key(tmp_path) == "file-key"

    def test_returns_none_when_no_source_set(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        # No runtime.json
        assert resolve_api_key(tmp_path) is None

    def test_returns_none_when_runtime_json_omits_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        (tmp_path / "runtime.json").write_text(json.dumps({"base_url": "x"}))

        assert resolve_api_key(tmp_path) is None

    def test_corrupt_runtime_json_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
        (tmp_path / "runtime.json").write_text("{not valid json")

        assert resolve_api_key(tmp_path) is None


# ---------------------------------------------------------------------------
# End-to-end through open_backend
# ---------------------------------------------------------------------------


class TestOpenBackendEndToEnd:
    def test_env_api_key_reaches_http_client_as_bearer(self, clean_env: None) -> None:
        from agent_brain_cli.client.transport import open_backend

        os.environ["API_KEY"] = "e2e-secret"
        cmd = click.Command("test")
        ctx = click.Context(cmd)
        ctx.obj = {
            "transport_hint": "http",
            "base_url_override": "http://127.0.0.1:9001",
        }
        client = open_backend(ctx)
        try:
            assert client._client.headers["Authorization"] == "Bearer e2e-secret"
            assert "X-API-Key" not in client._client.headers
        finally:
            client.close()
