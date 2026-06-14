"""Tests for doctor stale-graph WARN check + --fix restore action (Phase 64).

Covers all 5 behaviors per 64-03-PLAN.md:
1. Snapshot has MORE triplets than live kuzu: _check_graph_staleness returns WARN.
2. Live kuzu matches (or exceeds) snapshot: _check_graph_staleness returns OK.
3. store_type != kuzu OR no snapshot OR no kuzu DB: returns None (skip).
4. run_doctor() includes the staleness check; WARN keeps exit_code 0.
5. apply_safe_fixes on WARN: restores when server stopped; skips when running.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agent_brain_server.storage.graph_snapshot import (
    GraphSnapshotManager,
    SnapshotTriplet,
)

from agent_brain_cli.diagnostics import (
    SEVERITY_OK,
    SEVERITY_WARN,
    CheckResult,
    DoctorReport,
    _check_graph_staleness,
    apply_safe_fixes,
    run_doctor,
)


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """A minimal state dir with kuzu enabled in config.yaml."""
    sd = tmp_path / ".agent-brain"
    sd.mkdir()
    config_yaml = sd / "config.yaml"
    config_yaml.write_text(
        "graphrag:\n"
        "  enabled: true\n"
        "  store_type: kuzu\n"
    )
    return sd


@pytest.fixture
def graph_dir(state_dir: Path) -> Path:
    """The conventional graph_index directory under state_dir."""
    gd = state_dir / "data" / "graph_index"
    gd.mkdir(parents=True)
    return gd


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
        SnapshotTriplet(
            subject="ModuleA",
            predicate="imports",
            object="ModuleB",
        ),
    ]


def _seed_snapshot(graph_dir: Path, triplets: list[SnapshotTriplet]) -> Path:
    """Write a snapshot and return its path."""
    mgr = GraphSnapshotManager(graph_dir)
    return mgr.write(triplets)


def _seed_kuzu_db(graph_dir: Path) -> Path:
    """Create a fake (non-empty) kuzu_db file to satisfy the existence check."""
    kuzu_db = graph_dir / "kuzu_db"
    kuzu_db.mkdir()  # kuzu_db is a directory in real usage
    return kuzu_db


def _mock_live_count(count: int) -> MagicMock:
    """Build a mock kuzu.Connection that returns `count` for COUNT(r) query."""
    conn_mock = MagicMock()
    result_mock = MagicMock()
    result_mock.get_next.return_value = [count]
    conn_mock.execute.return_value = result_mock
    return conn_mock


class TestCheckGraphStalenessWarn:
    """Test 1: Snapshot > live kuzu contents -> WARN."""

    def test_stale_condition_returns_warn(
        self,
        state_dir: Path,
        graph_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        _seed_snapshot(graph_dir, sample_triplets)  # 3 triplets in snapshot
        _seed_kuzu_db(graph_dir)

        # Live kuzu has 0 relationships (stale after rollback)
        live_count = 0

        with (
            patch("agent_brain_cli.diagnostics._read_graphrag_block",
                  return_value={"enabled": True, "store_type": "kuzu"}),
            patch("agent_brain_cli.diagnostics._graph_index_dir",
                  return_value=graph_dir),
            patch("agent_brain_cli.diagnostics._get_live_kuzu_relationship_count",
                  return_value=live_count),
        ):
            result = _check_graph_staleness(state_dir)

        assert result is not None
        assert result.status == SEVERITY_WARN
        assert result.name == "graph_staleness"
        # Message mentions the count difference
        assert "3" in result.message  # snapshot_count
        assert "0" in result.message  # live_count
        # Fix hint names the restore command
        assert result.fix is not None
        assert "restore-from-snapshot" in result.fix
        # Details contain the counts
        assert result.details.get("snapshot_triplets") == 3
        assert result.details.get("live_relationships") == 0

    def test_warn_includes_restore_command_hint(
        self,
        state_dir: Path,
        graph_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        _seed_snapshot(graph_dir, sample_triplets)
        _seed_kuzu_db(graph_dir)

        with (
            patch("agent_brain_cli.diagnostics._read_graphrag_block",
                  return_value={"enabled": True, "store_type": "kuzu"}),
            patch("agent_brain_cli.diagnostics._graph_index_dir",
                  return_value=graph_dir),
            patch("agent_brain_cli.diagnostics._get_live_kuzu_relationship_count",
                  return_value=0),
        ):
            result = _check_graph_staleness(state_dir)

        assert result is not None
        assert "graph restore-from-snapshot" in (result.fix or "")


class TestCheckGraphStalenessOk:
    """Test 2: Live kuzu matches or exceeds snapshot -> OK."""

    def test_consistent_graph_returns_ok(
        self,
        state_dir: Path,
        graph_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        _seed_snapshot(graph_dir, sample_triplets)  # 3 triplets
        _seed_kuzu_db(graph_dir)

        # Live kuzu has same or more relationships -> OK
        live_count = 3

        with (
            patch("agent_brain_cli.diagnostics._read_graphrag_block",
                  return_value={"enabled": True, "store_type": "kuzu"}),
            patch("agent_brain_cli.diagnostics._graph_index_dir",
                  return_value=graph_dir),
            patch("agent_brain_cli.diagnostics._get_live_kuzu_relationship_count",
                  return_value=live_count),
        ):
            result = _check_graph_staleness(state_dir)

        assert result is not None
        assert result.status == SEVERITY_OK
        assert result.name == "graph_staleness"

    def test_live_exceeds_snapshot_returns_ok(
        self,
        state_dir: Path,
        graph_dir: Path,
        sample_triplets: list[SnapshotTriplet],
    ) -> None:
        _seed_snapshot(graph_dir, sample_triplets[:1])  # 1 triplet in snapshot
        _seed_kuzu_db(graph_dir)

        # Live kuzu has more relationships than snapshot -> OK
        live_count = 5

        with (
            patch("agent_brain_cli.diagnostics._read_graphrag_block",
                  return_value={"enabled": True, "store_type": "kuzu"}),
            patch("agent_brain_cli.diagnostics._graph_index_dir",
                  return_value=graph_dir),
            patch("agent_brain_cli.diagnostics._get_live_kuzu_relationship_count",
                  return_value=live_count),
        ):
            result = _check_graph_staleness(state_dir)

        assert result is not None
        assert result.status == SEVERITY_OK


class TestCheckGraphStalenessSkipped:
    """Test 3: Returns None when check is not applicable."""

    def test_non_kuzu_store_returns_none(
        self, state_dir: Path, graph_dir: Path
    ) -> None:
        with (
            patch("agent_brain_cli.diagnostics._read_graphrag_block",
                  return_value={"enabled": True, "store_type": "simple"}),
        ):
            result = _check_graph_staleness(state_dir)
        assert result is None

    def test_no_graphrag_block_returns_none(
        self, state_dir: Path
    ) -> None:
        with (
            patch("agent_brain_cli.diagnostics._read_graphrag_block",
                  return_value=None),
        ):
            result = _check_graph_staleness(state_dir)
        assert result is None

    def test_no_snapshot_returns_none(
        self, state_dir: Path, graph_dir: Path
    ) -> None:
        # No snapshot written — snapshots/ dir does not exist
        _seed_kuzu_db(graph_dir)

        with (
            patch("agent_brain_cli.diagnostics._read_graphrag_block",
                  return_value={"enabled": True, "store_type": "kuzu"}),
            patch("agent_brain_cli.diagnostics._graph_index_dir",
                  return_value=graph_dir),
        ):
            result = _check_graph_staleness(state_dir)
        assert result is None

    def test_no_kuzu_db_returns_none(
        self, state_dir: Path, graph_dir: Path, sample_triplets: list[SnapshotTriplet]
    ) -> None:
        # Snapshot exists but kuzu_db does not
        _seed_snapshot(graph_dir, sample_triplets)

        with (
            patch("agent_brain_cli.diagnostics._read_graphrag_block",
                  return_value={"enabled": True, "store_type": "kuzu"}),
            patch("agent_brain_cli.diagnostics._graph_index_dir",
                  return_value=graph_dir),
        ):
            result = _check_graph_staleness(state_dir)
        assert result is None


class TestRunDoctorIncludesStalenessCheck:
    """Test 4: run_doctor includes staleness check; WARN keeps exit_code 0."""

    def test_stale_graph_warn_in_report_exit_code_zero(
        self, tmp_path: Path
    ) -> None:
        """A WARN (not FAIL) keeps exit_code 0."""
        stale_check = CheckResult(
            "graph_staleness",
            SEVERITY_WARN,
            "Live kuzu graph has 0 relationships but the latest snapshot has 3",
            fix="Run `agent-brain graph restore-from-snapshot`",
            details={"live_relationships": 0, "snapshot_triplets": 3},
        )

        # Verify WARN does not set exit_code to 1
        report = DoctorReport(
            project_root=str(tmp_path),
            state_dir=str(tmp_path / ".agent-brain"),
            state_dir_exists=True,
            runtime_file=None,
            server_url="http://127.0.0.1:8000",
            checks=[stale_check],
        )
        assert report.exit_code == 0

    def test_run_doctor_calls_staleness_check(self, tmp_path: Path) -> None:
        """run_doctor invokes _check_graph_staleness and includes result."""
        stale_check = CheckResult(
            "graph_staleness",
            SEVERITY_WARN,
            "Stale graph detected",
            fix="Run restore",
        )

        # Patch the whole run_doctor to observe that _check_graph_staleness
        # is wired into the report
        with patch(
            "agent_brain_cli.diagnostics._check_graph_staleness",
            return_value=stale_check,
        ) as mock_check:
            # patch everything else run_doctor needs
            with (
                patch("agent_brain_cli.diagnostics.resolve_project_root_with_strategy",
                      return_value=(tmp_path, "cwd_fallback")),
                patch("agent_brain_cli.diagnostics.get_server_url",
                      return_value="http://127.0.0.1:8000"),
                patch("agent_brain_cli.diagnostics._check_python",
                      return_value=CheckResult("python_version", SEVERITY_OK, "ok")),
                patch("agent_brain_cli.diagnostics._check_version",
                      return_value=CheckResult("cli_version", SEVERITY_OK, "ok")),
                patch(
                    "agent_brain_cli.diagnostics._check_project_init",
                    return_value=CheckResult(
                        "project_initialized", SEVERITY_OK, "ok"
                    ),
                ),
                patch(
                    "agent_brain_cli.diagnostics._check_provider_config",
                    return_value=CheckResult("provider_config", SEVERITY_OK, "ok"),
                ),
                patch("agent_brain_cli.diagnostics._check_api_keys",
                      return_value=[]),
                patch("agent_brain_cli.diagnostics._check_graph_store_health",
                      return_value=None),
                patch(
                    "agent_brain_cli.diagnostics._check_gitignore",
                    return_value=CheckResult(
                        "gitignore_state_dir", SEVERITY_OK, "ok"
                    ),
                ),
                patch("agent_brain_cli.diagnostics._check_server",
                      return_value=CheckResult("server", SEVERITY_OK, "ok")),
                patch("agent_brain_cli.diagnostics.load_config",
                      return_value=None),
            ):
                report = run_doctor()

        mock_check.assert_called_once()
        # The stale_check result must appear in the report checks
        staleness_checks = [c for c in report.checks if c.name == "graph_staleness"]
        assert len(staleness_checks) == 1
        assert staleness_checks[0].status == SEVERITY_WARN
        # WARN does not affect exit_code
        assert report.exit_code == 0


class TestApplySafeFixesGraphStaleness:
    """Test 5: apply_safe_fixes restores when stopped; skips when running."""

    def _make_stale_report(
        self, tmp_path: Path, server_running: bool = False
    ) -> DoctorReport:
        state_dir = tmp_path / ".agent-brain"
        state_dir.mkdir(exist_ok=True)
        if server_running:
            (state_dir / "server.lock").write_text("pid=1234")
        stale_check = CheckResult(
            "graph_staleness",
            SEVERITY_WARN,
            "Live kuzu graph has 0 relationships but latest snapshot has 3",
            fix="Run `agent-brain graph restore-from-snapshot`",
            details={"live_relationships": 0, "snapshot_triplets": 3},
        )
        return DoctorReport(
            project_root=str(tmp_path),
            state_dir=str(state_dir),
            state_dir_exists=True,
            runtime_file=None,
            server_url="http://127.0.0.1:8000",
            checks=[stale_check],
        )

    def test_fix_calls_restore_when_server_stopped(
        self, tmp_path: Path
    ) -> None:
        report = self._make_stale_report(tmp_path, server_running=False)
        mgr_mock = MagicMock()
        mgr_mock.restore_from_snapshot.return_value = 3

        with (
            patch("agent_brain_cli.diagnostics.GraphStoreManager",
                  return_value=mgr_mock),
            patch("agent_brain_cli.diagnostics._graph_index_dir",
                  return_value=tmp_path / ".agent-brain" / "data" / "graph_index"),
        ):
            actions = apply_safe_fixes(report)

        mgr_mock.restore_from_snapshot.assert_called_once_with(None)
        assert any("3" in a and ("triplet" in a.lower() or "restore" in a.lower())
                   for a in actions)

    def test_fix_skips_restore_when_server_running(
        self, tmp_path: Path
    ) -> None:
        report = self._make_stale_report(tmp_path, server_running=True)
        mgr_mock = MagicMock()

        with (
            patch("agent_brain_cli.diagnostics.GraphStoreManager",
                  return_value=mgr_mock),
            patch("agent_brain_cli.diagnostics._graph_index_dir",
                  return_value=tmp_path / ".agent-brain" / "data" / "graph_index"),
        ):
            actions = apply_safe_fixes(report)

        mgr_mock.restore_from_snapshot.assert_not_called()
        # A "skipped" message is recorded
        assert any("skip" in a.lower() or "server" in a.lower() or "stop" in a.lower()
                   for a in actions)
