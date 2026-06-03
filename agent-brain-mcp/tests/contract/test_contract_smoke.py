"""Phase 55 Plan 01 smoke test — proves the contract fixture chain works.

ONE test only. Plans 02 (16-tool matrix, VAL-01), 03 (subscription
lifecycle, VAL-02), and 04 (HTTP transport, VAL-03) own the substantive
contract assertions; this module exists ONLY to prove that
``mcp_stdio_session()`` successfully spawns a fake-backed
``agent-brain-mcp`` subprocess, completes the MCP initialize handshake,
and tears down cleanly via the D-17 orphan-scan contract.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import pytest
from mcp import ClientSession


@pytest.mark.contract
@pytest.mark.asyncio
async def test_initialize_over_stdio(
    mcp_stdio_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """Initialize against the fake-backed contract subprocess.

    Asserts the MCP wire handshake completes AND that
    ``serverInfo.name`` matches the v1/v2 brand string ``agent-brain``.
    Any wire-level regression (SDK version drift, capability
    negotiation failure, subprocess crash on startup) surfaces here
    before Plans 02/03/04 even try to exercise tools / resources.
    """
    async with mcp_stdio_session() as session:
        result = await session.initialize()
        assert result.serverInfo.name == "agent-brain"
