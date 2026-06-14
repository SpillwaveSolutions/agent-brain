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

Phase 66 (Plan 01) adds the auth-mode toggle settings foundation (OAUTH-09):
  - ``AuthMode`` — typed enum over {none, basic, oauth}; default none
  - ``resolve_auth_mode()`` — reads AGENT_BRAIN_AUTH; unset → AuthMode.none
  - ``resolve_oauth_settings()`` — reads AGENT_BRAIN_OAUTH_RESOURCE and
    AGENT_BRAIN_OAUTH_ISSUER; pure-read, no validation (gate validates)
  - ``_raw_auth_mode()`` — raw lowercased env value used by the startup gate
  - ``check_auth_startup_gate()`` — boot-time gate; exits code 2 on misconfig
  - ``get_auth_dependency()`` — single mutual-exclusion auth selector seam

Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
  §"Auth-Mode Toggle and Deployment Shapes" (three-mode table)
  §"Canonical Resource URI Contract" (AGENT_BRAIN_OAUTH_RESOURCE format)
  §"Startup Gate: AGENT_BRAIN_OAUTH_RESOURCE Must Be Non-Empty in oauth Mode"
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.parse
from enum import Enum
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth-mode toggle (Phase 66 Plan 01 — OAUTH-09)
# ---------------------------------------------------------------------------

_VALID_AUTH_MODES = {"none", "basic", "oauth"}


class AuthMode(str, Enum):
    """Typed auth-mode toggle for the MCP server (OAUTH-09).

    Controls which authentication path the MCP server enforces on
    incoming connections. The toggle is mutually exclusive — exactly one
    mode is active at any time.

    Members:
        none:  No authentication (default). Loopback dev / trusted
               private network. No credentials required.
        basic: AGENT_BRAIN_API_KEY shared-secret Bearer token (the
               existing SECURITY-01 contract from Phase 66). No OAuth
               infrastructure needed.
        oauth: OAuth 2.1 Authorization Code flow via the Authorization
               Server embedded in the MCP server. Requires a valid
               AGENT_BRAIN_OAUTH_RESOURCE (RFC 8707 resource URI).

    Python 3.10 note: ``enum.StrEnum`` was added in 3.11. This repo
    targets 3.10+, so we use ``class AuthMode(str, Enum)`` — the same
    effect: members are both enum values AND strings, satisfying
    ``isinstance(AuthMode.none, str)``.

    Design doc: docs/plans/2026-06-14-mcp-v4-oauth-design.md
      §"Auth-Mode Toggle and Deployment Shapes"
    """

    none = "none"
    basic = "basic"
    oauth = "oauth"


def _raw_auth_mode() -> str | None:
    """Return the raw lowercased AGENT_BRAIN_AUTH value, or None if unset.

    This is the primitive the startup gate reads to detect invalid values
    BEFORE constructing an AuthMode enum. Separating raw-read from
    enum-construction keeps the exit-code-2 path in one place
    (check_auth_startup_gate) and lets resolve_auth_mode() remain a
    clean typed accessor that callers use AFTER the gate has passed.

    Returns:
        The lowercased env value string, or None if AGENT_BRAIN_AUTH is
        not set (or empty).
    """
    raw = os.environ.get("AGENT_BRAIN_AUTH")
    if not raw:
        return None
    return raw.lower()


def resolve_auth_mode() -> AuthMode | None:
    """Resolve AGENT_BRAIN_AUTH to a typed AuthMode.

    Reads AGENT_BRAIN_AUTH from the environment, lowercases the value,
    and maps it to an AuthMode member.

    Resolution rules:
      - Unset / empty → AuthMode.none (the safe default)
      - "none" / "basic" / "oauth" (case-insensitive) → matching member
      - Any other value → None (caller should be the startup gate which
        will log a CRITICAL message and call sys.exit(2))

    This function is called AFTER check_auth_startup_gate() has already
    validated the value. Treat a None return as "unknown — gate rejected
    this value". Normal application code should never see None here
    because the gate runs at startup.

    Returns:
        The resolved AuthMode, or None if the env value is invalid.
    """
    raw = _raw_auth_mode()
    if raw is None:
        return AuthMode.none
    try:
        return AuthMode(raw)
    except ValueError:
        return None


def resolve_oauth_settings() -> tuple[str | None, str | None]:
    """Read OAuth env vars and return (resource, issuer), normalising empty→None.

    Pure read — no validation. The startup gate (check_auth_startup_gate)
    validates presence and URI format when AGENT_BRAIN_AUTH=oauth.

    Env vars consumed:
      - AGENT_BRAIN_OAUTH_RESOURCE: The canonical resource URI that
        identifies THIS MCP server (RFC 8707 ``resource`` parameter).
        Fed into PRM discovery metadata and used as the ``aud`` claim in
        all issued JWTs (design doc §"Canonical Resource URI Contract").
      - AGENT_BRAIN_OAUTH_ISSUER: The Authorization Server issuer URI
        (used in /.well-known/oauth-authorization-server metadata and
        as the ``iss`` claim in issued tokens). Optional — defaults to
        None if not set.

    Returns:
        (resource, issuer) — each is the env-var string value, or None
        if unset or set to an empty string.
    """
    resource_raw = os.environ.get("AGENT_BRAIN_OAUTH_RESOURCE") or None
    issuer_raw = os.environ.get("AGENT_BRAIN_OAUTH_ISSUER") or None
    # Normalise whitespace-only strings to None too
    resource = resource_raw.strip() if resource_raw else None
    issuer = issuer_raw.strip() if issuer_raw else None
    return (resource or None, issuer or None)


def check_auth_startup_gate() -> None:
    """Validate auth-mode configuration at MCP server boot time.

    This is the MCP-side mirror of agent_brain_server's
    _check_api_key_startup_gate (SECURITY-01 contract). It validates the
    AGENT_BRAIN_AUTH toggle and — in oauth mode — the OAuth resource URI,
    before the server begins accepting any connections.

    Gate logic:
      1. Read raw AGENT_BRAIN_AUTH (lowercased). Unset → treat as "none"
         (valid, return None silently).
      2. If raw value is NOT in {none, basic, oauth}: CRITICAL log +
         sys.exit(2).
      3. In oauth mode only: AGENT_BRAIN_OAUTH_RESOURCE must be set,
         non-empty, and a syntactically valid URI with a scheme. On
         failure: CRITICAL log + sys.exit(2).
      4. none/basic modes: AGENT_BRAIN_OAUTH_RESOURCE is NOT required.

    Design doc risk rationale: Risk 2 (aud-omission attack) — an absent
    or scheme-less resource URI cannot be used as the RFC 8707 aud
    binding, silently weakening the token audience check. The gate
    catches this at startup rather than per-request.

    Raises:
        SystemExit: With code 2 on any misconfiguration (invalid toggle
            value, or oauth mode with absent/empty/scheme-less resource).

    Returns:
        None on valid configuration (silent, no log output).
    """
    raw = _raw_auth_mode()
    if raw is None:
        # Unset → default "none" — always valid and silent.
        return

    if raw not in _VALID_AUTH_MODES:
        logger.critical(
            "AGENT_BRAIN_AUTH must be one of {none, basic, oauth}, got %r. "
            "Set AGENT_BRAIN_AUTH to a valid value or unset it to use the "
            "default (none).",
            raw,
        )
        sys.exit(2)

    if raw == "oauth":
        resource, _ = resolve_oauth_settings()
        if not resource:
            logger.critical(
                "AGENT_BRAIN_AUTH=oauth requires AGENT_BRAIN_OAUTH_RESOURCE "
                "to be set to a non-empty URI (e.g. https://mcp.example.com/mcp). "
                "AGENT_BRAIN_OAUTH_RESOURCE is missing or empty. "
                "Risk: without a resource URI the RFC 8707 aud binding cannot "
                "be enforced (aud-omission attack surface)."
            )
            sys.exit(2)

        # Validate URI has a scheme (and is not just a bare hostname).
        parsed = urllib.parse.urlparse(resource)
        if not parsed.scheme or not (parsed.netloc or parsed.path):
            logger.critical(
                "AGENT_BRAIN_OAUTH_RESOURCE must be an absolute URI with a "
                "scheme (e.g. https://mcp.example.com/mcp), got %r. "
                "A bare hostname or path-only string is not a valid resource "
                "URI per the design doc §Canonical Resource URI Contract.",
                resource,
            )
            sys.exit(2)

        # Reject URIs with fragments (RFC 8707 MUST NOT contain fragment).
        if parsed.fragment:
            logger.critical(
                "AGENT_BRAIN_OAUTH_RESOURCE must NOT contain a fragment (#), "
                "got %r. RFC 8707 §2 prohibits fragments in resource URIs.",
                resource,
            )
            sys.exit(2)


def get_auth_dependency() -> object:
    """Return the single auth selector for the current AuthMode.

    This is the mutual-exclusion seam that structurally enforces exactly
    one auth path. Phase 66 wires the selector + validation; the OAuth
    middleware it selects for the ``oauth`` branch arrives in Phase 67
    (RequireAuthMiddleware).

    Phase 66 wires the selector + validation; the oauth middleware it
    selects arrives in Phase 67 (RequireAuthMiddleware).

    Returns:
        A single dependency/marker object — one per mode, never two.
        Callers MUST NOT compose the return value with another auth layer.

    Raises:
        NotImplementedError: For the oauth branch (Phase-67 placeholder).
            Phase 67 replaces this placeholder with RequireAuthMiddleware.
    """
    mode = resolve_auth_mode()

    if mode is AuthMode.none:
        # No-op: no auth on the request path for "none" mode.
        return None

    if mode is AuthMode.basic:
        # SECURITY-01 shared-secret path: AGENT_BRAIN_API_KEY Bearer token.
        # The existing verify_bearer_token logic (Phase 66 does NOT change
        # request-path behaviour — this branch names it under the toggle
        # per OAUTH-09; enforcement is via the existing API-key middleware).
        return "basic-bearer"

    # oauth mode — Phase-67 placeholder.
    # Phase 67 replaces this with the RequireAuthMiddleware selector.
    raise NotImplementedError(
        "OAuth middleware selector is a Phase-67 placeholder. "
        "RequireAuthMiddleware arrives in Phase 67."
    )


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


def _resolve_api_key(state_dir: Path | None) -> str | None:
    """Resolve the X-API-Key the MCP server should send to the backend (Issue #179).

    Precedence (first non-empty wins):
      1. ``AGENT_BRAIN_MCP_API_KEY`` env (MCP-specific override)
      2. ``AGENT_BRAIN_API_KEY`` env (shared with the CLI)
      3. ``runtime.json::api_key`` for the resolved state dir
         (set by a running server)
      4. ``config.json::api_key`` for the resolved state dir
         (set by ``agent-brain init``, used when the server has not
         started yet)

    Returns ``None`` when no source provides a value. The server's
    ``verify_api_key`` dependency is a no-op in that case, so unauthed
    loopback workflows keep working.
    """
    env_key = os.environ.get("AGENT_BRAIN_MCP_API_KEY") or os.environ.get(
        "AGENT_BRAIN_API_KEY"
    )
    if env_key:
        return env_key

    sdir = _resolve_state_dir(state_dir)
    if sdir is None:
        return None

    for filename in ("runtime.json", "config.json"):
        candidate = sdir / filename
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        api_key = payload.get("api_key")
        if api_key:
            return str(api_key)

    return None


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
    api_key: str | None = None,
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
    if api_key:
        client.headers["X-API-Key"] = api_key
    return client


def _open_http_client(
    backend_url: str, timeout: float, api_key: str | None = None
) -> httpx.Client:
    headers = {"X-API-Key": api_key} if api_key else None
    return httpx.Client(base_url=backend_url, timeout=timeout, headers=headers)


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

    Resolves the X-API-Key once and injects it into whichever client wins
    (Issue #179) so MCP can talk to an authed backend just like the CLI.
    """
    chosen = (backend or os.environ.get("AGENT_BRAIN_MCP_BACKEND") or "auto").lower()
    api_key = _resolve_api_key(state_dir)

    if chosen == "http":
        url = _resolve_http_url(backend_url, state_dir)
        return ("http", _open_http_client(url, timeout, api_key))

    if chosen == "uds":
        return ("uds", _open_uds_client(socket_path, state_dir, timeout, api_key))

    # auto
    try:
        return ("uds", _open_uds_client(socket_path, state_dir, timeout, api_key))
    except (AgentBrainUdsError, OSError, FileNotFoundError):
        url = _resolve_http_url(backend_url, state_dir)
        return ("http", _open_http_client(url, timeout, api_key))
