"""Main CLI entry point for doc-svr-ctl."""

import click

from . import __version__
from .commands import index_command, query_command, reset_command, status_command


@click.group()
@click.version_option(version=__version__, prog_name="doc-svr-ctl")
def cli() -> None:
    """Doc-Serve CLI - Manage and query the Doc-Serve server.

    A command-line interface for interacting with the Doc-Serve document
    indexing and semantic search API.

    \b
    Examples:
      doc-svr-ctl status                    # Check server status
      doc-svr-ctl query "how to use python" # Search documents
      doc-svr-ctl index ./docs              # Index documents
      doc-svr-ctl reset --yes               # Clear all indexed documents

    \b
    Environment Variables:
      DOC_SERVE_URL  Server URL (default: http://127.0.0.1:8000)
    """
    pass


# Register commands
cli.add_command(status_command, name="status")
cli.add_command(query_command, name="query")
cli.add_command(index_command, name="index")
cli.add_command(reset_command, name="reset")


if __name__ == "__main__":
    cli()
