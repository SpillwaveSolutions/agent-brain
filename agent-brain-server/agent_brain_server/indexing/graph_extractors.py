"""Entity extraction for GraphRAG (Feature 113).

Provides extractors for building the knowledge graph:
- LLMEntityExtractor: Uses LLM to extract entity-relationship triplets
- CodeMetadataExtractor: Extracts relationships from code AST metadata

All extractors return GraphTriple objects for graph construction.
"""

import logging
import re
from typing import Any

from agent_brain_server.config import settings
from agent_brain_server.models.graph import (
    CODE_ENTITY_TYPES,
    DOC_ENTITY_TYPES,
    ENTITY_TYPES,
    INFRA_ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    GraphTriple,
    normalize_entity_type,
)

logger = logging.getLogger(__name__)


class LLMEntityExtractor:
    """Wrapper for LLM-based entity extraction.

    Uses Claude to extract entity-relationship triplets from text.
    Implements graceful degradation when LLM is unavailable.

    Attributes:
        model: The LLM model to use for extraction.
        max_triplets: Maximum triplets to extract per chunk.
    """

    def __init__(
        self,
        model: str | None = None,
        max_triplets: int | None = None,
    ) -> None:
        """Initialize LLM entity extractor.

        Args:
            model: LLM model to use (defaults to settings.GRAPH_EXTRACTION_MODEL).
            max_triplets: Max triplets per chunk (defaults to settings value).
        """
        self.model = model or settings.GRAPH_EXTRACTION_MODEL
        self.max_triplets = max_triplets or settings.GRAPH_MAX_TRIPLETS_PER_CHUNK
        self._client: Any | None = None

    def _get_client(self) -> Any | None:
        """Get or create Anthropic client.

        Returns:
            Anthropic client or None if unavailable.
        """
        if self._client is not None:
            return self._client

        try:
            import anthropic

            api_key = settings.ANTHROPIC_API_KEY
            if not api_key:
                logger.debug("No Anthropic API key, LLM extraction disabled")
                return None

            self._client = anthropic.Anthropic(api_key=api_key)
            return self._client
        except ImportError:
            logger.debug("Anthropic SDK not installed, LLM extraction disabled")
            return None
        except Exception as e:
            logger.warning(f"Failed to create Anthropic client: {e}")
            return None

    def extract_triplets(
        self,
        text: str,
        max_triplets: int | None = None,
        source_chunk_id: str | None = None,
    ) -> list[GraphTriple]:
        """Extract entity-relationship triplets from text using LLM.

        Args:
            text: Text content to extract entities from.
            max_triplets: Override for max triplets (uses instance default).
            source_chunk_id: Optional source chunk ID for provenance.

        Returns:
            List of GraphTriple objects extracted from text.
            Returns empty list on failure (graceful degradation).
        """
        if not settings.ENABLE_GRAPH_INDEX:
            return []

        if not settings.GRAPH_USE_LLM_EXTRACTION:
            logger.debug("LLM extraction disabled in settings")
            return []

        client = self._get_client()
        if client is None:
            return []

        max_count = max_triplets or self.max_triplets

        # Truncate very long text to avoid token limits
        max_chars = 4000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        prompt = self._build_extraction_prompt(text, max_count)

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text
            triplets = self._parse_triplets(response_text, source_chunk_id)

            logger.debug(
                "llm_extractor.extract_triplets: completed",
                extra={
                    "triplet_count": len(triplets),
                    "model": self.model,
                    "text_length": len(text),
                    "source_chunk_id": source_chunk_id,
                },
            )
            return triplets

        except Exception as e:
            logger.warning(
                "llm_extractor.extract_triplets: failed",
                extra={
                    "error": str(e),
                    "model": self.model,
                    "text_length": len(text),
                    "source_chunk_id": source_chunk_id,
                },
            )
            return []

    def _build_extraction_prompt(self, text: str, max_triplets: int) -> str:
        """Build schema-aware extraction prompt for the LLM.

        Includes full schema vocabulary organized by category to guide LLM extraction.

        Args:
            text: Text to extract from.
            max_triplets: Maximum number of triplets to request.

        Returns:
            Formatted prompt string with schema vocabulary.
        """
        # Build entity type lists organized by category
        code_types = ", ".join(CODE_ENTITY_TYPES)
        doc_types = ", ".join(DOC_ENTITY_TYPES)
        infra_types = ", ".join(INFRA_ENTITY_TYPES)
        predicates = ", ".join(RELATIONSHIP_TYPES)

        return f"""Extract key entity relationships from the following text.
Return up to {max_triplets} triplets in the format:
SUBJECT | SUBJECT_TYPE | PREDICATE | OBJECT | OBJECT_TYPE

Valid entity types (SUBJECT_TYPE / OBJECT_TYPE):
- Code: {code_types}
- Documentation: {doc_types}
- Infrastructure: {infra_types}

Valid relationships (PREDICATE):
{predicates}

Rules:
- Use exact type/predicate names from lists above
- Prefer specific types (Method over Function for class methods)
- One triplet per line
- Only output triplets, no explanations

Text:
{text}

Triplets:"""

    def _parse_triplets(
        self,
        response: str,
        source_chunk_id: str | None = None,
    ) -> list[GraphTriple]:
        """Parse triplets from LLM response with schema normalization.

        Normalizes entity types and predicates to match schema vocabulary.
        Logs warnings for unknown types but remains permissive.

        Args:
            response: Raw LLM response text.
            source_chunk_id: Optional source chunk ID.

        Returns:
            List of parsed GraphTriple objects with normalized types.
        """
        triplets: list[GraphTriple] = []

        for line in response.strip().split("\n"):
            line = line.strip()
            if not line or "|" not in line:
                continue

            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                continue

            # Handle both 3-part and 5-part formats
            if len(parts) == 3:
                subject, predicate, obj = parts
                subject_type = None
                object_type = None
            elif len(parts) >= 5:
                subject, subject_type_raw, predicate, obj, object_type_raw = parts[:5]
                # Normalize entity types using schema
                subject_type = normalize_entity_type(subject_type_raw if subject_type_raw else None)
                object_type = normalize_entity_type(object_type_raw if object_type_raw else None)

                # Log debug warnings for unknown entity types (permissive, not strict)
                if subject_type and subject_type not in ENTITY_TYPES:
                    logger.debug(f"Unknown subject_type from LLM: {subject_type}")
                if object_type and object_type not in ENTITY_TYPES:
                    logger.debug(f"Unknown object_type from LLM: {object_type}")
            else:
                continue

            # Normalize predicate: lowercase and strip
            predicate = predicate.lower().strip()

            # Log debug warning for unknown predicates (permissive)
            if predicate not in RELATIONSHIP_TYPES:
                logger.debug(f"Unknown predicate from LLM: {predicate}")

            # Validate and clean
            if not subject or not predicate or not obj:
                continue

            try:
                triplet = GraphTriple(
                    subject=subject,
                    subject_type=subject_type,
                    predicate=predicate,
                    object=obj,
                    object_type=object_type,
                    source_chunk_id=source_chunk_id,
                )
                triplets.append(triplet)
            except Exception as e:
                logger.debug(f"Failed to create triplet: {e}")
                continue

        return triplets


class CodeMetadataExtractor:
    """Extract relationships from code AST metadata.

    Analyzes code chunk metadata to extract structural relationships
    such as imports, containment, and function calls.

    This extractor uses pre-computed AST metadata from the code chunking
    pipeline, making it fast and deterministic.
    """

    # Common relationship predicates for code (aligned with RelationshipType schema)
    PREDICATE_IMPORTS = "imports"          # matches RelationshipType
    PREDICATE_CONTAINS = "contains"        # matches RelationshipType
    PREDICATE_CALLS = "calls"              # matches RelationshipType
    PREDICATE_EXTENDS = "extends"          # matches RelationshipType
    PREDICATE_IMPLEMENTS = "implements"    # matches RelationshipType
    PREDICATE_DEFINED_IN = "defined_in"    # matches RelationshipType

    def __init__(self) -> None:
        """Initialize code metadata extractor."""
        pass

    def extract_from_metadata(
        self,
        metadata: dict[str, Any],
        source_chunk_id: str | None = None,
    ) -> list[GraphTriple]:
        """Extract import and containment relationships from code metadata.

        Looks for standard code metadata fields:
        - 'imports': List of imported modules/symbols
        - 'symbol_name': Name of the current code symbol
        - 'symbol_type': Type of symbol (function, class, method)
        - 'parent_symbol': Parent containing symbol
        - 'file_path': Source file path

        Args:
            metadata: Code chunk metadata dictionary.
            source_chunk_id: Optional source chunk ID for provenance.

        Returns:
            List of GraphTriple objects extracted from metadata.
        """
        if not settings.ENABLE_GRAPH_INDEX:
            return []

        if not settings.GRAPH_USE_CODE_METADATA:
            return []

        triplets: list[GraphTriple] = []

        symbol_name = metadata.get("symbol_name")
        symbol_type = metadata.get("symbol_type")
        parent_symbol = metadata.get("parent_symbol")
        file_path = metadata.get("file_path") or metadata.get("source")
        imports = metadata.get("imports", [])
        class_name = metadata.get("class_name")

        # Extract module name from file path
        module_name = self._extract_module_name(file_path) if file_path else None

        # 1. Symbol -> imports -> ImportedModule
        if isinstance(imports, list):
            for imp in imports:
                if isinstance(imp, str) and imp:
                    triplet = GraphTriple(
                        subject=symbol_name or module_name or "unknown",
                        subject_type=normalize_entity_type(symbol_type) or "Module",
                        predicate=self.PREDICATE_IMPORTS,
                        object=imp,
                        object_type="Module",
                        source_chunk_id=source_chunk_id,
                    )
                    triplets.append(triplet)

        # 2. Parent -> contains -> Symbol
        if symbol_name and parent_symbol:
            triplet = GraphTriple(
                subject=parent_symbol,
                subject_type="Class" if "." not in parent_symbol else "Module",
                predicate=self.PREDICATE_CONTAINS,
                object=symbol_name,
                object_type=normalize_entity_type(symbol_type) or "Symbol",
                source_chunk_id=source_chunk_id,
            )
            triplets.append(triplet)

        # 3. Class -> contains -> Method (for methods)
        if symbol_name and class_name and symbol_type in ("method", "function"):
            if class_name != symbol_name:  # Avoid self-reference
                triplet = GraphTriple(
                    subject=class_name,
                    subject_type="Class",
                    predicate=self.PREDICATE_CONTAINS,
                    object=symbol_name,
                    object_type=normalize_entity_type(symbol_type),
                    source_chunk_id=source_chunk_id,
                )
                triplets.append(triplet)

        # 4. Module -> contains -> TopLevelSymbol
        if module_name and symbol_name and not parent_symbol and not class_name:
            triplet = GraphTriple(
                subject=module_name,
                subject_type="Module",
                predicate=self.PREDICATE_CONTAINS,
                object=symbol_name,
                object_type=normalize_entity_type(symbol_type) or "Symbol",
                source_chunk_id=source_chunk_id,
            )
            triplets.append(triplet)

        # 5. Symbol -> defined_in -> Module
        if symbol_name and module_name:
            triplet = GraphTriple(
                subject=symbol_name,
                subject_type=normalize_entity_type(symbol_type) or "Symbol",
                predicate=self.PREDICATE_DEFINED_IN,
                object=module_name,
                object_type="Module",
                source_chunk_id=source_chunk_id,
            )
            triplets.append(triplet)

        logger.debug(
            "code_extractor.extract_from_metadata: completed",
            extra={
                "triplet_count": len(triplets),
                "symbol_name": symbol_name,
                "symbol_type": symbol_type,
                "file_path": file_path,
                "import_count": len(imports) if isinstance(imports, list) else 0,
                "source_chunk_id": source_chunk_id,
            },
        )
        return triplets

    def _extract_module_name(self, file_path: str) -> str | None:
        """Extract module name from file path.

        Args:
            file_path: Path to source file.

        Returns:
            Module name derived from file path, or None.
        """
        if not file_path:
            return None

        # Remove common prefixes and extensions
        path = file_path.replace("\\", "/")

        # Get just the filename without extension
        if "/" in path:
            path = path.rsplit("/", 1)[-1]

        # Remove extension
        if "." in path:
            path = path.rsplit(".", 1)[0]

        # Clean up invalid characters
        path = re.sub(r"[^a-zA-Z0-9_]", "_", path)

        return path if path else None

    def extract_from_text(
        self,
        text: str,
        language: str | None = None,
        source_chunk_id: str | None = None,
    ) -> list[GraphTriple]:
        """Extract relationships from code text using pattern matching.

        This is a fallback when AST metadata is not available.
        Uses regex patterns to identify imports and definitions.

        Args:
            text: Code text content.
            language: Programming language (python, javascript, etc.).
            source_chunk_id: Optional source chunk ID.

        Returns:
            List of GraphTriple objects.
        """
        if not settings.ENABLE_GRAPH_INDEX:
            return []

        triplets: list[GraphTriple] = []

        if not language:
            return triplets

        language = language.lower()

        # Extract Python imports
        if language == "python":
            triplets.extend(self._extract_python_imports(text, source_chunk_id))

        # Extract JavaScript/TypeScript imports
        elif language in ("javascript", "typescript", "tsx", "jsx"):
            triplets.extend(self._extract_js_imports(text, source_chunk_id))

        # Extract Java imports
        elif language == "java":
            triplets.extend(self._extract_java_imports(text, source_chunk_id))

        # Extract Go imports
        elif language == "go":
            triplets.extend(self._extract_go_imports(text, source_chunk_id))

        return triplets

    def _extract_python_imports(
        self,
        text: str,
        source_chunk_id: str | None,
    ) -> list[GraphTriple]:
        """Extract imports from Python code."""
        triplets: list[GraphTriple] = []

        # Match: import module
        for match in re.finditer(r"^import\s+([\w.]+)", text, re.MULTILINE):
            module = match.group(1)
            triplets.append(
                GraphTriple(
                    subject="current_module",
                    subject_type="Module",
                    predicate=self.PREDICATE_IMPORTS,
                    object=module,
                    object_type="Module",
                    source_chunk_id=source_chunk_id,
                )
            )

        # Match: from module import ...
        for match in re.finditer(r"^from\s+([\w.]+)\s+import", text, re.MULTILINE):
            module = match.group(1)
            triplets.append(
                GraphTriple(
                    subject="current_module",
                    subject_type="Module",
                    predicate=self.PREDICATE_IMPORTS,
                    object=module,
                    object_type="Module",
                    source_chunk_id=source_chunk_id,
                )
            )

        return triplets

    def _extract_js_imports(
        self,
        text: str,
        source_chunk_id: str | None,
    ) -> list[GraphTriple]:
        """Extract imports from JavaScript/TypeScript code."""
        triplets: list[GraphTriple] = []

        # Match: import ... from 'module'
        for match in re.finditer(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", text):
            module = match.group(1)
            triplets.append(
                GraphTriple(
                    subject="current_module",
                    subject_type="Module",
                    predicate=self.PREDICATE_IMPORTS,
                    object=module,
                    object_type="Module",
                    source_chunk_id=source_chunk_id,
                )
            )

        # Match: require('module')
        for match in re.finditer(r"require\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", text):
            module = match.group(1)
            triplets.append(
                GraphTriple(
                    subject="current_module",
                    subject_type="Module",
                    predicate=self.PREDICATE_IMPORTS,
                    object=module,
                    object_type="Module",
                    source_chunk_id=source_chunk_id,
                )
            )

        return triplets

    def _extract_java_imports(
        self,
        text: str,
        source_chunk_id: str | None,
    ) -> list[GraphTriple]:
        """Extract imports from Java code."""
        triplets: list[GraphTriple] = []

        # Match: import package.Class;
        for match in re.finditer(r"^import\s+([\w.]+);", text, re.MULTILINE):
            module = match.group(1)
            triplets.append(
                GraphTriple(
                    subject="current_module",
                    subject_type="Module",
                    predicate=self.PREDICATE_IMPORTS,
                    object=module,
                    object_type="Class",
                    source_chunk_id=source_chunk_id,
                )
            )

        return triplets

    def _extract_go_imports(
        self,
        text: str,
        source_chunk_id: str | None,
    ) -> list[GraphTriple]:
        """Extract imports from Go code."""
        triplets: list[GraphTriple] = []

        # Match: import "package"
        for match in re.finditer(r'import\s+"([^"]+)"', text):
            module = match.group(1)
            triplets.append(
                GraphTriple(
                    subject="current_module",
                    subject_type="Module",
                    predicate=self.PREDICATE_IMPORTS,
                    object=module,
                    object_type="Package",
                    source_chunk_id=source_chunk_id,
                )
            )

        # Match imports in parentheses
        import_block = re.search(r"import\s*\((.*?)\)", text, re.DOTALL)
        if import_block:
            for match in re.finditer(r'"([^"]+)"', import_block.group(1)):
                module = match.group(1)
                triplets.append(
                    GraphTriple(
                        subject="current_module",
                        subject_type="Module",
                        predicate=self.PREDICATE_IMPORTS,
                        object=module,
                        object_type="Package",
                        source_chunk_id=source_chunk_id,
                    )
                )

        return triplets


# Module-level singleton instances
_llm_extractor: LLMEntityExtractor | None = None
_code_extractor: CodeMetadataExtractor | None = None


def get_llm_extractor() -> LLMEntityExtractor:
    """Get the global LLM entity extractor instance."""
    global _llm_extractor
    if _llm_extractor is None:
        _llm_extractor = LLMEntityExtractor()
    return _llm_extractor


def get_code_extractor() -> CodeMetadataExtractor:
    """Get the global code metadata extractor instance."""
    global _code_extractor
    if _code_extractor is None:
        _code_extractor = CodeMetadataExtractor()
    return _code_extractor


def reset_extractors() -> None:
    """Reset extractor singletons. Used for testing."""
    global _llm_extractor, _code_extractor
    _llm_extractor = None
    _code_extractor = None
