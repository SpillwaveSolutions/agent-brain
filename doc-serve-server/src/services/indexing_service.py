"""Indexing service that orchestrates the document indexing pipeline."""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Callable, Awaitable

from ..models import IndexRequest, IndexingState, IndexingStatusEnum
from ..indexing import DocumentLoader, ContextAwareChunker, EmbeddingGenerator
from ..storage import VectorStoreManager, get_vector_store

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
        vector_store: Optional[VectorStoreManager] = None,
        document_loader: Optional[DocumentLoader] = None,
        chunker: Optional[ContextAwareChunker] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
    ):
        """
        Initialize the indexing service.

        Args:
            vector_store: Vector store manager instance.
            document_loader: Document loader instance.
            chunker: Text chunker instance.
            embedding_generator: Embedding generator instance.
        """
        self.vector_store = vector_store or get_vector_store()
        self.document_loader = document_loader or DocumentLoader()
        self.chunker = chunker or ContextAwareChunker()
        self.embedding_generator = embedding_generator or EmbeddingGenerator()

        # Internal state
        self._state = IndexingState()
        self._lock = asyncio.Lock()
        self._indexed_folders: list[str] = []

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
            self.vector_store.is_initialized
            and not self.is_indexing
            and self._state.status != IndexingStatusEnum.FAILED
        )

    async def start_indexing(
        self,
        request: IndexRequest,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """
        Start a new indexing job.

        Args:
            request: IndexRequest with folder path and configuration.
            progress_callback: Optional callback for progress updates.

        Returns:
            Job ID for tracking the indexing operation.

        Raises:
            RuntimeError: If indexing is already in progress.
        """
        async with self._lock:
            if self._state.is_indexing:
                raise RuntimeError("Indexing already in progress")

            # Generate job ID and initialize state
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            self._state = IndexingState(
                current_job_id=job_id,
                status=IndexingStatusEnum.INDEXING,
                is_indexing=True,
                folder_path=request.folder_path,
                started_at=datetime.utcnow(),
            )

        logger.info(f"Starting indexing job {job_id} for {request.folder_path}")

        # Run indexing in background
        asyncio.create_task(
            self._run_indexing_pipeline(request, job_id, progress_callback)
        )

        return job_id

    async def _run_indexing_pipeline(
        self,
        request: IndexRequest,
        job_id: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        """
        Execute the full indexing pipeline.

        Args:
            request: Indexing request configuration.
            job_id: Job identifier for tracking.
            progress_callback: Optional progress callback.
        """
        try:
            # Ensure vector store is initialized
            await self.vector_store.initialize()

            # Step 1: Load documents
            if progress_callback:
                await progress_callback(0, 100, "Loading documents...")

            documents = await self.document_loader.load_from_folder(
                request.folder_path,
                recursive=request.recursive,
            )

            self._state.total_documents = len(documents)
            logger.info(f"Loaded {len(documents)} documents")

            if not documents:
                logger.warning(f"No documents found in {request.folder_path}")
                self._state.status = IndexingStatusEnum.COMPLETED
                self._state.is_indexing = False
                self._state.completed_at = datetime.utcnow()
                return

            # Step 2: Chunk documents
            if progress_callback:
                await progress_callback(20, 100, "Chunking documents...")

            # Create chunker with request configuration
            chunker = ContextAwareChunker(
                chunk_size=request.chunk_size,
                chunk_overlap=request.chunk_overlap,
            )

            async def chunk_progress(processed: int, total: int) -> None:
                self._state.processed_documents = processed
                if progress_callback:
                    pct = 20 + int((processed / total) * 30)
                    await progress_callback(pct, 100, f"Chunking: {processed}/{total}")

            chunks = await chunker.chunk_documents(documents, chunk_progress)
            self._state.total_chunks = len(chunks)
            logger.info(f"Created {len(chunks)} chunks")

            # Step 3: Generate embeddings
            if progress_callback:
                await progress_callback(50, 100, "Generating embeddings...")

            async def embedding_progress(processed: int, total: int) -> None:
                if progress_callback:
                    pct = 50 + int((processed / total) * 40)
                    await progress_callback(pct, 100, f"Embedding: {processed}/{total}")

            embeddings = await self.embedding_generator.embed_chunks(
                chunks,
                embedding_progress,
            )
            logger.info(f"Generated {len(embeddings)} embeddings")

            # Step 4: Store in vector database
            if progress_callback:
                await progress_callback(90, 100, "Storing in vector database...")

            await self.vector_store.add_documents(
                ids=[chunk.chunk_id for chunk in chunks],
                embeddings=embeddings,
                documents=[chunk.text for chunk in chunks],
                metadatas=[chunk.metadata for chunk in chunks],
            )

            # Mark as completed
            self._state.status = IndexingStatusEnum.COMPLETED
            self._state.completed_at = datetime.utcnow()
            self._indexed_folders.append(request.folder_path)

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
            raise

        finally:
            self._state.is_indexing = False

    async def get_status(self) -> dict:
        """
        Get current indexing status.

        Returns:
            Dictionary with status information.
        """
        count = await self.vector_store.get_count() if self.vector_store.is_initialized else 0

        return {
            "status": self._state.status.value,
            "is_indexing": self._state.is_indexing,
            "current_job_id": self._state.current_job_id,
            "folder_path": self._state.folder_path,
            "total_documents": self._state.total_documents,
            "processed_documents": self._state.processed_documents,
            "total_chunks": count,
            "progress_percent": self._state.progress_percent,
            "started_at": self._state.started_at.isoformat() if self._state.started_at else None,
            "completed_at": self._state.completed_at.isoformat() if self._state.completed_at else None,
            "error": self._state.error,
            "indexed_folders": self._indexed_folders.copy(),
        }

    async def reset(self) -> None:
        """Reset the indexing service and vector store."""
        async with self._lock:
            await self.vector_store.reset()
            self._state = IndexingState()
            self._indexed_folders.clear()
            logger.info("Indexing service reset")


# Singleton instance
_indexing_service: Optional[IndexingService] = None


def get_indexing_service() -> IndexingService:
    """Get the global indexing service instance."""
    global _indexing_service
    if _indexing_service is None:
        _indexing_service = IndexingService()
    return _indexing_service
