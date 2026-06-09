"""Phase 60 (MCPHYG-02): 1000-invocation no-orphan stress test.

OPT-IN: marked ``pytest.mark.stress`` so default pytest runs SKIP this.
Driven by ``task mcp:stress:orphan-test`` — NOT in ``task before-push``.

Per the locked CONTEXT.md §"1000-invocation orphan detection mechanism":

- PRIMARY assert: ``psutil.Process(os.getpid()).children(recursive=True)``
  delta per iteration must shrink back to zero. Cross-platform.
- DIAGNOSTIC only: ``pgrep -f agent-brain-mcp`` is invoked ONLY when
  psutil already detected a leak — fed into the failure-message surface
  for human triage.
- Failure surface: {iteration #, spawned PIDs that survived, pgrep
  output, time-since-close}. Tight-loop STOPS on first leak (not after
  1000).
- Iteration count: default 1000, override via
  ``AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS`` env var.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time

import psutil
import pytest

from agent_brain_mcp.client import McpStdioBackend

# Default iteration count per ROADMAP Phase 60 SC3.
DEFAULT_MAX_ITERATIONS = 1000

# Optional override for development / faster iteration.
ITER_ENV_VAR = "AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS"


def _resolve_max_iterations() -> int:
    """Read AGENT_BRAIN_ORPHAN_TEST_MAX_ITERATIONS or fall back to default."""
    raw = os.environ.get(ITER_ENV_VAR)
    if not raw:
        return DEFAULT_MAX_ITERATIONS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_ITERATIONS
    return max(1, value)


def _pgrep_diagnostic() -> str:
    """Best-effort ``pgrep -f agent-brain-mcp`` for the failure surface.

    Returns the raw stdout or an empty string if pgrep is unavailable
    (e.g. Windows, or PATH lacks the binary).
    """
    if shutil.which("pgrep") is None:
        return "<pgrep not available on PATH>"
    try:
        result = subprocess.run(
            ["pgrep", "-f", "agent-brain-mcp"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        return result.stdout.strip() or "<no matches>"
    except Exception as exc:  # noqa: BLE001 — diagnostic is best-effort
        return f"<pgrep failed: {exc!r}>"


def _children_pids(parent_pid: int) -> set[int]:
    """Snapshot recursive descendant PIDs for the given parent.

    Returns a set for fast delta computation. Tolerates NoSuchProcess +
    AccessDenied — descendant may exit mid-walk; that race is exactly
    what we want to detect (delta should still resolve to zero after
    a successful close()).
    """
    try:
        parent = psutil.Process(parent_pid)
        return {child.pid for child in parent.children(recursive=True)}
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return set()


@pytest.fixture(scope="module")
def _agent_brain_mcp_on_path() -> str:
    """Locate agent-brain-mcp; skip the whole module if missing."""
    binary = shutil.which("agent-brain-mcp")
    if binary is None:
        pytest.skip(
            "agent-brain-mcp not on PATH — install the package "
            "(poetry install) before running the stress test."
        )
    return binary


@pytest.mark.stress
def test_no_orphan_subprocess_after_1000_query_close_cycles(
    _agent_brain_mcp_on_path: str,
) -> None:
    """Tight loop: instantiate + health() + close() N times; assert no orphans.

    Stops on first leak so failure messages stay readable.

    Note: the PRIMARY assertion is the psutil children delta check —
    NOT that ``health()`` succeeds. ``health()`` may legitimately raise
    when no live ``agent-brain-server`` is reachable at startup (the
    MCP subprocess does a ``MIN_BACKEND_VERSION`` check before
    accepting any tool calls). The subprocess still spawns + exits
    cleanly in that path; the question MCPHYG-02 closes is whether
    ``close()`` properly tears it down without leaking children.
    """
    max_iterations = _resolve_max_iterations()
    self_pid = os.getpid()

    baseline_children = _children_pids(self_pid)

    for iteration in range(1, max_iterations + 1):
        before = _children_pids(self_pid)

        backend = McpStdioBackend(_agent_brain_mcp_on_path)
        # health() may raise when no backend is reachable — that path
        # still spawns + tears down a subprocess, which is exactly the
        # hygiene contract MCPHYG-02 verifies. The orphan check below
        # is the load-bearing assertion regardless of health()'s outcome.
        try:
            backend.health()
        except Exception:
            pass
        close_started = time.monotonic()
        backend.close()
        time_since_close = time.monotonic() - close_started

        # Give the OS a brief moment to reap. The hygienic close()
        # already polls returncode; this is belt-and-suspenders.
        time.sleep(0.05)

        after = _children_pids(self_pid)
        # Delta against the pre-iteration snapshot: any PID that
        # appeared during this iteration AND is still alive is a leak.
        leaked = (after - before) - baseline_children

        if leaked:
            pgrep_output = _pgrep_diagnostic()
            pytest.fail(
                "Orphan subprocess detected after McpStdioBackend.close().\n"
                f"  iteration:       {iteration} / {max_iterations}\n"
                f"  surviving PIDs:  {sorted(leaked)}\n"
                f"  time-since-close: {time_since_close * 1000:.1f}ms\n"
                f"  pgrep diagnostic:\n{pgrep_output}\n"
                "  Phase 60 hygiene contract violated — close() must "
                "SIGTERM → wait grace_period_s → SIGKILL the in-flight "
                "subprocess. See plan 60-02."
            )
