"""Unit tests for graph extractors (Feature 113)."""

from unittest.mock import MagicMock, patch

import pytest

from agent_brain_server.indexing.graph_extractors import (
    CodeMetadataExtractor,
    LangExtractExtractor,
    LLMEntityExtractor,
    get_code_extractor,
    get_langextract_extractor,
    get_llm_extractor,
    reset_extractors,
)


@pytest.fixture(autouse=True)
def reset_extractor_singletons():
    """Reset extractor singletons before and after each test."""
    reset_extractors()
    yield
    reset_extractors()


class TestLLMEntityExtractor:
    """Tests for LLMEntityExtractor."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        extractor = LLMEntityExtractor()

        assert extractor.model is not None
        assert extractor.max_triplets > 0

    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        extractor = LLMEntityExtractor(
            model="test-model",
            max_triplets=5,
        )

        assert extractor.model == "test-model"
        assert extractor.max_triplets == 5

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_triplets_disabled(self, mock_settings: MagicMock):
        """Test extraction is no-op when graph indexing disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = False

        extractor = LLMEntityExtractor()
        result = extractor.extract_triplets("Some text content")

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_triplets_llm_disabled(self, mock_settings: MagicMock):
        """Test extraction returns empty when LLM extraction disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_LLM_EXTRACTION = False

        extractor = LLMEntityExtractor()
        result = extractor.extract_triplets("Some text content")

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_triplets_no_api_key(self, mock_settings: MagicMock):
        """Test extraction handles missing API key gracefully."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_LLM_EXTRACTION = True
        mock_settings.ANTHROPIC_API_KEY = ""

        extractor = LLMEntityExtractor()
        result = extractor.extract_triplets("Some text content")

        assert result == []

    def test_parse_triplets_3_part(self):
        """Test parsing 3-part triplet format."""
        extractor = LLMEntityExtractor()

        response = """FastAPI | uses | Pydantic
QueryService | calls | VectorStore"""

        triplets = extractor._parse_triplets(response, source_chunk_id="chunk_1")

        assert len(triplets) == 2
        assert triplets[0].subject == "FastAPI"
        assert triplets[0].predicate == "uses"
        assert triplets[0].object == "Pydantic"
        assert triplets[0].source_chunk_id == "chunk_1"

    def test_parse_triplets_5_part(self):
        """Test parsing 5-part triplet format with types."""
        extractor = LLMEntityExtractor()

        response = """FastAPI | Framework | uses | Pydantic | Library"""

        triplets = extractor._parse_triplets(response)

        assert len(triplets) == 1
        assert triplets[0].subject == "FastAPI"
        assert triplets[0].subject_type == "Framework"
        assert triplets[0].predicate == "uses"
        assert triplets[0].object == "Pydantic"
        assert triplets[0].object_type == "Library"

    def test_parse_triplets_invalid_lines(self):
        """Test parsing ignores invalid lines."""
        extractor = LLMEntityExtractor()

        response = """Valid | triplet | here
This is not a triplet
 | empty | subject
Another | valid | one"""

        triplets = extractor._parse_triplets(response)

        assert len(triplets) == 2

    def test_build_extraction_prompt(self):
        """Test prompt building includes text and max count."""
        extractor = LLMEntityExtractor()

        prompt = extractor._build_extraction_prompt("Sample text", max_triplets=5)

        assert "Sample text" in prompt
        assert "5 triplets" in prompt
        assert "SUBJECT" in prompt
        assert "PREDICATE" in prompt

    def test_schema_aware_prompt_contains_entity_types(self):
        """Test schema-aware prompt includes all entity type categories."""
        extractor = LLMEntityExtractor()

        prompt = extractor._build_extraction_prompt("test", max_triplets=5)

        # Code entity types
        assert "Package" in prompt
        assert "Module" in prompt
        assert "Class" in prompt
        assert "Function" in prompt
        assert "Method" in prompt

        # Documentation entity types
        assert "DesignDoc" in prompt
        assert "README" in prompt
        assert "APIDoc" in prompt

        # Infrastructure entity types
        assert "Service" in prompt
        assert "Endpoint" in prompt
        assert "Database" in prompt

    def test_schema_aware_prompt_contains_all_relationship_types(self):
        """Test schema-aware prompt includes all 8 relationship predicates."""
        extractor = LLMEntityExtractor()

        prompt = extractor._build_extraction_prompt("test", max_triplets=5)

        # All 8 relationship types
        assert "calls" in prompt
        assert "extends" in prompt
        assert "implements" in prompt
        assert "references" in prompt
        assert "depends_on" in prompt
        assert "imports" in prompt
        assert "contains" in prompt
        assert "defined_in" in prompt

    def test_parse_triplets_normalizes_types(self):
        """Test _parse_triplets normalizes entity types from LLM response."""
        extractor = LLMEntityExtractor()

        # LLM returns lowercase entity types - should be normalized
        response = "MyClass | class | calls | my_func | function"

        triplets = extractor._parse_triplets(response, source_chunk_id="chunk_1")

        assert len(triplets) == 1
        assert triplets[0].subject == "MyClass"
        assert triplets[0].subject_type == "Class"  # Normalized from "class"
        assert triplets[0].predicate == "calls"
        assert triplets[0].object == "my_func"
        assert triplets[0].object_type == "Function"  # Normalized from "function"
        assert triplets[0].source_chunk_id == "chunk_1"


class TestCodeMetadataExtractor:
    """Tests for CodeMetadataExtractor."""

    def test_init(self):
        """Test initialization."""
        extractor = CodeMetadataExtractor()
        assert extractor is not None

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_from_metadata_disabled(self, mock_settings: MagicMock):
        """Test extraction is no-op when graph indexing disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = False

        extractor = CodeMetadataExtractor()
        result = extractor.extract_from_metadata({"symbol_name": "test"})

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_from_metadata_code_metadata_disabled(
        self, mock_settings: MagicMock
    ):
        """Test extraction returns empty when code metadata disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = False

        extractor = CodeMetadataExtractor()
        result = extractor.extract_from_metadata({"symbol_name": "test"})

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_imports(self, mock_settings: MagicMock):
        """Test extracting import relationships."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = True

        extractor = CodeMetadataExtractor()
        metadata = {
            "symbol_name": "main",
            "symbol_type": "function",
            "imports": ["os", "sys", "typing"],
            "file_path": "src/main.py",
        }

        triplets = extractor.extract_from_metadata(metadata, source_chunk_id="chunk_1")

        # Should have import triplets
        import_triplets = [t for t in triplets if t.predicate == "imports"]
        assert len(import_triplets) == 3

        # Check one of them
        os_import = next((t for t in import_triplets if t.object == "os"), None)
        assert os_import is not None
        assert os_import.object_type == "Module"

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_containment(self, mock_settings: MagicMock):
        """Test extracting containment relationships."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = True

        extractor = CodeMetadataExtractor()
        metadata = {
            "symbol_name": "process_data",
            "symbol_type": "method",
            "parent_symbol": "DataProcessor",
            "file_path": "src/processor.py",
        }

        triplets = extractor.extract_from_metadata(metadata)

        # Should have containment triplet
        contains_triplets = [t for t in triplets if t.predicate == "contains"]
        assert len(contains_triplets) >= 1

        parent_contains = next(
            (t for t in contains_triplets if t.subject == "DataProcessor"), None
        )
        assert parent_contains is not None
        assert parent_contains.object == "process_data"

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_class_method(self, mock_settings: MagicMock):
        """Test extracting class-method relationships."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = True

        extractor = CodeMetadataExtractor()
        metadata = {
            "symbol_name": "get_user",
            "symbol_type": "method",
            "class_name": "UserService",
            "file_path": "src/services.py",
        }

        triplets = extractor.extract_from_metadata(metadata)

        # Should have class contains method
        class_contains = [
            t
            for t in triplets
            if t.predicate == "contains" and t.subject == "UserService"
        ]
        assert len(class_contains) >= 1
        assert class_contains[0].object == "get_user"
        assert class_contains[0].subject_type == "Class"

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_defined_in(self, mock_settings: MagicMock):
        """Test extracting defined_in relationships."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = True

        extractor = CodeMetadataExtractor()
        metadata = {
            "symbol_name": "process",
            "symbol_type": "function",
            "file_path": "src/utils.py",
        }

        triplets = extractor.extract_from_metadata(metadata)

        # Should have defined_in triplet
        defined_in = [t for t in triplets if t.predicate == "defined_in"]
        assert len(defined_in) >= 1
        assert defined_in[0].subject == "process"
        assert defined_in[0].object_type == "Module"

    def test_extract_module_name(self):
        """Test module name extraction from file path."""
        extractor = CodeMetadataExtractor()

        assert extractor._extract_module_name("src/main.py") == "main"
        assert extractor._extract_module_name("lib/utils.ts") == "utils"
        assert extractor._extract_module_name("my-module.js") == "my_module"
        assert extractor._extract_module_name(None) is None
        assert extractor._extract_module_name("") is None

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_from_text_python(self, mock_settings: MagicMock):
        """Test extracting imports from Python code text."""
        mock_settings.ENABLE_GRAPH_INDEX = True

        extractor = CodeMetadataExtractor()
        code = """
import os
import sys
from typing import List, Optional
from pathlib import Path

def main():
    pass
"""

        triplets = extractor.extract_from_text(code, language="python")

        # Should find import statements
        assert len(triplets) >= 4
        modules = {t.object for t in triplets}
        assert "os" in modules
        assert "sys" in modules
        assert "typing" in modules
        assert "pathlib" in modules

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_from_text_javascript(self, mock_settings: MagicMock):
        """Test extracting imports from JavaScript code text."""
        mock_settings.ENABLE_GRAPH_INDEX = True

        extractor = CodeMetadataExtractor()
        code = """
import React from 'react';
import { useState } from 'react';
const lodash = require('lodash');
"""

        triplets = extractor.extract_from_text(code, language="javascript")

        modules = {t.object for t in triplets}
        assert "react" in modules
        assert "lodash" in modules

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_from_text_java(self, mock_settings: MagicMock):
        """Test extracting imports from Java code text."""
        mock_settings.ENABLE_GRAPH_INDEX = True

        extractor = CodeMetadataExtractor()
        code = """
import java.util.List;
import com.example.Service;

public class Main {}
"""

        triplets = extractor.extract_from_text(code, language="java")

        modules = {t.object for t in triplets}
        assert "java.util.List" in modules
        assert "com.example.Service" in modules

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_from_text_go(self, mock_settings: MagicMock):
        """Test extracting imports from Go code text."""
        mock_settings.ENABLE_GRAPH_INDEX = True

        extractor = CodeMetadataExtractor()
        code = """
import "fmt"
import (
    "os"
    "path/filepath"
)
"""

        triplets = extractor.extract_from_text(code, language="go")

        modules = {t.object for t in triplets}
        assert "fmt" in modules
        assert "os" in modules
        assert "path/filepath" in modules

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_from_text_unknown_language(self, mock_settings: MagicMock):
        """Test extracting from unknown language returns empty."""
        mock_settings.ENABLE_GRAPH_INDEX = True

        extractor = CodeMetadataExtractor()
        result = extractor.extract_from_text("some code", language=None)

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_from_text_disabled(self, mock_settings: MagicMock):
        """Test extraction is no-op when disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = False

        extractor = CodeMetadataExtractor()
        result = extractor.extract_from_text("import os", language="python")

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_normalizes_function_type(self, mock_settings: MagicMock):
        """Test extract_from_metadata normalizes 'function' to 'Function'."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = True

        extractor = CodeMetadataExtractor()
        metadata = {
            "symbol_name": "foo",
            "symbol_type": "function",
            "file_path": "src/m.py",
        }

        triplets = extractor.extract_from_metadata(metadata)

        # Check defined_in triplet has normalized subject_type
        defined_in = [t for t in triplets if t.predicate == "defined_in"]
        assert len(defined_in) >= 1
        assert defined_in[0].subject_type == "Function"  # Not "function"

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_normalizes_method_type(self, mock_settings: MagicMock):
        """Test extract_from_metadata normalizes 'method' to 'Method'."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = True

        extractor = CodeMetadataExtractor()
        metadata = {
            "symbol_name": "bar",
            "symbol_type": "method",
            "class_name": "MyClass",
            "file_path": "src/m.py",
        }

        triplets = extractor.extract_from_metadata(metadata)

        # Check class contains method triplet has normalized object_type
        contains = [
            t for t in triplets if t.predicate == "contains" and t.subject == "MyClass"
        ]
        assert len(contains) >= 1
        assert contains[0].object_type == "Method"  # Not "method"

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_normalizes_class_type(self, mock_settings: MagicMock):
        """Test extract_from_metadata normalizes 'class' to 'Class'."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_USE_CODE_METADATA = True

        extractor = CodeMetadataExtractor()
        metadata = {
            "symbol_name": "MyClass",
            "symbol_type": "class",
            "file_path": "src/models.py",
        }

        triplets = extractor.extract_from_metadata(metadata)

        # Check defined_in triplet has normalized subject_type
        defined_in = [t for t in triplets if t.predicate == "defined_in"]
        assert len(defined_in) >= 1
        assert defined_in[0].subject_type == "Class"  # Not "class"


class TestLangExtractExtractor:
    """Tests for LangExtractExtractor."""

    def test_init_with_defaults(self):
        """Test initialization resolves provider from settings."""
        extractor = LangExtractExtractor()

        # provider should be resolved (non-empty string)
        assert extractor.provider is not None
        assert isinstance(extractor.provider, str)
        assert extractor.max_triplets > 0

    def test_init_with_explicit_params(self):
        """Test initialization with explicit provider and model."""
        extractor = LangExtractExtractor(
            provider="openai",
            model="gpt-4o",
            max_triplets=5,
        )

        assert extractor.provider == "openai"
        assert extractor.model == "gpt-4o"
        assert extractor.max_triplets == 5

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_triplets_disabled(self, mock_settings: MagicMock):
        """Test extraction is no-op when graph indexing disabled."""
        mock_settings.ENABLE_GRAPH_INDEX = False
        mock_settings.GRAPH_DOC_EXTRACTOR = "langextract"

        extractor = LangExtractExtractor(provider="ollama")
        result = extractor.extract_triplets("Some document text")

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_triplets_none_extractor(self, mock_settings: MagicMock):
        """Test extraction is no-op when GRAPH_DOC_EXTRACTOR=none."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_DOC_EXTRACTOR = "none"

        extractor = LangExtractExtractor(provider="ollama")
        result = extractor.extract_triplets("Some document text")

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_triplets_empty_text(self, mock_settings: MagicMock):
        """Test extraction returns empty list for empty text."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_DOC_EXTRACTOR = "langextract"

        extractor = LangExtractExtractor(provider="ollama")
        result = extractor.extract_triplets("")

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_triplets_langextract_not_installed(self, mock_settings: MagicMock):
        """Test graceful degradation when langextract is not installed."""
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_DOC_EXTRACTOR = "langextract"

        extractor = LangExtractExtractor(provider="ollama")

        with patch.dict("sys.modules", {"langextract": None}):
            result = extractor.extract_triplets("FastAPI uses Pydantic for validation")

        assert result == []

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_convert_relations_produces_correct_triplets(
        self, mock_settings: MagicMock
    ):
        """Test _convert_relations produces correct GraphTriple list.

        Tests conversion directly rather than mocking langextract's lazy import,
        which is separately covered by the graceful-degradation tests.
        """
        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_DOC_EXTRACTOR = "langextract"

        extractor = LangExtractExtractor(provider="ollama")

        relations = [
            {
                "subject": "FastAPI",
                "relation": "uses",
                "object": "Pydantic",
                "subject_type": "Framework",
                "object_type": "Library",
            },
            {
                "subject": "Agent Brain",
                "relation": "depends_on",
                "object": "ChromaDB",
            },
        ]

        triplets = extractor._convert_relations(relations, source_chunk_id="doc_1")

        assert len(triplets) == 2
        assert triplets[0].subject == "FastAPI"
        assert triplets[0].predicate == "uses"
        assert triplets[0].object == "Pydantic"
        assert triplets[0].source_chunk_id == "doc_1"
        assert triplets[1].subject == "Agent Brain"
        assert triplets[1].predicate == "depends_on"
        assert triplets[1].object == "ChromaDB"

    def test_convert_relations_dict_format(self):
        """Test _convert_relations handles dict-style relations."""
        extractor = LangExtractExtractor(provider="ollama")

        relations = [
            {
                "subject": "FastAPI",
                "relation": "uses",
                "object": "Pydantic",
                "subject_type": "Framework",
                "object_type": "Library",
            }
        ]

        triplets = extractor._convert_relations(relations, source_chunk_id="c1")

        assert len(triplets) == 1
        assert triplets[0].subject == "FastAPI"
        assert triplets[0].predicate == "uses"
        assert triplets[0].object == "Pydantic"
        assert triplets[0].source_chunk_id == "c1"

    def test_convert_relations_head_tail_format(self):
        """Test _convert_relations handles head/tail dict format."""
        extractor = LangExtractExtractor(provider="ollama")

        relations = [
            {
                "head": "Agent Brain",
                "predicate": "depends_on",
                "tail": "ChromaDB",
            }
        ]

        triplets = extractor._convert_relations(relations, source_chunk_id=None)

        assert len(triplets) == 1
        assert triplets[0].subject == "Agent Brain"
        assert triplets[0].predicate == "depends_on"
        assert triplets[0].object == "ChromaDB"

    def test_convert_relations_object_format(self):
        """Test _convert_relations handles object-style relations."""
        extractor = LangExtractExtractor(provider="ollama")

        mock_rel = MagicMock()
        mock_rel.subject = "Service"
        mock_rel.relation = "calls"
        mock_rel.object = "Database"
        mock_rel.subject_type = "Class"
        mock_rel.object_type = "Database"
        # Remove head/tail attributes
        del mock_rel.head
        del mock_rel.tail

        triplets = extractor._convert_relations([mock_rel], source_chunk_id=None)

        assert len(triplets) == 1
        assert triplets[0].subject == "Service"
        assert triplets[0].predicate == "calls"
        assert triplets[0].object == "Database"

    def test_convert_relations_skips_incomplete(self):
        """Test _convert_relations skips relations with missing fields."""
        extractor = LangExtractExtractor(provider="ollama")

        relations = [
            {"subject": "", "relation": "uses", "object": "Pydantic"},
            {"subject": "FastAPI", "relation": "", "object": "Pydantic"},
            {"subject": "FastAPI", "relation": "uses", "object": ""},
        ]

        triplets = extractor._convert_relations(relations, source_chunk_id=None)

        assert triplets == []

    def test_convert_relations_empty_input(self):
        """Test _convert_relations returns empty list for empty input."""
        extractor = LangExtractExtractor(provider="ollama")

        assert extractor._convert_relations([], source_chunk_id=None) == []
        assert extractor._convert_relations(None, source_chunk_id=None) == []  # type: ignore[arg-type]

    @patch("agent_brain_server.indexing.graph_extractors.settings")
    def test_extract_triplets_handles_exception(self, mock_settings: MagicMock):
        """Test extraction returns empty list on unexpected exceptions."""
        import sys

        mock_settings.ENABLE_GRAPH_INDEX = True
        mock_settings.GRAPH_DOC_EXTRACTOR = "langextract"
        mock_settings.GRAPH_MAX_TRIPLETS_PER_CHUNK = 10

        extractor = LangExtractExtractor(provider="ollama", max_triplets=10)

        mock_langextract = MagicMock()
        mock_langextract.extract_relations.side_effect = RuntimeError("provider error")

        original = sys.modules.get("langextract")
        sys.modules["langextract"] = mock_langextract
        try:
            result = extractor.extract_triplets("some text")
        finally:
            if original is None:
                sys.modules.pop("langextract", None)
            else:
                sys.modules["langextract"] = original

        assert result == []


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_llm_extractor_singleton(self):
        """Test get_llm_extractor returns singleton."""
        extractor1 = get_llm_extractor()
        extractor2 = get_llm_extractor()

        assert extractor1 is extractor2

    def test_get_code_extractor_singleton(self):
        """Test get_code_extractor returns singleton."""
        extractor1 = get_code_extractor()
        extractor2 = get_code_extractor()

        assert extractor1 is extractor2

    def test_get_langextract_extractor_singleton(self):
        """Test get_langextract_extractor returns singleton."""
        extractor1 = get_langextract_extractor()
        extractor2 = get_langextract_extractor()

        assert extractor1 is extractor2

    def test_reset_extractors_clears_all(self):
        """Test reset_extractors clears all three singletons."""
        llm1 = get_llm_extractor()
        code1 = get_code_extractor()
        langextract1 = get_langextract_extractor()

        reset_extractors()

        llm2 = get_llm_extractor()
        code2 = get_code_extractor()
        langextract2 = get_langextract_extractor()

        assert llm1 is not llm2
        assert code1 is not code2
        assert langextract1 is not langextract2

    def test_reset_extractors(self):
        """Test reset_extractors clears singletons."""
        extractor1 = get_llm_extractor()
        reset_extractors()
        extractor2 = get_llm_extractor()

        assert extractor1 is not extractor2
