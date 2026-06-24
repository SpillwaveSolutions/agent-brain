"""Register the Agent Brain MCP server into a Claude Code config file.

Claude Code discovers MCP servers from a JSON config with an ``mcpServers``
object — a project-level ``.mcp.json`` at the project root, or the user-level
``~/.claude.json`` for global scope. This module writes/merges the
``agent-brain`` entry into that file without disturbing other servers or keys.

It deliberately does NOT shell out to ``claude mcp add``: the file-based path is
dependency-free (no ``claude`` CLI required), deterministic, dry-run friendly,
and matches the file-writing pattern the rest of ``install-agent`` already uses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MCP_SERVER_NAME = "agent-brain"
MCP_COMMAND = "agent-brain-mcp"


def build_mcp_server_entry(
    state_dir: Path,
    backend: str = "auto",
    auth: str = "none",
) -> dict[str, Any]:
    """Build the ``mcpServers`` entry for the Agent Brain MCP server.

    Args:
        state_dir: The ``.agent-brain`` state directory the MCP server should
            use. Resolved to an absolute path — MCP clients launch the server
            from an unknown cwd, so a relative path would break discovery.
        backend: How the MCP server reaches ``agent-brain-serve``
            (``auto`` | ``uds`` | ``http``).
        auth: ``none`` (default) or ``oauth``. ``oauth`` injects
            ``AGENT_BRAIN_MCP_AUTH=oauth`` to opt the client into the OAuth dance.

    Returns:
        A dict suitable for ``mcpServers[<name>]``.
    """
    env: dict[str, str] = {
        "AGENT_BRAIN_STATE_DIR": str(state_dir.expanduser().resolve())
    }
    if auth == "oauth":
        env["AGENT_BRAIN_MCP_AUTH"] = "oauth"
    return {
        "command": MCP_COMMAND,
        "args": ["--backend", backend],
        "env": env,
    }


@dataclass
class McpRegistrationResult:
    """Outcome of an MCP registration attempt."""

    path: Path
    action: str  # "created" | "updated" | "unchanged"
    server_name: str
    entry: dict[str, Any]


def register_claude_mcp(
    config_path: Path,
    state_dir: Path,
    *,
    backend: str = "auto",
    auth: str = "none",
    dry_run: bool = False,
) -> McpRegistrationResult:
    """Merge the Agent Brain MCP entry into a Claude Code config file.

    Args:
        config_path: Path to ``.mcp.json`` (project) or ``~/.claude.json`` (global).
        state_dir: The ``.agent-brain`` state directory for the server.
        backend: MCP backend selector passed to the server.
        auth: ``none`` or ``oauth``.
        dry_run: When True, compute the action but write nothing.

    Returns:
        An :class:`McpRegistrationResult` describing what (would have) changed.

    Raises:
        ValueError: If an existing config file is not valid JSON.
    """
    entry = build_mcp_server_entry(state_dir, backend=backend, auth=auth)

    data: dict[str, Any]
    file_existed = config_path.exists()
    if file_existed:
        try:
            data = json.loads(config_path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Existing {config_path.name} is not valid JSON: {exc}. "
                "Fix or remove it, then re-run."
            ) from exc
    else:
        data = {}

    servers = data.setdefault("mcpServers", {})
    existing = servers.get(MCP_SERVER_NAME)

    if existing == entry:
        action = "unchanged"
    elif not file_existed:
        action = "created"
    else:
        action = "updated"

    if action != "unchanged" and not dry_run:
        servers[MCP_SERVER_NAME] = entry
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(data, indent=2) + "\n")

    return McpRegistrationResult(
        path=config_path,
        action=action,
        server_name=MCP_SERVER_NAME,
        entry=entry,
    )
