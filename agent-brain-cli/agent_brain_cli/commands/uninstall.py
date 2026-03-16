"""Uninstall command for removing all global Agent Brain data."""

import json
import os
import shutil
import signal
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.prompt import Confirm

from agent_brain_cli.xdg_paths import (
    LEGACY_DIR,
    get_registry_path,
    get_xdg_config_dir,
    get_xdg_state_dir,
)

console = Console()


def _read_registry(registry_path: Path) -> dict[str, Any]:
    """Read registry.json from given path.

    Args:
        registry_path: Path to registry.json file.

    Returns:
        Registry dict, or empty dict if file is missing or unreadable.
    """
    if not registry_path.exists():
        return {}
    try:
        result: dict[str, Any] = json.loads(registry_path.read_text())
        return result
    except Exception:
        return {}


def _read_runtime(state_dir: Path) -> dict[str, Any] | None:
    """Read runtime.json from state directory.

    Args:
        state_dir: Path to project state directory.

    Returns:
        Runtime dict or None if not found.
    """
    runtime_path = state_dir / "runtime.json"
    if not runtime_path.exists():
        return None
    try:
        result: dict[str, Any] = json.loads(runtime_path.read_text())
        return result
    except Exception:
        return None


def _stop_servers(registry: dict[str, Any]) -> int:
    """Send SIGTERM to all running server processes in registry.

    Args:
        registry: Registry dict with project entries.

    Returns:
        Count of servers that received SIGTERM.
    """
    stopped = 0
    for _project_root, entry in registry.items():
        state_dir = Path(entry.get("state_dir", ""))
        if not state_dir.exists():
            continue
        runtime = _read_runtime(state_dir)
        if not runtime:
            continue
        pid = runtime.get("pid")
        if not pid:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            stopped += 1
        except (ProcessLookupError, PermissionError):
            pass

    if stopped > 0:
        time.sleep(0.5)  # Brief wait for graceful shutdown

    return stopped


@click.command("uninstall")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def uninstall_command(yes: bool, json_output: bool) -> None:
    """Remove all global Agent Brain data and stop running servers.

    Removes:
      - ~/.config/agent-brain/    (XDG config directory)
      - ~/.local/state/agent-brain/  (XDG state directory)
      - ~/.agent-brain/           (legacy directory, if present)

    Does NOT remove project-level .agent-brain/ directories.

    \b
    Examples:
      agent-brain uninstall           # Prompt for confirmation
      agent-brain uninstall --yes     # Skip confirmation
      agent-brain uninstall --json    # JSON output
    """
    # Collect directories to remove (only existing ones)
    dirs_to_remove: list[Path] = []
    for d in [get_xdg_config_dir(), get_xdg_state_dir(), LEGACY_DIR]:
        if d.exists():
            dirs_to_remove.append(d)

    if not dirs_to_remove:
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "nothing_to_remove",
                        "removed": [],
                        "servers_stopped": 0,
                    }
                )
            )
        else:
            console.print(
                "[dim]Nothing to remove. Agent Brain is not installed globally.[/]"
            )
        return

    # Prompt for confirmation unless --yes or --json
    if not yes and not json_output:
        console.print(
            "[yellow]Warning:[/] This will permanently remove all global "
            "Agent Brain data:\n"
        )
        for d in dirs_to_remove:
            console.print(f"  [red]✗[/] {d}")
        console.print()
        if not Confirm.ask("Remove all Agent Brain global data?", default=False):
            console.print("[dim]Aborted.[/]")
            return

    # Stop running servers before removing directories
    registry_path = get_registry_path()
    registry = _read_registry(registry_path)
    servers_stopped = _stop_servers(registry)

    # Remove directories
    removed: list[str] = []
    for d in dirs_to_remove:
        try:
            shutil.rmtree(d, ignore_errors=True)
            removed.append(str(d))
        except OSError:
            pass

    # Report results
    if json_output:
        click.echo(
            json.dumps(
                {
                    "status": "uninstalled",
                    "removed": removed,
                    "servers_stopped": servers_stopped,
                },
                indent=2,
            )
        )
    else:
        console.print("\n[green]Agent Brain global data removed:[/]")
        for path in removed:
            console.print(f"  [dim]removed:[/] {path}")
        if servers_stopped > 0:
            console.print(f"\n[dim]Stopped {servers_stopped} running server(s).[/]")
