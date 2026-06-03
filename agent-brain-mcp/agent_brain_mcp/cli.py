"""``agent-brain-mcp`` CLI entry point — Click wrapper around server.main_async."""

from __future__ import annotations

import asyncio

import click

from .http import probe_port_available, validate_loopback_host
from .server import main_async


@click.command("agent-brain-mcp")
@click.option(
    "--backend",
    type=click.Choice(["auto", "uds", "http"], case_sensitive=False),
    default=None,
    help=(
        "Backend transport: auto (default), uds, or http. "
        "Honors AGENT_BRAIN_MCP_BACKEND env."
    ),
)
@click.option(
    "--backend-url",
    default=None,
    help=(
        "Explicit HTTP base URL for the Agent Brain server. "
        "Honors AGENT_BRAIN_MCP_BACKEND_URL / AGENT_BRAIN_URL env."
    ),
)
@click.option(
    "--state-dir",
    type=click.Path(),
    default=None,
    help=(
        "Override the Agent Brain state directory used to locate UDS "
        "socket + runtime.json. Honors AGENT_BRAIN_STATE_DIR env."
    ),
)
@click.option(
    "--transport",
    type=click.Choice(["stdio", "http"], case_sensitive=False),
    default="stdio",
    show_default=True,
    help=(
        "Listen transport. Auth deferred to v4 — http binds loopback only. "
        "AGENT_BRAIN_MCP_TRANSPORT env is reserved but NOT honored in v2 "
        "(Phase 53 D-02)."
    ),
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    show_default=True,
    help=(
        "Loopback host for --transport http. Only 127.0.0.1 / localhost / ::1 "
        "accepted (validated at startup in Plan 02)."
    ),
)
@click.option(
    "--port",
    type=click.IntRange(1, 65535),
    default=8765,
    show_default=True,
    help="TCP port for --transport http.",
)
def main(
    backend: str | None,
    backend_url: str | None,
    state_dir: str | None,
    transport: str,
    host: str,
    port: int,
) -> None:
    """Run the Agent Brain MCP server over stdio or Streamable HTTP."""
    # Phase 53 Plan 03: validate the loopback whitelist + probe the
    # port at the CLI layer BEFORE main_async() opens the backend
    # httpx client. The Plan 02 in-process checks inside ``run_http``
    # still serve as defense-in-depth for direct callers that bypass
    # the CLI (tests, embeddings), but operators get the fastest /
    # cleanest failure mode when the misconfiguration is rejected here.
    # Without these hoists, ``--transport http --host 0.0.0.0`` (or
    # ``--port <occupied>``) against a missing backend surfaces as
    # ``BackendUnavailable`` (the version-compat check fires before
    # the dispatcher reaches run_http) — a confusing error that hides
    # the real misconfiguration.
    if transport == "http":
        validate_loopback_host(host)
        probe_port_available(host, port)
    asyncio.run(
        main_async(
            backend=backend,
            backend_url=backend_url,
            state_dir=state_dir,
            transport=transport,
            host=host,
            port=port,
        )
    )


if __name__ == "__main__":
    main()
