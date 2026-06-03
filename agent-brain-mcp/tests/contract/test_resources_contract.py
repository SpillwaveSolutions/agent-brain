"""Phase 55 Plan 02 — Layer 2 SDK-driven resources contract suite (VAL-01).

Covers the resources-side of the MCP wire protocol that Plan 02's tool
suite does not touch:

* :func:`test_resources_templates_list_advertises_four_uri_schemes` —
  ``resources/templates/list`` returns the four RFC 6570 templates
  pinned in Phase 51 CONTEXT decision B (``chunk://``,
  ``graph-entity://``, ``job://``, ``file://``).
* :func:`test_resources_list_includes_v1_static_corpus_uris` —
  ``resources/list`` returns at least the five v1 ``corpus://``
  resources (config / status / health / providers / folders).
* :func:`test_resources_read_chunk` — ``resources/read chunk://chunk_001``
  round-trips a ChunkRecord JSON body.
* :func:`test_resources_read_graph_entity` —
  ``resources/read graph-entity://Function/foo`` round-trips a
  GraphEntityRecord JSON body.
* :func:`test_resources_read_job` — ``resources/read job://job_abc``
  round-trips a JobDetailResponse.
* :func:`test_resources_read_file` — ``resources/read file://...``
  round-trips a real on-disk read, with the contract test injecting a
  tmp folder via ``response_overrides`` so the file's parent is on the
  sandbox allowlist (per Phase 51 Plan 03 dynamic-roots refresh).

Templates list pins the **exact** Phase 51 CONTEXT decision B strings
because once published, MCP client libraries lock onto them and
changes are breaking (see ``test_e2e_templates_list_and_read_all_schemes``
in ``tests/test_e2e_stdio.py`` for the in-tree precedent).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path

import pytest
from mcp import ClientSession
from pydantic import AnyUrl

# v1 corpus:// URIs (5 — see ``agent_brain_mcp.resources.corpus``)
_V1_STATIC_CORPUS_URIS: frozenset[str] = frozenset(
    {
        "corpus://config",
        "corpus://status",
        "corpus://health",
        "corpus://providers",
        "corpus://folders",
    }
)

# RFC 6570 template strings pinned in Phase 51 CONTEXT decision B.
# Forward-compat commitment — MCP client libraries lock onto these
# strings once published.
_EXPECTED_URI_TEMPLATES: frozenset[str] = frozenset(
    {
        "chunk://{chunk_id}",
        "graph-entity://{type}/{id}",
        "job://{job_id}",
        "file://{+path}",
    }
)


@pytest.mark.contract
@pytest.mark.asyncio
async def test_resources_templates_list_advertises_four_uri_schemes(
    mcp_stdio_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``resources/templates/list`` returns exactly the four Phase 51 templates.

    Asserts the exact ``uriTemplate`` strings (not just the schemes)
    because Phase 51 CONTEXT decision B locks the strings as a
    forward-compatibility commitment — any drift here breaks MCP
    clients that locked onto the v10.2.0 advertised set.
    """
    async with mcp_stdio_session() as session:
        await session.initialize()
        templates_result = await session.list_resource_templates()
        advertised = {t.uriTemplate for t in templates_result.resourceTemplates}
        assert advertised == _EXPECTED_URI_TEMPLATES, (
            "resources/templates/list drifted from Phase 51 CONTEXT decision B. "
            f"advertised={sorted(advertised)}, "
            f"expected={sorted(_EXPECTED_URI_TEMPLATES)}"
        )

        # MimeType pins: 3 JSON-backed schemes + file:// = None
        # (per-read sniff). Mirrors the v1 templates-list e2e pin in
        # tests/test_e2e_stdio.py::test_e2e_templates_list_and_read_all_schemes.
        by_template = {
            t.uriTemplate: t.mimeType for t in templates_result.resourceTemplates
        }
        assert by_template["chunk://{chunk_id}"] == "application/json"
        assert by_template["graph-entity://{type}/{id}"] == "application/json"
        assert by_template["job://{job_id}"] == "application/json"
        assert by_template["file://{+path}"] is None


@pytest.mark.contract
@pytest.mark.asyncio
async def test_resources_list_includes_v1_static_corpus_uris(
    mcp_stdio_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``resources/list`` advertises every v1 ``corpus://`` URI.

    The v2 surface preserved all five v1 static URIs (CONTEXT decision
    A). Catching a regression here means a v2 plan dropped a v1
    resource by accident.
    """
    async with mcp_stdio_session() as session:
        await session.initialize()
        result = await session.list_resources()
        advertised = {str(r.uri) for r in result.resources}
        missing = _V1_STATIC_CORPUS_URIS - advertised
        assert not missing, (
            f"resources/list missing v1 corpus URIs: {sorted(missing)}. "
            f"advertised={sorted(advertised)}"
        )


@pytest.mark.contract
@pytest.mark.asyncio
async def test_resources_read_chunk(
    mcp_stdio_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``resources/read chunk://chunk_001`` round-trips the ChunkRecord body."""
    async with mcp_stdio_session() as session:
        await session.initialize()
        result = await session.read_resource(AnyUrl("chunk://chunk_001"))
        assert (
            len(result.contents) == 1
        ), f"chunk:// returned {len(result.contents)} contents, expected 1"
        content = result.contents[0]
        # SDK exposes the text body on ``.text`` for application/json reads.
        body = json.loads(content.text)  # type: ignore[union-attr]
        assert body["chunk_id"] == "chunk_001"
        assert body["language"] == "python"
        assert body["source"] == "/tmp/test/file.py"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_resources_read_graph_entity(
    mcp_stdio_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``resources/read graph-entity://Function/foo`` round-trips entity + 1-hop."""
    async with mcp_stdio_session() as session:
        await session.initialize()
        result = await session.read_resource(AnyUrl("graph-entity://Function/foo"))
        assert len(result.contents) == 1
        body = json.loads(result.contents[0].text)  # type: ignore[union-attr]
        assert body["entity"]["type"] == "Function"
        assert body["entity"]["id"] == "foo"
        # 1-hop neighbors stub is non-empty per _DEFAULT_RESPONSES.
        assert len(body["neighbors"]["incoming"]) >= 1
        assert len(body["neighbors"]["outgoing"]) >= 1


@pytest.mark.contract
@pytest.mark.asyncio
async def test_resources_read_job(
    mcp_stdio_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
) -> None:
    """``resources/read job://job_abc`` round-trips the JobDetailResponse."""
    async with mcp_stdio_session() as session:
        await session.initialize()
        result = await session.read_resource(AnyUrl("job://job_abc"))
        assert len(result.contents) == 1
        body = json.loads(result.contents[0].text)  # type: ignore[union-attr]
        assert body["job_id"] == "job_abc"
        # status is "running" per _DEFAULT_RESPONSES ("GET",
        # "/index/jobs/job_abc").
        assert body["status"] == "running"


@pytest.mark.contract
@pytest.mark.asyncio
async def test_resources_read_file(
    mcp_stdio_session: Callable[..., AbstractAsyncContextManager[ClientSession]],
    tmp_path: Path,
) -> None:
    """``resources/read file://<abs-path>`` round-trips a real on-disk read.

    The fake backend's default ``GET /index/folders/`` reports
    ``/tmp/test`` as the only indexed root. ``file://`` reads outside
    indexed roots are denied per Phase 51 Plan 03's sandbox helper
    (CONTEXT decision E — dynamic roots refresh on every read). For
    this contract test we override ``/index/folders/`` to advertise
    ``tmp_path`` as the indexed root, then write a real file there and
    read it via the SDK.
    """
    # Write a real file inside the tmp sandbox so the file:// handler
    # can actually read bytes off disk.
    sandbox_file = tmp_path / "contract.txt"
    sandbox_file.write_text("hello from the contract suite\n", encoding="utf-8")

    response_overrides = {
        ("GET", "/index/folders/"): {
            "folders": [
                {
                    "folder_path": str(tmp_path),
                    "chunk_count": 1,
                    "last_indexed": "2026-06-03T00:00:00Z",
                    "watch_mode": "off",
                    "watch_debounce_seconds": 30,
                }
            ]
        }
    }

    async with mcp_stdio_session(response_overrides=response_overrides) as session:
        await session.initialize()
        result = await session.read_resource(AnyUrl(f"file://{sandbox_file}"))
        assert len(result.contents) == 1
        # text/* MIME -> .text carries the body; binary -> .blob.
        assert result.contents[0].text == "hello from the contract suite\n"  # type: ignore[union-attr]
