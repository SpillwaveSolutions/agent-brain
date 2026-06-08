"""Skeleton conformance + architectural-boundary pinning for the new
``McpBackend`` Protocol (Phase 59 Plan 01).

Sibling to ``test_cli_backends_skeleton.py`` — that file pins
``BackendClient`` (the tools surface introduced in Plan 56-02);
this file pins ``McpBackend`` (the prompts + resources surface
introduced in Plan 59-01).

Three architectural pins:

1. ``McpStdioBackend`` structurally satisfies ``McpBackend``.
2. ``McpHttpBackend`` structurally satisfies ``McpBackend``.
3. ``DocServeClient`` does NOT satisfy ``McpBackend`` — the
   load-bearing negative case. UDS/HTTP transports cannot speak MCP
   prompts/resources by design; this assertion makes the boundary
   explicit and survives Phase 60+ refactors.

Plus a parametrized sentinel assertion: every skeleton method body on
both backends raises ``NotImplementedError("Wired in Phase 59 Plan 02")``
verbatim. Plan 59-02 greps for that exact string before replacing each
body, so a drift here would silently de-couple the skeletons from the
wire plan.
"""

from __future__ import annotations

import pytest
from agent_brain_cli.client import DocServeClient
from agent_brain_cli.client.protocol import McpBackend

from agent_brain_mcp.client import McpHttpBackend, McpStdioBackend

SKELETON_SENTINEL: str = "Wired in Phase 59 Plan 02"


def test_mcp_stdio_backend_satisfies_mcp_backend_protocol() -> None:
    backend = McpStdioBackend(command="agent-brain-mcp")
    assert isinstance(backend, McpBackend), (
        "McpStdioBackend must structurally satisfy McpBackend — "
        "Phase 59 Plan 01 architectural contract."
    )


def test_mcp_http_backend_satisfies_mcp_backend_protocol() -> None:
    backend = McpHttpBackend(url="http://127.0.0.1:9999/mcp")
    assert isinstance(backend, McpBackend), (
        "McpHttpBackend must structurally satisfy McpBackend — "
        "Phase 59 Plan 01 architectural contract."
    )


def test_doc_serve_client_does_not_satisfy_mcp_backend() -> None:
    """Load-bearing negative case: the architectural boundary.

    UDS/HTTP transports do NOT speak MCP prompts/resources. The split
    between :class:`BackendClient` (tools surface — DocServeClient
    satisfies) and :class:`McpBackend` (prompts+resources surface —
    DocServeClient does NOT satisfy) is the Phase 59 CONTEXT decision.
    If this test starts passing, somebody bolted MCP-only methods onto
    DocServeClient — revert.
    """
    client = DocServeClient(base_url="http://127.0.0.1:8000")
    assert not isinstance(client, McpBackend), (
        "DocServeClient must NOT satisfy McpBackend — the architectural "
        "boundary between tools surface (BackendClient) and prompts+"
        "resources surface (McpBackend) is intentional and load-bearing."
    )


_BACKEND_INSTANCES = [
    pytest.param(
        McpStdioBackend(command="dummy"),
        id="McpStdioBackend",
    ),
    pytest.param(
        McpHttpBackend(url="http://127.0.0.1:9999/mcp"),
        id="McpHttpBackend",
    ),
]


@pytest.mark.parametrize("backend", _BACKEND_INSTANCES)
def test_mcp_backend_skeleton_methods_raise_with_sentinel(
    backend: McpBackend,
) -> None:
    """Every skeleton method raises ``NotImplementedError`` with the
    verbatim Phase 59 Plan 02 sentinel.

    Plan 59-02 greps for the exact literal ``"Wired in Phase 59 Plan 02"``
    before replacing each method body with a real wire implementation —
    a drift in this string (extra period, paraphrase, wrong plan
    number) silently breaks the swap-in pattern.

    Method names and safe dummy args come from the ``McpBackend``
    Protocol signature; coverage is 10 calls (5 methods × 2 backends).
    """
    with pytest.raises(NotImplementedError) as exc_info:
        backend.get_prompt("any")
    assert str(exc_info.value) == SKELETON_SENTINEL

    with pytest.raises(NotImplementedError) as exc_info:
        backend.list_prompts()
    assert str(exc_info.value) == SKELETON_SENTINEL

    with pytest.raises(NotImplementedError) as exc_info:
        backend.list_resources()
    assert str(exc_info.value) == SKELETON_SENTINEL

    with pytest.raises(NotImplementedError) as exc_info:
        backend.list_resource_templates()
    assert str(exc_info.value) == SKELETON_SENTINEL

    with pytest.raises(NotImplementedError) as exc_info:
        backend.read_resource("any://x")
    assert str(exc_info.value) == SKELETON_SENTINEL
