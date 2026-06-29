"""Register the Agent Brain MCP server into a runtime's config file.

Each runtime discovers MCP servers from its own JSON config:

* **Claude Code** — an ``mcpServers`` object in a project-level ``.mcp.json`` (or
  the user-level ``~/.claude.json`` for global scope). Each entry is
  ``{command, args, env}``.
* **OpenCode** — an ``mcp`` object in the project-root ``opencode.json`` (or
  ``~/.config/opencode/opencode.json`` for global scope). Each entry is
  ``{type: "local", command: [...], enabled: true, environment: {...}}`` — the
  executable and its args are fused into one ``command`` array.
* **Codex** — a ``[mcp_servers.<name>]`` TOML table in
  ``$CODEX_HOME/config.toml`` (default ``~/.codex/config.toml``). The entry
  shape mirrors Claude's (``command`` string, ``args`` array, ``env`` table) but
  the file is TOML, so it is merged with tomlkit to preserve the user's other
  servers, top-level keys, and comments.

These writers deliberately do NOT shell out to a runtime CLI (``claude mcp add``
etc.): the file-based path is dependency-free, deterministic, dry-run friendly,
and matches the file-writing pattern the rest of ``install-agent`` already uses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

MCP_SERVER_NAME = "agent-brain"
MCP_COMMAND = "agent-brain-mcp"
OPENCODE_SCHEMA_URL = "https://opencode.ai/config.json"


def _build_env(state_dir: Path, auth: str) -> dict[str, str]:
    """Build the environment block shared by every runtime's entry.

    The state dir is resolved to an absolute path — MCP clients launch the
    server from an unknown cwd, so a relative path would break discovery.
    ``oauth`` opts the client into the OAuth dance via ``AGENT_BRAIN_MCP_AUTH``.
    """
    env: dict[str, str] = {
        "AGENT_BRAIN_STATE_DIR": str(state_dir.expanduser().resolve())
    }
    if auth == "oauth":
        env["AGENT_BRAIN_MCP_AUTH"] = "oauth"
    return env


def build_mcp_server_entry(
    state_dir: Path,
    backend: str = "auto",
    auth: str = "none",
) -> dict[str, Any]:
    """Build the Claude Code ``mcpServers`` entry for the Agent Brain MCP server.

    Args:
        state_dir: The ``.agent-brain`` state directory the MCP server should use.
        backend: How the MCP server reaches ``agent-brain-serve``
            (``auto`` | ``uds`` | ``http``).
        auth: ``none`` (default) or ``oauth``.

    Returns:
        A dict suitable for ``mcpServers[<name>]``.
    """
    return {
        "command": MCP_COMMAND,
        "args": ["--backend", backend],
        "env": _build_env(state_dir, auth),
    }


def build_opencode_mcp_entry(
    state_dir: Path,
    backend: str = "auto",
    auth: str = "none",
) -> dict[str, Any]:
    """Build the OpenCode ``mcp`` entry for the Agent Brain MCP server.

    OpenCode fuses the executable and its args into one ``command`` array, uses
    ``environment`` (not ``env``), and marks local servers with
    ``type: "local"`` and ``enabled: true``.

    Args:
        state_dir: The ``.agent-brain`` state directory the MCP server should use.
        backend: How the MCP server reaches ``agent-brain-serve``
            (``auto`` | ``uds`` | ``http``).
        auth: ``none`` (default) or ``oauth``.

    Returns:
        A dict suitable for ``mcp[<name>]`` in ``opencode.json``.
    """
    return {
        "type": "local",
        "command": [MCP_COMMAND, "--backend", backend],
        "enabled": True,
        "environment": _build_env(state_dir, auth),
    }


@dataclass
class McpRegistrationResult:
    """Outcome of an MCP registration attempt."""

    path: Path
    action: str  # "created" | "updated" | "unchanged"
    server_name: str
    entry: dict[str, Any]


def _merge_json_mcp(
    config_path: Path,
    *,
    servers_key: str,
    entry: dict[str, Any],
    top_level_defaults: dict[str, Any] | None = None,
    dry_run: bool = False,
) -> McpRegistrationResult:
    """Merge an MCP entry into a JSON config under ``servers_key``.

    Shared skeleton for every JSON-config runtime: read (fail closed on corrupt
    JSON), compare the existing ``agent-brain`` entry, classify the action, and
    write only when something changed. Other servers and top-level keys are
    preserved.

    Args:
        config_path: Path to the runtime's JSON config file.
        servers_key: Top-level key holding the server map
            (``mcpServers`` for Claude, ``mcp`` for OpenCode).
        entry: The fully-built entry to store under ``[servers_key][name]``.
        top_level_defaults: Keys applied via ``setdefault`` when writing
            (e.g. OpenCode's ``$schema``); only touched on create/update.
        dry_run: When True, compute the action but write nothing.

    Returns:
        An :class:`McpRegistrationResult` describing what (would have) changed.

    Raises:
        ValueError: If an existing config file is not valid JSON.
    """
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

    servers = data.setdefault(servers_key, {})
    existing = servers.get(MCP_SERVER_NAME)

    if existing == entry:
        action = "unchanged"
    elif not file_existed:
        action = "created"
    else:
        action = "updated"

    if action != "unchanged" and not dry_run:
        for key, value in (top_level_defaults or {}).items():
            data.setdefault(key, value)
        servers[MCP_SERVER_NAME] = entry
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(data, indent=2) + "\n")

    return McpRegistrationResult(
        path=config_path,
        action=action,
        server_name=MCP_SERVER_NAME,
        entry=entry,
    )


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
    return _merge_json_mcp(
        config_path,
        servers_key="mcpServers",
        entry=build_mcp_server_entry(state_dir, backend=backend, auth=auth),
        dry_run=dry_run,
    )


def register_opencode_mcp(
    config_path: Path,
    state_dir: Path,
    *,
    backend: str = "auto",
    auth: str = "none",
    dry_run: bool = False,
) -> McpRegistrationResult:
    """Merge the Agent Brain MCP entry into an OpenCode config file.

    Args:
        config_path: Path to the project-root ``opencode.json`` (project) or
            ``~/.config/opencode/opencode.json`` (global).
        state_dir: The ``.agent-brain`` state directory for the server.
        backend: MCP backend selector passed to the server.
        auth: ``none`` or ``oauth``.
        dry_run: When True, compute the action but write nothing.

    Returns:
        An :class:`McpRegistrationResult` describing what (would have) changed.

    Raises:
        ValueError: If an existing config file is not valid JSON.
    """
    return _merge_json_mcp(
        config_path,
        servers_key="mcp",
        entry=build_opencode_mcp_entry(state_dir, backend=backend, auth=auth),
        top_level_defaults={"$schema": OPENCODE_SCHEMA_URL},
        dry_run=dry_run,
    )


def register_codex_mcp(
    config_path: Path,
    state_dir: Path,
    *,
    backend: str = "auto",
    auth: str = "none",
    dry_run: bool = False,
) -> McpRegistrationResult:
    """Merge the Agent Brain MCP entry into a Codex ``config.toml`` file.

    Codex stores MCP servers as ``[mcp_servers.<name>]`` TOML tables. The entry
    fields match Claude's (``command``/``args``/``env``), so the value is built
    with :func:`build_mcp_server_entry`; only the on-disk format differs. tomlkit
    parses and re-emits the document so the user's other servers, top-level keys,
    and comments are preserved.

    Args:
        config_path: Path to ``$CODEX_HOME/config.toml`` (default
            ``~/.codex/config.toml``). Codex has no project-level MCP config, so
            both install scopes target this user-level file.
        state_dir: The ``.agent-brain`` state directory for the server.
        backend: MCP backend selector passed to the server.
        auth: ``none`` or ``oauth``.
        dry_run: When True, compute the action but write nothing.

    Returns:
        An :class:`McpRegistrationResult` describing what (would have) changed.

    Raises:
        ValueError: If an existing config file is not valid TOML.
    """
    entry = build_mcp_server_entry(state_dir, backend=backend, auth=auth)

    file_existed = config_path.exists()
    if file_existed:
        try:
            doc = tomlkit.parse(config_path.read_text())
        except TOMLKitError as exc:
            raise ValueError(
                f"Existing {config_path.name} is not valid TOML: {exc}. "
                "Fix or remove it, then re-run."
            ) from exc
    else:
        doc = tomlkit.document()

    servers = doc.get("mcp_servers")
    if servers is None:
        servers = tomlkit.table()
        doc["mcp_servers"] = servers

    existing = servers.get(MCP_SERVER_NAME)
    existing_plain = existing.unwrap() if existing is not None else None

    if existing_plain == entry:
        action = "unchanged"
    elif not file_existed:
        action = "created"
    else:
        action = "updated"

    if action != "unchanged" and not dry_run:
        servers[MCP_SERVER_NAME] = entry
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(tomlkit.dumps(doc))

    return McpRegistrationResult(
        path=config_path,
        action=action,
        server_name=MCP_SERVER_NAME,
        entry=entry,
    )
