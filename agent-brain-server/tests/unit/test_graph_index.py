"""Unit tests for GraphIndexManager (Feature 113)."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from agent_brain_server.indexing.graph_index import (
    GraphIndexManager,
    get_graph_index_manager,
    reset_graph_index_manager,
)
from agent_brain_server.models.graph import GraphIndexStatus, GraphTriple
from agent_brain_server.storage.graph_store import reset_graph_store_manager


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before and after each test."""
    reset_graph_index_manager()
    reset_graph_store_manager()
    yield
    reset_graph_index_manager()
    reset_graph_store_manager()


@pytest.fixture
def mock_graph_store():
    """Create a mock graph store manager."""
    mock = MagicMock()
    mock.is_initialized = True
    mock.entity_count = 10
    mock.relationship_count = 20
    mock.store_type = "simple"
    mock.last_updated = None
    mock.add_triplet.return_value = True
    mock.graph_store = MagicMock()
    mock.graph_store._relationships = []
    return mock


@pytest.fixture
def mock_llm_extractor():
    """Create a mock LLM extractor."""
    mock = MagicMock()
    mock.extract_triplets.return_value = []
    return mock


@pytest.fixture
def mock_code_extractor():
    """Create a mock code extractor."""
    mock = MagicMock()
    mock.extract_from_metadata.return_value = []
    mock.extract_from_text.return_value = []
    return mock


class TestGraphIndexManagerInitialization:
    """Tests for GraphIndexManager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        manager = GraphIndexManager()

        assert manager.graph_store is not None
        assert manager.llm_extractor is not None
        assert manager.code_extractor is not None

    def test_init_with_custom_deps(
        self, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test initialization with custom dependencies."""
        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        assert manager.graph_store is mock_graph_store
        assert manager.llm_extractor is mock_llm_extractor
        assert manager.code_extractor is mock_code_extractor


class TestGraphIndexManagerBuild:
    """Tests for GraphIndexManager.build_from_documents."""

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_build_disabled(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test build is no-op when graph indexing disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = False

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.build_from_documents([{"text": "test"}])

        assert result == 0
        mock_graph_store.add_triplet.assert_not_called()

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_build_empty_documents(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test build with empty document list."""
        mock_settings.ENABLE_GRAPH_INDEX = True

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.build_from_documents([])

        assert result == 0

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_build_extracts_from_code(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test build extracts from code metadata."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = True
        mock_settings.GRAPH_USE_LLM_EXTRACTION = False

        # Create a sample triplet
        triplet = GraphTriple(
            subject="TestClass",
            predicate="contains",
            object="test_method",
            source_chunk_id="chunk_1",
        )
        mock_code_extractor.extract_from_metadata.return_value = [triplet]

        @dataclass
        class FakeChunk:
            text: str
            chunk_id: str

            @dataclass
            class Metadata:
                source_type: str = "code"
                language: str = "python"

                def to_dict(self):
                    return {"source_type": self.source_type, "language": self.language}

            metadata: Metadata = None

            def __post_init__(self):
                self.metadata = self.Metadata()

        documents = [FakeChunk(text="def test():\n    pass", chunk_id="chunk_1")]

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.build_from_documents(documents)

        assert result == 1
        mock_graph_store.add_triplet.assert_called()
        mock_graph_store.persist.assert_called_once()

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_build_with_progress_callback(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test build calls progress callback."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = False
        mock_settings.GRAPH_USE_LLM_EXTRACTION = False

        progress_calls = []

        def progress_callback(current, total, message):
            progress_calls.append((current, total, message))

        @dataclass
        class FakeDoc:
            text: str = "test"

            @dataclass
            class Metadata:
                source_type: str = "doc"

                def to_dict(self):
                    return {"source_type": self.source_type}

            metadata: Metadata = None

            def __post_init__(self):
                self.metadata = self.Metadata()

        documents = [FakeDoc(), FakeDoc()]

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        manager.build_from_documents(documents, progress_callback=progress_callback)

        assert len(progress_calls) == 2
        assert progress_calls[0][0] == 1
        assert progress_calls[1][0] == 2


class TestGraphIndexManagerQuery:
    """Tests for GraphIndexManager.query."""

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_disabled(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query returns empty when disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = False

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.query("test query")

        assert result == []

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_not_initialized(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query returns empty when not initialized."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = False

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.query("test query")

        assert result == []

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_finds_matching_entities(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query finds matching entities."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True

        # Create a simple object with _relationships (not MagicMock)
        # to avoid hasattr returning True for get_triplets
        class SimpleGraphStore:
            def __init__(self):
                self._relationships = [
                    {
                        "subject": "QueryService",
                        "predicate": "uses",
                        "object": "VectorStore",
                        "source_chunk_id": "chunk_1",
                    }
                ]

        mock_graph_store.graph_store = SimpleGraphStore()

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.query("QueryService implementation")

        assert len(result) >= 1
        assert any(r.get("subject") == "QueryService" for r in result)

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_respects_top_k(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query respects top_k limit."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True
        mock_graph_store.graph_store._relationships = [
            {"subject": f"Entity{i}", "predicate": "relates", "object": f"Other{i}"}
            for i in range(20)
        ]

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.query("Entity", top_k=5)

        assert len(result) <= 5


class TestGraphIndexManagerGetContext:
    """Tests for GraphIndexManager.get_graph_context."""

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_get_context_disabled(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test get_graph_context returns empty when disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = False

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.get_graph_context("test query")

        assert result.related_entities == []
        assert result.relationship_paths == []
        assert result.graph_score == 0.0

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_get_context_returns_entities(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test get_graph_context returns related entities."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True

        # Create a simple object with _relationships (not MagicMock)
        # to avoid hasattr returning True for get_triplets
        class SimpleGraphStore:
            def __init__(self):
                self._relationships = [
                    {
                        "subject": "FastAPI",
                        "predicate": "uses",
                        "object": "Pydantic",
                        "source_chunk_id": "chunk_1",
                    }
                ]

        mock_graph_store.graph_store = SimpleGraphStore()

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.get_graph_context("FastAPI framework")

        assert len(result.related_entities) >= 1
        assert len(result.relationship_paths) >= 1


class TestGraphIndexManagerStatus:
    """Tests for GraphIndexManager.get_status."""

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_get_status_disabled(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test get_status when disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = False
        mock_settings.GRAPH_STORE_TYPE = "simple"

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        status = manager.get_status()

        assert isinstance(status, GraphIndexStatus)
        assert status.enabled is False
        assert status.entity_count == 0

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_get_status_enabled(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test get_status when enabled."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True
        mock_graph_store.entity_count = 50
        mock_graph_store.relationship_count = 100

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        status = manager.get_status()

        assert status.enabled is True
        assert status.initialized is True
        assert status.entity_count == 50
        assert status.relationship_count == 100


class TestGraphIndexManagerClear:
    """Tests for GraphIndexManager.clear."""

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_clear_graph(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test clearing the graph index."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        manager.clear()

        mock_graph_store.clear.assert_called_once()


class TestExtractQueryEntities:
    """Tests for entity extraction from queries."""

    def test_extract_camelcase(self, mock_graph_store):
        """Test extracting CamelCase entities."""
        manager = GraphIndexManager(graph_store=mock_graph_store)

        entities = manager._extract_query_entities("How does QueryService work?")

        assert "QueryService" in entities

    def test_extract_pascal_case(self, mock_graph_store):
        """Test extracting PascalCase entities."""
        manager = GraphIndexManager(graph_store=mock_graph_store)

        entities = manager._extract_query_entities("Using FastAPI framework")

        assert "FastAPI" in entities

    def test_extract_snake_case(self, mock_graph_store):
        """Test extracting snake_case entities."""
        manager = GraphIndexManager(graph_store=mock_graph_store)

        entities = manager._extract_query_entities(
            "The get_user_by_id function returns"
        )

        assert "get_user_by_id" in entities

    def test_extract_limits_count(self, mock_graph_store):
        """Test entity extraction limits count."""
        manager = GraphIndexManager(graph_store=mock_graph_store)

        # Create a query with many words
        query = " ".join([f"Entity{i}" for i in range(50)])
        entities = manager._extract_query_entities(query)

        assert len(entities) <= 10


class TestQueryByType:
    """Tests for GraphIndexManager.query_by_type (SCHEMA-04)."""

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_by_type_no_filters(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query_by_type without filters delegates to base query."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True

        class SimpleGraphStore:
            def __init__(self):
                self._relationships = [
                    {
                        "subject": "FastAPI",
                        "subject_type": "Class",
                        "predicate": "uses",
                        "object": "Pydantic",
                        "object_type": "Class",
                        "source_chunk_id": "chunk_1",
                    }
                ]

        mock_graph_store.graph_store = SimpleGraphStore()

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        # Call without filters should behave like base query
        result = manager.query_by_type(
            "FastAPI", entity_types=None, relationship_types=None
        )

        assert len(result) >= 1

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_by_type_entity_filter(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query_by_type filters by entity types."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True

        class SimpleGraphStore:
            def __init__(self):
                self._relationships = [
                    {
                        "subject": "MyClass",
                        "subject_type": "Class",
                        "predicate": "contains",
                        "object": "my_method",
                        "object_type": "Method",
                        "source_chunk_id": "chunk_1",
                    },
                    {
                        "subject": "my_package",
                        "subject_type": "Package",
                        "predicate": "contains",
                        "object": "MyClass",
                        "object_type": "Class",
                        "source_chunk_id": "chunk_2",
                    },
                    {
                        "subject": "standalone_func",
                        "subject_type": "Function",
                        "predicate": "calls",
                        "object": "other_func",
                        "object_type": "Function",
                        "source_chunk_id": "chunk_3",
                    },
                ]

        mock_graph_store.graph_store = SimpleGraphStore()

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        # Filter to only Class entities
        result = manager.query_by_type(
            "MyClass", entity_types=["Class"], relationship_types=None, top_k=10
        )

        # Should return only results involving Class entities
        for r in result:
            subject_type = r.get("subject_type")
            object_type = r.get("object_type")
            assert subject_type == "Class" or object_type == "Class"

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_by_type_relationship_filter(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query_by_type filters by relationship types."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True

        class SimpleGraphStore:
            def __init__(self):
                self._relationships = [
                    {
                        "subject": "ClassA",
                        "subject_type": "Class",
                        "predicate": "calls",
                        "object": "method_b",
                        "object_type": "Method",
                        "source_chunk_id": "chunk_1",
                    },
                    {
                        "subject": "ClassA",
                        "subject_type": "Class",
                        "predicate": "extends",
                        "object": "ClassB",
                        "object_type": "Class",
                        "source_chunk_id": "chunk_2",
                    },
                    {
                        "subject": "module_a",
                        "subject_type": "Module",
                        "predicate": "imports",
                        "object": "module_b",
                        "object_type": "Module",
                        "source_chunk_id": "chunk_3",
                    },
                ]

        mock_graph_store.graph_store = SimpleGraphStore()

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        # Filter to only "calls" relationships
        result = manager.query_by_type(
            "ClassA", entity_types=None, relationship_types=["calls"], top_k=10
        )

        # Should return only "calls" relationships
        for r in result:
            assert r.get("predicate") == "calls"

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_by_type_combined_filters(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query_by_type with both entity and relationship filters."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True

        class SimpleGraphStore:
            def __init__(self):
                self._relationships = [
                    {
                        "subject": "ClassA",
                        "subject_type": "Class",
                        "predicate": "calls",
                        "object": "method_b",
                        "object_type": "Method",
                        "source_chunk_id": "chunk_1",
                    },
                    {
                        "subject": "ClassA",
                        "subject_type": "Class",
                        "predicate": "extends",
                        "object": "ClassB",
                        "object_type": "Class",
                        "source_chunk_id": "chunk_2",
                    },
                    {
                        "subject": "func_a",
                        "subject_type": "Function",
                        "predicate": "calls",
                        "object": "func_b",
                        "object_type": "Function",
                        "source_chunk_id": "chunk_3",
                    },
                ]

        mock_graph_store.graph_store = SimpleGraphStore()

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        # Filter to Class entities with "extends" relationship
        result = manager.query_by_type(
            "ClassA",
            entity_types=["Class"],
            relationship_types=["extends"],
            top_k=10,
        )

        # Should return only results matching both filters
        assert len(result) == 1
        assert result[0].get("predicate") == "extends"
        assert result[0].get("subject_type") == "Class"

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_by_type_empty_after_filter(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query_by_type returns empty when filters match nothing."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_graph_store.is_initialized = True

        class SimpleGraphStore:
            def __init__(self):
                self._relationships = [
                    {
                        "subject": "ClassA",
                        "subject_type": "Class",
                        "predicate": "calls",
                        "object": "method_b",
                        "object_type": "Method",
                        "source_chunk_id": "chunk_1",
                    }
                ]

        mock_graph_store.graph_store = SimpleGraphStore()

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        # Filter with non-matching entity types
        result = manager.query_by_type(
            "ClassA", entity_types=["Package"], relationship_types=None, top_k=10
        )

        assert len(result) == 0

    @patch("agent_brain_server.indexing.graph_index.settings")
    def test_query_by_type_disabled(
        self, mock_settings, mock_graph_store, mock_llm_extractor, mock_code_extractor
    ):
        """Test query_by_type returns empty when ENABLE_GRAPH_INDEX is False."""
        mock_settings.ENABLE_GRAPH_INDEX = False

        manager = GraphIndexManager(
            graph_store=mock_graph_store,
            llm_extractor=mock_llm_extractor,
            code_extractor=mock_code_extractor,
        )

        result = manager.query_by_type(
            "test", entity_types=["Class"], relationship_types=None, top_k=10
        )

        assert result == []


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_graph_index_manager_singleton(self):
        """Test get_graph_index_manager returns singleton."""
        manager1 = get_graph_index_manager()
        manager2 = get_graph_index_manager()

        assert manager1 is manager2

    def test_reset_graph_index_manager(self):
        """Test reset_graph_index_manager clears singleton."""
        manager1 = get_graph_index_manager()
        reset_graph_index_manager()
        manager2 = get_graph_index_manager()

        assert manager1 is not manager2
