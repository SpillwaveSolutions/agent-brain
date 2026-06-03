"""Phase 55 Plan 02 — Layer 2 SDK-driven 16-tool contract tests (VAL-01).

Two parametrized tests x 16 tool entries = 32 contract assertions, each
spawned in its own fake-backed ``agent-brain-mcp`` subprocess via the
official MCP Python SDK client over stdio. This is the wire-protocol
correctness gate that the in-process Layer 1 suite
(:mod:`tests.test_each_tool`) cannot reach: the SDK enforces
``tools/list`` → ``tools/call`` round-trip framing, capability
negotiation, and JSON-RPC error code on the wire — exactly the
regressions Plan 01's smoke proved we can catch.

Test layout
-----------

* :func:`test_tool_happy_path` — for each tool: list_tools(), find by
  name, jsonschema-validate ``sample_arguments`` against the tool's
  ``inputSchema``, call_tool, assert ``content[0]`` is TextContent and
  ``structuredContent`` dict carries the ``expected_structured_keys``.
* :func:`test_tool_negative_args` — for each tool: call_tool with
  ``negative_arguments``, assert either ``CallToolResult.isError ==
  True`` OR a raised exception. Both shapes are MCP-spec conformant
  (the input-schema rejection branch may surface at the client SDK
  layer or at our handler depending on which fails first).

Backend
-------

Tests reuse the ``mcp_stdio_session`` factory from Plan 01's conftest.
The bundled fake-backend stubs (see ``tests/conftest.py``
``_DEFAULT_RESPONSES``) cover every happy-path call; no
``response_overrides`` are needed for the 16-row matrix because Plan 01
pre-extended ``_DEFAULT_RESPONSES`` with the v2 endpoint stubs.

Phase 55 CONTEXT D-02 / D-04 invariants honored:

* SDK is the client (``mcp.ClientSession``, not in-process handler
  invocation).
* Backend is in-memory MockTransport (NOT a live ``agent-brain-serve``).
* Each tool exercised through ``tools/list`` then ``tools/call`` — the
  wire-protocol path, not the registry lookup.
* ``jsonschema.validate`` proves the advertised ``inputSchema`` accepts
  the matrix's ``sample_arguments`` — catches accidental schema
  tightening that would break otherwise-valid clients.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import jsonschema
import pytest
from mcp import ClientSession, McpError

from tests.contract._tool_matrix import TOOLS, ToolCase


@pytest.mark.contract
@pytest.mark.asyncio
@pytest.mark.parametrize("case", TOOLS, ids=lambda c: c.name)
async def test_tool_happy_path(
    mcp_stdio_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
    case: ToolCase,
) -> None:
    """Each tool's happy-path invocation round-trips through SDK + fake backend.

    Validates four things end-to-end per row:

    1. Tool is listed in ``tools/list`` (catches registry drift / a
       handler that fails to register).
    2. The advertised ``inputSchema`` validates ``sample_arguments``
       (catches accidental schema tightening — sample_arguments here
       are the contract for valid MCP-side invocations).
    3. ``tools/call`` returns ``content[0]`` of MCP type ``text`` (the
       summary block).
    4. ``structuredContent`` is a dict that includes every key in
       ``expected_structured_keys`` (catches output-model breakage
       silently dropping required fields under
       ``exclude_none=False``).
    """
    async with mcp_stdio_session() as session:
        await session.initialize()

        tools_result = await session.list_tools()
        tool = next((t for t in tools_result.tools if t.name == case.name), None)
        assert (
            tool is not None
        ), f"{case.name}: not advertised in tools/list — registry drift?"

        # The advertised schema MUST accept the sample arguments.
        # jsonschema raises ValidationError on mismatch — surfacing it
        # here is more diagnostic than letting call_tool fail later.
        jsonschema.validate(case.sample_arguments, tool.inputSchema)

        result = await session.call_tool(case.name, case.sample_arguments)

        assert result.isError is False, (
            f"{case.name}: happy path returned isError=True. "
            f"content={result.content!r}"
        )
        assert result.content, f"{case.name}: call_tool returned no content blocks"
        assert result.content[0].type == "text", (
            f"{case.name}: first content block is not TextContent — "
            f"got {result.content[0].type!r}"
        )

        assert isinstance(result.structuredContent, dict), (
            f"{case.name}: structuredContent missing or not a dict — "
            f"got {type(result.structuredContent).__name__}"
        )
        for key in case.expected_structured_keys:
            assert key in result.structuredContent, (
                f"{case.name}: structuredContent missing required key "
                f"{key!r}. Got keys: {sorted(result.structuredContent.keys())}"
            )


@pytest.mark.contract
@pytest.mark.asyncio
@pytest.mark.parametrize("case", TOOLS, ids=lambda c: c.name)
async def test_tool_negative_args(
    mcp_stdio_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
    case: ToolCase,
) -> None:
    """Each tool's negative-arg invocation triggers a structured rejection.

    Both rejection shapes are MCP-spec conformant and we accept either:

    * ``CallToolResult.isError == True`` — the server-side handler ran
      ``model_validate`` and surfaced the failure as a tool-result
      error (Pydantic ``ValidationError`` → ``McpError`` →
      ``CallToolResult(isError=True)``; see
      ``server.call_tool`` ~line 287).
    * Raised :class:`McpError` — the SDK client converted a JSON-RPC
      error code response into an exception.

    The exact path depends on whether the SDK validates the
    ``inputSchema`` client-side before sending (1.12.x does NOT do
    client-side schema validation, so server-side rejection is the
    typical path) versus the server's ``model_validate`` raising. Both
    yield the same observable contract — the negative input was
    rejected.
    """
    async with mcp_stdio_session() as session:
        await session.initialize()

        try:
            result = await session.call_tool(case.name, case.negative_arguments)
        except McpError as exc:
            # Path B — SDK surfaced JSON-RPC error as exception.
            assert exc.error.code == case.expected_error_code, (
                f"{case.name}: raised McpError with code "
                f"{exc.error.code}, expected {case.expected_error_code}"
            )
            return

        # Path A — server returned a tool-result with isError=True.
        assert result.isError is True, (
            f"{case.name}: negative args were accepted (isError={result.isError!r}). "
            f"sample={case.negative_arguments!r}, "
            f"content={result.content!r}"
        )
