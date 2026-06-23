"""Agent Brain UDS — Unix-domain-socket transport for Agent Brain.

Client-side only. See docs/plans/2026-05-28-mcp-uds-transport-design.md §4.1.

Public surface:

- :func:`resolve_socket_path` — Resolve the canonical UDS socket path.
- :func:`validate_socket` — Validate socket file ownership and permissions.
- :func:`make_client` / :func:`make_async_client` — ``httpx`` clients
  pre-configured for UDS transport.
- :class:`AgentBrainUdsError` and subclasses — Exception hierarchy.

The server-side bind helper lives inside ``agent_brain_server`` to keep
the dependency direction acyclic (server has no upward deps).
"""

from .client import (
    BASE_URL,
    DEFAULT_TIMEOUT,
    make_async_client,
    make_client,
)
from .errors import (
    AgentBrainUdsError,
    SocketNotFoundError,
    SocketPathTooLongError,
    SocketPermissionError,
    SocketStaleError,
)
from .paths import (
    MAX_SOCKET_PATH_BYTES,
    POINTER_FILE_NAME,
    SOCKET_FILE_NAME,
    STATE_DIR_NAME,
    resolve_socket_path,
    resolve_state_dir,
    write_pointer_file,
)
from .permissions import validate_socket

__version__ = "10.4.0"

__all__ = [
    "BASE_URL",
    "DEFAULT_TIMEOUT",
    "MAX_SOCKET_PATH_BYTES",
    "POINTER_FILE_NAME",
    "SOCKET_FILE_NAME",
    "STATE_DIR_NAME",
    "AgentBrainUdsError",
    "SocketNotFoundError",
    "SocketPathTooLongError",
    "SocketPermissionError",
    "SocketStaleError",
    "__version__",
    "make_async_client",
    "make_client",
    "resolve_socket_path",
    "resolve_state_dir",
    "validate_socket",
    "write_pointer_file",
]
