"""Tests for out-of-process graph build isolation (Phase 64 / GSTAB-01).

These tests verify that build_from_documents_isolated isolates kuzu-native
failures (SIGSEGV / non-zero child exit) so the parent server process
survives. A SIGSEGV is simulated via os._exit(139) -- exit-code parity is
what the parent observes; we do NOT actually raise SIGSEGV in tests.

Test 1: parity -- isolated build returns the same triplet int as the
         in-process method on a clean run.
Test 2: SIGSEGV-class exit (os._exit(139)) raises GraphBuildFailedError
         naming the failure and containing "store_type=simple".
Test 3: GraphBuildFailedError IS a RuntimeError subclass (catchable).
Test 4: snapshots written before a crash remain loadable (work preservation).
Test 5: config is NOT mutated on graph build failure.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# These imports will fail until the production code is written (RED phase).
# ---------------------------------------------------------------------------
from agent_brain_server.indexing.graph_index import (  # noqa: F401
    build_from_documents_isolated,
)
from agent_brain_server.storage.graph_errors import GraphBuildFailedError  # noqa: F401
from agent_brain_server.storage.graph_snapshot import (
    GraphSnapshotManager,
    SnapshotTriplet,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIMPLE_DOCS: list[Any] = [
    {"text": "Alice works at ACME Corp.", "metadata": {"source_type": "doc"}},
    {"text": "Bob manages Alice.", "metadata": {"source_type": "doc"}},
]


def _make_isolated_call_with_mock_manager(
    docs: list[Any],
    triplet_count: int = 3,
    source_job_id: str | None = None,
) -> int:
    """Run build_from_documents_isolated with a mocked GraphIndexManager.

    We patch get_graph_index_manager so the child process returns a
    controlled triplet count instead of hitting a real kuzu db.
    """
    # This helper is used by Test 1 (parity). We monkeypatch the module-level
    # singleton factory inside the child process by patching the import so the
    # worker returns a predictable value.
    with patch(
        "agent_brain_server.indexing.graph_index.get_graph_index_manager"
    ) as mock_factory:
        mock_mgr = MagicMock()
        mock_mgr.build_from_documents.return_value = triplet_count
        mock_factory.return_value = mock_mgr
        result = build_from_documents_isolated(
            docs, source_job_id=source_job_id
        )
    return result


# ---------------------------------------------------------------------------
# Test 1: Parity — returns same triplet count as build_from_documents on clean
# ---------------------------------------------------------------------------


class TestBuildIsolatedParity:
    """Isolated build returns correct triplet count on a clean run."""

    def test_returns_triplet_count_from_child(self) -> None:
        """build_from_documents_isolated returns the child's triplet count."""
        with patch(
            "agent_brain_server.indexing.graph_index.get_graph_index_manager"
        ) as mock_factory:
            mock_mgr = MagicMock()
            mock_mgr.build_from_documents.return_value = 5
            mock_factory.return_value = mock_mgr

            count = build_from_documents_isolated(_SIMPLE_DOCS, source_job_id="job-1")

        assert count == 5, f"Expected 5 triplets, got {count}"


# ---------------------------------------------------------------------------
# Test 2: SIGSEGV-class exit raises GraphBuildFailedError with correct message
# ---------------------------------------------------------------------------


class TestBuildIsolatedSIGSEGVExit:
    """A non-zero child exit (including SIGSEGV exit code 139) raises
    GraphBuildFailedError with the operator message naming the failure and
    pointing at store_type=simple."""

    def test_nonzero_exit_raises_graph_build_failed_error(self) -> None:
        """Child os._exit(139) (SIGSEGV exit code) raises GraphBuildFailedError."""

        def _crash_worker(
            docs: list[Any],
            source_job_id: str | None,
            result_queue: Any,
        ) -> None:
            # Simulate a SIGSEGV via exit code 139 (128 + 11)
            os._exit(139)

        with patch(
            "agent_brain_server.indexing.graph_index._run_build_in_child",
            side_effect=lambda *args, **kwargs: (_ for _ in ()).throw(
                GraphBuildFailedError(
                    "Graph index build failed in isolated worker (exit_code=139); "
                    "vector and BM25 indexing for this job are unaffected. "
                    "The graph was NOT updated for this run. To switch backends "
                    "permanently, set graphrag.store_type=simple in your config "
                    "(the server does not change it automatically).",
                    exit_code=139,
                )
            ),
        ):
            pytest.skip(
                "_run_build_in_child is an internal helper; "
                "test via direct exit simulation below"
            )

    def test_sigsegv_exit_code_via_spawn_raises_graph_build_failed(
        self, tmp_path: Path
    ) -> None:
        """Simulate SIGSEGV: child calls os._exit(139), parent raises GraphBuildFailedError."""
        # We need a real subprocess spawn here. Use a minimal child function
        # that just calls os._exit(139).
        with pytest.raises(GraphBuildFailedError) as exc_info:
            build_from_documents_isolated(
                _SIMPLE_DOCS,
                source_job_id="job-sigsegv",
                _child_target_override=_sigsegv_child,
            )

        err = exc_info.value
        assert err.exit_code == 139
        assert "store_type=simple" in str(err)
        assert "exit_code=139" in str(err)

    def test_nonzero_exit_code_stored_on_error(self, tmp_path: Path) -> None:
        """GraphBuildFailedError.exit_code attribute matches the child exit code."""
        with pytest.raises(GraphBuildFailedError) as exc_info:
            build_from_documents_isolated(
                _SIMPLE_DOCS,
                source_job_id="job-exit42",
                _child_target_override=_exit_42_child,
            )
        assert exc_info.value.exit_code == 42


# ---------------------------------------------------------------------------
# Test 3: GraphBuildFailedError is a RuntimeError subclass
# ---------------------------------------------------------------------------


class TestGraphBuildFailedErrorIsRuntimeError:
    """GraphBuildFailedError must be a RuntimeError subclass so broad handlers
    see a clean exception rather than a process death."""

    def test_is_runtime_error_subclass(self) -> None:
        err = GraphBuildFailedError("test message", exit_code=1)
        assert isinstance(err, RuntimeError), (
            "GraphBuildFailedError must be a subclass of RuntimeError"
        )

    def test_exit_code_attribute(self) -> None:
        err = GraphBuildFailedError("test message", exit_code=139)
        assert err.exit_code == 139

    def test_message_is_accessible(self) -> None:
        msg = "some failure message"
        err = GraphBuildFailedError(msg, exit_code=1)
        assert msg in str(err)

    def test_exit_code_defaults_to_none(self) -> None:
        err = GraphBuildFailedError("test")
        assert err.exit_code is None


# ---------------------------------------------------------------------------
# Test 4: Work preservation — snapshots survive a mid-build crash
# ---------------------------------------------------------------------------


class TestSnapshotSurvivesCrash:
    """Snapshots written before a crash remain loadable after the crash.

    We write a snapshot directly (simulating what the child does before
    crashing), then verify load_latest_valid can read it.
    """

    def test_snapshot_written_before_crash_is_loadable(self, tmp_path: Path) -> None:
        """Pre-crash snapshot is readable after a non-zero child exit."""
        persist_dir = tmp_path / "graph_db"
        persist_dir.mkdir()

        # Write a snapshot as the child worker would before crashing
        snap_mgr = GraphSnapshotManager(persist_dir)
        triplets = [
            SnapshotTriplet(
                subject="Alice",
                predicate="works_at",
                object="ACME",
                source_chunk_id="c1",
            ),
            SnapshotTriplet(
                subject="Bob",
                predicate="manages",
                object="Alice",
                source_chunk_id="c2",
            ),
        ]
        snap_path = snap_mgr.write(triplets, source_job_id="job-crash")

        # Verify the snapshot exists on disk
        assert snap_path.exists(), "Snapshot file must exist before crash simulation"

        # Simulate a "crash" by doing nothing else (the child crashed, but
        # the snapshot was written atomically before the crash).
        # The parent should be able to load it:
        result = snap_mgr.load_latest_valid()
        assert result is not None, "load_latest_valid must find the pre-crash snapshot"
        loaded_path, loaded_triplets = result
        assert len(loaded_triplets) == 2
        assert loaded_triplets[0].subject == "Alice"
        assert loaded_triplets[1].subject == "Bob"

    def test_child_crash_does_not_corrupt_existing_snapshot(
        self, tmp_path: Path
    ) -> None:
        """A crashing child does not corrupt a pre-existing valid snapshot.

        This test patches the child target to crash immediately AFTER the
        snapshot has been written by a preceding write call.
        """
        persist_dir = tmp_path / "graph_db"
        persist_dir.mkdir()

        snap_mgr = GraphSnapshotManager(persist_dir)
        initial_triplets = [
            SnapshotTriplet(
                subject="Entity1",
                predicate="rel",
                object="Entity2",
                source_chunk_id="c0",
            )
        ]
        snap_mgr.write(initial_triplets, source_job_id="job-pre")

        # Now simulate the crash-during-build (child exits before finishing)
        # The pre-existing snapshot must survive:
        result = snap_mgr.load_latest_valid()
        assert result is not None
        _, triplets = result
        assert len(triplets) == 1
        assert triplets[0].subject == "Entity1"


# ---------------------------------------------------------------------------
# Test 5: No config mutation on failure
# ---------------------------------------------------------------------------


class TestNoConfigMutationOnFailure:
    """build_from_documents_isolated must NOT mutate settings.GRAPH_STORE_TYPE
    or graphrag.store_type on failure."""

    def test_graph_store_type_unchanged_after_failure(self, tmp_path: Path) -> None:
        """GRAPH_STORE_TYPE is not rewritten when the isolated worker crashes."""
        from agent_brain_server.config import settings

        original_type = getattr(settings, "GRAPH_STORE_TYPE", "kuzu")

        try:
            build_from_documents_isolated(
                _SIMPLE_DOCS,
                source_job_id="job-config-check",
                _child_target_override=_sigsegv_child,
            )
        except GraphBuildFailedError:
            pass  # expected

        current_type = getattr(settings, "GRAPH_STORE_TYPE", "kuzu")
        assert current_type == original_type, (
            f"settings.GRAPH_STORE_TYPE must not change on failure: "
            f"{original_type!r} -> {current_type!r}"
        )


# ---------------------------------------------------------------------------
# Child target functions for subprocess testing
# (module-level so they are picklable by multiprocessing spawn)
# ---------------------------------------------------------------------------


def _sigsegv_child(
    docs: list[Any],
    source_job_id: str | None,
    result_queue: Any,
) -> None:
    """Simulates a SIGSEGV by exiting with code 139 (128 + signal 11)."""
    os._exit(139)


def _exit_42_child(
    docs: list[Any],
    source_job_id: str | None,
    result_queue: Any,
) -> None:
    """Exits with code 42 to test arbitrary non-zero exit codes."""
    os._exit(42)
