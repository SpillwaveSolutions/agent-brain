"""Transport selector — builds a BackendClient over HTTP, UDS, or MCP.

Renamed in Phase 57 (Plan 57-01) from ``open_client`` to
``open_backend``. Return type widened from ``DocServeClient`` to
:class:`agent_brain_cli.client.protocol.BackendClient` so the
transport-dispatching factory can return any of:

  - ``DocServeClient`` (HTTP or UDS — the existing v1/v2 path)
  - ``McpStdioBackend`` (v3 stdio MCP — agent-brain-mcp subprocess)
  - ``McpHttpBackend`` (v3 streamable HTTP MCP — loopback listener)

The MCP backends are imported lazily inside the ``transport == "mcp"``
branch so HTTP/UDS-only invocations do NOT pay the MCP SDK import
cost AND so the CLI runs cleanly without ``agent-brain-mcp``
installed when the user never asks for it (CONTEXT decision: soft
dep on agent-brain-mcp).

Three §3.5 design-doc misuse cases surface as ``click.UsageError``
(exit code 2 — v10.2 HTTP-03 no-silent-fallback contract):

  1. ``--transport mcp`` + ``agent-brain-mcp`` package not installed
     → "install agent-brain-mcp to use --transport mcp"
  2. ``--mcp-transport http`` without ``--mcp-url`` (and no
     ``AGENT_BRAIN_MCP_URL`` env) AND no ``mcp.runtime.json``
     discovery file → raised by ``resolve_mcp_transport`` with the
     verbatim v3 §3.5 wording (Phase 58 CLI-MCP-08)
  3. ``--mcp-transport stdio`` + ``agent-brain-mcp`` not reachable
     on ``PATH`` (``shutil.which`` returns ``None``)
     → "agent-brain-mcp not found on PATH; install agent-brain-mcp
        into the same Python environment"
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import cast

import click

from ..config import resolve_api_key, resolve_mcp_transport, resolve_transport
from .api_client import DocServeClient
from .protocol import BackendClient, McpBackend


def _resolve_state_dir_for_discovery() -> Path | None:
    """Resolve state_dir for mcp.runtime.json discovery (Phase 58 CLI-MCP-08).

    Mirrors the chain used by ``agent-brain mcp start``. Returns None on
    any failure — callers treat that as "no discovery possible" and
    fall through to the explicit-url-or-error path inside
    ``resolve_mcp_transport``.
    """
    try:
        from agent_brain_cli.config import resolve_project_root
        from agent_brain_cli.migration import resolve_state_dir_with_fallback
        from agent_brain_cli.xdg_paths import migrate_legacy_paths

        migrate_legacy_paths()
        project_root = resolve_project_root()
        return resolve_state_dir_with_fallback(project_root)
    except Exception:
        return None


def _stdio_command(state_dir: Path | None) -> str | list[str]:
    """Build the ``agent-brain-mcp`` stdio command, pinning the state dir.

    When ``state_dir`` is resolved, returns
    ``["agent-brain-mcp", "--state-dir", <path>]`` so the spawned MCP
    server resolves the same backend the CLI's UDS path would (CLI-MCP-04
    byte-identical guarantee). ``McpStdioBackend`` filters the subprocess
    env through ``DEFAULT_ENV_ALLOWLIST`` (which intentionally drops
    ``AGENT_BRAIN_STATE_DIR``), so an explicit arg is the only reliable
    way to propagate the state dir across the env boundary.

    ``AGENT_BRAIN_STATE_DIR`` takes precedence over the discovery value,
    mirroring the UDS leg (``resolve_transport`` →
    ``resolve_socket_path`` honors the same override). Without this, a
    user who sets ``AGENT_BRAIN_STATE_DIR`` and runs from a non-project
    cwd would get the project-root discovery dir on the MCP leg but the
    override on the UDS leg — diverging the two and breaking CLI-MCP-04.

    When neither the env override nor ``state_dir`` resolves, returns the
    bare ``"agent-brain-mcp"`` string and lets the subprocess fall back
    to its own cwd-based discovery — preserving pre-fix behavior.
    """
    env_override = os.environ.get("AGENT_BRAIN_STATE_DIR")
    if env_override:
        resolved: str | None = str(Path(env_override).expanduser())
    elif state_dir is not None:
        resolved = str(state_dir)
    else:
        resolved = None

    if resolved is None:
        return "agent-brain-mcp"
    return ["agent-brain-mcp", "--state-dir", resolved]


def open_backend(ctx: click.Context, *, timeout: float = 30.0) -> BackendClient:
    """Construct a ``BackendClient`` over the transport selected by ``ctx``.

    Reads from ``ctx.obj`` (set by the top-level Click group in
    ``cli.py``):

      - ``transport_hint`` (``"auto"`` / ``"http"`` / ``"uds"`` /
        ``"mcp"`` / ``None``)
      - ``base_url_override``, ``socket_path_override``
      - ``mcp_transport_hint`` (``"stdio"`` / ``"http"`` / ``None``)
      - ``mcp_url_override`` (URL string or ``None``)
      - ``debug_transport`` (bool)

    Dispatch (in order):

      1. ``transport == "mcp"`` and ``mcp_transport == "stdio"`` →
         :class:`McpStdioBackend(command="agent-brain-mcp")` (precheck:
         ``shutil.which("agent-brain-mcp")`` must be non-None or
         raises with §3.5 case 3 wording)
      2. ``transport == "mcp"`` and ``mcp_transport == "http"`` →
         :class:`McpHttpBackend(url=resolved_mcp_url, timeout=timeout)`
      3. ``transport == "http"`` → :class:`DocServeClient`
      4. ``transport == "uds"`` → :class:`DocServeClient.from_httpx`

    Raises:
        click.UsageError: With exit code 2 when any of the three
            §3.5 design-doc misuse cases hit. NO silent fallback to
            UDS or HTTP — the operator's choice is honored or the
            CLI exits non-zero (v10.2 HTTP-03 contract).
    """
    obj = ctx.obj or {}
    transport_hint = obj.get("transport_hint")
    api_key = resolve_api_key()

    # --- MCP branch (v3) -----------------------------------------
    if (transport_hint or "").lower() == "mcp":
        state_dir = _resolve_state_dir_for_discovery()
        mcp_transport, mcp_target = resolve_mcp_transport(
            mcp_transport_hint=obj.get("mcp_transport_hint"),
            mcp_url_override=obj.get("mcp_url_override"),
            state_dir=state_dir,
        )
        if obj.get("debug_transport"):
            auth_marker = "with Bearer token" if api_key else "no auth"
            target_label = mcp_target if mcp_target else "subprocess: agent-brain-mcp"
            click.echo(
                f"[debug-transport] mcp ({mcp_transport}) -> "
                f"{target_label} ({auth_marker})",
                err=True,
            )
        try:
            from agent_brain_mcp.client import (  # noqa: F401
                McpHttpBackend,
                McpStdioBackend,
            )
        except ImportError as exc:
            raise click.UsageError(
                "install agent-brain-mcp to use --transport mcp"
            ) from exc

        if mcp_transport == "stdio":
            # §3.5 case 3 precheck — agent-brain-mcp must be on PATH
            # before we hand off to the subprocess-spawning backend.
            # Verbatim §3.5 wording — DO NOT paraphrase.
            if shutil.which("agent-brain-mcp") is None:
                raise click.UsageError(
                    "agent-brain-mcp not found on PATH; install "
                    "agent-brain-mcp into the same Python environment"
                )
            # Pin the resolved state dir into the subprocess as an
            # explicit --state-dir arg (CLI-MCP-04). McpStdioBackend
            # filters env through DEFAULT_ENV_ALLOWLIST, which drops
            # AGENT_BRAIN_STATE_DIR, so without this the spawned
            # agent-brain-mcp falls back to cwd discovery and may resolve
            # a DIFFERENT backend than --transport uds. Passing the dir
            # explicitly makes the byte-identical guarantee hold from any
            # cwd. When state_dir is None (resolution failed) we keep the
            # bare command and let agent-brain-mcp do its own cwd discovery.
            command = _stdio_command(state_dir)
            # cast(): agent_brain_mcp ships with ignore_missing_imports=true
            # so mypy treats McpStdioBackend as Any. The runtime
            # @runtime_checkable Protocol contract is pinned by the
            # Phase 56-03 isinstance test in agent-brain-mcp/tests/.
            return cast(BackendClient, McpStdioBackend(command=command))
        # mcp_transport == "http" — resolve_mcp_transport guarantees
        # mcp_target is not None for the http branch.
        assert mcp_target is not None  # noqa: S101
        return cast(BackendClient, McpHttpBackend(url=mcp_target, timeout=timeout))

    # --- HTTP / UDS branch (existing v1/v2 path) -----------------
    transport, target = resolve_transport(
        transport_hint=transport_hint,
        base_url_override=obj.get("base_url_override"),
        socket_path_override=obj.get("socket_path_override"),
    )
    if obj.get("debug_transport"):
        auth_marker = "with X-API-Key" if api_key else "no auth"
        click.echo(
            f"[debug-transport] {transport} -> {target} ({auth_marker})",
            err=True,
        )

    if transport == "http":
        return DocServeClient(base_url=target, timeout=timeout, api_key=api_key)

    # UDS: lazy import so HTTP-only invocations don't pay the cost.
    from agent_brain_uds import make_client

    inner = make_client(socket_path=Path(target), timeout=timeout)
    return DocServeClient.from_httpx(inner, api_key=api_key)


def open_mcp_backend(ctx: click.Context, *, timeout: float = 30.0) -> McpBackend:
    """Construct an ``McpBackend`` for MCP-only CLI commands (Phase 59).

    Sibling to :func:`open_backend`: that dispatcher returns a
    :class:`BackendClient` (the tools surface — health/query/index/etc.)
    over any of HTTP/UDS/MCP; this factory returns an
    :class:`McpBackend` (the prompts + resources surface — get_prompt /
    list_resources / read_resource) exclusively over MCP. Every Phase 59
    MCP-only command (``agent-brain prompt``, ``agent-brain resources
    *``) calls this instead of :func:`open_backend` so the
    ``--transport mcp`` check lives at a single point of contract.

    Reads from ``ctx.obj`` (set by the top-level Click group in
    ``cli.py``):

      - ``transport_hint`` — MUST be ``"mcp"`` (case-insensitive); any
        other value raises :class:`click.UsageError` per the Phase 57
        §3.5 no-silent-fallback contract.
      - ``mcp_transport_hint`` (``"stdio"`` / ``"http"`` / ``None``)
      - ``mcp_url_override`` (URL string or ``None``)
      - ``debug_transport`` (bool)

    Dispatch:

      1. ``mcp_transport == "stdio"`` →
         :class:`McpStdioBackend(command="agent-brain-mcp")` (precheck:
         ``shutil.which("agent-brain-mcp")`` must be non-None; same
         §3.5 case-3 wording as :func:`open_backend`).
      2. ``mcp_transport == "http"`` →
         :class:`McpHttpBackend(url=resolved_mcp_url, timeout=timeout)`.

    Raises:
        click.UsageError: Exit code 2 when (1) ``transport_hint`` is
            not ``"mcp"``, (2) ``agent-brain-mcp`` is not installed,
            (3) stdio binary not on PATH. Carries the Phase 57 §3.5
            verbatim wording — no silent fallback.
    """
    obj = ctx.obj or {}
    transport_hint = (obj.get("transport_hint") or "").lower()
    if transport_hint != "mcp":
        # Generic per-factory wording. Each MCP-only command may wrap
        # this and replace the trailing ``<command>`` placeholder with
        # its own name (``prompt``, ``resources list``, etc.) — the
        # default is sufficient for Plan 59-01's contract test and for
        # the rare case where a future command forgets the wrapper.
        raise click.UsageError(
            "This command requires --transport mcp; example: "
            "agent-brain --transport mcp --mcp-transport stdio <command>"
        )

    state_dir = _resolve_state_dir_for_discovery()
    mcp_transport, mcp_target = resolve_mcp_transport(
        mcp_transport_hint=obj.get("mcp_transport_hint"),
        mcp_url_override=obj.get("mcp_url_override"),
        state_dir=state_dir,
    )
    if obj.get("debug_transport"):
        target_label = mcp_target if mcp_target else "subprocess: agent-brain-mcp"
        click.echo(
            f"[debug-transport] mcp-only ({mcp_transport}) -> {target_label}",
            err=True,
        )
    try:
        from agent_brain_mcp.client import (  # noqa: F401
            McpHttpBackend,
            McpStdioBackend,
        )
    except ImportError as exc:
        raise click.UsageError(
            "install agent-brain-mcp to use --transport mcp"
        ) from exc

    if mcp_transport == "stdio":
        # §3.5 case 3 precheck — verbatim wording, same as open_backend.
        if shutil.which("agent-brain-mcp") is None:
            raise click.UsageError(
                "agent-brain-mcp not found on PATH; install "
                "agent-brain-mcp into the same Python environment"
            )
        # Pin the resolved state dir into the subprocess (CLI-MCP-04) —
        # same rationale as open_backend: DEFAULT_ENV_ALLOWLIST drops
        # AGENT_BRAIN_STATE_DIR, so prompts/resources would otherwise run
        # against a cwd-discovered backend.
        command = _stdio_command(state_dir)
        # cast(): mirrors open_backend's pattern. The runtime
        # @runtime_checkable Protocol contract is pinned by the
        # Plan 59-01 isinstance test in agent-brain-mcp/tests/
        # test_mcp_backend_protocol_skeleton.py.
        return cast(McpBackend, McpStdioBackend(command=command))
    # mcp_transport == "http" — resolve_mcp_transport guarantees
    # mcp_target is not None for the http branch.
    assert mcp_target is not None  # noqa: S101
    return cast(McpBackend, McpHttpBackend(url=mcp_target, timeout=timeout))
