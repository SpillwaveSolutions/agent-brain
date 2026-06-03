"""Phase 53 Plan 03: HTTP-02 loopback bind verification via psutil.

While Plan 02's :mod:`agent_brain_mcp.http` validates the ``--host``
value BEFORE binding (the contract message rejection at
``validate_loopback_host``), Plan 03 closes the loop by inspecting
the actual TCP socket the subprocess bound. ``psutil.Process(pid)
.net_connections(kind="tcp")`` filtered to ``LISTEN`` state reveals
the real bound interface — if a regression sneaks the listener onto
``0.0.0.0`` or a non-loopback NIC, this test fails loudly.

Marked ``e2e_http`` — spawns a real MCP HTTP subprocess. Skipped on
Windows because :meth:`psutil.Process.net_connections` returns no
results for foreign processes there without elevated privileges.
"""

from __future__ import annotations

import sys
from typing import Any

import psutil
import pytest

# Module-level marker so the test is opt-in (subprocess + uvicorn).
pytestmark = pytest.mark.e2e_http


# psutil's net_connections on Windows requires admin for foreign procs;
# the agent-brain-mcp dev/CI matrix is macOS + linux only.
_REQUIRES_PSUTIL_NET_CONNECTIONS = sys.platform != "win32"


@pytest.mark.skipif(
    not _REQUIRES_PSUTIL_NET_CONNECTIONS,
    reason="psutil.Process.net_connections needs elevated privileges on Windows.",
)
def test_http_listener_bound_to_loopback_only(
    mcp_http_subprocess: Any, free_loopback_port: int
) -> None:
    """The bound TCP socket reports a loopback ``laddr.ip`` (127.0.0.1 or ::1).

    Plan 02 enforces this with a startup-time host whitelist; Plan 03
    independently verifies the actual kernel-level bind. Both layers
    must agree — drift between them would be a silent regression
    against HTTP-02.
    """
    with mcp_http_subprocess() as proc:
        p = psutil.Process(proc.pid)
        # Filter to LISTEN-state TCP sockets — excludes the outbound
        # backend httpx connections that the MCP server might open
        # against agent-brain-serve.
        listening = [
            c for c in p.net_connections(kind="tcp") if c.status == psutil.CONN_LISTEN
        ]
        assert listening, (
            f"agent-brain-mcp HTTP subprocess (pid={proc.pid}) reports no "
            f"LISTEN-state TCP sockets — listener may have died or never "
            f"bound."
        )
        loopback_ips = {"127.0.0.1", "::1"}
        for conn in listening:
            ip = conn.laddr.ip
            assert ip in loopback_ips, (
                f"HTTP listener bound to non-loopback interface "
                f"{conn.laddr.ip}:{conn.laddr.port} — HTTP-02 violated. "
                f"Allowed loopback IPs: {sorted(loopback_ips)}."
            )

        # Sanity: at least one of the LISTEN sockets should be the port
        # we asked the subprocess to bind. (uvicorn may bind one or two
        # sockets depending on platform / ipv6 support; we just need to
        # confirm OUR port is in the list to prove the subprocess we're
        # inspecting is the right one.)
        ports = {c.laddr.port for c in listening}
        assert free_loopback_port in ports, (
            f"agent-brain-mcp did NOT bind the requested port "
            f"{free_loopback_port}; observed LISTEN ports: {sorted(ports)}"
        )
