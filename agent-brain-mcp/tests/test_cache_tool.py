"""Phase 54 Plan 02 — handler tests for ``cache_status`` (TOOL-07).

Coverage:
    * Happy path: server returns the six typed keys; handler projects
      faithfully into :class:`CacheStatusOutput`.
    * 503-uninitialised: server returns 503 with a ``detail`` body
      mirroring ``agent_brain_server.api.routers.cache._cache_status_impl``;
      the existing :func:`errors.raise_for_status` pipeline surfaces it
      as :class:`McpError` (CONTEXT decision G).
    * Forward-compat: unknown server-side additions land in ``extra``
      because :class:`CacheStatusOutput` opts into ``extra="allow"``.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from mcp import McpError

from agent_brain_mcp.client import ApiClient
from agent_brain_mcp.errors import SERVICE_INDEXING
from agent_brain_mcp.schemas import CacheStatusInput
from agent_brain_mcp.tools.cache import handle_cache_status


def _make_client(response_body: dict[str, Any], *, status: int = 200) -> ApiClient:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=response_body)

    transport = httpx.MockTransport(handler)
    return ApiClient(
        httpx.Client(transport=transport, base_url="http://test-agent-brain")
    )


class TestCacheStatusHappyPath:
    def test_returns_populated_status(self) -> None:
        api = _make_client(
            {
                "hits": 120,
                "misses": 30,
                "hit_rate": 0.8,
                "mem_entries": 64,
                "entry_count": 4096,
                "size_bytes": 1024 * 1024,
            }
        )
        out = handle_cache_status(api, CacheStatusInput())
        assert out.hits == 120
        assert out.misses == 30
        assert out.hit_rate == pytest.approx(0.8)
        assert out.mem_entries == 64
        assert out.entry_count == 4096
        assert out.size_bytes == 1024 * 1024

    def test_forward_compatible_extra_fields_accepted(self) -> None:
        """The output model is configured with ``extra="allow"`` so
        future server-side additions to the cache-status payload do not
        break MCP clients (CONTEXT-locked decision from Plan 01).
        """
        api = _make_client(
            {
                "hits": 1,
                "misses": 1,
                "hit_rate": 0.5,
                "mem_entries": 1,
                "entry_count": 1,
                "size_bytes": 100,
                # Forward-compat field added by a hypothetical future server.
                "cold_start_count": 7,
            }
        )
        out = handle_cache_status(api, CacheStatusInput())
        dumped = out.model_dump()
        assert dumped["cold_start_count"] == 7


class TestCacheStatus503Uninitialised:
    def test_503_surfaces_as_mcp_error(self) -> None:
        """Server's ``_cache_status_impl`` raises ``HTTPException(503)`` when
        the cache service is not initialised. ``ApiClient._request`` calls
        :func:`errors.raise_for_status` which maps 503 to
        :class:`McpError(SERVICE_INDEXING)` — handler doesn't need any
        per-tool error handling (CONTEXT decision G).
        """
        api = _make_client(
            {"detail": "Embedding cache service not initialised"},
            status=503,
        )
        with pytest.raises(McpError) as excinfo:
            handle_cache_status(api, CacheStatusInput())
        err = excinfo.value.error
        assert err.code == SERVICE_INDEXING
        assert "Embedding cache service not initialised" in err.message
