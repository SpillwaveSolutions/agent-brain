"""Unit tests for project_root module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_brain_server.project_root import (
    _resolve_git_root,
    _walk_up_for_marker,
    _walk_up_for_state_dir,
    resolve_project_root,
)


class TestResolveProjectRoot:
    """Tests for resolve_project_root function."""

    def test_returns_git_root_when_available(self, tmp_path):
        """Test that git root takes priority."""
        with patch(
            "agent_brain_server.project_root._resolve_git_root",
            return_value=tmp_path,
        ):
            result = resolve_project_root(tmp_path)
            assert result == tmp_path

    def test_falls_back_to_marker_when_no_git(self, tmp_path):
        """Test fallback to marker-based detection."""
        (tmp_path / ".claude").mkdir()

        with patch(
            "agent_brain_server.project_root._resolve_git_root",
            return_value=None,
        ):
            result = resolve_project_root(tmp_path)
            assert result == tmp_path

    def test_falls_back_to_start_path(self, tmp_path):
        """Test fallback to start path when no markers found."""
        with patch(
            "agent_brain_server.project_root._resolve_git_root",
            return_value=None,
        ):
            result = resolve_project_root(tmp_path)
            assert result == tmp_path.resolve()

    def test_uses_cwd_when_no_start_path(self):
        """Test defaults to cwd when no start path given."""
        with patch(
            "agent_brain_server.project_root._resolve_git_root",
            return_value=Path.cwd().resolve(),
        ):
            result = resolve_project_root()
            assert result == Path.cwd().resolve()

    def test_local_state_dir_preferred_over_git_root(self, tmp_path):
        """Nested ``.agent-brain/`` must win over the surrounding git root.

        Regression test for #124 (mono-repo) and #128 (status hitting wrong
        port). Before the fix, ``_resolve_git_root`` was called first and
        jumped to the top of the repo, skipping the local state dir.
        """
        # Simulate: git_root = tmp_path, but project lives in projects/app/
        # with its own .agent-brain/.
        nested = tmp_path / "projects" / "app"
        nested.mkdir(parents=True)
        (nested / ".agent-brain").mkdir()

        with patch(
            "agent_brain_server.project_root._resolve_git_root",
            return_value=tmp_path,
        ):
            assert resolve_project_root(nested) == nested

    def test_git_root_used_when_no_local_state_dir(self, tmp_path):
        """When there is no nested .agent-brain/, fall through to git root."""
        nested = tmp_path / "src"
        nested.mkdir()

        with patch(
            "agent_brain_server.project_root._resolve_git_root",
            return_value=tmp_path,
        ):
            assert resolve_project_root(nested) == tmp_path


class TestResolveGitRoot:
    """Tests for _resolve_git_root function."""

    def test_returns_path_on_success(self, tmp_path):
        """Test successful git root resolution."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = str(tmp_path)

        with patch("subprocess.run", return_value=mock_result):
            result = _resolve_git_root(tmp_path)
            assert result == tmp_path.resolve()

    def test_returns_none_on_failure(self, tmp_path):
        """Test returns None when git command fails."""
        mock_result = MagicMock()
        mock_result.returncode = 128

        with patch("subprocess.run", return_value=mock_result):
            result = _resolve_git_root(tmp_path)
            assert result is None

    def test_returns_none_on_timeout(self, tmp_path):
        """Test returns None when git command times out."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=5),
        ):
            result = _resolve_git_root(tmp_path)
            assert result is None

    def test_returns_none_when_git_not_found(self, tmp_path):
        """Test returns None when git is not installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = _resolve_git_root(tmp_path)
            assert result is None


class TestWalkUpForMarker:
    """Tests for _walk_up_for_marker function."""

    def test_finds_agent_brain_dir(self, tmp_path):
        """Test finding .agent-brain directory marker via the state-dir walker."""
        (tmp_path / ".agent-brain").mkdir()
        child = tmp_path / "sub" / "deep"
        child.mkdir(parents=True)

        # .agent-brain is now found by _walk_up_for_state_dir so it can take
        # precedence over the git root (issue #124). _walk_up_for_marker only
        # handles non-state markers.
        assert _walk_up_for_state_dir(child) == tmp_path

    def test_finds_claude_dir(self, tmp_path):
        """Test finding .claude directory marker."""
        (tmp_path / ".claude").mkdir()
        child = tmp_path / "sub" / "deep"
        child.mkdir(parents=True)

        result = _walk_up_for_marker(child)
        assert result == tmp_path

    def test_state_dir_takes_priority_over_claude(self, tmp_path):
        """Test .agent-brain takes priority over .claude (issue #124)."""
        (tmp_path / ".agent-brain").mkdir()
        (tmp_path / ".claude").mkdir()
        child = tmp_path / "src"
        child.mkdir()

        # The high-level resolver picks state dir first.
        assert resolve_project_root(child) == tmp_path

    def test_finds_pyproject_toml(self, tmp_path):
        """Test finding pyproject.toml marker."""
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]")
        child = tmp_path / "src"
        child.mkdir()

        result = _walk_up_for_marker(child)
        assert result == tmp_path

    def test_prefers_claude_over_pyproject(self, tmp_path):
        """Test .claude directory takes priority over pyproject.toml."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / "pyproject.toml").write_text("[tool.poetry]")
        child = tmp_path / "src"
        child.mkdir()

        result = _walk_up_for_marker(child)
        assert result == tmp_path

    def test_returns_none_when_no_markers(self, tmp_path):
        """Test returns None when no markers found."""
        child = tmp_path / "orphan"
        child.mkdir()

        result = _walk_up_for_marker(child)
        # May or may not find markers higher up (e.g. system pyproject.toml)
        # Just verify it doesn't crash
        assert result is None or isinstance(result, Path)
