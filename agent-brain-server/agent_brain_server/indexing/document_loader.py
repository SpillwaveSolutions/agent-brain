"""Document loading from various file formats using LlamaIndex."""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llama_index.core import Document, SimpleDirectoryReader

logger = logging.getLogger(__name__)


@dataclass
class LoadedDocument:
    """Represents a loaded document with metadata."""

    text: str
    source: str
    file_name: str
    file_path: str
    file_size: int
    metadata: dict[str, Any] = field(default_factory=dict)


class LanguageDetector:
    """
    Utility for detecting programming languages from file paths and content.

    Supports the 10 languages with tree-sitter parsers:
    - Python, TypeScript, JavaScript, Kotlin, C, C++, Java, Go, Rust, Swift
    """

    # Language detection by file extension
    EXTENSION_TO_LANGUAGE = {
        # Python
        ".py": "python",
        ".pyw": "python",
        ".pyi": "python",
        # TypeScript/JavaScript
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",
        # Kotlin
        ".kt": "kotlin",
        ".kts": "kotlin",
        # C/C++
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hxx": "cpp",
        # Java
        ".java": "java",
        # Go
        ".go": "go",
        # Rust
        ".rs": "rust",
        # Swift
        ".swift": "swift",
        # C#
        ".cs": "csharp",
        ".csx": "csharp",
    }

    # Language detection by content patterns (fallback)
    CONTENT_PATTERNS = {
        "python": [
            re.compile(r"^\s*import\s+\w+", re.MULTILINE),
            re.compile(r"^\s*from\s+\w+\s+import", re.MULTILINE),
            re.compile(r"^\s*def\s+\w+\s*\(", re.MULTILINE),
            re.compile(r"^\s*class\s+\w+", re.MULTILINE),
        ],
        "javascript": [
            re.compile(r"^\s*(const|let|var)\s+\w+\s*=", re.MULTILINE),
            re.compile(r"^\s*function\s+\w+\s*\(", re.MULTILINE),
            re.compile(r"^\s*=>\s*\{", re.MULTILINE),  # Arrow functions
        ],
        "typescript": [
            re.compile(r"^\s*interface\s+\w+", re.MULTILINE),
            re.compile(r"^\s*type\s+\w+\s*=", re.MULTILINE),
            re.compile(r":\s*(string|number|boolean|any)", re.MULTILINE),
        ],
        "java": [
            re.compile(r"^\s*public\s+class\s+\w+", re.MULTILINE),
            re.compile(r"^\s*package\s+\w+", re.MULTILINE),
            re.compile(r"^\s*import\s+java\.", re.MULTILINE),
        ],
        "kotlin": [
            re.compile(r"^\s*fun\s+\w+\s*\(", re.MULTILINE),
            re.compile(r"^\s*class\s+\w+", re.MULTILINE),
            re.compile(r":\s*(String|Int|Boolean)", re.MULTILINE),
        ],
        "cpp": [
            re.compile(r"^\s*#include\s*<", re.MULTILINE),
            re.compile(r"^\s*using\s+namespace", re.MULTILINE),
            re.compile(r"^\s*std::", re.MULTILINE),
        ],
        "c": [
            re.compile(r"^\s*#include\s*<", re.MULTILINE),
            re.compile(r"^\s*int\s+main\s*\(", re.MULTILINE),
            re.compile(r"^\s*printf\s*\(", re.MULTILINE),
        ],
        "go": [
            re.compile(r"^\s*package\s+\w+", re.MULTILINE),
            re.compile(r"^\s*import\s*\(", re.MULTILINE),
            re.compile(r"^\s*func\s+\w+\s*\(", re.MULTILINE),
        ],
        "rust": [
            re.compile(r"^\s*fn\s+\w+\s*\(", re.MULTILINE),
            re.compile(r"^\s*use\s+\w+::", re.MULTILINE),
            re.compile(r"^\s*let\s+(mut\s+)?\w+", re.MULTILINE),
        ],
        "swift": [
            re.compile(r"^\s*import\s+Foundation", re.MULTILINE),
            re.compile(r"^\s*func\s+\w+\s*\(", re.MULTILINE),
            re.compile(r"^\s*class\s+\w+\s*:", re.MULTILINE),
        ],
        "csharp": [
            re.compile(r"^\s*using\s+System", re.MULTILINE),
            re.compile(r"^\s*namespace\s+\w+", re.MULTILINE),
            re.compile(r"\{\s*get\s*;\s*(set\s*;)?\s*\}", re.MULTILINE),
            re.compile(r"\[[\w]+(\(.*\))?\]", re.MULTILINE),
            re.compile(
                r"^\s*public\s+(class|interface|struct|record|enum)\s+\w+",
                re.MULTILINE,
            ),
        ],
    }

    @classmethod
    def detect_from_path(cls, file_path: str) -> str | None:
        """
        Detect language from file path/extension.

        Args:
            file_path: Path to the file.

        Returns:
            Language name or None if not detected.
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        return cls.EXTENSION_TO_LANGUAGE.get(extension)

    @classmethod
    def detect_from_content(
        cls, content: str, top_n: int = 3
    ) -> list[tuple[str, float]]:
        """
        Detect language from file content using pattern matching.

        Args:
            content: File content to analyze.
            top_n: Number of top matches to return.

        Returns:
            List of (language, confidence) tuples, sorted by confidence.
        """
        scores: dict[str, float] = {}

        for language, patterns in cls.CONTENT_PATTERNS.items():
            total_score = 0.0
            pattern_count = len(patterns)

            for pattern in patterns:
                matches = len(pattern.findall(content))
                if matches > 0:
                    # Score based on number of matches, normalized by pattern count
                    total_score += min(matches / 10.0, 1.0)  # Cap at 1.0 per pattern

            if total_score > 0:
                scores[language] = total_score / pattern_count

        # Sort by score descending
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_n]

    @classmethod
    def detect_language(cls, file_path: str, content: str | None = None) -> str | None:
        """
        Detect programming language using both path and content analysis.

        Args:
            file_path: Path to the file.
            content: Optional file content for fallback detection.

        Returns:
            Detected language name or None.
        """
        # First try extension-based detection (fast and reliable)
        language = cls.detect_from_path(file_path)
        if language:
            return language

        # Fallback to content analysis if content is provided
        if content:
            content_matches = cls.detect_from_content(content, top_n=1)
            if (
                content_matches and content_matches[0][1] > 0.1
            ):  # Minimum confidence threshold
                return content_matches[0][0]

        return None

    @classmethod
    def is_supported_language(cls, language: str) -> bool:
        """
        Check if a language is supported by our tree-sitter parsers.

        Args:
            language: Language name to check.

        Returns:
            True if supported, False otherwise.
        """
        return language in cls.CONTENT_PATTERNS

    @classmethod
    def get_supported_languages(cls) -> list[str]:
        """Get list of all supported programming languages."""
        return list(cls.CONTENT_PATTERNS.keys())


class DocumentLoader:
    """
    Loads documents and code files from a folder supporting multiple file formats.

    Supported document formats: .txt, .md, .pdf, .docx, .html, .rst
    Supported code formats: .py, .ts, .tsx, .js, .jsx, .kt, .c, .cpp,
    .java, .go, .rs, .swift
    """

    # Document formats
    DOCUMENT_EXTENSIONS: set[str] = {".txt", ".md", ".pdf", ".docx", ".html", ".rst"}

    # Code formats (supported by tree-sitter)
    CODE_EXTENSIONS: set[str] = {
        ".py",
        ".pyw",
        ".pyi",  # Python
        ".ts",
        ".tsx",  # TypeScript
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",  # JavaScript
        ".kt",
        ".kts",  # Kotlin
        ".c",
        ".h",  # C
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
        ".hxx",  # C++
        ".java",  # Java
        ".go",  # Go
        ".rs",  # Rust
        ".swift",  # Swift
        ".cs",
        ".csx",  # C#
    }

    SUPPORTED_EXTENSIONS: set[str] = DOCUMENT_EXTENSIONS | CODE_EXTENSIONS

    # Default directories to exclude from indexing
    DEFAULT_EXCLUDE_PATTERNS: list[str] = [
        "**/node_modules/**",
        "**/__pycache__/**",
        "**/.venv/**",
        "**/venv/**",
        "**/.git/**",
        "**/dist/**",
        "**/build/**",
        "**/target/**",
        "**/.next/**",
        "**/.nuxt/**",
        "**/coverage/**",
        "**/.pytest_cache/**",
        "**/.mypy_cache/**",
        "**/.tox/**",
        "**/egg-info/**",
        "**/*.egg-info/**",
    ]

    def __init__(
        self,
        supported_extensions: set[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ):
        """
        Initialize the document loader.

        Args:
            supported_extensions: Set of file extensions to load.
                                  Defaults to SUPPORTED_EXTENSIONS.
            exclude_patterns: List of glob patterns to exclude.
                              Defaults to DEFAULT_EXCLUDE_PATTERNS.
        """
        self.extensions = supported_extensions or self.SUPPORTED_EXTENSIONS
        self.exclude_patterns = (
            exclude_patterns
            if exclude_patterns is not None
            else self.DEFAULT_EXCLUDE_PATTERNS
        )

    async def load_from_folder(
        self,
        folder_path: str,
        recursive: bool = True,
    ) -> list[LoadedDocument]:
        """
        Load all supported documents from a folder.

        Args:
            folder_path: Path to the folder containing documents.
            recursive: Whether to scan subdirectories recursively.

        Returns:
            List of LoadedDocument objects.

        Raises:
            ValueError: If the folder path is invalid.
            FileNotFoundError: If the folder doesn't exist.
        """
        path = Path(folder_path)

        if not path.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {folder_path}")

        logger.info(f"Loading documents from: {folder_path} (recursive={recursive})")
        if self.exclude_patterns:
            logger.info(
                f"Excluding patterns: {self.exclude_patterns[:3]}... "
                f"({len(self.exclude_patterns)} total)"
            )

        # Use LlamaIndex's SimpleDirectoryReader
        # Run in thread pool to avoid blocking the event loop
        try:
            reader = SimpleDirectoryReader(
                input_dir=str(path),
                recursive=recursive,
                required_exts=list(self.extensions),
                exclude=self.exclude_patterns,
                filename_as_id=True,
            )
            # reader.load_data() is blocking I/O - run in thread pool
            llama_documents: list[Document] = await asyncio.to_thread(reader.load_data)
        except Exception as e:
            logger.error(f"Failed to load documents: {e}")
            raise

        # Convert to our LoadedDocument format
        loaded_docs: list[LoadedDocument] = []

        for doc in llama_documents:
            file_path = doc.metadata.get("file_path", "")
            file_name = doc.metadata.get(
                "file_name", Path(file_path).name if file_path else "unknown"
            )

            # Get file size
            try:
                file_size = Path(file_path).stat().st_size if file_path else 0
            except OSError:
                file_size = 0

            # Detect language for code files
            language = None
            source_type = "doc"  # Default to document
            if file_path:
                path_ext = Path(file_path).suffix.lower()
                if path_ext in self.CODE_EXTENSIONS:
                    source_type = "code"
                    language = LanguageDetector.detect_language(file_path, doc.text)

            loaded_doc = LoadedDocument(
                text=doc.text,
                source=file_path,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                metadata={
                    **doc.metadata,
                    "doc_id": doc.doc_id,
                    "source_type": source_type,
                    "language": language,
                },
            )
            loaded_docs.append(loaded_doc)

        logger.info(f"Loaded {len(loaded_docs)} documents from {folder_path}")
        return loaded_docs

    async def load_single_file(self, file_path: str) -> LoadedDocument:
        """
        Load a single document file.

        Args:
            file_path: Path to the file.

        Returns:
            LoadedDocument object.

        Raises:
            ValueError: If the file type is not supported.
            FileNotFoundError: If the file doesn't exist.
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.suffix.lower() not in self.extensions:
            raise ValueError(
                f"Unsupported file type: {path.suffix}. "
                f"Supported: {', '.join(self.extensions)}"
            )

        reader = SimpleDirectoryReader(
            input_files=[str(path)],
            filename_as_id=True,
        )
        # Run in thread pool to avoid blocking the event loop
        docs = await asyncio.to_thread(reader.load_data)

        if not docs:
            raise ValueError(f"No content loaded from file: {file_path}")

        doc = docs[0]

        # Detect language for code files
        language = None
        source_type = "doc"  # Default to document
        path_ext = path.suffix.lower()
        if path_ext in self.CODE_EXTENSIONS:
            source_type = "code"
            language = LanguageDetector.detect_language(str(path), doc.text)

        return LoadedDocument(
            text=doc.text,
            source=file_path,
            file_name=path.name,
            file_path=str(path),
            file_size=path.stat().st_size,
            metadata={
                **doc.metadata,
                "doc_id": doc.doc_id,
                "source_type": source_type,
                "language": language,
            },
        )

    async def load_files(
        self,
        folder_path: str,
        recursive: bool = True,
        include_code: bool = False,
    ) -> list[LoadedDocument]:
        """
        Load documents and optionally code files from a folder.

        Args:
            folder_path: Path to the folder containing files to load.
            recursive: Whether to scan subdirectories recursively.
            include_code: Whether to include source code files alongside documents.

        Returns:
            List of LoadedDocument objects with proper metadata.

        Raises:
            ValueError: If folder path is invalid.
            FileNotFoundError: If folder doesn't exist.
        """
        # Configure extensions based on include_code flag
        if include_code:
            # Use all supported extensions (docs + code)
            effective_extensions = self.SUPPORTED_EXTENSIONS
        else:
            # Use only document extensions
            effective_extensions = self.DOCUMENT_EXTENSIONS

        # Create a temporary loader with the effective extensions and exclude patterns
        temp_loader = DocumentLoader(
            supported_extensions=effective_extensions,
            exclude_patterns=self.exclude_patterns,
        )

        # Load files using the configured extensions
        loaded_docs = await temp_loader.load_from_folder(folder_path, recursive)

        # Ensure all documents have proper source_type metadata
        for doc in loaded_docs:
            if not doc.metadata.get("source_type"):
                path_ext = Path(doc.source).suffix.lower()
                if path_ext in self.CODE_EXTENSIONS:
                    doc.metadata["source_type"] = "code"
                    # Detect language for code files
                    language = LanguageDetector.detect_language(doc.source, doc.text)
                    if language:
                        doc.metadata["language"] = language
                else:
                    doc.metadata["source_type"] = "doc"
                    doc.metadata["language"] = "markdown"  # Default for documents

        return loaded_docs

    def get_supported_files(
        self,
        folder_path: str,
        recursive: bool = True,
    ) -> list[Path]:
        """
        Get list of supported files in a folder without loading them.

        Args:
            folder_path: Path to the folder.
            recursive: Whether to scan subdirectories.

        Returns:
            List of Path objects for supported files.
        """
        path = Path(folder_path)

        if not path.exists() or not path.is_dir():
            return []

        if recursive:
            files = list(path.rglob("*"))
        else:
            files = list(path.glob("*"))

        return [f for f in files if f.is_file() and f.suffix.lower() in self.extensions]
