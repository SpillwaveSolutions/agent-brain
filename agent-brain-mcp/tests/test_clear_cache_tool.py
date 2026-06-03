"""Phase 54 Plan 03 — handler tests for ``clear_cache`` (TOOL-08).

Coverage:
    * Happy path: ``confirm=True`` + server returns ``{count, size_bytes,
      size_mb}``; handler projects faithfully into
      :class:`ClearCacheOutput`.
    * Missing confirm: Pydantic ``Literal[True]`` constraint on
      :class:`ClearCacheInput.confirm` rejects construction.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from agent_brain_mcp.client import ApiClient
from agent_brain_mcp.schemas import ClearCacheInput
from agent_brain_mcp.tools.cache import handle_clear_cache


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


class TestClearCacheHappyPath:
    def test_returns_count_size_bytes_size_mb(self) -> None:
        api, captured = _make_capturing_client(
            {"count": 1234, "size_bytes": 5_242_880, "size_mb": 5.0}
        )
        out = handle_clear_cache(api, ClearCacheInput(confirm=True))
        assert out.count == 1234
        assert out.size_bytes == 5_242_880
        assert out.size_mb == pytest.approx(5.0)

        # Request shape pin: DELETE with empty body, no query params.
        assert len(captured) == 1
        req = captured[0]
        assert req.method == "DELETE"
        assert req.url.path == "/index/cache/"
        assert req.content == b""
        assert dict(req.url.params) == {}


class TestClearCacheConfirmGuard:
    def test_missing_confirm_rejected_by_pydantic(self) -> None:
        """The :class:`ClearCacheInput.confirm` field is ``Literal[True]``
        — invocations without ``confirm=True`` (or omitting confirm) are
        rejected before the handler runs.
        """
        with pytest.raises(ValidationError):
            ClearCacheInput()  # type: ignore[call-arg]

    def test_confirm_false_rejected_by_pydantic(self) -> None:
        with pytest.raises(ValidationError):
            ClearCacheInput(confirm=False)  # type: ignore[arg-type]
