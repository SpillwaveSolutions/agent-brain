"""PostgreSQL storage backend implementing StorageBackendProtocol.

This module provides the PostgresBackend class which implements all 11
StorageBackendProtocol methods using pgvector for vector similarity search,
tsvector for full-text keyword search, and RRF for hybrid search fusion.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from agent_brain_server.config.provider_config import (
    load_provider_settings,
)
from agent_brain_server.providers.exceptions import ProviderMismatchError
from agent_brain_server.providers.factory import ProviderRegistry
from agent_brain_server.storage.postgres.config import PostgresConfig
from agent_brain_server.storage.postgres.connection import (
    PostgresConnectionManager,
)
from agent_brain_server.storage.postgres.keyword_ops import KeywordOps
from agent_brain_server.storage.postgres.schema import (
    PostgresSchemaManager,
)
from agent_brain_server.storage.postgres.vector_ops import VectorOps
from agent_brain_server.storage.protocol import (
    EmbeddingMetadata,
    SearchResult,
    StorageError,
)

logger = logging.getLogger(__name__)


class PostgresBackend:
    """PostgreSQL storage backend implementing StorageBackendProtocol.

    Composes PostgresConnectionManager, PostgresSchemaManager, VectorOps,
    and KeywordOps to provide a full async storage backend using pgvector
    for vector search and tsvector for keyword search.

    All scores are normalized to 0-1 (higher = better). All exceptions
    are wrapped in StorageError with ``backend="postgres"``.

    Attributes:
        config: PostgreSQL configuration.
    """

    def __init__(self, config: PostgresConfig) -> None:
        """Initialize PostgresBackend.

        Args:
            config: PostgreSQL configuration with connection,
                pool, HNSW, and language parameters.
        """
        self.config = config
        self.connection_manager = PostgresConnectionManager(config)
        self.schema_manager: PostgresSchemaManager | None = None
        self.vector_ops = VectorOps(self.connection_manager)
        self.keyword_ops = KeywordOps(self.connection_manager, language=config.language)
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if the storage backend is initialized.

        Returns:
            True if backend is ready for operations.
        """
        return self._initialized

    async def initialize(self) -> None:
        """Initialize the PostgreSQL backend.

        Connects to PostgreSQL with retry, discovers embedding
        dimensions from the provider registry, creates schema
        with pgvector/tsvector tables and indexes, and validates
        dimension consistency.

        Raises:
            StorageError: If initialization fails.
        """
        try:
            # 1. Connect with exponential backoff retry
            await self.connection_manager.initialize_with_retry()

            # 2. Discover embedding dimensions from provider config
            provider_settings = load_provider_settings()
            embedding_provider = ProviderRegistry.get_embedding_provider(
                provider_settings.embedding
            )
            dimensions = embedding_provider.get_dimensions()

            # 3. Create schema manager and apply schema
            self.schema_manager = PostgresSchemaManager(
                self.connection_manager,
                dimensions,
                config=self.config,
            )
            await self.schema_manager.create_schema()

            # 4. Validate dimension consistency (fail fast)
            await self.schema_manager.validate_dimensions()

            self._initialized = True
            logger.info(
                "PostgresBackend initialized (dimensions=%d)",
                dimensions,
            )
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Failed to initialize PostgresBackend: {e}",
                backend="postgres",
            ) from e

    async def upsert_documents(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        """Upsert documents with embeddings and tsvector.

        For each document, inserts text + metadata + tsvector via
        KeywordOps, then updates the embedding column via VectorOps.

        Args:
            ids: Unique chunk identifiers.
            embeddings: Embedding vectors.
            documents: Text content of chunks.
            metadatas: JSON-compatible metadata dicts.

        Returns:
            Number of documents upserted.

        Raises:
            ValueError: If input list lengths don't match.
            StorageError: If upsert operation fails.
        """
        lengths = {len(ids), len(embeddings), len(documents), len(metadatas)}
        if len(lengths) > 1:
            raise ValueError(
                f"Input list lengths must match: "
                f"ids={len(ids)}, embeddings={len(embeddings)}, "
                f"documents={len(documents)}, "
                f"metadatas={len(metadatas)}"
            )

        try:
            count = 0
            for i in range(len(ids)):
                # 1. Upsert text + metadata + tsvector
                await self.keyword_ops.upsert_with_tsvector(
                    chunk_id=ids[i],
                    document_text=documents[i],
                    metadata=metadatas[i],
                )
                # 2. Update embedding column
                await self.vector_ops.upsert_embeddings(
                    chunk_id=ids[i],
                    embedding=embeddings[i],
                )
                count += 1
            return count
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Failed to upsert documents: {e}",
                backend="postgres",
            ) from e

    async def vector_search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float,
        where: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Perform vector similarity search.

        Delegates to VectorOps with cosine distance metric.

        Args:
            query_embedding: Query embedding vector.
            top_k: Maximum number of results.
            similarity_threshold: Minimum similarity (0-1).
            where: Optional metadata filter (JSONB containment).

        Returns:
            List of SearchResult with 0-1 normalized scores.

        Raises:
            StorageError: If search fails.
        """
        return await self.vector_ops.vector_search(
            query_embedding=query_embedding,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            where=where,
        )

    async def keyword_search(
        self,
        query: str,
        top_k: int,
        source_types: list[str] | None = None,
        languages: list[str] | None = None,
    ) -> list[SearchResult]:
        """Perform full-text keyword search.

        Delegates to KeywordOps with tsvector.

        Args:
            query: Search query string.
            top_k: Maximum number of results.
            source_types: Optional source_type metadata filter.
            languages: Optional language metadata filter.

        Returns:
            List of SearchResult with 0-1 normalized scores.

        Raises:
            StorageError: If search fails.
        """
        return await self.keyword_ops.keyword_search(
            query=query,
            top_k=top_k,
            source_types=source_types,
            languages=languages,
        )

    async def hybrid_search_with_rrf(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
        rrf_k: int = 60,
    ) -> list[SearchResult]:
        """Hybrid search using Reciprocal Rank Fusion (RRF).

        Combines vector similarity and keyword search results using
        weighted RRF scoring. Each result's RRF score is computed as:
        ``weight / (rank + rrf_k)`` summed across both result lists.

        Args:
            query: Search query string for keyword search.
            query_embedding: Query embedding for vector search.
            top_k: Maximum number of final results.
            vector_weight: Weight for vector search RRF scores.
            keyword_weight: Weight for keyword search RRF scores.
            rrf_k: RRF constant (default 60, per literature).

        Returns:
            List of SearchResult sorted by RRF score descending,
            with scores normalized to 0-1.

        Raises:
            StorageError: If search fails.
        """
        try:
            # Fetch 2x results from both sources for better fusion
            fetch_k = 2 * top_k

            vector_results = await self.vector_ops.vector_search(
                query_embedding=query_embedding,
                top_k=fetch_k,
                similarity_threshold=0.0,
            )

            keyword_results = await self.keyword_ops.keyword_search(
                query=query,
                top_k=fetch_k,
            )

            # Build RRF scores
            rrf_scores: dict[str, float] = {}
            result_map: dict[str, SearchResult] = {}

            for rank, result in enumerate(vector_results):
                rrf_scores[result.chunk_id] = rrf_scores.get(
                    result.chunk_id, 0.0
                ) + vector_weight / (rank + rrf_k)
                result_map[result.chunk_id] = result

            for rank, result in enumerate(keyword_results):
                rrf_scores[result.chunk_id] = rrf_scores.get(
                    result.chunk_id, 0.0
                ) + keyword_weight / (rank + rrf_k)
                # Prefer vector result if already present
                if result.chunk_id not in result_map:
                    result_map[result.chunk_id] = result

            if not rrf_scores:
                return []

            # Sort by RRF score descending
            sorted_ids = sorted(
                rrf_scores.keys(),
                key=lambda cid: rrf_scores[cid],
                reverse=True,
            )[:top_k]

            # Normalize RRF scores to 0-1
            max_rrf = max(rrf_scores.values())
            if max_rrf <= 0:
                max_rrf = 1.0

            results: list[SearchResult] = []
            for chunk_id in sorted_ids:
                original = result_map[chunk_id]
                results.append(
                    SearchResult(
                        text=original.text,
                        metadata=original.metadata,
                        score=rrf_scores[chunk_id] / max_rrf,
                        chunk_id=chunk_id,
                    )
                )

            return results

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Hybrid search failed: {e}",
                backend="postgres",
            ) from e

    async def get_count(self, where: dict[str, Any] | None = None) -> int:
        """Get document count, optionally filtered.

        Args:
            where: Optional JSONB containment filter.

        Returns:
            Number of documents matching filter.

        Raises:
            StorageError: If count operation fails.
        """
        engine = self.connection_manager.engine
        try:
            params: dict[str, Any] = {}
            filter_clause = ""
            if where:
                filter_clause = "WHERE metadata @> CAST(:filter AS jsonb)"
                params["filter"] = json.dumps(where)

            sql = f"SELECT COUNT(*) FROM documents {filter_clause}"

            async with engine.connect() as conn:
                result = await conn.execute(text(sql), params)
                row = result.fetchone()
                return int(row[0]) if row else 0

        except Exception as e:
            raise StorageError(
                f"Get count failed: {e}",
                backend="postgres",
            ) from e

    async def get_by_id(self, chunk_id: str) -> dict[str, Any] | None:
        """Get document by chunk ID.

        Args:
            chunk_id: Unique chunk identifier.

        Returns:
            Dictionary with ``text`` and ``metadata`` keys,
            or None if not found.

        Raises:
            StorageError: If retrieval fails.
        """
        engine = self.connection_manager.engine
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        """
                        SELECT document_text, metadata
                        FROM documents
                        WHERE chunk_id = :chunk_id
                        """
                    ),
                    {"chunk_id": chunk_id},
                )
                row = result.fetchone()
                if row is None:
                    return None

                metadata_val = row[1]
                if isinstance(metadata_val, str):
                    metadata_val = json.loads(metadata_val)

                return {"text": row[0], "metadata": metadata_val}

        except Exception as e:
            raise StorageError(
                f"Get by ID failed: {e}",
                backend="postgres",
            ) from e

    async def reset(self) -> None:
        """Reset storage by dropping and recreating tables.

        Drops the documents and embedding_metadata tables, then
        recreates the full schema via the schema manager.

        Raises:
            StorageError: If reset fails.
        """
        engine = self.connection_manager.engine
        try:
            async with engine.begin() as conn:
                await conn.execute(text("DROP TABLE IF EXISTS documents;"))
                await conn.execute(text("DROP TABLE IF EXISTS embedding_metadata;"))

            if self.schema_manager is not None:
                await self.schema_manager.create_schema()

            logger.info("PostgresBackend reset complete")
        except Exception as e:
            raise StorageError(
                f"Reset failed: {e}",
                backend="postgres",
            ) from e

    async def get_embedding_metadata(
        self,
    ) -> EmbeddingMetadata | None:
        """Get stored embedding metadata.

        Returns:
            EmbeddingMetadata if stored, None otherwise.

        Raises:
            StorageError: If retrieval fails.
        """
        if self.schema_manager is None:
            return None

        try:
            meta_dict = await self.schema_manager.get_embedding_metadata()
            if meta_dict is None:
                return None

            return EmbeddingMetadata(
                provider=meta_dict.get("provider", "unknown"),
                model=meta_dict.get("model", "unknown"),
                dimensions=meta_dict.get("dimensions", 0),
            )
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Get embedding metadata failed: {e}",
                backend="postgres",
            ) from e

    async def set_embedding_metadata(
        self,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Store embedding metadata.

        Args:
            provider: Embedding provider name.
            model: Model name.
            dimensions: Embedding vector dimensions.

        Raises:
            StorageError: If storage fails.
        """
        if self.schema_manager is None:
            raise StorageError(
                "Cannot store embedding metadata: backend not " "initialized",
                backend="postgres",
            )

        try:
            await self.schema_manager.store_embedding_metadata(
                provider=provider,
                model=model,
                dimensions=dimensions,
            )
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                f"Set embedding metadata failed: {e}",
                backend="postgres",
            ) from e

    async def delete_by_metadata(
        self,
        where: dict[str, Any],
    ) -> int:
        """Delete documents matching a metadata JSONB filter.

        Executes a ``DELETE ... RETURNING`` statement with a JSONB
        containment filter so that the count of deleted rows is returned
        without a separate ``SELECT COUNT`` round-trip.

        Args:
            where: Metadata filter dict.  Applied as a JSONB containment
                query: ``metadata @> :filter_json::jsonb``.

        Returns:
            Number of documents deleted.

        Raises:
            StorageError: If the delete operation fails.
        """
        engine = self.connection_manager.engine
        try:
            sql = text(
                """
                DELETE FROM documents
                WHERE metadata @> CAST(:filter_json AS jsonb)
                RETURNING chunk_id
                """
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    sql,
                    {"filter_json": json.dumps(where)},
                )
                rows = result.fetchall()
            deleted_count = len(rows)
            logger.debug(
                "Deleted %d documents matching metadata filter %r",
                deleted_count,
                where,
            )
            return deleted_count
        except Exception as e:
            raise StorageError(
                f"Delete by metadata failed: {e}",
                backend="postgres",
            ) from e

    def validate_embedding_compatibility(
        self,
        provider: str,
        model: str,
        dimensions: int,
        stored_metadata: EmbeddingMetadata | None,
    ) -> None:
        """Validate embedding compatibility (synchronous).

        Checks if the current embedding dimensions match what was
        previously stored. A mismatch indicates incompatible indexes.

        Args:
            provider: Current provider name.
            model: Current model name.
            dimensions: Current embedding dimensions.
            stored_metadata: Previously stored metadata.

        Raises:
            ProviderMismatchError: If dimensions or provider don't match.
        """
        if stored_metadata is None:
            return  # No stored metadata, nothing to validate

        if stored_metadata.dimensions != dimensions:
            raise ProviderMismatchError(
                current_provider=provider,
                current_model=model,
                indexed_provider=stored_metadata.provider,
                indexed_model=stored_metadata.model,
            )

    async def close(self) -> None:
        """Close the connection pool and release resources.

        Idempotent -- safe to call multiple times.
        """
        await self.connection_manager.close()
        self._initialized = False
        logger.info("PostgresBackend closed")
