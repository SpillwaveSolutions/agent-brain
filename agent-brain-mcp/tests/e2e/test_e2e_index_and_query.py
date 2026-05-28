"""Phase 4 E2E: index_folder → poll get_job → query returns new chunks.

Exercises the tool that takes the longest end-to-end and proves the v1
loop without ``wait_for_job`` (which is v2). Skips until Phase 4.
"""

from __future__ import annotations

import pytest


def test_index_then_query_finds_new_content(
    mcp_client: object, tiny_corpus_path: object
) -> None:
    """Index the corpus → poll get_job until done → search for a string
    only present in the corpus → expect a hit."""
    pytest.skip("Phase 4 implementation pending.")


def test_cancel_running_job_requires_confirm(mcp_client: object) -> None:
    """``cancel_job`` without ``confirm: true`` returns -32602 InvalidParams
    (plan §6.2; safety enforced server-side because annotations are hints)."""
    pytest.skip("Phase 4 implementation pending.")


def test_list_jobs_cursor_pagination_roundtrips(mcp_client: object) -> None:
    """page-1's nextCursor decodes to the offset for page-2 (plan §12.3 #13)."""
    pytest.skip("Phase 4 implementation pending.")
