"""Phase 54 Plan 03 — handler tests for ``remove_folder`` (TOOL-06).

Coverage:
    * Happy path: ``confirm=True`` + valid folder; handler returns the
      server's :class:`FolderDeleteResponse` shape verbatim.
    * Missing confirm: Pydantic ``Literal[True]`` constraint on
      :class:`RemoveFolderInput.confirm` rejects construction.
    * 409 (active indexing job for folder, FOLD-07) surfaces as
      :class:`McpError` with code ``BACKEND_CONFLICT`` (-32000) via
      the existing :func:`errors.raise_for_status` pipeline.

Note on error code: the v1 :func:`errors.raise_for_status` maps HTTP
409 to ``BACKEND_CONFLICT`` (-32000), NOT ``INVALID_PARAMS`` (-32602).
The Plan 03 description text was paraphrasing; the actual surfaced
code is ``BACKEND_CONFLICT``. The handler does no per-code translation
(CONTEXT decision G — uniform error mapping).
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from mcp import McpError
from pydantic import ValidationError

from agent_brain_mcp.client import ApiClient
from agent_brain_mcp.errors import BACKEND_CONFLICT
from agent_brain_mcp.schemas import RemoveFolderInput
from agent_brain_mcp.tools.folders import handle_remove_folder


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


class TestRemoveFolderHappyPath:
    def test_returns_folder_path_chunks_deleted_message(self) -> None:
        api, captured = _make_capturing_client(
            {
                "folder_path": "/abs/repo/docs",
                "chunks_deleted": 42,
                "message": "Successfully removed 42 chunks for /abs/repo/docs",
            }
        )
        out = handle_remove_folder(
            api,
            RemoveFolderInput(folder_path="/abs/repo/docs", confirm=True),
        )
        assert out.folder_path == "/abs/repo/docs"
        assert out.chunks_deleted == 42
        assert "Successfully removed" in out.message

        # Request shape pin: DELETE with body, NOT query/path.
        assert len(captured) == 1
        req = captured[0]
        assert req.method == "DELETE"
        assert req.url.path == "/index/folders/"
        body = json.loads(req.content)
        assert body == {"folder_path": "/abs/repo/docs"}


class TestRemoveFolderConfirmGuard:
    def test_missing_confirm_rejected_by_pydantic(self) -> None:
        """The :class:`RemoveFolderInput.confirm` field is
        ``Literal[True]`` — invocations without ``confirm=True`` (or with
        ``confirm=False``) are rejected before the handler runs.
        """
        with pytest.raises(ValidationError):
            # confirm field is required & must be True; missing fails.
            RemoveFolderInput(folder_path="/abs/repo/docs")  # type: ignore[call-arg]

    def test_confirm_false_rejected_by_pydantic(self) -> None:
        with pytest.raises(ValidationError):
            RemoveFolderInput(folder_path="/abs/repo/docs", confirm=False)  # type: ignore[arg-type]


class TestRemoveFolder409ActiveJob:
    def test_409_active_job_surfaces_as_backend_conflict(self) -> None:
        """FOLD-07: server returns 409 when an indexing job is active for
        the folder. The existing :func:`errors.raise_for_status` pipeline
        maps 409 → :class:`McpError(BACKEND_CONFLICT)` (-32000)."""
        api, _ = _make_capturing_client(
            {
                "detail": (
                    "Cannot remove folder while indexing job is active "
                    "for this path: /abs/repo/docs"
                )
            },
            response_status=409,
        )
        with pytest.raises(McpError) as excinfo:
            handle_remove_folder(
                api,
                RemoveFolderInput(folder_path="/abs/repo/docs", confirm=True),
            )
        err = excinfo.value.error
        assert err.code == BACKEND_CONFLICT
        # Operator-visible detail from the server surfaces in the message
        # so MCP clients can render the "cancel the job first" hint.
        assert "indexing job is active" in err.message
