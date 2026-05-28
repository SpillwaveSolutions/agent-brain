"""Phase 2 TDD: RuntimeState gains an optional ``socket_path`` field.

Maps to plan §12.3 acceptance #4 — "RuntimeState.socket_path is present when
``--uds``, absent (and old runtime.json files still parse) otherwise."

These tests will FAIL until Phase 2 adds the field. That's the RED step.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_brain_server.runtime import RuntimeState, read_runtime, write_runtime


class TestSocketPathField:
    """The new optional ``socket_path`` attribute on RuntimeState."""

    def test_default_is_none(self) -> None:
        """When --uds is not used, socket_path must default to None.

        This keeps existing call sites (any current code constructing
        RuntimeState without socket_path) backwards-compatible.
        """
        state = RuntimeState()
        assert state.socket_path is None

    def test_accepts_string_path(self) -> None:
        """A string path round-trips through the model unchanged."""
        sock = "/Users/me/proj/.agent-brain/agent-brain.sock"
        state = RuntimeState(socket_path=sock)
        assert state.socket_path == sock

    def test_rejects_non_string_path(self) -> None:
        """Pydantic should reject non-string types so JSON round-trip is safe."""
        with pytest.raises(ValidationError):
            RuntimeState(socket_path=12345)  # type: ignore[arg-type]

    def test_serializes_field_in_json(self) -> None:
        """Field must round-trip through ``model_dump_json``."""
        sock = "/tmp/agent-brain-abcd1234.sock"
        state = RuntimeState(socket_path=sock)
        data = json.loads(state.model_dump_json())
        assert data["socket_path"] == sock

    def test_serializes_null_when_absent(self) -> None:
        """When socket_path is None, the JSON must still include the key
        (or omit it consistently). Pydantic default: include as null."""
        state = RuntimeState()
        data = json.loads(state.model_dump_json())
        assert data.get("socket_path") is None


class TestBackwardsCompat:
    """An old runtime.json (written by pre-v1.1 servers) must still load."""

    def test_load_old_runtime_json_without_socket_path(self, tmp_path: Path) -> None:
        """A runtime.json from a previous release lacks ``socket_path``.
        Reading it must not raise — the field is optional."""
        runtime_path = tmp_path / "runtime.json"
        runtime_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "mode": "project",
                    "project_root": "/some/path",
                    "instance_id": "abc123def456",
                    "base_url": "http://127.0.0.1:8000",
                    "bind_host": "127.0.0.1",
                    "port": 8000,
                    "pid": 99999,
                    "started_at": "2026-05-26T12:00:00+00:00",
                }
            )
        )
        state = read_runtime(tmp_path)
        assert state is not None
        assert state.socket_path is None
        assert state.port == 8000  # other fields unaffected

    def test_write_then_read_round_trips_socket_path(self, tmp_path: Path) -> None:
        """Round-trip a runtime.json that contains the new field."""
        sock = "/tmp/agent-brain-deadbeef.sock"
        written = RuntimeState(
            port=9999,
            pid=12345,
            base_url="http://127.0.0.1:9999",
            socket_path=sock,
        )
        write_runtime(tmp_path, written)

        loaded = read_runtime(tmp_path)
        assert loaded is not None
        assert loaded.socket_path == sock
        assert loaded.port == 9999
