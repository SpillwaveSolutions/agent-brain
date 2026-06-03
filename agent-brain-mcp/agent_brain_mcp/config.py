"""Backend selection — builds an httpx.Client over HTTP or UDS.

The MCP server speaks stdio to the LLM client and HTTP (or UDS) to the
Agent Brain backend. ``open_backend_client(...)`` picks the right
transport per the CLI flags / env vars and returns a live
``httpx.Client`` the :class:`agent_brain_mcp.client.ApiClient` wraps.

Resolution precedence (plan §7):
  1. Explicit ``backend`` argument ("uds" / "http" / "auto")
  2. ``AGENT_BRAIN_MCP_BACKEND`` env var
  3. Default: ``"auto"`` — UDS if validates, HTTP otherwise

For HTTP:
  - explicit ``backend_url`` arg →
  - ``AGENT_BRAIN_MCP_BACKEND_URL`` env →
  - ``AGENT_BRAIN_URL`` env →
  - runtime.json::base_url (if a server is running for this state dir) →
  - default ``http://127.0.0.1:8000``

For UDS:
  - explicit ``socket_path`` arg →
  - ``AGENT_BRAIN_UDS_PATH`` env →
  - ``resolve_socket_path(state_dir)``

Phase 52 (Plan 03) adds subscription-side settings — currently only the
``corpus://folders`` active-poll cadence (CONTEXT decision E: client-side
polling, no new server endpoint). The safety-poll cadence is parked
behind a settings knob too even though Plan 03 does NOT consume it; it
is reserved for a future v3 micro-plan if the 5s active cadence proves
insufficient. Both knobs read env vars at import time — there is NO
hot-reload (Phase 52 CONTEXT specifics: "read at MCP server startup, no
hot-reload in v2").
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

import httpx
from agent_brain_uds import (
    AgentBrainUdsError,
    resolve_socket_path,
    validate_socket,
)
from agent_brain_uds import (
    make_client as make_uds_client,
)
from pydantic import BaseModel, Field, ValidationError

DEFAULT_HTTP_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = 30.0
STATE_DIR_NAME = ".agent-brain"


# ---------------------------------------------------------------------------
# Subscription settings (Phase 52 Plan 03)
# ---------------------------------------------------------------------------


class MCPSubscriptionSettings(BaseModel):
    """Per-process MCP subscription tuning knobs.

    Currently scopes the ``corpus://folders`` polling cadence. Phase 52
    CONTEXT specifics §2 calls for these to be settings-driven so
    operators can tune the active-vs-safety trade-off without touching
    code. Both fields are floats with ``gt=0`` validation — non-positive
    intervals would either starve the loop (0) or invert the asyncio
    sleep contract (<0).

    Attributes:
        folders_active_interval_s: Seconds between successive polls of
            ``GET /index/folders/`` while at least one subscriber is
            active for ``corpus://folders``. Default 5.0s — Phase 52
            CONTEXT decision B picks this as the trade-off between
            responsiveness and HTTP round-trip cost.
        folders_safety_interval_s: Reserved settings knob for a future
            v3 "safety poll" cadence (CONTEXT decision E). Plan 03 does
            NOT wire this through the polling loop — the active 5s
            cadence already runs while subscribed, and there is no
            no-subscribers branch in the v2 design. Documented here so
            operators can pre-stage the value if v3 lands.
    """

    folders_active_interval_s: float = Field(
        default=5.0,
        gt=0,
        description=(
            "Active-subscriber polling cadence for corpus://folders, "
            "seconds. CorpusFoldersPolicy injects this at module import "
            "time (no hot-reload in v2)."
        ),
    )
    folders_safety_interval_s: float = Field(
        default=60.0,
        gt=0,
        description=(
            "Safety-poll cadence, seconds. Reserved for v3 — Plan 03 "
            "does not consume this. Documented so operators can pre-"
            "stage the value."
        ),
    )


def _load_subscription_settings() -> MCPSubscriptionSettings:
    """Read MCP subscription settings from environment variables.

    The two env vars consumed are:

    * ``AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_ACTIVE_INTERVAL_S``
    * ``AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_SAFETY_INTERVAL_S``

    Both parse as ``float``. Pydantic validates ``gt=0`` and raises
    :class:`pydantic.ValidationError` if the value is non-positive or
    malformed. The caller (module-level :data:`mcp_subscription_settings`
    in this module) catches it and re-raises as a clear ``RuntimeError``
    with the offending env var name so startup failure is debuggable.

    No env var set → Pydantic default is used (5.0 / 60.0).
    """
    raw: dict[str, float] = {}
    active = os.environ.get("AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_ACTIVE_INTERVAL_S")
    if active is not None:
        try:
            raw["folders_active_interval_s"] = float(active)
        except ValueError as exc:
            raise RuntimeError(
                "AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_ACTIVE_INTERVAL_S "
                f"must be a float, got {active!r}"
            ) from exc
    safety = os.environ.get("AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_SAFETY_INTERVAL_S")
    if safety is not None:
        try:
            raw["folders_safety_interval_s"] = float(safety)
        except ValueError as exc:
            raise RuntimeError(
                "AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_SAFETY_INTERVAL_S "
                f"must be a float, got {safety!r}"
            ) from exc
    try:
        return MCPSubscriptionSettings(**raw)
    except ValidationError as exc:
        # Re-raise with offending env var names included for operator
        # debuggability — Pydantic's default message references field
        # names, not env vars.
        raise RuntimeError(
            "Invalid MCP subscription settings (env vars "
            "AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_ACTIVE_INTERVAL_S / "
            "AGENT_BRAIN_MCP_SUBSCRIPTION_FOLDERS_SAFETY_INTERVAL_S): "
            f"{exc}"
        ) from exc


# Module-level singleton read at import time. Plan 03's
# :class:`CorpusFoldersPolicy` instantiates with this value at
# subscriptions/policies.py module-load. No hot-reload — restart the
# MCP server to pick up env-var changes (CONTEXT specifics §3).
mcp_subscription_settings: MCPSubscriptionSettings = _load_subscription_settings()


def _resolve_state_dir(state_dir: Path | None) -> Path | None:
    if state_dir is not None:
        return state_dir
    env_dir = os.environ.get("AGENT_BRAIN_STATE_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    candidate = Path.cwd() / STATE_DIR_NAME
    return candidate if candidate.exists() else None


def _resolve_http_url(
    backend_url: str | None,
    state_dir: Path | None,
) -> str:
    if backend_url:
        return backend_url
    env_url = os.environ.get("AGENT_BRAIN_MCP_BACKEND_URL") or os.environ.get(
        "AGENT_BRAIN_URL"
    )
    if env_url:
        return env_url
    sdir = _resolve_state_dir(state_dir)
    if sdir is not None:
        runtime = sdir / "runtime.json"
        if runtime.exists():
            try:
                data = json.loads(runtime.read_text())
                if data.get("base_url"):
                    return str(data["base_url"])
            except (json.JSONDecodeError, OSError):
                pass
    return DEFAULT_HTTP_BASE_URL


def _read_runtime_socket_path(state_dir: Path | None) -> Path | None:
    """Return ``socket_path`` from ``<state_dir>/runtime.json`` if set.

    Mirrors what ``_resolve_http_url`` does for ``base_url`` so UDS
    resolution honours the same authoritative source the CLI writes when
    starting the server (Phase 7 / reviewer #7).
    """
    sdir = _resolve_state_dir(state_dir)
    if sdir is None:
        return None
    runtime = sdir / "runtime.json"
    if not runtime.exists():
        return None
    try:
        data = json.loads(runtime.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    sp = data.get("socket_path")
    if not isinstance(sp, str) or not sp:
        return None
    return Path(sp).expanduser()


def _open_uds_client(
    socket_path: Path | None,
    state_dir: Path | None,
    timeout: float,
) -> httpx.Client:
    if socket_path is None:
        env_path = os.environ.get("AGENT_BRAIN_UDS_PATH")
        if env_path:
            socket_path = Path(env_path).expanduser()
        else:
            socket_path = _read_runtime_socket_path(state_dir) or resolve_socket_path(
                state_dir
            )
    validate_socket(socket_path)
    client: httpx.Client = make_uds_client(socket_path=socket_path, timeout=timeout)
    return client


def _open_http_client(backend_url: str, timeout: float) -> httpx.Client:
    return httpx.Client(base_url=backend_url, timeout=timeout)


def open_backend_client(
    *,
    backend: Literal["auto", "uds", "http"] | None = None,
    backend_url: str | None = None,
    socket_path: Path | None = None,
    state_dir: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[Literal["uds", "http"], httpx.Client]:
    """Return ``(transport, client)`` for the chosen backend.

    Auto mode tries UDS validation first; on any
    :class:`AgentBrainUdsError` falls back to HTTP transparently.
    """
    chosen = (backend or os.environ.get("AGENT_BRAIN_MCP_BACKEND") or "auto").lower()

    if chosen == "http":
        url = _resolve_http_url(backend_url, state_dir)
        return ("http", _open_http_client(url, timeout))

    if chosen == "uds":
        return ("uds", _open_uds_client(socket_path, state_dir, timeout))

    # auto
    try:
        return ("uds", _open_uds_client(socket_path, state_dir, timeout))
    except (AgentBrainUdsError, OSError, FileNotFoundError):
        url = _resolve_http_url(backend_url, state_dir)
        return ("http", _open_http_client(url, timeout))
