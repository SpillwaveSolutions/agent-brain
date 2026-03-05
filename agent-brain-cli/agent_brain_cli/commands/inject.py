"""Inject command for indexing documents with content injection."""

from pathlib import Path

import click
from rich.console import Console

from ..client import ConnectionError, DocServeClient, ServerError
from ..config import get_server_url

console = Console()


@click.command("inject")
@click.argument("folder_path", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--script",
    "injector_script",
    type=click.Path(exists=True),
    default=None,
    help="Python script exporting process_chunk(chunk: dict) -> dict",
)
@click.option(
    "--folder-metadata",
    "folder_metadata",
    type=click.Path(exists=True),
    default=None,
    help="JSON file with static metadata to merge into all chunks",
)
@click.option(
    "--dry-run",
    "dry_run",
    is_flag=True,
    help="Validate injector script against sample chunks without indexing",
)
@click.option(
    "--url",
    envvar="AGENT_BRAIN_URL",
    default=None,
    help="Agent Brain server URL (default: from config or http://127.0.0.1:8000)",
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
@click.option(
    "--include-code",
    is_flag=True,
    help="Index source code files alongside documents",
)
@click.option(
    "--languages",
    help="Comma-separated list of programming languages to index",
)
@click.option(
    "--code-strategy",
    default="ast_aware",
    type=click.Choice(["ast_aware", "text_based"]),
    help="Strategy for chunking code files (default: ast_aware)",
)
@click.option(
    "--include-patterns",
    help="Comma-separated additional include patterns (wildcards supported)",
)
@click.option(
    "--include-type",
    "include_type",
    help=(
        "Comma-separated file type presets to include "
        "(e.g., python,docs,typescript). "
        "Use 'agent-brain types list' to see all available presets."
    ),
)
@click.option(
    "--exclude-patterns",
    help="Comma-separated additional exclude patterns (wildcards supported)",
)
@click.option(
    "--generate-summaries",
    is_flag=True,
    help="Generate LLM summaries for code chunks to improve semantic search",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force re-indexing even if embedding provider has changed",
)
@click.option(
    "--allow-external",
    is_flag=True,
    help="Allow indexing paths outside the project directory",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def inject_command(
    folder_path: str,
    injector_script: str | None,
    folder_metadata: str | None,
    dry_run: bool,
    url: str | None,
    chunk_size: int,
    chunk_overlap: int,
    no_recursive: bool,
    include_code: bool,
    languages: str | None,
    code_strategy: str,
    include_patterns: str | None,
    include_type: str | None,
    exclude_patterns: str | None,
    generate_summaries: bool,
    force: bool,
    allow_external: bool,
    json_output: bool,
) -> None:
    """Index documents from a folder with content injection.

    FOLDER_PATH: Path to the folder containing documents to index.

    At least one of --script or --folder-metadata must be provided.
    """
    # Validate that at least one injection option is provided
    if injector_script is None and folder_metadata is None:
        if json_output:
            import json

            click.echo(
                json.dumps(
                    {
                        "error": (
                            "At least one of --script or --folder-metadata "
                            "must be provided."
                        )
                    }
                )
            )
        else:
            console.print(
                "[red]Error:[/] At least one of --script or --folder-metadata "
                "must be provided."
            )
        raise SystemExit(2)

    # Get URL from config if not specified
    resolved_url = url or get_server_url()

    # Resolve to absolute paths
    folder = Path(folder_path).resolve()
    resolved_script = str(Path(injector_script).resolve()) if injector_script else None
    resolved_metadata = (
        str(Path(folder_metadata).resolve()) if folder_metadata else None
    )

    # Parse comma-separated lists
    languages_list = (
        [lang.strip() for lang in languages.split(",")] if languages else None
    )
    include_patterns_list = (
        [pat.strip() for pat in include_patterns.split(",")]
        if include_patterns
        else None
    )
    include_types_list = (
        [t.strip() for t in include_type.split(",")] if include_type else None
    )
    exclude_patterns_list = (
        [pat.strip() for pat in exclude_patterns.split(",")]
        if exclude_patterns
        else None
    )

    try:
        with DocServeClient(base_url=resolved_url) as client:
            response = client.index(
                folder_path=str(folder),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                recursive=not no_recursive,
                include_code=include_code,
                supported_languages=languages_list,
                code_chunk_strategy=code_strategy,
                include_patterns=include_patterns_list,
                include_types=include_types_list,
                exclude_patterns=exclude_patterns_list,
                generate_summaries=generate_summaries,
                force=force,
                allow_external=allow_external,
                injector_script=resolved_script,
                folder_metadata_file=resolved_metadata,
                dry_run=dry_run,
            )

            if json_output:
                import json

                output = {
                    "job_id": response.job_id,
                    "status": response.status,
                    "message": response.message,
                    "folder": str(folder),
                    "dry_run": dry_run,
                }
                click.echo(json.dumps(output, indent=2))
                return

            if dry_run:
                console.print("\n[cyan]Dry-run validation complete.[/]\n")
                console.print(f"[bold]Folder:[/] {folder}")
                if response.message:
                    console.print(f"[bold]Report:[/] {response.message}")
                console.print(f"[bold]Status:[/] {response.status}")
            else:
                console.print("\n[green]Inject job queued![/]\n")
                console.print(f"[bold]Job ID:[/] {response.job_id}")
                console.print(f"[bold]Folder:[/] {folder}")
                console.print(f"[bold]Status:[/] {response.status}")
                if resolved_script:
                    console.print(f"[bold]Injector Script:[/] {resolved_script}")
                if resolved_metadata:
                    console.print(f"[bold]Folder Metadata:[/] {resolved_metadata}")
                if include_type:
                    console.print(f"[bold]Include Types:[/] {include_type}")
                if response.message:
                    if "Duplicate" in (response.message or ""):
                        console.print(f"[yellow]Note:[/] {response.message}")
                    else:
                        console.print(f"[bold]Message:[/] {response.message}")

                console.print(
                    "\n[dim]Use 'agent-brain jobs' or 'agent-brain jobs --watch' "
                    "to monitor progress.[/]"
                )

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
            if e.status_code == 429:
                console.print(
                    "\n[dim]The job queue is full. "
                    "Wait for some jobs to complete and try again.[/]"
                )
            elif e.status_code == 409:
                console.print(
                    "\n[dim]A conflict occurred. "
                    "Check 'agent-brain jobs' for queue status.[/]"
                )
        raise SystemExit(1) from e
