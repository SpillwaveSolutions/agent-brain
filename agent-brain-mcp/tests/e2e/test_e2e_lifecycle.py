"""Phase 4 E2E: subprocess lifecycle + no-orphan-procs.

These tests guard against the failure modes that unit/integration tests
can't see: stale sockets after SIGKILL, orphan child processes after
parent exit, signal handling under load.
"""

from __future__ import annotations

import pytest


def test_sigterm_cleans_up_socket_and_no_orphans(
    indexed_server: dict[str, object],
) -> None:
    """SIGTERM the server → socket is unlinked, no orphan agent-brain-serve."""
    pytest.skip("Phase 4 implementation pending.")


def test_sigkill_leaves_stale_socket_that_next_start_clears(
    indexed_server: dict[str, object],
) -> None:
    """SIGKILL leaves the socket file. Restarting the server unlinks the
    stale socket cleanly and rebinds (matches plan §6.2 stale-cleanup behavior)."""
    pytest.skip(
        "Phase 5 implementation pending — integration variant in "
        "agent-brain-server/tests/integration/test_uds_orphan_cleanup.py."
    )


def test_mcp_client_close_leaves_no_orphan_agent_brain_mcp(
    mcp_client: object,
) -> None:
    """After the MCP client closes its stdio session, the agent-brain-mcp
    subprocess must exit within 5s (no zombies). Verified via ``pgrep -f
    agent-brain-mcp``."""
    pytest.skip("Phase 4 implementation pending.")
