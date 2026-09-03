"""Isolation tests for ``project_isolated`` (#235 / #178).

Mirrors ``test_graph_isolation.py``: a SIGSEGV-class child exit must
raise GraphBuildFailedError without taking down the parent. We use
``_child_target_override`` so spawn children do not need a real kuzu db.
"""

from __future__ import annotations

from typing import Any

import pytest

from agent_brain_server.indexing.graph_index import project_isolated
from agent_brain_server.storage.graph_errors import GraphBuildFailedError

_ENTITIES = [{"type": "okf:Claim", "id": "claim.1", "properties": {}}]
_RELATIONS: list[dict[str, str]] = []


class TestProjectIsolatedParity:
    def test_returns_counts_from_child(self) -> None:
        counts = project_isolated(
            _ENTITIES,
            _RELATIONS,
            "research-graph",
            _child_target_override=_success_child,
        )
        assert counts["entities_upserted"] == 1
        assert counts["relations_upserted"] == 0


class TestProjectIsolatedSIGSEGV:
    def test_sigsegv_raises_graph_build_failed(self) -> None:
        with pytest.raises(GraphBuildFailedError) as exc_info:
            project_isolated(
                _ENTITIES,
                _RELATIONS,
                "research-graph",
                _child_target_override=_sigsegv_child,
            )
        err = exc_info.value
        assert err.exit_code == 139
        assert "store_type=simple" in str(err)
        assert "exit_code=139" in str(err)

    def test_parent_settings_unchanged(self) -> None:
        from agent_brain_server.config import settings

        original = getattr(settings, "GRAPH_STORE_TYPE", "simple")
        try:
            project_isolated(
                _ENTITIES,
                _RELATIONS,
                "research-graph",
                _child_target_override=_sigsegv_child,
            )
        except GraphBuildFailedError:
            pass
        assert getattr(settings, "GRAPH_STORE_TYPE", "simple") == original


def _success_child(payload: dict[str, Any], result_queue: Any) -> None:
    result_queue.put(
        {
            "entities_upserted": 1,
            "relations_upserted": 0,
            "entities_deleted": 0,
            "relations_deleted": 0,
        }
    )


def _sigsegv_child(payload: dict[str, Any], result_queue: Any) -> None:
    import os

    os._exit(139)
