"""Init command for initializing an Agent Brain project."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

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

STATE_DIR_NAME = ".claude/agent-brain"


def resolve_project_root(start_path: Path | None = None) -> Path:
    """Resolve the canonical project root directory.

    Resolution order:
    1. Git repository root (git rev-parse --show-toplevel)
    2. Walk up looking for .claude/ directory
    3. Walk up looking for pyproject.toml
    4. Fall back to cwd

    Args:
        start_path: Starting path for resolution. Defaults to cwd.

    Returns:
        Resolved project root path.
    """
    import subprocess

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
    help="Custom state directory for index data (default: .claude/agent-brain)",
)
def init_command(
    path: str | None,
    host: str,
    port: int | None,
    force: bool,
    json_output: bool,
    state_dir: str | None,
) -> None:
    """Initialize a new Agent Brain project.

    Creates the .claude/agent-brain/ directory structure and writes
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
        # Resolve project root
        if path:
            project_root = Path(path).resolve()
        else:
            project_root = resolve_project_root()

        # Use custom state_dir if provided, otherwise default
        if state_dir:
            resolved_state_dir = Path(state_dir).resolve()
        else:
            resolved_state_dir = project_root / STATE_DIR_NAME
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

        # Write configuration
        config_path.write_text(json.dumps(config, indent=2))

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
            console.print(
                Panel(
                    f"[green]Project initialized successfully![/]\n\n"
                    f"[bold]Project Root:[/] {project_root}\n"
                    f"[bold]State Directory:[/] {resolved_state_dir}\n"
                    f"[bold]Configuration:[/] {config_path}",
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
