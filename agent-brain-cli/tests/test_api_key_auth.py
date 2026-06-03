"""Tests for CLI-side bearer-token auth wiring (Issue #179).

Covers ``get_api_key`` resolution (env > runtime.json > none) and that
``DocServeClient`` attaches ``Authorization: Bearer <token>`` only when a key is
present.
"""

import json
from unittest.mock import patch

from agent_brain_cli.client.api_client import DocServeClient
from agent_brain_cli.config import get_api_key


def test_get_api_key_from_env(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "env-key")
    assert get_api_key() == "env-key"


def test_get_api_key_from_runtime_json(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
    (tmp_path / "runtime.json").write_text(json.dumps({"api_key": "rt-key"}))
    with patch("agent_brain_cli.config.get_state_dir", return_value=tmp_path):
        assert get_api_key() == "rt-key"


def test_env_overrides_runtime_json(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_BRAIN_API_KEY", "env-key")
    (tmp_path / "runtime.json").write_text(json.dumps({"api_key": "rt-key"}))
    with patch("agent_brain_cli.config.get_state_dir", return_value=tmp_path):
        assert get_api_key() == "env-key"


def test_get_api_key_none_when_absent(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
    with patch("agent_brain_cli.config.get_state_dir", return_value=tmp_path):
        assert get_api_key() is None


def test_get_api_key_none_when_runtime_has_no_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("AGENT_BRAIN_API_KEY", raising=False)
    (tmp_path / "runtime.json").write_text(json.dumps({"base_url": "http://x"}))
    with patch("agent_brain_cli.config.get_state_dir", return_value=tmp_path):
        assert get_api_key() is None


def test_client_sends_bearer_header() -> None:
    client = DocServeClient(base_url="http://x", api_key="my-key")
    try:
        assert client._client.headers["Authorization"] == "Bearer my-key"
    finally:
        client.close()


def test_client_no_header_without_key() -> None:
    client = DocServeClient(base_url="http://x")
    try:
        assert "authorization" not in client._client.headers
    finally:
        client.close()
