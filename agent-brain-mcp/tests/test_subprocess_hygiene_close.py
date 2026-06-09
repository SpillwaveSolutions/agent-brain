"""Phase 60 (MCPHYG-01): close() SIGTERM → SIGKILL escalation tests.

Uses the portable SIGTERM-ignoring Python stub at tests/_stubs/ignore_sigterm.py
to prove SIGKILL escalation runs when a real subprocess refuses to die
within self.grace_period_s.

Locked CONTEXT decisions:
- Default grace_period_s = 5.0s; tests use 0.5s for speed.
- Pattern A preserved (fresh subprocess per call) — close() is idempotent
  and does not prevent subsequent _async_* calls.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_brain_mcp.client import (
    McpStdioBackend,
    _extract_subprocess_from_streams,
    _wait_for_subprocess_exit,
)

STUB_PATH = Path(__file__).parent / "_stubs" / "ignore_sigterm.py"
EXIT_ON_SIGTERM_INLINE = (
    "import signal,time;"
    "signal.signal(signal.SIGTERM, lambda *_: __import__('sys').exit(0));"
    "print('READY', flush=True);"
    "time.sleep(30)"
)


class _FakeProcess:
    """Minimal asyncio.subprocess.Process-shaped fake that supports weakref.

    ``SimpleNamespace`` does NOT support ``weakref.ref()`` (no
    ``__weakref__`` slot), so the E2E extraction test needs a real class
    with default ``__dict__`` to be weak-referenceable. Duck-types the
    three attrs the extractor probes for: returncode / terminate / kill.
    """

    def __init__(self, returncode: int | None = None) -> None:
        self.returncode = returncode

    def terminate(self) -> None:
        pass

    def kill(self) -> None:
        pass


class TestCloseIdempotency:
    def test_close_on_fresh_backend_is_noop(self) -> None:
        backend = McpStdioBackend("agent-brain-mcp")
        # No in-flight subprocess; close() returns immediately.
        backend.close()
        assert backend._closed is True

    def test_close_twice_is_idempotent(self) -> None:
        backend = McpStdioBackend("agent-brain-mcp")
        backend.close()
        backend.close()  # Must not raise.
        assert backend._closed is True


class TestWaitForSubprocessExit:
    def test_returns_true_when_process_exits_within_timeout(self) -> None:
        # A SimpleNamespace with returncode=0 satisfies the duck-type.
        fake_process = SimpleNamespace(returncode=0)
        assert _wait_for_subprocess_exit(fake_process, 0.1) is True

    def test_returns_false_when_process_still_alive(self) -> None:
        fake_process = SimpleNamespace(returncode=None)
        start = time.monotonic()
        result = _wait_for_subprocess_exit(fake_process, 0.2)
        elapsed = time.monotonic() - start
        assert result is False
        assert elapsed >= 0.15  # roughly honored the timeout


class TestExtractSubprocessFromStreams:
    def test_returns_none_when_streams_lack_process(self) -> None:
        # Two-tuple of opaque streams — no _process/process/_transport.
        read = object()
        write = object()
        assert _extract_subprocess_from_streams((read, write)) is None

    def test_returns_process_when_write_has_process_attr(self) -> None:
        fake_process = SimpleNamespace(
            returncode=None,
            terminate=lambda: None,
            kill=lambda: None,
        )
        write = SimpleNamespace(_process=fake_process)
        read = object()
        result = _extract_subprocess_from_streams((read, write))
        assert result is fake_process

    def test_returns_none_on_exception(self) -> None:
        # Not iterable as a 2-tuple — function must soft-fail.
        assert _extract_subprocess_from_streams(None) is None


# ---- Real-subprocess escalation tests ---------------------------------------
# These spawn actual python subprocesses to exercise SIGTERM/SIGKILL signaling
# end-to-end. They are SLOW (~0.5-2s each) but prove the close() contract.


@pytest.mark.skipif(
    os.name == "nt", reason="POSIX signaling — Windows not supported in Phase 60"
)
class TestCloseEscalationRealSubprocess:
    @pytest.mark.asyncio
    async def test_sigterm_alone_kills_well_behaved_child(self) -> None:
        backend = McpStdioBackend("agent-brain-mcp", grace_period_s=2.0)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            EXIT_ON_SIGTERM_INLINE,
            stdout=asyncio.subprocess.PIPE,
        )
        # Wait for READY marker so we know the SIGTERM handler is installed.
        assert process.stdout is not None
        line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
        assert b"READY" in line
        pid = process.pid

        backend._register_inflight(process)
        start = time.monotonic()
        backend.close()
        elapsed = time.monotonic() - start

        # SIGTERM was honored — should exit fast, well under grace_period_s.
        # close() runs sync OUTSIDE the asyncio loop, so process.returncode
        # may still be None here even though the OS-level process is gone.
        # Use psutil.pid_exists for the kernel-level assertion. Then await
        # process.wait() so asyncio learns the returncode for the
        # exit-code assertion.
        import psutil

        assert not psutil.pid_exists(pid)
        assert elapsed < 2.0
        await asyncio.wait_for(process.wait(), timeout=2.0)
        # SIGTERM honored → exit code 0 (the inline handler calls sys.exit(0)).
        assert process.returncode == 0

    @pytest.mark.asyncio
    async def test_sigkill_escalation_kills_ignorant_child(self) -> None:
        # grace_period_s=0.5 keeps the test fast.
        backend = McpStdioBackend("agent-brain-mcp", grace_period_s=0.5)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            str(STUB_PATH),
            "--sleep",
            "30",
            stdout=asyncio.subprocess.PIPE,
        )
        assert process.stdout is not None
        line = await asyncio.wait_for(process.stdout.readline(), timeout=5.0)
        assert b"READY" in line
        pid = process.pid

        backend._register_inflight(process)
        start = time.monotonic()
        backend.close()
        elapsed = time.monotonic() - start

        # SIGTERM was IGNORED → SIGKILL escalation must have fired.
        # Same psutil + await wait() pattern as the SIGTERM-honored test.
        import psutil

        assert not psutil.pid_exists(pid)
        # Must have waited at least grace_period_s before escalating.
        assert elapsed >= 0.4
        # Plus a small SIGKILL wait — bounded above 3s.
        assert elapsed < 3.0
        await asyncio.wait_for(process.wait(), timeout=2.0)
        # Negative returncode indicates termination by signal on POSIX.
        # SIGKILL = 9 → returncode == -9.
        assert process.returncode == -signal.SIGKILL


class TestPatternAPreservation:
    def test_close_does_not_break_subsequent_stdio_params(self) -> None:
        # Pattern A invariant: backend is reusable across calls. close()
        # only tears down in-flight subprocesses; it does NOT mark the
        # backend permanently dead from a Pattern A standpoint.
        backend = McpStdioBackend("agent-brain-mcp")
        backend.close()
        # The flag flips True but the backend object still produces valid
        # StdioServerParameters (next call spawns a fresh subprocess).
        params = backend._stdio_params()
        assert params is not None
        # Pattern A: env is still filtered; cwd still pinned.
        assert params.cwd == backend.cwd


# ---- E2E extraction test (§3.5 no-silent-fallback guard) -------------------
# Drives the hygienic wrapper through a faked SDK-shaped stdio_client and
# asserts the extraction path actually populates self._inflight_ref. Without
# this, a future MCP SDK upgrade (e.g. 1.13+) could silently break
# _extract_subprocess_from_streams (which soft-fails to None) — hygiene would
# silently disable while every other unit test stays green.


class TestHygienicWrapperRealSdkShape:
    @pytest.mark.asyncio
    async def test_hygienic_wrapper_registers_inflight_on_real_sdk_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Build a fake (read, write) tuple matching the MCP SDK 1.12.x shape:
        # the write stream exposes a ._process attribute pointing at an
        # asyncio.subprocess.Process-shaped object (duck-typed —
        # returncode/terminate/kill). _FakeProcess (not SimpleNamespace)
        # because weakref.ref() requires __weakref__ slot.
        fake_process = _FakeProcess(returncode=None)
        fake_write = SimpleNamespace(_process=fake_process)
        fake_read = object()

        @asynccontextmanager
        async def fake_stdio_client(_params: object):  # type: ignore[no-untyped-def]
            yield (fake_read, fake_write)

        # Patch the SDK entry point that _hygienic_stdio_client imports
        # lazily. The in-function ``from mcp.client.stdio import stdio_client``
        # resolves to whatever is bound at ``mcp.client.stdio.stdio_client``
        # at call time — patching there is the right hook.
        monkeypatch.setattr(
            "mcp.client.stdio.stdio_client", fake_stdio_client, raising=True
        )

        backend = McpStdioBackend("agent-brain-mcp")
        # Sanity precondition — before the with-block, no in-flight ref.
        assert backend._inflight_ref is None

        async with backend._hygienic_stdio_client(backend._stdio_params()) as streams:
            # PRIMARY assertion — proves the extraction path actually
            # registered the SDK process on the backend.
            assert backend._inflight_ref is not None
            registered = backend._inflight_ref()
            assert registered is fake_process
            # Streams are passed through verbatim — wrapper is transparent.
            assert streams == (fake_read, fake_write)

        # Post-exit: wrapper must have unregistered.
        assert backend._inflight_ref is None
