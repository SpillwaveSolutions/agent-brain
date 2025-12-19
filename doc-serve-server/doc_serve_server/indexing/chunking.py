"""Context-aware text chunking with configurable overlap."""

import hashlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import tiktoken
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter

from doc_serve_server.config import settings

from .document_loader import LoadedDocument

logger = logging.getLogger(__name__)


@dataclass
class ChunkMetadata:
    """Structured metadata for document and code chunks with unified schema."""

    # Universal metadata (all chunk types)
    chunk_id: str
    source: str
    file_name: str
    chunk_index: int
    total_chunks: int
    source_type: str  # "doc", "code", or "test"
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Document-specific metadata
    language: Optional[str] = None  # For docs/code: language type
    heading_path: Optional[str] = None  # Document heading hierarchy
    section_title: Optional[str] = None  # Current section title
    content_type: Optional[str] = None  # "tutorial", "api_ref", "guide", etc.

    # Code-specific metadata (AST-aware fields)
    symbol_name: Optional[str] = None  # Full symbol path
    symbol_kind: Optional[str] = None  # "function", "class", "method", etc.
    start_line: Optional[int] = None  # 1-based line number
    end_line: Optional[int] = None  # 1-based line number
    section_summary: Optional[str] = None  # AI-generated summary
    prev_section_summary: Optional[str] = None  # Previous section summary
    docstring: Optional[str] = None  # Extracted docstring
    parameters: Optional[list[str]] = None  # Function parameters as strings
    return_type: Optional[str] = None  # Function return type
    decorators: Optional[list[str]] = None  # Python decorators or similar
    imports: Optional[list[str]] = None  # Import statements in this chunk

    # Additional flexible metadata
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert ChunkMetadata to a dictionary for storage."""
        data = {
            "chunk_id": self.chunk_id,
            "source": self.source,
            "file_name": self.file_name,
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "source_type": self.source_type,
            "created_at": self.created_at.isoformat(),
        }

        # Add optional fields if they exist
        if self.language:
            data["language"] = self.language
        if self.heading_path:
            data["heading_path"] = self.heading_path
        if self.section_title:
            data["section_title"] = self.section_title
        if self.content_type:
            data["content_type"] = self.content_type
        if self.symbol_name:
            data["symbol_name"] = self.symbol_name
        if self.symbol_kind:
            data["symbol_kind"] = self.symbol_kind
        if self.start_line is not None:
            data["start_line"] = self.start_line
        if self.end_line is not None:
            data["end_line"] = self.end_line
        if self.section_summary:
            data["section_summary"] = self.section_summary
        if self.prev_section_summary:
            data["prev_section_summary"] = self.prev_section_summary
        if self.docstring:
            data["docstring"] = self.docstring
        if self.parameters:
            data["parameters"] = self.parameters
        if self.return_type:
            data["return_type"] = self.return_type
        if self.decorators:
            data["decorators"] = self.decorators
        if self.imports:
            data["imports"] = self.imports

        # Add extra metadata
        data.update(self.extra)

        return data


@dataclass
class TextChunk:
    """Represents a chunk of text with structured metadata."""

    chunk_id: str
    text: str
    source: str
    chunk_index: int
    total_chunks: int
    token_count: int
    metadata: ChunkMetadata


@dataclass
class CodeChunk:
    """Represents a chunk of source code with AST-aware boundaries."""

    chunk_id: str
    text: str
    source: str
    chunk_index: int
    total_chunks: int
    token_count: int
    metadata: ChunkMetadata

    @classmethod
    def create(
        cls,
        chunk_id: str,
        text: str,
        source: str,
        language: str,
        chunk_index: int,
        total_chunks: int,
        token_count: int,
        symbol_name: Optional[str] = None,
        symbol_kind: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        section_summary: Optional[str] = None,
        prev_section_summary: Optional[str] = None,
        docstring: Optional[str] = None,
        parameters: Optional[list[str]] = None,
        return_type: Optional[str] = None,
        decorators: Optional[list[str]] = None,
        imports: Optional[list[str]] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> "CodeChunk":
        """Create a CodeChunk with properly structured metadata."""
        file_name = source.split("/")[-1] if "/" in source else source

        metadata = ChunkMetadata(
            chunk_id=chunk_id,
            source=source,
            file_name=file_name,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            source_type="code",
            language=language,
            symbol_name=symbol_name,
            symbol_kind=symbol_kind,
            start_line=start_line,
            end_line=end_line,
            section_summary=section_summary,
            prev_section_summary=prev_section_summary,
            docstring=docstring,
            parameters=parameters,
            return_type=return_type,
            decorators=decorators,
            imports=imports,
            extra=extra or {},
        )

        return cls(
            chunk_id=chunk_id,
            text=text,
            source=source,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            token_count=token_count,
            metadata=metadata,
        )


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
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
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
        documents: list[LoadedDocument],
        progress_callback: Optional[Callable[[int, int], Awaitable[None]]] = None,
    ) -> list[TextChunk]:
        """
        Chunk multiple documents into smaller pieces.

        Args:
            documents: List of LoadedDocument objects.
            progress_callback: Optional callback(processed, total) for progress.

        Returns:
            List of TextChunk objects with metadata.
        """
        all_chunks: list[TextChunk] = []

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
    ) -> list[TextChunk]:
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
        chunks: list[TextChunk] = []
        total_chunks = len(text_chunks)

        for idx, chunk_text in enumerate(text_chunks):
            # Generate a stable ID based on source path and chunk index
            # This helps avoid duplicates if the same folder is indexed again
            # We use MD5 for speed and stability
            id_seed = f"{document.source}_{idx}"
            stable_id = hashlib.md5(id_seed.encode()).hexdigest()

            # Extract document-specific metadata
            doc_language = document.metadata.get("language", "markdown")
            doc_heading_path = document.metadata.get("heading_path")
            doc_section_title = document.metadata.get("section_title")
            doc_content_type = document.metadata.get("content_type", "document")

            # Filter out fields we've already extracted to avoid duplication
            extra_metadata = {
                k: v
                for k, v in document.metadata.items()
                if k
                not in {"language", "heading_path", "section_title", "content_type"}
            }

            chunk_metadata = ChunkMetadata(
                chunk_id=f"chunk_{stable_id[:16]}",
                source=document.source,
                file_name=document.file_name,
                chunk_index=idx,
                total_chunks=total_chunks,
                source_type="doc",
                language=doc_language,
                heading_path=doc_heading_path,
                section_title=doc_section_title,
                content_type=doc_content_type,
                extra=extra_metadata,
            )

            chunk = TextChunk(
                chunk_id=f"chunk_{stable_id[:16]}",
                text=chunk_text,
                source=document.source,
                chunk_index=idx,
                total_chunks=total_chunks,
                token_count=self.count_tokens(chunk_text),
                metadata=chunk_metadata,
            )
            chunks.append(chunk)

        return chunks

    async def rechunk_with_config(
        self,
        documents: list[LoadedDocument],
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[TextChunk]:
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

    def get_chunk_stats(self, chunks: list[TextChunk]) -> dict[str, Any]:
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
            "unique_sources": len({c.source for c in chunks}),
        }


class CodeChunker:
    """
    AST-aware code chunking using LlamaIndex CodeSplitter.

    Splits source code at semantic boundaries (functions, classes, etc.)
    while preserving code structure and adding rich metadata.
    """

    def __init__(
        self,
        language: str,
        chunk_lines: Optional[int] = None,
        chunk_lines_overlap: Optional[int] = None,
        max_chars: Optional[int] = None,
        generate_summaries: bool = False,
    ):
        """
        Initialize the code chunker.

        Args:
            language: Programming language (must be supported by tree-sitter).
            chunk_lines: Target chunk size in lines. Defaults to 40.
            chunk_lines_overlap: Line overlap between chunks. Defaults to 15.
            max_chars: Maximum characters per chunk. Defaults to 1500.
            generate_summaries: Whether to generate LLM summaries for chunks.
        """
        self.language = language
        self.chunk_lines = chunk_lines or 40
        self.chunk_lines_overlap = chunk_lines_overlap or 15
        self.max_chars = max_chars or 1500
        self.generate_summaries = generate_summaries

        # Initialize LlamaIndex CodeSplitter for AST-aware chunking
        self.code_splitter = CodeSplitter(
            language=self.language,
            chunk_lines=self.chunk_lines,
            chunk_lines_overlap=self.chunk_lines_overlap,
            max_chars=self.max_chars,
        )

        # Initialize embedding generator for summaries (only if needed)
        if self.generate_summaries:
            from .embedding import get_embedding_generator
            self.embedding_generator = get_embedding_generator()

        # Initialize tokenizer for token counting
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string."""
        return len(self.tokenizer.encode(text))

    async def chunk_code_document(
        self,
        document: LoadedDocument,
    ) -> list[CodeChunk]:
        """
        Chunk a code document using AST-aware boundaries.

        Args:
            document: Code document to chunk (must have source_type="code").

        Returns:
            List of CodeChunk objects with AST metadata.

        Raises:
            ValueError: If document is not a code document or language mismatch.
        """
        if document.metadata.get("source_type") != "code":
            raise ValueError(f"Document {document.source} is not a code document")

        doc_language = document.metadata.get("language")
        if doc_language and doc_language != self.language:
            logger.warning(
                f"Language mismatch: document has {doc_language}, "
                f"chunker expects {self.language}. Using chunker language."
            )

        if not document.text.strip():
            logger.warning(f"Empty code document: {document.source}")
            return []

        try:
            # Use LlamaIndex CodeSplitter to get AST-aware chunks
            code_chunks = self.code_splitter.split_text(document.text)
        except Exception as e:
            logger.error(f"Failed to chunk code document {document.source}: {e}")
            # Fallback to text-based chunking if AST parsing fails
            logger.info(f"Falling back to text chunking for {document.source}")
            text_splitter = SentenceSplitter(
                chunk_size=self.max_chars,  # Use max_chars as approximate token limit
                chunk_overlap=int(self.max_chars * 0.1),  # 10% overlap
            )
            code_chunks = text_splitter.split_text(document.text)

        # Convert to our CodeChunk format with enhanced metadata
        chunks: list[CodeChunk] = []
        total_chunks = len(code_chunks)

        for idx, chunk_text in enumerate(code_chunks):
            # Generate stable chunk ID
            id_seed = f"{document.source}_{idx}"
            stable_id = hashlib.md5(id_seed.encode()).hexdigest()

            # Generate summary if enabled
            section_summary = None
            if self.generate_summaries and chunk_text.strip():
                try:
                    section_summary = await self.embedding_generator.generate_summary(
                        chunk_text
                    )
                    logger.debug(
                        f"Generated summary for chunk {idx}: {section_summary[:50]}..."
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate summary for chunk {idx}: {e}")
                    section_summary = ""

            chunk = CodeChunk.create(
                chunk_id=f"chunk_{stable_id[:16]}",
                text=chunk_text,
                source=document.source,
                language=self.language,
                chunk_index=idx,
                total_chunks=total_chunks,
                token_count=self.count_tokens(chunk_text),
                section_summary=section_summary,
                # AST metadata will be populated by post-processing if available
                extra=document.metadata.copy(),
            )
            chunks.append(chunk)

        logger.info(
            f"Code chunked {document.source} into {len(chunks)} chunks "
            f"(avg {len(chunks) / max(total_chunks, 1):.1f} chunks/doc)"
        )
        return chunks

    def get_code_chunk_stats(self, chunks: list[CodeChunk]) -> dict[str, Any]:
        """
        Get statistics about code chunks.

        Args:
            chunks: List of CodeChunk objects.

        Returns:
            Dictionary with code chunk statistics.
        """
        if not chunks:
            return {
                "total_chunks": 0,
                "avg_tokens": 0,
                "min_tokens": 0,
                "max_tokens": 0,
                "total_tokens": 0,
                "languages": set(),
                "symbol_types": set(),
            }

        token_counts = [c.token_count for c in chunks]
        languages = {c.metadata.language for c in chunks if c.metadata.language}
        symbol_types = {
            c.metadata.symbol_kind for c in chunks if c.metadata.symbol_kind
        }

        return {
            "total_chunks": len(chunks),
            "avg_tokens": sum(token_counts) / len(token_counts),
            "min_tokens": min(token_counts),
            "max_tokens": max(token_counts),
            "total_tokens": sum(token_counts),
            "unique_sources": len({c.source for c in chunks}),
            "languages": languages,
            "symbol_types": symbol_types,
        }
