"""Main CLI entry point for agent-brain CLI.

This module provides the command-line interface for managing and querying
the Agent Brain RAG server.
"""

import click

from . import __version__
from .commands import (
    cache_group,
    config_group,
    doctor_command,
    folders_group,
    index_command,
    init_command,
    inject_command,
    install_agent_command,
    jobs_command,
    list_command,
    query_command,
    reset_command,
    start_command,
    status_command,
    stop_command,
    types_group,
    uninstall_command,
)


@click.group()
@click.version_option(version=__version__, prog_name="agent-brain")
@click.option(
    "--transport",
    "transport",
    type=click.Choice(["auto", "http", "uds", "mcp"], case_sensitive=False),
    default=None,
    help=(
        "Transport: auto (UDS if available, HTTP otherwise), http, uds, "
        "or mcp (CLI talks to agent-brain-mcp). Honors AGENT_BRAIN_TRANSPORT env."
    ),
)
@click.option(
    "--socket-path",
    type=click.Path(),
    default=None,
    help="Override UDS socket path (only used with --transport=uds|auto).",
)
@click.option(
    "--base-url",
    default=None,
    help="Override server base URL (only used with --transport=http|auto).",
)
@click.option(
    "--mcp-transport",
    "mcp_transport",
    type=click.Choice(["stdio", "http"], case_sensitive=False),
    default=None,
    help=(
        "MCP listen transport for --transport mcp: stdio (default) "
        "or http. Honors AGENT_BRAIN_MCP_TRANSPORT env. Ignored "
        "when --transport != mcp."
    ),
)
@click.option(
    "--mcp-url",
    "mcp_url",
    default=None,
    help=(
        "MCP HTTP listener URL for --transport mcp --mcp-transport "
        "http (e.g. http://127.0.0.1:9999/mcp). Honors "
        "AGENT_BRAIN_MCP_URL env. mcp.runtime.json discovery "
        "lands in Phase 58."
    ),
)
@click.option(
    "--debug-transport",
    is_flag=True,
    default=False,
    help="Log the resolved transport (http or uds) and target to stderr.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    transport: str | None,
    socket_path: str | None,
    base_url: str | None,
    mcp_transport: str | None,
    mcp_url: str | None,
    debug_transport: bool,
) -> None:
    """Agent Brain CLI - Manage and query the Agent Brain RAG server.

    A command-line interface for interacting with the Agent Brain document
    indexing and semantic search API.

    \b
    Project Commands:
      init     Initialize a new agent-brain project
      start    Start the server for this project
      stop     Stop the server for this project
      list     List all running agent-brain instances

    \b
    Server Commands:
      status   Check server status
      query    Search documents
      index    Index documents from a folder
      inject   Index documents with content injection
      jobs     View and manage job queue
      reset    Clear all indexed documents
      doctor   Diagnose installation, configuration, and server state

    \b
    Cache Commands:
      cache    Manage the embedding cache (status, clear)

    \b
    Folder Commands:
      folders  Manage indexed folders (list, add, remove)

    \b
    File Type Commands:
      types    List available file type presets

    \b
    Examples:
      agent-brain init                                # Initialize project
      agent-brain start                               # Start server
      agent-brain status                              # Check server status
      agent-brain query "how to use python"           # Search documents
      agent-brain index ./docs                        # Index documents
      agent-brain index ./src --include-type python   # Index with preset
      agent-brain inject --script enrich.py ./docs   # Index with injection
      agent-brain folders list                        # List indexed folders
      agent-brain folders remove ./docs --yes         # Remove folder chunks
      agent-brain types list                          # Show file type presets
      agent-brain stop                                # Stop server

    \b
    Environment Variables:
      AGENT_BRAIN_URL        Server URL (default: http://127.0.0.1:8000)
      AGENT_BRAIN_TRANSPORT  Transport hint: auto, http, or uds
      AGENT_BRAIN_UDS_PATH   Override UDS socket path
    """
    ctx.ensure_object(dict)
    ctx.obj["transport_hint"] = transport
    ctx.obj["base_url_override"] = base_url
    ctx.obj["socket_path_override"] = socket_path
    ctx.obj["debug_transport"] = debug_transport
    ctx.obj["mcp_transport_hint"] = mcp_transport
    ctx.obj["mcp_url_override"] = mcp_url


# Register project management commands
cli.add_command(init_command, name="init")
cli.add_command(start_command, name="start")
cli.add_command(stop_command, name="stop")
cli.add_command(list_command, name="list")

# Register server interaction commands
cli.add_command(status_command, name="status")
cli.add_command(query_command, name="query")
cli.add_command(index_command, name="index")
cli.add_command(inject_command, name="inject")
cli.add_command(jobs_command, name="jobs")
cli.add_command(reset_command, name="reset")
cli.add_command(config_group, name="config")
cli.add_command(folders_group, name="folders")
cli.add_command(types_group, name="types")
cli.add_command(cache_group, name="cache")
cli.add_command(uninstall_command, name="uninstall")
cli.add_command(install_agent_command, name="install-agent")
cli.add_command(doctor_command, name="doctor")


if __name__ == "__main__":
    cli()
