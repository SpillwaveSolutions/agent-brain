"""Exception hierarchy for agent-brain-uds.

Each error carries the resolved socket path and a remediation hint so the
caller (CLI, MCP server, or third-party) can surface an actionable message
to the user without re-implementing the diagnostics.

See docs/plans/2026-05-28-mcp-uds-transport-design.md §6.7.
"""

from __future__ import annotations

from pathlib import Path


class AgentBrainUdsError(Exception):
    """Base class for all agent-brain-uds errors.

    Subclasses carry a ``socket_path`` attribute (when known) and a
    ``remediation`` hint that callers can show to the user.
    """

    def __init__(
        self,
        message: str,
        *,
        socket_path: Path | None = None,
        remediation: str | None = None,
    ) -> None:
        super().__init__(message)
        self.socket_path = socket_path
        self.remediation = remediation

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.socket_path is not None:
            parts.append(f"(socket: {self.socket_path})")
        if self.remediation:
            parts.append(f"\n  → {self.remediation}")
        return " ".join(parts)


class SocketNotFoundError(AgentBrainUdsError):
    """No socket file at the resolved path.

    Most common cause: the server has not been started with ``--uds``.
    """


class SocketStaleError(AgentBrainUdsError):
    """Socket file exists but no listener is bound.

    Typically left over from a crashed server process. The server's
    own bind helper unlinks stale sockets on startup, so this should
    be rare in practice.
    """


class SocketPermissionError(AgentBrainUdsError):
    """Socket file or its parent directory has unsafe permissions.

    Raised when the socket file is owned by a different UID, has
    group/world readable bits set, is a symlink, or its parent
    directory is not mode 0700.
    """


class SocketPathTooLongError(AgentBrainUdsError):
    """Resolved socket path exceeds the OS sockaddr_un limit.

    UDS paths are limited to ~104 bytes on macOS/BSD and ~108 on Linux.
    The resolver falls back to ``/tmp/agent-brain-<sha8>.sock`` and writes
    a pointer file; this error is raised only if even the fallback
    cannot be used.
    """
