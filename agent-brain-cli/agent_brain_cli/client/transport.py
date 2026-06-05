"""Transport selector — builds a DocServeClient over HTTP or UDS.

Plan §4.4: every CLI command should call ``open_client(ctx)`` instead of
``DocServeClient(base_url=resolved_url)`` directly. The selector reads
transport-related state off the Click context, calls
:func:`agent_brain_cli.config.resolve_transport`, then constructs the
appropriate wrapper.

The selector is intentionally tiny — three branches and one
``from_httpx`` call. Resolution logic stays in ``config.py`` so it is
testable without a live ``httpx.Client``.
"""

from __future__ import annotations

from pathlib import Path

import click

from ..config import resolve_api_key, resolve_transport
from .api_client import DocServeClient


def open_client(ctx: click.Context, *, timeout: float = 30.0) -> DocServeClient:
    """Construct a ``DocServeClient`` over the transport selected by ``ctx``.

    Args:
        ctx: Click context. Reads optional keys from ``ctx.obj``:
            ``transport_hint`` (``"http"`` / ``"uds"`` / ``"auto"`` /
            ``None``), ``base_url_override``, ``socket_path_override``,
            and ``debug_transport``.
        timeout: HTTP request timeout in seconds. Defaults to 30.

    Returns:
        A live ``DocServeClient``. The caller is responsible for closing
        it (use as a context manager).
    """
    obj = ctx.obj or {}
    transport, target = resolve_transport(
        transport_hint=obj.get("transport_hint"),
        base_url_override=obj.get("base_url_override"),
        socket_path_override=obj.get("socket_path_override"),
    )
    # Issue #179: resolve the API key alongside the transport so the same
    # CLI invocation works against an authed and an unauthed server.
    api_key = resolve_api_key()
    if obj.get("debug_transport"):
        auth_marker = "with X-API-Key" if api_key else "no auth"
        click.echo(
            f"[debug-transport] {transport} -> {target} ({auth_marker})", err=True
        )

    if transport == "http":
        return DocServeClient(base_url=target, timeout=timeout, api_key=api_key)

    # UDS: import lazily so HTTP-only invocations don't pay the cost.
    from agent_brain_uds import make_client

    inner = make_client(socket_path=Path(target), timeout=timeout)
    return DocServeClient.from_httpx(inner, api_key=api_key)
