"""Phase 55 Plan 04 — Streamable HTTP transport contract suite (VAL-03).

Drives the Streamable HTTP MCP transport end-to-end via the official MCP
Python SDK's :func:`mcp.client.streamable_http.streamablehttp_client` to
confirm that ``agent-brain-mcp --transport http`` serves the full
initialize → tools/list → tools/call → resources/list → resources/read
flow correctly. The first usage of ``streamablehttp_client`` in the
contract suite (Phase 53 Plan 03 used it under the ``e2e_http`` marker;
Plan 04 introduces a parallel ``contract``-marked HTTP fixture).

Per Phase 55 CONTEXT D-09 / D-10:

* The fake-server subprocess (Phase 53's ``fake_mcp_http_server.py``)
  wires :func:`agent_brain_mcp.server.build_server` to an in-memory
  :class:`httpx.MockTransport` backend so the suite stays under the
  per-test budget without standing up a real ``agent-brain-serve``.
* Loopback-only enforcement (``--host 0.0.0.0`` rejection) and
  ``--transport`` rejection are verified by Phase 53's own tests
  (D-10) — Plan 04 only asserts the happy path works via the SDK.

Per Phase 55 CONTEXT D-11:

* Free port allocation lives in ``free_loopback_port`` (TCP socket
  bind + release on ``("127.0.0.1", 0)``) so the suite never
  collides with multi-instance Agent Brain servers a developer may
  have running locally.

The 5 wire-protocol assertions parallel Plan 02's stdio-transport
tools/resources matrix at a coarser level — Plan 04 is NOT a 16-tool
matrix duplicate but a transport-equivalence proof that the same v1
and v2 surface (tool count, resource list, resource read) round-trips
correctly via the SDK HTTP client.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

import pytest
from mcp import ClientSession
from pydantic import AnyUrl

# Phase 54 + Phase 55 Plan 02 lock the 16-tool surface (7 v1 + 9 v2).
# Plan 04's transport-equivalence proof asserts the same count surfaces
# over HTTP — drift here indicates a v2 plan broke tool registration on
# one transport but not the other.
_EXPECTED_TOOL_COUNT: int = 16

# The five v1 static ``corpus://`` resources. Mirrors
# :data:`tests.contract.test_resources_contract._V1_STATIC_CORPUS_URIS`
# verbatim — duplicated rather than imported to keep this module's
# import surface narrow (Plan 04 has no other dependency on Plan 02's
# resources test module).
_V1_STATIC_CORPUS_URIS: frozenset[str] = frozenset(
    {
        "corpus://config",
        "corpus://status",
        "corpus://health",
        "corpus://providers",
        "corpus://folders",
    }
)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_http_initialize(
    mcp_http_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``initialize`` over HTTP returns ``serverInfo.name == 'agent-brain'``.

    Asserts the SDK handshake completes end-to-end and the server
    advertises the three v2 capability axes the rest of the surface
    depends on (tools, resources, prompts). Drift on any capability
    here means a v2 plan accidentally narrowed the server's advertised
    feature set when the HTTP listener was wired up.
    """
    async with mcp_http_session() as session:
        result = await session.initialize()
        assert (
            result.serverInfo.name == "agent-brain"
        ), f"expected serverInfo.name == 'agent-brain'; got {result.serverInfo.name!r}"
        # Tools / resources / prompts capabilities must be advertised —
        # the full v2 surface (16 tools, 5 corpus URIs + 4 templates, 6
        # prompts) depends on all three being present.
        assert (
            result.capabilities.tools is not None
        ), "HTTP initialize did not advertise tools capability"
        assert (
            result.capabilities.resources is not None
        ), "HTTP initialize did not advertise resources capability"
        assert (
            result.capabilities.prompts is not None
        ), "HTTP initialize did not advertise prompts capability"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_http_tools_list_returns_16(
    mcp_http_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``tools/list`` over HTTP returns the full 16-tool v2 surface.

    Phase 54 closes the 16-tool surface (7 v1 + 9 v2). Plan 02
    (stdio transport) already pins the count; this test asserts the
    HTTP transport sees the same 16 tools — transport-equivalence
    guard.
    """
    async with mcp_http_session() as session:
        await session.initialize()
        result = await session.list_tools()
        assert len(result.tools) == _EXPECTED_TOOL_COUNT, (
            f"tools/list over HTTP returned {len(result.tools)} tools; "
            f"v2 surface is {_EXPECTED_TOOL_COUNT} (7 v1 + 9 v2). "
            f"got names={sorted(t.name for t in result.tools)}"
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_http_tool_call_smoke(
    mcp_http_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``tools/call server_health`` over HTTP returns content + structuredContent.

    ``server_health`` is the safest read-only tool to smoke-test
    end-to-end: zero args, no mutation, deterministic stub response
    from the fake-server's ``GET /health/`` route. Asserts the SDK
    HTTP transport correctly:

    * dispatches the call to the registered handler;
    * unwraps the ``TextContent`` from ``content[0]``;
    * surfaces the ``structuredContent`` dict per the MCP 2024-11-05
      spec (and v2 design doc §3.2 dual-shape contract).
    """
    async with mcp_http_session() as session:
        await session.initialize()
        result = await session.call_tool("server_health", {})
        assert result.content, "call_tool('server_health') returned empty content"
        assert (
            result.content[0].type == "text"
        ), f"content[0].type expected 'text'; got {result.content[0].type!r}"
        assert isinstance(result.structuredContent, dict), (
            "structuredContent must be a dict per the dual-shape contract; "
            f"got {type(result.structuredContent).__name__}"
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_http_resources_list_includes_v1_static(
    mcp_http_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``resources/list`` over HTTP advertises every v1 ``corpus://`` URI.

    The v2 surface preserved all five v1 static URIs (Phase 55
    CONTEXT decision A). The HTTP transport must surface the SAME
    set as stdio — drift here means a v2 plan dropped a v1 resource
    on one transport but not the other.
    """
    async with mcp_http_session() as session:
        await session.initialize()
        result = await session.list_resources()
        advertised = {str(r.uri) for r in result.resources}
        missing = _V1_STATIC_CORPUS_URIS - advertised
        assert not missing, (
            f"resources/list over HTTP missing v1 corpus URIs: "
            f"{sorted(missing)}. advertised={sorted(advertised)}"
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_http_resources_read_corpus_config(
    mcp_http_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``resources/read corpus://config`` over HTTP returns valid JSON.

    Round-trips a real corpus config read through the SDK HTTP client.
    Asserts:

    * ``contents[0].mimeType == "application/json"`` — the corpus
      handlers all surface JSON per Phase 51 CONTEXT decision A;
    * ``contents[0].text`` parses cleanly as JSON — protects against
      transport-layer body corruption (encoding mismatch, gzip
      misframing, chunked-transfer truncation).

    The fake-server backend stubs ``GET /health/config`` (read by the
    ``corpus://config`` resource handler) per
    :data:`tests.conftest._FAKE_HTTP_SERVER_SCRIPT`.
    """
    async with mcp_http_session() as session:
        await session.initialize()
        result = await session.read_resource(AnyUrl("corpus://config"))
        assert result.contents, "resources/read corpus://config returned empty contents"
        content = result.contents[0]
        assert content.mimeType == "application/json", (
            f"corpus://config mimeType expected 'application/json'; "
            f"got {content.mimeType!r}"
        )
        # ``.text`` is set on text-mode contents; type-ignore is needed
        # because the SDK union (TextResourceContents | BlobResource-
        # Contents) doesn't statically narrow on mimeType.
        body = json.loads(content.text)  # type: ignore[union-attr]
        # The stubbed body includes ``storage_backend`` (per
        # ``_FAKE_HTTP_SERVER_SCRIPT``); a bare JSON-parse success is
        # enough to confirm the wire round-trip, but pinning one field
        # catches the degenerate case where the handler returned an
        # empty object.
        assert (
            "storage_backend" in body
        ), f"corpus://config body missing 'storage_backend': {body!r}"


@pytest.mark.contract
def test_http_mount_path_matches_production_constant() -> None:
    """Pin Plan 04's hard-coded ``_HTTP_MOUNT_PATH`` against production.

    The fixture's URL is constructed as
    ``http://{host}:{port}{_HTTP_MOUNT_PATH}`` — if the production
    constant ever drifts (e.g., a v3 plan changes the mount to
    ``/v2/mcp``), the fixture would silently 404 on every test. This
    sanity check catches the drift at collection time so the
    transport-contract suite fails loudly instead of vaguely.

    Not marked async: pure equality assertion, no SDK chain needed.
    """
    from agent_brain_mcp.http import MCP_MOUNT_PATH
    from tests.contract.conftest import _HTTP_MOUNT_PATH

    assert _HTTP_MOUNT_PATH == MCP_MOUNT_PATH, (
        f"Plan 04 fixture hard-coded mount path {_HTTP_MOUNT_PATH!r} "
        f"drifted from production constant {MCP_MOUNT_PATH!r}. Update "
        "tests/contract/conftest.py::_HTTP_MOUNT_PATH or revert the "
        "production change."
    )
