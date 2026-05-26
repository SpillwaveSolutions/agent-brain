"""End-to-end integration test for the Kuzu graph store (issue #144).

Exercises the real ``KuzuPropertyGraphStore`` (not a mock) through
``GraphStoreManager`` to prove that graph search with Kuzu actually works:

1. The new ``llama-index-graph-stores-kuzu>=0.9.0`` constructor accepts our
   call shape (a ``kuzu.Database`` object, ``use_vector_index=False``).
2. Triplets added via ``GraphStoreManager.add_triplet`` are persisted to the
   underlying Kuzu store via ``upsert_nodes`` + ``upsert_relations``.
3. ``get_triplets`` returns the stored data.
4. The triplets survive closing and reopening the store against the same
   ``persist_dir`` (Kuzu auto-persists to disk).

This is the hard CI gate for the goal "Kuzu graph DB is tested and works."
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

# Skip the whole module if Kuzu isn't installed — the dev group pins it,
# but this keeps the test honest in unusual environments.
kuzu = pytest.importorskip("kuzu")
pytest.importorskip("llama_index.graph_stores.kuzu")

from agent_brain_server.storage.graph_store import GraphStoreManager  # noqa: E402


@pytest.fixture
def enable_graphrag():
    """Enable graphrag via the env-var settings path."""
    with patch("agent_brain_server.storage.graph_store.settings") as mock_settings:
        mock_settings.ENABLE_GRAPH_INDEX = True
        yield mock_settings


def _make_manager(persist_dir: Path) -> GraphStoreManager:
    """Build a fresh manager (bypassing the singleton)."""
    GraphStoreManager._instance = None
    manager = GraphStoreManager(persist_dir, store_type="kuzu")
    manager.initialize()
    return manager


def test_kuzu_constructor_accepts_new_signature(
    tmp_path: Path, enable_graphrag
) -> None:
    """The constructor fix from #144 lets initialization succeed."""
    manager = _make_manager(tmp_path)

    assert (
        manager.store_type == "kuzu"
    ), "store_type fell back to 'simple' — Kuzu init failed"
    assert manager._initialized
    assert manager._kuzu_db is not None
    assert isinstance(manager._kuzu_db, kuzu.Database)
    assert (tmp_path / "kuzu_db").exists()


def test_add_triplet_persists_to_kuzu(tmp_path: Path, enable_graphrag) -> None:
    """add_triplet must actually write to Kuzu (not silently no-op)."""
    manager = _make_manager(tmp_path)

    assert manager.add_triplet(
        subject="FastAPI",
        predicate="DEPENDS_ON",
        obj="Pydantic",
        subject_type="Framework",
        object_type="Library",
    )
    assert manager.add_triplet(
        subject="FastAPI",
        predicate="DEPENDS_ON",
        obj="Starlette",
    )

    # Round-trip through the underlying store
    triplets = manager._graph_store.get_triplets()
    assert (
        len(triplets) >= 2
    ), f"Expected at least 2 triplets in Kuzu, got {len(triplets)}: {triplets}"

    predicates = {t[1].label for t in triplets}
    assert "DEPENDS_ON" in predicates


def test_kuzu_triplets_survive_reopen(tmp_path: Path, enable_graphrag) -> None:
    """Kuzu auto-persists; reopening the store should see prior triplets."""
    manager = _make_manager(tmp_path)
    assert manager.add_triplet("Alice", "KNOWS", "Bob")
    assert manager.add_triplet("Bob", "KNOWS", "Carol")

    # Drop references so Kuzu releases the DB lock
    manager._graph_store = None
    manager._kuzu_db = None
    del manager

    # Reopen against the same persist_dir
    reopened = _make_manager(tmp_path)
    triplets = reopened._graph_store.get_triplets()
    assert len(triplets) >= 2, f"Triplets did not survive reopen: {triplets}"
    assert {t[1].label for t in triplets} == {"KNOWS"}
