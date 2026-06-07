"""Phase 58-03 tests: ``resolve_mcp_transport`` discovery integration.

Closes CLI-MCP-08 (config-layer half). The helper now accepts a
``state_dir`` kwarg and reads ``mcp.runtime.json`` before raising, with
verbatim v3 design doc §3.5 wording on miss.

Also pins that the Phase 57 placeholder string
``"discovery file support lands in Phase 58; pass --mcp-url explicitly in Phase 57"``
has been DELETED from ``config.py``.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import click
import pytest


@pytest.fixture
def clean_mcp_env(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Strip the two MCP env vars for the duration of one test."""
    monkeypatch.delenv("AGENT_BRAIN_MCP_TRANSPORT", raising=False)
    monkeypatch.delenv("AGENT_BRAIN_MCP_URL", raising=False)
    yield


def _write_runtime(
    state_dir: Path, *, host: str = "127.0.0.1", port: int = 8765
) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    runtime = {
        "host": host,
        "port": port,
        "pid": 12345,
        "started_at": "2026-06-07T00:00:00+00:00",
        "transport": "http",
    }
    (state_dir / "mcp.runtime.json").write_text(json.dumps(runtime))


def test_resolve_mcp_transport_http_uses_discovery_when_no_url(
    clean_mcp_env: None, tmp_path: Path
) -> None:
    """http + no url + valid runtime → discovery yields http://host:port/mcp."""
    from agent_brain_cli.config import resolve_mcp_transport

    _write_runtime(tmp_path, host="127.0.0.1", port=8765)
    transport, target = resolve_mcp_transport(
        mcp_transport_hint="http",
        mcp_url_override=None,
        state_dir=tmp_path,
    )
    assert transport == "http"
    assert target == "http://127.0.0.1:8765/mcp"


def test_resolve_mcp_transport_http_raises_with_section_3_5_wording(
    clean_mcp_env: None, tmp_path: Path
) -> None:
    """http + no url + no runtime → click.UsageError with verbatim §3.5 wording."""
    from agent_brain_cli.config import resolve_mcp_transport

    with pytest.raises(click.UsageError) as exc_info:
        resolve_mcp_transport(
            mcp_transport_hint="http",
            mcp_url_override=None,
            state_dir=tmp_path,
        )
    msg = str(exc_info.value)
    assert "discovery file not found at" in msg
    assert "run 'agent-brain mcp start' or pass --mcp-url" in msg
    # The actual state_dir path must be interpolated.
    assert str(tmp_path) in msg


def test_resolve_mcp_transport_explicit_url_beats_discovery(
    clean_mcp_env: None, tmp_path: Path
) -> None:
    """Explicit url overrides discovery even when runtime exists."""
    from agent_brain_cli.config import resolve_mcp_transport

    _write_runtime(tmp_path, port=8765)
    transport, target = resolve_mcp_transport(
        mcp_transport_hint="http",
        mcp_url_override="http://127.0.0.1:9999/mcp",
        state_dir=tmp_path,
    )
    assert transport == "http"
    assert target == "http://127.0.0.1:9999/mcp"


def test_resolve_mcp_transport_env_url_beats_discovery(
    clean_mcp_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AGENT_BRAIN_MCP_URL env overrides discovery even when runtime exists."""
    from agent_brain_cli.config import resolve_mcp_transport

    _write_runtime(tmp_path, port=8765)
    monkeypatch.setenv("AGENT_BRAIN_MCP_URL", "http://127.0.0.1:7777/mcp")
    transport, target = resolve_mcp_transport(
        mcp_transport_hint="http",
        mcp_url_override=None,
        state_dir=tmp_path,
    )
    assert transport == "http"
    assert target == "http://127.0.0.1:7777/mcp"


def test_phase_57_placeholder_wording_removed_from_config_py() -> None:
    """The Phase 57 placeholder string is GONE from config.py."""
    config_path = (
        Path(__file__).resolve().parent.parent
        / "agent_brain_cli"
        / "config.py"
    )
    source = config_path.read_text()
    assert source.count("discovery file support lands in Phase 58") == 0, (
        "Phase 57 placeholder wording must be removed from config.py "
        "(Plan 58-03 must_have)"
    )


def test_resolve_mcp_transport_stdio_unchanged(clean_mcp_env: None) -> None:
    """Backwards-compat regression: stdio path returns (stdio, None)."""
    from agent_brain_cli.config import resolve_mcp_transport

    transport, target = resolve_mcp_transport(mcp_transport_hint="stdio")
    assert transport == "stdio"
    assert target is None
