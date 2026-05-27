"""Regression tests for issue #170: chroma/bm25 paths leaking to CWD.

Before the fix, calling ``get_vector_store()`` or ``get_bm25_manager()``
without prior ``set_*`` would create a singleton with the CWD-relative
default. The lifespan registered its own state-dir-resolved instance in
``app.state`` but never updated the module-level singleton, so any
service that pulled through the singleton (IndexingService,
QueryService, ChromaBackend) ended up with a *different* manager writing
to ``./chroma_db`` next to the project root.

The fix introduces ``set_vector_store()`` and ``set_bm25_manager()``
which the lifespan calls after constructing each manager with the
resolved path. These tests lock that contract in.
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_brain_server.api.main import _warn_about_stray_cwd_data_dirs
from agent_brain_server.indexing.bm25_index import (
    BM25IndexManager,
    get_bm25_manager,
    set_bm25_manager,
)
from agent_brain_server.storage.vector_store import (
    VectorStoreManager,
    get_vector_store,
    set_vector_store,
)


class TestSetVectorStoreOverridesSingleton:
    def test_set_vector_store_makes_get_return_same_instance(
        self, tmp_path: Path
    ) -> None:
        explicit = VectorStoreManager(persist_dir=str(tmp_path / "data" / "chroma_db"))
        set_vector_store(explicit)
        try:
            assert get_vector_store() is explicit
        finally:
            set_vector_store(None)  # type: ignore[arg-type]

    def test_get_vector_store_unset_logs_warning_and_uses_default(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Force fresh singleton state for this test.
        set_vector_store(None)  # type: ignore[arg-type]
        try:
            with caplog.at_level(
                logging.WARNING, logger="agent_brain_server.storage.vector_store"
            ):
                instance = get_vector_store()
            assert isinstance(instance, VectorStoreManager)
            assert any(
                "called before set_vector_store" in record.message
                for record in caplog.records
            )
        finally:
            set_vector_store(None)  # type: ignore[arg-type]


class TestSetBm25ManagerOverridesSingleton:
    def test_set_bm25_manager_makes_get_return_same_instance(
        self, tmp_path: Path
    ) -> None:
        explicit = BM25IndexManager(persist_dir=str(tmp_path / "data" / "bm25_index"))
        set_bm25_manager(explicit)
        try:
            assert get_bm25_manager() is explicit
        finally:
            set_bm25_manager(None)  # type: ignore[arg-type]

    def test_get_bm25_manager_unset_logs_warning_and_uses_default(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        set_bm25_manager(None)  # type: ignore[arg-type]
        try:
            with caplog.at_level(
                logging.WARNING, logger="agent_brain_server.indexing.bm25_index"
            ):
                instance = get_bm25_manager()
            assert isinstance(instance, BM25IndexManager)
            assert any(
                "called before set_bm25_manager" in record.message
                for record in caplog.records
            )
        finally:
            set_bm25_manager(None)  # type: ignore[arg-type]


class TestStrayCwdDataDirWarning:
    """``_warn_about_stray_cwd_data_dirs`` emits a guided manual-migration log."""

    def test_warns_when_stray_chroma_db_exists_at_cwd(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Build a fake CWD with a stray chroma_db and a separate state dir.
        fake_cwd = tmp_path / "project"
        fake_cwd.mkdir()
        (fake_cwd / "chroma_db").mkdir()
        state_dir = fake_cwd / ".agent-brain"
        state_dir.mkdir()

        with patch("agent_brain_server.api.main.Path.cwd", return_value=fake_cwd):
            with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
                _warn_about_stray_cwd_data_dirs(state_dir)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("stray data directory" in r.message for r in warnings)
        assert any("chroma_db" in r.message for r in warnings)
        # No silent move — message must point at a manual rm command.
        assert any("rm -rf" in r.message for r in warnings)

    def test_does_not_warn_when_no_stray_dirs(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        clean_cwd = tmp_path / "clean"
        clean_cwd.mkdir()
        state_dir = clean_cwd / ".agent-brain"
        state_dir.mkdir()

        with patch("agent_brain_server.api.main.Path.cwd", return_value=clean_cwd):
            with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
                _warn_about_stray_cwd_data_dirs(state_dir)

        assert not any("stray data directory" in r.message for r in caplog.records)

    def test_does_not_warn_when_state_dir_is_inside_cwd_only(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The canonical state-dir-relative path must not be flagged."""
        fake_cwd = tmp_path / "project"
        fake_cwd.mkdir()
        state_dir = fake_cwd / ".agent-brain"
        (state_dir / "data" / "chroma_db").mkdir(parents=True)
        # No stray chroma_db at CWD root, only inside state_dir.

        with patch("agent_brain_server.api.main.Path.cwd", return_value=fake_cwd):
            with caplog.at_level(logging.WARNING, logger="agent_brain_server.api.main"):
                _warn_about_stray_cwd_data_dirs(state_dir)

        assert not any("stray data directory" in r.message for r in caplog.records)


class TestLifespanContractIsDocumented:
    """Surface-level: the lifespan source still calls the new setters."""

    def test_main_py_calls_set_vector_store(self) -> None:
        main_path = (
            Path(__file__).parent.parent.parent
            / "agent_brain_server"
            / "api"
            / "main.py"
        )
        source = main_path.read_text()
        assert (
            "set_vector_store(vector_store)" in source
        ), "lifespan must register the state-dir-resolved vector store singleton"
        assert (
            "set_bm25_manager(bm25_manager)" in source
        ), "lifespan must register the state-dir-resolved bm25 manager singleton"
