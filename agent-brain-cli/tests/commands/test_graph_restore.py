"""Tests for `agent-brain graph restore-from-snapshot` CLI command (Phase 64).

Covers all 6 behaviors per 64-03-PLAN.md:
1. --dry-run prints plan and exits 0 WITHOUT calling restore_from_snapshot.
2. --yes performs restore non-interactively; restore_from_snapshot called once.
3. Default (no flags) prompts: 'n' aborts without restoring; 'y' restores.
4. --snapshot /path/to/snap.json passes that path through to plan/restore.
5. Server running: refuses with message telling operator to stop first.
6. No snapshot available: reports "no snapshot" and exits non-zero.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from agent_brain_cli.commands.graph import graph_group


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def snap_path(tmp_path: Path) -> Path:
    """A fake snapshot file (exists on disk for --snapshot path validation)."""
    p = tmp_path / "snapshot-2026-06-14T12-00-00Z.json"
    p.write_text('{"schema_version": 1, "triplets": []}')
    return p


def _make_mgr_mock(
    plan_result: tuple[Path, int] | None,
    restore_result: int = 0,
) -> MagicMock:
    """Build a mock GraphStoreManager with plan_restore / restore_from_snapshot."""
    mgr = MagicMock()
    mgr.plan_restore.return_value = plan_result
    mgr.restore_from_snapshot.return_value = restore_result
    return mgr


def _patch_context(
    tmp_path: Path,
    mgr_mock: MagicMock,
    server_running: bool = False,
) -> list:
    """Return a list of patch context managers for the graph command helpers."""
    graph_index = tmp_path / "data" / "graph_index"
    graph_index.mkdir(parents=True, exist_ok=True)

    return [
        patch(
            "agent_brain_cli.commands.graph._graph_index_dir",
            return_value=graph_index,
        ),
        patch(
            "agent_brain_cli.commands.graph._read_graphrag_block",
            return_value={"enabled": True, "store_type": "kuzu"},
        ),
        patch(
            "agent_brain_cli.commands.graph._server_is_running",
            return_value=server_running,
        ),
        patch(
            "agent_brain_cli.commands.graph.GraphStoreManager",
            return_value=mgr_mock,
        ),
    ]


class TestDryRun:
    """Test 1: --dry-run prints plan and exits 0 without mutating."""

    def test_dry_run_prints_plan_no_mutation(
        self, runner: CliRunner, tmp_path: Path, snap_path: Path
    ) -> None:
        plan_result = (snap_path, 42)
        mgr = _make_mgr_mock(plan_result=plan_result, restore_result=42)

        with (
            patch(
                "agent_brain_cli.commands.graph._graph_index_dir",
                return_value=tmp_path / "data" / "graph_index",
            ),
            patch(
                "agent_brain_cli.commands.graph._read_graphrag_block",
                return_value={"enabled": True, "store_type": "kuzu"},
            ),
            patch(
                "agent_brain_cli.commands.graph._server_is_running",
                return_value=False,
            ),
            patch(
                "agent_brain_cli.commands.graph.GraphStoreManager",
                return_value=mgr,
            ),
        ):
            result = runner.invoke(
                graph_group, ["restore-from-snapshot", "--dry-run"]
            )

        assert result.exit_code == 0, result.output
        assert "42" in result.output
        assert "dry run" in result.output.lower() or "dry-run" in result.output.lower()
        # plan_restore was called; restore_from_snapshot was NOT
        mgr.plan_restore.assert_called_once()
        mgr.restore_from_snapshot.assert_not_called()


class TestYesFlag:
    """Test 2: --yes restores non-interactively."""

    def test_yes_calls_restore_and_prints_count(
        self, runner: CliRunner, tmp_path: Path, snap_path: Path
    ) -> None:
        plan_result = (snap_path, 5)
        mgr = _make_mgr_mock(plan_result=plan_result, restore_result=5)

        with (
            patch(
                "agent_brain_cli.commands.graph._graph_index_dir",
                return_value=tmp_path / "data" / "graph_index",
            ),
            patch(
                "agent_brain_cli.commands.graph._read_graphrag_block",
                return_value={"enabled": True, "store_type": "kuzu"},
            ),
            patch(
                "agent_brain_cli.commands.graph._server_is_running",
                return_value=False,
            ),
            patch(
                "agent_brain_cli.commands.graph.GraphStoreManager",
                return_value=mgr,
            ),
        ):
            result = runner.invoke(
                graph_group, ["restore-from-snapshot", "--yes"]
            )

        assert result.exit_code == 0, result.output
        mgr.restore_from_snapshot.assert_called_once()
        assert "5" in result.output or "Restored" in result.output


class TestInteractivePrompt:
    """Test 3: Interactive prompt — 'n' aborts, 'y' restores."""

    def test_answer_no_aborts_without_restoring(
        self, runner: CliRunner, tmp_path: Path, snap_path: Path
    ) -> None:
        plan_result = (snap_path, 3)
        mgr = _make_mgr_mock(plan_result=plan_result, restore_result=3)

        with (
            patch(
                "agent_brain_cli.commands.graph._graph_index_dir",
                return_value=tmp_path / "data" / "graph_index",
            ),
            patch(
                "agent_brain_cli.commands.graph._read_graphrag_block",
                return_value={"enabled": True, "store_type": "kuzu"},
            ),
            patch(
                "agent_brain_cli.commands.graph._server_is_running",
                return_value=False,
            ),
            patch(
                "agent_brain_cli.commands.graph.GraphStoreManager",
                return_value=mgr,
            ),
        ):
            result = runner.invoke(
                graph_group,
                ["restore-from-snapshot"],
                input="n\n",
            )

        assert result.exit_code == 0, result.output
        mgr.restore_from_snapshot.assert_not_called()
        assert "abort" in result.output.lower() or "cancel" in result.output.lower()

    def test_answer_yes_restores(
        self, runner: CliRunner, tmp_path: Path, snap_path: Path
    ) -> None:
        plan_result = (snap_path, 3)
        mgr = _make_mgr_mock(plan_result=plan_result, restore_result=3)

        with (
            patch(
                "agent_brain_cli.commands.graph._graph_index_dir",
                return_value=tmp_path / "data" / "graph_index",
            ),
            patch(
                "agent_brain_cli.commands.graph._read_graphrag_block",
                return_value={"enabled": True, "store_type": "kuzu"},
            ),
            patch(
                "agent_brain_cli.commands.graph._server_is_running",
                return_value=False,
            ),
            patch(
                "agent_brain_cli.commands.graph.GraphStoreManager",
                return_value=mgr,
            ),
        ):
            result = runner.invoke(
                graph_group,
                ["restore-from-snapshot"],
                input="y\n",
            )

        assert result.exit_code == 0, result.output
        mgr.restore_from_snapshot.assert_called_once()


class TestExplicitSnapshotPath:
    """Test 4: --snapshot /path passes the path through to plan/restore."""

    def test_snapshot_path_passed_to_plan_restore(
        self, runner: CliRunner, tmp_path: Path, snap_path: Path
    ) -> None:
        plan_result = (snap_path, 7)
        mgr = _make_mgr_mock(plan_result=plan_result, restore_result=7)

        with (
            patch(
                "agent_brain_cli.commands.graph._graph_index_dir",
                return_value=tmp_path / "data" / "graph_index",
            ),
            patch(
                "agent_brain_cli.commands.graph._read_graphrag_block",
                return_value={"enabled": True, "store_type": "kuzu"},
            ),
            patch(
                "agent_brain_cli.commands.graph._server_is_running",
                return_value=False,
            ),
            patch(
                "agent_brain_cli.commands.graph.GraphStoreManager",
                return_value=mgr,
            ),
        ):
            result = runner.invoke(
                graph_group,
                ["restore-from-snapshot", "--snapshot", str(snap_path), "--yes"],
            )

        assert result.exit_code == 0, result.output
        # plan_restore was called with the explicit path
        mgr.plan_restore.assert_called_once_with(snap_path)
        # restore_from_snapshot was called with the same explicit path
        mgr.restore_from_snapshot.assert_called_once_with(snap_path)


class TestServerRunningGuard:
    """Test 5: Refuses when server is running."""

    def test_refuses_when_server_running(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        mgr = _make_mgr_mock(plan_result=None)

        with (
            patch(
                "agent_brain_cli.commands.graph._graph_index_dir",
                return_value=tmp_path / "data" / "graph_index",
            ),
            patch(
                "agent_brain_cli.commands.graph._read_graphrag_block",
                return_value={"enabled": True, "store_type": "kuzu"},
            ),
            patch(
                "agent_brain_cli.commands.graph._server_is_running",
                return_value=True,
            ),
            patch(
                "agent_brain_cli.commands.graph.GraphStoreManager",
                return_value=mgr,
            ),
        ):
            result = runner.invoke(graph_group, ["restore-from-snapshot", "--yes"])

        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert "stop" in output_lower or "server" in output_lower or "running" in output_lower
        mgr.restore_from_snapshot.assert_not_called()


class TestNoSnapshotAvailable:
    """Test 6: No snapshot available exits non-zero."""

    def test_no_snapshot_exits_nonzero(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        mgr = _make_mgr_mock(plan_result=None)

        with (
            patch(
                "agent_brain_cli.commands.graph._graph_index_dir",
                return_value=tmp_path / "data" / "graph_index",
            ),
            patch(
                "agent_brain_cli.commands.graph._read_graphrag_block",
                return_value={"enabled": True, "store_type": "kuzu"},
            ),
            patch(
                "agent_brain_cli.commands.graph._server_is_running",
                return_value=False,
            ),
            patch(
                "agent_brain_cli.commands.graph.GraphStoreManager",
                return_value=mgr,
            ),
        ):
            result = runner.invoke(graph_group, ["restore-from-snapshot"])

        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert "no snapshot" in output_lower or "available" in output_lower
        mgr.restore_from_snapshot.assert_not_called()


class TestHelpOutput:
    """Verify --help lists the expected options."""

    def test_help_lists_options(self, runner: CliRunner) -> None:
        result = runner.invoke(graph_group, ["restore-from-snapshot", "--help"])
        assert result.exit_code == 0
        assert "--snapshot" in result.output
        assert "--dry-run" in result.output
        assert "--yes" in result.output
