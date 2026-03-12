"""Cache command group for managing the embedding cache."""

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from ..client import ConnectionError, DocServeClient, ServerError
from ..config import get_server_url

console = Console()


@click.group("cache")
def cache_group() -> None:
    """Manage the embedding cache."""
    pass


@cache_group.command("status")
@click.option(
    "--url",
    envvar="AGENT_BRAIN_URL",
    default=None,
    help="Agent Brain server URL (default: from config or http://127.0.0.1:8000)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def cache_status(url: str | None, json_output: bool) -> None:
    """Show embedding cache statistics."""
    resolved_url = url or get_server_url()
    try:
        with DocServeClient(base_url=resolved_url) as client:
            data = client.cache_status()

            if json_output:
                import json

                click.echo(json.dumps(data, indent=2))
                return

            entry_count = data.get("entry_count", 0)
            hit_rate = data.get("hit_rate", 0.0)
            hits = data.get("hits", 0)
            misses = data.get("misses", 0)
            mem_entries = data.get("mem_entries", 0)
            size_bytes = data.get("size_bytes", 0)
            size_mb = size_bytes / (1024 * 1024) if size_bytes else 0.0

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Metric", style="dim")
            table.add_column("Value")

            table.add_row("Entries (disk)", f"{entry_count:,}")
            table.add_row("Entries (memory)", f"{mem_entries:,}")
            table.add_row("Hit Rate", f"{hit_rate:.1%}")
            table.add_row("Hits", f"{hits:,}")
            table.add_row("Misses", f"{misses:,}")
            table.add_row("Size", f"{size_mb:.2f} MB")

            console.print(table)

    except ConnectionError as e:
        if json_output:
            import json

            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Connection Error:[/] {e}")
        raise SystemExit(1) from e

    except ServerError as e:
        if json_output:
            import json

            click.echo(json.dumps({"error": str(e), "detail": e.detail}))
        else:
            console.print(f"[red]Server Error ({e.status_code}):[/] {e.detail}")
        raise SystemExit(1) from e


@cache_group.command("clear")
@click.option(
    "--url",
    envvar="AGENT_BRAIN_URL",
    default=None,
    help="Agent Brain server URL (default: from config or http://127.0.0.1:8000)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def cache_clear(url: str | None, yes: bool) -> None:
    """Clear all cached embeddings from the cache.

    Without --yes, shows the current entry count and prompts for confirmation.
    """
    resolved_url = url or get_server_url()
    try:
        with DocServeClient(base_url=resolved_url) as client:
            if not yes:
                # Get current count before asking
                try:
                    status_data = client.cache_status()
                    count = status_data.get("entry_count", 0)
                except (ConnectionError, ServerError):
                    count = 0

                if not Confirm.ask(
                    f"This will flush {count:,} cached embeddings. Continue?",
                    default=False,
                ):
                    console.print("[dim]Aborted.[/]")
                    return

            result = client.clear_cache()
            cleared_count = result.get("count", 0)
            size_mb = result.get("size_mb", 0.0)
            console.print(
                f"[green]Cleared {cleared_count:,} cached embeddings "
                f"({size_mb:.1f} MB freed)[/]"
            )

    except ConnectionError as e:
        console.print(f"[red]Connection Error:[/] {e}")
        raise SystemExit(1) from e

    except ServerError as e:
        console.print(f"[red]Server Error ({e.status_code}):[/] {e.detail}")
        raise SystemExit(1) from e
