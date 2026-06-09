"""Phase 58-03 tests: ``McpHttpBackend.__init__`` discovery integration.

Closes CLI-MCP-08 — the constructor accepts ``url=None`` and resolves the
URL via ``<state_dir>/mcp.runtime.json`` (Phase 58 §2.4 locked schema).
On a discovery miss, raises ``RuntimeError`` with the verbatim v3 design
doc §3.5 wording.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_brain_mcp.client import McpHttpBackend


def _write_runtime(
    state_dir: Path, *, host: str = "127.0.0.1", port: int = 9000
) -> None:
    """Write a 5-field §2.4 mcp.runtime.json into state_dir."""
    state_dir.mkdir(parents=True, exist_ok=True)
    runtime = {
        "host": host,
        "port": port,
        "pid": 12345,
        "started_at": "2026-01-01T00:00:00+00:00",
        "transport": "http",
    }
    (state_dir / "mcp.runtime.json").write_text(json.dumps(runtime))


def test_mcp_http_backend_uses_explicit_url_when_given() -> None:
    """Backwards compat: explicit url is honored verbatim."""
    backend = McpHttpBackend(url="http://x:1/mcp")
    assert backend.url == "http://x:1/mcp"


def test_mcp_http_backend_raises_value_error_when_both_none() -> None:
    """Both url and state_dir None is a programmer error → ValueError."""
    with pytest.raises(ValueError, match="must pass either url or state_dir"):
        McpHttpBackend(url=None, state_dir=None)


def test_mcp_http_backend_discovers_via_state_dir(tmp_path: Path) -> None:
    """url=None + state_dir + valid runtime → discovery succeeds."""
    _write_runtime(tmp_path, host="127.0.0.1", port=9000)
    backend = McpHttpBackend(url=None, state_dir=tmp_path)
    assert backend.url == "http://127.0.0.1:9000/mcp"


def test_mcp_http_backend_raises_when_discovery_file_missing(
    tmp_path: Path,
) -> None:
    """url=None + state_dir + no runtime → RuntimeError with §3.5 wording."""
    with pytest.raises(RuntimeError) as exc_info:
        McpHttpBackend(url=None, state_dir=tmp_path)
    msg = str(exc_info.value)
    assert "discovery file not found at" in msg
    assert "run 'agent-brain mcp start' or pass --mcp-url" in msg


def test_mcp_http_backend_raises_when_discovery_file_malformed(
    tmp_path: Path,
) -> None:
    """Runtime missing port → RuntimeError mentions 'malformed: missing host/port'."""
    # Write a runtime missing the port field.
    (tmp_path / "mcp.runtime.json").write_text(
        json.dumps(
            {
                "host": "127.0.0.1",
                # port deliberately omitted
                "pid": 12345,
                "started_at": "2026-01-01T00:00:00+00:00",
                "transport": "http",
            }
        )
    )
    with pytest.raises(RuntimeError, match="malformed: missing host/port"):
        McpHttpBackend(url=None, state_dir=tmp_path)


def test_mcp_http_backend_error_contains_state_dir_path(tmp_path: Path) -> None:
    """The actual state_dir path appears in the error message (no placeholder leak)."""
    with pytest.raises(RuntimeError) as exc_info:
        McpHttpBackend(url=None, state_dir=tmp_path)
    msg = str(exc_info.value)
    assert str(tmp_path) in msg
    # No raw angle-bracket placeholder should leak through.
    assert "<state_dir>" not in msg
