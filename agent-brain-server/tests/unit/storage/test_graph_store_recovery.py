"""Tests for Kuzu graph store corruption recovery (Issue #166).

Covers the defensive path added to ``_initialize_kuzu_store``: when
``kuzu.Database()`` raises ``IndexError`` or ``RuntimeError`` from the
pybind11 C++ constructor (typical symptom of a kill-mid-write corruption),
the store quarantines the corrupted files, retries on a fresh path, and
replays the latest valid snapshot.

The Kuzu library is mocked because we want to exercise the recovery
state machine without depending on actual Kuzu C++ corruption — which is
hard to synthesize portably.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_brain_server.storage.graph_snapshot import (
    GraphSnapshotManager,
    SnapshotTriplet,
)
from agent_brain_server.storage.graph_store import (
    GraphStoreManager,
    _corrupted_sibling,
    _quarantine_file,
    reset_graph_store_manager,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_graph_store_manager()
    yield
    reset_graph_store_manager()


@pytest.fixture
def persist_dir(tmp_path: Path) -> Path:
    d = tmp_path / "graph_index"
    d.mkdir()
    return d


@pytest.fixture
def kuzu_db_file(persist_dir: Path) -> Path:
    """Pre-create a 'corrupted' kuzu_db file with junk bytes."""
    f = persist_dir / "kuzu_db"
    f.write_bytes(b"\x00\x01\x02junk-not-a-valid-kuzu-catalog")
    return f


@pytest.fixture
def sample_triplets() -> list[SnapshotTriplet]:
    return [
        SnapshotTriplet(
            subject="FunctionA",
            predicate="calls",
            object="FunctionB",
            subject_type="Function",
            object_type="Function",
            source_chunk_id="chunk_1",
        ),
        SnapshotTriplet(
            subject="ClassX",
            predicate="extends",
            object="ClassY",
        ),
    ]


class TestQuarantineHelpers:
    def test_corrupted_sibling_includes_timestamp(self, tmp_path: Path):
        sibling = _corrupted_sibling(tmp_path / "kuzu_db")
        assert sibling.parent == tmp_path
        assert sibling.name.startswith("kuzu_db.corrupted-")

    def test_quarantine_file_renames(self, tmp_path: Path):
        src = tmp_path / "kuzu_db"
        src.write_bytes(b"corrupted")
        dest = _quarantine_file(src)
        assert dest is not None
        assert dest.exists()
        assert not src.exists()
        assert dest.read_bytes() == b"corrupted"

    def test_quarantine_missing_file_returns_none(self, tmp_path: Path):
        assert _quarantine_file(tmp_path / "does-not-exist") is None


class TestCorruptionRecovery:
    """End-to-end tests for the recovery path with a mocked Kuzu."""

    def _make_kuzu_mock(self, fail_first: bool):
        """Return a mock 'kuzu' module whose Database() raises on first call.

        If ``fail_first`` is True, the first call raises IndexError (like the
        real bug); subsequent calls return a MagicMock instance representing
        a healthy Database. If False, every call succeeds.
        """
        db_instance = MagicMock(name="kuzu.Database()")
        calls = {"count": 0}

        def database_factory(path):
            calls["count"] += 1
            if fail_first and calls["count"] == 1:
                raise IndexError("unordered_map::at: key not found")
            return db_instance

        kuzu_mod = MagicMock()
        kuzu_mod.Database.side_effect = database_factory
        return kuzu_mod, calls

    def _make_kuzu_store_class(self):
        """Return a fake KuzuPropertyGraphStore class for monkeypatching."""

        class FakeKuzuPropertyGraphStore:
            def __init__(self, db, use_vector_index=False):
                self.db = db
                self._upserted_triplets = []
                self._upserted_nodes = []
                self._upserted_relations = []

            def upsert_nodes(self, nodes):
                self._upserted_nodes.extend(nodes)

            def upsert_relations(self, relations):
                self._upserted_relations.extend(relations)

        return FakeKuzuPropertyGraphStore

    def _install_mocks(self, monkeypatch, kuzu_mod, store_cls):
        """Patch sys.modules so the import inside _initialize_kuzu_store
        picks up our fakes instead of the real Kuzu library."""
        import sys
        import types

        monkeypatch.setitem(sys.modules, "kuzu", kuzu_mod)

        # The store import is `from llama_index.graph_stores.kuzu import
        # KuzuPropertyGraphStore` — patch that path.
        fake_pkg = types.ModuleType("llama_index.graph_stores.kuzu")
        fake_pkg.KuzuPropertyGraphStore = store_cls
        monkeypatch.setitem(sys.modules, "llama_index.graph_stores.kuzu", fake_pkg)

    @patch("agent_brain_server.storage.graph_store._graphrag_enabled")
    def test_clean_open_skips_recovery(
        self,
        mock_enabled,
        monkeypatch,
        persist_dir: Path,
    ):
        mock_enabled.return_value = True
        kuzu_mod, calls = self._make_kuzu_mock(fail_first=False)
        store_cls = self._make_kuzu_store_class()
        self._install_mocks(monkeypatch, kuzu_mod, store_cls)

        mgr = GraphStoreManager(persist_dir, store_type="kuzu")
        mgr.initialize()

        assert calls["count"] == 1  # opened exactly once
        assert mgr._recovered_from_corruption is False

    @patch("agent_brain_server.storage.graph_store._graphrag_enabled")
    def test_corruption_triggers_quarantine_and_retry(
        self,
        mock_enabled,
        monkeypatch,
        persist_dir: Path,
        kuzu_db_file: Path,
    ):
        mock_enabled.return_value = True
        kuzu_mod, calls = self._make_kuzu_mock(fail_first=True)
        store_cls = self._make_kuzu_store_class()
        self._install_mocks(monkeypatch, kuzu_mod, store_cls)

        mgr = GraphStoreManager(persist_dir, store_type="kuzu")
        mgr.initialize()

        # Database() called twice: once before quarantine, once after
        assert calls["count"] == 2
        # Original kuzu_db file moved aside
        assert not kuzu_db_file.exists()
        corrupted = list(persist_dir.glob("kuzu_db.corrupted-*"))
        assert len(corrupted) == 1
        assert corrupted[0].read_bytes().startswith(b"\x00\x01\x02")
        assert mgr._recovered_from_corruption is True

    @patch("agent_brain_server.storage.graph_store._graphrag_enabled")
    def test_corruption_with_wal_quarantines_both(
        self,
        mock_enabled,
        monkeypatch,
        persist_dir: Path,
        kuzu_db_file: Path,
    ):
        wal = persist_dir / "kuzu_db.wal"
        wal.write_bytes(b"wal-data")

        mock_enabled.return_value = True
        kuzu_mod, _ = self._make_kuzu_mock(fail_first=True)
        store_cls = self._make_kuzu_store_class()
        self._install_mocks(monkeypatch, kuzu_mod, store_cls)

        mgr = GraphStoreManager(persist_dir, store_type="kuzu")
        mgr.initialize()

        assert not wal.exists()
        wal_corrupted = list(persist_dir.glob("kuzu_db.wal.corrupted-*"))
        assert len(wal_corrupted) == 1

    @patch("agent_brain_server.storage.graph_store._graphrag_enabled")
    def test_recovery_replays_snapshot(
        self,
        mock_enabled,
        monkeypatch,
        persist_dir: Path,
        kuzu_db_file: Path,
        sample_triplets,
    ):
        # Pre-write a snapshot the recovery path should restore from
        snap_mgr = GraphSnapshotManager(persist_dir)
        snap_mgr.write(sample_triplets, source_job_id="job_prior")

        mock_enabled.return_value = True
        kuzu_mod, _ = self._make_kuzu_mock(fail_first=True)
        store_cls = self._make_kuzu_store_class()
        self._install_mocks(monkeypatch, kuzu_mod, store_cls)

        mgr = GraphStoreManager(persist_dir, store_type="kuzu")
        mgr.initialize()

        store = mgr._graph_store
        # Two triplets → 4 entity nodes (2 per triplet), 2 relations
        assert len(store._upserted_nodes) == 4
        assert len(store._upserted_relations) == 2
        labels = {r.label for r in store._upserted_relations}
        assert labels == {"calls", "extends"}
        assert mgr._relationship_count == 2

    @patch("agent_brain_server.storage.graph_store._graphrag_enabled")
    def test_recovery_with_no_snapshot_starts_empty(
        self,
        mock_enabled,
        monkeypatch,
        persist_dir: Path,
        kuzu_db_file: Path,
    ):
        mock_enabled.return_value = True
        kuzu_mod, _ = self._make_kuzu_mock(fail_first=True)
        store_cls = self._make_kuzu_store_class()
        self._install_mocks(monkeypatch, kuzu_mod, store_cls)

        mgr = GraphStoreManager(persist_dir, store_type="kuzu")
        mgr.initialize()  # should not raise

        assert mgr._graph_store is not None
        assert mgr._graph_store._upserted_relations == []

    @patch("agent_brain_server.storage.graph_store._graphrag_enabled")
    def test_double_failure_raises_structured_error(
        self,
        mock_enabled,
        monkeypatch,
        persist_dir: Path,
        kuzu_db_file: Path,
    ):
        mock_enabled.return_value = True

        # Database() raises every single time — quarantine doesn't help
        kuzu_mod = MagicMock()
        kuzu_mod.Database.side_effect = IndexError("unordered_map::at: key not found")
        store_cls = self._make_kuzu_store_class()
        self._install_mocks(monkeypatch, kuzu_mod, store_cls)

        mgr = GraphStoreManager(persist_dir, store_type="kuzu")
        with pytest.raises(RuntimeError, match="Failed to initialize Kuzu"):
            mgr.initialize()


class TestPreflightCheck:
    @patch("agent_brain_server.storage.graph_store._graphrag_enabled")
    def test_preflight_no_op_when_graphrag_disabled(
        self, mock_enabled, persist_dir: Path
    ):
        mock_enabled.return_value = False
        mgr = GraphStoreManager(persist_dir, store_type="kuzu")
        assert mgr.preflight_check() is False
        assert not mgr.is_initialized

    @patch("agent_brain_server.storage.graph_store._graphrag_enabled")
    def test_preflight_no_op_when_not_kuzu(self, mock_enabled, persist_dir: Path):
        mock_enabled.return_value = True
        mgr = GraphStoreManager(persist_dir, store_type="simple")
        assert mgr.preflight_check() is False

    @patch("agent_brain_server.storage.graph_store._graphrag_enabled")
    def test_preflight_initializes_when_kuzu(
        self,
        mock_enabled,
        monkeypatch,
        persist_dir: Path,
    ):
        mock_enabled.return_value = True

        recovery_test = TestCorruptionRecovery()
        kuzu_mod, calls = recovery_test._make_kuzu_mock(fail_first=False)
        store_cls = recovery_test._make_kuzu_store_class()
        recovery_test._install_mocks(monkeypatch, kuzu_mod, store_cls)

        mgr = GraphStoreManager(persist_dir, store_type="kuzu")
        assert mgr.preflight_check() is True
        assert mgr.is_initialized
        # Calling again should be a no-op
        calls_after_first = calls["count"]
        assert mgr.preflight_check() is True
        assert calls["count"] == calls_after_first
