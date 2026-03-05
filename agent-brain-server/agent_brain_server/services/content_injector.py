"""Content injection service for enriching chunks with metadata during indexing.

Implements INJECT-01 through INJECT-07: user-provided Python scripts or static JSON
metadata can be applied to each chunk before embedding generation, enabling
domain-specific metadata enrichment without modifying the core pipeline.
"""

from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_brain_server.indexing.chunking import CodeChunk, TextChunk

logger = logging.getLogger(__name__)

# Keys that are part of the standard ChunkMetadata schema (not extras)
_KNOWN_CHUNK_KEYS: frozenset[str] = frozenset(
    {
        "chunk_id",
        "source",
        "file_name",
        "chunk_index",
        "total_chunks",
        "source_type",
        "created_at",
        "language",
        "heading_path",
        "section_title",
        "content_type",
        "symbol_name",
        "symbol_kind",
        "start_line",
        "end_line",
        "section_summary",
        "prev_section_summary",
        "docstring",
        "parameters",
        "return_type",
        "decorators",
        "imports",
    }
)


class ContentInjector:
    """Enriches chunks with metadata during indexing.

    Supports two enrichment modes (usable separately or together):

    1. **Script injection** — loads a user-provided Python module via importlib
       and calls its ``process_chunk(chunk: dict) -> dict`` function on every chunk.
    2. **Folder metadata** — merges a static ``dict`` (typically loaded from JSON)
       into every chunk before script injection runs.

    Per-chunk exceptions are caught and logged without crashing the pipeline
    (INJECT-05). Non-scalar values that ChromaDB cannot store are validated and
    stripped with a warning (INJECT-06).

    Example::

        injector = ContentInjector.build(
            script_path="/path/to/inject.py",
            metadata_path="/path/to/meta.json",
        )
        if injector is not None:
            injector.apply_to_chunks(all_chunks, known_keys)
    """

    def __init__(
        self,
        script_path: Path | None = None,
        folder_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ContentInjector.

        Args:
            script_path: Path to a Python file that exports
                ``process_chunk(chunk: dict) -> dict``.
            folder_metadata: Static key/value pairs merged into every chunk.
        """
        self._folder_metadata: dict[str, Any] = folder_metadata or {}
        self._process_chunk_fn: Any = None

        if script_path is not None:
            self._load_script(script_path)

    # ------------------------------------------------------------------
    # Script loading
    # ------------------------------------------------------------------

    def _load_script(self, script_path: Path) -> None:
        """Load a Python injector script from disk via importlib.

        Args:
            script_path: Absolute or relative path to the ``.py`` script.

        Raises:
            FileNotFoundError: Script file does not exist.
            ImportError: Module spec could not be created or module failed to load.
            AttributeError: Module does not expose a ``process_chunk`` attribute.
            TypeError: ``process_chunk`` attribute is not callable.
        """
        if not script_path.exists():
            raise FileNotFoundError(f"Injector script not found: {script_path}")

        spec = importlib.util.spec_from_file_location("_injector_script", script_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create module spec from: {script_path}")

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise ImportError(
                f"Failed to load injector module {script_path}: {exc}"
            ) from exc

        if not hasattr(module, "process_chunk"):
            raise AttributeError(
                f"Injector script {script_path} must define 'process_chunk'"
            )

        fn = module.process_chunk
        if not callable(fn):
            raise TypeError(
                f"'process_chunk' in {script_path} must be callable, "
                f"got {type(fn).__name__}"
            )

        self._process_chunk_fn = fn
        logger.info(f"Loaded injector script: {script_path}")

    # ------------------------------------------------------------------
    # Class-method factories
    # ------------------------------------------------------------------

    @classmethod
    def from_folder_metadata_file(cls, metadata_path: Path) -> ContentInjector:
        """Create a ContentInjector from a JSON metadata file.

        Args:
            metadata_path: Path to a JSON file whose root value is a ``dict``.

        Returns:
            ContentInjector configured with the loaded metadata.

        Raises:
            FileNotFoundError: File does not exist.
            TypeError: JSON root value is not a dict.
        """
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        raw = metadata_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        if not isinstance(data, dict):
            raise TypeError(
                f"Metadata file {metadata_path} must contain a JSON object "
                f"(dict), got {type(data).__name__}"
            )

        return cls(folder_metadata=data)

    @classmethod
    def build(
        cls,
        script_path: str | None = None,
        metadata_path: str | None = None,
    ) -> ContentInjector | None:
        """Factory: build a ContentInjector from optional string paths.

        Returns ``None`` when both arguments are ``None`` (no injection needed).

        Args:
            script_path: String path to the Python injector script, or None.
            metadata_path: String path to the JSON metadata file, or None.

        Returns:
            A configured ``ContentInjector``, or ``None`` if both paths are None.
        """
        if script_path is None and metadata_path is None:
            return None

        folder_metadata: dict[str, Any] | None = None
        if metadata_path is not None:
            meta_p = Path(metadata_path).expanduser().resolve()
            if not meta_p.exists():
                raise FileNotFoundError(f"Metadata file not found: {metadata_path}")
            raw = meta_p.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise TypeError(
                    f"Metadata file must contain a JSON object, "
                    f"got {type(data).__name__}"
                )
            folder_metadata = data

        resolved_script: Path | None = None
        if script_path is not None:
            resolved_script = Path(script_path).expanduser().resolve()

        return cls(script_path=resolved_script, folder_metadata=folder_metadata)

    # ------------------------------------------------------------------
    # Core apply methods
    # ------------------------------------------------------------------

    def apply(self, chunk: dict[str, Any]) -> dict[str, Any]:
        """Apply injector enrichment to a single chunk dict.

        Steps:
        1. Merge folder_metadata (shallow merge, metadata values win).
        2. Call process_chunk_fn if loaded.
        3. Validate and strip non-scalar values.

        Per-chunk exceptions are caught and logged; the original (or partially
        enriched) chunk is returned without crashing the pipeline (INJECT-05).

        Args:
            chunk: A dict representation of chunk metadata.

        Returns:
            Enriched chunk dict with non-scalar values stripped.
        """
        # Step 1: Merge folder metadata
        if self._folder_metadata:
            try:
                chunk = {**chunk, **self._folder_metadata}
            except Exception as exc:
                logger.warning(
                    f"ContentInjector: failed to merge folder metadata: {exc}"
                )

        # Step 2: Call user script
        if self._process_chunk_fn is not None:
            try:
                result = self._process_chunk_fn(chunk)
                if not isinstance(result, dict):
                    logger.warning(
                        f"ContentInjector: process_chunk returned "
                        f"{type(result).__name__}, expected dict — skipping script "
                        "enrichment"
                    )
                else:
                    chunk = result
            except Exception as exc:
                logger.warning(
                    f"ContentInjector: process_chunk raised an exception "
                    f"({type(exc).__name__}: {exc}) — skipping script enrichment"
                )

        # Step 3: Validate scalar values
        chunk = self._validate_metadata_values(chunk)

        return chunk

    def _validate_metadata_values(self, chunk: dict[str, Any]) -> dict[str, Any]:
        """Strip non-scalar metadata values incompatible with ChromaDB.

        ChromaDB requires all metadata values to be ``str | int | float | bool | None``.
        Any other type (list, dict, set, …) is logged as a warning and removed.

        Args:
            chunk: Chunk metadata dict to validate.

        Returns:
            Cleaned dict with only scalar values.
        """
        cleaned: dict[str, Any] = {}
        for key, value in chunk.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                cleaned[key] = value
            else:
                logger.warning(
                    f"ContentInjector: metadata key '{key}' has non-scalar value "
                    f"({type(value).__name__}) — removing for ChromaDB compatibility"
                )
        return cleaned

    def apply_to_chunks(
        self,
        chunks: list[TextChunk | CodeChunk],
        known_keys: set[str],
    ) -> int:
        """Apply injection to chunks, writing new keys to chunk.metadata.extra.

        Only keys that are *not* in ``known_keys`` (standard schema keys) are
        written back to ``chunk.metadata.extra``.  This prevents injectors from
        accidentally overwriting core metadata fields.

        Args:
            chunks: List of TextChunk or CodeChunk objects from the pipeline.
            known_keys: Set of standard metadata key names to exclude from extra.

        Returns:
            Count of chunks that had at least one new key injected.
        """
        enriched_count = 0

        for chunk in chunks:
            original_dict = chunk.metadata.to_dict()
            enriched_dict = self.apply(original_dict)

            # Extract only new/unknown keys
            new_keys: dict[str, Any] = {}
            for key, value in enriched_dict.items():
                if key not in known_keys:
                    new_keys[key] = value

            if new_keys:
                chunk.metadata.extra.update(new_keys)
                enriched_count += 1

        return enriched_count
