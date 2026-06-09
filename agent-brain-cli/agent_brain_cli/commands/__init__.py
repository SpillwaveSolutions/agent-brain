"""CLI commands for agent-brain."""

from .cache import cache_group
from .config import config_group
from .doctor import doctor_command
from .folders import folders_group
from .index import index_command
from .init import init_command
from .inject import inject_command
from .install_agent import install_agent_command
from .jobs import jobs_command
from .list_cmd import list_command
from .mcp import mcp_group
from .prompt import prompt_command
from .query import query_command
from .reset import reset_command
from .resources import resources_group
from .start import start_command
from .status import status_command
from .stop import stop_command
from .types import types_group
from .uninstall import uninstall_command

__all__ = [
    "cache_group",
    "config_group",
    "doctor_command",
    "folders_group",
    "index_command",
    "inject_command",
    "init_command",
    "install_agent_command",
    "jobs_command",
    "list_command",
    "mcp_group",
    "prompt_command",
    "query_command",
    "reset_command",
    "resources_group",
    "start_command",
    "status_command",
    "stop_command",
    "types_group",
    "uninstall_command",
]
