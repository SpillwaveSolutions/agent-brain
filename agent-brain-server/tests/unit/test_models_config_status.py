"""Phase 2 TDD: ``ConfigStatus`` Pydantic model for ``GET /health/config``.

Maps to plan §12.3 acceptance #16 (data-shape part) — the new endpoint at
``GET /health/config`` returns this shape and feeds the MCP ``corpus://config``
resource (Phase 4).

The model lives at ``agent_brain_server.models.health.ConfigStatus`` per the
plan §4.3 file layout. These tests fail at import time until that symbol
exists. That's the RED step.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from agent_brain_server.models.health import ConfigStatus


class TestConfigStatusShape:
    """The on-the-wire shape must match what corpus://config promises."""

    def test_minimal_valid_payload(self) -> None:
        payload = {
            "storage_backend": "chroma",
            "stores": {"vector": True, "bm25": True, "graph": False},
            "reranker_enabled": False,
            "embedding_model": "text-embedding-3-large",
            "rerank_model": None,
            "graph_extractor": None,
            "watcher_running": False,
        }
        cfg = ConfigStatus.model_validate(payload)
        assert cfg.storage_backend == "chroma"
        assert cfg.stores.vector is True
        assert cfg.stores.bm25 is True
        assert cfg.stores.graph is False
        assert cfg.reranker_enabled is False
        assert cfg.embedding_model == "text-embedding-3-large"
        assert cfg.rerank_model is None
        assert cfg.graph_extractor is None
        assert cfg.watcher_running is False

    def test_storage_backend_rejects_unknown_value(self) -> None:
        """Only ``chroma`` and ``postgres`` are valid in v1."""
        with pytest.raises(ValidationError):
            ConfigStatus.model_validate(
                {
                    "storage_backend": "redis",
                    "stores": {"vector": True, "bm25": True, "graph": False},
                    "reranker_enabled": False,
                    "embedding_model": "text-embedding-3-large",
                    "rerank_model": None,
                    "graph_extractor": None,
                    "watcher_running": False,
                }
            )

    def test_postgres_backend_is_valid(self) -> None:
        cfg = ConfigStatus.model_validate(
            {
                "storage_backend": "postgres",
                "stores": {"vector": True, "bm25": True, "graph": True},
                "reranker_enabled": True,
                "embedding_model": "text-embedding-3-large",
                "rerank_model": "bge-reranker-v2-m3",
                "graph_extractor": "anthropic",
                "watcher_running": True,
            }
        )
        assert cfg.storage_backend == "postgres"
        assert cfg.stores.graph is True
        assert cfg.reranker_enabled is True

    def test_stores_requires_all_three_keys(self) -> None:
        """vector, bm25, and graph must all be present."""
        with pytest.raises(ValidationError):
            ConfigStatus.model_validate(
                {
                    "storage_backend": "chroma",
                    "stores": {"vector": True, "bm25": True},  # missing graph
                    "reranker_enabled": False,
                    "embedding_model": "text-embedding-3-large",
                    "rerank_model": None,
                    "graph_extractor": None,
                    "watcher_running": False,
                }
            )

    def test_serializes_to_documented_field_names(self) -> None:
        """The MCP corpus://config resource depends on exact JSON field names."""
        cfg = ConfigStatus.model_validate(
            {
                "storage_backend": "chroma",
                "stores": {"vector": True, "bm25": True, "graph": False},
                "reranker_enabled": False,
                "embedding_model": "text-embedding-3-large",
                "rerank_model": None,
                "graph_extractor": None,
                "watcher_running": False,
            }
        )
        data = json.loads(cfg.model_dump_json())
        # Top-level keys per plan §4.3 / §6.5 corpus://config row
        assert set(data.keys()) == {
            "storage_backend",
            "stores",
            "reranker_enabled",
            "embedding_model",
            "rerank_model",
            "graph_extractor",
            "watcher_running",
        }
        assert set(data["stores"].keys()) == {"vector", "bm25", "graph"}
