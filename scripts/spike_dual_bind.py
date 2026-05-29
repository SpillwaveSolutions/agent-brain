#!/usr/bin/env python3
"""Phase 1 spike — prove uvicorn can dual-bind UDS + TCP from one process.

This is the exit gate for Phase 1 of the MCP + UDS plan
(``docs/plans/2026-05-28-mcp-uds-transport-design.md`` §5 / §6.2 / DR-5).

``uvicorn.Config.bind_socket()`` is mutually exclusive between ``uds=`` and
``(host, port)=``. To serve both transports from one process we instantiate
two ``uvicorn.Server``s, run them on a shared asyncio loop, and disable
``lifespan`` on one of them so the app's startup/shutdown hooks fire exactly
once.

The spike exits 0 if:
    (a) both servers start,
    (b) HTTP GET ``/health/`` over loopback returns 200,
    (c) HTTP GET ``/health/`` over the UDS socket returns 200,
    (d) ``SIGTERM`` shuts down both cleanly,
    (e) the socket file is unlinked.

Architecture: the asyncio loop runs in the **main thread** so
``loop.add_signal_handler`` is allowed. The probes (HTTP + UDS) run in a
background thread that fires ``SIGTERM`` at the end, exercising the same
shutdown path the production server uses.

If this fails, the fallback (per plan DR-5) is "UDS lives in its own uvicorn
process" — a separate ``agent-brain-serve --uds-only`` instance, discovered
via ``runtime.json``. That fallback is implemented in Phase 2.

Run:

    poetry run -C agent-brain-uds python ../scripts/spike_dual_bind.py
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import signal
import socket as _socket
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


def _build_app() -> Starlette:
    """A minimal ASGI app that mirrors the real ``/health/`` shape."""

    async def health(_request: object) -> JSONResponse:
        return JSONResponse({"status": "healthy", "spike": True})

    return Starlette(routes=[Route("/health/", health)])


@dataclass
class ProbeOutcome:
    """Results passed from the background probe thread back to main."""

    http_ok: bool = False
    uds_ok: bool = False
    error: str | None = None
    notes: list[str] = field(default_factory=list)


async def _serve_dual(
    server_tcp: uvicorn.Server,
    server_uds: uvicorn.Server,
    socket_path: Path,
) -> None:
    """Run both ``uvicorn.Server``s on one loop, with signal-driven shutdown."""

    def _request_shutdown(*_args: object) -> None:
        server_tcp.should_exit = True
        server_uds.should_exit = True

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, _request_shutdown)

    try:
        await asyncio.gather(server_tcp.serve(), server_uds.serve())
    finally:
        # uvicorn unlinks on graceful shutdown, but if it didn't (abnormal
        # exit), we still want the socket gone.
        with contextlib.suppress(FileNotFoundError):
            Path(socket_path).unlink()


def _pick_free_port() -> int:
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for(predicate, *, timeout: float = 5.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


def _probe_http(host: str, port: int) -> bool:
    try:
        response = httpx.get(f"http://{host}:{port}/health/", timeout=3.0)
        response.raise_for_status()
        return response.json().get("status") == "healthy"
    except Exception:  # noqa: BLE001 — spike script; surface via outcome
        return False


def _probe_uds(socket_path: Path) -> bool:
    try:
        transport = httpx.HTTPTransport(uds=str(socket_path))
        with httpx.Client(
            transport=transport, base_url="http://agent-brain", timeout=3.0
        ) as client:
            response = client.get("/health/")
            response.raise_for_status()
            return response.json().get("status") == "healthy"
    except Exception:  # noqa: BLE001
        return False


def _run_probes_then_sigterm(
    host: str,
    port: int,
    socket_path: Path,
    outcome: ProbeOutcome,
) -> None:
    """Background thread: wait for bind, probe, then fire SIGTERM."""
    try:
        if not _wait_for(socket_path.exists, timeout=5.0):
            outcome.error = f"socket {socket_path} not created within timeout"
            os.kill(os.getpid(), signal.SIGTERM)
            return
        # Lock down socket perms; uvicorn binds at the process umask default.
        os.chmod(socket_path, 0o600)

        if not _wait_for(lambda: _probe_http(host, port), timeout=5.0):
            outcome.error = "HTTP /health/ never responded healthy"
            os.kill(os.getpid(), signal.SIGTERM)
            return
        outcome.http_ok = True
        outcome.notes.append(f"HTTP /health/ OK on {host}:{port}")

        outcome.uds_ok = _probe_uds(socket_path)
        if outcome.uds_ok:
            outcome.notes.append(f"UDS /health/ OK on {socket_path}")
        else:
            outcome.error = "UDS /health/ did not respond healthy"
    finally:
        # Trigger shutdown via the same path the production server uses.
        os.kill(os.getpid(), signal.SIGTERM)


def run_spike(*, host: str = "127.0.0.1", port: int | None = None) -> int:
    port = port or _pick_free_port()

    tmpdir = Path(tempfile.mkdtemp(prefix="ab-spike-"))
    os.chmod(tmpdir, 0o700)
    socket_path = tmpdir / "agent-brain.sock"

    app = _build_app()
    cfg_tcp = uvicorn.Config(
        app=app, host=host, port=port, log_level="warning", lifespan="on"
    )
    cfg_uds = uvicorn.Config(
        app=app, uds=str(socket_path), log_level="warning", lifespan="off"
    )
    server_tcp = uvicorn.Server(cfg_tcp)
    server_uds = uvicorn.Server(cfg_uds)

    outcome = ProbeOutcome()
    probe_thread = threading.Thread(
        target=_run_probes_then_sigterm,
        args=(host, port, socket_path, outcome),
        daemon=True,
    )

    print(f"[spike] starting dual-bind on http://{host}:{port}/ and {socket_path}")
    probe_thread.start()
    try:
        # Main-thread asyncio loop — required for add_signal_handler to work.
        asyncio.run(_serve_dual(server_tcp, server_uds, socket_path))
    except KeyboardInterrupt:  # pragma: no cover — manual interrupt
        pass
    probe_thread.join(timeout=5.0)

    failures: list[str] = []
    for note in outcome.notes:
        print(f"[spike] {note}")
    if outcome.error:
        failures.append(outcome.error)
    if not outcome.http_ok:
        failures.append("HTTP probe never succeeded")
    if not outcome.uds_ok:
        failures.append("UDS probe never succeeded")
    if socket_path.exists():
        failures.append(f"socket file {socket_path} not cleaned up after shutdown")

    # Best-effort cleanup of tmpdir.
    with contextlib.suppress(OSError):
        for child in tmpdir.iterdir():
            child.unlink()
        tmpdir.rmdir()

    if failures:
        for f in failures:
            print(f"[spike] FAIL: {f}")
        return 1

    print("[spike] OK: SIGTERM shutdown completed; socket file removed.")
    print("[spike] PASS: dual-bind works; Phase 2 keeps single-process design.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)
    return run_spike(host=args.host, port=args.port)


if __name__ == "__main__":
    sys.exit(main())
