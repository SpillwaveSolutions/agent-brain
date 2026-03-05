"""Unit tests for ContentInjector service (INJECT-01 through INJECT-07)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from agent_brain_server.indexing.chunking import ChunkMetadata, TextChunk
from agent_brain_server.services.content_injector import ContentInjector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_chunk(extra: dict[str, Any] | None = None) -> TextChunk:
    """Create a minimal TextChunk for testing."""
    metadata = ChunkMetadata(
        chunk_id="chunk_001",
        source="/some/file.md",
        file_name="file.md",
        chunk_index=0,
        total_chunks=1,
        source_type="doc",
        extra=extra or {},
    )
    return TextChunk(
        chunk_id="chunk_001",
        text="Hello world",
        source="/some/file.md",
        chunk_index=0,
        total_chunks=1,
        token_count=2,
        metadata=metadata,
    )


def _write_script(tmp_path: Path, content: str) -> Path:
    """Write a Python script to a temp file and return its path."""
    script = tmp_path / "inject.py"
    script.write_text(content, encoding="utf-8")
    return script


def _write_meta(tmp_path: Path, data: Any) -> Path:
    """Write JSON metadata to a temp file and return its path."""
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps(data), encoding="utf-8")
    return meta


# ---------------------------------------------------------------------------
# _load_script — happy path
# ---------------------------------------------------------------------------


def test_load_script_happy_path(tmp_path: Path) -> None:
    """Script is loaded and process_chunk is called correctly."""
    script = _write_script(
        tmp_path,
        "def process_chunk(chunk):\n    chunk['added'] = True\n    return chunk\n",
    )
    injector = ContentInjector(script_path=script)
    result = injector.apply({"source": "test"})
    assert result["added"] is True
    assert result["source"] == "test"


# ---------------------------------------------------------------------------
# _load_script — error cases
# ---------------------------------------------------------------------------


def test_load_script_file_not_found(tmp_path: Path) -> None:
    """FileNotFoundError raised when script does not exist."""
    missing = tmp_path / "nonexistent.py"
    with pytest.raises(FileNotFoundError, match="nonexistent.py"):
        ContentInjector(script_path=missing)


def test_load_script_missing_process_chunk(tmp_path: Path) -> None:
    """AttributeError raised when script has no process_chunk."""
    script = _write_script(tmp_path, "x = 1\n")
    with pytest.raises(AttributeError, match="process_chunk"):
        ContentInjector(script_path=script)


def test_load_script_non_callable_process_chunk(tmp_path: Path) -> None:
    """TypeError raised when process_chunk attribute is not callable."""
    script = _write_script(tmp_path, "process_chunk = 42\n")
    with pytest.raises(TypeError, match="callable"):
        ContentInjector(script_path=script)


# ---------------------------------------------------------------------------
# from_folder_metadata_file — happy path
# ---------------------------------------------------------------------------


def test_from_folder_metadata_file_happy_path(tmp_path: Path) -> None:
    """Metadata from JSON file is merged into chunks."""
    meta = _write_meta(tmp_path, {"project": "myproject", "team": "alpha"})
    injector = ContentInjector.from_folder_metadata_file(meta)
    result = injector.apply({"source": "test"})
    assert result["project"] == "myproject"
    assert result["team"] == "alpha"


# ---------------------------------------------------------------------------
# from_folder_metadata_file — error cases
# ---------------------------------------------------------------------------


def test_from_folder_metadata_file_not_found(tmp_path: Path) -> None:
    """FileNotFoundError raised when metadata file does not exist."""
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError, match="missing.json"):
        ContentInjector.from_folder_metadata_file(missing)


def test_from_folder_metadata_file_non_dict_json(tmp_path: Path) -> None:
    """TypeError raised when JSON root is not a dict."""
    meta = _write_meta(tmp_path, ["a", "b", "c"])
    with pytest.raises(TypeError, match="dict"):
        ContentInjector.from_folder_metadata_file(meta)


# ---------------------------------------------------------------------------
# apply — exception handling (INJECT-05)
# ---------------------------------------------------------------------------


def test_apply_script_exception_logs_warning_returns_original(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Per-chunk script exception is caught, warning logged, original chunk returned."""
    script = _write_script(
        tmp_path,
        "def process_chunk(chunk):\n    raise RuntimeError('boom')\n",
    )
    injector = ContentInjector(script_path=script)
    chunk = {"source": "test", "chunk_index": 0}

    with caplog.at_level(logging.WARNING):
        result = injector.apply(chunk.copy())

    # Should still have original keys (script error was swallowed)
    assert result["source"] == "test"
    assert any("boom" in record.message for record in caplog.records)


def test_apply_script_returns_non_dict_logs_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """process_chunk returning non-dict logs warning and keeps original chunk."""
    script = _write_script(
        tmp_path,
        "def process_chunk(chunk):\n    return 'not a dict'\n",
    )
    injector = ContentInjector(script_path=script)
    chunk = {"source": "test"}

    with caplog.at_level(logging.WARNING):
        result = injector.apply(chunk.copy())

    assert result["source"] == "test"
    assert any("expected dict" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# _validate_metadata_values
# ---------------------------------------------------------------------------


def test_validate_metadata_values_strips_list_and_dict() -> None:
    """Lists and dicts are stripped; scalars and None are kept."""
    injector = ContentInjector()
    chunk: dict[str, Any] = {
        "text": "hello",
        "count": 5,
        "score": 0.9,
        "flag": True,
        "empty": None,
        "bad_list": [1, 2, 3],
        "bad_dict": {"a": 1},
    }
    result = injector._validate_metadata_values(chunk)
    assert "text" in result
    assert "count" in result
    assert "score" in result
    assert "flag" in result
    assert "empty" in result
    assert "bad_list" not in result
    assert "bad_dict" not in result


def test_validate_metadata_values_warns_on_non_scalar(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A warning is logged for each non-scalar value stripped."""
    injector = ContentInjector()
    with caplog.at_level(logging.WARNING):
        injector._validate_metadata_values({"bad": [1, 2]})

    assert any("bad" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# build — factory
# ---------------------------------------------------------------------------


def test_build_returns_none_when_both_paths_none() -> None:
    """build() returns None when both script_path and metadata_path are None."""
    result = ContentInjector.build(script_path=None, metadata_path=None)
    assert result is None


def test_build_creates_injector_with_both_script_and_metadata(
    tmp_path: Path,
) -> None:
    """build() wires both script and folder_metadata when both paths are given."""
    script = _write_script(
        tmp_path,
        "def process_chunk(chunk):\n    chunk['scripted'] = True\n    return chunk\n",
    )
    meta = _write_meta(tmp_path, {"env": "prod"})

    injector = ContentInjector.build(
        script_path=str(script), metadata_path=str(meta)
    )
    assert injector is not None

    result = injector.apply({"source": "x"})
    assert result["env"] == "prod"
    assert result["scripted"] is True


def test_build_with_only_metadata(tmp_path: Path) -> None:
    """build() creates injector with folder_metadata only."""
    meta = _write_meta(tmp_path, {"region": "us-west"})
    injector = ContentInjector.build(metadata_path=str(meta))
    assert injector is not None
    result = injector.apply({"source": "x"})
    assert result["region"] == "us-west"


def test_build_with_only_script(tmp_path: Path) -> None:
    """build() creates injector with script only."""
    script = _write_script(
        tmp_path,
        "def process_chunk(chunk):\n    chunk['tagged'] = 1\n    return chunk\n",
    )
    injector = ContentInjector.build(script_path=str(script))
    assert injector is not None
    result = injector.apply({"source": "x"})
    assert result["tagged"] == 1


# ---------------------------------------------------------------------------
# apply_to_chunks
# ---------------------------------------------------------------------------


def test_apply_to_chunks_updates_extra_for_new_keys(tmp_path: Path) -> None:
    """apply_to_chunks writes new keys to chunk.metadata.extra."""
    meta = _write_meta(tmp_path, {"project": "test", "priority": 1})
    injector = ContentInjector.from_folder_metadata_file(meta)

    chunk = _make_text_chunk()
    known_keys: set[str] = {
        "chunk_id", "source", "file_name", "chunk_index", "total_chunks",
        "source_type", "created_at",
    }

    count = injector.apply_to_chunks([chunk], known_keys)
    assert count == 1
    assert chunk.metadata.extra["project"] == "test"
    assert chunk.metadata.extra["priority"] == 1


def test_apply_to_chunks_does_not_overwrite_known_keys(tmp_path: Path) -> None:
    """apply_to_chunks does not write known schema keys into extra."""
    # Try to inject a value for 'source', which is a known key
    meta = _write_meta(tmp_path, {"source": "injected", "custom_tag": "hello"})
    injector = ContentInjector.from_folder_metadata_file(meta)

    chunk = _make_text_chunk()
    original_source = chunk.metadata.source
    known_keys: set[str] = {"chunk_id", "source", "file_name", "chunk_index",
                             "total_chunks", "source_type", "created_at"}

    injector.apply_to_chunks([chunk], known_keys)

    # 'source' must NOT be in extra (it's in known_keys)
    assert "source" not in chunk.metadata.extra
    # The original metadata.source must be unchanged
    assert chunk.metadata.source == original_source
    # 'custom_tag' (new key) should be in extra
    assert chunk.metadata.extra["custom_tag"] == "hello"


def test_apply_to_chunks_returns_zero_when_no_new_keys() -> None:
    """apply_to_chunks returns 0 when all injected keys are known keys."""
    # Inject only known-schema keys — nothing new ends up in extra
    injector = ContentInjector(
        folder_metadata={"source": "overridden"}  # known key
    )
    chunk = _make_text_chunk()
    known_keys: set[str] = {"chunk_id", "source", "file_name", "chunk_index",
                             "total_chunks", "source_type", "created_at"}
    count = injector.apply_to_chunks([chunk], known_keys)
    assert count == 0


# ---------------------------------------------------------------------------
# ChunkMetadata.to_dict() — injected keys survive serialization
# ---------------------------------------------------------------------------


def test_chunk_metadata_to_dict_includes_extra_keys() -> None:
    """Injected keys stored in extra survive to_dict() (confirms ChromaDB compat)."""
    metadata = ChunkMetadata(
        chunk_id="c1",
        source="/file.md",
        file_name="file.md",
        chunk_index=0,
        total_chunks=1,
        source_type="doc",
        extra={"project": "test", "priority": 1},
    )
    d = metadata.to_dict()
    assert d["project"] == "test"
    assert d["priority"] == 1
