"""Phase 4 test: each resource returns parsable JSON (plan §12.3 #17)."""

from __future__ import annotations

import json

import httpx
import mcp.types as types
import pytest
from pydantic import AnyUrl

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


class TestResourcesRead:
    @pytest.mark.asyncio
    async def test_corpus_config(self, fake_httpx_client: httpx.Client) -> None:
        server = build_server(fake_httpx_client)
        body = await _read(server, "corpus://config")
        data = json.loads(body)
        assert data["storage_backend"] == "chroma"
        assert data["stores"]["vector"] is True

    @pytest.mark.asyncio
    async def test_corpus_status(self, fake_httpx_client: httpx.Client) -> None:
        server = build_server(fake_httpx_client)
        body = await _read(server, "corpus://status")
        data = json.loads(body)
        assert data["total_documents"] == 42
        assert data["total_chunks"] == 420

    @pytest.mark.asyncio
    async def test_corpus_health(self, fake_httpx_client: httpx.Client) -> None:
        server = build_server(fake_httpx_client)
        body = await _read(server, "corpus://health")
        data = json.loads(body)
        assert data["status"] == "healthy"
        assert data["version"] == "10.0.7"

    @pytest.mark.asyncio
    async def test_corpus_providers(self, fake_httpx_client: httpx.Client) -> None:
        server = build_server(fake_httpx_client)
        body = await _read(server, "corpus://providers")
        data = json.loads(body)
        assert "providers" in data

    @pytest.mark.asyncio
    async def test_corpus_folders(self, fake_httpx_client: httpx.Client) -> None:
        server = build_server(fake_httpx_client)
        body = await _read(server, "corpus://folders")
        data = json.loads(body)
        assert "folders" in data
        assert len(data["folders"]) == 1
        assert data["folders"][0]["folder_path"] == "/tmp/test"
