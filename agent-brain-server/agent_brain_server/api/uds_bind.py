"""Server-side UDS bind helpers.

Implements the two-``uvicorn.Server`` orchestration pattern proven by
``scripts/spike_dual_bind.py`` (plan §5).

``serve_dual`` runs HTTP and UDS on a single asyncio loop with one lifespan;
``serve_uds_only`` is the UDS-without-TCP shape used when ``--uds-only``
is passed. Both accept a ``server_holder`` dict so callers (including the
unit tests) can flip ``should_exit`` from a different thread.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI

logger = logging.getLogger(__name__)


async def serve_uds_only(
    app: FastAPI,
    *,
    socket_path: Path,
    server_holder: dict[str, Any] | None = None,
    log_level: str = "info",
) -> None:
    """Bind ``app`` to ``socket_path`` over AF_UNIX only.

    Raises:
        FileNotFoundError: if the parent directory of ``socket_path`` doesn't
            exist (fail loud rather than guess at the intended location).
    """
    parent = socket_path.parent
    if not parent.exists():
        raise FileNotFoundError(
            f"Parent directory {parent} does not exist for UDS socket {socket_path}"
        )

    config = uvicorn.Config(
        app=app, uds=str(socket_path), log_level=log_level, lifespan="on"
    )
    server = uvicorn.Server(config)
    if server_holder is not None:
        server_holder["server"] = server

    try:
        await server.serve()
    finally:
        with contextlib.suppress(FileNotFoundError):
            socket_path.unlink()


async def serve_dual(
    app: FastAPI,
    *,
    host: str,
    port: int,
    socket_path: Path,
    server_holder: dict[str, Any] | None = None,
    log_level: str = "info",
) -> None:
    """Bind ``app`` to both TCP ``host:port`` and ``socket_path`` simultaneously.

    Per the Phase 1 spike, lifespan runs on the TCP server only so the app's
    startup hooks fire exactly once. The UDS server runs with ``lifespan="off"``
    against the same already-initialized app.

    Both servers stop when their ``should_exit`` flag is set; callers can flip
    those flags via ``server_holder["server_tcp"]`` / ``server_holder["server_uds"]``.
    """
    parent = socket_path.parent
    if not parent.exists():
        raise FileNotFoundError(
            f"Parent directory {parent} does not exist for UDS socket {socket_path}"
        )

    config_tcp = uvicorn.Config(
        app=app, host=host, port=port, log_level=log_level, lifespan="on"
    )
    config_uds = uvicorn.Config(
        app=app, uds=str(socket_path), log_level=log_level, lifespan="off"
    )
    server_tcp = uvicorn.Server(config_tcp)
    server_uds = uvicorn.Server(config_uds)
    if server_holder is not None:
        server_holder["server_tcp"] = server_tcp
        server_holder["server_uds"] = server_uds

    try:
        await asyncio.gather(server_tcp.serve(), server_uds.serve())
    finally:
        with contextlib.suppress(FileNotFoundError):
            socket_path.unlink()
