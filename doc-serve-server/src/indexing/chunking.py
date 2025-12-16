"""Context-aware text chunking with configurable overlap."""

import logging
import uuid
from typing import List, Optional
from dataclasses import dataclass, field

import tiktoken
from llama_index.core.node_parser import SentenceSplitter

from .document_loader import LoadedDocument
from ..config import settings

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""

    chunk_id: str
    text: str
    source: str
    chunk_index: int
    total_chunks: int
    token_count: int
    metadata: dict = field(default_factory=dict)


class ContextAwareChunker:
    """
    Splits documents into chunks with context-aware boundaries.

    Uses a recursive splitting strategy:
    1. Split by paragraphs (\\n\\n)
    2. If too large, split by sentences
    3. If still too large, split by words

    Maintains overlap between consecutive chunks to preserve context.
    """

    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        tokenizer_name: str = "cl100k_base",
    ):
        """
        Initialize the chunker.

        Args:
            chunk_size: Target chunk size in tokens. Defaults to config value.
            chunk_overlap: Token overlap between chunks. Defaults to config value.
            tokenizer_name: Tiktoken encoding name for token counting.
        """
        self.chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP

        # Initialize tokenizer for accurate token counting
        self.tokenizer = tiktoken.get_encoding(tokenizer_name)

        # Initialize LlamaIndex sentence splitter
        self.splitter = SentenceSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            paragraph_separator="\n\n",
            secondary_chunking_regex="[.!?]\\s+",  # Sentence boundaries
        )

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        return len(self.tokenizer.encode(text))

    async def chunk_documents(
        self,
        documents: List[LoadedDocument],
        progress_callback: Optional[callable] = None,
    ) -> List[TextChunk]:
        """
        Chunk multiple documents into smaller pieces.

        Args:
            documents: List of LoadedDocument objects.
            progress_callback: Optional callback(processed, total) for progress.

        Returns:
            List of TextChunk objects with metadata.
        """
        all_chunks: List[TextChunk] = []

        for idx, doc in enumerate(documents):
            doc_chunks = await self.chunk_single_document(doc)
            all_chunks.extend(doc_chunks)

            if progress_callback:
                await progress_callback(idx + 1, len(documents))

        logger.info(
            f"Chunked {len(documents)} documents into {len(all_chunks)} chunks "
            f"(avg {len(all_chunks) / max(len(documents), 1):.1f} chunks/doc)"
        )
        return all_chunks

    async def chunk_single_document(
        self,
        document: LoadedDocument,
    ) -> List[TextChunk]:
        """
        Chunk a single document.

        Args:
            document: The document to chunk.

        Returns:
            List of TextChunk objects.
        """
        if not document.text.strip():
            logger.warning(f"Empty document: {document.source}")
            return []

        # Use LlamaIndex splitter to get text chunks
        text_chunks = self.splitter.split_text(document.text)

        # Convert to our TextChunk format with metadata
        chunks: List[TextChunk] = []
        total_chunks = len(text_chunks)

        for idx, chunk_text in enumerate(text_chunks):
            chunk = TextChunk(
                chunk_id=f"chunk_{uuid.uuid4().hex[:12]}",
                text=chunk_text,
                source=document.source,
                chunk_index=idx,
                total_chunks=total_chunks,
                token_count=self.count_tokens(chunk_text),
                metadata={
                    "file_name": document.file_name,
                    "file_path": document.file_path,
                    "chunk_index": idx,
                    "total_chunks": total_chunks,
                    **document.metadata,
                },
            )
            chunks.append(chunk)

        return chunks

    async def rechunk_with_config(
        self,
        documents: List[LoadedDocument],
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[TextChunk]:
        """
        Rechunk documents with different configuration.

        Args:
            documents: List of documents to chunk.
            chunk_size: New chunk size in tokens.
            chunk_overlap: New overlap in tokens.

        Returns:
            List of TextChunk objects.
        """
        # Create a new chunker with the specified config
        chunker = ContextAwareChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        return await chunker.chunk_documents(documents)

    def get_chunk_stats(self, chunks: List[TextChunk]) -> dict:
        """
        Get statistics about a list of chunks.

        Args:
            chunks: List of TextChunk objects.

        Returns:
            Dictionary with chunk statistics.
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "avg_tokens": 0,
                "min_tokens": 0,
                "max_tokens": 0,
                "total_tokens": 0,
            }

        token_counts = [c.token_count for c in chunks]

        return {
            "total_chunks": len(chunks),
            "avg_tokens": sum(token_counts) / len(token_counts),
            "min_tokens": min(token_counts),
            "max_tokens": max(token_counts),
            "total_tokens": sum(token_counts),
            "unique_sources": len(set(c.source for c in chunks)),
        }
