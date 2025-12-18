"""CLI commands for doc-svr-ctl."""

from .index import index_command
from .query import query_command
from .reset import reset_command
from .status import status_command

__all__ = ["status_command", "query_command", "index_command", "reset_command"]
