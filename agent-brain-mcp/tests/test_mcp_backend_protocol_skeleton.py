"""Architectural-boundary pinning for the ``McpBackend`` Protocol
(Phase 59 Plan 01 — wired by Phase 59 Plan 02).

Sibling to ``test_cli_backends_skeleton.py`` — that file pins
``BackendClient`` (the tools surface introduced in Plan 56-02);
this file pins ``McpBackend`` (the prompts + resources surface
introduced in Plan 59-01, wired in Plan 59-02).

Three architectural pins survive Plan 02 unchanged:

1. ``McpStdioBackend`` structurally satisfies ``McpBackend``.
2. ``McpHttpBackend`` structurally satisfies ``McpBackend``.
3. ``DocServeClient`` does NOT satisfy ``McpBackend`` — the
   load-bearing negative case. UDS/HTTP transports cannot speak MCP
   prompts/resources by design; this assertion makes the boundary
   explicit and survives Phase 60+ refactors.

A parametrized "sentinel-gone" pin: every previously-skeleton method
body on both backends now raises ANY exception OTHER than the
Plan 59-01 sentinel ``NotImplementedError("Wired in Phase 59 Plan
02")``. Plan 02 wired the bodies; this pin proves the swap happened.
The expected runtime error on a dummy backend is a real SDK
connection failure (or similar), surfaced here as the negation of
the obsolete sentinel.
"""

from __future__ import annotations

import pytest
from agent_brain_cli.client import DocServeClient
from agent_brain_cli.client.protocol import McpBackend

from agent_brain_mcp.client import McpHttpBackend, McpStdioBackend

# The Plan 59-01 sentinel literal — Plan 59-02 removes this from every
# method body. Kept here as the negative-case anchor so a regression
# (someone reverting the wires) trips this test immediately.
PLAN_59_01_SENTINEL: str = "Wired in Phase 59 Plan 02"


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
def test_mcp_backend_methods_no_longer_raise_plan_59_01_sentinel(
    backend: McpBackend,
) -> None:
    """Every Phase 59 method body on both backends MUST NOT raise the
    Plan 59-01 ``NotImplementedError`` sentinel anymore.

    Plan 02 replaces each skeleton with a real wire — the bodies now
    attempt an actual MCP SDK round-trip. Against the dummy backends
    constructed here (bogus stdio command + unreachable HTTP URL), the
    real wires raise SDK connection failures (httpx.ConnectError,
    BrokenPipeError, FileNotFoundError, etc. — sometimes wrapped in
    ExceptionGroup / BaseExceptionGroup from anyio). The negation
    contract: whatever exception bubbles up, it MUST NOT be the
    Plan 59-01 sentinel string.

    Coverage is 10 calls (5 methods × 2 backends) — same surface
    pinned by the original Plan 59-01 skeleton-conformance test;
    Plan 59-02 inverts the assertion now that the bodies are wired.
    """
    method_calls = [
        ("get_prompt", lambda b: b.get_prompt("any")),
        ("list_prompts", lambda b: b.list_prompts()),
        ("list_resources", lambda b: b.list_resources()),
        ("list_resource_templates", lambda b: b.list_resource_templates()),
        ("read_resource", lambda b: b.read_resource("any://x")),
    ]
    for method_name, call in method_calls:
        with pytest.raises(BaseException) as exc_info:
            call(backend)
        # Whatever bubbles up — connection error, BaseExceptionGroup,
        # subprocess error — it MUST NOT be the obsolete Plan 59-01
        # sentinel. (str() on BaseExceptionGroup recursively includes
        # all sub-exception messages — that's the right surface to
        # check; a sentinel reappearing as a re-raised
        # NotImplementedError would surface here.)
        rendered = str(exc_info.value)
        assert PLAN_59_01_SENTINEL not in rendered, (
            f"{method_name} on {type(backend).__name__} still raises "
            f"the Plan 59-01 sentinel — Plan 02 wire never landed."
        )
