"""Index command for triggering document indexing."""

from pathlib import Path

import click
from rich.console import Console

from ..client import ConnectionError, DocServeClient, ServerError

console = Console()


@click.command("index")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--url",
    envvar="DOC_SERVE_URL",
    default="http://127.0.0.1:8000",
    help="Doc-Serve server URL",
)
@click.option(
    "--chunk-size",
    default=512,
    type=int,
    help="Target chunk size in tokens (default: 512)",
)
@click.option(
    "--chunk-overlap",
    default=50,
    type=int,
    help="Overlap between chunks in tokens (default: 50)",
)
@click.option(
    "--no-recursive",
    is_flag=True,
    help="Don't scan folder recursively",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def index_command(
    folder_path: str,
    url: str,
    chunk_size: int,
    chunk_overlap: int,
    no_recursive: bool,
    json_output: bool,
) -> None:
    """Index documents from a folder.

    FOLDER_PATH: Path to the folder containing documents to index.
    """
    # Resolve to absolute path
    folder = Path(folder_path).resolve()

    try:
        with DocServeClient(base_url=url) as client:
            response = client.index(
                folder_path=str(folder),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                recursive=not no_recursive,
            )

            if json_output:
                import json

                output = {
                    "job_id": response.job_id,
                    "status": response.status,
                    "message": response.message,
                    "folder": str(folder),
                }
                click.echo(json.dumps(output, indent=2))
                return

            console.print("\n[green]Indexing started![/]\n")
            console.print(f"[bold]Job ID:[/] {response.job_id}")
            console.print(f"[bold]Folder:[/] {folder}")
            console.print(f"[bold]Status:[/] {response.status}")
            if response.message:
                console.print(f"[bold]Message:[/] {response.message}")

            console.print("\n[dim]Use 'doc-svr-ctl status' to monitor progress.[/]")

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
                    "\n[dim]Indexing is already in progress. "
                    "Wait for it to complete or reset the index.[/]"
                )
        raise SystemExit(1) from e
