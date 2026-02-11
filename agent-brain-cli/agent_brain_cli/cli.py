"""Main CLI entry point for agent-brain CLI.

This module provides the command-line interface for managing and querying
the Agent Brain RAG server.
"""

import click

from . import __version__
from .commands import (
    config_group,
    index_command,
    init_command,
    jobs_command,
    list_command,
    query_command,
    reset_command,
    start_command,
    status_command,
    stop_command,
)


@click.group()
@click.version_option(version=__version__, prog_name="agent-brain")
def cli() -> None:
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
      jobs     View and manage job queue
      reset    Clear all indexed documents

    \b
    Examples:
      agent-brain init                      # Initialize project
      agent-brain start                     # Start server
      agent-brain status                    # Check server status
      agent-brain query "how to use python" # Search documents
      agent-brain index ./docs              # Index documents
      agent-brain stop                      # Stop server

    \b
    Environment Variables:
      AGENT_BRAIN_URL  Server URL (default: http://127.0.0.1:8000)
    """
    pass


# Register project management commands
cli.add_command(init_command, name="init")
cli.add_command(start_command, name="start")
cli.add_command(stop_command, name="stop")
cli.add_command(list_command, name="list")

# Register server interaction commands
cli.add_command(status_command, name="status")
cli.add_command(query_command, name="query")
cli.add_command(index_command, name="index")
cli.add_command(jobs_command, name="jobs")
cli.add_command(reset_command, name="reset")
cli.add_command(config_group, name="config")


if __name__ == "__main__":
    cli()
