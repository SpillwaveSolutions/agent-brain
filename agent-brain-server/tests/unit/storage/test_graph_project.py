"""Store-level tests for graph projection (#235).

Uses the simple backend (always available). Verifies:

- upsert of namespaced entities + extra predicates
- lookup traverses asserts / evidenced_by
- re-projecting identical input is idempotent
- delete-by-source_tag + re-project converges
- SCHEMA-01 nodes without the tag survive delete-by-tag
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agent_brain_server.storage.graph_store import (
    GraphStoreManager,
    reset_graph_store_manager,
)


@pytest.fixture(autouse=True)
def _reset_singleton() -> Any:
    reset_graph_store_manager()
    yield
    reset_graph_store_manager()


@pytest.fixture
def persist_dir(tmp_path: Path) -> Path:
    d = tmp_path / "graph_index"
    d.mkdir()
    return d


@pytest.fixture
def manager(persist_dir: Path) -> Any:
    patcher = patch("agent_brain_server.storage.graph_store.settings")
    mock_settings = patcher.start()
    mock_settings.ENABLE_GRAPH_INDEX = True
    mock_settings.GRAPH_STORE_TYPE = "simple"
    try:
        mgr = GraphStoreManager(persist_dir, store_type="simple")
        mgr.initialize()
        if mgr.graph_store is None:
            pytest.skip("simple backend produced no graph_store")
        yield mgr
    finally:
        patcher.stop()


_ENTITIES = [
    {
        "type": "okf:Finding",
        "id": "finding.1",
        "properties": {"title": "loop policy"},
    },
    {"type": "okf:Claim", "id": "claim.1", "properties": {}},
    {"type": "okf:Evidence", "id": "evidence.1", "properties": {}},
]
_RELATIONS = [
    {"src": "finding.1", "predicate": "asserts", "dst": "claim.1"},
    {"src": "claim.1", "predicate": "evidenced_by", "dst": "evidence.1"},
]


class TestProjectUpsert:
    def test_writes_typed_spine(self, manager: GraphStoreManager) -> None:
        counts = manager.project(_ENTITIES, _RELATIONS, source_tag="research-graph")
        assert counts["entities_upserted"] == 3
        assert counts["relations_upserted"] == 2

        finding = manager.get_entity_by_id("okf:Finding", "finding.1")
        assert finding is not None
        assert finding.entity.type == "okf:Finding"
        outgoing = {n.id: n.predicate for n in finding.neighbors.outgoing}
        assert outgoing.get("claim.1") == "asserts"

        claim = manager.get_entity_by_id("okf:Claim", "claim.1")
        assert claim is not None
        outgoing_c = {n.id: n.predicate for n in claim.neighbors.outgoing}
        incoming_c = {n.id: n.predicate for n in claim.neighbors.incoming}
        assert outgoing_c.get("evidence.1") == "evidenced_by"
        assert incoming_c.get("finding.1") == "asserts"

    def test_idempotent_reproject(self, manager: GraphStoreManager) -> None:
        manager.project(_ENTITIES, _RELATIONS, source_tag="research-graph")
        manager.project(_ENTITIES, _RELATIONS, source_tag="research-graph")
        finding = manager.get_entity_by_id("okf:Finding", "finding.1")
        assert finding is not None
        assert len(finding.neighbors.outgoing) == 1

    def test_replace_rebuild_converges(self, manager: GraphStoreManager) -> None:
        manager.project(_ENTITIES, _RELATIONS, source_tag="research-graph")
        counts = manager.project(
            _ENTITIES,
            _RELATIONS,
            source_tag="research-graph",
            replace=True,
        )
        assert counts["entities_deleted"] >= 1
        finding = manager.get_entity_by_id("okf:Finding", "finding.1")
        assert finding is not None
        assert len(finding.neighbors.outgoing) == 1

    def test_delete_by_tag_spares_other_nodes(
        self, manager: GraphStoreManager
    ) -> None:
        from llama_index.core.graph_stores.types import EntityNode

        store = manager.graph_store
        assert store is not None
        store.upsert_nodes(
            [EntityNode(name="login", label="Function", properties={})]
        )
        manager.project(_ENTITIES, _RELATIONS, source_tag="research-graph")
        deleted_e, _deleted_r = manager.delete_by_source_tag("research-graph")
        assert deleted_e >= 1
        assert manager.get_entity_by_id("okf:Finding", "finding.1") is None
        leftover = manager.get_entity_by_id("Function", "login")
        assert leftover is not None
        assert leftover.entity.id == "login"
