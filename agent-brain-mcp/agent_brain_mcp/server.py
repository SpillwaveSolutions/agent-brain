"""MCP stdio server — wires the registries into the low-level Server.

Capabilities advertised (plan §6.1):
  tools.listChanged   = False
  resources.subscribe = False
  resources.listChanged = False
  prompts.listChanged = False

No sampling / elicitation / logging / completions / subscriptions in v1.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from typing import Any

import httpx
import mcp.server.stdio
import mcp.types as types
from mcp import McpError
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.models import InitializationOptions
from mcp.types import ErrorData
from pydantic import AnyUrl, ValidationError

from . import __version__
from .client import ApiClient
from .errors import INVALID_PARAMS, raise_backend_unavailable
from .prompts import PROMPT_REGISTRY
from .resources import PARAMETERIZED_HANDLERS, RESOURCE_REGISTRY, parse_uri
from .schemas import json_schema
from .tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)

SERVER_NAME = "agent-brain"
# Lowest server /health/ ``version`` that this MCP build is compatible with.
MIN_BACKEND_VERSION = "10.0.7"


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


def build_server(httpx_client: httpx.Client, *, transport: str = "http") -> Server:
    """Construct and configure the low-level MCP ``Server`` instance."""
    server: Server = Server(SERVER_NAME, version=__version__)

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
        # Run the sync handler in a thread so the asyncio event loop stays
        # responsive (plan §6.4 / §12.3 #12). A blocking httpx call inline
        # in an async def would freeze stdio and defeat MCP
        # ``notifications/cancelled``.
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

    @server.read_resource()
    async def read_resource(uri: AnyUrl) -> list[ReadResourceContents]:
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
            content = await handler(api, parsed)
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

    server._agent_brain_transport = transport  # type: ignore[attr-defined]
    return server


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
    return f"{tool_name} → ok"


async def run_stdio(server: Server) -> None:
    """Run the MCP server over stdio until the client disconnects."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
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
                    "Agent Brain MCP v1 — 7 tools, 5 resources, 6 prompts, "
                    "stdio. Read-only resources (no subscriptions in v1)."
                ),
            ),
        )


async def main_async(
    *,
    backend: str | None = None,
    backend_url: str | None = None,
    state_dir: str | None = None,
) -> None:
    """Entry point for the ``agent-brain-mcp`` CLI command."""
    from pathlib import Path

    from .config import open_backend_client

    try:
        transport, httpx_client = open_backend_client(
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

    server = build_server(httpx_client, transport=transport)
    try:
        await run_stdio(server)
    finally:
        httpx_client.close()
