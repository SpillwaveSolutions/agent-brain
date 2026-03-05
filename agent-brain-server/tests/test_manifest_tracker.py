"""Unit tests for ManifestTracker, FileRecord, FolderManifest, compute_file_checksum."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import pytest_asyncio  # noqa: F401 — used by pytest-asyncio fixtures

from agent_brain_server.services.manifest_tracker import (
    FileRecord,
    FolderManifest,
    ManifestTracker,
    compute_file_checksum,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_file_record(
    checksum: str = "abc123",
    mtime: float = 1700000000.0,
    chunk_ids: list[str] | None = None,
) -> FileRecord:
    return FileRecord(
        checksum=checksum,
        mtime=mtime,
        chunk_ids=chunk_ids if chunk_ids is not None else ["chunk-1", "chunk-2"],
    )


def make_manifest(
    folder_path: str = "/tmp/test_folder",
    files: dict[str, FileRecord] | None = None,
) -> FolderManifest:
    if files is None:
        files = {
            "/tmp/test_folder/a.py": make_file_record(
                checksum="aaa", mtime=1.0, chunk_ids=["c1"]
            ),
            "/tmp/test_folder/b.py": make_file_record(
                checksum="bbb", mtime=2.0, chunk_ids=["c2", "c3"]
            ),
            "/tmp/test_folder/c.md": make_file_record(
                checksum="ccc", mtime=3.0, chunk_ids=["c4"]
            ),
        }
    return FolderManifest(folder_path=folder_path, files=files)


# ---------------------------------------------------------------------------
# ManifestTracker.load — returns None for missing manifest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_returns_none_for_missing_manifest(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path / "manifests")
    result = await tracker.load("/nonexistent/folder")
    assert result is None


# ---------------------------------------------------------------------------
# ManifestTracker.save + load — round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_load_round_trip(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path / "manifests")
    folder_path = "/home/user/project"
    manifest = make_manifest(folder_path=folder_path)

    await tracker.save(manifest)
    loaded = await tracker.load(folder_path)

    assert loaded is not None
    assert loaded.folder_path == folder_path
    assert set(loaded.files.keys()) == set(manifest.files.keys())

    for fp, expected in manifest.files.items():
        actual = loaded.files[fp]
        assert actual.checksum == expected.checksum
        assert actual.mtime == expected.mtime
        assert actual.chunk_ids == expected.chunk_ids


@pytest.mark.asyncio
async def test_save_and_load_empty_manifest(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path / "manifests")
    folder_path = "/empty/folder"
    manifest = FolderManifest(folder_path=folder_path, files={})

    await tracker.save(manifest)
    loaded = await tracker.load(folder_path)

    assert loaded is not None
    assert loaded.folder_path == folder_path
    assert loaded.files == {}


# ---------------------------------------------------------------------------
# ManifestTracker.delete — removes the manifest file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_removes_manifest_file(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path / "manifests")
    folder_path = "/tmp/to_delete"
    manifest = make_manifest(folder_path=folder_path)

    await tracker.save(manifest)
    manifest_file = tracker._manifest_path(folder_path)
    assert manifest_file.exists()

    await tracker.delete(folder_path)
    assert not manifest_file.exists()


@pytest.mark.asyncio
async def test_delete_is_noop_for_missing_manifest(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path / "manifests")
    # Should not raise even when no manifest exists
    await tracker.delete("/folder/that/never/existed")


@pytest.mark.asyncio
async def test_load_returns_none_after_delete(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path / "manifests")
    folder_path = "/tmp/deleted_folder"
    manifest = make_manifest(folder_path=folder_path)

    await tracker.save(manifest)
    await tracker.delete(folder_path)

    result = await tracker.load(folder_path)
    assert result is None


# ---------------------------------------------------------------------------
# ManifestTracker._manifest_path — deterministic SHA-256 based path
# ---------------------------------------------------------------------------


def test_manifest_path_is_deterministic(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path)
    folder = "/consistent/path/to/folder"
    path1 = tracker._manifest_path(folder)
    path2 = tracker._manifest_path(folder)
    assert path1 == path2


def test_manifest_path_uses_sha256(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path)
    folder = "/some/folder"
    expected_key = hashlib.sha256(folder.encode()).hexdigest()
    path = tracker._manifest_path(folder)
    assert path.name == f"{expected_key}.json"
    assert path.parent == tmp_path


def test_manifest_path_differs_for_different_folders(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path)
    path_a = tracker._manifest_path("/folder/a")
    path_b = tracker._manifest_path("/folder/b")
    assert path_a != path_b


# ---------------------------------------------------------------------------
# compute_file_checksum — correct SHA-256 for known content
# ---------------------------------------------------------------------------


def test_compute_file_checksum_known_content(tmp_path: Path) -> None:
    content = b"hello agent brain"
    expected = hashlib.sha256(content).hexdigest()

    test_file = tmp_path / "sample.txt"
    test_file.write_bytes(content)

    result = compute_file_checksum(str(test_file))
    assert result == expected


def test_compute_file_checksum_empty_file(tmp_path: Path) -> None:
    test_file = tmp_path / "empty.txt"
    test_file.write_bytes(b"")
    expected = hashlib.sha256(b"").hexdigest()
    result = compute_file_checksum(str(test_file))
    assert result == expected


def test_compute_file_checksum_large_file(tmp_path: Path) -> None:
    """Verify checksum handles files larger than a single 64KB chunk."""
    content = b"x" * (65536 * 3 + 100)  # Three full chunks + partial
    expected = hashlib.sha256(content).hexdigest()

    test_file = tmp_path / "large.bin"
    test_file.write_bytes(content)

    result = compute_file_checksum(str(test_file))
    assert result == expected


def test_compute_file_checksum_is_deterministic(tmp_path: Path) -> None:
    test_file = tmp_path / "det.txt"
    test_file.write_bytes(b"deterministic content")
    result1 = compute_file_checksum(str(test_file))
    result2 = compute_file_checksum(str(test_file))
    assert result1 == result2


# ---------------------------------------------------------------------------
# Atomic write — no .tmp file left over after save
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_atomic_write_leaves_no_tmp_file(tmp_path: Path) -> None:
    manifests_dir = tmp_path / "manifests"
    tracker = ManifestTracker(manifests_dir=manifests_dir)
    folder_path = "/tmp/atomic_test"
    manifest = make_manifest(folder_path=folder_path)

    await tracker.save(manifest)

    # Verify the real file exists
    manifest_file = tracker._manifest_path(folder_path)
    assert manifest_file.exists()

    # Verify no temp file remains
    tmp_file = manifest_file.with_suffix(".json.tmp")
    assert not tmp_file.exists()


@pytest.mark.asyncio
async def test_save_creates_manifests_directory_if_missing(tmp_path: Path) -> None:
    nested_dir = tmp_path / "deep" / "nested" / "manifests"
    assert not nested_dir.exists()

    tracker = ManifestTracker(manifests_dir=nested_dir)
    await tracker.save(make_manifest())

    assert nested_dir.exists()


# ---------------------------------------------------------------------------
# Multiple manifests — different folders stored independently
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_manifests_stored_independently(tmp_path: Path) -> None:
    tracker = ManifestTracker(manifests_dir=tmp_path / "manifests")

    folder_a = "/project/a"
    folder_b = "/project/b"

    manifest_a = FolderManifest(
        folder_path=folder_a,
        files={"/project/a/file.py": make_file_record(checksum="aaa")},
    )
    manifest_b = FolderManifest(
        folder_path=folder_b,
        files={"/project/b/other.py": make_file_record(checksum="bbb")},
    )

    await tracker.save(manifest_a)
    await tracker.save(manifest_b)

    loaded_a = await tracker.load(folder_a)
    loaded_b = await tracker.load(folder_b)

    assert loaded_a is not None
    assert loaded_b is not None
    assert "/project/a/file.py" in loaded_a.files
    assert "/project/b/other.py" in loaded_b.files
    # Cross-contamination check
    assert "/project/b/other.py" not in loaded_a.files
    assert "/project/a/file.py" not in loaded_b.files
