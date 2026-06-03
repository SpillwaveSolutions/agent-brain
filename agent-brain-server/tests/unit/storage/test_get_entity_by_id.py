"""Contract test for ``GraphStoreManager.get_entity_by_id``.

Parametrized across both graph backends:

- ``simple`` — ``SimplePropertyGraphStore`` (always available).
- ``kuzu`` — ``KuzuPropertyGraphStore`` (skipped when kuzu isn't installed
  or when initialization raises a corruption signature, per #178).

The contract checked here is the same one ``GET /graph/entity/{type}/{id}``
relies on: existing entities round-trip with their 1-hop neighbors, empty
neighbor lists are ``[]`` (never ``None``), missing entities return
``None``, and disabled graphrag short-circuits to ``None`` without touching
the store.

Mirrors the v6.0 storage-protocol contract pattern (parametrize across
backend implementations) so the wire contract holds equally on both.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agent_brain_server.models import (
    GraphEntityRecord,
    GraphEntityRecordNeighbor,
)
from agent_brain_server.storage.graph_store import (
    GraphStoreManager,
    KuzuUnavailableError,
    reset_graph_store_manager,
)

# ---------------------------------------------------------------------------
# Backend availability detection
# ---------------------------------------------------------------------------


def _kuzu_available() -> bool:
    """Return True when the kuzu + llama-index-graph-stores-kuzu pair is
    importable.

    Issue #178 means Kuzu may also be skipped at runtime — that path is
    covered by a separate test that exercises ``KuzuUnavailableError``.
    """
    try:
        import kuzu  # noqa: F401
        from llama_index.graph_stores.kuzu import (  # noqa: F401
            KuzuPropertyGraphStore,
        )
    except (ImportError, RuntimeError):
        return False
    return True


BACKENDS: list[str] = ["simple"]
if _kuzu_available():
    BACKENDS.append("kuzu")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton() -> Any:
    """Reset the singleton between tests so each backend gets a fresh store."""
    reset_graph_store_manager()
    yield
    reset_graph_store_manager()


@pytest.fixture
def persist_dir(tmp_path: Path) -> Path:
    """Per-test graph persistence dir under pytest's tmp_path."""
    d = tmp_path / "graph_index"
    d.mkdir()
    return d


def _seed_graph(store: Any) -> None:
    """Populate the graph with a small fixture used by every backend.

    Topology:

        Database --uses--> AuthService --calls--> login
        UserAdmin --extends--> AuthService

    So ``AuthService`` has two incoming edges (``uses``, ``extends``) and
    one outgoing edge (``calls``). ``login`` has zero outgoing.
    """
    from llama_index.core.graph_stores.types import EntityNode, Relation

    n_auth = EntityNode(
        name="AuthService",
        label="Class",
        properties={"module": "auth.service"},
    )
    n_login = EntityNode(name="login", label="Function", properties={})
    n_db = EntityNode(name="Database", label="Class", properties={})
    n_admin = EntityNode(name="UserAdmin", label="Class", properties={})

    store.upsert_nodes([n_auth, n_login, n_db, n_admin])
    store.upsert_relations(
        [
            Relation(
                label="calls",
                source_id=n_auth.id,
                target_id=n_login.id,
                properties={"source_chunk_id": "chunk_1"},
            ),
            Relation(
                label="uses",
                source_id=n_db.id,
                target_id=n_auth.id,
                properties={},
            ),
            Relation(
                label="extends",
                source_id=n_admin.id,
                target_id=n_auth.id,
                properties={},
            ),
        ]
    )


@pytest.fixture(params=BACKENDS)
def manager(request: pytest.FixtureRequest, persist_dir: Path) -> Any:
    """Initialized manager seeded with the fixture graph for each backend.

    The ``ENABLE_GRAPH_INDEX`` patch is held open for the entire test
    body — ``with patch(...)`` is used as a contextmanager and yielded so
    the per-test settings remain mocked while the test runs.
    """
    backend = request.param
    patcher = patch("agent_brain_server.storage.graph_store.settings")
    mock_settings = patcher.start()
    mock_settings.ENABLE_GRAPH_INDEX = True
    try:
        mgr = GraphStoreManager(persist_dir, store_type=backend)
        try:
            mgr.initialize()
        except (RuntimeError, IndexError, OSError) as exc:
            # Kuzu corruption can surface here per #178. Skip rather than
            # fail the test suite — the unavailability path is covered by
            # ``test_kuzu_unavailable_surfaces_error``.
            pytest.skip(f"{backend} backend unavailable in test env: {exc}")

        if mgr.graph_store is None:
            pytest.skip(f"{backend} backend produced no graph_store")

        # Some Kuzu builds fall back to simple when the import succeeded
        # but the schema init raised. Honor whatever store_type ended up.
        _seed_graph(mgr.graph_store)
        yield mgr
    finally:
        patcher.stop()


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestGetEntityByIdContract:
    """Behavioral contract that both backends must satisfy."""

    def test_existing_entity_returns_record_with_neighbors(
        self, manager: GraphStoreManager
    ) -> None:
        """Existing entity yields full GraphEntityRecord with 1-hop neighbors."""
        record = manager.get_entity_by_id("Class", "AuthService")

        assert record is not None
        assert isinstance(record, GraphEntityRecord)
        assert record.entity.type == "Class"
        assert record.entity.id == "AuthService"

        # Two incoming edges (Database uses, UserAdmin extends), one outgoing
        # (AuthService calls login).
        incoming_ids = {n.id for n in record.neighbors.incoming}
        outgoing_ids = {n.id for n in record.neighbors.outgoing}
        assert incoming_ids == {
            "Database",
            "UserAdmin",
        }, f"expected Database+UserAdmin incoming, got {incoming_ids}"
        assert outgoing_ids == {"login"}, f"expected login outgoing, got {outgoing_ids}"

        # Predicate carried through.
        predicates_in = {n.predicate for n in record.neighbors.incoming}
        assert predicates_in == {"uses", "extends"}
        for n in record.neighbors.outgoing:
            assert n.predicate == "calls"
        # source_chunk_id property propagated on backends that preserve
        # relationship properties. Kuzu's PropertyGraphStore schema in
        # llama-index-graph-stores-kuzu 0.9.x does not persist custom
        # Relation properties (only the predicate ends up as ``label``),
        # so this assertion is conditional on the backend.
        if manager.store_type != "kuzu":
            for n in record.neighbors.outgoing:
                assert n.properties.get("source_chunk_id") == "chunk_1"

    def test_entity_with_zero_outgoing_returns_empty_list_not_none(
        self, manager: GraphStoreManager
    ) -> None:
        """``login`` has no outgoing edges → outgoing == [] (not None)."""
        record = manager.get_entity_by_id("Function", "login")

        assert record is not None
        assert record.entity.id == "login"
        assert record.entity.type == "Function"
        # Outgoing must be an empty list — NOT None.
        assert record.neighbors.outgoing == []
        assert isinstance(record.neighbors.outgoing, list)
        # Incoming has one edge (AuthService calls login).
        assert len(record.neighbors.incoming) == 1
        assert record.neighbors.incoming[0].id == "AuthService"
        assert record.neighbors.incoming[0].predicate == "calls"

    def test_missing_entity_returns_none(self, manager: GraphStoreManager) -> None:
        """Unknown ``(type, id)`` returns None — router maps this to 404."""
        assert manager.get_entity_by_id("Function", "no_such_function") is None
        # Wrong type for an existing id also returns None.
        assert manager.get_entity_by_id("Function", "AuthService") is None

    def test_returns_graph_entity_record_pydantic_shape(
        self, manager: GraphStoreManager
    ) -> None:
        """Round-trip the response through Pydantic's serializer."""
        record = manager.get_entity_by_id("Class", "AuthService")
        assert record is not None
        dumped = record.model_dump()
        # Top-level keys locked by design doc §2.4.
        assert set(dumped.keys()) == {"entity", "neighbors"}
        assert set(dumped["entity"].keys()) == {"type", "id", "properties"}
        assert set(dumped["neighbors"].keys()) == {"incoming", "outgoing"}
        # Every neighbor record has the locked field set.
        for n in record.neighbors.incoming + record.neighbors.outgoing:
            assert isinstance(n, GraphEntityRecordNeighbor)
            assert {"type", "id", "predicate", "properties"}.issubset(
                n.model_dump().keys()
            )


class TestGetEntityByIdDisabled:
    """When GraphRAG is disabled, the lookup short-circuits to None."""

    def test_disabled_returns_none(self, persist_dir: Path) -> None:
        with patch("agent_brain_server.storage.graph_store.settings") as mock_settings:
            mock_settings.ENABLE_GRAPH_INDEX = False
            mgr = GraphStoreManager(persist_dir, store_type="simple")
            mgr.initialize()  # no-op while disabled
            assert mgr.get_entity_by_id("Function", "anything") is None

    def test_not_initialized_returns_none(self, persist_dir: Path) -> None:
        with patch("agent_brain_server.storage.graph_store.settings") as mock_settings:
            mock_settings.ENABLE_GRAPH_INDEX = True
            mgr = GraphStoreManager(persist_dir, store_type="simple")
            # Don't call initialize() — manager has no graph store yet.
            assert mgr.get_entity_by_id("Function", "anything") is None


class TestKuzuUnavailableSentinel:
    """``KuzuUnavailableError`` surfaces when the Kuzu backend raises.

    Verifies the #178 protection path: a corruption signature inside
    ``get(ids=...)`` or ``get_triplets(ids=...)`` must raise the sentinel,
    not crash the process.
    """

    def test_kuzu_corruption_during_get_raises_sentinel(
        self, persist_dir: Path
    ) -> None:
        """Simulating Kuzu corruption on ``store.get`` raises the sentinel."""
        from unittest.mock import MagicMock

        with patch("agent_brain_server.storage.graph_store.settings") as mock_settings:
            mock_settings.ENABLE_GRAPH_INDEX = True
            mgr = GraphStoreManager(persist_dir, store_type="simple")
            mgr.initialize()
            # Force the store_type to look like kuzu so the corruption
            # branch is taken — the underlying simple store remains.
            mgr.store_type = "kuzu"
            mock_store = MagicMock()
            mock_store.get.side_effect = IndexError("unordered_map::at: key not found")
            mgr._graph_store = mock_store

            with pytest.raises(KuzuUnavailableError):
                mgr.get_entity_by_id("Class", "AuthService")

    def test_kuzu_corruption_during_get_triplets_raises_sentinel(
        self, persist_dir: Path
    ) -> None:
        """Simulating Kuzu corruption on ``get_triplets`` raises the sentinel."""
        from unittest.mock import MagicMock

        from llama_index.core.graph_stores.types import EntityNode

        with patch("agent_brain_server.storage.graph_store.settings") as mock_settings:
            mock_settings.ENABLE_GRAPH_INDEX = True
            mgr = GraphStoreManager(persist_dir, store_type="simple")
            mgr.initialize()
            mgr.store_type = "kuzu"
            mock_store = MagicMock()
            mock_store.get.return_value = [
                EntityNode(name="AuthService", label="Class", properties={})
            ]
            mock_store.get_triplets.side_effect = RuntimeError("kuzu catalog corrupted")
            mgr._graph_store = mock_store

            with pytest.raises(KuzuUnavailableError):
                mgr.get_entity_by_id("Class", "AuthService")

    def test_simple_backend_does_not_raise_sentinel(self, persist_dir: Path) -> None:
        """An unexpected error from the simple backend degrades to None.

        The sentinel is reserved for Kuzu; other backends shouldn't suddenly
        start surfacing 503s if they hit a transient quirk.
        """
        from unittest.mock import MagicMock

        with patch("agent_brain_server.storage.graph_store.settings") as mock_settings:
            mock_settings.ENABLE_GRAPH_INDEX = True
            mgr = GraphStoreManager(persist_dir, store_type="simple")
            mgr.initialize()
            mock_store = MagicMock()
            mock_store.get.side_effect = OSError("disk hiccup")
            mgr._graph_store = mock_store

            # Should degrade to None, NOT raise.
            assert mgr.get_entity_by_id("Class", "AuthService") is None
