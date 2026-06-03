"""Phase 54 Plan 02 — handler tests for ``list_folders`` (TOOL-05).

Coverage:
    * Happy path: server returns a populated folder list + total; handler
      projects each entry into :class:`FolderInfoMcp` faithfully and the
      output's ``total`` matches the server.
    * Empty-corpus path: server returns ``{"folders": [], "total": 0}``;
      handler returns an empty :class:`ListFoldersOutput` (folders=[],
      total=0) without raising.
"""

from __future__ import annotations

from typing import Any

import httpx

from agent_brain_mcp.client import ApiClient
from agent_brain_mcp.schemas import ListFoldersInput
from agent_brain_mcp.tools.folders import handle_list_folders


def _make_client(response_body: dict[str, Any]) -> ApiClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_body)

    transport = httpx.MockTransport(handler)
    return ApiClient(
        httpx.Client(transport=transport, base_url="http://test-agent-brain")
    )


class TestListFoldersHappyPath:
    def test_returns_folders_with_total(self) -> None:
        api = _make_client(
            {
                "folders": [
                    {
                        "folder_path": "/abs/repo/docs",
                        "chunk_count": 42,
                        "last_indexed": "2026-06-03T00:00:00Z",
                        "watch_mode": "auto",
                        "watch_debounce_seconds": 15,
                    },
                    {
                        "folder_path": "/abs/repo/src",
                        "chunk_count": 128,
                        "last_indexed": "2026-06-03T01:00:00Z",
                        "watch_mode": "off",
                        "watch_debounce_seconds": None,
                    },
                ],
                "total": 2,
            }
        )
        out = handle_list_folders(api, ListFoldersInput())
        assert out.total == 2
        assert len(out.folders) == 2
        assert out.folders[0].folder_path == "/abs/repo/docs"
        assert out.folders[0].chunk_count == 42
        assert out.folders[0].last_indexed == "2026-06-03T00:00:00Z"
        assert out.folders[0].watch_mode == "auto"
        assert out.folders[0].watch_debounce_seconds == 15
        assert out.folders[1].folder_path == "/abs/repo/src"
        assert out.folders[1].watch_mode == "off"
        assert out.folders[1].watch_debounce_seconds is None


class TestListFoldersEmptyCorpus:
    def test_empty_folder_list_returns_empty_output(self) -> None:
        api = _make_client({"folders": [], "total": 0})
        out = handle_list_folders(api, ListFoldersInput())
        assert out.folders == []
        assert out.total == 0

    def test_response_missing_total_falls_back_to_folders_length(self) -> None:
        """Defense-in-depth: if the server ever drops ``total`` from the
        response, the handler still produces a non-erroring output.
        """
        api = _make_client(
            {
                "folders": [
                    {
                        "folder_path": "/abs/x",
                        "chunk_count": 1,
                        "last_indexed": "2026-06-03T00:00:00Z",
                    },
                ]
            }
        )
        out = handle_list_folders(api, ListFoldersInput())
        assert out.total == 1
        assert len(out.folders) == 1
