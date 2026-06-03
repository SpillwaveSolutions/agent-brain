"""Phase 53 Plan 03: HTTP-03 no-silent-fallback subprocess tests.

HTTP-03 ("Invalid transport / non-loopback / port-in-use fail
explicitly") is partially proven in-process by Plan 01's CLI flag
tests (the Click usage errors) and Plan 02's loopback enforcement
unit tests. Plan 03 closes the loop with three subprocess-level
proofs:

1. ``--transport bogus`` exits non-zero and Click prints "not one of".
   No bind attempt — runs in the fast lane WITHOUT the e2e_http
   marker because there's no uvicorn cold start.
2. ``--transport http --host 0.0.0.0`` exits non-zero with the
   contract message. Plan 02's validator rejects BEFORE bind, so this
   also runs in the fast lane WITHOUT the marker.
3. ``--transport http --port <occupied>`` exits with code 2 (Plan 02
   D-12 ``PortInUseError`` contract). DOES need the e2e_http marker
   because Plan 02's pre-flight port probe briefly attempts a bind
   before raising — that's a real socket operation, slow on CI.

Note: the negative tests target the **real CLI entry point**
(``python -m agent_brain_mcp.cli``) — they exercise Click + Plan 01's
dispatcher + Plan 02's validator end-to-end. Unlike
``test_transport_selection.py`` (which uses the fake-server harness
to bypass the version-compat check), these tests reject BEFORE the
version check fires, so a real backend is never needed.
"""

from __future__ import annotations

import socket
import subprocess
import sys

import pytest


def _run_cli(*args: str, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    """Run ``python -m agent_brain_mcp.cli`` with the given args."""
    return subprocess.run(
        [sys.executable, "-m", "agent_brain_mcp.cli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_bogus_transport_rejected_by_click() -> None:
    """``--transport bogus`` → Click's standard ``not one of`` rejection.

    No e2e_http marker: Click's :class:`click.Choice` rejects before
    Plan 01's dispatcher runs — no socket touched, no uvicorn cold
    start. Belongs in the fast lane.
    """
    result = _run_cli("--transport", "bogus")
    assert result.returncode != 0, (
        f"Expected non-zero exit for --transport bogus; "
        f"got {result.returncode}. stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    combined = (result.stderr + result.stdout).lower()
    assert "not one of" in combined or "invalid value" in combined, (
        f"Expected Click's 'not one of' rejection; "
        f"got combined output: {combined!r}"
    )


def test_non_loopback_host_rejected_before_bind() -> None:
    """``--transport http --host 0.0.0.0`` → loopback whitelist rejection.

    Plan 02's ``validate_loopback_host`` raises
    :class:`click.ClickException` with the contract message BEFORE the
    pre-flight port probe runs. No socket bind attempted — fast lane.
    """
    result = _run_cli("--transport", "http", "--host", "0.0.0.0")
    assert result.returncode != 0, (
        f"Expected non-zero exit for --host 0.0.0.0; "
        f"got {result.returncode}. stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    combined = (result.stderr + result.stdout).lower()
    # Plan 02's exact contract phrase is "must be one of {127.0.0.1,
    # localhost, ::1}"; the unique substring "loopback" anchors against
    # message regressions while accepting minor wording polish.
    assert "must be one of" in combined or "loopback" in combined, (
        f"Expected loopback whitelist rejection message; "
        f"got combined output: {combined!r}"
    )


@pytest.mark.e2e_http
def test_port_in_use_exits_code_2(free_loopback_port: int) -> None:
    """``--transport http --port <occupied>`` → exit 2 (Plan 02 D-12).

    Marked ``e2e_http`` because Plan 02's pre-flight probe briefly
    attempts a real ``socket.bind`` — slow enough on CI runners that
    we keep it off the fast lane.

    Holds the port open in the test process so the subprocess hits
    EADDRINUSE and Plan 02's :class:`PortInUseError` (exit code 2)
    fires.
    """
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        holder.bind(("127.0.0.1", free_loopback_port))
        holder.listen(1)
        result = _run_cli(
            "--transport",
            "http",
            "--port",
            str(free_loopback_port),
        )
        # Plan 02 D-12: PortInUseError.exit_code = 2 — distinct from
        # the default exit_code=1 used by host-validation rejection.
        # Two distinct exit codes for two distinct failure modes lets
        # operators route on ``$?`` without parsing stderr.
        assert result.returncode == 2, (
            f"Expected exit code 2 for port-in-use; got {result.returncode}. "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        combined = (result.stderr + result.stdout).lower()
        assert "already in use" in combined, (
            f"Expected 'already in use' in port-collision message; "
            f"got combined output: {combined!r}"
        )
    finally:
        holder.close()
