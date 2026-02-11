"""Unit tests for graph models (Feature 113)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agent_brain_server.models import (
    CODE_ENTITY_TYPES,
    DOC_ENTITY_TYPES,
    ENTITY_TYPE_NORMALIZE,
    ENTITY_TYPES,
    INFRA_ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    SYMBOL_TYPE_MAPPING,
    GraphEntity,
    GraphIndexStatus,
    GraphQueryContext,
    GraphTriple,
    normalize_entity_type,
)


class TestGraphTriple:
    """Tests for GraphTriple model."""

    def test_valid_triple(self):
        """Test creating a valid triple."""
        triple = GraphTriple(
            subject="FastAPI",
            predicate="uses",
            object="Pydantic",
        )

        assert triple.subject == "FastAPI"
        assert triple.predicate == "uses"
        assert triple.object == "Pydantic"
        assert triple.subject_type is None
        assert triple.object_type is None
        assert triple.source_chunk_id is None

    def test_triple_with_types(self):
        """Test triple with type classifications."""
        triple = GraphTriple(
            subject="FastAPI",
            subject_type="Framework",
            predicate="uses",
            object="Pydantic",
            object_type="Library",
            source_chunk_id="chunk_123",
        )

        assert triple.subject_type == "Framework"
        assert triple.object_type == "Library"
        assert triple.source_chunk_id == "chunk_123"

    def test_triple_frozen(self):
        """Test that triple is immutable (frozen)."""
        triple = GraphTriple(
            subject="A",
            predicate="relates",
            object="B",
        )

        with pytest.raises(ValidationError):
            triple.subject = "C"  # type: ignore[misc]

    def test_triple_empty_subject_rejected(self):
        """Test that empty subject is rejected."""
        with pytest.raises(ValidationError):
            GraphTriple(
                subject="",
                predicate="relates",
                object="B",
            )

    def test_triple_empty_predicate_rejected(self):
        """Test that empty predicate is rejected."""
        with pytest.raises(ValidationError):
            GraphTriple(
                subject="A",
                predicate="",
                object="B",
            )

    def test_triple_empty_object_rejected(self):
        """Test that empty object is rejected."""
        with pytest.raises(ValidationError):
            GraphTriple(
                subject="A",
                predicate="relates",
                object="",
            )

    def test_triple_serialization(self):
        """Test triple JSON serialization."""
        triple = GraphTriple(
            subject="FastAPI",
            subject_type="Framework",
            predicate="uses",
            object="Pydantic",
            object_type="Library",
        )

        data = triple.model_dump()

        assert data["subject"] == "FastAPI"
        assert data["predicate"] == "uses"
        assert data["object"] == "Pydantic"


class TestGraphEntity:
    """Tests for GraphEntity model."""

    def test_valid_entity(self):
        """Test creating a valid entity."""
        entity = GraphEntity(name="VectorStoreManager")

        assert entity.name == "VectorStoreManager"
        assert entity.entity_type is None
        assert entity.description is None
        assert entity.source_chunk_ids == []
        assert entity.properties == {}

    def test_entity_with_all_fields(self):
        """Test entity with all fields populated."""
        entity = GraphEntity(
            name="VectorStoreManager",
            entity_type="Class",
            description="Manages Chroma vector store",
            source_chunk_ids=["chunk_1", "chunk_2"],
            properties={"module": "storage.vector_store"},
        )

        assert entity.entity_type == "Class"
        assert entity.description == "Manages Chroma vector store"
        assert len(entity.source_chunk_ids) == 2
        assert entity.properties["module"] == "storage.vector_store"

    def test_entity_frozen(self):
        """Test that entity is immutable (frozen)."""
        entity = GraphEntity(name="Test")

        with pytest.raises(ValidationError):
            entity.name = "Modified"  # type: ignore[misc]

    def test_entity_empty_name_rejected(self):
        """Test that empty name is rejected."""
        with pytest.raises(ValidationError):
            GraphEntity(name="")

    def test_entity_serialization(self):
        """Test entity JSON serialization."""
        entity = GraphEntity(
            name="TestClass",
            entity_type="Class",
            source_chunk_ids=["c1"],
        )

        data = entity.model_dump()

        assert data["name"] == "TestClass"
        assert data["entity_type"] == "Class"


class TestGraphIndexStatus:
    """Tests for GraphIndexStatus model."""

    def test_default_status(self):
        """Test default status values."""
        status = GraphIndexStatus()

        assert status.enabled is False
        assert status.initialized is False
        assert status.entity_count == 0
        assert status.relationship_count == 0
        assert status.last_updated is None
        assert status.store_type == "simple"

    def test_status_with_values(self):
        """Test status with populated values."""
        now = datetime.now(timezone.utc)
        status = GraphIndexStatus(
            enabled=True,
            initialized=True,
            entity_count=150,
            relationship_count=320,
            last_updated=now,
            store_type="kuzu",
        )

        assert status.enabled is True
        assert status.initialized is True
        assert status.entity_count == 150
        assert status.relationship_count == 320
        assert status.last_updated == now
        assert status.store_type == "kuzu"

    def test_status_frozen(self):
        """Test that status is immutable (frozen)."""
        status = GraphIndexStatus(enabled=True)

        with pytest.raises(ValidationError):
            status.enabled = False  # type: ignore[misc]

    def test_status_negative_counts_rejected(self):
        """Test that negative counts are rejected."""
        with pytest.raises(ValidationError):
            GraphIndexStatus(entity_count=-1)

        with pytest.raises(ValidationError):
            GraphIndexStatus(relationship_count=-1)

    def test_status_serialization(self):
        """Test status JSON serialization."""
        status = GraphIndexStatus(
            enabled=True,
            entity_count=100,
        )

        data = status.model_dump()

        assert data["enabled"] is True
        assert data["entity_count"] == 100


class TestGraphQueryContext:
    """Tests for GraphQueryContext model."""

    def test_default_context(self):
        """Test default context values."""
        context = GraphQueryContext()

        assert context.related_entities == []
        assert context.relationship_paths == []
        assert context.subgraph_triplets == []
        assert context.graph_score == 0.0

    def test_context_with_values(self):
        """Test context with populated values."""
        triple = GraphTriple(
            subject="FastAPI",
            predicate="uses",
            object="Pydantic",
        )

        context = GraphQueryContext(
            related_entities=["FastAPI", "Pydantic", "Uvicorn"],
            relationship_paths=["FastAPI -> uses -> Pydantic"],
            subgraph_triplets=[triple],
            graph_score=0.85,
        )

        assert len(context.related_entities) == 3
        assert "FastAPI -> uses -> Pydantic" in context.relationship_paths
        assert len(context.subgraph_triplets) == 1
        assert context.graph_score == 0.85

    def test_context_frozen(self):
        """Test that context is immutable (frozen)."""
        context = GraphQueryContext(graph_score=0.5)

        with pytest.raises(ValidationError):
            context.graph_score = 0.8  # type: ignore[misc]

    def test_context_score_bounds(self):
        """Test graph_score validation bounds."""
        # Valid bounds
        GraphQueryContext(graph_score=0.0)
        GraphQueryContext(graph_score=1.0)

        # Invalid bounds
        with pytest.raises(ValidationError):
            GraphQueryContext(graph_score=-0.1)

        with pytest.raises(ValidationError):
            GraphQueryContext(graph_score=1.1)

    def test_context_serialization(self):
        """Test context JSON serialization."""
        context = GraphQueryContext(
            related_entities=["A", "B"],
            graph_score=0.75,
        )

        data = context.model_dump()

        assert data["related_entities"] == ["A", "B"]
        assert data["graph_score"] == 0.75


class TestQueryResultGraphFields:
    """Tests for GraphRAG fields in QueryResult."""

    def test_query_result_with_graph_fields(self):
        """Test QueryResult with graph fields populated."""
        from agent_brain_server.models import QueryResult

        result = QueryResult(
            text="Sample text",
            source="file.py",
            score=0.9,
            chunk_id="chunk_1",
            graph_score=0.85,
            related_entities=["FastAPI", "Pydantic"],
            relationship_path=["FastAPI -> uses -> Pydantic"],
        )

        assert result.graph_score == 0.85
        assert "FastAPI" in result.related_entities  # type: ignore[operator]
        assert "FastAPI -> uses -> Pydantic" in result.relationship_path  # type: ignore[operator]

    def test_query_result_graph_fields_optional(self):
        """Test QueryResult graph fields are optional."""
        from agent_brain_server.models import QueryResult

        result = QueryResult(
            text="Sample text",
            source="file.py",
            score=0.9,
            chunk_id="chunk_1",
        )

        assert result.graph_score is None
        assert result.related_entities is None
        assert result.relationship_path is None

    def test_query_result_serialization_with_graph(self):
        """Test QueryResult serialization includes graph fields."""
        from agent_brain_server.models import QueryResult

        result = QueryResult(
            text="Sample text",
            source="file.py",
            score=0.9,
            chunk_id="chunk_1",
            graph_score=0.75,
            related_entities=["Entity1"],
        )

        data = result.model_dump()

        assert data["graph_score"] == 0.75
        assert data["related_entities"] == ["Entity1"]


class TestEntityTypeSchema:
    """Tests for entity type schema (Feature 122 - Phase 3)."""

    def test_entity_types_complete(self):
        """Test ENTITY_TYPES has exactly 17 entries with expected values."""
        assert len(ENTITY_TYPES) == 17

        # Code types (7)
        assert "Package" in ENTITY_TYPES
        assert "Module" in ENTITY_TYPES
        assert "Class" in ENTITY_TYPES
        assert "Method" in ENTITY_TYPES
        assert "Function" in ENTITY_TYPES
        assert "Interface" in ENTITY_TYPES
        assert "Enum" in ENTITY_TYPES

        # Documentation types (6)
        assert "DesignDoc" in ENTITY_TYPES
        assert "UserDoc" in ENTITY_TYPES
        assert "PRD" in ENTITY_TYPES
        assert "Runbook" in ENTITY_TYPES
        assert "README" in ENTITY_TYPES
        assert "APIDoc" in ENTITY_TYPES

        # Infrastructure types (4)
        assert "Service" in ENTITY_TYPES
        assert "Endpoint" in ENTITY_TYPES
        assert "Database" in ENTITY_TYPES
        assert "ConfigFile" in ENTITY_TYPES

    def test_code_entity_types(self):
        """Test CODE_ENTITY_TYPES contains exactly 7 code types."""
        assert len(CODE_ENTITY_TYPES) == 7
        assert "Package" in CODE_ENTITY_TYPES
        assert "Module" in CODE_ENTITY_TYPES
        assert "Class" in CODE_ENTITY_TYPES
        assert "Method" in CODE_ENTITY_TYPES
        assert "Function" in CODE_ENTITY_TYPES
        assert "Interface" in CODE_ENTITY_TYPES
        assert "Enum" in CODE_ENTITY_TYPES

    def test_doc_entity_types(self):
        """Test DOC_ENTITY_TYPES contains exactly 6 documentation types."""
        assert len(DOC_ENTITY_TYPES) == 6
        assert "DesignDoc" in DOC_ENTITY_TYPES
        assert "UserDoc" in DOC_ENTITY_TYPES
        assert "PRD" in DOC_ENTITY_TYPES
        assert "Runbook" in DOC_ENTITY_TYPES
        assert "README" in DOC_ENTITY_TYPES
        assert "APIDoc" in DOC_ENTITY_TYPES

    def test_infra_entity_types(self):
        """Test INFRA_ENTITY_TYPES contains exactly 4 infrastructure types."""
        assert len(INFRA_ENTITY_TYPES) == 4
        assert "Service" in INFRA_ENTITY_TYPES
        assert "Endpoint" in INFRA_ENTITY_TYPES
        assert "Database" in INFRA_ENTITY_TYPES
        assert "ConfigFile" in INFRA_ENTITY_TYPES

    def test_relationship_types_complete(self):
        """Test RELATIONSHIP_TYPES has exactly 8 predicates."""
        assert len(RELATIONSHIP_TYPES) == 8
        assert "calls" in RELATIONSHIP_TYPES
        assert "extends" in RELATIONSHIP_TYPES
        assert "implements" in RELATIONSHIP_TYPES
        assert "references" in RELATIONSHIP_TYPES
        assert "depends_on" in RELATIONSHIP_TYPES
        assert "imports" in RELATIONSHIP_TYPES
        assert "contains" in RELATIONSHIP_TYPES
        assert "defined_in" in RELATIONSHIP_TYPES

    def test_normalize_entity_type_known(self):
        """Test normalize_entity_type with known lowercase types."""
        assert normalize_entity_type("function") == "Function"
        assert normalize_entity_type("class") == "Class"
        assert normalize_entity_type("method") == "Method"
        assert normalize_entity_type("module") == "Module"
        assert normalize_entity_type("package") == "Package"
        assert normalize_entity_type("interface") == "Interface"
        assert normalize_entity_type("enum") == "Enum"

    def test_normalize_entity_type_case_insensitive(self):
        """Test normalize_entity_type is case-insensitive with acronym preservation."""
        # Uppercase
        assert normalize_entity_type("CLASS") == "Class"
        assert normalize_entity_type("FUNCTION") == "Function"

        # Acronyms must be preserved (not .capitalize() which breaks them)
        assert normalize_entity_type("readme") == "README"
        assert normalize_entity_type("README") == "README"
        assert normalize_entity_type("apidoc") == "APIDoc"
        assert normalize_entity_type("APIDOC") == "APIDoc"
        assert normalize_entity_type("prd") == "PRD"
        assert normalize_entity_type("PRD") == "PRD"

        # Mixed case
        assert normalize_entity_type("ClAsS") == "Class"
        assert normalize_entity_type("fUnCtIoN") == "Function"

    def test_normalize_entity_type_none(self):
        """Test normalize_entity_type returns None for None input."""
        assert normalize_entity_type(None) is None

    def test_normalize_entity_type_unknown(self):
        """Test normalize_entity_type returns original string for unknown types."""
        # Unknown types are passed through (permissive, not strict)
        assert normalize_entity_type("SomeUnknownType") == "SomeUnknownType"
        assert normalize_entity_type("CustomEntity") == "CustomEntity"
        assert normalize_entity_type("Framework") == "Framework"

    def test_symbol_type_mapping_keys(self):
        """Test SYMBOL_TYPE_MAPPING has lowercase keys for all code entity types."""
        # All keys should be lowercase
        for key in SYMBOL_TYPE_MAPPING.keys():
            assert key == key.lower()

        # Verify mappings for code types
        assert SYMBOL_TYPE_MAPPING.get("function") == "Function"
        assert SYMBOL_TYPE_MAPPING.get("class") == "Class"
        assert SYMBOL_TYPE_MAPPING.get("method") == "Method"
        assert SYMBOL_TYPE_MAPPING.get("module") == "Module"
        assert SYMBOL_TYPE_MAPPING.get("package") == "Package"
        assert SYMBOL_TYPE_MAPPING.get("interface") == "Interface"
        assert SYMBOL_TYPE_MAPPING.get("enum") == "Enum"

    def test_triple_backward_compat_untyped(self):
        """Test GraphTriple backward compatibility with untyped entities."""
        # Existing untyped triplets with subject_type=None must still work
        triple = GraphTriple(
            subject="A",
            predicate="uses",
            object="B",
        )

        assert triple.subject == "A"
        assert triple.subject_type is None
        assert triple.object_type is None

    def test_triple_backward_compat_custom_type(self):
        """Test GraphTriple backward compatibility with non-schema types."""
        # Existing triplets with custom types (not in schema) must still work
        triple = GraphTriple(
            subject="FastAPI",
            subject_type="Framework",  # Not in schema, but valid
            predicate="uses",
            object="Pydantic",
            object_type="Library",  # Not in schema, but valid
        )

        assert triple.subject_type == "Framework"
        assert triple.object_type == "Library"

    def test_entity_type_normalize_dict(self):
        """Test ENTITY_TYPE_NORMALIZE dict is populated correctly."""
        # Should have entries for all ENTITY_TYPES (lowercase keys)
        for entity_type in ENTITY_TYPES:
            assert entity_type.lower() in ENTITY_TYPE_NORMALIZE

        # Should also have SYMBOL_TYPE_MAPPING entries
        for key in SYMBOL_TYPE_MAPPING.keys():
            assert key in ENTITY_TYPE_NORMALIZE


class TestQueryRequestGraphFilters:
    """Tests for entity_types and relationship_types fields (SCHEMA-04)."""

    def test_query_request_entity_types_field(self):
        """Test QueryRequest accepts entity_types filter."""
        from agent_brain_server.models import QueryRequest

        request = QueryRequest(query="test query", entity_types=["Class", "Function"])

        assert request.entity_types == ["Class", "Function"]

    def test_query_request_relationship_types_field(self):
        """Test QueryRequest accepts relationship_types filter."""
        from agent_brain_server.models import QueryRequest

        request = QueryRequest(
            query="test query", relationship_types=["calls", "extends"]
        )

        assert request.relationship_types == ["calls", "extends"]

    def test_query_request_defaults_none(self):
        """Test QueryRequest filter fields default to None."""
        from agent_brain_server.models import QueryRequest

        request = QueryRequest(query="test query")

        assert request.entity_types is None
        assert request.relationship_types is None

    def test_query_request_both_filters(self):
        """Test QueryRequest with both filters set."""
        from agent_brain_server.models import QueryRequest

        request = QueryRequest(
            query="test query",
            entity_types=["Class"],
            relationship_types=["calls"],
        )

        assert request.entity_types == ["Class"]
        assert request.relationship_types == ["calls"]

    def test_query_request_serialization_with_filters(self):
        """Test QueryRequest serialization includes filter fields."""
        from agent_brain_server.models import QueryRequest

        request = QueryRequest(
            query="test query",
            entity_types=["Class", "Function"],
            relationship_types=["calls"],
        )

        data = request.model_dump()

        assert data["entity_types"] == ["Class", "Function"]
        assert data["relationship_types"] == ["calls"]
