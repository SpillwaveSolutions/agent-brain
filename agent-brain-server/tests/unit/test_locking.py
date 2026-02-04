"""Unit tests for locking module."""

import os

from agent_brain_server.locking import (
    LOCK_FILE,
    PID_FILE,
    acquire_lock,
    cleanup_stale,
    is_stale,
    read_pid,
    release_lock,
)


class TestAcquireLock:
    """Tests for acquire_lock function."""

    def test_acquires_lock(self, tmp_path):
        """Test successful lock acquisition."""
        state_dir = tmp_path / "state"
        result = acquire_lock(state_dir)
        assert result is True
        assert (state_dir / LOCK_FILE).exists()
        assert (state_dir / PID_FILE).exists()
        # Clean up
        release_lock(state_dir)

    def test_creates_pid_file(self, tmp_path):
        """Test PID file contains current process PID."""
        state_dir = tmp_path / "state"
        acquire_lock(state_dir)

        pid = int((state_dir / PID_FILE).read_text().strip())
        assert pid == os.getpid()
        release_lock(state_dir)

    def test_double_acquire_fails(self, tmp_path):
        """Test second acquire fails when lock already held."""
        state_dir = tmp_path / "state"
        assert acquire_lock(state_dir) is True
        # Second acquire opens a new fd which cannot get the lock
        # because the first fd still holds it
        assert acquire_lock(state_dir) is False
        release_lock(state_dir)

    def test_creates_directory(self, tmp_path):
        """Test creates state directory if it doesn't exist."""
        state_dir = tmp_path / "new" / "nested" / "state"
        result = acquire_lock(state_dir)
        assert result is True
        assert state_dir.exists()
        release_lock(state_dir)


class TestReleaseLock:
    """Tests for release_lock function."""

    def test_releases_lock(self, tmp_path):
        """Test lock release cleans up files."""
        state_dir = tmp_path / "state"
        acquire_lock(state_dir)
        release_lock(state_dir)

        assert not (state_dir / LOCK_FILE).exists()
        assert not (state_dir / PID_FILE).exists()

    def test_noop_when_not_locked(self, tmp_path):
        """Test release without prior acquire doesn't crash."""
        state_dir = tmp_path / "state"
        state_dir.mkdir(parents=True)
        release_lock(state_dir)  # Should not raise


class TestReadPid:
    """Tests for read_pid function."""

    def test_reads_pid(self, tmp_path):
        """Test reading PID from file."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / PID_FILE).write_text("12345")

        result = read_pid(state_dir)
        assert result == 12345

    def test_returns_none_when_missing(self, tmp_path):
        """Test returns None when PID file missing."""
        result = read_pid(tmp_path)
        assert result is None

    def test_returns_none_on_invalid_content(self, tmp_path):
        """Test returns None when PID file has invalid content."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / PID_FILE).write_text("not-a-number")

        result = read_pid(state_dir)
        assert result is None


class TestIsStale:
    """Tests for is_stale function."""

    def test_stale_when_no_pid(self, tmp_path):
        """Test stale when no PID file exists."""
        assert is_stale(tmp_path) is True

    def test_not_stale_when_process_alive(self, tmp_path):
        """Test not stale when PID is current process."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / PID_FILE).write_text(str(os.getpid()))

        assert is_stale(state_dir) is False

    def test_stale_when_process_dead(self, tmp_path):
        """Test stale when PID doesn't exist."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / PID_FILE).write_text("99999999")

        # This PID is very unlikely to be alive
        result = is_stale(state_dir)
        assert result is True


class TestCleanupStale:
    """Tests for cleanup_stale function."""

    def test_cleans_stale_files(self, tmp_path):
        """Test cleaning up stale lock files."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / LOCK_FILE).write_text("")
        (state_dir / PID_FILE).write_text("99999999")
        (state_dir / "runtime.json").write_text("{}")

        cleanup_stale(state_dir)

        assert not (state_dir / LOCK_FILE).exists()
        assert not (state_dir / PID_FILE).exists()
        # runtime.json is intentionally NOT deleted to allow CLI to read URL
        assert (state_dir / "runtime.json").exists()

    def test_no_cleanup_when_alive(self, tmp_path):
        """Test no cleanup when process is alive."""
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / PID_FILE).write_text(str(os.getpid()))
        (state_dir / LOCK_FILE).write_text("")

        cleanup_stale(state_dir)

        # Files should still exist since process is alive
        assert (state_dir / PID_FILE).exists()
        assert (state_dir / LOCK_FILE).exists()
