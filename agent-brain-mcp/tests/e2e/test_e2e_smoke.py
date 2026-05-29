"""Phase 4 E2E smoke — every primitive listed once.

Per test plan §4.5, this maps to the manual command:

    agent-brain-mcp --backend uds < scripts/mcp-smoke.jsonl > /tmp/mcp-out.jsonl
    jq -e '.result.tools | length == 7'    /tmp/mcp-out.jsonl
    jq -e '.result.resources | length == 5' /tmp/mcp-out.jsonl
    jq -e '.result.prompts | length == 6'  /tmp/mcp-out.jsonl

All tests skip until Phase 4 ships the ``mcp_client`` fixture.
"""

from __future__ import annotations

import pytest


def test_initialize_advertises_v1_capabilities(mcp_client: object) -> None:
    """``initialize`` reports tools, resources, prompts; nothing else.

    Plan §6.1: ``{tools.listChanged: false, resources.subscribe: false,
    resources.listChanged: false, prompts.listChanged: false}`` — no
    sampling, no logging, no completions, no elicitation.
    """
    pytest.skip("Phase 4 implementation pending — see test plan §3 Phase 4.")


def test_tools_list_returns_exactly_seven(mcp_client: object) -> None:
    """``tools/list`` returns: search_documents, query_count, index_folder,
    get_job, list_jobs, cancel_job, server_health (plan §6.2)."""
    pytest.skip("Phase 4 implementation pending.")


def test_resources_list_returns_exactly_five(mcp_client: object) -> None:
    """``resources/list`` returns: corpus://config, corpus://status,
    corpus://health, corpus://providers, corpus://folders (plan §6.5)."""
    pytest.skip("Phase 4 implementation pending.")


def test_prompts_list_returns_exactly_six(mcp_client: object) -> None:
    """``prompts/list`` returns: find-callers, find-implementation,
    explain-architecture, compare-search-modes, onboard-to-codebase,
    audit-indexed-folders (plan §6.6)."""
    pytest.skip("Phase 4 implementation pending.")
