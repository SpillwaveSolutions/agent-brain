"""Regression test for issue #143 — zero-chunk diff must not fail the job.

When the manifest diff sees N "new" files that all chunk to zero (empty
placeholder ``.md`` files, scaffolding, etc.), the BM25 build must not
raise ``Please pass exactly one of index, nodes, or docstore.``. v9.6.0
silently no-oped here; v10.0.x regressed.
"""

from __future__ import annotations

import logging

from llama_index.core.schema import TextNode

from agent_brain_server.indexing.bm25_index import BM25IndexManager


def test_bm25_build_index_empty_nodes_is_noop(tmp_path, caplog) -> None:
    """build_index([]) must log and return, not raise."""
    mgr = BM25IndexManager(persist_dir=str(tmp_path))

    with caplog.at_level(logging.INFO):
        mgr.build_index([])  # must not raise

    # Defensive guard logs the skip
    messages = [r.message for r in caplog.records]
    assert any("empty nodes" in m for m in messages), messages
    # And no retriever should be created
    assert mgr._retriever is None


def test_bm25_build_index_then_empty_does_not_corrupt(tmp_path, caplog) -> None:
    """Calling build_index([]) after a real build must not blow away state.

    Operators rebuilding a partial index shouldn't lose their existing
    retriever just because a follow-up incremental call had zero new nodes.
    """
    mgr = BM25IndexManager(persist_dir=str(tmp_path))
    real_nodes = [
        TextNode(text="The quick brown fox", id_="n1"),
        TextNode(text="jumps over the lazy dog", id_="n2"),
    ]
    mgr.build_index(real_nodes)
    assert mgr._retriever is not None
    retriever_before = mgr._retriever

    with caplog.at_level(logging.INFO):
        mgr.build_index([])

    # Existing retriever preserved (no-op leaves prior state intact)
    assert mgr._retriever is retriever_before
