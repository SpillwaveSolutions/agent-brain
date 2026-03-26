"""Config commands for viewing and managing Agent Brain configuration."""

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.table import Table

from agent_brain_cli.config_migrate import (
    MigrationResult,
    diff_config_file,
    migrate_config_file,
)
from agent_brain_cli.config_schema import (
    format_validation_errors,
    validate_config_file,
)
from agent_brain_cli.xdg_paths import get_xdg_config_dir

console = Console()


EMBEDDING_DEFAULT_MODELS = {
    "openai": "text-embedding-3-large",
    "ollama": "nomic-embed-text",
    "cohere": "embed-english-v3.0",
}

SUMMARIZATION_DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-5-mini",
    "ollama": "llama3.2:latest",
    "gemini": "gemini-3-flash",
}


def _find_available_api_port(start: int = 8000, end: int = 8300) -> int:
    """Find an available TCP port in an inclusive range."""
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise click.ClickException(f"No available ports found in range {start}-{end}")


def _find_config_file() -> Path | None:
    """Find the configuration file in standard locations.

    Search order:
    1. AGENT_BRAIN_CONFIG environment variable
    2. State directory config.yaml (if AGENT_BRAIN_STATE_DIR set)
    3. Current directory config.yaml
    4. Walk up from CWD: .agent-brain/config.yaml (or legacy path)
    5. XDG config ~/.config/agent-brain/config.yaml (preferred)
    6. Legacy ~/.agent-brain/config.yaml (deprecated, prints warning)

    Returns:
        Path to config file or None if not found
    """
    # 1. Environment variable override
    env_config = os.getenv("AGENT_BRAIN_CONFIG")
    if env_config:
        path = Path(env_config)
        if path.exists():
            return path

    # 2. State directory
    state_dir = os.getenv("AGENT_BRAIN_STATE_DIR") or os.getenv("DOC_SERVE_STATE_DIR")
    if state_dir:
        state_config = Path(state_dir) / "config.yaml"
        if state_config.exists():
            return state_config

    # 3. Current directory
    cwd_config = Path.cwd() / "config.yaml"
    if cwd_config.exists():
        return cwd_config

    # 4. Walk up from CWD looking for .agent-brain/ or legacy .claude/agent-brain/
    current = Path.cwd()
    root = Path(current.anchor)
    while current != root:
        new_config = current / ".agent-brain" / "config.yaml"
        if new_config.exists():
            return new_config
        legacy_config = current / ".claude" / "agent-brain" / "config.yaml"
        if legacy_config.exists():
            return legacy_config
        current = current.parent

    # 5. XDG config (checked before legacy per XDG standard)
    xdg_config_path = get_xdg_config_dir() / "config.yaml"
    if xdg_config_path.exists():
        return xdg_config_path

    xdg_alt = get_xdg_config_dir() / "agent-brain.yaml"
    if xdg_alt.exists():
        return xdg_alt

    # 6. Legacy path ~/.agent-brain/ (deprecated, fallback only)
    home_config = Path.home() / ".agent-brain" / "config.yaml"
    if home_config.exists():
        sys.stderr.write(
            "Warning: Using legacy config path ~/.agent-brain/config.yaml. "
            "Run 'agent-brain start' to migrate to ~/.config/agent-brain/.\n"
        )
        return home_config

    home_alt = Path.home() / ".agent-brain" / "agent-brain.yaml"
    if home_alt.exists():
        sys.stderr.write(
            "Warning: Using legacy config path ~/.agent-brain/agent-brain.yaml. "
            "Run 'agent-brain start' to migrate to ~/.config/agent-brain/.\n"
        )
        return home_alt

    return None


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML configuration file."""
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _resolve_wizard_config_path() -> Path:
    """Resolve output path for config wizard.

    Returns:
        Path to .agent-brain/config.yaml in nearest existing state dir,
        or creates .agent-brain/config.yaml in current working directory.
    """
    current = Path.cwd()
    root = Path(current.anchor)

    while True:
        state_dir = current / ".agent-brain"
        if state_dir.is_dir():
            return state_dir / "config.yaml"

        if current == root:
            break
        current = current.parent

    return Path.cwd() / ".agent-brain" / "config.yaml"


@click.group("config")
def config_group() -> None:
    """View and manage Agent Brain configuration.

    \b
    Commands:
      show     - Display active configuration
      path     - Show config file location
      wizard   - Create/update config interactively
      validate - Validate config against schema
      migrate  - Upgrade config to current schema
      diff     - Preview what migrate would change
    """
    pass


@config_group.command("wizard")
def wizard() -> None:
    """Interactive configuration wizard for Agent Brain providers."""
    # Check existing config for validation issues before prompting
    existing_config = _find_config_file()
    if existing_config:
        existing_errors = validate_config_file(existing_config)
        if existing_errors:
            console.print(
                "\n[bold yellow]Warning:[/] Existing config has validation issues:"
            )
            console.print(format_validation_errors(existing_errors))
            console.print()

    embed_provider: str = click.prompt(
        "Embedding provider",
        type=click.Choice(["openai", "ollama", "cohere"]),
        default="openai",
    )
    embed_model: str = click.prompt(
        "Embedding model",
        default=EMBEDDING_DEFAULT_MODELS[embed_provider],
    )

    batch_size: str | None = None
    request_delay_ms: int | None = None
    if embed_provider == "ollama":
        batch_size = click.prompt(
            "Batch size",
            type=click.Choice(["1", "5", "10", "20", "50", "100"]),
            default="10",
        )
        request_delay_ms = click.prompt(
            "Request delay between batches (ms, 0=none)",
            type=click.IntRange(min=0),
            default=0,
        )

    summ_provider: str = click.prompt(
        "Summarization provider",
        type=click.Choice(["anthropic", "openai", "ollama", "gemini"]),
        default="anthropic",
    )
    summ_model: str = click.prompt(
        "Summarization model",
        default=SUMMARIZATION_DEFAULT_MODELS[summ_provider],
    )

    graphrag_mode: str = click.prompt(
        "GraphRAG mode\n"
        "1) Disabled\n"
        "2) AST for code + LangExtract for docs (recommended for mixed repos)\n"
        "3) Kuzu + AST for code + LangExtract for docs\n"
        "4) AST for code only",
        type=click.Choice(["1", "2", "3", "4"]),
        default="1",
    )

    suggested_port = _find_available_api_port(8000, 8300)
    click.echo(f"Discovered available API port in 8000-8300 range: {suggested_port}")

    deployment_mode: str = click.prompt(
        "Deployment mode\n"
        "1) Localhost only (127.0.0.1)\n"
        "2) Network accessible (0.0.0.0 or custom host)\n"
        "3) Custom port on localhost",
        type=click.Choice(["1", "2", "3"]),
        default="1",
    )

    api_host = "127.0.0.1"
    if deployment_mode == "2":
        host_mode: str = click.prompt(
            "Host selection\n" "1) 0.0.0.0\n" "2) Custom host/IP",
            type=click.Choice(["1", "2"]),
            default="1",
        )
        if host_mode == "1":
            api_host = "0.0.0.0"
        else:
            api_host = click.prompt("Custom host", default="0.0.0.0")

    api_port: int = click.prompt(
        "API port",
        type=click.IntRange(min=1, max=65535),
        default=suggested_port,
    )

    config: dict[str, Any] = {
        "embedding": {
            "provider": embed_provider,
            "model": embed_model,
        },
        "summarization": {
            "provider": summ_provider,
            "model": summ_model,
        },
        "graphrag": {
            "enabled": False,
        },
        "api": {
            "host": api_host,
            "port": api_port,
        },
    }

    if embed_provider == "ollama":
        config["embedding"]["params"] = {
            "batch_size": int(batch_size or "10"),
            "request_delay_ms": int(request_delay_ms or 0),
        }

    if graphrag_mode == "2":
        config["graphrag"] = {
            "enabled": True,
            "store_type": "simple",
            "use_code_metadata": True,
            "doc_extractor": "langextract",
        }
    elif graphrag_mode == "3":
        config["graphrag"] = {
            "enabled": True,
            "store_type": "kuzu",
            "use_code_metadata": True,
            "doc_extractor": "langextract",
        }
    elif graphrag_mode == "4":
        config["graphrag"] = {
            "enabled": True,
            "store_type": "simple",
            "use_code_metadata": True,
        }

    config_path = _resolve_wizard_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

    console.print(f"[green]Config written to {config_path}[/]")

    # Validate the written config and warn if issues found
    post_write_errors = validate_config_file(config_path)
    if post_write_errors:
        console.print(
            "\n[bold yellow]Warning:[/] The generated config has validation issues:\n"
        )
        console.print(format_validation_errors(post_write_errors))
        if not click.confirm("Continue with this config anyway?", default=False):
            console.print(
                "[red]Config wizard aborted."
                " Please fix the issues and try again.[/]"
            )
            sys.exit(1)


@config_group.command("show")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def show_config(json_output: bool) -> None:
    """Display the active provider configuration.

    Shows which config file is being used and the current provider settings
    for embedding, summarization, and reranking.

    \b
    Examples:
      agent-brain config show           # Rich formatted output
      agent-brain config show --json    # JSON output for scripting
    """
    config_path = _find_config_file()

    if json_output:
        output: dict[str, Any] = {
            "config_file": str(config_path) if config_path else None,
            "config_source": "file" if config_path else "defaults",
        }

        if config_path:
            config = _load_yaml(config_path)
            output["embedding"] = config.get("embedding", {})
            output["summarization"] = config.get("summarization", {})
            output["reranker"] = config.get("reranker", {})
        else:
            output["embedding"] = {
                "provider": "openai",
                "model": "text-embedding-3-large",
            }
            output["summarization"] = {
                "provider": "anthropic",
                "model": "claude-haiku-4-5-20251001",
            }

        click.echo(json.dumps(output, indent=2))
        return

    # Rich formatted output
    if config_path:
        console.print(f"\n[bold]Config file:[/] {config_path}\n")
        config = _load_yaml(config_path)
    else:
        console.print("\n[yellow]No config file found, using defaults[/]\n")
        config = {}

    # Embedding provider
    embedding = config.get("embedding", {})
    embed_table = Table(title="Embedding Provider", show_header=False)
    embed_table.add_column("Setting", style="cyan")
    embed_table.add_column("Value")
    embed_table.add_row("Provider", embedding.get("provider", "openai"))
    embed_table.add_row("Model", embedding.get("model", "text-embedding-3-large"))
    embed_table.add_row("API Key Env", embedding.get("api_key_env", "OPENAI_API_KEY"))
    if embedding.get("base_url"):
        embed_table.add_row("Base URL", embedding["base_url"])
    console.print(embed_table)

    # Summarization provider
    summarization = config.get("summarization", {})
    summ_table = Table(title="Summarization Provider", show_header=False)
    summ_table.add_column("Setting", style="cyan")
    summ_table.add_column("Value")
    summ_table.add_row("Provider", summarization.get("provider", "anthropic"))
    summ_table.add_row("Model", summarization.get("model", "claude-haiku-4-5-20251001"))
    summ_table.add_row(
        "API Key Env", summarization.get("api_key_env", "ANTHROPIC_API_KEY")
    )
    if summarization.get("base_url"):
        summ_table.add_row("Base URL", summarization["base_url"])
    console.print(summ_table)

    # Reranker (if configured)
    reranker = config.get("reranker", {})
    if reranker:
        rerank_table = Table(title="Reranker Provider", show_header=False)
        rerank_table.add_column("Setting", style="cyan")
        rerank_table.add_column("Value")
        rerank_table.add_row(
            "Provider", reranker.get("provider", "sentence-transformers")
        )
        rerank_table.add_row(
            "Model", reranker.get("model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        )
        if reranker.get("base_url"):
            rerank_table.add_row("Base URL", reranker["base_url"])
        console.print(rerank_table)

    console.print()


@config_group.command("path")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def config_path(json_output: bool) -> None:
    """Show the path to the active config file.

    \b
    Examples:
      agent-brain config path           # Print config file path
      agent-brain config path --json    # JSON output
    """
    config_path = _find_config_file()

    if json_output:
        click.echo(
            json.dumps(
                {
                    "config_file": str(config_path) if config_path else None,
                    "exists": config_path.exists() if config_path else False,
                }
            )
        )
        return

    if config_path:
        console.print(f"[green]{config_path}[/]")
    else:
        console.print("[yellow]No config file found[/]")


@config_group.command("validate")
@click.option(
    "--file",
    "config_file",
    type=click.Path(exists=True),
    default=None,
    help="Path to config file (default: auto-detect)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def validate_config(config_file: str | None, json_output: bool) -> None:
    """Validate config.yaml against the Agent Brain schema.

    Checks for unknown keys, invalid provider values, deprecated fields,
    and type errors. Reports line numbers and fix suggestions.

    \b
    Examples:
      agent-brain config validate
      agent-brain config validate --file ./my-config.yaml
      agent-brain config validate --json
    """
    if config_file is not None:
        path: Path | None = Path(config_file)
    else:
        path = _find_config_file()

    if path is None:
        if json_output:
            click.echo(
                json.dumps(
                    {
                        "valid": None,
                        "config_file": None,
                        "errors": [],
                        "message": "No config file found",
                    }
                )
            )
        else:
            console.print("[yellow]No config file found. Nothing to validate.[/]")
        sys.exit(0)

    errors = validate_config_file(path)

    if json_output:
        output: dict[str, Any] = {
            "valid": len(errors) == 0,
            "config_file": str(path),
            "errors": [
                {
                    "field": e.field,
                    "message": e.message,
                    "line_number": e.line_number,
                    "suggestion": e.suggestion,
                }
                for e in errors
            ],
        }
        click.echo(json.dumps(output, indent=2))
        if errors:
            sys.exit(1)
        return

    if not errors:
        console.print(f"[green]Config is valid[/] ({path})")
        sys.exit(0)

    console.print(format_validation_errors(errors))
    sys.exit(1)


@config_group.command("migrate")
@click.option(
    "--file",
    "config_file",
    type=click.Path(exists=True),
    default=None,
    help="Path to config file (default: auto-detect)",
)
@click.option(
    "--dry-run", is_flag=True, help="Show what would change without modifying"
)
def migrate_config_cmd(config_file: str | None, dry_run: bool) -> None:
    """Migrate config.yaml to the current schema version.

    Upgrades deprecated keys and restructures config sections.
    Use --dry-run to preview changes without modifying the file.

    \b
    Examples:
      agent-brain config migrate
      agent-brain config migrate --dry-run
      agent-brain config migrate --file ./old-config.yaml
    """
    if config_file is not None:
        path: Path | None = Path(config_file)
    else:
        path = _find_config_file()

    if path is None:
        console.print("[yellow]No config file found.[/]")
        sys.exit(0)

    if dry_run:
        diff = diff_config_file(path)
        if diff:
            console.print(diff)
        else:
            console.print("[green]Config is already up to date. No changes needed.[/]")
        sys.exit(0)

    result: MigrationResult = migrate_config_file(path)
    if result.already_current:
        console.print("[green]Config is already up to date[/]")
        sys.exit(0)

    for change in result.changes:
        console.print(f"  [cyan]->[/] {change}")
    console.print(f"\n[green]Config migrated successfully[/] ({path})")


@config_group.command("diff")
@click.option(
    "--file",
    "config_file",
    type=click.Path(exists=True),
    default=None,
    help="Path to config file (default: auto-detect)",
)
def diff_config_cmd(config_file: str | None) -> None:
    """Show what 'config migrate' would change.

    Displays a unified diff of the current config vs the migrated version.

    \b
    Examples:
      agent-brain config diff
      agent-brain config diff --file ./config.yaml
    """
    if config_file is not None:
        path: Path | None = Path(config_file)
    else:
        path = _find_config_file()

    if path is None:
        console.print("[yellow]No config file found.[/]")
        sys.exit(0)

    diff = diff_config_file(path)
    if not diff:
        console.print("[green]Config is already up to date. No changes needed.[/]")
        sys.exit(0)

    for line in diff.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            console.print(f"[bold]{line}[/]")
        elif line.startswith("-"):
            console.print(f"[red]{line}[/]")
        elif line.startswith("+"):
            console.print(f"[green]{line}[/]")
        elif line.startswith("@@"):
            console.print(f"[cyan]{line}[/]")
        else:
            console.print(line)
