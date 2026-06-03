"""``agent-brain-mcp`` CLI entry point — Click wrapper around server.main_async."""

from __future__ import annotations

import asyncio

import click

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
