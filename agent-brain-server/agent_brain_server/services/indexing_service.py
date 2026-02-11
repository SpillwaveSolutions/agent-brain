"""Indexing service that orchestrates the document indexing pipeline."""

import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from llama_index.core.schema import TextNode

from agent_brain_server.config import settings
from agent_brain_server.config.provider_config import load_provider_settings
from agent_brain_server.indexing import (
    BM25IndexManager,
    ContextAwareChunker,
    DocumentLoader,
    EmbeddingGenerator,
    get_bm25_manager,
)
from agent_brain_server.indexing.chunking import CodeChunk, CodeChunker, TextChunk
from agent_brain_server.indexing.graph_index import (
    GraphIndexManager,
    get_graph_index_manager,
)
from agent_brain_server.models import IndexingState, IndexingStatusEnum, IndexRequest
from agent_brain_server.storage import (
    StorageBackendProtocol,
    VectorStoreManager,
    get_storage_backend,
    get_vector_store,
)

logger = logging.getLogger(__name__)


# Type alias for progress callback
ProgressCallback = Callable[[int, int, str], Awaitable[None]]


class IndexingService:
    """
    Orchestrates the document indexing pipeline.

    Coordinates document loading, chunking, embedding generation,
    and vector store storage with progress tracking.
    """

    def __init__(
        self,
        vector_store: VectorStoreManager | None = None,
        document_loader: DocumentLoader | None = None,
        chunker: ContextAwareChunker | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
        bm25_manager: BM25IndexManager | None = None,
        graph_index_manager: GraphIndexManager | None = None,
        storage_backend: StorageBackendProtocol | None = None,
    ):
        """
        Initialize the indexing service.

        Args:
            vector_store: [DEPRECATED] Vector store manager
                (for backward compat).
            document_loader: Document loader instance.
            chunker: Text chunker instance.
            embedding_generator: Embedding generator instance.
            bm25_manager: [DEPRECATED] BM25 index manager
                (for backward compat).
            graph_index_manager: Graph index manager instance (Feature 113).
            storage_backend: Storage backend implementing protocol (preferred).
        """
        # Resolve storage_backend with backward compatibility
        if storage_backend is not None:
            self.storage_backend = storage_backend
        elif vector_store is not None or bm25_manager is not None:
            # Legacy path: wrap provided stores in ChromaBackend
            from agent_brain_server.storage.chroma.backend import ChromaBackend

            self.storage_backend = ChromaBackend(
                vector_store=vector_store,
                bm25_manager=bm25_manager,
            )
        else:
            # New path: use factory
            self.storage_backend = get_storage_backend()

        # Maintain backward-compatible aliases
        if hasattr(self.storage_backend, "vector_store"):
            self.vector_store = self.storage_backend.vector_store
        else:
            self.vector_store = vector_store or get_vector_store()

        if hasattr(self.storage_backend, "bm25_manager"):
            self.bm25_manager = self.storage_backend.bm25_manager
        else:
            self.bm25_manager = bm25_manager or get_bm25_manager()

        self.document_loader = document_loader or DocumentLoader()
        self.chunker = chunker or ContextAwareChunker()
        self.embedding_generator = embedding_generator or EmbeddingGenerator()
        self.graph_index_manager = graph_index_manager or get_graph_index_manager()

        # Internal state
        self._state = IndexingState(
            current_job_id="",
            folder_path="",
            started_at=None,
            completed_at=None,
            error=None,
        )
        self._lock = asyncio.Lock()
        self._indexed_folders: set[str] = set()
        self._total_doc_chunks = 0
        self._total_code_chunks = 0
        self._supported_languages: set[str] = set()

    @property
    def state(self) -> IndexingState:
        """Get the current indexing state."""
        return self._state

    @property
    def is_indexing(self) -> bool:
        """Check if indexing is currently in progress."""
        return self._state.is_indexing

    @property
    def is_ready(self) -> bool:
        """Check if the system is ready for queries."""
        return (
            self.storage_backend.is_initialized
            and not self.is_indexing
            and self._state.status != IndexingStatusEnum.FAILED
        )

    async def start_indexing(
        self,
        request: IndexRequest,
        progress_callback: ProgressCallback | None = None,
        force: bool = False,
    ) -> str:
        """
        Start a new indexing job.

        Args:
            request: IndexRequest with folder path and configuration.
            progress_callback: Optional callback for progress updates.
            force: If True, bypass embedding compatibility validation.

        Returns:
            Job ID for tracking the indexing operation.

        Raises:
            RuntimeError: If indexing is already in progress.
        """
        async with self._lock:
            if self._state.is_indexing:
                raise RuntimeError("Indexing already in progress")

            # Validate embedding compatibility unless force=True
            if not force:
                await self._validate_embedding_compatibility()

            # Generate job ID and initialize state
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            self._state = IndexingState(
                current_job_id=job_id,
                status=IndexingStatusEnum.INDEXING,
                is_indexing=True,
                folder_path=request.folder_path,
                started_at=datetime.now(timezone.utc),
                completed_at=None,
                error=None,
            )

        logger.info(f"Starting indexing job {job_id} for {request.folder_path}")

        # Run indexing in background
        asyncio.create_task(
            self._run_indexing_pipeline(request, job_id, progress_callback)
        )

        return job_id

    async def _validate_embedding_compatibility(self) -> None:
        """Validate current embedding config matches existing index.

        Raises:
            ProviderMismatchError: If provider/model/dimensions don't match
        """
        # Get stored metadata
        stored_metadata = await self.storage_backend.get_embedding_metadata()

        if stored_metadata is None:
            # No existing index, no validation needed
            return

        # Get current config
        provider_settings = load_provider_settings()
        current_provider = provider_settings.embedding.provider
        current_model = provider_settings.embedding.model
        current_dimensions = self.embedding_generator.get_embedding_dimensions()

        # Validate
        self.storage_backend.validate_embedding_compatibility(
            provider=str(current_provider),
            model=current_model,
            dimensions=current_dimensions,
            stored_metadata=stored_metadata,
        )

    async def _run_indexing_pipeline(
        self,
        request: IndexRequest,
        job_id: str,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """
        Execute the full indexing pipeline.

        Args:
            request: Indexing request configuration.
            job_id: Job identifier for tracking.
            progress_callback: Optional progress callback.
        """
        try:
            # Ensure storage backend is initialized
            await self.storage_backend.initialize()

            # Get current embedding config for metadata storage
            provider_settings = load_provider_settings()
            current_provider = str(provider_settings.embedding.provider)
            current_model = provider_settings.embedding.model
            current_dimensions = self.embedding_generator.get_embedding_dimensions()

            # Validate embedding compatibility unless force=True
            if not request.force:
                stored_metadata = await self.storage_backend.get_embedding_metadata()
                if stored_metadata is not None:
                    self.storage_backend.validate_embedding_compatibility(
                        provider=current_provider,
                        model=current_model,
                        dimensions=current_dimensions,
                        stored_metadata=stored_metadata,
                    )

            # Step 1: Load documents
            if progress_callback:
                await progress_callback(0, 100, "Loading documents...")

            # Normalize folder path to absolute path to avoid duplicates
            abs_folder_path = os.path.abspath(request.folder_path)
            logger.info(
                f"Normalizing indexing path: {request.folder_path} -> {abs_folder_path}"
            )

            documents = await self.document_loader.load_files(
                abs_folder_path,
                recursive=request.recursive,
                include_code=request.include_code,
            )

            self._state.total_documents = len(documents)
            logger.info(f"Loaded {len(documents)} documents")

            if not documents:
                logger.warning(f"No documents found in {request.folder_path}")
                self._state.status = IndexingStatusEnum.COMPLETED
                self._state.is_indexing = False
                self._state.completed_at = datetime.now(timezone.utc)
                return

            # Step 2: Chunk documents and code files
            if progress_callback:
                await progress_callback(20, 100, "Chunking documents...")

            # Separate documents by type
            doc_documents = [
                d for d in documents if d.metadata.get("source_type") == "doc"
            ]
            code_documents = [
                d for d in documents if d.metadata.get("source_type") == "code"
            ]

            logger.info(
                f"Processing {len(doc_documents)} documents and "
                f"{len(code_documents)} code files"
            )

            all_chunks: list[TextChunk | CodeChunk] = []
            total_to_process = len(documents)

            # Chunk documents
            doc_chunker = None
            if doc_documents:
                doc_chunker = ContextAwareChunker(
                    chunk_size=request.chunk_size,
                    chunk_overlap=request.chunk_overlap,
                )

                async def doc_chunk_progress(processed: int, total: int) -> None:
                    self._state.processed_documents = processed
                    if progress_callback:
                        pct = 20 + int((processed / total_to_process) * 15)
                        await progress_callback(
                            pct, 100, f"Chunking docs: {processed}/{total}"
                        )

                doc_chunks = await doc_chunker.chunk_documents(
                    doc_documents, doc_chunk_progress
                )
                all_chunks.extend(doc_chunks)
                self._total_doc_chunks += len(doc_chunks)
                logger.info(f"Created {len(doc_chunks)} document chunks")

            # Chunk code files
            if code_documents:
                # Group code documents by language for efficient chunking
                code_by_language: dict[str, list[Any]] = {}
                for doc in code_documents:
                    lang = doc.metadata.get("language", "unknown")
                    if lang not in code_by_language:
                        code_by_language[lang] = []
                    code_by_language[lang].append(doc)

                # Track total code documents processed across all languages
                total_code_processed = 0

                for lang, lang_docs in code_by_language.items():
                    if lang == "unknown":
                        logger.warning(
                            f"Skipping {len(lang_docs)} code files with unknown "
                            "language"
                        )
                        continue

                    try:
                        code_chunker = CodeChunker(
                            language=lang, generate_summaries=request.generate_summaries
                        )

                        # Create progress callback with fixed offset for this language
                        def make_progress_callback(
                            offset: int,
                        ) -> Callable[[int, int], Awaitable[None]]:
                            async def progress_callback_fn(
                                processed: int,
                                total: int,
                            ) -> None:
                                # processed is relative to current language batch
                                # Convert to total documents processed across
                                # all languages
                                total_processed = offset + processed
                                self._state.processed_documents = total_processed
                                if progress_callback:
                                    pct = 35 + int(
                                        (total_processed / total_to_process) * 15
                                    )
                                    await progress_callback(
                                        pct,
                                        100,
                                        f"Chunking code: {total_processed}/"
                                        f"{total_to_process}",
                                    )

                            return progress_callback_fn

                        # Calculate offset and create callback for this language batch
                        # Progress callback created but not used in
                        # current implementation
                        # progress_offset = len(doc_documents) + total_code_processed
                        # code_chunk_progress = make_progress_callback(progress_offset)

                        for doc in lang_docs:
                            code_chunks = await code_chunker.chunk_code_document(doc)
                            all_chunks.extend(code_chunks)
                            self._total_code_chunks += len(code_chunks)
                            self._supported_languages.add(lang)

                        # Update the total code documents processed
                        total_code_processed += len(lang_docs)

                        chunk_count = sum(
                            1 for c in all_chunks if c.metadata.language == lang
                        )
                        logger.info(f"Created {chunk_count} {lang} chunks")

                    except Exception as e:
                        logger.error(f"Failed to chunk {lang} files: {e}")
                        # Fallback: treat as documents
                        if doc_chunker is not None:  # Reuse doc chunker if available
                            fallback_chunks = await doc_chunker.chunk_documents(
                                lang_docs
                            )
                            all_chunks.extend(fallback_chunks)
                            logger.info(
                                f"Fell back to document chunking for "
                                f"{len(fallback_chunks)} {lang} files"
                            )
                        else:
                            # Create a temporary chunker for fallback
                            fallback_chunker = ContextAwareChunker(
                                chunk_size=request.chunk_size,
                                chunk_overlap=request.chunk_overlap,
                            )
                            fallback_chunks = await fallback_chunker.chunk_documents(
                                lang_docs
                            )
                            all_chunks.extend(fallback_chunks)
                            logger.info(
                                f"Fell back to document chunking for "
                                f"{len(fallback_chunks)} {lang} files"
                            )

            chunks = all_chunks
            self._state.total_chunks = len(chunks)
            logger.info(f"Created {len(chunks)} total chunks")

            # Step 3: Generate embeddings
            if progress_callback:
                await progress_callback(50, 100, "Generating embeddings...")

            async def embedding_progress(processed: int, total: int) -> None:
                if progress_callback:
                    pct = 50 + int((processed / total) * 40)
                    await progress_callback(pct, 100, f"Embedding: {processed}/{total}")

            # The chunks list contains both TextChunk and CodeChunk,
            # but both are TextChunk subclasses
            embeddings = await self.embedding_generator.embed_chunks(
                chunks,  # type: ignore
                embedding_progress,
            )
            logger.info(f"Generated {len(embeddings)} embeddings")

            # Step 4: Store in vector database
            if progress_callback:
                await progress_callback(90, 100, "Storing in vector database...")

            # ChromaDB has a max batch size of 41666, so we need to batch our upserts
            # Use a safe batch size of 40000 to leave some margin
            chroma_batch_size = 40000

            for batch_start in range(0, len(chunks), chroma_batch_size):
                batch_end = min(batch_start + chroma_batch_size, len(chunks))
                batch_chunks = chunks[batch_start:batch_end]
                batch_embeddings = embeddings[batch_start:batch_end]

                await self.storage_backend.upsert_documents(
                    ids=[chunk.chunk_id for chunk in batch_chunks],
                    embeddings=batch_embeddings,
                    documents=[chunk.text for chunk in batch_chunks],
                    metadatas=[chunk.metadata.to_dict() for chunk in batch_chunks],
                )

                logger.info(
                    f"Stored batch {batch_start // chroma_batch_size + 1} "
                    f"({len(batch_chunks)} chunks) in vector database"
                )

            # Store embedding metadata for future validation
            await self.storage_backend.set_embedding_metadata(
                provider=current_provider,
                model=current_model,
                dimensions=current_dimensions,
            )

            # Step 5: Build BM25 index
            if progress_callback:
                await progress_callback(95, 100, "Building BM25 index...")

            nodes = [
                TextNode(
                    text=chunk.text,
                    id_=chunk.chunk_id,
                    metadata=chunk.metadata.to_dict(),
                )
                for chunk in chunks
            ]
            self.bm25_manager.build_index(nodes)

            # Step 6: Build graph index if enabled (Feature 113)
            if settings.ENABLE_GRAPH_INDEX:
                if progress_callback:
                    await progress_callback(97, 100, "Building graph index...")

                def graph_progress(current: int, total: int, message: str) -> None:
                    # Synchronous callback wrapper
                    logger.debug(f"Graph indexing: {message}")

                triplet_count = self.graph_index_manager.build_from_documents(
                    chunks,
                    progress_callback=graph_progress,
                )
                logger.info(f"Graph index built with {triplet_count} triplets")

            # Mark as completed
            self._state.status = IndexingStatusEnum.COMPLETED
            self._state.completed_at = datetime.now(timezone.utc)
            self._state.is_indexing = False
            self._indexed_folders.add(abs_folder_path)

            if progress_callback:
                await progress_callback(100, 100, "Indexing complete!")

            logger.info(
                f"Indexing job {job_id} completed: "
                f"{len(documents)} docs, {len(chunks)} chunks"
            )

        except Exception as e:
            logger.error(f"Indexing job {job_id} failed: {e}")
            self._state.status = IndexingStatusEnum.FAILED
            self._state.error = str(e)
            self._state.is_indexing = False
            raise

        finally:
            self._state.is_indexing = False

    async def get_status(self) -> dict[str, Any]:
        """
        Get current indexing status.

        Returns:
            Dictionary with status information.
        """
        total_chunks = (
            await self.storage_backend.get_count()
            if self.storage_backend.is_initialized
            else 0
        )

        # Use the instance variables we've been tracking during indexing
        total_doc_chunks = self._total_doc_chunks
        total_code_chunks = self._total_code_chunks
        supported_languages = sorted(self._supported_languages)

        # Get graph index status (Feature 113)
        graph_status = self.graph_index_manager.get_status()

        return {
            "status": self._state.status.value,
            "is_indexing": self._state.is_indexing,
            "current_job_id": self._state.current_job_id,
            "folder_path": self._state.folder_path,
            "total_documents": self._state.total_documents,
            "processed_documents": self._state.processed_documents,
            "total_chunks": total_chunks,
            "total_doc_chunks": total_doc_chunks,
            "total_code_chunks": total_code_chunks,
            "supported_languages": supported_languages,
            "progress_percent": self._state.progress_percent,
            "started_at": (
                self._state.started_at.isoformat() if self._state.started_at else None
            ),
            "completed_at": (
                self._state.completed_at.isoformat()
                if self._state.completed_at
                else None
            ),
            "error": self._state.error,
            "indexed_folders": sorted(self._indexed_folders),
            # Graph index status (Feature 113)
            "graph_index": {
                "enabled": graph_status.enabled,
                "initialized": graph_status.initialized,
                "entity_count": graph_status.entity_count,
                "relationship_count": graph_status.relationship_count,
                "store_type": graph_status.store_type,
            },
        }

    async def reset(self) -> None:
        """Reset the indexing service and vector store.

        Note: Embedding metadata is stored in collection metadata,
        so it will be cleared when collection is reset.
        """
        async with self._lock:
            await self.vector_store.reset()
            self.bm25_manager.reset()
            # Clear graph index (Feature 113)
            self.graph_index_manager.clear()
            self._state = IndexingState(
                current_job_id="",
                folder_path="",
                started_at=None,
                completed_at=None,
                error=None,
            )
            self._indexed_folders.clear()
            self._total_doc_chunks = 0
            self._total_code_chunks = 0
            self._supported_languages.clear()
            logger.info("Indexing service reset")


# Singleton instance
_indexing_service: IndexingService | None = None


def get_indexing_service() -> IndexingService:
    """Get the global indexing service instance."""
    global _indexing_service
    if _indexing_service is None:
        _indexing_service = IndexingService()
    return _indexing_service
