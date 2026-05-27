"""Tests for periodic triplet snapshots during graph indexing (Issue #166).

These tests focus on the cadence hook inside ``build_from_documents``: a
snapshot must be written every ``GRAPH_SNAPSHOT_CHUNKS`` chunks OR every
``GRAPH_SNAPSHOT_INTERVAL_SEC`` seconds (whichever first), so a kill
mid-langextract doesn't lose extraction work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_brain_server.indexing.graph_index import GraphIndexManager
from agent_brain_server.models.graph import GraphTriple
from agent_brain_server.storage.graph_snapshot import GraphSnapshotManager


@pytest.fixture
def real_persist_dir(tmp_path: Path) -> Path:
    d = tmp_path / "graph_index"
    d.mkdir()
    return d


@pytest.fixture
def mock_graph_store_with_real_dir(real_persist_dir: Path):
    """A graph store mock whose persist_dir is a real tmp path so the
    snapshot manager can actually write to disk."""
    mock = MagicMock()
    mock.is_initialized = True
    mock.entity_count = 0
    mock.relationship_count = 0
    mock.store_type = "kuzu"
    mock.persist_dir = real_persist_dir
    mock.add_triplet.return_value = True
    mock.graph_store = MagicMock()
    return mock


@pytest.fixture
def mock_llm_extractor():
    mock = MagicMock()
    mock.extract_triplets.return_value = []
    return mock


@pytest.fixture
def mock_code_extractor():
    mock = MagicMock()
    mock.extract_from_metadata.return_value = []
    mock.extract_from_text.return_value = []
    return mock


@pytest.fixture
def mock_langextract_extractor():
    mock = MagicMock()
    mock.extract_triplets.return_value = []
    return mock


@dataclass
class _FakeChunk:
    text: str
    chunk_id: str

    @dataclass
    class _Metadata:
        source_type: str = "code"
        language: str = "python"

        def to_dict(self):
            return {"source_type": self.source_type, "language": self.language}

    metadata: object = None

    def __post_init__(self):
        self.metadata = self._Metadata()


def _build_manager(graph_store, llm, code, langextract) -> GraphIndexManager:
    return GraphIndexManager(
        graph_store=graph_store,
        llm_extractor=llm,
        code_extractor=code,
        langextract_extractor=langextract,
    )


def _make_triplet(i: int) -> GraphTriple:
    return GraphTriple(
        subject=f"sub_{i}",
        predicate="rel",
        object=f"obj_{i}",
        source_chunk_id=f"chunk_{i}",
    )


@patch("agent_brain_server.indexing.graph_index._graphrag_enabled")
@patch("agent_brain_server.indexing.graph_index.settings")
def test_snapshot_written_at_chunk_threshold(
    mock_settings,
    mock_enabled,
    mock_graph_store_with_real_dir,
    mock_llm_extractor,
    mock_code_extractor,
    mock_langextract_extractor,
    real_persist_dir,
):
    mock_enabled.return_value = True
    mock_settings.GRAPH_USE_CODE_METADATA = True
    mock_settings.GRAPH_USE_LLM_EXTRACTION = False
    mock_settings.GRAPH_SNAPSHOT_CHUNKS = 5
    mock_settings.GRAPH_SNAPSHOT_INTERVAL_SEC = 999  # effectively disabled
    mock_settings.GRAPH_SNAPSHOT_KEEP = 3

    # Each chunk produces 1 triplet
    mock_code_extractor.extract_from_metadata.side_effect = [
        [_make_triplet(i)] for i in range(12)
    ]

    docs = [_FakeChunk(text="x", chunk_id=f"c{i}") for i in range(12)]
    manager = _build_manager(
        mock_graph_store_with_real_dir,
        mock_llm_extractor,
        mock_code_extractor,
        mock_langextract_extractor,
    )
    manager.build_from_documents(docs, source_job_id="job_test")

    snap_mgr = GraphSnapshotManager(real_persist_dir)
    snaps = snap_mgr.list_snapshots()
    # 12 chunks @ threshold=5 → snapshots at 5 and 10, plus a final tail
    # snapshot for the last 2 chunks. With rotation keeping 3, we still see 3.
    assert len(snaps) == 3

    latest_triplets = snap_mgr.load(snaps[0])
    assert len(latest_triplets) == 12  # final snapshot has all
    assert latest_triplets[0].subject == "sub_0"
    assert latest_triplets[-1].subject == "sub_11"


@patch("agent_brain_server.indexing.graph_index._graphrag_enabled")
@patch("agent_brain_server.indexing.graph_index.settings")
def test_final_snapshot_when_below_threshold(
    mock_settings,
    mock_enabled,
    mock_graph_store_with_real_dir,
    mock_llm_extractor,
    mock_code_extractor,
    mock_langextract_extractor,
    real_persist_dir,
):
    """A run that ends before crossing any threshold still gets a tail
    snapshot — otherwise the trailing triplets would be lost on a kill
    right after the build completes."""
    mock_enabled.return_value = True
    mock_settings.GRAPH_USE_CODE_METADATA = True
    mock_settings.GRAPH_USE_LLM_EXTRACTION = False
    mock_settings.GRAPH_SNAPSHOT_CHUNKS = 100
    mock_settings.GRAPH_SNAPSHOT_INTERVAL_SEC = 999
    mock_settings.GRAPH_SNAPSHOT_KEEP = 3

    mock_code_extractor.extract_from_metadata.side_effect = [
        [_make_triplet(i)] for i in range(3)
    ]

    docs = [_FakeChunk(text="x", chunk_id=f"c{i}") for i in range(3)]
    manager = _build_manager(
        mock_graph_store_with_real_dir,
        mock_llm_extractor,
        mock_code_extractor,
        mock_langextract_extractor,
    )
    manager.build_from_documents(docs, source_job_id="job_short")

    snaps = GraphSnapshotManager(real_persist_dir).list_snapshots()
    assert len(snaps) == 1
    triplets = GraphSnapshotManager(real_persist_dir).load(snaps[0])
    assert len(triplets) == 3


@patch("agent_brain_server.indexing.graph_index._graphrag_enabled")
@patch("agent_brain_server.indexing.graph_index.settings")
def test_no_snapshot_when_no_triplets_extracted(
    mock_settings,
    mock_enabled,
    mock_graph_store_with_real_dir,
    mock_llm_extractor,
    mock_code_extractor,
    mock_langextract_extractor,
    real_persist_dir,
):
    """A build that yields zero triplets should not produce a snapshot."""
    mock_enabled.return_value = True
    mock_settings.GRAPH_USE_CODE_METADATA = True
    mock_settings.GRAPH_USE_LLM_EXTRACTION = False
    mock_settings.GRAPH_SNAPSHOT_CHUNKS = 5
    mock_settings.GRAPH_SNAPSHOT_INTERVAL_SEC = 999
    mock_settings.GRAPH_SNAPSHOT_KEEP = 3

    mock_code_extractor.extract_from_metadata.return_value = []

    docs = [_FakeChunk(text="x", chunk_id=f"c{i}") for i in range(3)]
    manager = _build_manager(
        mock_graph_store_with_real_dir,
        mock_llm_extractor,
        mock_code_extractor,
        mock_langextract_extractor,
    )
    manager.build_from_documents(docs)

    snaps = GraphSnapshotManager(real_persist_dir).list_snapshots()
    assert snaps == []


@patch("agent_brain_server.indexing.graph_index._graphrag_enabled")
@patch("agent_brain_server.indexing.graph_index.settings")
def test_snapshot_write_failure_doesnt_break_indexing(
    mock_settings,
    mock_enabled,
    mock_graph_store_with_real_dir,
    mock_llm_extractor,
    mock_code_extractor,
    mock_langextract_extractor,
    real_persist_dir,
):
    """If the snapshot can't be written (e.g. disk full), indexing must
    still complete successfully — the snapshot is a safety net, not a
    critical path."""
    mock_enabled.return_value = True
    mock_settings.GRAPH_USE_CODE_METADATA = True
    mock_settings.GRAPH_USE_LLM_EXTRACTION = False
    mock_settings.GRAPH_SNAPSHOT_CHUNKS = 1
    mock_settings.GRAPH_SNAPSHOT_INTERVAL_SEC = 999
    mock_settings.GRAPH_SNAPSHOT_KEEP = 3

    mock_code_extractor.extract_from_metadata.side_effect = [
        [_make_triplet(i)] for i in range(3)
    ]
    docs = [_FakeChunk(text="x", chunk_id=f"c{i}") for i in range(3)]

    manager = _build_manager(
        mock_graph_store_with_real_dir,
        mock_llm_extractor,
        mock_code_extractor,
        mock_langextract_extractor,
    )

    with patch(
        "agent_brain_server.indexing.graph_index.GraphSnapshotManager.write",
        side_effect=OSError("disk full"),
    ):
        result = manager.build_from_documents(docs)

    # Indexing still succeeded — all 3 triplets added even though snapshots
    # all failed to write
    assert result == 3
    assert mock_graph_store_with_real_dir.add_triplet.call_count == 3
