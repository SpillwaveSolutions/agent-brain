"""Phase 4 E2E: every search mode through the real MCP server.

Maps to test plan §3 Phase 4 acceptance #9 (structuredContent) and #11
(error mapping). Each test skips until Phase 4 ships ``mcp_client``.
"""

from __future__ import annotations

import pytest


@pytest.mark.parametrize("mode", ["vector", "bm25", "hybrid", "graph", "multi"])
def test_search_documents_each_mode_returns_structured_content(
    mcp_client: object, mode: str
) -> None:
    """Calling ``search_documents`` with each of the 5 modes returns
    both ``content`` (human summary) and ``structuredContent`` (typed)."""
    pytest.skip("Phase 4 implementation pending.")


def test_search_documents_explain_true_includes_explanation(
    mcp_client: object,
) -> None:
    """With ``explain=true``, each result carries an ``explanation`` field
    (matches the server's QueryResult.explanation shape from explain
    parameter — see commit 1d61325)."""
    pytest.skip("Phase 4 implementation pending.")


def test_search_documents_invalid_mode_returns_mcp_error(
    mcp_client: object,
) -> None:
    """An invalid mode returns ``-32602 InvalidParams`` (Phase 4 error
    mapping, plan §6.3)."""
    pytest.skip("Phase 4 implementation pending.")
