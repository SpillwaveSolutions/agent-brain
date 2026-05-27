"""Tests for GraphSnapshotManager (Issue #166).

Snapshots are the durability safety net for graph triplets: a kill
mid-indexing should never lose more than the most recent snapshot's worth
of work. These tests cover the write/list/load/rotate lifecycle plus the
corruption-recovery path used by the graph store on startup.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent_brain_server.storage.graph_snapshot import (
    DEFAULT_KEEP,
    SCHEMA_VERSION,
    GraphSnapshotManager,
    SnapshotTriplet,
)


@pytest.fixture
def snap_dir(tmp_path: Path) -> Path:
    """Persist dir that doesn't yet contain a snapshots/ subdir."""
    return tmp_path / "graph_index"


@pytest.fixture
def manager(snap_dir: Path) -> GraphSnapshotManager:
    return GraphSnapshotManager(snap_dir)


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
            predicate="inherits",
            object="ClassY",
        ),
    ]


def _fake_now(offset_seconds: int = 0) -> datetime:
    return datetime(2026, 5, 26, 21, 5, 32, tzinfo=timezone.utc) + timedelta(
        seconds=offset_seconds
    )


class TestWrite:
    def test_creates_snapshot_dir_on_first_write(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        assert not manager.snapshot_dir.exists()
        manager.write(sample_triplets)
        assert manager.snapshot_dir.is_dir()

    def test_writes_valid_json_payload(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        path = manager.write(
            sample_triplets,
            source_job_id="job_abc",
            kuzu_version="0.11.3",
            now=_fake_now(),
        )

        payload = json.loads(path.read_text())
        assert payload["schema_version"] == SCHEMA_VERSION
        assert payload["source_job_id"] == "job_abc"
        assert payload["kuzu_version"] == "0.11.3"
        assert payload["triplet_count"] == 2
        assert payload["created_at"].startswith("2026-05-26T21:05:32")
        assert len(payload["triplets"]) == 2
        assert payload["triplets"][0]["subject"] == "FunctionA"
        assert payload["triplets"][0]["subject_type"] == "Function"
        assert payload["triplets"][1]["subject_type"] is None

    def test_empty_triplets_writes_zero_count_snapshot(
        self, manager: GraphSnapshotManager
    ):
        path = manager.write([], now=_fake_now())
        payload = json.loads(path.read_text())
        assert payload["triplet_count"] == 0
        assert payload["triplets"] == []

    def test_atomic_write_leaves_no_tmp_file(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        manager.write(sample_triplets, now=_fake_now())
        leftover = list(manager.snapshot_dir.glob("*.tmp"))
        assert leftover == []

    def test_clock_collision_uses_sequence_suffix(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        moment = _fake_now()
        first = manager.write(sample_triplets, now=moment)
        second = manager.write(sample_triplets, now=moment)
        third = manager.write(sample_triplets, now=moment)
        assert {first.name, second.name, third.name} == {
            "snapshot-2026-05-26T21-05-32Z.json",
            "snapshot-2026-05-26T21-05-32Z-001.json",
            "snapshot-2026-05-26T21-05-32Z-002.json",
        }


class TestListAndLatest:
    def test_empty_dir_returns_empty_list(self, manager: GraphSnapshotManager):
        assert manager.list_snapshots() == []
        assert manager.latest() is None

    def test_listing_is_newest_first(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        oldest = manager.write(sample_triplets, now=_fake_now(0))
        middle = manager.write(sample_triplets, now=_fake_now(60))
        newest = manager.write(sample_triplets, now=_fake_now(120))

        snaps = manager.list_snapshots()
        assert snaps == [newest, middle, oldest]
        assert manager.latest() == newest

    def test_ignores_unrelated_files(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        manager.write(sample_triplets, now=_fake_now())
        # Drop a junk file in the snapshot dir
        (manager.snapshot_dir / "README.md").write_text("not a snapshot")
        (manager.snapshot_dir / "snapshot-garbage.json").write_text("{}")
        snaps = manager.list_snapshots()
        assert len(snaps) == 1


class TestLoad:
    def test_round_trip(self, manager: GraphSnapshotManager, sample_triplets):
        path = manager.write(sample_triplets, now=_fake_now())
        loaded = manager.load(path)
        assert loaded == sample_triplets

    def test_bad_json_raises_value_error(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        path = manager.write(sample_triplets, now=_fake_now())
        path.write_text("{ not json")
        with pytest.raises(ValueError, match="not valid JSON"):
            manager.load(path)

    def test_wrong_schema_version_raises(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        path = manager.write(sample_triplets, now=_fake_now())
        payload = json.loads(path.read_text())
        payload["schema_version"] = 999
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="unsupported schema_version"):
            manager.load(path)

    def test_missing_triplets_key_raises(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        path = manager.write(sample_triplets, now=_fake_now())
        path.write_text(json.dumps({"schema_version": SCHEMA_VERSION}))
        with pytest.raises(ValueError, match="missing 'triplets'"):
            manager.load(path)

    def test_triplet_missing_required_key_raises(self, manager: GraphSnapshotManager):
        path = manager.write([], now=_fake_now())
        payload = json.loads(path.read_text())
        payload["triplets"] = [{"subject": "A", "predicate": "calls"}]  # no object
        path.write_text(json.dumps(payload))
        with pytest.raises(ValueError, match="missing required key"):
            manager.load(path)


class TestLoadLatestValid:
    def test_returns_none_when_empty(self, manager: GraphSnapshotManager):
        assert manager.load_latest_valid() is None

    def test_returns_newest_valid_snapshot(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        manager.write(sample_triplets, now=_fake_now(0))
        newest = manager.write(sample_triplets, now=_fake_now(60))
        result = manager.load_latest_valid()
        assert result is not None
        path, triplets = result
        assert path == newest
        assert triplets == sample_triplets

    def test_skips_corrupted_newest_and_falls_back(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        oldest = manager.write(sample_triplets, now=_fake_now(0))
        newest = manager.write(sample_triplets, now=_fake_now(60))
        # Corrupt the newest
        newest.write_text("{ broken json")

        result = manager.load_latest_valid()
        assert result is not None
        path, triplets = result
        assert path == oldest
        assert triplets == sample_triplets

        # The corrupted snapshot should have been renamed so it isn't
        # retried next time.
        assert not newest.exists()
        assert (newest.parent / (newest.name + ".corrupted")).exists()


class TestRotate:
    def test_keep_one_of_five(self, manager: GraphSnapshotManager, sample_triplets):
        paths = [
            manager.write(sample_triplets, now=_fake_now(i * 60)) for i in range(5)
        ]
        deleted = manager.rotate(keep=1)
        assert deleted == 4
        remaining = manager.list_snapshots()
        assert remaining == [paths[-1]]

    def test_keep_default_three(self, manager: GraphSnapshotManager, sample_triplets):
        for i in range(5):
            manager.write(sample_triplets, now=_fake_now(i * 60))
        manager.rotate()  # default keep=3
        assert len(manager.list_snapshots()) == DEFAULT_KEEP

    def test_rejects_keep_below_one(self, manager: GraphSnapshotManager):
        with pytest.raises(ValueError):
            manager.rotate(keep=0)

    def test_noop_when_fewer_than_keep(
        self, manager: GraphSnapshotManager, sample_triplets
    ):
        manager.write(sample_triplets, now=_fake_now())
        deleted = manager.rotate(keep=10)
        assert deleted == 0
        assert len(manager.list_snapshots()) == 1
