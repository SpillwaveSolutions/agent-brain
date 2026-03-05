"""Unit tests for storage_paths module."""

from pathlib import Path

from agent_brain_server.storage_paths import (
    STATE_DIR_NAME,
    resolve_state_dir,
    resolve_storage_paths,
)


class TestResolveStateDir:
    """Tests for resolve_state_dir function."""

    def test_returns_correct_path(self, tmp_path):
        """Test state dir is under project root."""
        result = resolve_state_dir(tmp_path)
        assert result == tmp_path / STATE_DIR_NAME

    def test_resolves_symlinks(self, tmp_path):
        """Test symlinks are resolved."""
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        result = resolve_state_dir(link_dir)
        assert result == real_dir / STATE_DIR_NAME

    def test_state_dir_name_constant(self):
        """Test STATE_DIR_NAME is correct."""
        assert STATE_DIR_NAME == ".claude/agent-brain"


class TestResolveStoragePaths:
    """Tests for resolve_storage_paths function."""

    def test_creates_all_directories(self, tmp_path):
        """Test all storage directories are created."""
        state_dir = tmp_path / ".claude" / "agent-brain"
        paths = resolve_storage_paths(state_dir)

        for name, path in paths.items():
            assert path.exists(), f"{name} directory not created"
            assert path.is_dir(), f"{name} is not a directory"

    def test_returns_expected_keys(self, tmp_path):
        """Test returned dict has expected keys."""
        state_dir = tmp_path / ".claude" / "agent-brain"
        paths = resolve_storage_paths(state_dir)

        expected_keys = {
            "state_dir",
            "data",
            "chroma_db",
            "bm25_index",
            "llamaindex",
            "graph_index",
            "logs",
            "manifests",
        }
        assert set(paths.keys()) == expected_keys

    def test_paths_are_under_state_dir(self, tmp_path):
        """Test all paths are under the state directory."""
        state_dir = tmp_path / ".claude" / "agent-brain"
        paths = resolve_storage_paths(state_dir)

        for name, path in paths.items():
            assert str(path).startswith(str(state_dir)), f"{name} not under state_dir"

    def test_idempotent(self, tmp_path):
        """Test calling twice returns same paths."""
        state_dir = tmp_path / ".claude" / "agent-brain"
        paths1 = resolve_storage_paths(state_dir)
        paths2 = resolve_storage_paths(state_dir)
        assert paths1 == paths2


class TestResolveSharedProjectDir:
    """Tests for resolve_shared_project_dir function."""

    def test_creates_directory(self, tmp_path, monkeypatch):
        """Test shared project directory is created."""
        monkeypatch.setenv("HOME", str(tmp_path))
        # Need to also patch Path.home() since it may be cached
        import agent_brain_server.storage_paths as sp

        original_home = Path.home

        def mock_home():
            return tmp_path

        Path.home = staticmethod(mock_home)
        try:
            result = sp.resolve_shared_project_dir("test-project")
            assert result.exists()
            assert result.is_dir()
            assert "test-project" in str(result)
        finally:
            Path.home = original_home

    def test_different_projects_get_different_dirs(self, tmp_path, monkeypatch):
        """Test different project IDs get different directories."""
        import agent_brain_server.storage_paths as sp

        original_home = Path.home

        def mock_home():
            return tmp_path

        Path.home = staticmethod(mock_home)
        try:
            dir1 = sp.resolve_shared_project_dir("project-a")
            dir2 = sp.resolve_shared_project_dir("project-b")
            assert dir1 != dir2
        finally:
            Path.home = original_home
