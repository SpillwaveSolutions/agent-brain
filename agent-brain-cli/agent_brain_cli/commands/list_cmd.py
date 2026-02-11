"""List command for showing all running Agent Brain instances."""

import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import click
from rich.console import Console
from rich.table import Table

console = Console()

RUNTIME_FILE = "runtime.json"


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


def get_registry() -> dict[str, Any]:
    """Load the global registry of Agent Brain projects."""
    registry_path = Path.home() / ".agent-brain" / "registry.json"
    if not registry_path.exists():
        return {}
    try:
        result: dict[str, Any] = json.loads(registry_path.read_text())
        return result
    except Exception:
        return {}


def save_registry(registry: dict[str, Any]) -> None:
    """Save the global registry."""
    registry_dir = Path.home() / ".agent-brain"
    registry_dir.mkdir(parents=True, exist_ok=True)
    registry_path = registry_dir / "registry.json"
    registry_path.write_text(json.dumps(registry, indent=2))


def scan_instances() -> list[dict[str, Any]]:
    """Scan registry for running instances and validate them.

    Returns:
        List of instance info dictionaries with validation status.
    """
    registry = get_registry()
    instances = []
    stale_entries = []

    for project_root, entry in registry.items():
        state_dir = Path(entry.get("state_dir", ""))
        if not state_dir.exists():
            stale_entries.append(project_root)
            continue

        runtime = read_runtime(state_dir)
        if not runtime:
            stale_entries.append(project_root)
            continue

        pid = runtime.get("pid", 0)
        base_url = runtime.get("base_url", "")
        mode = runtime.get("mode", "project")
        started_at = runtime.get("started_at", "")

        # Validate process
        process_alive = is_process_alive(pid) if pid else False

        # Validate health
        health_ok = check_health(base_url) if base_url else False

        # Determine status
        if process_alive and health_ok:
            status = "running"
        elif process_alive:
            status = "unhealthy"
        else:
            status = "stale"
            stale_entries.append(project_root)

        instances.append(
            {
                "project_root": project_root,
                "project_name": entry.get("project_name", Path(project_root).name),
                "base_url": base_url,
                "pid": pid,
                "mode": mode,
                "status": status,
                "started_at": started_at,
            }
        )

    # Clean up stale entries
    if stale_entries:
        for project_root in stale_entries:
            if project_root in registry:
                del registry[project_root]
        save_registry(registry)

    return instances


@click.command("list")
@click.option(
    "--all",
    "-a",
    "show_all",
    is_flag=True,
    help="Show all instances including stale ones",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_command(show_all: bool, json_output: bool) -> None:
    """List all running Agent Brain instances.

    Scans the global registry for Agent Brain instances and validates
    each one by checking if the process is alive and the health
    endpoint responds.

    \b
    Examples:
      agent-brain list            # List running instances
      agent-brain list --all      # Include stale instances
      agent-brain list --json     # Output as JSON
    """
    try:
        instances = scan_instances()

        # Filter unless --all
        if not show_all:
            instances = [i for i in instances if i["status"] == "running"]

        if json_output:
            click.echo(
                json.dumps(
                    {
                        "instances": instances,
                        "total": len(instances),
                    },
                    indent=2,
                )
            )
            return

        if not instances:
            console.print("[dim]No running Agent Brain instances found.[/]")
            console.print("\n[dim]Start a server with: agent-brain start[/]")
            return

        # Create table
        table = Table(
            title="Agent Brain Instances",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Project", style="bold")
        table.add_column("URL")
        table.add_column("PID", justify="right")
        table.add_column("Mode")
        table.add_column("Status")

        for instance in instances:
            # Color status
            status = instance["status"]
            if status == "running":
                status_text = "[green]running[/]"
            elif status == "unhealthy":
                status_text = "[yellow]unhealthy[/]"
            else:
                status_text = "[red]stale[/]"

            table.add_row(
                instance["project_name"],
                instance["base_url"],
                str(instance["pid"]) if instance["pid"] else "-",
                instance["mode"],
                status_text,
            )

        console.print(table)

        # Summary
        running_count = sum(1 for i in instances if i["status"] == "running")
        if running_count < len(instances):
            stale_count = len(instances) - running_count
            console.print(
                f"\n[dim]{running_count} running, {stale_count} stale/unhealthy[/]"
            )

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
