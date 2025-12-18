"""Reset command for clearing the index."""

import click
from rich.console import Console
from rich.prompt import Confirm

from ..client import ConnectionError, DocServeClient, ServerError

console = Console()


@click.command("reset")
@click.option(
    "--url",
    envvar="DOC_SERVE_URL",
    default="http://127.0.0.1:8000",
    help="Doc-Serve server URL",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def reset_command(url: str, yes: bool, json_output: bool) -> None:
    """Reset the index by deleting all indexed documents.

    WARNING: This permanently removes all indexed content.
    """
    # Confirm unless --yes flag provided
    if not yes and not json_output:
        console.print(
            "[yellow]Warning:[/] This will permanently delete all indexed documents."
        )
        if not Confirm.ask("Are you sure you want to reset the index?"):
            console.print("[dim]Aborted.[/]")
            return

    try:
        with DocServeClient(base_url=url) as client:
            response = client.reset()

            if json_output:
                import json

                output = {
                    "job_id": response.job_id,
                    "status": response.status,
                    "message": response.message,
                }
                click.echo(json.dumps(output, indent=2))
                return

            console.print("\n[green]Index reset successfully![/]")
            if response.message:
                console.print(f"[bold]Message:[/] {response.message}")

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
            if e.status_code == 409:
                console.print(
                    "\n[dim]Cannot reset while indexing is in progress. "
                    "Wait for indexing to complete first.[/]"
                )
        raise SystemExit(1) from e
