"""Phase 57-01 TDD: ``agent_brain_cli.config.resolve_mcp_transport``.

Maps to v3 design doc §3.5 (No-silent-fallback contract) — the helper
is the *pure* per-axis resolver for the MCP transport axis, mirroring
the shape of :func:`agent_brain_cli.config.resolve_transport` (which
handles the HTTP/UDS axis).

Precedence (per Phase 57 CONTEXT §decisions / design doc §3.5):

  1. ``mcp_transport_hint`` argument (CLI ``--mcp-transport`` flag)
  2. ``AGENT_BRAIN_MCP_TRANSPORT`` environment variable
  3. Default: ``"stdio"``

URL precedence for ``http`` transport:

  1. ``mcp_url_override`` argument (CLI ``--mcp-url`` flag)
  2. ``AGENT_BRAIN_MCP_URL`` environment variable
  3. Hard error — `mcp.runtime.json` discovery lands in Phase 58.

RED until Phase 57-01 ships ``resolve_mcp_transport()`` next to
``resolve_transport()`` in ``agent_brain_cli/config.py``.
"""

from __future__ import annotations

import os
from collections.abc import Generator

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


class TestResolveMcpTransportFlagWins:
    """``mcp_transport_hint`` argument wins over env / default."""

    def test_explicit_stdio_returns_stdio_no_target(self, clean_mcp_env: None) -> None:
        from agent_brain_cli.config import resolve_mcp_transport

        transport, target = resolve_mcp_transport(mcp_transport_hint="stdio")
        assert transport == "stdio"
        assert target is None

    def test_explicit_http_with_url_override(self, clean_mcp_env: None) -> None:
        from agent_brain_cli.config import resolve_mcp_transport

        transport, target = resolve_mcp_transport(
            mcp_transport_hint="http",
            mcp_url_override="http://127.0.0.1:9999/mcp",
        )
        assert transport == "http"
        assert target == "http://127.0.0.1:9999/mcp"


class TestResolveMcpTransportEnvPrecedence:
    """Env vars are honored when the flag is None; default below env."""

    def test_env_transport_and_env_url(
        self, clean_mcp_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_brain_cli.config import resolve_mcp_transport

        monkeypatch.setenv("AGENT_BRAIN_MCP_TRANSPORT", "http")
        monkeypatch.setenv("AGENT_BRAIN_MCP_URL", "http://127.0.0.1:7777/mcp")
        transport, target = resolve_mcp_transport(mcp_transport_hint=None)
        assert transport == "http"
        assert target == "http://127.0.0.1:7777/mcp"

    def test_default_is_stdio_when_nothing_set(self, clean_mcp_env: None) -> None:
        from agent_brain_cli.config import resolve_mcp_transport

        transport, target = resolve_mcp_transport(mcp_transport_hint=None)
        assert transport == "stdio"
        assert target is None

    def test_env_url_supplies_target_when_flag_missing(
        self, clean_mcp_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from agent_brain_cli.config import resolve_mcp_transport

        monkeypatch.setenv("AGENT_BRAIN_MCP_URL", "http://127.0.0.1:8888/mcp")
        transport, target = resolve_mcp_transport(
            mcp_transport_hint="http", mcp_url_override=None
        )
        assert transport == "http"
        assert target == "http://127.0.0.1:8888/mcp"


class TestResolveMcpTransportHttpWithoutUrlRaises:
    """§3.5 no-silent-fallback — http transport with no url is exit 2."""

    def test_http_without_url_raises_click_usage_error(
        self, clean_mcp_env: None
    ) -> None:
        from agent_brain_cli.config import resolve_mcp_transport

        with pytest.raises(click.UsageError) as exc_info:
            resolve_mcp_transport(mcp_transport_hint="http", mcp_url_override=None)
        # Phase 58 swapped Phase 57's placeholder for the verbatim v3
        # design doc §3.5 wording. With no state_dir passed (defensive
        # branch), the literal "<state_dir>" placeholder appears in the
        # error message.
        msg = str(exc_info.value)
        assert "discovery file not found at" in msg
        assert "run 'agent-brain mcp start' or pass --mcp-url" in msg


# Sanity assertion: the helper must read from os.environ at call time,
# not at import time (so monkeypatch.setenv works inside the test).
def test_helper_reads_env_at_call_time(
    clean_mcp_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agent_brain_cli.config import resolve_mcp_transport

    # First call: nothing set → stdio.
    transport, target = resolve_mcp_transport(mcp_transport_hint=None)
    assert transport == "stdio"
    assert target is None

    # Now set env → next call honors it.
    monkeypatch.setenv("AGENT_BRAIN_MCP_TRANSPORT", "http")
    monkeypatch.setenv("AGENT_BRAIN_MCP_URL", "http://x/mcp")
    transport, target = resolve_mcp_transport(mcp_transport_hint=None)
    assert transport == "http"
    assert target == "http://x/mcp"
    # Sanity: os.environ unchanged side-effect-wise.
    assert os.environ.get("AGENT_BRAIN_MCP_TRANSPORT") == "http"
