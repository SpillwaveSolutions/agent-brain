"""Triplet snapshot manager for Kuzu graph store durability (Issue #166).

Provides periodic JSON snapshots of graph triplets so that a process kill
mid-indexing does not destroy previously-extracted work. Snapshots are
written atomically (tmp + os.replace) under
``<persist_dir>/snapshots/snapshot-<ISO8601>.json`` and rotated to keep
the K most recent.

After the defensive recovery path in ``graph_store._initialize_kuzu_store``
renames a corrupted ``kuzu_db``, the latest valid snapshot is replayed
into the fresh database — preserving API spend on previously-extracted
triplets.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
SNAPSHOT_DIR_NAME = "snapshots"
SNAPSHOT_FILE_PREFIX = "snapshot-"
SNAPSHOT_FILE_SUFFIX = ".json"
DEFAULT_KEEP = 3

# Filename pattern: snapshot-2026-05-26T21-05-32Z.json (colons replaced for
# filesystem safety) plus an optional ``-NNN`` monotonic suffix for clock
# collisions within the same second.
_FILENAME_RE = re.compile(
    r"^snapshot-(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z)"
    r"(?:-(?P<seq>\d{3}))?\.json$"
)


@dataclass(frozen=True)
class SnapshotTriplet:
    """A single graph triplet, serializable to/from snapshot JSON."""

    subject: str
    predicate: str
    object: str
    subject_type: str | None = None
    object_type: str | None = None
    source_chunk_id: str | None = None


def _timestamp_for_filename(now: datetime | None = None) -> str:
    """Return an ISO8601-ish UTC timestamp safe for filenames."""
    moment = now or datetime.now(timezone.utc)
    # Replace ':' with '-' so the filename is portable across filesystems.
    return moment.strftime("%Y-%m-%dT%H-%M-%SZ")


class GraphSnapshotManager:
    """Writes, lists, and rotates triplet snapshots for the graph store.

    Snapshots live under ``<persist_dir>/snapshots/`` as JSON files. The
    manager is intentionally backend-agnostic — it operates on plain
    ``SnapshotTriplet`` records and never touches Kuzu directly.

    Attributes:
        persist_dir: The graph store's persist directory (e.g.
            ``.agent-brain/data/graph_index``). The snapshots subdirectory
            is created lazily on first write.
    """

    def __init__(self, persist_dir: Path) -> None:
        self.persist_dir = Path(persist_dir)

    @property
    def snapshot_dir(self) -> Path:
        """Path of the snapshots subdirectory (may not yet exist)."""
        return self.persist_dir / SNAPSHOT_DIR_NAME

    def write(
        self,
        triplets: list[SnapshotTriplet],
        source_job_id: str | None = None,
        kuzu_version: str | None = None,
        now: datetime | None = None,
    ) -> Path:
        """Write a snapshot atomically and return its path.

        Args:
            triplets: Triplets to snapshot. May be empty (an empty snapshot
                still writes — it represents "we got here with zero
                triplets" which is useful for restore-from-empty).
            source_job_id: Optional indexing job id for attribution.
            kuzu_version: Optional Kuzu version string for forensic context.
            now: Override timestamp (testing).

        Returns:
            Path of the written snapshot file.

        Raises:
            OSError: If the write fails (disk full, permission, etc.).
        """
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        moment = now or datetime.now(timezone.utc)
        base_name = (
            f"{SNAPSHOT_FILE_PREFIX}{_timestamp_for_filename(moment)}"
            f"{SNAPSHOT_FILE_SUFFIX}"
        )
        target = self.snapshot_dir / base_name

        # Clock-collision tie-break: if a snapshot already exists for this
        # exact second, append a monotonic 3-digit suffix.
        if target.exists():
            for seq in range(1, 1000):
                candidate = self.snapshot_dir / (
                    f"{SNAPSHOT_FILE_PREFIX}{_timestamp_for_filename(moment)}"
                    f"-{seq:03d}{SNAPSHOT_FILE_SUFFIX}"
                )
                if not candidate.exists():
                    target = candidate
                    break

        payload = {
            "schema_version": SCHEMA_VERSION,
            "created_at": moment.isoformat(),
            "kuzu_version": kuzu_version,
            "source_job_id": source_job_id,
            "triplet_count": len(triplets),
            "triplets": [asdict(t) for t in triplets],
        }

        tmp = target.with_suffix(target.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)

        logger.info(
            "graph_snapshot.write: wrote snapshot",
            extra={
                "path": str(target),
                "triplet_count": len(triplets),
                "source_job_id": source_job_id,
            },
        )
        return target

    def list_snapshots(self) -> list[Path]:
        """Return snapshot paths sorted newest-first.

        Sort key is (mtime, filename) — mtime is the primary signal so a
        snapshot written milliseconds after another is correctly newer,
        even when both share the same ISO-second filename stamp. Filename
        breaks ties for determinism in tests that pre-create files.
        """
        if not self.snapshot_dir.is_dir():
            return []
        candidates = [
            p
            for p in self.snapshot_dir.iterdir()
            if p.is_file() and _FILENAME_RE.match(p.name)
        ]
        candidates.sort(key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
        return candidates

    def latest(self) -> Path | None:
        """Return the newest snapshot path or None if none exist."""
        snaps = self.list_snapshots()
        return snaps[0] if snaps else None

    def load(self, path: Path) -> list[SnapshotTriplet]:
        """Load and parse a snapshot file.

        Args:
            path: Snapshot file to load.

        Returns:
            List of triplets parsed from the snapshot.

        Raises:
            OSError: If the file cannot be read.
            ValueError: If the file is not a valid snapshot (bad JSON,
                missing fields, unknown schema version). Callers handle
                this to fall back to an older snapshot.
        """
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Snapshot {path} is not valid JSON") from exc

        schema = payload.get("schema_version")
        if schema != SCHEMA_VERSION:
            raise ValueError(
                f"Snapshot {path} has unsupported schema_version={schema} "
                f"(expected {SCHEMA_VERSION})"
            )

        raw_triplets = payload.get("triplets")
        if not isinstance(raw_triplets, list):
            raise ValueError(f"Snapshot {path} is missing 'triplets' list")

        out: list[SnapshotTriplet] = []
        for entry in raw_triplets:
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Snapshot {path} contains non-dict triplet: {entry!r}"
                )
            try:
                out.append(
                    SnapshotTriplet(
                        subject=entry["subject"],
                        predicate=entry["predicate"],
                        object=entry["object"],
                        subject_type=entry.get("subject_type"),
                        object_type=entry.get("object_type"),
                        source_chunk_id=entry.get("source_chunk_id"),
                    )
                )
            except KeyError as exc:
                raise ValueError(
                    f"Snapshot {path} triplet missing required key: {exc}"
                ) from exc

        return out

    def load_latest_valid(self) -> tuple[Path, list[SnapshotTriplet]] | None:
        """Load the newest valid snapshot, skipping corrupted ones.

        Walks newest-to-oldest, returning the first that parses cleanly.
        Corrupted snapshots are renamed with a ``.corrupted`` suffix so the
        next call doesn't re-encounter them, and a WARN is logged.

        Returns:
            (path, triplets) for the loaded snapshot, or None if no valid
            snapshot exists.
        """
        for path in self.list_snapshots():
            try:
                triplets = self.load(path)
                return path, triplets
            except (ValueError, OSError) as exc:
                logger.warning(
                    "graph_snapshot.load_latest_valid: skipping corrupted "
                    "snapshot %s (%s)",
                    path,
                    exc,
                )
                corrupted = path.with_suffix(path.suffix + ".corrupted")
                try:
                    path.rename(corrupted)
                except OSError as rename_exc:
                    logger.warning(
                        "graph_snapshot.load_latest_valid: could not rename "
                        "corrupted snapshot %s: %s",
                        path,
                        rename_exc,
                    )
        return None

    def rotate(self, keep: int = DEFAULT_KEEP) -> int:
        """Delete older snapshots, keeping the ``keep`` most recent.

        Args:
            keep: Number of snapshots to retain. Must be >= 1.

        Returns:
            Number of snapshots deleted.
        """
        if keep < 1:
            raise ValueError(f"keep must be >= 1, got {keep}")
        snaps = self.list_snapshots()
        to_delete = snaps[keep:]
        for path in to_delete:
            try:
                path.unlink()
            except OSError as exc:
                logger.warning(
                    "graph_snapshot.rotate: failed to delete %s: %s", path, exc
                )
        if to_delete:
            logger.debug(
                "graph_snapshot.rotate: kept %d, deleted %d", keep, len(to_delete)
            )
        return len(to_delete)
