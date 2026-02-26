"""Folders command group for managing indexed folders."""

import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..client import ConnectionError, DocServeClient, ServerError
from ..config import get_server_url

console = Console()


@click.group("folders")
def folders_group() -> None:
    """Manage indexed folders. List, add, or remove indexed folders.

    \b
    Examples:
      agent-brain folders list              # Show all indexed folders
      agent-brain folders add ./docs        # Index a new folder
      agent-brain folders remove ./docs     # Remove folder chunks
    """
    pass


@folders_group.command("list")
@click.option(
    "--url",
    envvar="AGENT_BRAIN_URL",
    default=None,
    help="Agent Brain server URL (default: from config or http://127.0.0.1:8000)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def list_folders_cmd(url: str | None, json_output: bool) -> None:
    """List all indexed folders with chunk counts and last indexed time.

    \b
    Examples:
      agent-brain folders list
      agent-brain folders list --json
    """
    resolved_url = url or get_server_url()

    try:
        with DocServeClient(base_url=resolved_url) as client:
            folders = client.list_folders()

            if json_output:
                output = {
                    "folders": [
                        {
                            "folder_path": f.folder_path,
                            "chunk_count": f.chunk_count,
                            "last_indexed": f.last_indexed,
                        }
                        for f in folders
                    ]
                }
                click.echo(json.dumps(output, indent=2))
                return

            if not folders:
                console.print("[dim]No folders indexed yet.[/]")
                return

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("Folder Path", style="bold")
            table.add_column("Chunks", justify="right")
            table.add_column("Last Indexed")

            for folder in folders:
                last_indexed = folder.last_indexed
                # Truncate microseconds for readability
                if "." in last_indexed:
                    last_indexed = last_indexed.split(".")[0]

                table.add_row(
                    folder.folder_path,
                    str(folder.chunk_count),
                    last_indexed,
                )

            console.print(table)

    except ConnectionError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Connection Error:[/] {e}")
        raise SystemExit(1) from e

    except ServerError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e), "detail": e.detail}))
        else:
            console.print(f"[red]Server Error ({e.status_code}):[/] {e.detail}")
        raise SystemExit(1) from e


@folders_group.command("add")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--url",
    envvar="AGENT_BRAIN_URL",
    default=None,
    help="Agent Brain server URL (default: from config or http://127.0.0.1:8000)",
)
@click.option(
    "--include-code",
    is_flag=True,
    help="Index source code files alongside documents",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def add_folder_cmd(
    folder_path: str,
    url: str | None,
    include_code: bool,
    json_output: bool,
) -> None:
    """Index documents from a folder (alias for 'agent-brain index').

    FOLDER_PATH: Path to the folder containing documents to index.

    \b
    Examples:
      agent-brain folders add ./docs
      agent-brain folders add ./src --include-code
    """
    resolved_url = url or get_server_url()
    folder = Path(folder_path).resolve()

    try:
        with DocServeClient(base_url=resolved_url) as client:
            response = client.index(
                folder_path=str(folder),
                include_code=include_code,
            )

            if json_output:
                output = {
                    "job_id": response.job_id,
                    "status": response.status,
                    "message": response.message,
                    "folder": str(folder),
                }
                click.echo(json.dumps(output, indent=2))
                return

            console.print("\n[green]Indexing job queued![/]\n")
            console.print(f"[bold]Job ID:[/] {response.job_id}")
            console.print(f"[bold]Folder:[/] {folder}")
            console.print(f"[bold]Status:[/] {response.status}")
            if response.message:
                console.print(f"[bold]Message:[/] {response.message}")

            console.print("\n[dim]Use 'agent-brain jobs' to monitor progress.[/]")

    except ConnectionError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Connection Error:[/] {e}")
        raise SystemExit(1) from e

    except ServerError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e), "detail": e.detail}))
        else:
            console.print(f"[red]Server Error ({e.status_code}):[/] {e.detail}")
        raise SystemExit(1) from e


@folders_group.command("remove")
@click.argument("folder_path", type=str)
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
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def remove_folder_cmd(
    folder_path: str,
    url: str | None,
    yes: bool,
    json_output: bool,
) -> None:
    """Remove all indexed chunks for a folder.

    FOLDER_PATH: Path to the indexed folder to remove.
    The folder does not need to exist on disk.

    \b
    Examples:
      agent-brain folders remove ./docs --yes
      agent-brain folders remove /absolute/path/to/docs
    """
    resolved_url = url or get_server_url()
    resolved_path = str(Path(folder_path).resolve())

    if not yes:
        click.confirm(
            f"Remove all indexed chunks for {resolved_path}?",
            abort=True,
        )

    try:
        with DocServeClient(base_url=resolved_url) as client:
            result = client.delete_folder(folder_path=resolved_path)

            chunks_deleted = result.get("chunks_deleted", 0)
            message = result.get("message", "")

            if json_output:
                click.echo(json.dumps(result, indent=2))
                return

            console.print(
                f"\n[green]Removed {chunks_deleted} chunks for " f"{resolved_path}[/]"
            )
            if message:
                console.print(f"[dim]{message}[/]")

    except ConnectionError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e)}))
        else:
            console.print(f"[red]Connection Error:[/] {e}")
        raise SystemExit(1) from e

    except ServerError as e:
        if json_output:
            click.echo(json.dumps({"error": str(e), "detail": e.detail}))
        else:
            if e.status_code == 404:
                console.print(
                    f"[yellow]Folder not found:[/] {resolved_path} is not indexed"
                )
            elif e.status_code == 409:
                console.print(
                    "[red]Conflict:[/] An active indexing job is running "
                    "for this folder. Cancel the job first."
                )
            else:
                console.print(f"[red]Server Error ({e.status_code}):[/] {e.detail}")
        raise SystemExit(1) from e
