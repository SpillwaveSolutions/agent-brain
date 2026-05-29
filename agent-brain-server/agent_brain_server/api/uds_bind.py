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
import hashlib
import logging
import os
import signal
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI

logger = logging.getLogger(__name__)

#: Canonical socket file name (must match agent_brain_uds.paths.SOCKET_FILE_NAME).
SOCKET_FILE_NAME = "agent-brain.sock"

#: Pointer-file name written when the canonical path exceeds the platform
#: socket-path limit (must match agent_brain_uds.paths.POINTER_FILE_NAME).
POINTER_FILE_NAME = "agent-brain.sock.path"

#: Conservative sockaddr_un sun_path limit — 104 bytes on macOS/BSD.
#: Must match agent_brain_uds.paths.MAX_SOCKET_PATH_BYTES so client + server
#: independently compute the same fallback path.
MAX_SOCKET_PATH_BYTES = 104


def _short_fallback_path(state_dir: Path) -> Path:
    """Return the ``/tmp`` fallback socket path for ``state_dir``.

    Algorithm is duplicated from :func:`agent_brain_uds.paths._short_fallback_path`
    so client and server compute the same path without an import cycle
    (server has no upward deps on the uds package).
    """
    digest = hashlib.sha256(str(state_dir.resolve()).encode("utf-8")).hexdigest()[:8]
    return Path("/tmp") / f"agent-brain-{digest}.sock"


def resolve_bind_path(
    state_dir: Path, requested: Path | None = None
) -> tuple[Path, bool]:
    """Resolve the path the UDS server should actually bind on.

    Returns ``(bind_path, used_fallback)``. When the canonical path
    exceeds the platform limit, writes a pointer file at
    ``<state_dir>/agent-brain.sock.path`` so clients can discover the
    real socket location.

    Args:
        state_dir: The project's state directory (must exist or be creatable).
        requested: Explicit socket path; when None, uses
            ``state_dir / SOCKET_FILE_NAME``.

    Returns:
        Tuple of (path uvicorn should bind on, whether the /tmp fallback
        was used).
    """
    target = requested if requested is not None else state_dir / SOCKET_FILE_NAME

    if len(str(target).encode("utf-8")) >= MAX_SOCKET_PATH_BYTES:
        fallback = _short_fallback_path(state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)
        pointer = state_dir / POINTER_FILE_NAME
        pointer.write_text(str(fallback))
        logger.info(
            "UDS socket path exceeds %d bytes; bound at %s, pointer written at %s",
            MAX_SOCKET_PATH_BYTES,
            fallback,
            pointer,
        )
        return fallback, True
    return target, False


def _install_shutdown_signal_handlers(servers: list[uvicorn.Server]) -> None:
    """Wire SIGINT/SIGTERM to set ``should_exit`` on every server.

    uvicorn's built-in signal handlers are only installed inside
    ``Server.run()`` — we call ``server.serve()`` directly, so they
    never fire. Without this, SIGTERM to a `agent-brain start --uds`
    subprocess won't unwind ``asyncio.gather`` cleanly and the socket
    file's ``unlink`` in the finally block never runs.

    Only works on the main thread of the main interpreter; silently
    no-ops in test threads (those tests already drive shutdown via
    ``server_holder["server"].should_exit = True``).
    """

    def _signal_handler() -> None:
        logger.info("Shutdown signal received; setting should_exit on all servers")
        for srv in servers:
            srv.should_exit = True

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, ValueError, RuntimeError):
            # NotImplementedError: Windows.
            # ValueError / RuntimeError: not on main thread (asyncio
            # requires set_wakeup_fd, which is main-thread only). Test
            # threads drive shutdown via server_holder; production path
            # always runs on the main thread.
            return


async def _chmod_socket_when_ready(
    socket_path: Path,
    *,
    poll_interval_s: float = 0.05,
    timeout_s: float = 5.0,
    stable_iterations_required: int = 5,
) -> None:
    """Poll for ``socket_path`` to exist, then chmod to ``0o600`` and hold.

    uvicorn binds the AF_UNIX socket inside ``Server.startup()`` and
    *also* explicitly ``chmod(0o666)``s it after binding (see
    ``uvicorn/server.py:148-153``). That clobbers a one-shot chmod from
    us. To win the race, we chmod on every poll where the mode isn't
    yet ``0o600`` and only return once the mode has stayed ``0o600`` for
    several consecutive polls (``stable_iterations_required * poll_interval_s``).

    Also chmods the parent directory to ``0o700`` once the socket mode
    is stable, so the client-side ``validate_socket()`` parent-mode
    check passes.
    """
    import stat as _stat

    deadline = asyncio.get_running_loop().time() + timeout_s
    socket_seen = False
    stable = 0
    while asyncio.get_running_loop().time() < deadline:
        if socket_path.exists():
            socket_seen = True
            current_mode = _stat.S_IMODE(os.lstat(socket_path).st_mode)
            if current_mode != 0o600:
                try:
                    os.chmod(socket_path, 0o600)
                except OSError as exc:
                    logger.warning(
                        "Failed to chmod UDS socket at %s: %s — clients "
                        "will reject the connection via validate_socket().",
                        socket_path,
                        exc,
                    )
                    return
                stable = 0
            else:
                stable += 1
                if stable >= stable_iterations_required:
                    try:
                        os.chmod(socket_path.parent, 0o700)
                    except OSError as exc:
                        logger.warning(
                            "Failed to chmod parent dir %s: %s",
                            socket_path.parent,
                            exc,
                        )
                    logger.debug(
                        "UDS socket %s held at 0o600 (parent dir 0o700)",
                        socket_path,
                    )
                    return
        await asyncio.sleep(poll_interval_s)

    if socket_seen:
        logger.warning(
            "UDS socket mode at %s never stabilised at 0o600 within %.1fs",
            socket_path,
            timeout_s,
        )
    else:
        logger.warning(
            "UDS socket at %s did not appear within %.1fs; not chmoded.",
            socket_path,
            timeout_s,
        )


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
    _install_shutdown_signal_handlers([server])

    try:
        await asyncio.gather(
            server.serve(),
            _chmod_socket_when_ready(socket_path),
        )
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
    _install_shutdown_signal_handlers([server_tcp, server_uds])

    try:
        await asyncio.gather(
            server_tcp.serve(),
            server_uds.serve(),
            _chmod_socket_when_ready(socket_path),
        )
    finally:
        with contextlib.suppress(FileNotFoundError):
            socket_path.unlink()
