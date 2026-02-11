"""Context-aware text chunking with configurable overlap."""

import hashlib
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

import tiktoken
import tree_sitter
import tree_sitter_language_pack as tslp
from llama_index.core.node_parser import CodeSplitter, SentenceSplitter

from agent_brain_server.config import settings

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
    language: str | None = None  # For docs/code: language type
    heading_path: str | None = None  # Document heading hierarchy
    section_title: str | None = None  # Current section title
    content_type: str | None = None  # "tutorial", "api_ref", "guide", etc.

    # Code-specific metadata (AST-aware fields)
    symbol_name: str | None = None  # Full symbol path
    symbol_kind: str | None = None  # "function", "class", "method", etc.
    start_line: int | None = None  # 1-based line number
    end_line: int | None = None  # 1-based line number
    section_summary: str | None = None  # AI-generated summary
    prev_section_summary: str | None = None  # Previous section summary
    docstring: str | None = None  # Extracted docstring
    parameters: list[str] | None = None  # Function parameters as strings
    return_type: str | None = None  # Function return type
    decorators: list[str] | None = None  # Python decorators or similar
    imports: list[str] | None = None  # Import statements in this chunk

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
        symbol_name: str | None = None,
        symbol_kind: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        section_summary: str | None = None,
        prev_section_summary: str | None = None,
        docstring: str | None = None,
        parameters: list[str] | None = None,
        return_type: str | None = None,
        decorators: list[str] | None = None,
        imports: list[str] | None = None,
        extra: dict[str, Any] | None = None,
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
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
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
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
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
        chunk_lines: int | None = None,
        chunk_lines_overlap: int | None = None,
        max_chars: int | None = None,
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

        # Initialize tree-sitter parser
        self._setup_language()

        # Initialize embedding generator for summaries (only if needed)
        if self.generate_summaries:
            from .embedding import get_embedding_generator

            self.embedding_generator = get_embedding_generator()

        # Initialize tokenizer for token counting
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def _setup_language(self) -> None:
        """Set up the tree-sitter language and parser."""
        try:
            # Map common names to tree-sitter identifiers
            lang_map = {
                "python": "python",
                "typescript": "typescript",
                "tsx": "tsx",
                "javascript": "javascript",
                "go": "go",
                "rust": "rust",
                "java": "java",
                "cpp": "cpp",
                "c": "c",
                "csharp": "csharp",
            }

            lang_id = lang_map.get(self.language)
            if not lang_id:
                logger.warning(
                    f"AST metadata extraction not supported for {self.language}"
                )
                self.ts_language = None
                return

            self.ts_language = tslp.get_language(cast(tslp.SupportedLanguage, lang_id))
            self.parser = tree_sitter.Parser(self.ts_language)

        except Exception as e:
            logger.warning(f"Failed to load tree-sitter language {self.language}: {e}")
            self.ts_language = None

    def _get_symbols(self, text: str) -> list[dict[str, Any]]:
        """Extract symbols (functions, classes) and their line ranges from text."""
        if not hasattr(self, "ts_language") or not self.ts_language:
            return []

        try:
            tree = self.parser.parse(text.encode("utf-8"))
            root = tree.root_node
        except Exception as e:
            logger.error(f"Failed to parse AST: {e}")
            return []

        symbols = []

        # Define queries for common languages
        query_str = ""
        if self.language == "python":
            query_str = """
                (function_definition
                  name: (identifier) @name) @symbol
                (class_definition
                  name: (identifier) @name) @symbol
            """
        elif self.language in ["typescript", "tsx", "javascript"]:
            # Use separate patterns instead of alternation to avoid QueryError
            # in some versions
            class_name_type = (
                "type_identifier"
                if self.language in ["typescript", "tsx"]
                else "identifier"
            )
            query_str = f"""
                (function_declaration
                  name: (identifier) @name) @symbol
                (method_definition
                  name: (property_identifier) @name) @symbol
                (class_declaration
                  name: ({class_name_type}) @name) @symbol
                (variable_declarator
                  name: (identifier) @name
                  value: (arrow_function)) @symbol
                (variable_declarator
                  name: (identifier) @name
                  value: (function_expression)) @symbol
            """
        elif self.language == "java":
            query_str = """
                (method_declaration
                  name: (identifier) @name) @symbol
                (class_declaration
                  name: (identifier) @name) @symbol
            """
        elif self.language == "go":
            query_str = """
                (function_declaration
                  name: (identifier) @name) @symbol
                (method_declaration
                  name: (field_identifier) @name) @symbol
                (type_declaration
                  (type_spec
                    name: (type_identifier) @name)) @symbol
            """
        elif self.language == "csharp":
            query_str = """
                (class_declaration
                  name: (identifier) @name) @symbol
                (method_declaration
                  name: (identifier) @name) @symbol
                (constructor_declaration
                  name: (identifier) @name) @symbol
                (interface_declaration
                  name: (identifier) @name) @symbol
                (property_declaration
                  name: (identifier) @name) @symbol
                (enum_declaration
                  name: (identifier) @name) @symbol
                (struct_declaration
                  name: (identifier) @name) @symbol
                (record_declaration
                  name: (identifier) @name) @symbol
                (namespace_declaration
                  name: (identifier) @name) @symbol
            """

        if not query_str:
            return []

        try:
            query = tree_sitter.Query(self.ts_language, query_str)
            cursor = tree_sitter.QueryCursor(query)
            matches = cursor.matches(root)

            for _, captures in matches:
                # In 0.22+, captures is a dict mapping capture name to list of nodes
                symbol_nodes = captures.get("symbol", [])
                name_nodes = captures.get("name", [])

                if symbol_nodes and name_nodes:
                    node = symbol_nodes[0]
                    name_node = name_nodes[0]
                    name_text = ""
                    if hasattr(name_node, "text") and name_node.text:
                        name_text = name_node.text.decode("utf-8")

                    symbol_info: dict[str, Any] = {
                        "name": name_text,
                        "kind": node.type,
                        "start_line": node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                    }

                    # Extract XML doc comments for C# declarations
                    if self.language == "csharp":
                        docstring = self._extract_xml_doc_comment(
                            text, node.start_point[0]
                        )
                        if docstring:
                            symbol_info["docstring"] = docstring

                    symbols.append(symbol_info)
        except Exception as e:
            logger.error(f"Error querying AST for {self.language}: {e}")

        return symbols

    def _extract_xml_doc_comment(self, text: str, declaration_line: int) -> str | None:
        """
        Extract XML doc comments (/// lines) preceding a C# declaration.

        Args:
            text: The full source code text.
            declaration_line: The 0-based line index of the declaration.

        Returns:
            Plain text extracted from XML doc comments, or None if not found.
        """
        lines = text.split("\n")
        doc_lines: list[str] = []

        # Walk backwards from the line before the declaration
        line_idx = declaration_line - 1
        while line_idx >= 0:
            stripped = lines[line_idx].strip()
            if stripped.startswith("///"):
                # Remove the /// prefix
                content = stripped[3:].strip()
                doc_lines.insert(0, content)
                line_idx -= 1
            elif stripped.startswith("[") and stripped.endswith("]"):
                # Skip attributes like [Serializable]
                line_idx -= 1
            else:
                break

        if not doc_lines:
            return None

        # Strip XML tags for plain text
        combined = " ".join(doc_lines)
        # Remove XML tags like <summary>, </summary>, <param name="x">, etc.
        plain_text = re.sub(r"<[^>]+>", "", combined)
        # Collapse whitespace
        plain_text = re.sub(r"\s+", " ", plain_text).strip()

        return plain_text if plain_text else None

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

        # Extract symbols for metadata enrichment
        symbols = self._get_symbols(document.text)

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

        # Track line numbers by matching chunk text back to original document
        current_pos = 0
        original_text = document.text

        for idx, chunk_text in enumerate(code_chunks):
            # Generate stable chunk ID
            id_seed = f"{document.source}_{idx}"
            stable_id = hashlib.md5(id_seed.encode()).hexdigest()

            # Determine line numbers for this chunk
            start_line = None
            end_line = None
            start_idx = original_text.find(chunk_text, current_pos)
            if start_idx != -1:
                start_line = original_text.count("\n", 0, start_idx) + 1
                end_line = start_line + chunk_text.count("\n")
                current_pos = start_idx + len(chunk_text)

            # Find dominant symbol for this chunk
            symbol_name = None
            symbol_kind = None
            if start_line is not None and end_line is not None:
                # Find symbols that overlap with this chunk
                overlapping_symbols = [
                    s
                    for s in symbols
                    if not (s["end_line"] < start_line or s["start_line"] > end_line)
                ]

                if overlapping_symbols:
                    # Strategy:
                    # 1. Prefer symbols that START within the chunk
                    # 2. If multiple start in chunk, pick the first one
                    # 3. If none start in chunk, pick the most "nested" one
                    #    that overlaps (the one that starts latest)

                    in_chunk_symbols = [
                        s
                        for s in overlapping_symbols
                        if start_line <= s["start_line"] <= end_line
                    ]

                    if in_chunk_symbols:
                        # Pick the most "specific" one starting in the chunk
                        # (latest start line)
                        in_chunk_symbols.sort(
                            key=lambda x: x["start_line"], reverse=True
                        )
                        symbol_name = in_chunk_symbols[0]["name"]
                        symbol_kind = in_chunk_symbols[0]["kind"]
                    else:
                        # None start in chunk, pick the one that starts latest
                        # (most specific parent)
                        overlapping_symbols.sort(
                            key=lambda x: x["start_line"], reverse=True
                        )
                        symbol_name = overlapping_symbols[0]["name"]
                        symbol_kind = overlapping_symbols[0]["kind"]

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
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=start_line,
                end_line=end_line,
                section_summary=section_summary,
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
