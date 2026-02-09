"""Contract tests for QueryMode enum values and QueryResult model.

These tests ensure API stability by verifying that QueryMode enum values
remain consistent across releases. Changing these values would be a
breaking change for API consumers.

Feature 113: GraphRAG Integration
Feature 123: Two-Stage Reranking
"""

import pytest

from agent_brain_server.models.query import QueryMode, QueryResult


class TestQueryModeContract:
    """Contract tests for QueryMode enum values."""

    def test_query_mode_has_required_values(self) -> None:
        """Verify all required QueryMode values exist.

        These values are part of the API contract and must not be removed.
        """
        required_modes = ["vector", "bm25", "hybrid", "graph", "multi"]

        for mode in required_modes:
            assert hasattr(
                QueryMode, mode.upper()
            ), f"QueryMode.{mode.upper()} must exist"

    def test_query_mode_vector_value(self) -> None:
        """Verify QueryMode.VECTOR has the correct string value."""
        assert QueryMode.VECTOR.value == "vector"

    def test_query_mode_bm25_value(self) -> None:
        """Verify QueryMode.BM25 has the correct string value."""
        assert QueryMode.BM25.value == "bm25"

    def test_query_mode_hybrid_value(self) -> None:
        """Verify QueryMode.HYBRID has the correct string value."""
        assert QueryMode.HYBRID.value == "hybrid"

    def test_query_mode_graph_value(self) -> None:
        """Verify QueryMode.GRAPH has the correct string value (Feature 113)."""
        assert QueryMode.GRAPH.value == "graph"

    def test_query_mode_multi_value(self) -> None:
        """Verify QueryMode.MULTI has the correct string value (Feature 113)."""
        assert QueryMode.MULTI.value == "multi"

    def test_query_mode_is_string_enum(self) -> None:
        """Verify QueryMode values can be used as strings via .value."""
        # String enum values should be accessible via .value
        assert QueryMode.VECTOR.value == "vector"
        assert QueryMode.BM25.value == "bm25"
        assert QueryMode.HYBRID.value == "hybrid"
        assert QueryMode.GRAPH.value == "graph"
        assert QueryMode.MULTI.value == "multi"

        # String enum should inherit from str for direct comparison
        assert QueryMode.VECTOR == "vector"
        assert QueryMode.BM25 == "bm25"
        assert QueryMode.HYBRID == "hybrid"
        assert QueryMode.GRAPH == "graph"
        assert QueryMode.MULTI == "multi"

    def test_query_mode_from_string(self) -> None:
        """Verify QueryMode can be created from string values."""
        assert QueryMode("vector") == QueryMode.VECTOR
        assert QueryMode("bm25") == QueryMode.BM25
        assert QueryMode("hybrid") == QueryMode.HYBRID
        assert QueryMode("graph") == QueryMode.GRAPH
        assert QueryMode("multi") == QueryMode.MULTI

    def test_query_mode_minimum_count(self) -> None:
        """Verify QueryMode has at least 5 values (original 3 + 2 from Feature 113)."""
        mode_count = len(QueryMode)
        assert mode_count >= 5, f"Expected at least 5 query modes, got {mode_count}"

    @pytest.mark.parametrize(
        "mode_name,mode_value",
        [
            ("VECTOR", "vector"),
            ("BM25", "bm25"),
            ("HYBRID", "hybrid"),
            ("GRAPH", "graph"),
            ("MULTI", "multi"),
        ],
    )
    def test_query_mode_name_value_pairs(self, mode_name: str, mode_value: str) -> None:
        """Verify all query mode name-value pairs are correct."""
        mode = getattr(QueryMode, mode_name)
        assert mode.value == mode_value
        assert mode.name == mode_name


class TestQueryModeGraphRAGContract:
    """Contract tests specifically for GraphRAG query modes (Feature 113)."""

    def test_graph_mode_exists_and_valid(self) -> None:
        """Verify GRAPH mode is available for graph-only queries."""
        graph_mode = QueryMode.GRAPH

        # Must be a valid string enum
        assert isinstance(graph_mode.value, str)
        assert graph_mode.value == "graph"

        # Must be case-insensitive comparable
        assert QueryMode("graph") == graph_mode

    def test_multi_mode_exists_and_valid(self) -> None:
        """Verify MULTI mode is available for multi-retrieval fusion."""
        multi_mode = QueryMode.MULTI

        # Must be a valid string enum
        assert isinstance(multi_mode.value, str)
        assert multi_mode.value == "multi"

        # Must be case-insensitive comparable
        assert QueryMode("multi") == multi_mode

    def test_graphrag_modes_are_distinct(self) -> None:
        """Verify GraphRAG modes are distinct from each other and existing modes."""
        all_modes = list(QueryMode)
        all_values = [m.value for m in all_modes]

        # No duplicate values
        assert len(all_values) == len(set(all_values))

        # GRAPH and MULTI are different
        assert QueryMode.GRAPH != QueryMode.MULTI
        assert QueryMode.GRAPH.value != QueryMode.MULTI.value

    def test_graphrag_modes_in_enumeration(self) -> None:
        """Verify GraphRAG modes appear in enumeration of all modes."""
        all_modes = list(QueryMode)

        assert QueryMode.GRAPH in all_modes
        assert QueryMode.MULTI in all_modes

    def test_invalid_mode_raises_error(self) -> None:
        """Verify invalid mode values raise ValueError."""
        with pytest.raises(ValueError):
            QueryMode("invalid_mode")

        with pytest.raises(ValueError):
            QueryMode("graphrag")  # Not a valid mode name

        with pytest.raises(ValueError):
            QueryMode("GRAPH")  # Case sensitive - must be lowercase


class TestRerankingContract:
    """Contract tests for two-stage reranking feature (Feature 123).

    These tests verify the API contract for reranking fields and settings.
    """

    def test_reranking_disabled_by_default(self) -> None:
        """ENABLE_RERANKING is false by default for backward compatibility."""
        from agent_brain_server.config.settings import Settings

        settings = Settings()
        assert settings.ENABLE_RERANKING is False

    def test_reranker_settings_exist(self) -> None:
        """All reranker settings are defined in Settings."""
        from agent_brain_server.config.settings import Settings

        settings = Settings()
        # All reranking settings should be present
        # Note: RERANKER_BATCH_SIZE removed (CrossEncoder handles batching)
        assert hasattr(settings, "ENABLE_RERANKING")
        assert hasattr(settings, "RERANKER_PROVIDER")
        assert hasattr(settings, "RERANKER_MODEL")
        assert hasattr(settings, "RERANKER_TOP_K_MULTIPLIER")
        assert hasattr(settings, "RERANKER_MAX_CANDIDATES")

    def test_query_result_has_rerank_fields(self) -> None:
        """QueryResult model includes reranking fields."""
        result = QueryResult(
            text="test content",
            source="test.py",
            score=0.9,
            chunk_id="c1",
            rerank_score=0.85,
            original_rank=3,
        )
        assert result.rerank_score == 0.85
        assert result.original_rank == 3

    def test_rerank_fields_optional(self) -> None:
        """Reranking fields are optional (None by default)."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.9,
            chunk_id="c1",
        )
        assert result.rerank_score is None
        assert result.original_rank is None

    def test_rerank_score_field_type(self) -> None:
        """rerank_score field accepts float values."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.9,
            chunk_id="c1",
            rerank_score=0.123456,
        )
        assert isinstance(result.rerank_score, float)
        assert result.rerank_score == 0.123456

    def test_original_rank_field_type(self) -> None:
        """original_rank field accepts integer values (1-indexed)."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.9,
            chunk_id="c1",
            original_rank=1,
        )
        assert isinstance(result.original_rank, int)
        assert result.original_rank == 1

    def test_rerank_score_can_be_higher_than_original(self) -> None:
        """rerank_score can differ from original score."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.5,  # Original score
            chunk_id="c1",
            rerank_score=0.95,  # Higher rerank score
            original_rank=10,  # Was ranked 10th, now might be higher
        )
        assert result.rerank_score > result.score

    def test_query_result_serialization_includes_rerank_fields(self) -> None:
        """QueryResult serialization includes reranking fields."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.9,
            chunk_id="c1",
            rerank_score=0.85,
            original_rank=5,
        )
        data = result.model_dump()
        assert "rerank_score" in data
        assert "original_rank" in data
        assert data["rerank_score"] == 0.85
        assert data["original_rank"] == 5

    def test_query_result_serialization_null_rerank_fields(self) -> None:
        """QueryResult serialization handles null reranking fields."""
        result = QueryResult(
            text="test",
            source="test.py",
            score=0.9,
            chunk_id="c1",
        )
        data = result.model_dump()
        assert "rerank_score" in data
        assert "original_rank" in data
        assert data["rerank_score"] is None
        assert data["original_rank"] is None


class TestRerankerProviderContract:
    """Contract tests for reranker provider types."""

    def test_reranker_provider_types_exist(self) -> None:
        """RerankerProviderType enum has required values."""
        from agent_brain_server.providers.base import RerankerProviderType

        assert hasattr(RerankerProviderType, "SENTENCE_TRANSFORMERS")
        assert hasattr(RerankerProviderType, "OLLAMA")

    def test_reranker_provider_values(self) -> None:
        """RerankerProviderType values match expected strings."""
        from agent_brain_server.providers.base import RerankerProviderType

        assert (
            RerankerProviderType.SENTENCE_TRANSFORMERS.value == "sentence-transformers"
        )
        assert RerankerProviderType.OLLAMA.value == "ollama"

    def test_reranker_config_exists(self) -> None:
        """RerankerConfig model exists and is importable."""
        from agent_brain_server.config.provider_config import RerankerConfig

        config = RerankerConfig()
        assert config.provider is not None
        assert config.model is not None

    def test_reranker_config_default_values(self) -> None:
        """RerankerConfig has sensible defaults."""
        from agent_brain_server.config.provider_config import RerankerConfig
        from agent_brain_server.providers.base import RerankerProviderType

        config = RerankerConfig()
        # Default provider should be sentence-transformers
        assert config.provider == RerankerProviderType.SENTENCE_TRANSFORMERS
        # Default model should be the fast MiniLM model
        assert "MiniLM" in config.model

    def test_provider_registry_has_reranker_methods(self) -> None:
        """ProviderRegistry has reranker-related methods."""
        from agent_brain_server.providers.factory import ProviderRegistry

        assert hasattr(ProviderRegistry, "register_reranker_provider")
        assert hasattr(ProviderRegistry, "get_reranker_provider")
        assert hasattr(ProviderRegistry, "get_available_reranker_providers")

    def test_reranker_providers_are_registered(self) -> None:
        """Both reranker providers are registered on import."""
        # Import reranker module to trigger registration
        import agent_brain_server.providers.reranker  # noqa: F401
        from agent_brain_server.providers.factory import ProviderRegistry

        available = ProviderRegistry.get_available_reranker_providers()
        assert "sentence-transformers" in available
        assert "ollama" in available
