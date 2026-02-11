"""File-based locking for Agent Brain instances."""

import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


# Platform-safe file locking functions
def _lock_exclusive_noop(fd: int) -> None:
    """No-op exclusive lock for platforms without native support."""
    pass


def _lock_nonblocking_noop(fd: int) -> bool:
    """No-op non-blocking lock. Returns True (always succeeds)."""
    return True


def _unlock_noop(fd: int) -> None:
    """No-op unlock for platforms without native support."""
    pass


# Initialize lock/unlock functions based on platform
_lock_exclusive: Callable[[int], None] = _lock_exclusive_noop
_try_lock_exclusive: Callable[[int], bool] = _lock_nonblocking_noop
_unlock: Callable[[int], None] = _unlock_noop
_lock_warning_shown = False

if sys.platform != "win32":
    try:
        import fcntl

        def _lock_exclusive_fcntl(fd: int) -> None:
            """Blocking exclusive lock using fcntl (POSIX)."""
            fcntl.flock(fd, fcntl.LOCK_EX)

        def _try_lock_exclusive_fcntl(fd: int) -> bool:
            """Non-blocking exclusive lock using fcntl (POSIX)."""
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except OSError:
                return False

        def _unlock_fcntl(fd: int) -> None:
            """Unlock using fcntl (POSIX)."""
            fcntl.flock(fd, fcntl.LOCK_UN)

        _lock_exclusive = _lock_exclusive_fcntl
        _try_lock_exclusive = _try_lock_exclusive_fcntl
        _unlock = _unlock_fcntl
    except ImportError:
        pass
else:
    try:
        import msvcrt

        def _lock_exclusive_msvcrt(fd: int) -> None:
            """Blocking exclusive lock using msvcrt (Windows)."""
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)

        def _try_lock_exclusive_msvcrt(fd: int) -> bool:
            """Non-blocking exclusive lock using msvcrt (Windows)."""
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                return False

        def _unlock_msvcrt(fd: int) -> None:
            """Unlock using msvcrt (Windows)."""
            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass

        _lock_exclusive = _lock_exclusive_msvcrt
        _try_lock_exclusive = _try_lock_exclusive_msvcrt
        _unlock = _unlock_msvcrt
    except ImportError:
        pass

LOCK_FILE = "agent-brain.lock"
PID_FILE = "agent-brain.pid"

# Module-level storage for lock file descriptors
_lock_fds: dict[str, int] = {}


def acquire_lock(state_dir: Path) -> bool:
    """Acquire an exclusive lock for the state directory.

    Non-blocking. Returns immediately if lock cannot be acquired.

    Args:
        state_dir: Path to the state directory.

    Returns:
        True if lock acquired, False if already held.
    """
    global _lock_warning_shown

    state_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / LOCK_FILE

    # Warn once if no locking available
    if _try_lock_exclusive is _lock_nonblocking_noop and not _lock_warning_shown:
        logger.warning(
            "File locking not available on this platform. "
            "Multiple instances may conflict."
        )
        _lock_warning_shown = True

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_WRONLY)

        if not _try_lock_exclusive(fd):
            os.close(fd)
            logger.warning(f"Lock already held: {lock_path}")
            return False

        # Write PID
        pid_path = state_dir / PID_FILE
        pid_path.write_text(str(os.getpid()))

        # Store fd for later release
        _lock_fds[str(state_dir)] = fd
        logger.info(f"Lock acquired: {lock_path}")
        return True

    except OSError:
        logger.warning(f"Lock already held: {lock_path}")
        return False


def release_lock(state_dir: Path) -> None:
    """Release the lock for the state directory.

    Args:
        state_dir: Path to the state directory.
    """
    lock_path = state_dir / LOCK_FILE

    fd = _lock_fds.pop(str(state_dir), None)
    if fd is not None:
        try:
            _unlock(fd)
            os.close(fd)
        except OSError:
            pass

    # Clean up files
    for fname in [LOCK_FILE, PID_FILE]:
        fpath = state_dir / fname
        if fpath.exists():
            try:
                fpath.unlink()
            except OSError:
                pass

    logger.info(f"Lock released: {lock_path}")


def read_pid(state_dir: Path) -> int | None:
    """Read the PID from the PID file.

    Args:
        state_dir: Path to the state directory.

    Returns:
        PID value or None if file doesn't exist or is invalid.
    """
    pid_path = state_dir / PID_FILE
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text().strip())
    except (ValueError, OSError):
        return None


def is_stale(state_dir: Path) -> bool:
    """Check if the lock is stale (PID no longer alive).

    Args:
        state_dir: Path to the state directory.

    Returns:
        True if the lock is stale or no PID exists.
    """
    pid = read_pid(state_dir)
    if pid is None:
        return True
    try:
        os.kill(pid, 0)
        return False  # Process is alive
    except ProcessLookupError:
        return True  # Process is dead
    except PermissionError:
        return False  # Process exists but we can't signal it


def cleanup_stale(state_dir: Path) -> None:
    """Clean up stale lock and PID files.

    Only cleans up if the lock is determined to be stale.
    Note: Does NOT clean runtime.json - that's managed by the CLI
    to avoid race conditions during server startup.

    Args:
        state_dir: Path to the state directory.
    """
    if is_stale(state_dir):
        for fname in [LOCK_FILE, PID_FILE]:
            fpath = state_dir / fname
            if fpath.exists():
                try:
                    fpath.unlink()
                    logger.info(f"Cleaned stale file: {fpath}")
                except OSError:
                    pass
