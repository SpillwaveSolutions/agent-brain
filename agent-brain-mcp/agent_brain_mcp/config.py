"""Backend selection — builds an httpx.Client over HTTP or UDS.

The MCP server speaks stdio to the LLM client and HTTP (or UDS) to the
Agent Brain backend. ``open_backend_client(...)`` picks the right
transport per the CLI flags / env vars and returns a live
``httpx.Client`` the :class:`agent_brain_mcp.client.ApiClient` wraps.

Resolution precedence (plan §7):
  1. Explicit ``backend`` argument ("uds" / "http" / "auto")
  2. ``AGENT_BRAIN_MCP_BACKEND`` env var
  3. Default: ``"auto"`` — UDS if validates, HTTP otherwise

For HTTP:
  - explicit ``backend_url`` arg →
  - ``AGENT_BRAIN_MCP_BACKEND_URL`` env →
  - ``AGENT_BRAIN_URL`` env →
  - runtime.json::base_url (if a server is running for this state dir) →
  - default ``http://127.0.0.1:8000``

For UDS:
  - explicit ``socket_path`` arg →
  - ``AGENT_BRAIN_UDS_PATH`` env →
  - ``resolve_socket_path(state_dir)``
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

import httpx
from agent_brain_uds import (
    AgentBrainUdsError,
    resolve_socket_path,
    validate_socket,
)
from agent_brain_uds import (
    make_client as make_uds_client,
)

DEFAULT_HTTP_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 30.0
STATE_DIR_NAME = ".agent-brain"


def _resolve_state_dir(state_dir: Path | None) -> Path | None:
    if state_dir is not None:
        return state_dir
    env_dir = os.environ.get("AGENT_BRAIN_STATE_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    candidate = Path.cwd() / STATE_DIR_NAME
    return candidate if candidate.exists() else None


def _resolve_http_url(
    backend_url: str | None,
    state_dir: Path | None,
) -> str:
    if backend_url:
        return backend_url
    env_url = os.environ.get("AGENT_BRAIN_MCP_BACKEND_URL") or os.environ.get(
        "AGENT_BRAIN_URL"
    )
    if env_url:
        return env_url
    sdir = _resolve_state_dir(state_dir)
    if sdir is not None:
        runtime = sdir / "runtime.json"
        if runtime.exists():
            try:
                data = json.loads(runtime.read_text())
                if data.get("base_url"):
                    return str(data["base_url"])
            except (json.JSONDecodeError, OSError):
                pass
    return DEFAULT_HTTP_BASE_URL


def _open_uds_client(
    socket_path: Path | None,
    state_dir: Path | None,
    timeout: float,
) -> httpx.Client:
    if socket_path is None:
        env_path = os.environ.get("AGENT_BRAIN_UDS_PATH")
        socket_path = Path(env_path) if env_path else resolve_socket_path(state_dir)
    validate_socket(socket_path)
    client: httpx.Client = make_uds_client(socket_path=socket_path, timeout=timeout)
    return client


def _open_http_client(backend_url: str, timeout: float) -> httpx.Client:
    return httpx.Client(base_url=backend_url, timeout=timeout)


def open_backend_client(
    *,
    backend: Literal["auto", "uds", "http"] | None = None,
    backend_url: str | None = None,
    socket_path: Path | None = None,
    state_dir: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[Literal["uds", "http"], httpx.Client]:
    """Return ``(transport, client)`` for the chosen backend.

    Auto mode tries UDS validation first; on any
    :class:`AgentBrainUdsError` falls back to HTTP transparently.
    """
    chosen = (backend or os.environ.get("AGENT_BRAIN_MCP_BACKEND") or "auto").lower()

    if chosen == "http":
        url = _resolve_http_url(backend_url, state_dir)
        return ("http", _open_http_client(url, timeout))

    if chosen == "uds":
        return ("uds", _open_uds_client(socket_path, state_dir, timeout))

    # auto
    try:
        return ("uds", _open_uds_client(socket_path, state_dir, timeout))
    except (AgentBrainUdsError, OSError, FileNotFoundError):
        url = _resolve_http_url(backend_url, state_dir)
        return ("http", _open_http_client(url, timeout))
