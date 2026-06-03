"""Phase 51 Plan 04 (URI-05): templates/list advertises 4 RFC 6570 templates.

Mirrors the v1 ``test_resources_list.py`` pattern: parametrize over the
templates registry, drive the handler through the low-level Server's
request_handlers dispatch table, and assert the wire-shape contract.

The four ``uriTemplate`` strings are a forward-compatibility commitment
per Phase 51 CONTEXT decision B. Once advertised, MCP client libraries
lock onto them. The string-equality assertions here are intentionally
strict — any future change would surface as a test failure that forces
a deliberate decision (and a CHANGELOG entry).
"""

from __future__ import annotations

import httpx
import mcp.types as types
import pytest

from agent_brain_mcp.resources import TEMPLATE_REGISTRY
from agent_brain_mcp.server import build_server

# Exact uriTemplate strings from Phase 51 CONTEXT decision B. If one of
# these ever needs to change, that's a deliberate forward-incompat
# decision — change here, change docs/plans/2026-06-02-mcp-v2-
# subscriptions.md §3.2, and add a CHANGELOG note.
EXPECTED_URI_TEMPLATES = {
    "chunk://{chunk_id}",
    "graph-entity://{type}/{id}",
    "job://{job_id}",
    "file://{+path}",
}

# JSON-backed schemes advertise a static mimeType. file:// does not (its
# MIME is sniffed per-read by mimetypes.guess_type).
JSON_SCHEMES_BY_TEMPLATE = {
    "chunk://{chunk_id}": "application/json",
    "graph-entity://{type}/{id}": "application/json",
    "job://{job_id}": "application/json",
}
FILE_TEMPLATE = "file://{+path}"


class TestTemplateRegistry:
    """Registry-level assertions (no MCP wire involved)."""

    def test_registry_has_exactly_four_templates(self) -> None:
        assert len(TEMPLATE_REGISTRY) == 4

    def test_registry_uri_templates_match_expected_set(self) -> None:
        advertised = {t.uriTemplate for t in TEMPLATE_REGISTRY}
        assert advertised == EXPECTED_URI_TEMPLATES

    @pytest.mark.parametrize(
        "uri_template,expected_mime", JSON_SCHEMES_BY_TEMPLATE.items()
    )
    def test_json_schemes_carry_application_json_mimetype(
        self, uri_template: str, expected_mime: str
    ) -> None:
        matches = [t for t in TEMPLATE_REGISTRY if t.uriTemplate == uri_template]
        assert len(matches) == 1, f"expected one template for {uri_template}"
        assert matches[0].mimeType == expected_mime

    def test_file_scheme_has_no_static_mimetype(self) -> None:
        """file://{+path} must NOT advertise a static mimeType. The MIME
        is sniffed per-read (mimetypes.guess_type) so advertising one
        statically would misroute file-type detection at the client side.
        Per Phase 51 CONTEXT decision E."""
        matches = [t for t in TEMPLATE_REGISTRY if t.uriTemplate == FILE_TEMPLATE]
        assert len(matches) == 1
        assert matches[0].mimeType is None

    def test_each_template_has_name_and_description(self) -> None:
        """Both fields are required for MCP-spec-compliant template
        publication and for UI surfaces (e.g., MCP Inspector). Empty
        strings would technically pass the SDK validation but would
        present a broken UX."""
        for t in TEMPLATE_REGISTRY:
            assert t.name, f"template {t.uriTemplate} missing name"
            assert t.description, f"template {t.uriTemplate} missing description"
            assert (
                len(t.description) > 20
            ), f"template {t.uriTemplate} description too short to be useful"

    def test_file_template_uses_reserved_expansion(self) -> None:
        """Belt-and-suspenders check on the {+path} operator. The default
        RFC 6570 expansion would percent-encode '/' as '%2F', which is
        the WRONG behavior for filesystem paths. Pin the operator
        choice explicitly so a future "simplify the template" PR can't
        silently change the semantics."""
        matches = [t for t in TEMPLATE_REGISTRY if t.uriTemplate == FILE_TEMPLATE]
        assert len(matches) == 1
        assert "{+path}" in matches[0].uriTemplate
        # NOT the default-expansion form:
        assert "{path}" not in matches[0].uriTemplate.replace("{+path}", "")


class TestListResourceTemplatesHandler:
    """End-to-end via the MCP low-level Server request_handlers dispatch.

    Mirrors the pattern used by test_resources_list.py — build the
    server with a fake httpx client, look up the handler from the
    server's request_handlers dict by request type, await it with the
    matching pydantic request model, and assert on the result.root
    structure.
    """

    @pytest.mark.asyncio
    async def test_handler_returns_four_templates(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListResourceTemplatesRequest]
        result = await handler(
            types.ListResourceTemplatesRequest(method="resources/templates/list")
        )
        templates = result.root.resourceTemplates
        assert len(templates) == 4

    @pytest.mark.asyncio
    async def test_handler_returns_expected_uri_templates(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListResourceTemplatesRequest]
        result = await handler(
            types.ListResourceTemplatesRequest(method="resources/templates/list")
        )
        advertised = {t.uriTemplate for t in result.root.resourceTemplates}
        assert advertised == EXPECTED_URI_TEMPLATES

    @pytest.mark.asyncio
    async def test_handler_returns_correct_mimetypes(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListResourceTemplatesRequest]
        result = await handler(
            types.ListResourceTemplatesRequest(method="resources/templates/list")
        )
        by_template = {t.uriTemplate: t.mimeType for t in result.root.resourceTemplates}
        assert by_template["chunk://{chunk_id}"] == "application/json"
        assert by_template["graph-entity://{type}/{id}"] == "application/json"
        assert by_template["job://{job_id}"] == "application/json"
        # file://{+path} must NOT carry a static MIME.
        assert by_template["file://{+path}"] is None


class TestResourcesListUnchanged:
    """Regression: Phase 51 must NOT change ``resources/list``.

    v1 MCP clients that only call ``resources/list`` continue to see
    exactly the 5 static ``corpus://*`` resources they saw before. The
    4 new templates live on a separate endpoint (``resources/templates/
    list``); the parameterized URIs are explicitly NOT listed as
    static resources because every concrete chunk://, graph-entity://,
    job://, file:// is a different URI (per CONTEXT decision A).
    """

    @pytest.mark.asyncio
    async def test_list_resources_still_returns_five_corpus_uris(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListResourcesRequest]
        result = await handler(types.ListResourcesRequest(method="resources/list"))
        resources = result.root.resources
        assert len(resources) == 5
        advertised = {str(r.uri).rstrip("/") for r in resources}
        assert advertised == {
            "corpus://config",
            "corpus://status",
            "corpus://health",
            "corpus://providers",
            "corpus://folders",
        }

    @pytest.mark.asyncio
    async def test_list_resources_does_not_advertise_parameterized_schemes(
        self, fake_httpx_client: httpx.Client
    ) -> None:
        """The four parameterized schemes (chunk://, graph-entity://,
        job://, file://) MUST NOT appear in resources/list — they have
        no concrete static URIs to advertise. Discovery flows through
        resources/templates/list instead (CONTEXT decision A)."""
        server = build_server(fake_httpx_client)
        handler = server.request_handlers[types.ListResourcesRequest]
        result = await handler(types.ListResourcesRequest(method="resources/list"))
        schemes = {str(r.uri).split(":", 1)[0] for r in result.root.resources}
        # Only corpus is allowed in resources/list.
        assert schemes == {"corpus"}
        for forbidden in {"chunk", "graph-entity", "job", "file"}:
            assert forbidden not in schemes
