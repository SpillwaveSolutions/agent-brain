"""`agent-brain graph` Click sub-group for graph management commands (Phase 64).

Subcommands:
    restore-from-snapshot — replay the latest (or a specific) kuzu snapshot
        back into the live graph. Confirm-by-default; --yes skips the prompt
        for non-interactive/CI use; --dry-run reports the plan without mutating.

Closes #184 bug 1: when kuzu opens cleanly but the live graph is STALE after
an AGENT_BRAIN_JOB_TIMEOUT rollback, operators can replay the latest valid
snapshot to bring the graph back in sync.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

from agent_brain_cli.config import STATE_DIR_NAME, resolve_project_root

# Re-use diagnostics helpers for state-dir + store-type resolution and the
# server-running guard. These are local imports inside the CLI so the module
# loads without requiring the server package to be installed.
from agent_brain_cli.diagnostics import (
    _graph_index_dir,
    _read_graphrag_block,
    _server_is_running,
)

# agent-brain-rag is a declared dependency of agent-brain-cli (^10.x), so this
# import is safe at module level. The lazy try/except below is a belt-and-braces
# guard for edge cases where the server wheel is not installed in the env.
try:
    from agent_brain_server.storage.graph_store import GraphStoreManager
except ImportError:  # pragma: no cover
    GraphStoreManager = None

console = Console()


@click.group(name="graph")
def graph_group() -> None:
    """Manage the GraphRAG graph index (kuzu backend).

    \b
    Commands:
      restore-from-snapshot  Replay a snapshot back into kuzu.
    """


@graph_group.command("restore-from-snapshot")
@click.option(
    "--snapshot",
    "snapshot_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help=(
        "Snapshot file to restore (default: latest valid snapshot on disk). "
        "Must be a .json snapshot written by the agent-brain-server."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would be restored and exit without mutating kuzu.",
)
@click.option(
    "--yes",
    "assume_yes",
    is_flag=True,
    help="Skip the confirmation prompt (non-interactive/CI use).",
)
def restore_from_snapshot(
    snapshot_path: Path | None,
    dry_run: bool,
    assume_yes: bool,
) -> None:
    """Replay a kuzu snapshot back into the live graph.

    Resolves the project's graph_index directory, reads the store type from
    config, then replays the latest valid (or a specific) snapshot back into
    the kuzu database.

    Default (no flags): prints a summary of what WILL be restored and prompts
    for confirmation.  Use --yes for CI/scripted invocations; --dry-run to
    preview without touching the database.

    The server MUST be stopped before running this command because kuzu does
    not allow concurrent writers.
    """
    # --- Resolve state dir + store type ----------------------------------- #
    project_root = resolve_project_root()
    state_dir = project_root / STATE_DIR_NAME

    block = _read_graphrag_block(state_dir)
    store_type = str((block or {}).get("store_type") or "simple").lower()

    if store_type != "kuzu":
        console.print(
            "[yellow]Graph restore only applies to the kuzu backend "
            f"(configured store_type={store_type!r}). Nothing to do.[/yellow]"
        )
        return

    # --- Guard: server must be stopped ------------------------------------ #
    if _server_is_running(state_dir):
        console.print(
            "[red]Stop the server first (`agent-brain stop`) — restore "
            "mutates the kuzu database the server holds open.[/red]"
        )
        raise SystemExit(1)

    # --- Build the graph store manager ------------------------------------ #
    graph_dir = _graph_index_dir(state_dir)
    if GraphStoreManager is None:  # pragma: no cover
        console.print(
            "[red]Cannot import agent-brain-server. Install it with "
            "`uv pip install agent-brain-rag`.[/red]"
        )
        raise SystemExit(1)

    mgr = GraphStoreManager(graph_dir, "kuzu")

    # --- Preview (plan) --------------------------------------------------- #
    plan = mgr.plan_restore(snapshot_path)
    if plan is None:
        console.print(
            "[yellow]No snapshot available to restore at "
            f"{graph_dir / 'snapshots'}.[/yellow]"
        )
        raise SystemExit(1)

    snap_file, triplet_count = plan
    kuzu_db_path = graph_dir / "kuzu_db"
    console.print(
        f"Will restore [bold]{triplet_count}[/bold] triplets from "
        f"[cyan]{snap_file.name}[/cyan] into [cyan]{kuzu_db_path}[/cyan]."
    )

    if dry_run:
        console.print("(dry run — nothing changed)")
        return

    # --- Interactive confirmation ------------------------------------------ #
    if not assume_yes:
        confirmed = click.confirm("Proceed with restore?", default=False)
        if not confirmed:
            console.print("Aborted.")
            return

    # --- Execute restore --------------------------------------------------- #
    restored = mgr.restore_from_snapshot(snapshot_path)
    console.print(f"Restored [bold]{restored}[/bold] triplets.")
