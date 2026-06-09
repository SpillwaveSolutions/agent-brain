"""Start command for launching an Agent Brain server instance."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import click
from rich.console import Console
from rich.panel import Panel

from agent_brain_cli.config import resolve_project_root
from agent_brain_cli.migration import resolve_state_dir_with_fallback
from agent_brain_cli.xdg_paths import get_xdg_state_dir, migrate_legacy_paths

console = Console()

STATE_DIR_NAME = ".agent-brain"
LOCK_FILE = "agent-brain.lock"
PID_FILE = "agent-brain.pid"
RUNTIME_FILE = "runtime.json"
SOCKET_FILE_NAME = "agent-brain.sock"


def read_config(state_dir: Path) -> dict[str, Any]:
    """Read configuration from state directory."""
    config_path = state_dir / "config.json"
    if config_path.exists():
        result: dict[str, Any] = json.loads(config_path.read_text())
        return result
    return {}


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


def write_runtime(state_dir: Path, runtime: dict[str, Any]) -> None:
    """Write runtime state to state directory."""
    runtime_path = state_dir / RUNTIME_FILE
    runtime_path.write_text(json.dumps(runtime, indent=2))


def delete_runtime(state_dir: Path) -> None:
    """Delete runtime state file."""
    runtime_path = state_dir / RUNTIME_FILE
    if runtime_path.exists():
        runtime_path.unlink()


def is_process_alive(pid: int) -> bool:
    """Check if a process is alive."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # Process exists but we can't signal it


def is_stale(state_dir: Path) -> bool:
    """Check if the lock is stale (PID no longer alive)."""
    pid_path = state_dir / PID_FILE
    if not pid_path.exists():
        return True
    try:
        pid = int(pid_path.read_text().strip())
        return not is_process_alive(pid)
    except (ValueError, OSError):
        return True


def cleanup_stale(state_dir: Path) -> None:
    """Clean up stale lock and runtime files."""
    for fname in [LOCK_FILE, PID_FILE, RUNTIME_FILE]:
        fpath = state_dir / fname
        if fpath.exists():
            try:
                fpath.unlink()
            except OSError:
                pass


def check_health(base_url: str, timeout: float = 3.0) -> bool:
    """Check if the server health endpoint responds."""
    try:
        req = Request(f"{base_url}/health/", method="GET")
        with urlopen(req, timeout=timeout) as resp:
            return bool(resp.status == 200)
    except Exception:
        return False


def _probe_uds(socket_path: str, *, timeout_s: float = 2.0) -> bool:
    """Probe ``socket_path`` with a UDS GET /health/ — True if 200.

    Used by ``start --uds`` after the HTTP readiness probe to confirm
    the UDS transport is actually live before advertising it in
    runtime.json (Phase 7 reviewer #4). Local import keeps httpx out of
    the start command's hot path when UDS isn't requested.
    """
    try:
        import httpx
    except ImportError:
        return False
    try:
        transport = httpx.HTTPTransport(uds=str(socket_path))
        with httpx.Client(
            transport=transport,
            base_url="http://agent-brain",
            timeout=timeout_s,
        ) as client:
            response = client.get("/health/")
            return bool(response.status_code == 200)
    except Exception:
        return False


def find_available_port(host: str, start_port: int, end_port: int) -> int | None:
    """Find an available port in the given range."""
    for port in range(start_port, end_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((host, port))
                return port
        except OSError:
            continue
    return None


def update_registry(project_root: Path, state_dir: Path) -> None:
    """Add project to global registry."""
    registry_dir = get_xdg_state_dir()
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / "registry.json"

    registry: dict[str, Any] = {}
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text())
        except Exception:
            pass

    # Use project root as key
    registry[str(project_root)] = {
        "state_dir": str(state_dir),
        "project_name": project_root.name,
    }
    registry_path.write_text(json.dumps(registry, indent=2))


@click.command("start")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project path (default: auto-detect project root)",
)
@click.option(
    "--host",
    default=None,
    help="Server bind host (overrides config)",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="Server port (overrides config)",
)
@click.option(
    "--foreground",
    "-f",
    is_flag=True,
    help="Run in foreground (don't daemonize)",
)
@click.option(
    "--timeout",
    type=int,
    default=120,
    help="Startup timeout in seconds (default: 120)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option(
    "--strict",
    is_flag=True,
    help="Enable strict mode: fail on critical provider configuration errors",
)
@click.option(
    "--uds",
    is_flag=True,
    help="Also bind a Unix Domain Socket alongside the HTTP listener.",
)
@click.option(
    "--uds-only",
    is_flag=True,
    help="Bind only the Unix Domain Socket (no TCP listener). Implies --uds.",
)
@click.option(
    "--insecure",
    is_flag=True,
    help=(
        "Start the server with authentication disabled (sets INSECURE_NO_AUTH=true). "
        "Strips any inherited API_KEY / AGENT_BRAIN_API_KEY env var so the server's "
        "startup gate honors the opt-out unambiguously. Only safe on a single-user, "
        "single-process machine. (Issue #199)"
    ),
)
def start_command(
    path: str | None,
    host: str | None,
    port: int | None,
    foreground: bool,
    timeout: int,
    json_output: bool,
    strict: bool,
    uds: bool,
    uds_only: bool,
    insecure: bool,
) -> None:
    """Start an Agent Brain server for this project.

    Spawns a new server instance bound to the project. If a server is
    already running for this project, reports its URL instead.

    \b
    Examples:
      agent-brain start                    # Start server for current project
      agent-brain start --port 8080        # Start on specific port
      agent-brain start --strict           # Fail on missing API keys
      agent-brain start --foreground       # Run in foreground
      agent-brain start --path /my/project # Start for specific project
    """
    try:
        # Trigger one-time migration from legacy ~/.agent-brain to XDG dirs
        migrate_legacy_paths()

        # Resolve project root
        if path:
            project_root = Path(path).resolve()
        else:
            project_root = resolve_project_root()

        state_dir = resolve_state_dir_with_fallback(project_root)

        # Check if initialized
        if not state_dir.exists():
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "error": "Project not initialized",
                            "hint": "Run 'agent-brain init' first",
                        }
                    )
                )
            else:
                console.print(
                    f"[red]Error:[/] Project not initialized at {project_root}"
                )
                console.print(
                    "[dim]Run 'agent-brain init' to initialize the project.[/]"
                )
            raise SystemExit(1)

        # Read configuration
        config = read_config(state_dir)

        # Check for existing runtime
        runtime = read_runtime(state_dir)
        if runtime:
            pid = runtime.get("pid", 0)
            if pid and is_process_alive(pid):
                base_url = runtime.get("base_url", "")
                if check_health(base_url):
                    if json_output:
                        click.echo(
                            json.dumps(
                                {
                                    "status": "already_running",
                                    "base_url": base_url,
                                    "pid": pid,
                                    "project_root": str(project_root),
                                }
                            )
                        )
                    else:
                        console.print(
                            Panel(
                                f"[yellow]Server already running![/]\n\n"
                                f"[bold]URL:[/] {base_url}\n"
                                f"[bold]PID:[/] {pid}\n"
                                f"[bold]Project:[/] {project_root}",
                                title="Server Running",
                                border_style="yellow",
                            )
                        )
                    return

            # Stale state, clean up
            if json_output:
                pass  # Silent cleanup in JSON mode
            else:
                console.print("[dim]Cleaning up stale server state...[/]")
            cleanup_stale(state_dir)

        # Determine bind host and port
        bind_host = host or config.get("bind_host", "127.0.0.1")
        bind_port: int
        if port:
            bind_port = port
        elif config.get("auto_port", True):
            start_port = config.get("port_range_start", 8000)
            end_port = config.get("port_range_end", 8100)
            available_port = find_available_port(bind_host, start_port, end_port)
            if available_port is None:
                if json_output:
                    click.echo(
                        json.dumps(
                            {
                                "error": (
                                    f"No available port in range "
                                    f"{start_port}-{end_port}"
                                )
                            }
                        )
                    )
                else:
                    console.print(
                        f"[red]Error:[/] No available port in range "
                        f"{start_port}-{end_port}"
                    )
                raise SystemExit(1)
            bind_port = available_port
        else:
            bind_port = config.get("port", 8000)

        base_url = f"http://{bind_host}:{bind_port}"

        if not json_output:
            console.print(f"[dim]Starting server on {base_url}...[/]")

        # Build server command. We invoke `agent_brain_server.api.main`'s
        # Click CLI (not raw `python -m uvicorn`) so the server's `run()`
        # function actually fires — it's the only place that branches on
        # AGENT_BRAIN_UDS / _UDS_ONLY env vars to delegate to uds_bind
        # (Phase 7 fix for reviewer finding A1). Behaviour for HTTP-only
        # users is identical because run() ends up calling uvicorn.run()
        # with the same args.
        server_cmd = [
            sys.executable,
            "-m",
            "agent_brain_server.api.main",
            "--host",
            bind_host,
            "--port",
            str(bind_port),
        ]

        # --uds-only implies --uds (plan §7)
        enable_uds = uds or uds_only
        socket_path = str(state_dir / SOCKET_FILE_NAME) if enable_uds else None

        # Set environment variables for server
        env = os.environ.copy()
        env["AGENT_BRAIN_PROJECT_ROOT"] = str(project_root)
        env["AGENT_BRAIN_STATE_DIR"] = str(state_dir)

        # Issue #199: --insecure short-circuits all key propagation and
        # tells the server's startup gate to accept the auth-disabled
        # posture explicitly. Strip any inherited key so a stale
        # API_KEY in the shell doesn't silently re-enable auth and
        # confuse operators who asked for --insecure on purpose.
        if insecure:
            env["INSECURE_NO_AUTH"] = "true"
            env.pop("API_KEY", None)
            env.pop("AGENT_BRAIN_API_KEY", None)
        else:
            # Issue #199: propagate the project-local API key from config.json
            # into the server subprocess as ``API_KEY`` (canonical v2 name).
            # Existing env values win so operators can override the file-
            # stored key without re-running init. The server's Settings
            # validator backfills the deprecated AGENT_BRAIN_API_KEY env
            # var, so legacy env-var setters keep working.
            config_api_key = config.get("api_key")
            if (
                config_api_key
                and not env.get("API_KEY")
                and not env.get("AGENT_BRAIN_API_KEY")
            ):
                env["API_KEY"] = str(config_api_key)
        if strict:
            env["AGENT_BRAIN_STRICT_MODE"] = "true"
        if enable_uds:
            env["AGENT_BRAIN_UDS"] = "1"
            assert socket_path is not None  # for mypy
            env["AGENT_BRAIN_UDS_PATH"] = socket_path
        if uds_only:
            env["AGENT_BRAIN_UDS_ONLY"] = "1"

        if foreground:
            # Write runtime state even in foreground mode so CLI can discover the URL
            from datetime import datetime, timezone
            from uuid import uuid4

            runtime_state = {
                "schema_version": "1.0",
                "mode": "project",
                "project_root": str(project_root),
                "instance_id": uuid4().hex[:12],
                "base_url": base_url,
                "bind_host": bind_host,
                "port": bind_port,
                "pid": os.getpid(),  # Current PID (will be replaced by exec)
                "started_at": datetime.now(timezone.utc).isoformat(),
                "foreground": True,  # Mark as foreground for cleanup detection
                "socket_path": socket_path,
            }
            write_runtime(state_dir, runtime_state)

            # Update global registry
            update_registry(project_root, state_dir)

            if not json_output:
                console.print(
                    Panel(
                        f"[green]Starting server in foreground[/]\n\n"
                        f"[bold]URL:[/] {base_url}\n"
                        f"[bold]Project:[/] {project_root}\n\n"
                        f"[dim]Press Ctrl+C to stop[/]",
                        title="Agent Brain Server",
                        border_style="green",
                    )
                )
            os.execvpe(server_cmd[0], server_cmd, env)
        else:
            # Daemonize the server
            log_dir = state_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            stdout_log = log_dir / "server.log"
            stderr_log = log_dir / "server.err"

            with (
                open(stdout_log, "a") as stdout_f,
                open(stderr_log, "a") as stderr_f,
            ):
                process = subprocess.Popen(
                    server_cmd,
                    env=env,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    start_new_session=True,
                )

            # Write runtime state
            from datetime import datetime, timezone
            from uuid import uuid4

            runtime_state = {
                "schema_version": "1.0",
                "mode": "project",
                "project_root": str(project_root),
                "instance_id": uuid4().hex[:12],
                "base_url": base_url,
                "bind_host": bind_host,
                "port": bind_port,
                "pid": process.pid,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "socket_path": socket_path,
            }
            write_runtime(state_dir, runtime_state)

            # Update global registry
            update_registry(project_root, state_dir)

            # Wait for server to be ready
            start_time = time.time()
            ready = False
            while time.time() - start_time < timeout:
                if check_health(base_url, timeout=2.0):
                    ready = True
                    break
                # Check if process died
                if process.poll() is not None:
                    break
                time.sleep(0.5)

            # If UDS was requested, probe the socket too and unset the
            # runtime.json::socket_path field if it isn't actually live.
            # Otherwise a runtime.json entry for socket_path misleads any
            # client (MCP, CLI auto-mode) that prefers UDS (Phase 7
            # reviewer #4).
            if ready and enable_uds and socket_path:
                if not _probe_uds(socket_path, timeout_s=2.0):
                    runtime_state["socket_path"] = None
                    write_runtime(state_dir, runtime_state)
                    if not json_output:
                        console.print(
                            "[yellow]UDS socket probe failed — "
                            "runtime.json::socket_path cleared. "
                            "Clients will use HTTP.[/]"
                        )

            if ready:
                if json_output:
                    click.echo(
                        json.dumps(
                            {
                                "status": "started",
                                "base_url": base_url,
                                "pid": process.pid,
                                "project_root": str(project_root),
                                "log_file": str(stdout_log),
                                "socket_path": runtime_state.get("socket_path"),
                            },
                            indent=2,
                        )
                    )
                else:
                    console.print(
                        Panel(
                            f"[green]Server started successfully![/]\n\n"
                            f"[bold]URL:[/] {base_url}\n"
                            f"[bold]PID:[/] {process.pid}\n"
                            f"[bold]Project:[/] {project_root}\n"
                            f"[bold]Log:[/] {stdout_log}",
                            title="Agent Brain Server Running",
                            border_style="green",
                        )
                    )
                    console.print("\n[dim]Next steps:[/]")
                    console.print(
                        f"  - Query: [bold]agent-brain query 'search term' "
                        f"--url {base_url}[/]"
                    )
                    console.print("  - Stop: [bold]agent-brain stop[/]")
            else:
                # Cleanup on failure
                if process.poll() is None:
                    os.kill(process.pid, signal.SIGTERM)
                delete_runtime(state_dir)

                if json_output:
                    click.echo(
                        json.dumps(
                            {
                                "error": "Server failed to start",
                                "log_file": str(stderr_log),
                            }
                        )
                    )
                else:
                    console.print("[red]Error:[/] Server failed to start")
                    console.print(f"[dim]Check logs: {stderr_log}[/]")
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
