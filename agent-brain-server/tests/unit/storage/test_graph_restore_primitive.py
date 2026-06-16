"""Tests for GraphStoreManager.restore_from_snapshot and plan_restore (Phase 64).

Covers the public restore-on-demand primitives — distinct from the private
``_restore_from_snapshot_if_available`` which only runs on corruption recovery.

All 5 behaviors per 64-03-PLAN.md:
1. restore_from_snapshot(None) replays the latest valid snapshot, returns triplet count.
2. restore_from_snapshot(Path) replays the specified snapshot file.
3. restore_from_snapshot(None) when no snapshot exists returns 0, does not raise.
4. plan_restore returns (path, count) WITHOUT applying triplets (store unchanged).
5. restore_from_snapshot does NOT require _recovered_from_corruption=True.
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
    reset_graph_store_manager,
)


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:  # type: ignore[return]
    reset_graph_store_manager()
    yield
    reset_graph_store_manager()


@pytest.fixture
def persist_dir(tmp_path: Path) -> Path:
    d = tmp_path / "graph_index"
    d.mkdir()
    return d


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


def _make_manager_with_mock_store(persist_dir: Path) -> GraphStoreManager:
    """Create a GraphStoreManager with a mocked graph store backend."""
    mgr = GraphStoreManager(persist_dir, store_type="simple")
    mgr._initialized = True
    mgr._graph_store = MagicMock()
    # Mock upsert_triplet to always succeed
    mgr._graph_store.upsert_triplet = MagicMock(return_value=None)
    return mgr


class TestRestoreFromSnapshotLatest:
    """Test 1: restore_from_snapshot(None) replays latest valid snapshot."""

    def test_restore_none_replays_latest_and_returns_count(
        self,
        persist_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        # Seed a snapshot.
        snap_mgr = GraphSnapshotManager(persist_dir)
        snap_mgr.write(sample_triplets)

        mgr = _make_manager_with_mock_store(persist_dir)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ):
            count = mgr.restore_from_snapshot(None)

        assert count == len(sample_triplets)
        # Verify the store received upsert calls
        assert mgr._graph_store.upsert_triplet.call_count == len(sample_triplets)

    def test_restore_updates_relationship_count(
        self,
        persist_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        snap_mgr = GraphSnapshotManager(persist_dir)
        snap_mgr.write(sample_triplets)

        mgr = _make_manager_with_mock_store(persist_dir)
        mgr._relationship_count = 0

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ):
            count = mgr.restore_from_snapshot(None)

        assert mgr._relationship_count == count
        assert mgr._last_updated is not None


class TestRestoreFromSnapshotExplicitPath:
    """Test 2: restore_from_snapshot(Path) replays that specific file."""

    def test_restore_explicit_path_replays_exactly(
        self,
        persist_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        snap_mgr = GraphSnapshotManager(persist_dir)
        # Write two snapshots
        snap_mgr.write(sample_triplets[:1])  # older: 1 triplet
        import time

        time.sleep(0.01)  # ensure mtime difference
        snap_path = snap_mgr.write(sample_triplets)  # newest: 2 triplets

        mgr = _make_manager_with_mock_store(persist_dir)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ):
            count = mgr.restore_from_snapshot(snap_path)

        assert count == len(sample_triplets)

    def test_restore_bad_path_raises_value_error(
        self,
        persist_dir: Path,
    ) -> None:
        bad_path = persist_dir / "nonexistent_snapshot.json"
        mgr = _make_manager_with_mock_store(persist_dir)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ):
            with pytest.raises((OSError, ValueError, RuntimeError)):
                mgr.restore_from_snapshot(bad_path)


class TestRestoreFromSnapshotNoSnapshot:
    """Test 3: restore_from_snapshot(None) when no snapshot exists returns 0."""

    def test_restore_no_snapshot_returns_zero_no_raise(
        self,
        persist_dir: Path,
    ) -> None:
        mgr = _make_manager_with_mock_store(persist_dir)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ):
            count = mgr.restore_from_snapshot(None)

        assert count == 0
        # Store should not have been called
        assert mgr._graph_store.upsert_triplet.call_count == 0


class TestPlanRestore:
    """Test 4: plan_restore returns (path, count) without mutating the store."""

    def test_plan_restore_returns_path_and_count_no_mutation(
        self,
        persist_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        snap_mgr = GraphSnapshotManager(persist_dir)
        snap_path = snap_mgr.write(sample_triplets)

        mgr = _make_manager_with_mock_store(persist_dir)
        initial_rel_count = mgr._relationship_count

        result = mgr.plan_restore(None)

        assert result is not None
        path, count = result
        assert path == snap_path
        assert count == len(sample_triplets)
        # Store was NOT mutated
        assert mgr._graph_store.upsert_triplet.call_count == 0
        assert mgr._relationship_count == initial_rel_count

    def test_plan_restore_explicit_path(
        self,
        persist_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        snap_mgr = GraphSnapshotManager(persist_dir)
        snap_path = snap_mgr.write(sample_triplets)

        mgr = _make_manager_with_mock_store(persist_dir)
        result = mgr.plan_restore(snap_path)

        assert result is not None
        path, count = result
        assert path == snap_path
        assert count == len(sample_triplets)

    def test_plan_restore_no_snapshot_returns_none(
        self,
        persist_dir: Path,
    ) -> None:
        mgr = _make_manager_with_mock_store(persist_dir)
        result = mgr.plan_restore(None)
        assert result is None


class TestRestoreDoesNotRequireCorruptionFlag:
    """Test 5: restore_from_snapshot does NOT require _recovered_from_corruption."""

    def test_restore_works_without_corruption_flag(
        self,
        persist_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        snap_mgr = GraphSnapshotManager(persist_dir)
        snap_mgr.write(sample_triplets)

        mgr = _make_manager_with_mock_store(persist_dir)
        # Explicitly confirm corruption flag is False/absent
        assert not getattr(mgr, "_recovered_from_corruption", False)

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ):
            count = mgr.restore_from_snapshot(None)

        # Should have restored even without the corruption flag
        assert count == len(sample_triplets)

    def test_private_restore_method_requires_corruption_flag(
        self,
        persist_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        """The PRIVATE _restore_from_snapshot_if_available still requires the flag."""
        snap_mgr = GraphSnapshotManager(persist_dir)
        snap_mgr.write(sample_triplets)

        mgr = _make_manager_with_mock_store(persist_dir)
        # Private method returns 0 when flag is not set
        count = mgr._restore_from_snapshot_if_available()
        assert count == 0

    def test_public_restore_ignores_corruption_flag(
        self,
        persist_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        """Public restore_from_snapshot works regardless of corruption flag."""
        snap_mgr = GraphSnapshotManager(persist_dir)
        snap_mgr.write(sample_triplets)

        mgr = _make_manager_with_mock_store(persist_dir)
        # Ensure corruption flag is False
        mgr._recovered_from_corruption = False

        with patch(
            "agent_brain_server.storage.graph_store._graphrag_enabled",
            return_value=True,
        ):
            count = mgr.restore_from_snapshot(None)

        assert count == len(sample_triplets)
