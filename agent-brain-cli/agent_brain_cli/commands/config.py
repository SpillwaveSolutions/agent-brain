"""Config commands for viewing and managing Agent Brain configuration."""

import json
import os
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from agent_brain_cli.xdg_paths import get_xdg_config_dir

console = Console()


def _find_config_file() -> Path | None:
    """Find the configuration file in standard locations.

    Search order:
    1. AGENT_BRAIN_CONFIG environment variable
    2. State directory config.yaml (if AGENT_BRAIN_STATE_DIR set)
    3. Current directory config.yaml
    4. Walk up from CWD looking for .claude/agent-brain/config.yaml
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

    # 4. Walk up from CWD
    current = Path.cwd()
    root = Path(current.anchor)
    while current != root:
        claude_config = current / ".claude" / "agent-brain" / "config.yaml"
        if claude_config.exists():
            return claude_config
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
    import yaml

    with open(path) as f:
        return yaml.safe_load(f) or {}


@click.group("config")
def config_group() -> None:
    """View and manage Agent Brain configuration.

    \b
    Commands:
      show   - Display active configuration
      path   - Show config file location
    """
    pass


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
