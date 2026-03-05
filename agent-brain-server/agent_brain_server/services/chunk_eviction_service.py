"""Chunk eviction service for incremental indexing.

This module provides the ChunkEvictionService which computes the diff
between the current filesystem state and the prior folder manifest,
deletes stale chunks from the storage backend, and returns the set of
files that need (re-)indexing.

Satisfies: EVICT-02, EVICT-03, EVICT-04, EVICT-05, EVICT-07.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from .manifest_tracker import (
    EvictionSummary,
    ManifestTracker,
    compute_file_checksum,
)

if TYPE_CHECKING:
    from agent_brain_server.storage.protocol import StorageBackendProtocol

logger = logging.getLogger(__name__)


class ChunkEvictionService:
    """Computes manifest diff and evicts stale chunks from storage.

    Accepts a ManifestTracker and a StorageBackendProtocol. On each call
    to compute_diff_and_evict(), it:

    1. Loads the prior manifest (if any)
    2. Computes which files are added, changed, deleted, or unchanged
    3. Bulk-evicts chunk IDs for deleted and changed files
    4. Returns an EvictionSummary and the list of files to (re-)index

    Force mode skips the diff and evicts ALL prior chunks, returning all
    current files for full reindexing.
    """

    def __init__(
        self,
        manifest_tracker: ManifestTracker,
        storage_backend: StorageBackendProtocol,
    ) -> None:
        """Initialize ChunkEvictionService.

        Args:
            manifest_tracker: ManifestTracker for loading/deleting manifests
            storage_backend: Storage backend for bulk chunk deletion
        """
        self._manifest = manifest_tracker
        self._storage = storage_backend

    async def compute_diff_and_evict(
        self,
        folder_path: str,
        current_files: list[str],
        force: bool = False,
    ) -> tuple[EvictionSummary, list[str]]:
        """Compute manifest diff, evict stale chunks, return files to index.

        Args:
            folder_path: Absolute path to the indexed folder
            current_files: Absolute paths of files currently on disk
            force: If True, evict all prior chunks and return all current
                   files for full reindexing (bypasses diff)

        Returns:
            Tuple of (EvictionSummary, files_to_index) where files_to_index
            is the subset of current_files that need (re-)indexing.
        """
        if force:
            return await self._handle_force(folder_path, current_files)

        prior = await self._manifest.load(folder_path)
        if prior is None:
            # No manifest: treat all files as new (first-time indexing)
            logger.debug(
                f"No manifest found for {folder_path} — treating all "
                f"{len(current_files)} files as new"
            )
            return (
                EvictionSummary(
                    files_added=list(current_files),
                    files_changed=[],
                    files_deleted=[],
                    files_unchanged=[],
                    chunks_evicted=0,
                    chunks_to_create=len(current_files),
                ),
                list(current_files),
            )

        return await self._compute_incremental_diff(folder_path, current_files, prior)

    async def _handle_force(
        self,
        folder_path: str,
        current_files: list[str],
    ) -> tuple[EvictionSummary, list[str]]:
        """Handle force mode: evict all prior chunks, return all files.

        Args:
            folder_path: Absolute path to the indexed folder
            current_files: Absolute paths of files currently on disk

        Returns:
            Tuple of (EvictionSummary, current_files)
        """
        prior = await self._manifest.load(folder_path)
        chunks_evicted = 0
        if prior:
            all_prior_ids = [
                cid for rec in prior.files.values() for cid in rec.chunk_ids
            ]
            if all_prior_ids:
                chunks_evicted = await self._storage.delete_by_ids(all_prior_ids)
                logger.info(
                    f"Force mode: evicted {chunks_evicted} chunks for {folder_path}"
                )
            await self._manifest.delete(folder_path)

        return (
            EvictionSummary(
                files_added=list(current_files),
                files_changed=[],
                files_deleted=[],
                files_unchanged=[],
                chunks_evicted=chunks_evicted,
                chunks_to_create=len(current_files),
            ),
            list(current_files),
        )

    async def _compute_incremental_diff(
        self,
        folder_path: str,
        current_files: list[str],
        prior: object,
    ) -> tuple[EvictionSummary, list[str]]:
        """Compute incremental diff against prior manifest.

        Args:
            folder_path: Absolute path to the indexed folder
            current_files: Absolute paths of files currently on disk
            prior: Prior FolderManifest loaded from disk

        Returns:
            Tuple of (EvictionSummary, files_to_index)
        """
        from .manifest_tracker import FolderManifest

        assert isinstance(prior, FolderManifest)

        current_set = set(current_files)
        prior_set = set(prior.files.keys())

        files_deleted = list(prior_set - current_set)
        files_to_evict: list[str] = list(files_deleted)
        files_unchanged: list[str] = []
        files_added: list[str] = []
        files_changed: list[str] = []
        files_to_index: list[str] = []

        for fp in current_files:
            if fp not in prior_set:
                files_added.append(fp)
                files_to_index.append(fp)
            else:
                prior_rec = prior.files[fp]
                try:
                    current_mtime = os.stat(fp).st_mtime
                except OSError:
                    # File disappeared between scan and stat — treat as deleted
                    files_deleted.append(fp)
                    files_to_evict.append(fp)
                    continue

                if current_mtime == prior_rec.mtime:
                    # mtime unchanged — assume content unchanged (skip checksum)
                    files_unchanged.append(fp)
                else:
                    # mtime changed — verify by content checksum
                    current_checksum = await asyncio.to_thread(
                        compute_file_checksum, fp
                    )
                    if current_checksum == prior_rec.checksum:
                        # Content same despite mtime change (touch, git checkout etc.)
                        files_unchanged.append(fp)
                    else:
                        files_changed.append(fp)
                        files_to_evict.append(fp)
                        files_to_index.append(fp)

        # Bulk evict stale chunk IDs (deleted + changed files)
        ids_to_evict: list[str] = []
        for fp in files_to_evict:
            if fp in prior.files:
                ids_to_evict.extend(prior.files[fp].chunk_ids)

        chunks_evicted = 0
        if ids_to_evict:
            chunks_evicted = await self._storage.delete_by_ids(ids_to_evict)

        logger.info(
            f"Manifest diff for {folder_path}: "
            f"+{len(files_added)} added "
            f"~{len(files_changed)} changed "
            f"-{len(files_deleted)} deleted "
            f"={len(files_unchanged)} unchanged, "
            f"{chunks_evicted} chunks evicted"
        )

        return (
            EvictionSummary(
                files_added=files_added,
                files_changed=files_changed,
                files_deleted=files_deleted,
                files_unchanged=files_unchanged,
                chunks_evicted=chunks_evicted,
                chunks_to_create=len(files_to_index),
            ),
            files_to_index,
        )
