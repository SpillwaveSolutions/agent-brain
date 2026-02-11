"""Stop command for stopping an Agent Brain server instance."""

import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import click
from rich.console import Console

console = Console()

STATE_DIR_NAME = ".claude/agent-brain"
LOCK_FILE = "agent-brain.lock"
PID_FILE = "agent-brain.pid"
RUNTIME_FILE = "runtime.json"


def resolve_project_root(start_path: Path | None = None) -> Path:
    """Resolve the canonical project root directory."""
    start = (start_path or Path.cwd()).resolve()

    # Try git root first
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(start),
        )
        if result.returncode == 0:
            return Path(result.stdout.strip()).resolve()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Walk up looking for markers
    current = start
    while current != current.parent:
        if (current / ".claude").is_dir():
            return current
        if (current / "pyproject.toml").is_file():
            return current
        current = current.parent

    return start


def read_runtime(state_dir: Path) -> dict[str, Any] | None:
    """Read runtime state from state directory."""
    runtime_path = state_dir / RUNTIME_FILE
    if not runtime_path.exists():
        return None
    try:
        result: dict[str, Any] = json.loads(runtime_path.read_text())
        return result
    except Exception:
        return None


def delete_runtime(state_dir: Path) -> None:
    """Delete runtime state file."""
    runtime_path = state_dir / RUNTIME_FILE
    if runtime_path.exists():
        runtime_path.unlink()


def cleanup_state_files(state_dir: Path) -> None:
    """Clean up all state files after stop."""
    for fname in [LOCK_FILE, PID_FILE, RUNTIME_FILE]:
        fpath = state_dir / fname
        if fpath.exists():
            try:
                fpath.unlink()
            except OSError:
                pass


def is_process_alive(pid: int) -> bool:
    """Check if a process is alive."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Process exists but we can't signal it


def check_health(base_url: str, timeout: float = 2.0) -> bool:
    """Check if the server health endpoint responds."""
    try:
        req = Request(f"{base_url}/health/", method="GET")
        with urlopen(req, timeout=timeout) as resp:
            return bool(resp.status == 200)
    except Exception:
        return False


def wait_for_process_exit(pid: int, timeout: float = 10.0) -> bool:
    """Wait for a process to exit.

    Args:
        pid: Process ID to wait for.
        timeout: Maximum time to wait in seconds.

    Returns:
        True if process exited, False if timeout reached.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not is_process_alive(pid):
            return True
        time.sleep(0.2)
    return False


def remove_from_registry(project_root: Path) -> None:
    """Remove project from global registry."""
    registry_path = Path.home() / ".agent-brain" / "registry.json"
    if not registry_path.exists():
        return

    try:
        registry = json.loads(registry_path.read_text())
        if str(project_root) in registry:
            del registry[str(project_root)]
            registry_path.write_text(json.dumps(registry, indent=2))
    except Exception:
        pass


@click.command("stop")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project path (default: auto-detect project root)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force stop with SIGKILL if SIGTERM fails",
)
@click.option(
    "--timeout",
    type=int,
    default=10,
    help="Timeout for graceful shutdown in seconds (default: 10)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def stop_command(
    path: str | None,
    force: bool,
    timeout: int,
    json_output: bool,
) -> None:
    """Stop the Agent Brain server for this project.

    Sends SIGTERM to the server process and waits for graceful shutdown.
    If --force is specified and the process doesn't exit within the timeout,
    sends SIGKILL.

    \b
    Examples:
      agent-brain stop                    # Stop server for current project
      agent-brain stop --force            # Force stop if graceful fails
      agent-brain stop --path /my/project # Stop specific project's server
    """
    try:
        # Resolve project root
        if path:
            project_root = Path(path).resolve()
        else:
            project_root = resolve_project_root()

        state_dir = project_root / STATE_DIR_NAME

        # Check if state directory exists
        if not state_dir.exists():
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "error": "No Agent Brain state found",
                            "project_root": str(project_root),
                        }
                    )
                )
            else:
                console.print(
                    f"[yellow]No Agent Brain state found for:[/] {project_root}"
                )
            raise SystemExit(1)

        # Read runtime state
        runtime = read_runtime(state_dir)
        if not runtime:
            # Check if there's a stale PID file
            pid_path = state_dir / PID_FILE
            if pid_path.exists():
                try:
                    pid = int(pid_path.read_text().strip())
                    if is_process_alive(pid):
                        if json_output:
                            click.echo(
                                json.dumps(
                                    {
                                        "status": "stopping",
                                        "message": "Found stale PID, stopping",
                                        "pid": pid,
                                    }
                                )
                            )
                        else:
                            console.print(
                                f"[dim]Found stale PID {pid}, attempting to stop...[/]"
                            )
                        runtime = {"pid": pid}
                except (ValueError, OSError):
                    pass

            if not runtime:
                cleanup_state_files(state_dir)
                if json_output:
                    click.echo(
                        json.dumps(
                            {
                                "status": "not_running",
                                "message": "No server running",
                                "project_root": str(project_root),
                            }
                        )
                    )
                else:
                    console.print("[yellow]No server running for this project.[/]")
                return

        pid = runtime.get("pid", 0)

        if not pid:
            cleanup_state_files(state_dir)
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "status": "not_running",
                            "message": "No PID in runtime state",
                        }
                    )
                )
            else:
                console.print("[yellow]No server PID found in runtime state.[/]")
            return

        # Check if process is alive
        if not is_process_alive(pid):
            cleanup_state_files(state_dir)
            remove_from_registry(project_root)
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "status": "already_stopped",
                            "message": "Server process already stopped",
                            "pid": pid,
                        }
                    )
                )
            else:
                console.print(f"[yellow]Server process (PID {pid}) already stopped.[/]")
                console.print("[dim]Cleaned up state files.[/]")
            return

        if not json_output:
            console.print(f"[dim]Stopping server (PID {pid})...[/]")

        # Send SIGTERM
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            # Process already gone
            pass
        except PermissionError as e:
            if json_output:
                click.echo(json.dumps({"error": f"Permission denied: {e}"}))
            else:
                console.print(f"[red]Permission denied:[/] Cannot signal PID {pid}")
            raise SystemExit(1) from e

        # Wait for graceful shutdown
        if wait_for_process_exit(pid, timeout):
            cleanup_state_files(state_dir)
            remove_from_registry(project_root)
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "status": "stopped",
                            "message": "Server stopped gracefully",
                            "pid": pid,
                            "project_root": str(project_root),
                        },
                        indent=2,
                    )
                )
            else:
                console.print(f"[green]Server stopped gracefully (PID {pid}).[/]")
            return

        # Graceful shutdown failed
        if force:
            if not json_output:
                console.print(
                    "[yellow]Graceful shutdown timeout, sending SIGKILL...[/]"
                )

            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

            # Wait briefly for SIGKILL
            if wait_for_process_exit(pid, 5.0):
                cleanup_state_files(state_dir)
                remove_from_registry(project_root)
                if json_output:
                    click.echo(
                        json.dumps(
                            {
                                "status": "killed",
                                "message": "Server force killed",
                                "pid": pid,
                                "project_root": str(project_root),
                            },
                            indent=2,
                        )
                    )
                else:
                    console.print(f"[yellow]Server force killed (PID {pid}).[/]")
                return
            else:
                if json_output:
                    click.echo(
                        json.dumps(
                            {
                                "error": "Failed to stop server",
                                "pid": pid,
                                "message": "Process did not respond to SIGKILL",
                            }
                        )
                    )
                else:
                    console.print(f"[red]Error:[/] Failed to stop server (PID {pid})")
                raise SystemExit(1)
        else:
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "error": "Graceful shutdown timeout",
                            "pid": pid,
                            "hint": "Use --force to send SIGKILL",
                        }
                    )
                )
            else:
                console.print(f"[yellow]Graceful shutdown timeout for PID {pid}.[/]")
                console.print("[dim]Use --force to send SIGKILL.[/]")
            raise SystemExit(1)

    except PermissionError as e:
        if json_output:
            click.echo(json.dumps({"error": f"Permission denied: {e}"}))
        else:
            console.print(f"[red]Permission Error:[/] {e}")
        raise SystemExit(1) from e
    except OSError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1) from e
