"""Phase 51 (URI-03): parameterized URI dispatcher + ``job://`` handler.

Mirrors :mod:`tests.test_resources_read` for the parameterized schemes.
Only ``job://`` cases are populated in Plan 51-01; Plans 51-02 and 51-03
extend this file (or add sibling modules) for the remaining schemes.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import mcp.types as types
import pytest
from mcp import McpError
from pydantic import AnyUrl

from agent_brain_mcp.errors import INVALID_PARAMS
from agent_brain_mcp.resources import (
    PARAMETERIZED_HANDLERS,
    PARAMETERIZED_SCHEMES,
    ParsedURI,
    parse_uri,
)
from agent_brain_mcp.server import build_server


async def _read(server, uri: str) -> str:
    handler = server.request_handlers[types.ReadResourceRequest]
    req = types.ReadResourceRequest(
        method="resources/read",
        params=types.ReadResourceRequestParams(uri=AnyUrl(uri)),
    )
    result = await handler(req)
    contents = result.root.contents
    assert len(contents) == 1
    return contents[0].text  # type: ignore[union-attr]


# --- parse_uri unit tests -------------------------------------------------


class TestParseUri:
    """Pure ``parse_uri`` behavior — no server, no httpx, no async."""

    @pytest.mark.parametrize(
        "uri,expected_id",
        [
            ("job://abc", "abc"),
            ("job://abc/", "abc"),  # trailing slash collapses
            ("job://job_abc-123", "job_abc-123"),
            ("job:abc", "abc"),  # RFC-correct no-slashes form
        ],
    )
    def test_job_uri_extracts_id(self, uri: str, expected_id: str) -> None:
        parsed = parse_uri(uri)
        assert parsed is not None
        assert parsed.scheme == "job"
        assert parsed.job_id == expected_id

    def test_job_uri_missing_id_raises_invalid_params(self) -> None:
        with pytest.raises(McpError) as ei:
            parse_uri("job://")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data == {"uri": "job://", "reason": "missing_job_id"}

    def test_corpus_uri_returns_none(self) -> None:
        # corpus:// is NOT a parameterized scheme — caller falls
        # through to RESOURCE_REGISTRY.
        assert parse_uri("corpus://config") is None

    def test_unknown_scheme_returns_none(self) -> None:
        assert parse_uri("mystery://abc") is None

    def test_parameterized_schemes_set_is_closed(self) -> None:
        # Defensive: if Plans 51-02/03 add new schemes, they must
        # extend this set (otherwise dispatch silently misroutes).
        assert PARAMETERIZED_SCHEMES == frozenset(
            {"chunk", "graph-entity", "job", "file"}
        )

    def test_handler_registry_covers_all_schemes(self) -> None:
        # Contract for Plans 51-02 and 51-03: the four scheme keys
        # exist (with NotImplementedError placeholders for now).
        assert set(PARAMETERIZED_HANDLERS.keys()) == PARAMETERIZED_SCHEMES


# --- end-to-end read_resource dispatch tests ------------------------------


class TestReadResourceJobUri:
    """End-to-end ``resources/read`` for ``job://<job_id>``."""

    @pytest.mark.asyncio
    async def test_read_job_uri_success(self, fake_httpx_client: httpx.Client) -> None:
        server = build_server(fake_httpx_client)
        body = await _read(server, "job://job_abc")
        data = json.loads(body)
        # Mirrors the JobDetailResponse from GET /index/jobs/<id>
        assert data["job_id"] == "job_abc"
        assert data["status"] == "running"
        assert data["progress_percent"] == 50.0

    @pytest.mark.asyncio
    async def test_read_job_uri_full_detail_passthrough(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # Decision F: read shape mirrors GET /index/jobs/<id> verbatim,
        # zero transformation. Asserts the full body round-trips.
        server = build_server(fake_httpx_client)
        body = await _read(server, "job://job_51_full")
        data = json.loads(body)
        assert data["job_id"] == "job_51_full"
        assert data["folder_path"] == "/tmp/repo"
        assert data["files_processed"] == 147
        assert data["files_total"] == 200

    @pytest.mark.asyncio
    async def test_read_job_uri_missing_id(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        with pytest.raises(McpError) as ei:
            await _read(server, "job://")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data == {"uri": "job://", "reason": "missing_job_id"}

    @pytest.mark.asyncio
    async def test_read_job_uri_404_refines_error_data(
        self,
        mock_client_factory: Callable[..., httpx.Client],
    ) -> None:
        # Decision D: 404 → INVALID_PARAMS, but the data blob is
        # refined with the scheme + job_id so MCP clients can route
        # the failure.
        client = mock_client_factory(
            responses={
                ("GET", "/index/jobs/nonexistent-uuid"): {
                    "detail": "Job not found",
                },
            },
            status_overrides={
                ("GET", "/index/jobs/nonexistent-uuid"): 404,
            },
        )
        server = build_server(client)
        with pytest.raises(McpError) as ei:
            await _read(server, "job://nonexistent-uuid")
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert isinstance(err.data, dict)
        assert err.data["scheme"] == "job"
        assert err.data["job_id"] == "nonexistent-uuid"
        assert err.data["httpStatus"] == 404
        assert "cause" in err.data

    @pytest.mark.asyncio
    async def test_read_job_uri_trailing_slash_normalized(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # job://job_abc/ should behave identically to job://job_abc.
        # The server strips the trailing slash from the URI before
        # parsing (read_resource: ``uri_str = str(uri).rstrip('/')``).
        server = build_server(fake_httpx_client)
        body = await _read(server, "job://job_abc/")
        data = json.loads(body)
        assert data["job_id"] == "job_abc"


# --- regression: existing corpus:// path unchanged ------------------------


class TestReadResourceFallThrough:
    """Regression: dispatcher must NOT break existing ``corpus://*``
    reads or the ``Unknown resource`` fallback."""

    @pytest.mark.asyncio
    async def test_read_corpus_uri_still_works(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # All 5 corpus:// resources continue to read correctly after
        # the dispatcher insertion.
        server = build_server(fake_httpx_client)
        for uri in (
            "corpus://config",
            "corpus://status",
            "corpus://health",
            "corpus://providers",
            "corpus://folders",
        ):
            body = await _read(server, uri)
            data = json.loads(body)
            assert isinstance(data, dict), f"corpus URI {uri} did not return dict"

    @pytest.mark.asyncio
    async def test_read_unknown_scheme_falls_through(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # mystery:// is not in PARAMETERIZED_SCHEMES, so parse_uri()
        # returns None, dispatch falls through to RESOURCE_REGISTRY,
        # which has no entry — final fallback raises 'Unknown resource'.
        server = build_server(fake_httpx_client)
        with pytest.raises(McpError) as ei:
            await _read(server, "mystery://abc")
        assert ei.value.error.code == INVALID_PARAMS
        assert "Unknown resource" in ei.value.error.message


# --- chunk:// end-to-end (Plan 51-02, URI-01) -----------------------------


class TestReadResourceChunkUri:
    """End-to-end ``resources/read`` for ``chunk://<chunk_id>``."""

    @pytest.mark.asyncio
    async def test_read_chunk_uri_success(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # Mirrors the ChunkRecord body from GET /query/chunk/{id}. The
        # MCP wrapper round-trips the full shape unchanged.
        server = build_server(fake_httpx_client)
        body = await _read(server, "chunk://chunk_001")
        data = json.loads(body)
        assert data["chunk_id"] == "chunk_001"
        assert data["parent_doc_id"] == "/tmp/test/file.py"
        assert data["source"] == "/tmp/test/file.py"
        assert "def hello()" in data["content"]
        assert data["summary"] == "Greets the world."
        assert data["language"] == "python"
        # Decision C: embedding is intentionally absent
        assert "embedding" not in data

    @pytest.mark.asyncio
    async def test_read_chunk_uri_missing_id(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        with pytest.raises(McpError) as ei:
            await _read(server, "chunk://")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data == {
            "uri": "chunk://",
            "reason": "missing_chunk_id",
        }

    @pytest.mark.asyncio
    async def test_read_chunk_uri_404_refines_error_data(
        self,
        mock_client_factory: Callable[..., httpx.Client],
    ) -> None:
        # Decision D: 404 → INVALID_PARAMS with data refined to include
        # scheme, chunk_id, httpStatus, cause so MCP clients can route.
        client = mock_client_factory(
            responses={
                ("GET", "/query/chunk/nonexistent"): {
                    "detail": {
                        "error": "chunk_not_found",
                        "chunk_id": "nonexistent",
                    }
                },
            },
            status_overrides={
                ("GET", "/query/chunk/nonexistent"): 404,
            },
        )
        server = build_server(client)
        with pytest.raises(McpError) as ei:
            await _read(server, "chunk://nonexistent")
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert isinstance(err.data, dict)
        assert err.data["scheme"] == "chunk"
        assert err.data["chunk_id"] == "nonexistent"
        assert err.data["httpStatus"] == 404
        assert "cause" in err.data


# --- graph-entity:// end-to-end (Plan 51-02, URI-02) ----------------------


class TestReadResourceGraphEntityUri:
    """End-to-end ``resources/read`` for ``graph-entity://<type>/<id>``."""

    @pytest.mark.asyncio
    async def test_read_graph_entity_uri_success(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # Mirrors GraphEntityRecord wire shape: entity + 1-hop neighbors.
        server = build_server(fake_httpx_client)
        body = await _read(server, "graph-entity://Function/foo")
        data = json.loads(body)
        assert data["entity"]["type"] == "Function"
        assert data["entity"]["id"] == "foo"
        assert data["entity"]["properties"]["module"] == "demo"
        # Both directions present even when empty.
        assert "incoming" in data["neighbors"]
        assert "outgoing" in data["neighbors"]
        assert len(data["neighbors"]["incoming"]) == 1
        assert data["neighbors"]["incoming"][0]["predicate"] == "calls"
        assert len(data["neighbors"]["outgoing"]) == 1
        assert data["neighbors"]["outgoing"][0]["type"] == "Class"

    @pytest.mark.asyncio
    async def test_read_graph_entity_uri_missing_type(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # graph-entity:// → missing both type and id, but the type check
        # fires first per the parser's order.
        server = build_server(fake_httpx_client)
        with pytest.raises(McpError) as ei:
            await _read(server, "graph-entity://")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data == {
            "uri": "graph-entity://",
            "reason": "missing_type",
        }

    @pytest.mark.asyncio
    async def test_read_graph_entity_uri_missing_id(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # graph-entity://Function → server.py strips one trailing slash
        # for normalization, then the parser sees no id segment.
        server = build_server(fake_httpx_client)
        with pytest.raises(McpError) as ei:
            await _read(server, "graph-entity://Function")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data == {
            "uri": "graph-entity://Function",
            "reason": "missing_id",
        }

    @pytest.mark.asyncio
    async def test_read_graph_entity_uri_trailing_slash_missing_id(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # graph-entity://Function/ — server.py strips the single trailing
        # slash → "graph-entity://Function" → missing_id surfaces.
        server = build_server(fake_httpx_client)
        with pytest.raises(McpError) as ei:
            await _read(server, "graph-entity://Function/")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data["reason"] == "missing_id"

    @pytest.mark.asyncio
    async def test_read_graph_entity_uri_id_with_embedded_slash(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        # Phase 50 decision B: entity ids may contain "/". The parser
        # treats everything after the type segment as the full id.
        server = build_server(fake_httpx_client)
        body = await _read(server, "graph-entity://Function/AuthService/login")
        data = json.loads(body)
        assert data["entity"]["id"] == "AuthService/login"

    @pytest.mark.asyncio
    async def test_read_graph_entity_uri_404_refines_error_data(
        self,
        mock_client_factory: Callable[..., httpx.Client],
    ) -> None:
        # Decision D: 404 → INVALID_PARAMS with scheme/entity_type/
        # entity_id/httpStatus/cause for client routing.
        client = mock_client_factory(
            responses={
                ("GET", "/graph/entity/Function/missing"): {
                    "detail": {
                        "error": "entity_not_found",
                        "type": "Function",
                        "id": "missing",
                    }
                },
            },
            status_overrides={
                ("GET", "/graph/entity/Function/missing"): 404,
            },
        )
        server = build_server(client)
        with pytest.raises(McpError) as ei:
            await _read(server, "graph-entity://Function/missing")
        err = ei.value.error
        assert err.code == INVALID_PARAMS
        assert isinstance(err.data, dict)
        assert err.data["scheme"] == "graph-entity"
        assert err.data["entity_type"] == "Function"
        assert err.data["entity_id"] == "missing"
        assert err.data["httpStatus"] == 404
        assert "cause" in err.data

    @pytest.mark.asyncio
    async def test_read_graph_entity_uri_503_graphrag_disabled(
        self,
        mock_client_factory: Callable[..., httpx.Client],
    ) -> None:
        # Phase 50 decision B / Phase 51 CONTEXT decision D: 503 from
        # the server's "graphrag_disabled" path surfaces as
        # SERVICE_INDEXING, refined with scheme + entity ids + a
        # ``reason`` slug extracted from the detail body.
        from agent_brain_mcp.errors import SERVICE_INDEXING

        client = mock_client_factory(
            responses={
                ("GET", "/graph/entity/Function/foo"): {
                    "detail": {
                        "error": "graphrag_disabled",
                        "hint": (
                            "set graphrag.enabled = true in config to "
                            "enable graph-entity addressing"
                        ),
                    }
                },
            },
            status_overrides={
                ("GET", "/graph/entity/Function/foo"): 503,
            },
        )
        server = build_server(client)
        with pytest.raises(McpError) as ei:
            await _read(server, "graph-entity://Function/foo")
        err = ei.value.error
        assert err.code == SERVICE_INDEXING
        assert isinstance(err.data, dict)
        assert err.data["scheme"] == "graph-entity"
        assert err.data["entity_type"] == "Function"
        assert err.data["entity_id"] == "foo"
        assert err.data["reason"] == "graphrag_disabled"
        assert err.data["httpStatus"] == 503

    @pytest.mark.asyncio
    async def test_read_graph_entity_uri_503_kuzu_unavailable(
        self,
        mock_client_factory: Callable[..., httpx.Client],
    ) -> None:
        # Phase 50 Plan 03 #178 SIGSEGV fallback: when Kuzu corrupts
        # the server returns 503 with detail.error == "kuzu_unavailable".
        # MCP must surface SERVICE_INDEXING with reason=kuzu_unavailable
        # so operators can route on it (distinct from "graphrag is off").
        from agent_brain_mcp.errors import SERVICE_INDEXING

        client = mock_client_factory(
            responses={
                ("GET", "/graph/entity/Function/foo"): {
                    "detail": {
                        "error": "kuzu_unavailable",
                        "hint": (
                            "Kuzu graph store raised during lookup "
                            "(issue #178). Set graphrag.store_type="
                            "simple in config until the Kuzu fix lands."
                        ),
                    }
                },
            },
            status_overrides={
                ("GET", "/graph/entity/Function/foo"): 503,
            },
        )
        server = build_server(client)
        with pytest.raises(McpError) as ei:
            await _read(server, "graph-entity://Function/foo")
        err = ei.value.error
        assert err.code == SERVICE_INDEXING
        assert isinstance(err.data, dict)
        assert err.data["reason"] == "kuzu_unavailable"


# --- placeholder schemes raise NotImplementedError ------------------------


class TestPlaceholderHandlers:
    """Plan 51-03 will replace the remaining ``file://`` placeholder.
    Until it ships, attempting to read that scheme raises
    ``NotImplementedError`` — not ``McpError``. This is intentional:
    callers should not be able to silently get an empty/None response
    for an unwired handler. Plans 51-01 and 51-02 have already swapped
    out their placeholders, so only ``file://`` remains here."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "uri",
        [
            "file:///tmp/foo.py",
        ],
    )
    async def test_placeholder_schemes_raise_not_implemented(
        self, fake_httpx_client: httpx.Client, uri: str
    ) -> None:
        server = build_server(fake_httpx_client)
        with pytest.raises(NotImplementedError):
            await _read(server, uri)


# --- parse_uri unit tests for chunk + graph-entity (Plan 51-02) -----------


class TestParseUriChunkAndGraphEntity:
    """Pure ``parse_uri`` behavior for the Plan 51-02 schemes."""

    @pytest.mark.parametrize(
        "uri,expected_id",
        [
            ("chunk://chunk_001", "chunk_001"),
            ("chunk://chunk_001/", "chunk_001"),  # trailing slash collapses
            ("chunk:chunk_001", "chunk_001"),  # RFC-correct no-slashes form
        ],
    )
    def test_chunk_uri_extracts_id(self, uri: str, expected_id: str) -> None:
        parsed = parse_uri(uri)
        assert parsed is not None
        assert parsed.scheme == "chunk"
        assert parsed.chunk_id == expected_id

    def test_chunk_uri_missing_id_raises_invalid_params(self) -> None:
        with pytest.raises(McpError) as ei:
            parse_uri("chunk://")
        assert ei.value.error.code == INVALID_PARAMS
        assert ei.value.error.data == {
            "uri": "chunk://",
            "reason": "missing_chunk_id",
        }

    def test_graph_entity_uri_extracts_type_and_id(self) -> None:
        parsed = parse_uri("graph-entity://Function/foo")
        assert parsed is not None
        assert parsed.scheme == "graph-entity"
        assert parsed.entity_type == "Function"
        assert parsed.entity_id == "foo"

    def test_graph_entity_uri_allows_id_with_slashes(self) -> None:
        # Phase 50 decision B — hierarchical ids stay intact.
        parsed = parse_uri("graph-entity://Function/AuthService/login")
        assert parsed is not None
        assert parsed.entity_type == "Function"
        assert parsed.entity_id == "AuthService/login"

    def test_graph_entity_uri_missing_type(self) -> None:
        with pytest.raises(McpError) as ei:
            parse_uri("graph-entity://")
        assert ei.value.error.data == {
            "uri": "graph-entity://",
            "reason": "missing_type",
        }

    def test_graph_entity_uri_missing_id(self) -> None:
        with pytest.raises(McpError) as ei:
            parse_uri("graph-entity://Function")
        assert ei.value.error.data == {
            "uri": "graph-entity://Function",
            "reason": "missing_id",
        }


# --- ParsedURI dataclass invariants ---------------------------------------


class TestParsedURI:
    def test_parsed_uri_is_frozen(self) -> None:
        parsed = ParsedURI(scheme="job", job_id="abc")
        with pytest.raises((AttributeError, Exception)):
            parsed.job_id = "different"  # type: ignore[misc]

    def test_parsed_uri_only_scheme_field_populated(self) -> None:
        parsed = ParsedURI(scheme="job", job_id="abc")
        assert parsed.scheme == "job"
        assert parsed.job_id == "abc"
        # Other scheme fields stay None
        assert parsed.chunk_id is None
        assert parsed.entity_type is None
        assert parsed.entity_id is None
        assert parsed.path is None
