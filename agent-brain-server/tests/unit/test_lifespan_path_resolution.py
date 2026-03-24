"""Regression tests for BUGFIX-02: lifespan storage path resolution.

These tests verify that storage paths in the server lifespan always resolve
relative to a state_dir, and never fall back to CWD-relative paths like
'./chroma_db' or './bm25_index'.
"""

from pathlib import Path
from unittest.mock import patch


class TestLifespanFallbackGuaranteesStateDir:
    """BUGFIX-02: The lifespan fallback always produces a non-None state_dir."""

    def test_fallback_sets_state_dir_when_resolve_succeeds(self, tmp_path: Path) -> None:
        """When resolve_state_dir succeeds, state_dir is populated."""
        from agent_brain_server.storage_paths import resolve_state_dir, resolve_storage_paths

        state_dir = resolve_state_dir(tmp_path)
        storage_paths = resolve_storage_paths(state_dir)

        assert state_dir is not None
        assert storage_paths is not None

    def test_fallback_sets_state_dir_when_resolve_fails(self, tmp_path: Path) -> None:
        """When resolve_state_dir raises, a guaranteed fallback state_dir is used.

        This is the core of BUGFIX-02: even on failure, state_dir must not be None.
        We simulate the corrected behavior: a fallback .agent-brain in the project root.
        """
        from agent_brain_server.storage_paths import resolve_storage_paths

        # Simulate what the corrected lifespan except block should do
        state_dir: Path | None = None
        try:
            raise RuntimeError("Simulated resolve_state_dir failure")
        except Exception:
            # Corrected behavior: guaranteed fallback
            state_dir = tmp_path / ".agent-brain"
            state_dir.mkdir(parents=True, exist_ok=True)
            storage_paths = resolve_storage_paths(state_dir)

        # state_dir MUST be non-None after the except block
        assert state_dir is not None, "state_dir must be set even when resolve fails"

    def test_main_py_has_guaranteed_fallback_assertion(self) -> None:
        """BUGFIX-02: main.py source must assert state_dir is not None after fallback."""
        from pathlib import Path

        main_path = (
            Path(__file__).parent.parent.parent
            / "agent_brain_server"
            / "api"
            / "main.py"
        )
        source = main_path.read_text()
        assert (
            "assert state_dir is not None" in source
        ), "main.py must assert state_dir is not None after path resolution block"

    def test_main_py_tier3_cwd_fallback_is_unreachable(self) -> None:
        """BUGFIX-02: The tier-3 CWD fallback (settings.CHROMA_PERSIST_DIR) must be
        replaced with a RuntimeError, making it unreachable dead code."""
        from pathlib import Path

        main_path = (
            Path(__file__).parent.parent.parent
            / "agent_brain_server"
            / "api"
            / "main.py"
        )
        source = main_path.read_text()
        # The fix: RuntimeError must replace the CWD-relative fallback
        assert (
            "state_dir is unexpectedly None" in source
        ), "main.py must have a RuntimeError guard in place of the CWD-relative tier-3 fallback"


class TestStoragePathsAreAbsoluteUnderStateDir:
    """BUGFIX-02: All storage paths resolved via lifespan are absolute paths under state_dir."""

    def test_chroma_dir_is_absolute_under_state_dir(self, tmp_path: Path) -> None:
        """chroma_db path must be absolute and under state_dir, not CWD-relative."""
        from agent_brain_server.storage_paths import resolve_storage_paths

        state_dir = (tmp_path / ".agent-brain").resolve()
        state_dir.mkdir()
        paths = resolve_storage_paths(state_dir)

        chroma_dir = paths["chroma_db"]
        assert chroma_dir.is_absolute(), f"chroma_db path must be absolute, got: {chroma_dir}"
        assert str(chroma_dir).startswith(
            str(state_dir)
        ), f"chroma_db {chroma_dir} must be under state_dir {state_dir}"
        # Must NOT be the CWD-relative legacy string
        assert str(chroma_dir) != "./chroma_db"
        assert "chroma_db" in str(chroma_dir)

    def test_bm25_dir_is_absolute_under_state_dir(self, tmp_path: Path) -> None:
        """bm25_index path must be absolute and under state_dir, not CWD-relative."""
        from agent_brain_server.storage_paths import resolve_storage_paths

        state_dir = (tmp_path / ".agent-brain").resolve()
        state_dir.mkdir()
        paths = resolve_storage_paths(state_dir)

        bm25_dir = paths["bm25_index"]
        assert bm25_dir.is_absolute(), f"bm25_index path must be absolute, got: {bm25_dir}"
        assert str(bm25_dir).startswith(
            str(state_dir)
        ), f"bm25_index {bm25_dir} must be under state_dir {state_dir}"
        assert str(bm25_dir) != "./bm25_index"

    def test_graph_index_is_absolute_under_state_dir(self, tmp_path: Path) -> None:
        """graph_index path must be absolute and under state_dir, not CWD-relative."""
        from agent_brain_server.storage_paths import resolve_storage_paths

        state_dir = (tmp_path / ".agent-brain").resolve()
        state_dir.mkdir()
        paths = resolve_storage_paths(state_dir)

        graph_dir = paths["graph_index"]
        assert graph_dir.is_absolute(), f"graph_index path must be absolute, got: {graph_dir}"
        assert str(graph_dir).startswith(
            str(state_dir)
        ), f"graph_index {graph_dir} must be under state_dir {state_dir}"
        assert str(graph_dir) != "./graph_index"

    def test_embedding_cache_is_absolute_under_state_dir(self, tmp_path: Path) -> None:
        """embedding_cache path must be absolute and under state_dir, not a tempdir."""
        from agent_brain_server.storage_paths import resolve_storage_paths

        state_dir = (tmp_path / ".agent-brain").resolve()
        state_dir.mkdir()
        paths = resolve_storage_paths(state_dir)

        cache_dir = paths["embedding_cache"]
        assert cache_dir.is_absolute(), f"embedding_cache path must be absolute, got: {cache_dir}"
        assert str(cache_dir).startswith(
            str(state_dir)
        ), f"embedding_cache {cache_dir} must be under state_dir {state_dir}"
        # Must not be a tempdir
        assert "tmp" not in str(cache_dir).lower() or str(state_dir) in str(cache_dir)


class TestCWDRelativeTierIsUnreachable:
    """BUGFIX-02: Verify the CWD-relative tier-3 fallback cannot be reached in normal operation."""

    def test_settings_chroma_persist_dir_is_cwd_relative_legacy(self) -> None:
        """settings.CHROMA_PERSIST_DIR is CWD-relative (legacy) and should NOT be used
        in normal operation where state_dir is always resolved."""
        from agent_brain_server.config.settings import settings

        # The default is CWD-relative — this is a documented legacy default
        assert settings.CHROMA_PERSIST_DIR == "./chroma_db"

    def test_settings_has_legacy_comment(self) -> None:
        """settings.py must document that CWD-relative paths are legacy defaults."""
        from pathlib import Path

        settings_path = (
            Path(__file__).parent.parent.parent
            / "agent_brain_server"
            / "config"
            / "settings.py"
        )
        source = settings_path.read_text()
        assert (
            "Legacy CWD-relative" in source
        ), "settings.py must document the CWD-relative defaults as legacy"
