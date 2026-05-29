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
def main(
    backend: str | None,
    backend_url: str | None,
    state_dir: str | None,
) -> None:
    """Run the Agent Brain MCP server over stdio."""
    asyncio.run(
        main_async(
            backend=backend,
            backend_url=backend_url,
            state_dir=state_dir,
        )
    )


if __name__ == "__main__":
    main()
