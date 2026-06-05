"""Init command for initializing an Agent Brain project."""

import json
import secrets
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from agent_brain_cli.config import resolve_project_root
from agent_brain_cli.migration import migrate_state_dir
from agent_brain_cli.xdg_paths import migrate_legacy_paths

console = Console()

# Default configuration values for config.json (project settings only)
# Provider settings (embedding/summarization) go in config.yaml
DEFAULT_CONFIG = {
    "bind_host": "127.0.0.1",
    "port_range_start": 8000,
    "port_range_end": 8100,
    "auto_port": True,
    "chunk_size": 512,
    "chunk_overlap": 50,
    # Directories to exclude from indexing (glob patterns)
    "exclude_patterns": [
        "**/node_modules/**",
        "**/__pycache__/**",
        "**/.venv/**",
        "**/venv/**",
        "**/.git/**",
        "**/dist/**",
        "**/build/**",
        "**/target/**",
    ],
}

STATE_DIR_NAME = ".agent-brain"


@click.command("init")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    help="Project path (default: auto-detect project root)",
)
@click.option(
    "--host",
    default=DEFAULT_CONFIG["bind_host"],
    help=f"Server bind host (default: {DEFAULT_CONFIG['bind_host']})",
)
@click.option(
    "--port",
    type=int,
    default=None,
    help="Preferred server port (default: auto-select from range)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Overwrite existing configuration",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option(
    "--state-dir",
    "-s",
    type=click.Path(file_okay=False, resolve_path=True),
    help="Custom state directory for index data (default: .agent-brain)",
)
@click.option(
    "--no-api-key",
    is_flag=True,
    help=(
        "Skip auto-generating an API key (Issue #179). Use for single-user "
        "loopback dev when no auth is desired. Server still starts without auth."
    ),
)
def init_command(
    path: str | None,
    host: str,
    port: int | None,
    force: bool,
    json_output: bool,
    state_dir: str | None,
    no_api_key: bool,
) -> None:
    """Initialize a new Agent Brain project.

    Creates the .agent-brain/ directory structure and writes
    a default config.json file.

    \b
    Examples:
      agent-brain init                              # Initialize in current project
      agent-brain init --path /my/project           # Initialize specific project
      agent-brain init --port 8080                  # Set preferred port
      agent-brain init --state-dir /custom/path     # Custom storage location
      agent-brain init --force                      # Overwrite existing config
    """
    try:
        # Trigger one-time migration from legacy ~/.agent-brain to XDG dirs
        migrate_legacy_paths()

        # Resolve project root
        if path:
            project_root = Path(path).resolve()
        else:
            project_root = resolve_project_root()

        # Use custom state_dir if provided, otherwise default
        if state_dir:
            resolved_state_dir = Path(state_dir).resolve()
        else:
            # Auto-migrate from legacy .claude/agent-brain if needed
            resolved_state_dir = migrate_state_dir(project_root)
        config_path = resolved_state_dir / "config.json"

        # Check for existing configuration
        if config_path.exists() and not force:
            if json_output:
                click.echo(
                    json.dumps(
                        {
                            "error": "Configuration already exists",
                            "path": str(config_path),
                            "hint": "Use --force to overwrite",
                        }
                    )
                )
            else:
                console.print(f"[yellow]Configuration already exists:[/] {config_path}")
                console.print(
                    "[dim]Use --force to overwrite existing configuration.[/]"
                )
            raise SystemExit(1)

        # Create state directory structure
        resolved_state_dir.mkdir(parents=True, exist_ok=True)
        (resolved_state_dir / "data").mkdir(exist_ok=True)
        (resolved_state_dir / "data" / "chroma_db").mkdir(exist_ok=True)
        (resolved_state_dir / "data" / "bm25_index").mkdir(exist_ok=True)
        (resolved_state_dir / "data" / "llamaindex").mkdir(exist_ok=True)
        (resolved_state_dir / "logs").mkdir(exist_ok=True)

        # Build configuration
        config = {
            **DEFAULT_CONFIG,
            "bind_host": host,
            "project_root": str(project_root),
        }
        if port is not None:
            config["port"] = port
            config["auto_port"] = False

        # Issue #179: auto-generate an API key so the server boots with auth
        # by default. Stored in config.json (project-local); the `start`
        # command exports it as AGENT_BRAIN_API_KEY for the server
        # subprocess, and `resolve_api_key` reads it for the CLI side. Opt
        # out with --no-api-key for single-user loopback workflows.
        if not no_api_key:
            config["api_key"] = secrets.token_urlsafe(32)

        # Write configuration with mode 0o600 since it may carry a secret.
        config_path.write_text(json.dumps(config, indent=2))
        try:
            config_path.chmod(0o600)
        except OSError:
            # Best-effort; filesystems without POSIX modes (FAT) still work.
            pass

        if json_output:
            click.echo(
                json.dumps(
                    {
                        "status": "initialized",
                        "project_root": str(project_root),
                        "state_dir": str(resolved_state_dir),
                        "config_path": str(config_path),
                        "config": config,
                    },
                    indent=2,
                )
            )
        else:
            api_key_note = (
                f"[bold]API Key:[/] generated ({config_path.name}, mode 0o600)"
                if not no_api_key
                else "[bold]API Key:[/] [yellow]disabled[/] (--no-api-key)"
            )
            console.print(
                Panel(
                    f"[green]Project initialized successfully![/]\n\n"
                    f"[bold]Project Root:[/] {project_root}\n"
                    f"[bold]State Directory:[/] {resolved_state_dir}\n"
                    f"[bold]Configuration:[/] {config_path}\n"
                    f"{api_key_note}",
                    title="Agent Brain Initialized",
                    border_style="green",
                )
            )
            console.print("\n[dim]Next steps:[/]")
            console.print("  1. Run [bold]agent-brain start[/] to start the server")
            console.print(
                "  2. Run [bold]agent-brain index ./docs[/] to index documents"
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
