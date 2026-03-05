"""Manifest tracker for per-folder incremental indexing.

This module provides the ManifestTracker service which maintains per-folder
JSON manifests recording file checksums, mtimes, and chunk IDs. It enables
incremental indexing by detecting which files have changed since the last
index run.

Manifest path: <manifests_dir>/<sha256(folder_path)>.json
Atomic writes via temp + Path.replace() for crash safety.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileRecord:
    """Per-file record stored in a folder manifest.

    Attributes:
        checksum: SHA-256 hex digest of the file's content
        mtime: File modification time as float seconds (os.stat().st_mtime)
        chunk_ids: List of chunk IDs produced from this file during indexing
    """

    checksum: str
    mtime: float
    chunk_ids: list[str]


@dataclass
class FolderManifest:
    """Full manifest for one indexed folder.

    Attributes:
        folder_path: Absolute path to the indexed folder
        files: Mapping of absolute file path strings to FileRecord objects
    """

    folder_path: str
    files: dict[str, FileRecord] = field(default_factory=dict)


@dataclass
class EvictionSummary:
    """Result of a manifest diff and chunk eviction pass.

    Attributes:
        files_added: New files not present in prior manifest
        files_changed: Files whose content checksum changed
        files_deleted: Files present in prior manifest but not on disk
        files_unchanged: Files with matching mtime/checksum (skipped)
        chunks_evicted: Total chunk IDs deleted from storage backend
        chunks_to_create: Number of files requiring (re-)indexing
    """

    files_added: list[str]
    files_changed: list[str]
    files_deleted: list[str]
    files_unchanged: list[str]
    chunks_evicted: int
    chunks_to_create: int


class ManifestTracker:
    """Tracks per-folder file manifests for incremental indexing.

    Stores one JSON file per indexed folder at:
        <manifests_dir>/<sha256(folder_path)>.json

    Uses atomic write (temp + Path.replace()) for crash safety and
    a single asyncio.Lock for all manifest operations.

    Mirrors the FolderManager async/lock/atomic-write pattern established
    in Phase 12.
    """

    def __init__(self, manifests_dir: Path) -> None:
        """Initialize ManifestTracker.

        Args:
            manifests_dir: Directory for manifest file storage
        """
        self.manifests_dir = manifests_dir
        self._lock = asyncio.Lock()

    def _manifest_path(self, folder_path: str) -> Path:
        """Compute the manifest file path for a given folder.

        Uses SHA-256 of the folder path string as the filename to avoid
        path-separator issues and keep the manifests directory flat.

        Args:
            folder_path: Absolute path to the indexed folder

        Returns:
            Path to the manifest JSON file
        """
        key = hashlib.sha256(folder_path.encode()).hexdigest()
        return self.manifests_dir / f"{key}.json"

    async def load(self, folder_path: str) -> FolderManifest | None:
        """Load manifest for folder, returns None if not present.

        Args:
            folder_path: Absolute path to the indexed folder

        Returns:
            FolderManifest if manifest file exists, None otherwise

        Raises:
            OSError: If manifest file exists but cannot be read
            json.JSONDecodeError: If manifest file contains invalid JSON
        """
        path = self._manifest_path(folder_path)
        if not path.exists():
            return None
        return await asyncio.to_thread(self._read_manifest, path, folder_path)

    async def save(self, manifest: FolderManifest) -> None:
        """Atomically persist manifest to disk.

        Uses temp file + Path.replace() for crash safety. Under lock
        to prevent concurrent writes to the same manifest.

        Args:
            manifest: FolderManifest to persist

        Raises:
            OSError: If manifest cannot be written
        """
        async with self._lock:
            await asyncio.to_thread(self._write_manifest, manifest)

    async def delete(self, folder_path: str) -> None:
        """Remove manifest file.

        Used on folder removal or force reindex. No-op if manifest
        does not exist.

        Args:
            folder_path: Absolute path to the indexed folder

        Raises:
            OSError: If manifest file exists but cannot be deleted
        """
        path = self._manifest_path(folder_path)
        async with self._lock:
            if path.exists():
                await asyncio.to_thread(path.unlink)
                logger.debug(f"Deleted manifest for {folder_path}")

    def _read_manifest(self, path: Path, folder_path: str) -> FolderManifest:
        """Deserialize manifest from JSON file (synchronous).

        Args:
            path: Path to the manifest JSON file
            folder_path: Folder path for the manifest

        Returns:
            Deserialized FolderManifest

        Raises:
            OSError: If file cannot be read
            json.JSONDecodeError: If file contains invalid JSON
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        files = {
            fp: FileRecord(
                checksum=rec["checksum"],
                mtime=rec["mtime"],
                chunk_ids=rec["chunk_ids"],
            )
            for fp, rec in data.get("files", {}).items()
        }
        return FolderManifest(folder_path=folder_path, files=files)

    def _write_manifest(self, manifest: FolderManifest) -> None:
        """Serialize and atomically write manifest to JSON file (synchronous).

        Creates manifests directory if it does not exist. Uses a temporary
        file and atomic rename (Path.replace()) for crash safety.

        Must be called under self._lock.

        Args:
            manifest: FolderManifest to serialize

        Raises:
            OSError: If manifest cannot be written
        """
        self.manifests_dir.mkdir(parents=True, exist_ok=True)
        path = self._manifest_path(manifest.folder_path)
        temp_path = path.with_suffix(".json.tmp")
        data = {
            "folder_path": manifest.folder_path,
            "files": {
                fp: {
                    "checksum": rec.checksum,
                    "mtime": rec.mtime,
                    "chunk_ids": rec.chunk_ids,
                }
                for fp, rec in manifest.files.items()
            },
        }
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        temp_path.replace(path)  # POSIX atomic rename


def compute_file_checksum(file_path: str) -> str:
    """Compute SHA-256 hex digest of file contents.

    Reads the file in 64 KB chunks to handle large files without
    loading the entire file into memory.

    Args:
        file_path: Absolute path to the file

    Returns:
        SHA-256 hex digest string (64 hex characters)

    Raises:
        OSError: If file cannot be read
    """
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
