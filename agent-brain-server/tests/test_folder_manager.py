"""Tests for FolderManager service."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from agent_brain_server.services.folder_manager import FolderManager, FolderRecord


@pytest.mark.asyncio
async def test_initialize_empty_dir(tmp_path: Path) -> None:
    """Test initializing FolderManager with no existing JSONL file."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    folders = await manager.list_folders()
    assert folders == []


@pytest.mark.asyncio
async def test_initialize_with_existing_jsonl(tmp_path: Path) -> None:
    """Test initializing FolderManager with existing JSONL data."""
    # Create JSONL file with test data
    jsonl_path = tmp_path / "indexed_folders.jsonl"
    test_data = [
        {
            "folder_path": "/path/to/folder1",
            "chunk_count": 10,
            "last_indexed": "2026-01-01T00:00:00Z",
            "chunk_ids": ["chunk1", "chunk2"],
        },
        {
            "folder_path": "/path/to/folder2",
            "chunk_count": 20,
            "last_indexed": "2026-01-02T00:00:00Z",
            "chunk_ids": ["chunk3", "chunk4"],
        },
    ]

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for record in test_data:
            f.write(json.dumps(record) + "\n")

    # Initialize and verify
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    folders = await manager.list_folders()
    assert len(folders) == 2
    assert folders[0].folder_path == "/path/to/folder1"
    assert folders[0].chunk_count == 10
    assert folders[1].folder_path == "/path/to/folder2"
    assert folders[1].chunk_count == 20


@pytest.mark.asyncio
async def test_add_folder_normalizes_path(tmp_path: Path) -> None:
    """Test that add_folder normalizes paths via Path.resolve()."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    # Add folder with relative path
    record = await manager.add_folder(
        folder_path="./test/../test/folder",
        chunk_count=5,
        chunk_ids=["chunk1", "chunk2"],
    )

    # Verify path is normalized to absolute
    assert record.folder_path == str(Path("./test/../test/folder").resolve())

    # Verify can retrieve with different path form
    retrieved = await manager.get_folder("test/folder")
    assert retrieved is not None
    assert retrieved.folder_path == record.folder_path


@pytest.mark.asyncio
async def test_add_folder_updates_existing(tmp_path: Path) -> None:
    """Test that add_folder is idempotent (updates existing record)."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    folder_path = str(tmp_path / "test_folder")

    # Add folder first time
    record1 = await manager.add_folder(
        folder_path=folder_path,
        chunk_count=10,
        chunk_ids=["chunk1", "chunk2"],
    )

    # Add again with different data
    record2 = await manager.add_folder(
        folder_path=folder_path,
        chunk_count=20,
        chunk_ids=["chunk3", "chunk4", "chunk5"],
    )

    # Verify updated
    assert record2.chunk_count == 20
    assert len(record2.chunk_ids) == 3
    assert record2.last_indexed > record1.last_indexed

    # Verify only one record exists
    folders = await manager.list_folders()
    assert len(folders) == 1


@pytest.mark.asyncio
async def test_remove_folder_returns_record(tmp_path: Path) -> None:
    """Test that remove_folder returns the removed record."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    folder_path = str(tmp_path / "test_folder")

    # Add folder
    await manager.add_folder(
        folder_path=folder_path,
        chunk_count=10,
        chunk_ids=["chunk1"],
    )

    # Remove and verify return value
    removed = await manager.remove_folder(folder_path)
    assert removed is not None
    assert removed.folder_path == str(Path(folder_path).resolve())
    assert removed.chunk_count == 10

    # Verify removed from list
    folders = await manager.list_folders()
    assert len(folders) == 0


@pytest.mark.asyncio
async def test_remove_folder_nonexistent_returns_none(tmp_path: Path) -> None:
    """Test that remove_folder returns None for nonexistent folder."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    removed = await manager.remove_folder("/nonexistent/path")
    assert removed is None


@pytest.mark.asyncio
async def test_list_folders_returns_sorted(tmp_path: Path) -> None:
    """Test that list_folders returns folders sorted by path."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    # Add folders in non-alphabetical order
    await manager.add_folder("/path/c", 1, ["chunk1"])
    await manager.add_folder("/path/a", 2, ["chunk2"])
    await manager.add_folder("/path/b", 3, ["chunk3"])

    folders = await manager.list_folders()
    assert len(folders) == 3
    assert folders[0].folder_path == "/path/a"
    assert folders[1].folder_path == "/path/b"
    assert folders[2].folder_path == "/path/c"


@pytest.mark.asyncio
async def test_persistence_survives_restart(tmp_path: Path) -> None:
    """Test that folder data persists across FolderManager instances."""
    folder_path = str(tmp_path / "test_folder")

    # Create first manager and add data
    manager1 = FolderManager(state_dir=tmp_path)
    await manager1.initialize()
    await manager1.add_folder(folder_path, 10, ["chunk1", "chunk2"])

    # Create second manager and verify data survives
    manager2 = FolderManager(state_dir=tmp_path)
    await manager2.initialize()

    folders = await manager2.list_folders()
    assert len(folders) == 1
    assert folders[0].folder_path == str(Path(folder_path).resolve())
    assert folders[0].chunk_count == 10
    assert folders[0].chunk_ids == ["chunk1", "chunk2"]


@pytest.mark.asyncio
async def test_clear_removes_all_and_deletes_file(tmp_path: Path) -> None:
    """Test that clear removes all records and deletes JSONL file."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    # Add some data
    await manager.add_folder("/path/1", 10, ["chunk1"])
    await manager.add_folder("/path/2", 20, ["chunk2"])

    # Verify JSONL file exists
    assert manager.jsonl_path.exists()

    # Clear
    await manager.clear()

    # Verify cache is empty
    folders = await manager.list_folders()
    assert len(folders) == 0

    # Verify JSONL file is deleted
    assert not manager.jsonl_path.exists()


@pytest.mark.asyncio
async def test_clear_on_empty_manager(tmp_path: Path) -> None:
    """Test that clear works on empty manager (no JSONL file)."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    # Clear without adding data
    await manager.clear()

    # Should not raise error
    folders = await manager.list_folders()
    assert len(folders) == 0


@pytest.mark.asyncio
async def test_concurrent_adds_dont_corrupt(tmp_path: Path) -> None:
    """Test that concurrent add_folder calls don't corrupt data."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    # Add 10 folders concurrently
    tasks = [
        manager.add_folder(f"/path/{i}", i, [f"chunk{i}"])
        for i in range(10)
    ]
    await asyncio.gather(*tasks)

    # Verify all were added
    folders = await manager.list_folders()
    assert len(folders) == 10

    # Verify JSONL file is valid
    with open(manager.jsonl_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 10
        for line in lines:
            # Should be valid JSON
            data = json.loads(line)
            assert "folder_path" in data
            assert "chunk_count" in data


@pytest.mark.asyncio
async def test_load_jsonl_handles_corrupt_lines(tmp_path: Path) -> None:
    """Test that corrupt JSONL lines are skipped with warnings."""
    jsonl_path = tmp_path / "indexed_folders.jsonl"

    # Create JSONL with mix of valid and corrupt lines
    with open(jsonl_path, "w", encoding="utf-8") as f:
        # Valid line
        f.write(json.dumps({
            "folder_path": "/valid/path",
            "chunk_count": 10,
            "last_indexed": "2026-01-01T00:00:00Z",
            "chunk_ids": ["chunk1"],
        }) + "\n")
        # Corrupt JSON
        f.write("{invalid json\n")
        # Missing required field
        f.write(json.dumps({"folder_path": "/incomplete"}) + "\n")
        # Empty line
        f.write("\n")
        # Another valid line
        f.write(json.dumps({
            "folder_path": "/valid/path2",
            "chunk_count": 20,
            "last_indexed": "2026-01-02T00:00:00Z",
            "chunk_ids": ["chunk2"],
        }) + "\n")

    # Initialize and verify only valid records loaded
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    folders = await manager.list_folders()
    assert len(folders) == 2
    assert folders[0].folder_path == "/valid/path"
    assert folders[1].folder_path == "/valid/path2"


@pytest.mark.asyncio
async def test_get_folder_normalizes_path(tmp_path: Path) -> None:
    """Test that get_folder normalizes the lookup path."""
    manager = FolderManager(state_dir=tmp_path)
    await manager.initialize()

    # Add folder with absolute path (with redundant segments)
    folder_path = str(tmp_path / "test_folder")
    await manager.add_folder(folder_path, 10, ["chunk1"])

    # Get with equivalent absolute path (with redundant ./ prefix normalization)
    # Path.resolve() normalizes /some/path/./test_folder -> /some/path/test_folder
    redundant_path = str(tmp_path) + "/./test_folder"
    retrieved = await manager.get_folder(redundant_path)
    assert retrieved is not None
    assert retrieved.chunk_count == 10
