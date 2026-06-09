"""Skeleton conformance tests for the v3 CLI backends (Phase 56 Plan 03).

Pins the BackendClient Protocol conformance for McpStdioBackend and
McpHttpBackend BEFORE Phase 57 wires the actual MCP SDK calls. The
NotImplementedError pinning tests confirm Phase 57's transport
selector tests have a clear sentinel to grep for ("Wired in Phase 57+")
when distinguishing skeleton from real implementation.

Regression-pin: also re-asserts DocServeClient still satisfies
BackendClient after Plan 03 lands. Plan 02 added the same assertion in
agent-brain-cli; this duplicate in the MCP test tree catches the case
where Plan 03 accidentally broke the Protocol surface by editing
api_client.py instead of leaving it alone.
"""

from __future__ import annotations

from agent_brain_cli.client import DocServeClient
from agent_brain_cli.client.protocol import BackendClient

from agent_brain_mcp.client import McpHttpBackend, McpStdioBackend


def test_mcp_stdio_backend_satisfies_backend_client_protocol() -> None:
    backend = McpStdioBackend(command="agent-brain-mcp")
    assert isinstance(backend, BackendClient), (
        "McpStdioBackend must structurally satisfy BackendClient — " "Plan 02 contract."
    )


def test_mcp_http_backend_satisfies_backend_client_protocol() -> None:
    backend = McpHttpBackend(url="http://127.0.0.1:9999/mcp")
    assert isinstance(backend, BackendClient), (
        "McpHttpBackend must structurally satisfy BackendClient — " "Plan 02 contract."
    )


def test_doc_serve_client_still_satisfies_backend_client_protocol() -> None:
    """Regression-pin: Plan 03 must not have broken Plan 02's contract.

    DocServeClient (HTTP/UDS) must continue to structurally satisfy
    BackendClient after the v3 backends land. If this fails, Plan 03
    accidentally edited agent-brain-cli/.../api_client.py — which it
    must NOT do.
    """
    client = DocServeClient(base_url="http://127.0.0.1:8000")
    assert isinstance(client, BackendClient)


def test_context_manager_lifecycle_does_not_raise() -> None:
    """Skeleton ctx-mgr must work — Plan 03 specifically permits these
    three methods (__enter__, __exit__, close) to be real, not stubs."""
    with McpStdioBackend(command="dummy") as stdio:
        assert stdio is not None
    with McpHttpBackend(url="http://127.0.0.1:9999/mcp") as http:
        assert http is not None
