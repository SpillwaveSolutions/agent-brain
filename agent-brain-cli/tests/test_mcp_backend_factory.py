"""Tests pinning ``open_mcp_backend(ctx)`` — the Phase 59 MCP-only
backend factory.

Sibling to the existing ``open_backend(ctx) -> BackendClient`` dispatcher
in ``agent_brain_cli/client/transport.py``. The new factory returns an
``McpBackend`` (NOT a ``BackendClient``) and enforces the
``--transport mcp`` requirement as a single point of contract — every
MCP-only command (``agent-brain prompt``, ``agent-brain resources *``)
calls ``open_mcp_backend`` and inherits the UsageError surfacing for
free.

This file covers:

- Negative cases: ``transport_hint`` is not ``"mcp"`` (None, "auto",
  "http", "uds") → ``click.UsageError`` exit code 2.
- Positive case (stdio): returns an instance that satisfies the
  ``McpBackend`` Protocol; ``shutil.which("agent-brain-mcp")`` is
  mocked to a non-None path.
- Positive case (http): an explicit ``--mcp-url`` is honored and the
  factory returns an instance that satisfies ``McpBackend``.
- Missing binary case (stdio): when ``shutil.which`` returns None for
  ``agent-brain-mcp``, the factory raises ``click.UsageError`` with
  verbatim Phase 57 §3.5 wording.
- Skeleton sentinel reaches through the factory: ``open_mcp_backend``
  returns the real McpStdioBackend (not a stub), so
  ``backend.get_prompt("any")`` raises the Phase 59 Plan 02 sentinel.
"""

from __future__ import annotations

from unittest.mock import patch

import click
import pytest

from agent_brain_cli.client.protocol import McpBackend
from agent_brain_cli.client.transport import open_mcp_backend


def _make_ctx(**obj_overrides: object) -> click.Context:
    """Build a minimal Click context with the obj dict prepopulated.

    Mirrors the top-level Click group's ``ctx.obj`` shape: at minimum
    populates ``transport_hint`` and the MCP-axis keys
    (``mcp_transport_hint``, ``mcp_url_override``) so callers can vary
    a single axis at a time.
    """
    ctx = click.Context(click.Command("test"))
    base: dict[str, object] = {
        "transport_hint": "mcp",
        "mcp_transport_hint": "stdio",
        "mcp_url_override": None,
        "base_url_override": None,
        "socket_path_override": None,
        "debug_transport": False,
    }
    base.update(obj_overrides)
    ctx.obj = base
    return ctx


@pytest.mark.parametrize(
    "transport_hint",
    [None, "auto", "http", "uds"],
    ids=["none", "auto", "http", "uds"],
)
def test_open_mcp_backend_rejects_non_mcp_transport(
    transport_hint: str | None,
) -> None:
    """Without ``--transport mcp``, the factory MUST raise UsageError.

    Carries the Phase 57 §3.5 no-silent-fallback contract: MCP-only
    commands surface the missing-transport failure loudly with exit
    code 2; no auto-fallback to UDS/HTTP.
    """
    ctx = _make_ctx(transport_hint=transport_hint)
    with pytest.raises(click.UsageError) as exc_info:
        open_mcp_backend(ctx)
    # The message must include the "--transport mcp" pointer so the
    # operator can fix it without reading source.
    assert "--transport mcp" in str(exc_info.value)


def test_open_mcp_backend_accepts_mcp_stdio_returns_mcp_backend() -> None:
    """With ``--transport mcp --mcp-transport stdio`` and the binary on
    PATH, the factory returns an ``McpBackend``."""
    ctx = _make_ctx(transport_hint="mcp", mcp_transport_hint="stdio")
    with patch(
        "agent_brain_cli.client.transport.shutil.which",
        return_value="/usr/local/bin/agent-brain-mcp",
    ):
        backend = open_mcp_backend(ctx)
    assert isinstance(backend, McpBackend)


def test_open_mcp_backend_accepts_mcp_http_returns_mcp_backend() -> None:
    """With ``--transport mcp --mcp-transport http --mcp-url ...`` the
    factory returns an ``McpBackend``."""
    ctx = _make_ctx(
        transport_hint="mcp",
        mcp_transport_hint="http",
        mcp_url_override="http://127.0.0.1:9999/mcp",
    )
    backend = open_mcp_backend(ctx)
    assert isinstance(backend, McpBackend)


def test_open_mcp_backend_missing_agent_brain_mcp_raises_usage_error() -> None:
    """Stdio + missing binary on PATH → verbatim Phase 57 §3.5 wording.

    The wording is duplicated from ``open_backend`` to keep both
    factories surface the same error verbatim — operators copy-paste
    error strings into bug reports.
    """
    ctx = _make_ctx(transport_hint="mcp", mcp_transport_hint="stdio")
    with patch(
        "agent_brain_cli.client.transport.shutil.which",
        return_value=None,
    ):
        with pytest.raises(click.UsageError) as exc_info:
            open_mcp_backend(ctx)
    assert (
        str(exc_info.value) == "agent-brain-mcp not found on PATH; install "
        "agent-brain-mcp into the same Python environment"
    )


def test_open_mcp_backend_unimplemented_methods_still_raise() -> None:
    """The factory returns the real McpStdioBackend, NOT a stub.

    Proves the skeleton bodies from Task 2 reach the caller through
    the factory: ``backend.get_prompt("any")`` raises
    ``NotImplementedError`` with the Phase 59 Plan 02 sentinel.
    """
    ctx = _make_ctx(transport_hint="mcp", mcp_transport_hint="stdio")
    with patch(
        "agent_brain_cli.client.transport.shutil.which",
        return_value="/usr/local/bin/agent-brain-mcp",
    ):
        backend = open_mcp_backend(ctx)
    with pytest.raises(NotImplementedError) as exc_info:
        backend.get_prompt("any")
    assert str(exc_info.value) == "Wired in Phase 59 Plan 02"
