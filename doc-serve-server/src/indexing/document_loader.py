"""Document loading from various file formats using LlamaIndex."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

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


class DocumentLoader:
    """
    Loads documents from a folder supporting multiple file formats.

    Supported formats: .txt, .md, .pdf, .docx, .html
    """

    SUPPORTED_EXTENSIONS: set[str] = {".txt", ".md", ".pdf", ".docx", ".html", ".rst"}

    def __init__(
        self,
        supported_extensions: Optional[set[str]] = None,
    ):
        """
        Initialize the document loader.

        Args:
            supported_extensions: Set of file extensions to load.
                                  Defaults to SUPPORTED_EXTENSIONS.
        """
        self.extensions = supported_extensions or self.SUPPORTED_EXTENSIONS

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

        # Use LlamaIndex's SimpleDirectoryReader
        try:
            reader = SimpleDirectoryReader(
                input_dir=str(path),
                recursive=recursive,
                required_exts=list(self.extensions),
                filename_as_id=True,
            )
            llama_documents: list[Document] = reader.load_data()
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

            loaded_doc = LoadedDocument(
                text=doc.text,
                source=file_path,
                file_name=file_name,
                file_path=file_path,
                file_size=file_size,
                metadata={
                    **doc.metadata,
                    "doc_id": doc.doc_id,
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
        docs = reader.load_data()

        if not docs:
            raise ValueError(f"No content loaded from file: {file_path}")

        doc = docs[0]
        return LoadedDocument(
            text=doc.text,
            source=file_path,
            file_name=path.name,
            file_path=str(path),
            file_size=path.stat().st_size,
            metadata={
                **doc.metadata,
                "doc_id": doc.doc_id,
            },
        )

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
