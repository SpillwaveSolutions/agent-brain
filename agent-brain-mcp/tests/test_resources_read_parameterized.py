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
    async def test_read_job_uri_success(
        self, fake_httpx_client: httpx.Client
    ) -> None:
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


# --- placeholder schemes raise NotImplementedError ------------------------


class TestPlaceholderHandlers:
    """Plans 51-02 and 51-03 will replace these placeholders. Until
    they ship, attempting to read those schemes raises
    ``NotImplementedError`` — not ``McpError``. This is intentional:
    callers should not be able to silently get an empty/None response
    for an unwired handler."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "uri",
        [
            "chunk://chunk_001",
            "graph-entity://Function/foo",
            "file:///tmp/foo.py",
        ],
    )
    async def test_placeholder_schemes_raise_not_implemented(
        self, fake_httpx_client: httpx.Client, uri: str
    ) -> None:
        server = build_server(fake_httpx_client)
        with pytest.raises(NotImplementedError):
            await _read(server, uri)


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
