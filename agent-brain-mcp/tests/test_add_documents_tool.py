"""Phase 54 Plan 03 — handler tests for ``add_documents`` (TOOL-02).

Coverage:
    * Happy path: server returns ``{job_id, status, message}``; handler
      projects faithfully into :class:`AddDocumentsOutput`.
    * ``force=True``: the query string carries ``force=true`` through
      :meth:`ApiClient.add_documents`.
    * Empty paths list: Pydantic ``min_length=1`` constraint on
      :class:`AddDocumentsInput.paths` rejects construction.

Defense-in-depth assertion: the request body MUST NOT include
``allow_external``. Issue #180 removed the server-side parameter; the
handler intentionally does not expose it. A test pins the body shape.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from agent_brain_mcp.client import ApiClient
from agent_brain_mcp.schemas import AddDocumentsInput
from agent_brain_mcp.tools.index import handle_add_documents


def _make_capturing_client(
    response_body: dict[str, Any],
    response_status: int = 200,
) -> tuple[ApiClient, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(response_status, json=response_body)

    transport = httpx.MockTransport(handler)
    return (
        ApiClient(
            httpx.Client(transport=transport, base_url="http://test-agent-brain")
        ),
        captured,
    )


class TestAddDocumentsHappyPath:
    def test_returns_job_id_and_status(self) -> None:
        api, captured = _make_capturing_client(
            {"job_id": "job-add-1", "status": "queued", "message": "queued"}
        )
        out = handle_add_documents(api, AddDocumentsInput(paths=["/abs/repo/docs"]))
        assert out.job_id == "job-add-1"
        assert out.status == "queued"
        assert out.message == "queued"
        # Request shape pin: route + body contain only the documented fields.
        assert len(captured) == 1
        req = captured[0]
        assert req.method == "POST"
        assert req.url.path == "/index/add"
        body = json.loads(req.content)
        assert body == {"paths": ["/abs/repo/docs"]}

    def test_body_omits_allow_external_field(self) -> None:
        """Defense-in-depth — the handler MUST NOT include allow_external in
        the request body. Issue #180 removed the server-side parameter;
        exposing it MCP-side would be a silent no-op + security drift signal.
        """
        api, captured = _make_capturing_client({"job_id": "j", "status": "queued"})
        handle_add_documents(
            api,
            AddDocumentsInput(paths=["/a", "/b"]),
        )
        body = json.loads(captured[0].content)
        assert "allow_external" not in body


class TestAddDocumentsForceQueryParam:
    def test_force_true_propagates_to_query_string(self) -> None:
        api, captured = _make_capturing_client({"job_id": "j", "status": "queued"})
        handle_add_documents(
            api,
            AddDocumentsInput(paths=["/x"], force=True),
        )
        req = captured[0]
        assert dict(req.url.params) == {"force": "true"}

    def test_force_false_omits_query_param(self) -> None:
        api, captured = _make_capturing_client({"job_id": "j", "status": "queued"})
        handle_add_documents(
            api,
            AddDocumentsInput(paths=["/x"], force=False),
        )
        req = captured[0]
        assert "force" not in dict(req.url.params)


class TestAddDocumentsSchemaValidation:
    def test_empty_paths_list_rejected_by_pydantic(self) -> None:
        """``paths`` is constrained to ``min_length=1`` (Plan 01). Pydantic
        rejects construction before the handler ever runs."""
        with pytest.raises(ValidationError) as excinfo:
            AddDocumentsInput(paths=[])
        msg = str(excinfo.value).lower()
        # The validation error message references the list length constraint.
        assert "paths" in msg
