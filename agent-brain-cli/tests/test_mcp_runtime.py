"""Tests for ``agent_brain_cli.mcp_runtime`` (Phase 58 Plan 01).

Covers the 6 helper functions + 2 constants + 1 exception type that
``agent-brain mcp start``/``stop`` (Plans 58-02 / 58-03) and the
``McpHttpBackend.__init__`` discovery integration (Plan 58-03) consume.

Test scope is UNIT — the psutil verifier (:func:`is_listening`) is
exercised via monkeypatched ``psutil.Process`` so no real subprocess is
spawned at unit-test time. Real-subprocess coverage lands in Plan
58-03's end-to-end test where the full ``mcp start`` → query → ``mcp
stop`` flow runs.

The verbatim error wording
``"agent-brain mcp already running on port {port} (pid {pid}); run
'agent-brain mcp stop' first"`` is pinned by a regex assertion so Plan
58-02 (which formats the operator-facing error from the MCP command
group) can grep for it without depending on this module.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import psutil
import pytest

from agent_brain_cli.mcp_runtime import (
    MCP_DEFAULT_PORT,
    MCP_DEFAULT_START_TIMEOUT,
    MCP_LOCK_FILE,
    MCP_RUNTIME_FILE,
    LockAcquisitionError,
    acquire_lock,
    delete_mcp_runtime,
    is_listening,
    read_mcp_runtime,
    release_lock,
    write_mcp_runtime,
)

# ---------------------------------------------------------------------------
# Module-level constant sanity
# ---------------------------------------------------------------------------


def test_module_constants_match_design_doc() -> None:
    """The public constants are pinned against silent rename."""
    assert MCP_RUNTIME_FILE == "mcp.runtime.json"
    assert MCP_LOCK_FILE == "agent-brain-mcp.lock"
    assert MCP_DEFAULT_PORT == 8765
    assert MCP_DEFAULT_START_TIMEOUT == 10.0


# ---------------------------------------------------------------------------
# read_mcp_runtime
# ---------------------------------------------------------------------------


def test_read_mcp_runtime_returns_none_when_missing(tmp_path: Path) -> None:
    """File absent → returns None (mirrors start.py::read_runtime)."""
    assert read_mcp_runtime(tmp_path) is None


def test_read_mcp_runtime_returns_dict_when_present(tmp_path: Path) -> None:
    """File present with valid JSON → returns the parsed dict."""
    payload = {
        "host": "127.0.0.1",
        "port": 8765,
        "pid": 12345,
        "started_at": "2026-06-07T01:49:08.173+00:00",
        "transport": "http",
    }
    (tmp_path / MCP_RUNTIME_FILE).write_text(json.dumps(payload))
    result = read_mcp_runtime(tmp_path)
    assert result == payload


def test_read_mcp_runtime_returns_none_when_malformed(tmp_path: Path) -> None:
    """Malformed JSON → returns None (does NOT raise)."""
    (tmp_path / MCP_RUNTIME_FILE).write_text("{not-valid-json")
    assert read_mcp_runtime(tmp_path) is None


# ---------------------------------------------------------------------------
# write_mcp_runtime
# ---------------------------------------------------------------------------


def test_write_mcp_runtime_creates_file_with_0o600_perms(tmp_path: Path) -> None:
    """Written file has 0o600 perms (issue #179 carry-forward)."""
    payload = {
        "host": "127.0.0.1",
        "port": 8765,
        "pid": 1,
        "started_at": "x",
        "transport": "http",
    }
    write_mcp_runtime(tmp_path, payload)
    runtime_path = tmp_path / MCP_RUNTIME_FILE
    assert runtime_path.exists()
    mode = os.stat(runtime_path).st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600 perms, got {oct(mode)}"
    assert json.loads(runtime_path.read_text()) == payload


def test_write_mcp_runtime_creates_state_dir(tmp_path: Path) -> None:
    """Missing parent state_dir is created (mkdir parents=True)."""
    nested = tmp_path / "deep" / "nested" / "state"
    assert not nested.exists()
    write_mcp_runtime(
        nested,
        {"host": "x", "port": 1, "pid": 1, "started_at": "x", "transport": "http"},
    )
    assert nested.exists()
    assert (nested / MCP_RUNTIME_FILE).exists()


# ---------------------------------------------------------------------------
# delete_mcp_runtime
# ---------------------------------------------------------------------------


def test_delete_mcp_runtime_is_idempotent(tmp_path: Path) -> None:
    """Missing file → no-op; present file → deleted; second call → no-op."""
    # First call (missing) — should not raise.
    delete_mcp_runtime(tmp_path)
    # Write then delete.
    (tmp_path / MCP_RUNTIME_FILE).write_text("{}")
    delete_mcp_runtime(tmp_path)
    assert not (tmp_path / MCP_RUNTIME_FILE).exists()
    # Second delete (missing again) — should not raise.
    delete_mcp_runtime(tmp_path)


# ---------------------------------------------------------------------------
# acquire_lock / release_lock
# ---------------------------------------------------------------------------


def test_acquire_lock_creates_file_when_missing(tmp_path: Path) -> None:
    """No prior lock → atomic create with current pid + 0o600 perms."""
    lock_path = acquire_lock(tmp_path)
    assert lock_path == tmp_path / MCP_LOCK_FILE
    assert lock_path.exists()
    mode = os.stat(lock_path).st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600 perms, got {oct(mode)}"
    assert lock_path.read_text().strip() == str(os.getpid())


def test_acquire_lock_raises_when_holder_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lock present + recorded pid alive → LockAcquisitionError."""
    # Write a runtime file pointing at a "live" pid.
    write_mcp_runtime(
        tmp_path,
        {
            "host": "127.0.0.1",
            "port": 8765,
            "pid": 99999,
            "started_at": "x",
            "transport": "http",
        },
    )
    # Pre-create the lock file (simulate a holder).
    (tmp_path / MCP_LOCK_FILE).write_text("99999")
    # Force psutil.pid_exists to report alive.
    monkeypatch.setattr(psutil, "pid_exists", lambda pid: True)
    with pytest.raises(LockAcquisitionError) as excinfo:
        acquire_lock(tmp_path)
    msg = str(excinfo.value)
    assert "agent-brain mcp already running" in msg
    assert "8765" in msg
    assert "99999" in msg


def test_acquire_lock_reclaims_when_holder_dead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lock present + recorded pid dead → reclaim + retry once → success."""
    # Pre-existing stale lock + runtime file.
    (tmp_path / MCP_LOCK_FILE).write_text("99999")
    write_mcp_runtime(
        tmp_path,
        {
            "host": "127.0.0.1",
            "port": 8765,
            "pid": 99999,
            "started_at": "x",
            "transport": "http",
        },
    )
    # Force psutil.pid_exists to report DEAD for the recorded pid.
    monkeypatch.setattr(psutil, "pid_exists", lambda pid: False)
    # Acquisition succeeds via stale-pid reclamation.
    lock_path = acquire_lock(tmp_path)
    assert lock_path.exists()
    assert lock_path.read_text().strip() == str(os.getpid())


def test_release_lock_is_idempotent(tmp_path: Path) -> None:
    """Missing → no-op; present → deleted; second call → no-op."""
    release_lock(tmp_path)  # missing — must not raise
    (tmp_path / MCP_LOCK_FILE).write_text(str(os.getpid()))
    release_lock(tmp_path)
    assert not (tmp_path / MCP_LOCK_FILE).exists()
    release_lock(tmp_path)  # missing again — must not raise


def test_lock_acquisition_error_message_matches_verbatim_wording(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exception message wording is pinned for Plan 58-02 grep."""
    write_mcp_runtime(
        tmp_path,
        {
            "host": "127.0.0.1",
            "port": 8765,
            "pid": 42,
            "started_at": "x",
            "transport": "http",
        },
    )
    (tmp_path / MCP_LOCK_FILE).write_text("42")
    monkeypatch.setattr(psutil, "pid_exists", lambda pid: True)
    with pytest.raises(LockAcquisitionError) as excinfo:
        acquire_lock(tmp_path)
    pattern = re.compile(
        r"agent-brain mcp already running on port .+ \(pid \d+\); "
        r"run 'agent-brain mcp stop' first"
    )
    assert pattern.search(
        str(excinfo.value)
    ), f"Wording drift: got {str(excinfo.value)!r}"


# ---------------------------------------------------------------------------
# is_listening — psutil stub-based tests
# ---------------------------------------------------------------------------


class _StubLAddr:
    """Stub for ``conn.laddr`` matching psutil's namedtuple shape."""

    def __init__(self, ip: str, port: int) -> None:
        self.ip = ip
        self.port = port


class _StubConn:
    """Stub for a single ``psutil.Process.net_connections`` row."""

    def __init__(self, status: str, ip: str, port: int) -> None:
        self.status = status
        self.laddr = _StubLAddr(ip, port)


class _StubProcess:
    """Stub for ``psutil.Process`` returning canned connections."""

    def __init__(self, connections: list[Any]) -> None:
        self._connections = connections

    def net_connections(self, kind: str = "inet") -> list[Any]:
        # Plan 58-01 helper passes kind="inet" — pin the kwarg shape.
        assert kind == "inet", f"Expected kind='inet', got kind={kind!r}"
        return self._connections


def test_is_listening_returns_true_when_psutil_reports_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Match → True (same shape as agent-brain-mcp/tests/test_http_loopback.py)."""
    conns = [_StubConn(psutil.CONN_LISTEN, "127.0.0.1", 8765)]
    monkeypatch.setattr(psutil, "Process", lambda pid: _StubProcess(conns))
    assert is_listening(1234, "127.0.0.1", 8765, timeout=0.0) is True


def test_is_listening_returns_false_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No matching LISTEN → False once deadline expires."""
    # Empty connection list — never matches.
    monkeypatch.setattr(psutil, "Process", lambda pid: _StubProcess([]))
    assert (
        is_listening(1234, "127.0.0.1", 8765, timeout=0.05, poll_interval=0.01) is False
    )


def test_is_listening_returns_false_when_process_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """psutil.NoSuchProcess → returns False (does NOT raise)."""

    def _raise_nsp(_pid: int) -> Any:
        raise psutil.NoSuchProcess(_pid)

    monkeypatch.setattr(psutil, "Process", _raise_nsp)
    assert is_listening(1234, "127.0.0.1", 8765, timeout=0.0) is False


def test_is_listening_returns_false_on_access_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """psutil.AccessDenied → returns False (does NOT raise)."""

    def _raise_ad(_pid: int) -> Any:
        raise psutil.AccessDenied(_pid)

    monkeypatch.setattr(psutil, "Process", _raise_ad)
    assert is_listening(1234, "127.0.0.1", 8765, timeout=0.0) is False


def test_is_listening_filters_to_loopback_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LISTEN socket on 0.0.0.0 (NOT 127.0.0.1) → False."""
    conns = [_StubConn(psutil.CONN_LISTEN, "0.0.0.0", 8765)]
    monkeypatch.setattr(psutil, "Process", lambda pid: _StubProcess(conns))
    assert is_listening(1234, "127.0.0.1", 8765, timeout=0.0) is False


def test_is_listening_filters_to_exact_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LISTEN socket on 127.0.0.1 but wrong port → False."""
    conns = [_StubConn(psutil.CONN_LISTEN, "127.0.0.1", 9999)]
    monkeypatch.setattr(psutil, "Process", lambda pid: _StubProcess(conns))
    assert is_listening(1234, "127.0.0.1", 8765, timeout=0.0) is False


def test_is_listening_ignores_non_listen_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ESTABLISHED outbound conn on same port → False (status filter)."""
    conns = [_StubConn(psutil.CONN_ESTABLISHED, "127.0.0.1", 8765)]
    monkeypatch.setattr(psutil, "Process", lambda pid: _StubProcess(conns))
    assert is_listening(1234, "127.0.0.1", 8765, timeout=0.0) is False
