"""`agent-brain mcp` Click sub-group for the MCP helper commands (Phase 58).

Subcommands:
    start — spawn `agent-brain-mcp --transport http` as a detached background
            subprocess on a free loopback port, write mcp.runtime.json after
            psutil-verified listener-ready. (CLI-MCP-09)
    stop  — read mcp.runtime.json, os.killpg(pgid, SIGTERM) → grace poll →
            os.killpg(pgid, SIGKILL) → delete runtime + release lock.
            Idempotent (no-op exit 0 if not running). (CLI-MCP-10)

The schema written to mcp.runtime.json is locked by the v3 design doc §2.4
(lines 176-188): {host, port, pid, started_at, transport}. All five fields
are mandatory and load-bearing across the v3 milestone.

DO NOT extend agent-brain-cli/agent_brain_cli/commands/start.py — that module
manages the agent-brain-server, not the MCP server. Phase 58 lives in a
dedicated commands/mcp.py to keep the `agent-brain mcp ...` namespace clean.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click
import psutil
from rich.console import Console

from agent_brain_cli.config import resolve_project_root
from agent_brain_cli.mcp_runtime import (
    MCP_RUNTIME_FILE,
    LockAcquisitionError,
    acquire_lock,
    delete_mcp_runtime,
    is_listening,
    read_mcp_runtime,
    release_lock,
    write_mcp_runtime,
)
from agent_brain_cli.migration import resolve_state_dir_with_fallback
from agent_brain_cli.xdg_paths import migrate_legacy_paths

console = Console()

MCP_DEFAULT_PORT = 8765
MCP_DEFAULT_START_TIMEOUT = 10
MCP_DEFAULT_STOP_GRACE = 5
MCP_SIGKILL_WAIT = 1.0
MCP_LOOPBACK_HOST = "127.0.0.1"
MCP_STDOUT_LOG = "mcp.stdout.log"
MCP_STDERR_LOG = "mcp.stderr.log"


@click.group("mcp")
def mcp_group() -> None:
    """Manage the agent-brain-mcp HTTP listener for this project.

    \b
    Examples:
      agent-brain mcp start                        # Spawn MCP HTTP on 127.0.0.1:8765
      agent-brain mcp start --port 9000            # Use port 9000 (or OS fallback)
      agent-brain mcp start --port 0               # OS picks a free port
      agent-brain mcp stop                         # Stop the running listener
      agent-brain --transport mcp --mcp-transport http query "X"
                                                   # Auto-discovers via mcp.runtime.json
    """


def _resolve_state_dir(state_dir_override: str | None) -> Path:
    """Mirror the existing server-side commands' state-dir resolution chain."""
    migrate_legacy_paths()
    if state_dir_override:
        return Path(state_dir_override).resolve()
    project_root = resolve_project_root()
    return resolve_state_dir_with_fallback(project_root)


def _resolve_preferred_port(port_flag: int | None) -> int:
    """Precedence: --port flag > AGENT_BRAIN_MCP_PORT env > 8765 default."""
    if port_flag is not None:
        return port_flag
    env_val = os.environ.get("AGENT_BRAIN_MCP_PORT")
    if env_val:
        try:
            return int(env_val)
        except ValueError as exc:
            raise click.UsageError(
                f"AGENT_BRAIN_MCP_PORT={env_val!r} is not a valid integer"
            ) from exc
    return MCP_DEFAULT_PORT


def _allocate_port(preferred: int) -> int:
    """Try to bind the preferred port; fall back to OS-allocated on EADDRINUSE.

    --port 0 means "always ask the OS" (skip the preferred-port try).
    Returns the bound port number; the socket is closed before return so
    the agent-brain-mcp subprocess can claim it. TOCTOU window is
    microseconds — same risk profile as the server start.py logic.
    """
    if preferred == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((MCP_LOOPBACK_HOST, 0))
            return int(sock.getsockname()[1])

    # Try preferred first.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((MCP_LOOPBACK_HOST, preferred))
            return preferred
    except OSError as exc:
        # macOS errno 48 / Linux errno 98 = EADDRINUSE.
        if exc.errno not in (48, 98):
            raise
        # Fallback: OS picks.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((MCP_LOOPBACK_HOST, 0))
            return int(sock.getsockname()[1])


def _tail_log(path: Path, n: int) -> list[str]:
    """Return the last n lines of a log file (best-effort, swallows errors)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return [line.rstrip() for line in lines[-n:]]
    except OSError:
        return []


@mcp_group.command("start")
@click.option(
    "--port",
    type=int,
    default=None,
    help=(
        "Preferred TCP port (default 8765, or AGENT_BRAIN_MCP_PORT env). "
        "Falls back to OS-allocated on EADDRINUSE. Pass 0 to always ask "
        "the OS."
    ),
)
@click.option(
    "--start-timeout",
    type=int,
    default=MCP_DEFAULT_START_TIMEOUT,
    envvar="AGENT_BRAIN_MCP_START_TIMEOUT",
    help=(
        f"Max seconds to wait for the MCP listener to become ready "
        f"(default {MCP_DEFAULT_START_TIMEOUT})."
    ),
)
@click.option(
    "--state-dir",
    "state_dir_override",
    type=click.Path(),
    default=None,
    help="Override state directory (default: auto-detect via project root)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def start_command(
    port: int | None,
    start_timeout: int,
    state_dir_override: str | None,
    json_output: bool,
) -> None:
    """Spawn agent-brain-mcp --transport http on a free loopback port.

    Writes <state_dir>/mcp.runtime.json AFTER psutil-verified
    listener-ready. The CLI auto-discovers via this file when
    --transport mcp --mcp-transport http is invoked without --mcp-url.
    """
    state_dir = _resolve_state_dir(state_dir_override)
    state_dir.mkdir(parents=True, exist_ok=True)

    # 1) Acquire the MCP lock (stale-pid reclamation is built into the helper).
    try:
        acquire_lock(state_dir)
    except LockAcquisitionError as exc:
        if json_output:
            click.echo(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[red]Error:[/] {exc}")
        raise SystemExit(1) from exc

    # 2) Resolve + reserve the port.
    try:
        preferred = _resolve_preferred_port(port)
        resolved_port = _allocate_port(preferred)
    except Exception:
        release_lock(state_dir)
        raise

    # 3) Open log files and spawn the detached subprocess.
    stdout_log = state_dir / MCP_STDOUT_LOG
    stderr_log = state_dir / MCP_STDERR_LOG
    cmd = [
        sys.executable,
        "-m",
        "agent_brain_mcp",
        "--transport",
        "http",
        "--host",
        MCP_LOOPBACK_HOST,
        "--port",
        str(resolved_port),
    ]

    try:
        stdout_handle = open(stdout_log, "a")
        stderr_handle = open(stderr_log, "a")
        try:
            process: subprocess.Popen[bytes] = subprocess.Popen(
                cmd,
                stdout=stdout_handle,
                stderr=stderr_handle,
                start_new_session=True,
            )
        finally:
            stdout_handle.close()
            stderr_handle.close()
    except Exception as exc:
        release_lock(state_dir)
        if json_output:
            click.echo(json.dumps({"error": f"failed to spawn agent-brain-mcp: {exc}"}))
        else:
            console.print(f"[red]Error:[/] failed to spawn agent-brain-mcp: {exc}")
        raise SystemExit(1) from exc

    # 4) Wait for listener-ready via psutil socket-bind verification.
    ready = is_listening(
        pid=process.pid,
        host=MCP_LOOPBACK_HOST,
        port=resolved_port,
        timeout=float(start_timeout),
    )

    if not ready:
        # Best-effort cleanup. Phase 58-03's stop() uses os.killpg; here we
        # send SIGTERM directly because the runtime file isn't written yet.
        try:
            process.terminate()
        except ProcessLookupError:
            pass
        release_lock(state_dir)
        tail = _tail_log(stderr_log, 20)
        msg = (
            f"agent-brain-mcp did not start within {start_timeout}s; "
            f"see {stderr_log}"
        )
        if tail:
            msg = f"{msg}\n--- last {len(tail)} stderr lines ---\n" + "\n".join(tail)
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "error": msg,
                        "stderr_log": str(stderr_log),
                        "stdout_log": str(stdout_log),
                    }
                )
            )
        else:
            console.print(f"[red]Error:[/] {msg}")
        raise SystemExit(1)

    # 5) Write the runtime file (the locked §2.4 schema).
    runtime = {
        "host": MCP_LOOPBACK_HOST,
        "port": resolved_port,
        "pid": process.pid,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "transport": "http",
    }
    write_mcp_runtime(state_dir, runtime)

    # 6) Success output.
    runtime_path = state_dir / MCP_RUNTIME_FILE
    if json_output:
        click.echo(
            json.dumps(
                {
                    "status": "started",
                    "host": MCP_LOOPBACK_HOST,
                    "port": resolved_port,
                    "pid": process.pid,
                    "runtime_file": str(runtime_path),
                    "stdout_log": str(stdout_log),
                    "stderr_log": str(stderr_log),
                },
                indent=2,
            )
        )
    else:
        console.print(
            f"[green]agent-brain-mcp listening on "
            f"http://{MCP_LOOPBACK_HOST}:{resolved_port} "
            f"(pid {process.pid})[/]"
        )
        console.print(f"[dim]runtime: {runtime_path}[/]")


def _wait_for_pid_exit(pid: int, timeout: float, poll_interval: float = 0.1) -> bool:
    """Poll psutil.pid_exists until False or timeout.

    Returns True if the process exited within ``timeout`` seconds, False
    otherwise. ``timeout == 0`` performs a single check with no sleep.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if not psutil.pid_exists(pid):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval)


@mcp_group.command("stop")
@click.option(
    "--grace",
    type=int,
    default=MCP_DEFAULT_STOP_GRACE,
    envvar="AGENT_BRAIN_MCP_STOP_GRACE",
    help=(
        f"Grace period in seconds before SIGKILL "
        f"(default {MCP_DEFAULT_STOP_GRACE})."
    ),
)
@click.option(
    "--state-dir",
    "state_dir_override",
    type=click.Path(),
    default=None,
    help="Override state directory (default: auto-detect via project root)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def stop_command(grace: int, state_dir_override: str | None, json_output: bool) -> None:
    """Stop the agent-brain-mcp HTTP listener for this project.

    Reads mcp.runtime.json, sends SIGTERM to the process group, waits
    --grace seconds, escalates to SIGKILL if needed, deletes the runtime
    file + releases the lock. Idempotent: a no-op exit 0 if not running.

    \b
    Examples:
      agent-brain mcp stop                  # Graceful stop with 5s grace
      agent-brain mcp stop --grace 10       # Override grace period
      agent-brain mcp stop --json           # Machine-readable output
    """
    state_dir = _resolve_state_dir(state_dir_override)
    runtime = read_mcp_runtime(state_dir)

    # Path 1: nothing to stop (idempotent).
    if runtime is None:
        release_lock(state_dir)
        if json_output:
            click.echo(
                json.dumps({"status": "not_running", "state_dir": str(state_dir)})
            )
        else:
            console.print("[yellow]agent-brain mcp not running.[/]")
        return

    # Path 2: runtime present but missing pid (malformed).
    pid = runtime.get("pid")
    if not isinstance(pid, int):
        delete_mcp_runtime(state_dir)
        release_lock(state_dir)
        if json_output:
            click.echo(json.dumps({"status": "not_running", "reason": "no pid"}))
        else:
            console.print("[yellow]No pid in mcp.runtime.json; cleaned up.[/]")
        return

    # Path 3: pid in runtime but process is dead.
    if not psutil.pid_exists(pid):
        delete_mcp_runtime(state_dir)
        release_lock(state_dir)
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "already_stopped",
                        "pid": pid,
                        "message": ("process already exited; cleaned up state files"),
                    }
                )
            )
        else:
            console.print(
                f"[yellow]agent-brain mcp (pid {pid}) already stopped; "
                f"cleaned up state files.[/]"
            )
        return

    # Path 4: pid alive — signal the process group with SIGTERM.
    try:
        pgid = os.getpgid(pid)
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        # Race: process died between pid_exists and getpgid/killpg.
        delete_mcp_runtime(state_dir)
        release_lock(state_dir)
        if json_output:
            click.echo(json.dumps({"status": "already_stopped", "pid": pid}))
        else:
            console.print(f"[yellow]agent-brain mcp (pid {pid}) already stopped.[/]")
        return
    except PermissionError as exc:
        msg = f"Permission denied: cannot signal pid {pid}"
        if json_output:
            click.echo(json.dumps({"error": msg}))
        else:
            console.print(f"[red]{msg}[/]")
        raise SystemExit(1) from exc

    # Path 4a: process exits within grace period — SIGTERM was enough.
    if _wait_for_pid_exit(pid, float(grace)):
        delete_mcp_runtime(state_dir)
        release_lock(state_dir)
        if json_output:
            click.echo(
                json.dumps({"status": "stopped", "pid": pid, "method": "sigterm"})
            )
        else:
            console.print(f"[green]agent-brain mcp stopped (pid {pid}).[/]")
        return

    # Path 4b: process refused to die — escalate to SIGKILL.
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        # Vanished mid-escalation; treat as success.
        pass
    _wait_for_pid_exit(pid, MCP_SIGKILL_WAIT)
    delete_mcp_runtime(state_dir)
    release_lock(state_dir)
    if json_output:
        click.echo(json.dumps({"status": "killed", "pid": pid, "method": "sigkill"}))
    else:
        console.print(
            f"[yellow]agent-brain mcp (pid {pid}) did not exit within "
            f"{grace}s; sent SIGKILL.[/]"
        )


__all__ = ["mcp_group"]
