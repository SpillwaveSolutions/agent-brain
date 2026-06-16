"""MCP stdio server — wires the registries into the low-level Server.

Capabilities advertised:
  tools.listChanged     = False
  resources.subscribe   = True   (Phase 52 — flipped from False)
  resources.listChanged = False
  prompts.listChanged   = False

Phase 52 wires the ``resources/subscribe`` + ``resources/unsubscribe``
handlers and a per-session :class:`SubscriptionManager` instance.

Plan 04 refactor — :func:`build_server` now returns a tuple
``(server, manager)`` so :func:`run_stdio` can call
``manager.cleanup_all()`` on session disconnect explicitly, without
poking the ``server._subscription_manager`` private attr that Plan 02
used as a short-term workaround. The private attr is preserved for
backwards compatibility (Plan 02 pinned it via
``test_build_server_attaches_subscription_manager``) but Plan 04+
consumers should unpack the tuple.

No sampling / elicitation / logging / completions in v2.
"""

from __future__ import annotations

import asyncio
import json
import logging
import warnings
from collections.abc import Iterable
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any

import anyio
import httpx
import mcp.server.stdio
import mcp.types as types
from mcp import McpError
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.models import InitializationOptions
from mcp.server.session import InitializationState, ServerSession
from mcp.shared.session import RequestResponder
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS
from mcp.types import ErrorData
from pydantic import AnyUrl, ValidationError

from . import __version__
from .client import ApiClient
from .config import AuthMode, resolve_auth_mode
from .errors import INVALID_PARAMS, raise_backend_unavailable
from .http import run_http
from .oauth.scopes import InsufficientScopeError, require_scope
from .prompts import PROMPT_REGISTRY
from .resources import (
    PARAMETERIZED_HANDLERS,
    RESOURCE_REGISTRY,
    TEMPLATE_REGISTRY,
    parse_uri,
)
from .resources.parameterized import PARAMETERIZED_SCHEMES
from .schemas import json_schema
from .subscriptions import (
    SubscribableUriRejected,
    SubscriptionManager,
    resolve_policy,
)
from .tools import TOOL_REGISTRY, TOOL_SCOPE_REQUIREMENTS

if TYPE_CHECKING:
    # Phase 54 Plan 04: type-only import. ``ProgressNotifier`` is the
    # async closure shape that progress-emitting tool handlers consume;
    # imported here purely for the forward-reference in
    # :func:`_build_progress_notifier`'s return type annotation.
    from .tools.wait import ProgressNotifier  # noqa: F401

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-tool scope guard — defense-in-depth for in-process / stdio callers
# (Phase 68 Plan 02, Task 1).  The HTTP /mcp path is guarded by the
# ScopeEnforcementMiddleware pre-dispatch guard in http.py (Task 2), which
# fires BEFORE the session manager runs.  This helper covers callers that
# never traverse that middleware (in-process unit tests, stdio transport).
# ---------------------------------------------------------------------------


def _enforce_scope(server: Server, required: str) -> None:
    """Per-tool scope guard (design Risk 4), defense-in-depth.

    No-op unless AGENT_BRAIN_AUTH=oauth. Reads the authenticated token's
    scopes off the Starlette Request carried in the MCP request context
    (set by Phase 67 AuthenticationMiddleware) and delegates to
    oauth.scopes.require_scope. Raises InsufficientScopeError on
    insufficient scope. For the HTTP /mcp path the pre-dispatch
    ScopeEnforcementMiddleware (http.py) already emits the 403 BEFORE
    this runs; this guard covers in-process / stdio callers that never
    traverse that middleware.

    Args:
        server: The low-level MCP Server instance. Used to reach the
            current request context via ``server.request_context``.
        required: The scope string the current operation requires
            (one of the 4 locked scopes from TOOL_SCOPE_REQUIREMENTS or
            the resource/subscription constants).

    Raises:
        InsufficientScopeError: When the token lacks the required scope
            (including the empty-scopes case — deny by default).
    """
    if resolve_auth_mode() != AuthMode.oauth:
        return  # none/basic: no token scopes — dispatch unchanged
    try:
        req = server.request_context.request
    except LookupError:
        req = None
    user = getattr(req, "user", None)
    token_scopes = list(getattr(user, "scopes", []) or [])
    require_scope(required, token_scopes)


SERVER_NAME = "agent-brain"
# Lowest server /health/ ``version`` that this MCP build is compatible with.
#
# Phase 51 Plan 04 bumps this floor from "10.0.7" → "10.2.0". The new
# floor pins the v2 server-side endpoints introduced in Phase 50 — namely
# ``GET /query/chunk/{id}`` and ``GET /graph/entity/{type}/{id}`` — which
# back the ``chunk://`` and ``graph-entity://`` URI schemes. Without
# them, the parameterized URI handlers would fail with 404 against a
# v1-era server, presenting a confusing error rather than a clear
# "upgrade your server" message at startup.
#
# Release-train coupling: ``agent-brain-server 10.2.0`` MUST ship to
# PyPI BEFORE ``agent-brain-mcp 10.2.0`` is published. Otherwise
# operators upgrading their MCP package against an older server will
# see this floor check refuse to start. Documented in the v2 design
# doc and in CHANGELOG [10.2.0].
MIN_BACKEND_VERSION = "10.2.0"


def _parse_version(v: str) -> tuple[int, ...]:
    """Coerce 'X.Y.Z' to a comparable tuple. Stops at the first non-numeric."""
    parts: list[int] = []
    for chunk in v.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def check_backend_version(
    actual_version: str, *, minimum: str = MIN_BACKEND_VERSION
) -> None:
    """Raise ``McpError`` if the backend reports a version below the floor.

    Plan §12.3 #14 — refuse to start if /health/ reports a version below
    the floor pinned in pyproject.toml.
    """
    if _parse_version(actual_version) < _parse_version(minimum):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=(
                    f"Backend version {actual_version} is below the MCP "
                    f"client minimum {minimum}. Upgrade agent-brain-server."
                ),
                data={"backendVersion": actual_version, "minimum": minimum},
            )
        )


def _normalize_uri(uri: AnyUrl | str) -> str:
    """Apply the Phase 51 trailing-slash strip used by ``read_resource``.

    Strips at most a single trailing ``/`` so ``job://abc/`` collapses
    to ``job://abc`` without mangling empty-netloc URIs like ``job://``
    (which we want to surface verbatim for the malformed-URI error path).
    Mirrors the inline normalization at ``read_resource`` above so the
    subscribe handler keys against the same canonical URI string as
    ``RESOURCE_REGISTRY`` / ``PARAMETERIZED_SCHEMES``.
    """
    raw = str(uri)
    return raw[:-1] if raw.endswith("/") and not raw.endswith("//") else raw


def _is_known_uri(uri_str: str) -> bool:
    """Return True if ``uri_str`` corresponds to a known resource.

    Two ways a URI can be "known":

    1. **Exact string match** in ``RESOURCE_REGISTRY`` — the static
       ``corpus://*`` URIs (5 entries).
    2. **Parameterized scheme** in ``PARAMETERIZED_SCHEMES`` — the four
       templated schemes (``chunk``, ``graph-entity``, ``job``,
       ``file``). For subscription purposes we only check that the URI's
       scheme is recognized; per-id validation (does ``job://abc`` exist
       in the backend?) is deferred to the polling fetcher in Plan 03.

    The "scheme is recognized" check is intentionally NOT a full
    ``parse_uri`` invocation. ``parse_uri`` raises for malformed
    parameterized URIs (e.g., ``job://`` with no id), but for the
    subscribe handler we want the *not_subscribable* / *unknown_uri*
    branches to win over *missing_job_id*. A malformed parameterized
    URI is still "known scheme" → falls through to the policy lookup
    → ``not_subscribable`` if no policy matches the empty id.
    """
    if uri_str in RESOURCE_REGISTRY:
        return True
    # Cheap scheme extraction — same shape as resolve_policy in
    # :mod:`subscriptions.policies` but here we check membership in the
    # broader PARAMETERIZED_SCHEMES set (any of the 4 templated schemes
    # is considered "known", even if no subscription policy is
    # registered for it).
    sep = uri_str.find("://")
    if sep == -1:
        return False
    scheme = uri_str[:sep]
    return scheme in PARAMETERIZED_SCHEMES


def build_server(
    httpx_client: httpx.Client,
    *,
    backend_transport: str = "http",
    listen_transport: str = "stdio",
    transport: str | None = None,
) -> tuple[Server, SubscriptionManager]:
    """Construct and configure the low-level MCP ``Server`` instance.

    Phase 52 owns subscription wiring:

    * Constructs a :class:`SubscriptionManager` instance per server.
    * Registers ``@server.subscribe_resource()`` / ``@server.unsubscribe_resource()``
      handlers that gate URIs against the subscribable allowlist defined
      in :mod:`agent_brain_mcp.subscriptions.policies`.
    * Patches ``server.get_capabilities`` so the SDK's hardcoded
      ``subscribe=False`` is flipped to ``True`` whenever Phase 52's
      handler is present. The MCP SDK (mcp 1.12.x, spec 2025-03-26)
      hardcodes the capability at ``mcp/server/lowlevel/server.py:211``
      with no opt-in flag on :class:`NotificationOptions`; a wrapper is
      the surgical fix until upstream exposes a knob.

    Args:
        httpx_client: Pre-configured backend httpx client (the
            **backend** axis — how the MCP server talks to
            ``agent-brain-serve``).
        backend_transport: Label for the backend httpx transport
            (``"http"`` / ``"uds"`` / ``"auto"`` resolved). Surfaced as
            ``server._agent_brain_backend_transport`` for client
            debugging via the MCP ``_meta`` channel (Phase 55 will wire
            the over-the-wire surfacing — for now the attribute is the
            in-process contract).
        listen_transport: Label for the listen-side transport that the
            MCP client uses to reach this server (``"stdio"`` /
            ``"http"``). The two axes are orthogonal (Phase 53 D-01).
            Surfaced as ``server._agent_brain_listen_transport``.
        transport: **Deprecated** Phase 52 kwarg, retained as a
            backwards-compatible alias for ``backend_transport``. Passing
            ``transport=`` emits :class:`DeprecationWarning`; the value
            is routed to ``backend_transport`` so downstream behavior is
            unchanged. Slated for removal in Phase 55.

    Returns:
        ``(server, subscription_manager)`` — Plan 04 tuple shape. The
        :class:`SubscriptionManager` is also still attached as
        ``server._subscription_manager`` for backwards compatibility
        with Plan 02's pin (``test_build_server_attaches_subscription_manager``);
        new callers should prefer unpacking the tuple over poking the
        private attr.
    """
    # Phase 53 Plan 01: backwards-compat alias. Phase 52 callers passed
    # ``transport=`` to label the BACKEND httpx transport on the Server
    # instance; Phase 53 splits this into two orthogonal axes
    # (backend_transport + listen_transport), so the old kwarg becomes
    # ambiguous. Route legacy callers to backend_transport with a
    # DeprecationWarning so the test suite can pin the migration path
    # without a coordinated rename across all build_server() call sites.
    if transport is not None:
        warnings.warn(
            "build_server(transport=) is deprecated; use backend_transport=",
            DeprecationWarning,
            stacklevel=2,
        )
        backend_transport = transport

    server: Server = Server(SERVER_NAME, version=__version__)

    # Phase 52 (Plan 02 → Plan 04): one SubscriptionManager per server.
    # Plan 04 returns it as the second tuple element so ``run_stdio``
    # can wire ``cleanup_all()`` into its ``finally`` block. The private
    # attribute is retained because Plan 02 pinned it via
    # ``test_build_server_attaches_subscription_manager``.
    subscription_manager = SubscriptionManager()
    server._subscription_manager = subscription_manager  # type: ignore[attr-defined]

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        out: list[types.Tool] = []
        for spec in TOOL_REGISTRY.values():
            out.append(
                types.Tool(
                    name=spec.name,
                    description=spec.description,
                    inputSchema=json_schema(spec.input_model),
                    outputSchema=json_schema(spec.output_model),
                    annotations=(
                        types.ToolAnnotations(**spec.annotations)
                        if spec.annotations
                        else None
                    ),
                )
            )
        return out

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> tuple[Iterable[types.ContentBlock], dict[str, Any]]:
        spec = TOOL_REGISTRY.get(name)
        if spec is None:
            raise McpError(
                ErrorData(code=INVALID_PARAMS, message=f"Unknown tool: {name}")
            )
        # Phase 68 Plan 02 (Task 1): defense-in-depth scope enforcement.
        # The pre-dispatch ScopeEnforcementMiddleware in http.py already
        # emits a real HTTP 403 BEFORE this runs for /mcp HTTP callers.
        # This guard covers in-process / stdio callers. Mode-gated to oauth.
        _enforce_scope(server, TOOL_SCOPE_REQUIREMENTS[name])
        try:
            args = spec.input_model.model_validate(arguments)
        except ValidationError as e:
            raise McpError(
                ErrorData(
                    code=INVALID_PARAMS,
                    message=f"Invalid arguments for {name}: {e.errors()[0]['msg']}",
                    data={"validation_errors": e.errors()},
                )
            ) from e

        api = ApiClient(httpx_client)
        if spec.emits_progress:
            # Phase 54 Plan 04 — async dispatch for progress-emitting
            # tools. The handler is an ``async def`` with signature
            # ``(api, args, *, notify) -> output``; ``notify`` is a
            # closure that wraps the SDK's
            # ``ServerSession.send_progress_notification``, baking in
            # the ``progressToken`` from the request meta and the
            # ``related_request_id``. If the client did NOT attach a
            # ``progressToken`` (progress notifications are opt-in per
            # MCP spec), the closure becomes a no-op so the handler's
            # control flow stays uniform.
            notify = _build_progress_notifier(server)
            result = await spec.handler(api, args, notify=notify)
        else:
            # Run the sync handler in a thread so the asyncio event loop
            # stays responsive (plan §6.4 / §12.3 #12). A blocking httpx
            # call inline in an async def would freeze stdio and defeat
            # MCP ``notifications/cancelled``.
            result = await asyncio.to_thread(spec.handler, api, args)
        structured = result.model_dump(mode="json", exclude_none=False)
        text_summary = _summarize(name, structured)
        return ([types.TextContent(type="text", text=text_summary)], structured)

    @server.list_resources()
    async def list_resources() -> list[types.Resource]:
        return [
            types.Resource(
                uri=AnyUrl(spec.uri),
                name=spec.name,
                description=spec.description,
                mimeType=spec.mime_type,
            )
            for spec in RESOURCE_REGISTRY.values()
        ]

    @server.list_resource_templates()
    async def list_resource_templates() -> list[types.ResourceTemplate]:
        # Phase 51 (URI-05): publish the 4 RFC 6570 templates for the
        # parameterized URI schemes (chunk, graph-entity, job, file).
        # Static corpus://* URIs stay in list_resources(); they are NOT
        # retrofitted into templates because they are genuinely static
        # (5 fixed URIs, no parameters) — CONTEXT decision A.
        #
        # The MCP SDK auto-detects ``resourceTemplates`` capability from
        # handler presence in the spec revision pinned in pyproject.toml
        # (mcp = ^1.12.0 → 2026-03-26 spec). No explicit capability flag
        # bump is required in get_capabilities(); resources.subscribe
        # stays False until Phase 52.
        return list(TEMPLATE_REGISTRY)

    @server.read_resource()
    async def read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
        # Phase 68 Plan 02 (Task 1): defense-in-depth scope enforcement.
        # All resource reads require agent-brain:read (design Scope Table).
        # Mode-gated to oauth; no-op in none/basic.
        _enforce_scope(server, "agent-brain:read")
        # Strip at most a single trailing '/' so 'job://abc/' → 'job://abc'
        # without collapsing 'job://' (empty netloc) into 'job:'. The v1
        # ``.rstrip('/')`` form mangled empty-netloc URIs that we now
        # want to surface verbatim in malformed-URI error data (51-01).
        raw = str(uri)
        uri_str = raw[:-1] if raw.endswith("/") and not raw.endswith("//") else raw

        # Phase 51 (URI-03): parameterized schemes dispatch first.
        # parse_uri() returns None for any scheme outside the four-
        # scheme allow-list (including corpus://), so we fall through
        # to the static RESOURCE_REGISTRY below. Malformed parameterized
        # URIs (recognized scheme, missing required segment) raise
        # McpError(INVALID_PARAMS) inside parse_uri — let it propagate.
        parsed = parse_uri(uri_str)
        if parsed is not None:
            handler = PARAMETERIZED_HANDLERS.get(parsed.scheme)
            if handler is None:
                # parse_uri only returns ParsedURI for registered
                # schemes, so this is defensive against a future
                # registry mismatch.
                raise McpError(
                    ErrorData(
                        code=INVALID_PARAMS,
                        message=f"Unknown resource: {uri}",
                    )
                )
            api = ApiClient(httpx_client)
            # Parameterized handlers are async; they do their own
            # asyncio.to_thread() for the sync httpx call inside the
            # handler body, so we await directly here.
            #
            # Handler return contract (Plans 51-01/02/03):
            #   - str → wrap as ``application/json`` (the JSON-backed
            #     schemes: ``job``, ``chunk``, ``graph-entity``).
            #   - ReadResourceContents → use verbatim (file://, which
            #     needs a per-file mime_type + may carry bytes for
            #     binary blob payloads).
            # This dual-return shape is the minimal-surface way to let
            # file:// pick its own MIME without forcing the JSON
            # schemes to construct a ReadResourceContents themselves.
            content = await handler(api, parsed)
            if isinstance(content, ReadResourceContents):
                return [content]
            return [
                ReadResourceContents(
                    content=content,
                    mime_type="application/json",
                )
            ]

        # Static corpus:// resource path (unchanged from v1).
        spec = RESOURCE_REGISTRY.get(uri_str) or RESOURCE_REGISTRY.get(str(uri))
        if spec is None:
            raise McpError(
                ErrorData(code=INVALID_PARAMS, message=f"Unknown resource: {uri}")
            )
        api = ApiClient(httpx_client)
        # Same to_thread treatment as call_tool — resource handlers also
        # issue sync httpx calls.
        data = await asyncio.to_thread(spec.handler, api)
        return [
            ReadResourceContents(
                content=json.dumps(data, indent=2, default=str),
                mime_type=spec.mime_type,
            )
        ]

    @server.list_prompts()
    async def list_prompts() -> list[types.Prompt]:
        return [
            types.Prompt(
                name=spec.name,
                description=spec.description,
                arguments=[
                    types.PromptArgument(
                        name=a.name,
                        description=a.description,
                        required=a.required,
                    )
                    for a in spec.arguments
                ],
            )
            for spec in PROMPT_REGISTRY.values()
        ]

    @server.get_prompt()
    async def get_prompt(
        name: str, arguments: dict[str, str] | None
    ) -> types.GetPromptResult:
        # Phase 68 Plan 02 (Task 1): defense-in-depth scope enforcement.
        # All registered prompts require agent-brain:read (CONTEXT locked).
        # Mode-gated to oauth; no-op in none/basic.
        _enforce_scope(server, "agent-brain:read")
        spec = PROMPT_REGISTRY.get(name)
        if spec is None:
            raise McpError(
                ErrorData(code=INVALID_PARAMS, message=f"Unknown prompt: {name}")
            )
        args_dict: dict[str, Any] = dict(arguments or {})
        try:
            spec.validate(args_dict)
        except ValueError as e:
            raise McpError(ErrorData(code=INVALID_PARAMS, message=str(e))) from e

        messages_raw = spec.render(args_dict)
        messages = [
            types.PromptMessage(
                role=m["role"],
                content=types.TextContent(type="text", text=m["content"]["text"]),
            )
            for m in messages_raw
        ]
        return types.GetPromptResult(description=spec.description, messages=messages)

    @server.subscribe_resource()
    async def handle_subscribe(uri: AnyUrl) -> None:
        """Validate + dispatch ``resources/subscribe`` to the polling manager.

        Pipeline (Plan 02 acceptance criteria):

        1. Normalize URI (strip single trailing slash — Phase 51 shape).
        2. Reject if URI is neither a known static ``corpus://*`` entry
           nor a recognized parameterized scheme:
           ``SubscribableUriRejected(reason="unknown_uri")``.
        3. Reject if no policy matches the URI (exact then scheme-prefix
           lookup): ``SubscribableUriRejected(reason="not_subscribable")``.
        4. Get the owning ``ServerSession`` via
           ``server.request_context.session``.
        5. Reject if this ``(session, uri)`` pair already has an active
           subscription: ``SubscribableUriRejected(reason="duplicate_subscribe")``.
           This pre-checks ``manager.is_subscribed`` so the bare
           :class:`RuntimeError` from ``start_polling`` never surfaces
           as a generic internal error on the MCP wire.
        6. Build the fetcher closure from
           ``policy.build_fetcher(api_client, uri)`` and the on-change
           closure that calls
           ``session.send_resource_updated(AnyUrl(uri))``.
        7. Hand off to ``manager.start_polling(...)``.

        Subscribable allowlist (Phase 52 CONTEXT decision A):
            ``job://<id>``, ``corpus://status``, ``corpus://folders``.
        Anything else fails at step 3, even if it's a valid
        ``read_resource`` target (``chunk://``, ``graph-entity://``,
        ``file://``, ``corpus://config``, etc.).
        """
        # Phase 68 Plan 02 (Task 1): defense-in-depth scope enforcement.
        # Subscription requests require agent-brain:subscribe.
        # Mode-gated to oauth; no-op in none/basic.
        _enforce_scope(server, "agent-brain:subscribe")
        uri_str = _normalize_uri(uri)

        # (2) Is the URI even known to this server?
        if not _is_known_uri(uri_str):
            raise SubscribableUriRejected(uri_str, reason="unknown_uri")

        # (3) Is a subscription policy registered? Plan 03 populates the
        # registry; under Plan 02 alone the registry is empty so every
        # subscribe attempt returns ``not_subscribable``. Tests use
        # ``monkeypatch.setitem`` to install a stub policy.
        policy = resolve_policy(uri_str)
        if policy is None:
            raise SubscribableUriRejected(uri_str, reason="not_subscribable")

        # (4) Capture the owning session. ``request_context`` raises
        # ``LookupError`` if we're somehow invoked outside a request —
        # the SDK guarantees we are, so let it propagate (it would be a
        # framework-level bug).
        session = server.request_context.session

        # (5) Duplicate-subscribe check. CONTEXT decision A picks strict
        # rejection so the polling-task lifecycle stays deterministic.
        if subscription_manager.is_subscribed(session, uri_str):
            raise SubscribableUriRejected(uri_str, reason="duplicate_subscribe")

        # (6) Build the on-change closure that fires
        # ``notifications/resources/updated`` on the OWNING session only
        # (Phase 52 CONTEXT decision A — per-session, not per-URI).
        api_client = ApiClient(httpx_client)
        fetcher = policy.build_fetcher(api_client, uri_str)
        sid_slug = f"{id(session):x}"[-8:]

        async def on_change(changed_uri: str, _payload: dict[str, Any]) -> None:
            logger.info(
                "send_resource_updated session=%s uri=%s", sid_slug, changed_uri
            )
            await session.send_resource_updated(AnyUrl(changed_uri))

        # (7) Hand off to the manager. ``start_polling`` registers the
        # task synchronously so a follow-up ``unsubscribe`` on the next
        # line cancels it cleanly (Plan 01 race-safety contract).
        subscription_manager.start_polling(
            session=session,
            uri=uri_str,
            interval_s=policy.interval_s,
            fetcher=fetcher,
            on_change=on_change,
            drop_keys=policy.drop_keys,
        )

    @server.unsubscribe_resource()
    async def handle_unsubscribe(uri: AnyUrl) -> None:
        """Tear down the polling task for ``resources/unsubscribe``.

        Per the MCP spec, ``resources/unsubscribe`` for a URI the client
        never subscribed to is a no-op (the SDK still acks with
        ``EmptyResult``). We follow that semantic — ``manager.unsubscribe``
        returns a bool flagging "was a task actually cancelled?" but we
        intentionally ignore the return value here. The acknowledgement
        is sent regardless.

        Normalization mirrors the subscribe path so a client that uses
        a trailing-slash variant in unsubscribe still matches whatever
        it subscribed to.
        """
        uri_str = _normalize_uri(uri)
        # Tolerated no-op if no subscription existed — MCP spec lets
        # clients send unsubscribe for URIs they never subscribed to.
        subscription_manager.unsubscribe(server.request_context.session, uri_str)

    # Phase 52 capability flip. The MCP SDK 1.12.x hardcodes
    # ``subscribe=False`` at ``mcp/server/lowlevel/server.py:211``,
    # ignoring both ``NotificationOptions`` and ``_subscribe_resource_handler``
    # presence (verified at Plan 02 land time). We wrap ``get_capabilities``
    # so the cap is flipped to ``True`` whenever Phase 52's handler is
    # registered, which is always-true after this build_server() runs.
    #
    # Why a wrapper and not a monkeypatched return: the SDK's
    # ``create_initialization_options`` calls ``self.get_capabilities``;
    # patching the bound method is the minimal-touch path. Plan 04 keeps
    # this — there's no upstream SDK fix yet (see issue tracker note in
    # the v2 design doc).
    _original_get_capabilities = server.get_capabilities

    def _patched_get_capabilities(
        notification_options: NotificationOptions,
        experimental_capabilities: dict[str, dict[str, Any]],
    ) -> types.ServerCapabilities:
        caps = _original_get_capabilities(
            notification_options, experimental_capabilities
        )
        if caps.resources is not None:
            # Pydantic ServerCapabilities is mutable; flipping the field
            # in place is the simplest path. ``resources.subscribe`` is
            # the only knob Phase 52 cares about — ``listChanged`` stays
            # whatever ``notification_options.resources_changed`` says.
            caps.resources.subscribe = True
        return caps

    server.get_capabilities = _patched_get_capabilities  # type: ignore[method-assign]

    # Phase 53 Plan 01: surface BOTH axis labels for client debugging.
    # ``_agent_brain_backend_transport`` labels how this MCP server
    # talks to ``agent-brain-serve`` (backend httpx); the new
    # ``_agent_brain_listen_transport`` labels how the MCP client
    # reaches this server (stdio vs Streamable HTTP). The legacy
    # ``_agent_brain_transport`` attribute is retained as a backwards-
    # compat shim mirroring ``backend_transport`` — slated for removal
    # in Phase 55.
    server._agent_brain_backend_transport = backend_transport  # type: ignore[attr-defined]
    server._agent_brain_listen_transport = listen_transport  # type: ignore[attr-defined]
    server._agent_brain_transport = backend_transport  # type: ignore[attr-defined]

    # Phase 53 Plan 03: surface BOTH axis labels over the wire via the
    # MCP ``initialize`` response. The MCP SDK 1.12.x hardcodes the
    # ``Implementation`` construction inside
    # ``mcp/server/session.py:_received_request`` (lines 177-182) with
    # no extension hook — but ``Implementation.model_config =
    # ConfigDict(extra="allow")`` (mcp/types.py:274), so passing
    # ``_meta=<dict>`` as a constructor kwarg stores it as an extra
    # field that the wire-format ``model_dump(by_alias=True)`` includes
    # as ``"_meta": {...}``.
    #
    # We wire this by wrapping ``server.run``. The wrapper substitutes
    # a tiny ``_MetaInjectingServerSession`` subclass (defined below)
    # in place of the SDK's ``ServerSession``. The substitute mirrors
    # the SDK's Initialize handler verbatim with one change: the
    # ``Implementation(...)`` call carries ``_meta=server._agent_brain_meta``.
    # Both stdio (``run_stdio``) and HTTP (``run_http`` via the SDK's
    # ``StreamableHTTPSessionManager`` → ``Server.run``) inherit the
    # injection because both paths land in ``Server.run`` eventually.
    server._agent_brain_meta = {  # type: ignore[attr-defined]
        "agentBrainBackendTransport": backend_transport,
        "agentBrainListenTransport": listen_transport,
    }
    _install_meta_injecting_session(server)
    return server, subscription_manager


def _summarize(tool_name: str, structured: dict[str, Any]) -> str:
    """Produce the human-readable ``text`` block for a tool result."""
    if tool_name == "search_documents":
        n = structured.get("total_results", len(structured.get("results", [])))
        return f"search_documents → {n} result(s) for mode={structured.get('mode')}"
    if tool_name == "query_count":
        return (
            f"query_count → {structured.get('total_documents')} docs, "
            f"{structured.get('total_chunks')} chunks"
        )
    if tool_name == "index_folder":
        return (
            f"index_folder → job {structured.get('job_id')} "
            f"({structured.get('status')})"
        )
    if tool_name == "get_job":
        return (
            f"get_job → {structured.get('job_id')}: "
            f"{structured.get('status')} ({structured.get('progress_percent')}%)"
        )
    if tool_name == "list_jobs":
        return f"list_jobs → {len(structured.get('jobs', []))} job(s)"
    if tool_name == "cancel_job":
        return (
            f"cancel_job → {structured.get('job_id')}: "
            f"cancelled={structured.get('cancelled')}"
        )
    if tool_name == "server_health":
        return (
            f"server_health → {structured.get('status')} "
            f"(v{structured.get('version')})"
        )
    # ---------------------------------------------------------------------
    # Phase 54 Plan 02/03 — 8 Phase 54 tool summaries (4 read-only from
    # Plan 02 + 4 mutating from Plan 03). Branch order is alphabetical
    # (add_documents → cache_status → clear_cache → explain_result →
    # inject_documents → list_file_types → list_folders → remove_folder)
    # so Plan 04's wait_for_job slots in cleanly.
    # ---------------------------------------------------------------------
    if tool_name == "add_documents":
        return (
            f"add_documents → job {structured.get('job_id')} "
            f"({structured.get('status')})"
        )
    if tool_name == "cache_status":
        return (
            f"cache_status → {structured.get('hit_rate')}% hit rate "
            f"({structured.get('size_bytes')} bytes)"
        )
    if tool_name == "clear_cache":
        return (
            f"clear_cache → cache cleared "
            f"({structured.get('count')} entries, "
            f"{structured.get('size_bytes')} bytes)"
        )
    if tool_name == "explain_result":
        reason = str(structured.get("reason", ""))
        reason_fragment = reason[:80]
        return f"explain_result → {structured.get('chunk_id')}: {reason_fragment}"
    if tool_name == "inject_documents":
        job_id = str(structured.get("job_id", ""))
        if job_id == "dry_run":
            message = str(structured.get("message", "validation complete"))
            return f"inject_documents → dry_run: {message[:80]}"
        return f"inject_documents → job {job_id} ({structured.get('status')})"
    if tool_name == "list_file_types":
        return f"list_file_types → {structured.get('preset_count')} presets"
    if tool_name == "list_folders":
        folders = structured.get("folders") or []
        n = structured.get("total", len(folders))
        return f"list_folders → {n} folder(s) indexed"
    if tool_name == "remove_folder":
        return (
            f"remove_folder → {structured.get('folder_path')}: "
            f"{structured.get('chunks_deleted')} chunks removed"
        )
    if tool_name == "wait_for_job":
        # Phase 54 Plan 04: ``wait_for_job → <job_id>: <status>
        # (<progress>%) after <elapsed>s`` per CONTEXT specifics §6.
        # ``progress_percent`` is 0-100 from the server's job record;
        # ``elapsed_seconds`` is the wait duration.
        pct = structured.get("progress_percent")
        pct_str = f"{pct}%" if pct is not None else "0%"
        elapsed = structured.get("elapsed_seconds", 0.0) or 0.0
        return (
            f"wait_for_job → {structured.get('job_id')}: "
            f"{structured.get('status')} ({pct_str}) after {elapsed:.1f}s"
        )
    return f"{tool_name} → ok"


def _build_progress_notifier(
    server: Server,
) -> ProgressNotifier:
    """Build the ``notify`` closure injected into progress-emitting tools.

    Captures the current ``request_context`` once at handler-invocation
    time and returns a closure that emits one ``notifications/progress``
    per call. The closure handles three runtime conditions:

    1. **No progressToken on the request meta** — the MCP spec makes
       progress notifications opt-in; the client signals participation
       by attaching ``_meta.progressToken`` to the request. Without
       a token there is no addressable recipient. The closure
       silently no-ops in this case — the handler's control flow
       (poll → notify → check terminal) stays identical.
    2. **Token present** — emit ``send_progress_notification(token,
       progress, total, message, related_request_id)``. The
       ``related_request_id`` is the JSON-RPC id of the ``tools/call``
       request that triggered the wait, captured from
       ``request_context.request_id``. The MCP SDK requires it on
       progress notifications so the client can route the
       notification to the originating call.
    3. **Token type** — MCP spec allows ``str`` or ``int``. The SDK's
       ``ProgressNotificationParams.progressToken`` accepts both
       (``ProgressToken = str | int``); we pass through verbatim.

    Returns:
        An async callable ``(progress: float, total: float,
        message: str | None) -> None``. Re-entrant; safe to invoke
        multiple times per handler call.
    """
    # Lookup the request context ONCE at notifier-construction. The
    # context is a ContextVar; reading it inside the closure would also
    # work but would re-read on every notification — pointless overhead
    # since the request is the same for the handler's entire lifetime.
    try:
        ctx = server.request_context
    except LookupError:
        # Direct in-process callers (e.g., unit tests calling
        # call_tool without a request context) get a no-op notifier.
        # Production paths always have a context — the SDK guarantees
        # it before dispatching a tools/call.
        async def _noop(_progress: float, _total: float, _message: str | None) -> None:
            return None

        return _noop

    progress_token = ctx.meta.progressToken if ctx.meta is not None else None
    # ``request_id`` is ``RequestId = int | str`` in the MCP SDK but
    # ``send_progress_notification(related_request_id=...)`` is typed
    # narrowly as ``str | None``. Coerce defensively — at runtime the
    # SDK is happy with either form.
    raw_rid = ctx.request_id
    related_request_id: str | None = str(raw_rid) if raw_rid is not None else None
    session = ctx.session

    if progress_token is None:
        # Client did not opt into progress. No-op closure keeps the
        # handler's poll/notify/check loop uniform.
        async def _noop_no_token(
            _progress: float, _total: float, _message: str | None
        ) -> None:
            return None

        return _noop_no_token

    async def _emit(progress: float, total: float, message: str | None) -> None:
        await session.send_progress_notification(
            progress_token=progress_token,
            progress=progress,
            total=total,
            message=message,
            related_request_id=related_request_id,
        )

    return _emit


class _MetaInjectingServerSession(ServerSession):
    """Phase 53 Plan 03: ServerSession variant that injects ``_meta`` on initialize.

    The bare :class:`mcp.server.session.ServerSession` hard-codes the
    :class:`mcp.types.Implementation` construction inside
    ``_received_request`` (lines 177-182 of mcp/server/session.py in
    mcp 1.12.x), with no extension hook for adding ``_meta``. This
    subclass overrides ``_received_request`` only for the
    ``InitializeRequest`` case — every other case defers to the SDK
    parent class verbatim — and constructs
    :class:`mcp.types.Implementation` with the ``_meta`` kwarg drawn
    from the bound ``server._agent_brain_meta`` dict.

    The ``Implementation`` model has ``model_config =
    ConfigDict(extra="allow")`` (mcp/types.py:274), so passing the
    extra ``_meta`` kwarg is accepted and round-trips through the
    wire-format JSON-RPC response.

    SDK version pin: the duplicated handler logic mirrors
    ``mcp/server/session.py`` lines 165-187 in mcp 1.12.x. If the SDK
    surface evolves (e.g., new InitializeResult fields), this subclass
    needs to mirror those changes. The duplication is the price of the
    SDK's missing extension hook; Phase 55 will revisit if upstream
    publishes a cleaner injection point.
    """

    _agent_brain_meta: dict[str, Any] | None = None

    async def _received_request(
        self, responder: RequestResponder[types.ClientRequest, types.ServerResult]
    ) -> None:
        match responder.request.root:
            case types.InitializeRequest(params=params):
                requested_version = params.protocolVersion
                self._initialization_state = InitializationState.Initializing
                self._client_params = params
                with responder:
                    # Implementation accepts extras (extra="allow"); pass
                    # _meta as a kwarg so it round-trips on the wire.
                    impl_kwargs: dict[str, Any] = {
                        "name": self._init_options.server_name,
                        "version": self._init_options.server_version,
                        "websiteUrl": self._init_options.website_url,
                        "icons": self._init_options.icons,
                    }
                    if self._agent_brain_meta is not None:
                        impl_kwargs["_meta"] = dict(self._agent_brain_meta)
                    await responder.respond(
                        types.ServerResult(
                            types.InitializeResult(
                                protocolVersion=(
                                    requested_version
                                    if requested_version in SUPPORTED_PROTOCOL_VERSIONS
                                    else types.LATEST_PROTOCOL_VERSION
                                ),
                                capabilities=self._init_options.capabilities,
                                serverInfo=types.Implementation(**impl_kwargs),
                                instructions=self._init_options.instructions,
                            )
                        )
                    )
                self._initialization_state = InitializationState.Initialized
            case _:
                # Defer every other request type to the SDK parent.
                await super()._received_request(responder)


def _install_meta_injecting_session(server: Server) -> None:
    """Patch ``server.run`` to use :class:`_MetaInjectingServerSession`.

    The SDK's :meth:`Server.run` hard-codes
    ``ServerSession(read_stream, write_stream, init_options,
    stateless=stateless)`` inline; the only surgical way to substitute
    our subclass is to wrap the method on the instance. This is the
    "Plan 03 carry-forward Plan 02 SUMMARY's option (b)" — extending
    ``build_server``'s capability-patching wrapper so the substitution
    works for stdio AND HTTP transports through the same code path.

    The wrapper mirrors :meth:`Server.run` from mcp 1.12.x verbatim
    (lines 640-690 of mcp/server/lowlevel/server.py) with the single
    substitution noted above. SDK version pin is the same as for
    :class:`_MetaInjectingServerSession`.
    """
    original_run = server.run

    async def _run(  # type: ignore[no-untyped-def]
        read_stream,
        write_stream,
        initialization_options,
        raise_exceptions: bool = False,
        stateless: bool = False,
    ) -> None:
        # Body mirrors mcp/server/lowlevel/server.py:640-690 with the
        # ``ServerSession`` substitution. See the class docstring for
        # the SDK pin rationale.
        async with AsyncExitStack() as stack:
            lifespan_context = await stack.enter_async_context(server.lifespan(server))
            session = await stack.enter_async_context(
                _MetaInjectingServerSession(
                    read_stream,
                    write_stream,
                    initialization_options,
                    stateless=stateless,
                )
            )
            # Inject the meta dict captured in build_server.
            session._agent_brain_meta = getattr(server, "_agent_brain_meta", None)

            # Configure task support for this session if enabled. Mirrors
            # the SDK's check on ``self._experimental_handlers``.
            task_support = (
                server._experimental_handlers.task_support
                if server._experimental_handlers
                else None
            )
            if task_support is not None:
                task_support.configure_session(session)
                await stack.enter_async_context(task_support.run())

            async with anyio.create_task_group() as tg:
                try:
                    async for message in session.incoming_messages:
                        logger.debug("Received message: %s", message)
                        tg.start_soon(
                            server._handle_message,
                            message,
                            session,
                            lifespan_context,
                            raise_exceptions,
                        )
                finally:
                    tg.cancel_scope.cancel()

    # Stash the original on the instance so tests can introspect / restore.
    server._agent_brain_original_run = original_run  # type: ignore[attr-defined]
    server.run = _run  # type: ignore[method-assign]


async def run_stdio(server: Server, subscription_manager: SubscriptionManager) -> None:
    """Run the MCP server over stdio until the client disconnects.

    Phase 52: the ``capabilities`` blob now advertises
    ``resources.subscribe: true`` (flipped by the wrapper in
    :func:`build_server`).

    Plan 04 disconnect-cleanup contract: the inner ``server.run`` call
    is wrapped in ``try / finally`` so a stdio EOF (the MCP client
    closing the pipe) or an exception triggers
    :meth:`SubscriptionManager.cleanup_all` on the way out. That
    guarantees no polling task survives a client disconnect — Phase 52
    CONTEXT decision D, layer 1 ("MCP SDK layer cleanup hook"). The
    HTTP transport analog will land alongside Phase 53; the per-task
    guard in :meth:`SubscriptionManager._poll_loop` (Plan 01 / Plan 04
    explicit ``CancelledError`` clause) is the layer-2 defense-in-depth.
    """
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        try:
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=SERVER_NAME,
                    server_version=__version__,
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(
                            prompts_changed=False,
                            resources_changed=False,
                            tools_changed=False,
                        ),
                        experimental_capabilities={},
                    ),
                    instructions=(
                        "Agent Brain MCP v2 — 7 tools, 5 resources, "
                        "6 prompts, stdio. Resources support "
                        "subscribe/unsubscribe; per-URI policies are "
                        "wired for job://, corpus://status, corpus://folders."
                    ),
                ),
            )
        finally:
            # Plan 04 disconnect-cleanup. Calls cleanup_all() on EVERY
            # exit path — graceful EOF, client crash, mid-loop
            # exception. ``cleanup_all`` is idempotent (empty registry
            # returns 0) so re-entrancy is safe.
            cleaned = subscription_manager.cleanup_all()
            if cleaned:
                logger.info(
                    "subscription cleanup: cancelled %d polling task(s) on "
                    "session close",
                    cleaned,
                )


# Phase 53 Plan 02: ``run_http`` lives in :mod:`agent_brain_mcp.http`
# (Starlette + uvicorn wiring is too involved to keep co-located with
# the stdio path). Plan 01's local ``NotImplementedError`` stub was
# replaced by the module-top re-export below — callers that already
# import ``from agent_brain_mcp.server import run_http`` keep working
# unchanged.


async def main_async(
    *,
    backend: str | None = None,
    backend_url: str | None = None,
    state_dir: str | None = None,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Entry point for the ``agent-brain-mcp`` CLI command.

    Phase 53 Plan 01 adds the listen-transport dispatcher. The default
    (``transport="stdio"``) preserves the v1/Phase 52 behavior verbatim.
    ``transport="http"`` reaches the Plan 02 stub
    (:func:`run_http`) which raises :class:`NotImplementedError`.

    Args:
        backend: Backend httpx transport label (``"auto"`` / ``"uds"`` /
            ``"http"``) — controls how this MCP server reaches
            ``agent-brain-serve``. Orthogonal to ``transport`` per
            Phase 53 D-01.
        backend_url: Explicit HTTP base URL for the backend (overrides
            UDS auto-discovery).
        state_dir: Override the Agent Brain state directory used to
            locate UDS socket + runtime.json.
        transport: Listen-side transport (``"stdio"`` / ``"http"``).
            Click's :class:`click.Choice` rejects anything else at the
            CLI layer; the defensive ``ValueError`` branch below catches
            direct callers (e.g., tests) that bypass Click.
        host: Host to bind for ``transport="http"``. Ignored by the
            stdio path. Plan 02 enforces the loopback whitelist.
        port: TCP port for ``transport="http"``. Ignored by the stdio
            path.
    """
    from pathlib import Path

    from .config import open_backend_client

    try:
        backend_transport, httpx_client = open_backend_client(
            backend=backend,  # type: ignore[arg-type]
            backend_url=backend_url,
            state_dir=Path(state_dir).expanduser() if state_dir else None,
        )
    except Exception as e:
        raise_backend_unavailable(e)
        return

    # Version-compat check (plan §12.3 #14).
    api = ApiClient(httpx_client)
    try:
        health = api.server_health()
        actual_version = str(health.get("version", "0.0.0"))
        check_backend_version(actual_version)
    except McpError:
        # Re-raise to abort startup cleanly.
        httpx_client.close()
        raise

    server, subscription_manager = build_server(
        httpx_client,
        backend_transport=backend_transport,
        listen_transport=transport,
    )
    try:
        # Phase 53 Plan 01: dispatch on the listen-side transport.
        # No silent fallback (HTTP-03): unrecognized values raise; an
        # HTTP failure does NOT downgrade to stdio (and vice versa).
        if transport == "stdio":
            await run_stdio(server, subscription_manager)
        elif transport == "http":
            await run_http(server, subscription_manager, host=host, port=port)
        else:
            # Click's Choice already rejects invalid values; this guard
            # is for direct callers (tests, embeddings) that bypass the
            # CLI wrapper.
            raise ValueError(f"Unknown transport: {transport!r}")
    finally:
        httpx_client.close()
