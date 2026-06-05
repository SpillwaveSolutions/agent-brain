"""Unit tests for runtime module."""

import json
import os
from unittest.mock import patch

from agent_brain_server.runtime import (
    RuntimeState,
    delete_runtime,
    read_runtime,
    validate_runtime,
    write_runtime,
)


class TestRuntimeState:
    """Tests for RuntimeState model."""

    def test_default_values(self):
        """Test RuntimeState has sensible defaults."""
        state = RuntimeState()
        assert state.schema_version == "1.0"
        assert state.mode == "project"
        assert state.bind_host == "127.0.0.1"
        assert state.port == 0
        assert state.pid == 0
        assert len(state.instance_id) == 12
        assert state.started_at  # Should have a timestamp

    def test_custom_values(self):
        """Test RuntimeState with custom values."""
        state = RuntimeState(
            mode="shared",
            project_root="/some/path",
            base_url="http://localhost:8000",
            port=8000,
            pid=12345,
            project_id="my-project",
        )
        assert state.mode == "shared"
        assert state.port == 8000
        assert state.pid == 12345
        assert state.project_id == "my-project"

    def test_unique_instance_ids(self):
        """Test each RuntimeState gets a unique instance_id."""
        state1 = RuntimeState()
        state2 = RuntimeState()
        assert state1.instance_id != state2.instance_id


class TestWriteRuntime:
    """Tests for write_runtime function."""

    def test_writes_json_file(self, tmp_path):
        """Test writing runtime state creates a JSON file."""
        state = RuntimeState(port=8080, pid=os.getpid())
        write_runtime(tmp_path, state)

        runtime_path = tmp_path / "runtime.json"
        assert runtime_path.exists()
        data = json.loads(runtime_path.read_text())
        assert data["port"] == 8080

    def test_creates_directory(self, tmp_path):
        """Test creates state directory if missing."""
        state_dir = tmp_path / "new" / "dir"
        state = RuntimeState()
        write_runtime(state_dir, state)

        assert state_dir.exists()
        assert (state_dir / "runtime.json").exists()

    def test_chmods_file_to_0600(self, tmp_path):
        """runtime.json may carry an api_key — must be owner-only (Issue #179)."""
        import stat

        state = RuntimeState(api_key="secret-token")
        write_runtime(tmp_path, state)

        runtime_path = tmp_path / "runtime.json"
        mode = stat.S_IMODE(runtime_path.stat().st_mode)
        assert mode == 0o600, f"runtime.json mode is {oct(mode)}, expected 0o600"

    def test_api_key_round_trips(self, tmp_path):
        """api_key field persists across write/read."""
        state = RuntimeState(api_key="secret-token", port=8080)
        write_runtime(tmp_path, state)

        result = read_runtime(tmp_path)
        assert result is not None
        assert result.api_key == "secret-token"

    def test_api_key_defaults_to_none(self, tmp_path):
        """Omitting api_key produces None (existing runtime.json files keep working)."""
        state = RuntimeState(port=8080)
        write_runtime(tmp_path, state)

        result = read_runtime(tmp_path)
        assert result is not None
        assert result.api_key is None


class TestReadRuntime:
    """Tests for read_runtime function."""

    def test_reads_written_state(self, tmp_path):
        """Test reading back a written state."""
        state = RuntimeState(port=9090, pid=999)
        write_runtime(tmp_path, state)

        result = read_runtime(tmp_path)
        assert result is not None
        assert result.port == 9090
        assert result.pid == 999
        assert result.instance_id == state.instance_id

    def test_returns_none_when_missing(self, tmp_path):
        """Test returns None when file doesn't exist."""
        result = read_runtime(tmp_path)
        assert result is None

    def test_returns_none_on_corrupt_json(self, tmp_path):
        """Test returns None when JSON is corrupt."""
        (tmp_path / "runtime.json").write_text("not valid json{{")
        result = read_runtime(tmp_path)
        assert result is None


class TestDeleteRuntime:
    """Tests for delete_runtime function."""

    def test_deletes_file(self, tmp_path):
        """Test deleting runtime state file."""
        state = RuntimeState()
        write_runtime(tmp_path, state)
        assert (tmp_path / "runtime.json").exists()

        delete_runtime(tmp_path)
        assert not (tmp_path / "runtime.json").exists()

    def test_noop_when_missing(self, tmp_path):
        """Test no error when file doesn't exist."""
        delete_runtime(tmp_path)  # Should not raise


class TestValidateRuntime:
    """Tests for validate_runtime function."""

    def test_invalid_when_pid_dead(self, tmp_path):
        """Test returns False when PID is dead."""
        state = RuntimeState(pid=99999999)  # Very unlikely to be alive
        with patch("os.kill", side_effect=ProcessLookupError()):
            result = validate_runtime(state)
            assert result is False

    def test_invalid_when_health_fails(self):
        """Test returns False when health check fails."""
        state = RuntimeState(
            pid=os.getpid(),
            base_url="http://127.0.0.1:99999",
        )
        result = validate_runtime(state)
        assert result is False

    def test_invalid_when_no_base_url_and_no_pid(self):
        """Test returns False with no base_url and no pid."""
        state = RuntimeState()  # pid=0, base_url=""
        result = validate_runtime(state)
        assert result is False
