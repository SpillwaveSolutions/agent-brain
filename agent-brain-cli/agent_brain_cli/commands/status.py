"""Status command for checking server health."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..client import ConnectionError, DocServeClient, ServerError
from ..config import get_server_url

console = Console()


@click.command("status")
@click.option(
    "--url",
    envvar="AGENT_BRAIN_URL",
    default=None,
    help="Agent Brain server URL (default: from config or http://127.0.0.1:8000)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def status_command(url: str | None, json_output: bool) -> None:
    """Check Agent Brain server status and health."""
    resolved_url = url or get_server_url()
    try:
        with DocServeClient(base_url=resolved_url) as client:
            health = client.health()
            indexing = client.status()

            if json_output:
                import json

                output = {
                    "health": {
                        "status": health.status,
                        "message": health.message,
                        "version": health.version,
                    },
                    "indexing": {
                        "total_documents": indexing.total_documents,
                        "total_chunks": indexing.total_chunks,
                        "indexing_in_progress": indexing.indexing_in_progress,
                        "progress_percent": indexing.progress_percent,
                        "indexed_folders": indexing.indexed_folders,
                    },
                }
                click.echo(json.dumps(output, indent=2))
                return

            # Determine status color
            status_color = {
                "healthy": "green",
                "indexing": "yellow",
                "degraded": "orange3",
                "unhealthy": "red",
            }.get(health.status, "white")

            # Create status panel
            status_text = f"[bold {status_color}]{health.status.upper()}[/]"
            if health.message:
                status_text += f"\n{health.message}"

            console.print(
                Panel(status_text, title="Server Status", border_style=status_color)
            )

            # Create info table
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Metric", style="dim")
            table.add_column("Value")

            table.add_row("Server Version", health.version)
            table.add_row("Total Documents", str(indexing.total_documents))
            table.add_row("Total Chunks", str(indexing.total_chunks))

            if indexing.indexing_in_progress:
                table.add_row(
                    "Indexing Progress", f"[yellow]{indexing.progress_percent:.1f}%[/]"
                )
                if indexing.current_job_id:
                    table.add_row("Current Job", indexing.current_job_id)
            else:
                table.add_row("Indexing", "[green]Idle[/]")

            if indexing.indexed_folders:
                table.add_row(
                    "Indexed Folders",
                    "\n".join(indexing.indexed_folders[:5])
                    + (
                        f"\n... and {len(indexing.indexed_folders) - 5} more"
                        if len(indexing.indexed_folders) > 5
                        else ""
                    ),
                )

            if indexing.last_indexed_at:
                table.add_row("Last Indexed", indexing.last_indexed_at)

            # Show graph index status if available (Feature 113)
            graph_status = getattr(indexing, "graph_index", None)
            if graph_status:
                if graph_status.get("enabled"):
                    entities = graph_status.get("entity_count", 0)
                    rels = graph_status.get("relationship_count", 0)
                    table.add_row(
                        "Graph Index",
                        f"[green]Enabled[/] - {entities} entities, {rels} rels",
                    )
                else:
                    table.add_row("Graph Index", "[dim]Disabled[/]")

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
