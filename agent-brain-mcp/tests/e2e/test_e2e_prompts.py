"""Phase 4 E2E: every prompt expansion + the full onboard run.

Maps to plan §6.6 + §12.3 acceptance #18 / #19.
"""

from __future__ import annotations

import pytest


def test_prompts_list_advertises_six_with_arguments(mcp_client: object) -> None:
    """Each of the 6 prompts shows up with its declared arguments."""
    pytest.skip("Phase 4 implementation pending.")


def test_find_callers_expands_with_symbol_argument(mcp_client: object) -> None:
    """``prompts/get find-callers symbol=QueryService`` returns a plan that
    calls ``search_documents`` with ``mode=graph``,
    ``relationship_types=["calls"]``."""
    pytest.skip("Phase 4 implementation pending.")


def test_find_callers_missing_required_argument_rejected(
    mcp_client: object,
) -> None:
    """``prompts/get find-callers`` (no args) returns a clear error."""
    pytest.skip("Phase 4 implementation pending.")


def test_compare_search_modes_runs_all_three(mcp_client: object) -> None:
    """``compare-search-modes`` produces a plan that runs the same query
    under ``bm25``, ``hybrid``, and ``multi`` for side-by-side comparison."""
    pytest.skip("Phase 4 implementation pending.")


def test_onboard_to_codebase_full_run(mcp_client: object) -> None:
    """Plan §12.3 acceptance #19: ``prompts/get onboard-to-codebase`` →
    the client model executes the resulting plan (reads ``corpus://config``,
    ``corpus://stats``, ``corpus://folders``; runs ``search_documents``
    for top-N entrypoints) → produces a coherent briefing on the tiny
    fixture corpus."""
    pytest.skip("Phase 4 implementation pending.")


def test_audit_indexed_folders_flags_stale_and_unwatched(
    mcp_client: object,
) -> None:
    """``audit-indexed-folders`` reads ``corpus://folders``, flags folders
    with ``last_indexed`` older than 7 days OR ``watch_mode == 'off'``,
    suggests ``index_folder`` calls for each."""
    pytest.skip("Phase 4 implementation pending.")
