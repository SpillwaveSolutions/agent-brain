"""``httpx`` client factory for UDS transport.

Returns a configured ``httpx.Client`` / ``httpx.AsyncClient`` that speaks
HTTP/1.1 over the project's UDS socket. The ``base_url`` is a placeholder
(``http://agent-brain``) because ``httpx`` requires a URL even though UDS
ignores the host component — using a fixed sentinel makes log messages
self-documenting.

The client validates socket permissions on construction so a stale or
hijacked socket fails loud immediately, not on the first request.

See docs/plans/2026-05-28-mcp-uds-transport-design.md §6.3.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from .paths import resolve_socket_path
from .permissions import validate_socket

#: Sentinel base URL that ends up in logs / error messages.
BASE_URL = "http://agent-brain"

#: Default request timeout (seconds). Overridable per call site.
DEFAULT_TIMEOUT = 30.0


def _resolve_path(
    state_dir: Path | None,
    socket_path: Path | None,
) -> Path:
    """Decide which socket path to use.

    Precedence: explicit ``socket_path`` argument → ``AGENT_BRAIN_UDS_PATH``
    env var → ``resolve_socket_path(state_dir)``.
    """
    if socket_path is not None:
        return socket_path
    env_path = os.environ.get("AGENT_BRAIN_UDS_PATH")
    if env_path:
        return Path(env_path).expanduser()
    return resolve_socket_path(state_dir)


def make_client(
    *,
    state_dir: Path | None = None,
    socket_path: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.Client:
    """Return a synchronous ``httpx.Client`` configured for UDS.

    Args:
        state_dir: Override the state-directory resolver. Defaults to
            ``AGENT_BRAIN_STATE_DIR`` env var or CWD lookup.
        socket_path: Override the entire path-resolution chain.
        timeout: HTTP request timeout in seconds.

    Raises:
        SocketNotFoundError: when the resolved socket does not exist.
        SocketPermissionError: when the socket fails the permission checks
            in :mod:`agent_brain_uds.permissions`.
    """
    path = _resolve_path(state_dir, socket_path)
    validate_socket(path)
    transport = httpx.HTTPTransport(uds=str(path))
    return httpx.Client(transport=transport, base_url=BASE_URL, timeout=timeout)


def make_async_client(
    *,
    state_dir: Path | None = None,
    socket_path: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.AsyncClient:
    """Async counterpart of :func:`make_client`."""
    path = _resolve_path(state_dir, socket_path)
    validate_socket(path)
    transport = httpx.AsyncHTTPTransport(uds=str(path))
    return httpx.AsyncClient(transport=transport, base_url=BASE_URL, timeout=timeout)
