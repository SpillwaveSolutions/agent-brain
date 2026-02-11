"""Jobs command for viewing and managing the job queue."""

import time
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..client import ConnectionError, DocServeClient, ServerError
from ..config import get_server_url

console = Console()


def _format_timestamp(ts: str | None) -> str:
    """Format a timestamp for display, handling None values."""
    if not ts:
        return "-"
    # Truncate to seconds if it has microseconds
    if "." in ts:
        ts = ts.split(".")[0]
    return ts


def _format_progress(progress: float | None, total: int | None) -> str:
    """Format progress for display."""
    if progress is None:
        return "-"
    if total:
        return f"{progress:.1f}% ({total} files)"
    return f"{progress:.1f}%"


def _get_status_style(status: str) -> str:
    """Get Rich style for a job status."""
    styles = {
        "queued": "yellow",
        "pending": "yellow",
        "running": "cyan",
        "in_progress": "cyan",
        "completed": "green",
        "done": "green",
        "failed": "red",
        "error": "red",
        "cancelled": "dim",
        "canceled": "dim",
    }
    return styles.get(status.lower(), "white")


def _create_jobs_table(jobs: list[dict[str, Any]]) -> Table:
    """Create a Rich table for displaying jobs."""
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Status")
    table.add_column("Folder", max_width=40)
    table.add_column("Progress", justify="right")
    table.add_column("Enqueued")
    table.add_column("Started")
    table.add_column("Error", max_width=30)

    for job in jobs:
        job_id = job.get("job_id", job.get("id", ""))[:12]
        status = job.get("status", "unknown")
        status_style = _get_status_style(status)
        folder = job.get("folder_path", job.get("folder", ""))
        # Truncate folder path if too long
        if len(folder) > 40:
            folder = "..." + folder[-37:]

        progress = _format_progress(
            job.get("progress_percent", job.get("progress")),
            job.get("total_files"),
        )
        enqueued = _format_timestamp(job.get("enqueued_at", job.get("created_at")))
        started = _format_timestamp(job.get("started_at"))
        error = job.get("error", job.get("error_message", "")) or ""
        if len(error) > 30:
            error = error[:27] + "..."

        table.add_row(
            job_id,
            f"[{status_style}]{status}[/{status_style}]",
            folder,
            progress,
            enqueued,
            started,
            f"[red]{error}[/red]" if error else "-",
        )

    return table


def _create_job_detail_panel(job: dict[str, Any]) -> Panel:
    """Create a Rich panel for displaying job details."""
    job_id = job.get("job_id", job.get("id", "unknown"))
    status = job.get("status", "unknown")
    status_style = _get_status_style(status)

    lines = [
        f"[bold]Job ID:[/] {job_id}",
        f"[bold]Status:[/] [{status_style}]{status}[/{status_style}]",
    ]

    if folder := job.get("folder_path", job.get("folder")):
        lines.append(f"[bold]Folder:[/] {folder}")

    if (progress := job.get("progress_percent", job.get("progress"))) is not None:
        total = job.get("total_files", 0)
        processed = job.get("processed_files", 0)
        if total:
            lines.append(
                f"[bold]Progress:[/] {progress:.1f}% ({processed}/{total} files)"
            )
        else:
            lines.append(f"[bold]Progress:[/] {progress:.1f}%")

    if enqueued := job.get("enqueued_at", job.get("created_at")):
        lines.append(f"[bold]Enqueued:[/] {_format_timestamp(enqueued)}")

    if started := job.get("started_at"):
        lines.append(f"[bold]Started:[/] {_format_timestamp(started)}")

    if completed := job.get("completed_at", job.get("finished_at")):
        lines.append(f"[bold]Completed:[/] {_format_timestamp(completed)}")

    if error := job.get("error", job.get("error_message")):
        lines.append(f"[bold]Error:[/] [red]{error}[/red]")

    # Additional metadata
    if chunk_size := job.get("chunk_size"):
        lines.append(f"[bold]Chunk Size:[/] {chunk_size}")

    if languages := job.get("supported_languages"):
        lines.append(f"[bold]Languages:[/] {', '.join(languages)}")

    if job.get("include_code"):
        lines.append("[bold]Include Code:[/] Yes")

    if job.get("generate_summaries"):
        lines.append("[bold]Generate Summaries:[/] Yes")

    content = "\n".join(lines)
    title = f"Job Details: {job_id[:12]}"
    return Panel(content, title=title, border_style=status_style)


def _list_jobs(client: DocServeClient, limit: int, json_output: bool) -> None:
    """List all jobs."""
    jobs = client.list_jobs(limit=limit)

    if json_output:
        import json

        click.echo(json.dumps(jobs, indent=2))
        return

    if not jobs:
        console.print("[dim]No jobs in queue[/]")
        return

    table = _create_jobs_table(jobs)
    console.print(table)


def _show_job_detail(client: DocServeClient, job_id: str, json_output: bool) -> None:
    """Show details for a specific job."""
    job = client.get_job(job_id)

    if json_output:
        import json

        click.echo(json.dumps(job, indent=2))
        return

    panel = _create_job_detail_panel(job)
    console.print(panel)


def _cancel_job(client: DocServeClient, job_id: str, json_output: bool) -> None:
    """Cancel a specific job."""
    result = client.cancel_job(job_id)

    if json_output:
        import json

        click.echo(json.dumps(result, indent=2))
        return

    status = result.get("status", "unknown")
    message = result.get("message", f"Job {job_id} cancellation requested")

    if status in ("cancelled", "canceled"):
        console.print(f"[green]Job {job_id[:12]} cancelled successfully[/]")
    else:
        console.print(f"[yellow]{message}[/]")


def _watch_jobs(client: DocServeClient, limit: int) -> None:
    """Watch jobs with periodic refresh."""
    try:
        while True:
            console.clear()
            console.print("[bold]Agent Brain Job Queue[/]\n")

            jobs = client.list_jobs(limit=limit)

            if not jobs:
                console.print("[dim]No jobs in queue[/]")
            else:
                table = _create_jobs_table(jobs)
                console.print(table)

            console.print(
                "\n[dim]Refreshing in 3s... Press Ctrl+C to stop[/]",
                highlight=False,
            )
            time.sleep(3)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped watching[/]")


@click.command("jobs")
@click.argument("job_id", required=False)
@click.option("--watch", "-w", is_flag=True, help="Poll every 3 seconds")
@click.option("--cancel", "-c", is_flag=True, help="Cancel the specified job")
@click.option("--limit", "-l", default=20, help="Max jobs to show (default: 20)")
@click.option(
    "--url",
    envvar="AGENT_BRAIN_URL",
    default=None,
    help="Agent Brain server URL (default: from config or http://127.0.0.1:8000)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def jobs_command(
    job_id: str | None,
    watch: bool,
    cancel: bool,
    limit: int,
    url: str | None,
    json_output: bool,
) -> None:
    """View job queue and status.

    Without JOB_ID: List all jobs in the queue.
    With JOB_ID: Show detailed information for that job.

    \b
    Examples:
      agent-brain jobs              # List all jobs
      agent-brain jobs --watch      # Watch queue (refresh every 3s)
      agent-brain jobs JOB_ID       # Show job details
      agent-brain jobs JOB_ID --cancel  # Cancel a job
    """
    resolved_url = url or get_server_url()

    # Validate options
    if cancel and not job_id:
        raise click.UsageError("--cancel requires a JOB_ID argument")

    if watch and job_id:
        raise click.UsageError("--watch cannot be used with a specific JOB_ID")

    if watch and json_output:
        raise click.UsageError("--watch cannot be used with --json")

    try:
        with DocServeClient(base_url=resolved_url) as client:
            if cancel and job_id:
                _cancel_job(client, job_id, json_output)
            elif watch:
                _watch_jobs(client, limit)
            elif job_id:
                _show_job_detail(client, job_id, json_output)
            else:
                _list_jobs(client, limit, json_output)

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
