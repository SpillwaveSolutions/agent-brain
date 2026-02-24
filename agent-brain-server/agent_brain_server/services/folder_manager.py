"""Folder management service with JSONL persistence.

This module provides the FolderManager service which tracks indexed folders,
persists folder records to JSONL files, and provides atomic, thread-safe
operations for adding, removing, and querying folder metadata.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FolderRecord:
    """Record of an indexed folder with chunk tracking.

    Attributes:
        folder_path: Canonical absolute path to the folder
        chunk_count: Number of chunks indexed from this folder
        last_indexed: ISO 8601 UTC timestamp of last indexing
        chunk_ids: List of chunk IDs for targeted deletion
    """

    folder_path: str
    chunk_count: int
    last_indexed: str
    chunk_ids: list[str]


class FolderManager:
    """Manages indexed folder records with JSONL persistence.

    This service maintains a cache of indexed folders and persists them
    to a JSONL file using atomic write operations. All path operations
    normalize to absolute paths via Path.resolve().

    Thread-safe operations are provided via asyncio.Lock.
    """

    def __init__(self, state_dir: Path) -> None:
        """Initialize FolderManager.

        Args:
            state_dir: Directory for persistent state storage
        """
        self.state_dir = state_dir
        self.jsonl_path = state_dir / "indexed_folders.jsonl"
        self._lock = asyncio.Lock()
        self._cache: dict[str, FolderRecord] = {}

    async def initialize(self) -> None:
        """Initialize the folder manager by loading existing records.

        Loads folder records from JSONL file if it exists. Handles
        missing files gracefully (starts with empty cache).

        Raises:
            OSError: If JSONL file exists but cannot be read
        """
        async with self._lock:
            if self.jsonl_path.exists():
                self._cache = await asyncio.to_thread(self._load_jsonl)
                logger.info(
                    f"Loaded {len(self._cache)} folder records from "
                    f"{self.jsonl_path}"
                )
            else:
                logger.info("No existing folder records found, starting fresh")

    async def add_folder(
        self,
        folder_path: str,
        chunk_count: int,
        chunk_ids: list[str],
    ) -> FolderRecord:
        """Add or update a folder record.

        Normalizes the folder path to absolute form before storing.
        If the folder already exists, updates the record (idempotent).

        Args:
            folder_path: Path to the indexed folder
            chunk_count: Number of chunks indexed
            chunk_ids: List of chunk IDs for deletion

        Returns:
            The created or updated FolderRecord
        """
        normalized_path = str(Path(folder_path).resolve())
        timestamp = datetime.now(timezone.utc).isoformat()

        record = FolderRecord(
            folder_path=normalized_path,
            chunk_count=chunk_count,
            last_indexed=timestamp,
            chunk_ids=chunk_ids,
        )

        async with self._lock:
            self._cache[normalized_path] = record
            await self._persist()

        logger.debug(
            f"Added folder record: {normalized_path} "
            f"({chunk_count} chunks, {len(chunk_ids)} IDs)"
        )
        return record

    async def remove_folder(self, folder_path: str) -> FolderRecord | None:
        """Remove a folder record.

        Normalizes the folder path before lookup. If the folder
        doesn't exist, returns None.

        Args:
            folder_path: Path to the folder to remove

        Returns:
            The removed FolderRecord, or None if not found
        """
        normalized_path = str(Path(folder_path).resolve())

        async with self._lock:
            record = self._cache.pop(normalized_path, None)
            if record is not None:
                await self._persist()
                logger.debug(f"Removed folder record: {normalized_path}")
            else:
                logger.debug(f"Folder not found for removal: {normalized_path}")

        return record

    async def list_folders(self) -> list[FolderRecord]:
        """List all folder records, sorted by path.

        Returns:
            List of FolderRecord objects sorted by folder_path
        """
        async with self._lock:
            return sorted(self._cache.values(), key=lambda r: r.folder_path)

    async def get_folder(self, folder_path: str) -> FolderRecord | None:
        """Get a folder record by path.

        Normalizes the folder path before lookup.

        Args:
            folder_path: Path to the folder

        Returns:
            FolderRecord if found, None otherwise
        """
        normalized_path = str(Path(folder_path).resolve())
        async with self._lock:
            return self._cache.get(normalized_path)

    async def clear(self) -> None:
        """Clear all folder records and delete the JSONL file.

        This is typically used for testing or when resetting the index.
        """
        async with self._lock:
            self._cache.clear()
            if self.jsonl_path.exists():
                await asyncio.to_thread(self.jsonl_path.unlink)
                logger.info(f"Cleared all folder records and deleted {self.jsonl_path}")
            else:
                logger.info("Cleared folder records (no JSONL file to delete)")

    async def _persist(self) -> None:
        """Persist the cache to JSONL file using atomic write.

        Uses a temp file + atomic rename to ensure consistency even
        if the process crashes during write. Must be called under lock.
        """
        await asyncio.to_thread(self._write_jsonl)

    def _load_jsonl(self) -> dict[str, FolderRecord]:
        """Load folder records from JSONL file (synchronous).

        Handles corrupt lines with logging warnings. Empty lines are skipped.

        Returns:
            Dictionary of folder records keyed by folder_path
        """
        records: dict[str, FolderRecord] = {}

        with open(self.jsonl_path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    record = FolderRecord(
                        folder_path=data["folder_path"],
                        chunk_count=data["chunk_count"],
                        last_indexed=data["last_indexed"],
                        chunk_ids=data["chunk_ids"],
                    )
                    records[record.folder_path] = record
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(
                        f"Skipping corrupt line {line_num} in "
                        f"{self.jsonl_path}: {e}"
                    )
                    continue

        return records

    def _write_jsonl(self) -> None:
        """Write folder records to JSONL file with atomic rename (synchronous).

        Uses a temporary file and atomic replace to ensure consistency.
        Must be called under lock.
        """
        # Ensure state directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Write to temporary file
        temp_path = self.jsonl_path.with_suffix(".jsonl.tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            for record in self._cache.values():
                line = json.dumps(asdict(record))
                f.write(line + "\n")

        # Atomic rename
        temp_path.replace(self.jsonl_path)
