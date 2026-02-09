"""Graph index manager for GraphRAG (Feature 113).

Manages graph index building and querying for the knowledge graph.
Coordinates between extractors, graph store, and vector store.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from agent_brain_server.config import settings
from agent_brain_server.indexing.graph_extractors import (
    CodeMetadataExtractor,
    LLMEntityExtractor,
    get_code_extractor,
    get_llm_extractor,
)
from agent_brain_server.models.graph import (
    GraphIndexStatus,
    GraphQueryContext,
    GraphTriple,
)
from agent_brain_server.storage.graph_store import (
    GraphStoreManager,
    get_graph_store_manager,
)

logger = logging.getLogger(__name__)


# Type for progress callbacks
ProgressCallback = Callable[[int, int, str], None]


class GraphIndexManager:
    """Manages graph index building and querying.

    Coordinates:
    - Entity extraction from documents (LLM and code metadata)
    - Triplet storage in GraphStoreManager
    - Graph-based retrieval for queries

    All operations are no-ops when ENABLE_GRAPH_INDEX is False.

    Attributes:
        graph_store: The underlying graph store manager.
        llm_extractor: LLM-based entity extractor.
        code_extractor: Code metadata extractor.
    """

    def __init__(
        self,
        graph_store: Optional[GraphStoreManager] = None,
        llm_extractor: Optional[LLMEntityExtractor] = None,
        code_extractor: Optional[CodeMetadataExtractor] = None,
    ) -> None:
        """Initialize graph index manager.

        Args:
            graph_store: Graph store manager (defaults to singleton).
            llm_extractor: LLM extractor (defaults to singleton).
            code_extractor: Code extractor (defaults to singleton).
        """
        self.graph_store = graph_store or get_graph_store_manager()
        self.llm_extractor = llm_extractor or get_llm_extractor()
        self.code_extractor = code_extractor or get_code_extractor()
        self._last_build_time: Optional[datetime] = None
        self._last_triplet_count: int = 0

    def build_from_documents(
        self,
        documents: list[Any],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> int:
        """Build graph index from documents.

        Extracts entities and relationships from document chunks
        and stores them in the graph.

        Args:
            documents: List of document chunks with text and metadata.
            progress_callback: Optional callback(current, total, message).

        Returns:
            Total number of triplets extracted and stored.
        """
        if not settings.ENABLE_GRAPH_INDEX:
            logger.debug(
                "graph_index.build_from_documents: skipped (ENABLE_GRAPH_INDEX=false)"
            )
            return 0

        # Ensure graph store is initialized
        if not self.graph_store.is_initialized:
            logger.info("graph_index.build_from_documents: initializing graph store")
            self.graph_store.initialize()

        total_triplets = 0
        total_docs = len(documents)

        logger.info(
            "graph_index.build_from_documents: starting",
            extra={
                "document_count": total_docs,
                "llm_extraction": settings.GRAPH_USE_LLM_EXTRACTION,
                "code_metadata": settings.GRAPH_USE_CODE_METADATA,
            },
        )

        for idx, doc in enumerate(documents):
            if progress_callback:
                progress_callback(
                    idx + 1,
                    total_docs,
                    f"Extracting entities: {idx + 1}/{total_docs}",
                )

            triplets = self._extract_from_document(doc)

            for triplet in triplets:
                success = self.graph_store.add_triplet(
                    subject=triplet.subject,
                    predicate=triplet.predicate,
                    obj=triplet.object,
                    subject_type=triplet.subject_type,
                    object_type=triplet.object_type,
                    source_chunk_id=triplet.source_chunk_id,
                )
                if success:
                    total_triplets += 1

        # Persist the graph
        self.graph_store.persist()
        self._last_build_time = datetime.now(timezone.utc)
        self._last_triplet_count = total_triplets

        logger.info(
            "graph_index.build_from_documents: completed",
            extra={
                "triplet_count": total_triplets,
                "document_count": total_docs,
                "entity_count": self.graph_store.entity_count,
                "relationship_count": self.graph_store.relationship_count,
            },
        )

        return total_triplets

    def _extract_from_document(self, doc: Any) -> list[GraphTriple]:
        """Extract triplets from a single document.

        Uses both code metadata extractor and LLM extractor
        depending on document type and settings.

        Args:
            doc: Document with text content and metadata.

        Returns:
            List of GraphTriple objects.
        """
        triplets: list[GraphTriple] = []

        # Get document properties
        text = self._get_document_text(doc)
        metadata = self._get_document_metadata(doc)
        chunk_id = self._get_document_id(doc)
        source_type = metadata.get("source_type", "doc")
        language = metadata.get("language")

        # 1. Extract from code metadata (fast, deterministic)
        if source_type == "code" and settings.GRAPH_USE_CODE_METADATA:
            code_triplets = self.code_extractor.extract_from_metadata(
                metadata, source_chunk_id=chunk_id
            )
            triplets.extend(code_triplets)

            # Also try pattern-based extraction from text
            if language:
                text_triplets = self.code_extractor.extract_from_text(
                    text, language=language, source_chunk_id=chunk_id
                )
                triplets.extend(text_triplets)

        # 2. Extract using LLM (slower, more comprehensive)
        if settings.GRAPH_USE_LLM_EXTRACTION and text:
            llm_triplets = self.llm_extractor.extract_triplets(
                text, source_chunk_id=chunk_id
            )
            triplets.extend(llm_triplets)

        return triplets

    def _get_document_text(self, doc: Any) -> str:
        """Get text content from document."""
        if hasattr(doc, "text"):
            return str(doc.text)
        elif hasattr(doc, "get_content"):
            return str(doc.get_content())
        elif hasattr(doc, "page_content"):
            return str(doc.page_content)
        elif isinstance(doc, dict):
            text = doc.get("text", doc.get("content", ""))
            return str(text) if text else ""
        return str(doc)

    def _get_document_metadata(self, doc: Any) -> dict[str, Any]:
        """Get metadata from document."""
        if hasattr(doc, "metadata"):
            meta = doc.metadata
            if hasattr(meta, "to_dict"):
                result = meta.to_dict()
                return dict(result) if result else {}
            elif isinstance(meta, dict):
                return dict(meta)
        elif isinstance(doc, dict):
            meta = doc.get("metadata", {})
            return dict(meta) if meta else {}
        return {}

    def _get_document_id(self, doc: Any) -> Optional[str]:
        """Get document/chunk ID."""
        if hasattr(doc, "chunk_id"):
            val = doc.chunk_id
            return str(val) if val else None
        elif hasattr(doc, "id_"):
            val = doc.id_
            return str(val) if val else None
        elif hasattr(doc, "node_id"):
            val = doc.node_id
            return str(val) if val else None
        elif isinstance(doc, dict):
            val = doc.get("chunk_id", doc.get("id"))
            return str(val) if val else None
        return None

    def query(
        self,
        query_text: str,
        top_k: int = 10,
        traversal_depth: int = 2,
    ) -> list[dict[str, Any]]:
        """Query the graph for related entities and documents.

        Performs entity recognition on query, finds matching nodes,
        and traverses relationships to discover related content.

        Args:
            query_text: Natural language query.
            top_k: Maximum number of results to return.
            traversal_depth: How many hops to traverse in graph.

        Returns:
            List of result dicts with entity info and relationship paths.
        """
        if not settings.ENABLE_GRAPH_INDEX:
            logger.debug(
                "graph_index.query: skipped (ENABLE_GRAPH_INDEX=false)",
                extra={"query": query_text[:100]},
            )
            return []

        if not self.graph_store.is_initialized:
            logger.debug(
                "graph_index.query: skipped (store not initialized)",
                extra={"query": query_text[:100]},
            )
            return []

        # Get graph store for querying
        graph_store = self.graph_store.graph_store
        if graph_store is None:
            logger.debug(
                "graph_index.query: skipped (no graph store)",
                extra={"query": query_text[:100]},
            )
            return []

        results: list[dict[str, Any]] = []

        # Extract potential entity names from query
        query_entities = self._extract_query_entities(query_text)

        logger.debug(
            "graph_index.query: extracted entities",
            extra={
                "query": query_text[:100],
                "entity_count": len(query_entities),
                "entities": query_entities[:5],
            },
        )

        # Find matching entities and their relationships
        for entity in query_entities:
            entity_results = self._find_entity_relationships(
                entity, traversal_depth, top_k
            )
            results.extend(entity_results)

        # Deduplicate and sort by relevance
        seen_keys: set[str] = set()
        unique_results: list[dict[str, Any]] = []
        for result in results:
            # Use source_chunk_id if available, otherwise use relationship path
            chunk_id = result.get("source_chunk_id")
            rel_path = result.get("relationship_path", "")
            dedup_key = chunk_id if chunk_id else rel_path

            if dedup_key and dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                unique_results.append(result)
            elif not dedup_key:
                # No dedup key available, still include result
                unique_results.append(result)

        # Limit to top_k
        final_results = unique_results[:top_k]

        logger.info(
            "graph_index.query: completed",
            extra={
                "query": query_text[:100],
                "result_count": len(final_results),
                "entities_searched": len(query_entities),
                "top_k": top_k,
                "traversal_depth": traversal_depth,
            },
        )

        return final_results

    def _extract_query_entities(self, query_text: str) -> list[str]:
        """Extract potential entity names from query text.

        Uses simple heuristics to identify entity-like terms.

        Args:
            query_text: Query text to analyze.

        Returns:
            List of potential entity names.
        """
        import re

        entities: list[str] = []

        # Split into words
        words = query_text.split()

        # Look for CamelCase or PascalCase words
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r"[^\w]", "", word)
            if not clean_word:
                continue

            # CamelCase detection
            if re.match(r"^[A-Z][a-z]+[A-Z]", clean_word):
                entities.append(clean_word)
            # ALL_CAPS constants
            elif re.match(r"^[A-Z_]+$", clean_word) and len(clean_word) > 2:
                entities.append(clean_word)
            # Capitalized words (potential class names)
            elif clean_word[0].isupper() and len(clean_word) > 2:
                entities.append(clean_word)
            # snake_case function names
            elif "_" in clean_word and clean_word.islower():
                entities.append(clean_word)

        # Also include significant lowercase terms
        for word in words:
            clean_word = re.sub(r"[^\w]", "", word).lower()
            if len(clean_word) > 3 and clean_word not in (
                "what",
                "where",
                "when",
                "which",
                "that",
                "this",
                "have",
                "does",
                "with",
                "from",
                "about",
                "into",
            ):
                if clean_word not in [e.lower() for e in entities]:
                    entities.append(clean_word)

        return entities[:10]  # Limit to prevent query explosion

    def _find_entity_relationships(
        self,
        entity: str,
        depth: int,
        max_results: int,
    ) -> list[dict[str, Any]]:
        """Find entity relationships in the graph.

        Args:
            entity: Entity name to search for.
            depth: Traversal depth.
            max_results: Maximum results per entity.

        Returns:
            List of result dictionaries.
        """
        results: list[dict[str, Any]] = []
        graph_store = self.graph_store.graph_store

        if graph_store is None:
            return results

        # Try to get triplets from graph store
        try:
            if hasattr(graph_store, "get_triplets"):
                triplets = graph_store.get_triplets()
            elif hasattr(graph_store, "_relationships"):
                triplets = graph_store._relationships
            else:
                return results

            # Search for matching entities
            entity_lower = entity.lower()
            matching_triplets: list[Any] = []

            for triplet in triplets:
                subject = self._get_triplet_field(triplet, "subject", "").lower()
                obj = self._get_triplet_field(triplet, "object", "").lower()

                if entity_lower in subject or entity_lower in obj:
                    matching_triplets.append(triplet)

            # Build result entries from matching triplets
            for triplet in matching_triplets[:max_results]:
                result = {
                    "entity": entity,
                    "subject": self._get_triplet_field(triplet, "subject", ""),
                    "predicate": self._get_triplet_field(triplet, "predicate", ""),
                    "object": self._get_triplet_field(triplet, "object", ""),
                    "source_chunk_id": self._get_triplet_field(
                        triplet, "source_chunk_id", None
                    ),
                    "relationship_path": self._format_relationship_path(triplet),
                    "graph_score": 1.0,  # Direct match
                }
                results.append(result)

        except Exception as e:
            logger.warning(f"Error querying graph store: {e}")

        return results

    def _get_triplet_field(self, triplet: Any, field: str, default: Any) -> Any:
        """Get field from triplet (handles both dict and object forms)."""
        if isinstance(triplet, dict):
            return triplet.get(field, default)
        return getattr(triplet, field, default)

    def _format_relationship_path(self, triplet: Any) -> str:
        """Format a triplet as a relationship path string."""
        subject = self._get_triplet_field(triplet, "subject", "?")
        predicate = self._get_triplet_field(triplet, "predicate", "?")
        obj = self._get_triplet_field(triplet, "object", "?")
        return f"{subject} -> {predicate} -> {obj}"

    def get_graph_context(
        self,
        query_text: str,
        top_k: int = 5,
        traversal_depth: int = 2,
    ) -> GraphQueryContext:
        """Get graph context for a query.

        Returns structured context information from the knowledge graph
        that can be used to augment retrieval results.

        Args:
            query_text: Natural language query.
            top_k: Maximum entities to include.
            traversal_depth: Graph traversal depth.

        Returns:
            GraphQueryContext with related entities and paths.
        """
        if not settings.ENABLE_GRAPH_INDEX:
            return GraphQueryContext()

        results = self.query(query_text, top_k=top_k, traversal_depth=traversal_depth)

        if not results:
            return GraphQueryContext()

        # Extract unique entities
        related_entities: list[str] = []
        relationship_paths: list[str] = []
        subgraph_triplets: list[GraphTriple] = []

        seen_entities: set[str] = set()
        for result in results:
            # Add entities
            for entity_field in ["subject", "object"]:
                entity = result.get(entity_field)
                if entity and entity not in seen_entities:
                    seen_entities.add(entity)
                    related_entities.append(entity)

            # Add relationship path
            path = result.get("relationship_path")
            if path and path not in relationship_paths:
                relationship_paths.append(path)

            # Create triplet
            try:
                triplet = GraphTriple(
                    subject=result.get("subject", ""),
                    predicate=result.get("predicate", ""),
                    object=result.get("object", ""),
                    source_chunk_id=result.get("source_chunk_id"),
                )
                subgraph_triplets.append(triplet)
            except Exception:
                pass

        # Calculate average graph score
        scores = [r.get("graph_score", 0.0) for r in results if r.get("graph_score")]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return GraphQueryContext(
            related_entities=related_entities[:top_k],
            relationship_paths=relationship_paths[:top_k],
            subgraph_triplets=subgraph_triplets[:top_k],
            graph_score=min(avg_score, 1.0),
        )

    def get_status(self) -> GraphIndexStatus:
        """Get current graph index status.

        Returns:
            GraphIndexStatus with entity/relationship counts.
        """
        if not settings.ENABLE_GRAPH_INDEX:
            return GraphIndexStatus(
                enabled=False,
                initialized=False,
                entity_count=0,
                relationship_count=0,
                store_type=settings.GRAPH_STORE_TYPE,
            )

        return GraphIndexStatus(
            enabled=True,
            initialized=self.graph_store.is_initialized,
            entity_count=self.graph_store.entity_count,
            relationship_count=self.graph_store.relationship_count,
            last_updated=self.graph_store.last_updated,
            store_type=self.graph_store.store_type,
        )

    def clear(self) -> None:
        """Clear the graph index."""
        if settings.ENABLE_GRAPH_INDEX and self.graph_store.is_initialized:
            prev_triplet_count = self._last_triplet_count
            self.graph_store.clear()
            self._last_build_time = None
            self._last_triplet_count = 0
            logger.info(
                "graph_index.clear: completed",
                extra={"previous_triplet_count": prev_triplet_count},
            )
        else:
            logger.debug(
                "graph_index.clear: skipped",
                extra={
                    "enabled": settings.ENABLE_GRAPH_INDEX,
                    "initialized": (
                        self.graph_store.is_initialized
                        if settings.ENABLE_GRAPH_INDEX
                        else False
                    ),
                },
            )


# Module-level singleton
_graph_index_manager: Optional[GraphIndexManager] = None


def get_graph_index_manager() -> GraphIndexManager:
    """Get the global graph index manager instance."""
    global _graph_index_manager
    if _graph_index_manager is None:
        _graph_index_manager = GraphIndexManager()
    return _graph_index_manager


def reset_graph_index_manager() -> None:
    """Reset the global graph index manager. Used for testing."""
    global _graph_index_manager
    _graph_index_manager = None
